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
    # Verbs/quantifiers that follow "mi <relation>" far more often than a name
    # does ("mi hija tiene 5 años"). Without these the family-relation frames
    # below would drop most sentences about a relative's health, age or
    # status rather than the rare ones that actually state a name.
    "tiene", "esta", "está", "necesita", "es", "no", "se", "ya", "todavia",
    "todavía", "tambien", "también", "nacio", "nació", "cumple", "va",
    "fue", "quiere", "sufre", "padece",
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

# Family-relation frames. This is the single most common place a name appears
# in this corpus — introducing a family member — and it was the gap the
# reviewer found: "mi hija xiomara" has no frame and (before this fix) no
# gazetteer entry either. Same lowercase-only gating as _THIRD_PARTY_FRAMES:
# a capitalised name after "mi hija" is still NER's job.
_FAMILY_FRAMES = [
    re.compile(
        r"\bmi\s+(?:hija|hijo|esposa|esposo|mam[aá]|pap[aá]|madre|padre|"
        r"hermana|hermano|abuela|abuelo|nieta|nieto|sobrina|sobrino|"
        r"prima|primo|t[ií]a|t[ií]o|cuñada|cuñado|pareja|novia|novio|"
        r"vecina|vecino)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)",
        re.I,
    ),
]


# Layer 2's third rung. Frames (above) close the phrasings we anticipated —
# "me llamo X", "hable con X" — but cannot close the ones we did not think of.
# spaCy tags PER largely off capitalisation, and this corpus is lowercase
# phone-typed Spanish, so a bare first name with no frame around it and no
# capital letter on it is invisible to both Layer 1 and the frame regexes.
# This gazetteer keys on the name itself rather than on the words around it,
# so it is the only layer that still works when both capitalisation and the
# surrounding frame are absent.
#
# Known cost: a message like "mi hija sofia esta enferma" gets dropped even
# though the name is incidental to the message's content. That is accepted —
# drops cost coverage of the corpus, not rows in the output, because the
# sampler refills each bucket from the next candidate.
#
# Traditional Spanish/Latin-American names plus the Venezuelan-specific
# coinages common in this population (yorbelis, yusmary, keiber, ...) that
# generic Spanish name lists omit.
#
# HONEST LIMIT: this is a finite list. A name absent from it, spoken with no
# capital letter and no frame around it, WILL pass through unscrubbed — this
# layer cannot and does not guarantee completeness, only that it catches the
# names someone thought to add. That is why the sample this feeds is read
# end-to-end by a human before it ships, not because this layer is expected
# to be enough on its own.
_FIRST_NAMES = frozenset({
    # Traditional female
    "maria", "ana", "rosa", "carmen", "isabel", "laura", "sofia", "valentina",
    "camila", "andrea", "paola", "carolina", "daniela", "gabriela", "patricia",
    "monica", "claudia", "diana", "alejandra", "natalia", "viviana", "sandra",
    "martha", "marcela", "adriana", "liliana", "yolanda", "gloria", "elena",
    "teresa", "cristina", "lucia", "victoria", "fernanda", "jimena", "ximena",
    "catalina", "juliana", "mariana", "valeria", "luisa", "beatriz",
    "esperanza", "consuelo", "dolores", "pilar", "rocio", "nubia", "amparo",
    "alicia", "ines", "mercedes", "angela", "marisol", "milagros", "milena",
    "noemi", "ruth", "raquel", "sara", "rebeca", "abigail", "dulce", "karina",
    "karla", "carla", "sarai", "ivonne", "brenda", "tania", "tatiana",
    "veronica", "vanessa", "samantha", "stefany", "stephanie", "estefania",
    "fabiola", "francia", "hilda", "jacqueline", "janeth", "katherine",
    "kimberly", "leidy", "lizeth", "luz", "magaly", "maribel", "marina",
    "marisela", "michelle", "nataly", "oriana", "paula", "roxana", "silvia",
    "soraya", "wendy", "zoraida", "yesenia", "yamile", "yaneth", "yuliana",
    "yudith", "nayeli", "nayibe", "dayana", "dayanara", "yusmary", "yolimar",
    "yoselin", "yohana", "yenifer", "jenifer", "keila", "keyla", "kelly",
    "greisy", "greicy", "deisy", "deysi", "luzmila", "marleny", "marlin",
    "marlene", "yesica", "yeimy", "yeisy", "yorbelis", "yulieth", "yudi",
    "belkis", "damaris", "eglee", "eglis", "yhajaira", "yajaira", "zulay",
    "zuleima", "genesis", "genesys", "anyelina", "anyeli", "estrella",
    "esneida", "yubisay", "yumaira", "yusneidy",
    # Additional Venezuelan/Colombian coinages (y-/j-initial and otherwise)
    # found missing on review — a genuine pass for frequency, not padding.
    "xiomara", "katiuska", "maryuri", "yurani", "yuraima", "marilyn",
    "marilin", "yulimar", "yusleidy", "yeraldin", "geraldine", "anyela",
    "anyi", "yurley", "yumary", "dailyn", "yorley", "breidy", "franyelis",
    "yulisbeth", "anggie", "angie", "yesibel", "luzney", "yeraldine",
    "maiber", "maigualida", "neidy", "neiry", "zulmary", "zuly", "yolvia",
    "dubraska", "keily", "keyra", "yasmin", "jazmin", "yoletzy",
    "yoleidy", "yorgelis", "yosmely", "yosneidy", "yulieska", "franyi",
    "keismary", "keimary", "leidymar", "durley", "yolanny", "yubelkis",
    # Traditional male
    "jose", "luis", "carlos", "juan", "miguel", "antonio", "francisco",
    "daniel", "gabriel", "pedro", "jesus", "andres", "felipe", "alejandro",
    "fernando", "ricardo", "roberto", "jorge", "sergio", "cesar", "oscar",
    "oswaldo", "eduardo", "enrique", "rafael", "ramon", "martin", "victor",
    "ivan", "alberto", "alfredo", "arturo", "armando", "angel", "anibal",
    "benjamin", "bernardo", "cristian", "dario", "david", "diego", "domingo",
    "edgar", "edwin", "efrain", "elias", "emiro", "ernesto", "esteban",
    "ezequiel", "federico", "freddy", "gerardo", "german", "gilberto",
    "gonzalo", "gregorio", "guillermo", "gustavo", "hector", "henry",
    "heriberto", "hernan", "hugo", "humberto", "ignacio", "isidro", "ismael",
    "jairo", "javier", "jefferson", "joaquin", "johan", "jhon", "jhoan",
    "jhonny", "joel", "jonathan", "josue", "julio", "justo", "kevin",
    "leandro", "leonardo", "leonel", "lorenzo", "lucas", "manuel", "marco",
    "marcos", "mario", "mauricio", "maximiliano", "moises", "nelson",
    "nestor", "nicolas", "norberto", "octavio", "orlando", "pablo",
    "patricio", "rene", "reinaldo", "reynaldo", "rigoberto", "rodrigo",
    "rolando", "ruben", "salvador", "samuel", "santiago", "saul", "sebastian",
    "simon", "tomas", "ulises", "vicente", "walter", "wilfredo", "wilfrido",
    "william", "wilmer", "wilson", "yeison", "yeferson", "yerson", "yorman",
    "yordan", "yosman", "deiber", "deiver", "deivi", "keiber", "keivin",
    "keny", "kleiver", "kleider", "junior", "maiker", "maikol", "maykol",
    "breiner", "brayan", "brandon", "franklin", "franyi", "frangel",
    "geordy", "geraldo", "yeimer", "yerlin", "yorvin", "eliexer", "eliecer",
    "yeiker", "yeikol", "neiker", "neomar", "reimer", "reinier", "jeanpiere",
    # Additional Venezuelan/Colombian coinages (y-/j-initial and otherwise)
    # found missing on review — a genuine pass for frequency, not padding.
    "anderson", "yeimar", "yosimar", "yorvis", "yulexis", "anyerson",
    "maikel", "maickol", "jeanfranco", "jeandry", "jeampiere", "kleimer",
    "kleyver", "yorbis", "yeriel", "deiker", "deinis", "neider", "jhonder",
    "jhorman", "jheisson", "jheferson", "jhonatan", "yohander", "yoiber",
    "yoendris", "franyer", "francys", "kendry", "kender", "maiko",
    "maikelson", "ronal", "yulio", "yeikel", "leidyber",
    "jeanpierre", "yorwin", "keinner", "kleyner",
})

_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+")

# `es_core_news_sm` tags sentence-initial capitalised tokens as PER on this
# corpus: phone keyboards auto-capitalise the first word of a message, and
# "Quisiera", "Cuales", "Buenas" etc. get mislabelled as a person's name.
# Measured on a real pipeline run: 21/138 sampled rows had a Layer-1
# redaction applied, and every single one was this false positive, not a
# real name. This is a fixed, named list of the SPECIFIC words the model
# mistags — not a positional rule. An earlier version of scrub() also
# distrusted PER purely by sentence-initial position (regardless of whether
# the word was on this list), which silently let real sentence-initial
# names ship unredacted; that was reverted. Matched case-insensitively, and
# applied wherever the word appears — not just sentence-initially — since it
# is never a name in this corpus regardless of position.
_OPENER_STOPLIST = frozenset({
    "quisiera", "quiero", "queria", "quería", "quisieramos", "quisiéramos",
    "deseo", "necesito", "tengo", "podria", "podría", "puedo", "cuales",
    "cuáles", "cual", "cuál", "cuando", "cuándo", "como", "cómo", "donde",
    "dónde", "quien", "quién", "porque", "porqué", "buenas", "buenos",
    "hola", "gracias", "disculpe", "disculpa", "perdon", "perdón", "señor",
    "señora", "señores", "estimado", "estimada", "estimados", "saludos",
    "cordialmente", "atentamente", "porfavor", "favor", "ayuda",
    "informacion", "información", "solicito", "solicite", "solicité",
    "ingrese", "ingresé",
})

def contains_known_first_name(text: str) -> bool:
    """True when a whole word in text matches the gazetteer, case-insensitive.

    Whole-word only: a substring check would fire on "ana" inside "mañana",
    "semana", "ventana" and gut the sample for no safety gain.
    """
    if not text:
        return False
    return any(w.lower() in _FIRST_NAMES for w in _WORD.findall(text))


def has_self_identification(text: str) -> bool:
    """True when the message announces a person's name in a frame NER misses."""
    if not text:
        return False
    if any(p.search(text) for p in _FRAMES):
        return True
    m = _SOY.search(text)
    if m and m.group(1).lower() not in _NOT_NAMES:
        return True
    for pattern in _THIRD_PARTY_FRAMES + _FAMILY_FRAMES:
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
    # The gazetteer runs alongside the frame checks — it is the layer that
    # still works when a bare name has neither a capital letter nor a frame.
    if has_self_identification(text) or contains_known_first_name(text):
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
    #
    # A PER span is distrusted ONLY when its lowercased text is on the opener
    # stoplist (above) — regardless of position. Position alone is NOT a
    # signal: a prior version of this rule also distrusted any sentence-initial
    # PER absent from the gazetteer, on the theory that a genuine
    # sentence-initial name would already have been dropped by the gazetteer.
    # That reasoning only holds for names actually IN the 400-entry gazetteer.
    # A real name spaCy correctly tags as PER but that isn't in the gazetteer
    # (e.g. "Ingrid me acompano...") was shipping untouched — a name leak, not
    # a false-positive fix. The stoplist names the SPECIFIC words this model
    # mistags on this corpus; anything else the model calls a person is
    # treated as a person and gets redacted. Expect a little over-redaction
    # for openers not yet on the stoplist — that is the safe failure
    # direction, and a recurring one gets added to the stoplist.
    changed = False
    if nlp is not None:
        pers = sorted(
            (e for e in nlp(text).ents if e.label_ == "PER"),
            key=lambda e: e.start_char,
        )
        to_redact = []
        for ent in pers:
            if ent.text.lower() in _OPENER_STOPLIST:
                continue
            to_redact.append(ent)
        for prev, cur in zip(to_redact, to_redact[1:]):
            if cur.start_char < prev.end_char:
                return None, False
        for ent in reversed(to_redact):
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
