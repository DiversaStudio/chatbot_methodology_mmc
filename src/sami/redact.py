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

# Capitalised tokens that follow "soy" but are not people. Without these the
# "soy <Capitalised>" rule drops a large share of a corpus in which stating
# one's nationality is the single most common opening move.
_NOT_NAMES = frozenset({
    "venezolana", "venezolano", "colombiana", "colombiano", "ecuatoriana",
    "ecuatoriano", "madre", "padre", "mama", "papa", "migrante", "refugiada",
    "refugiado", "beneficiaria", "beneficiario", "estudiante", "menor",
})

# NOTE: `_SOY` is deliberately NOT case-insensitive. The capital letter IS the
# signal that the following token is a proper noun. Adding re.I here would make
# the rule fire on every "soy venezolana" in the corpus.
_SOY = re.compile(r"\bsoy\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)")
_FRAMES = [
    re.compile(r"\bme\s+llamo\b", re.I),
    re.compile(r"\bmi\s+nombre\s+es\b", re.I),
    re.compile(r"\bse(?:ñ|n)or(?:a)?\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+", re.I),
]


def has_self_identification(text: str) -> bool:
    """True when the message announces a person's name in a frame NER misses."""
    if not text:
        return False
    if any(p.search(text) for p in _FRAMES):
        return True
    m = _SOY.search(text)
    return bool(m and m.group(1).lower() not in _NOT_NAMES)


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
    changed = False
    if nlp is not None:
        for ent in nlp(text).ents:
            if ent.label_ == "PER" and ent.text in text:
                text = text.replace(ent.text, NAME_PLACEHOLDER)
                changed = True

    # Layer 3: the pipeline's own gate, applied to the OUTPUT. Anything that
    # survives redaction here was never safe to begin with.
    if any(p.search(text) for p in qa._PII_PATTERNS):
        return None, False
    return text, changed
