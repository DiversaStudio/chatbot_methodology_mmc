"""Three-layer scrub for the message-example sample.

Layer 1 is spaCy NER. Layer 2 is a regex tripwire that runs INDEPENDENTLY of
NER, and it is the reason this module exists rather than a one-line call into
spacy: `es_core_news_sm` tags PER largely off capitalisation, and this corpus
is lowercase phone-typed Spanish. "me llamo maria" slips past the model. Layer 3
re-runs the pipeline's existing PII gate on the output.

Layer 2 DROPS rather than redacts. That asymmetry is deliberate: when a name is
suspected but cannot be located precisely enough to replace, the safe move is to
lose the message, not to ship a partially-scrubbed one. Drops cost coverage, and
the sampler refills the bucket from the next candidate.
"""
from __future__ import annotations
import re

from . import qa

NAME_PLACEHOLDER = "[nombre]"

# Words that show up right after a naming frame but are not people. Function
# words (de, la, un...) and self-descriptions (soltera, desplazado...) are the
# two big categories that would otherwise get reject-on-doubt dropped for no
# safety gain — stating nationality, marital status, or displacement status is
# some of the most common opening text in this corpus.
_NOT_NAMES = frozenset({
    "venezolana", "venezolano", "colombiana", "colombiano", "ecuatoriana",
    "ecuatoriano", "madre", "padre", "mama", "papa", "migrante", "refugiada",
    "refugiado", "beneficiaria", "beneficiario", "estudiante", "menor",
    "de", "del", "la", "el", "las", "los", "un", "una", "mi", "muy",
    "mayor", "nueva", "nuevo", "soltera", "soltero", "casada", "casado",
    "embarazada", "discapacitada", "discapacitado", "desplazada", "desplazado",
    "victima", "adulta", "adulto", "joven", "persona", "mujer", "hombre",
})

# The verb is matched case-insensitively via the scoped inline flag `(?i:soy)`
# so re.I never leaks onto the captured name group — phone keyboards
# auto-capitalise the first letter of a message ("Soy andrea...") while the
# typed name itself stays lowercase, and that lowercase name is still the
# thing we need to catch. The capture no longer requires a capital letter:
# capitalisation stopped being the signal. Instead any token that is NOT a
# known non-name (see _NOT_NAMES) triggers a drop, regardless of its case —
# reject-on-doubt. Over-dropping costs coverage; under-dropping ships a name.
_SOY = re.compile(r"\b(?i:soy)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)")

# Unconditional: presence alone is the signal, no name-token check needed.
_FRAMES = [
    re.compile(r"\bme\s+llamo\b", re.I),
    re.compile(r"\bmi\s+nombre\s+es\b", re.I),
    re.compile(r"\bse(?:ñ|n)or(?:a)?\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+", re.I),
]

# Third-party mention frames (bounded to the common ones in this corpus, per
# review — a general gazetteer is being decided separately, not added here).
# These are gated to LOWERCASE captures only: a capitalised name here is
# NER's job (Layer 1 already redacts it, see scrub()), and dropping those too
# would fight Layer 1 instead of backing it up. The gap this closes is the
# lowercase name NER cannot see because es_core_news_sm leans on
# capitalisation — the same blind spot that motivates this whole module.
_THIRD_PARTY_FRAMES = [
    re.compile(r"\bhabl[eé]\s+con\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
    re.compile(r"\bme\s+atendi[oó]\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
    re.compile(r"\bpregunt[eé]\s+por\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
    re.compile(r"\bme\s+dijo\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
    re.compile(r"\b(?:el|la)\s+doctor(?:a)?\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
    re.compile(r"\b(?:el|la)\s+abogad[oa]\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
    re.compile(r"\b(?:el|la)\s+trabajador(?:a)?\s+social\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.I),
]


def has_self_identification(text: str) -> bool:
    """True when the message announces a person's name in a frame NER misses."""
    if not text:
        return False
    if any(p.search(text) for p in _FRAMES):
        return True
    m = _SOY.search(text)
    if m and m.group(1).lower() not in _NOT_NAMES:
        return True
    for pattern in _THIRD_PARTY_FRAMES:
        m = pattern.search(text)
        if m:
            token = m.group(1)
            if token[:1].islower() and token.lower() not in _NOT_NAMES:
                return True
    return False


def load_ner():
    """The es_core_news_sm pipeline with everything but NER disabled."""
    import spacy
    return spacy.load("es_core_news_sm", exclude=["lemmatizer", "tagger", "parser"])


def scrub(text, nlp=None) -> "tuple[str | None, bool]":
    """Return (clean_text, was_changed), or (None, False) to DROP the message.

    `nlp=None` skips layer 1 and runs layers 2 and 3 only. Tests use it; the
    pipeline always passes a real model.
    """
    if not text or not str(text).strip():
        return None, False
    text = str(text)

    # Layer 2 first: it is a drop, so there is no point scrubbing before it.
    if has_self_identification(text):
        return None, False

    # Layer 1: person names out, places and organisations kept. Cities are
    # already public in dim_city, and the organisations ARE the finding.
    #
    # Replacement is by character OFFSET, not str.replace on the entity text:
    # str.replace on a shorter span (e.g. "Ana") also eats the prefix of a
    # longer overlapping span ("Ana Maria Rodriguez"), and the longer span's
    # `in text` guard then silently fails, shipping "Maria Rodriguez" in
    # clear while reporting changed=True. Overlapping spans are therefore
    # refused outright rather than guessed at — this is a privacy backstop,
    # and a redaction that cannot be applied cleanly must never be a silent
    # no-op; the safe move is to drop the whole message.
    changed = False
    if nlp is not None:
        pers = sorted(
            (e for e in nlp(text).ents if e.label_ == "PER"),
            key=lambda e: e.start_char,
        )
        for prev, cur in zip(pers, pers[1:]):
            if cur.start_char < prev.end_char:
                return None, False
        for ent in reversed(pers):
            start, end = ent.start_char, ent.end_char
            if text[start:end] != ent.text:
                # Offsets don't line up with the text being scrubbed — refuse
                # rather than guess where the name actually is.
                return None, False
            text = text[:start] + NAME_PLACEHOLDER + text[end:]
            changed = True

    # Layer 3: the pipeline's own gate, applied to the OUTPUT. Anything that
    # survives redaction here was never safe to begin with.
    if any(p.search(text) for p in qa._PII_PATTERNS):
        return None, False
    return text, changed
