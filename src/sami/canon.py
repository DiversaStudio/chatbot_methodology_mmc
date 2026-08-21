"""Canonical dictionaries and mapping for city / nationality / duration."""
from __future__ import annotations
import unicodedata
import pandas as pd

# 10 MMC priority cities + common variants -> canonical display name
CITY_CANON: dict[str, str] = {
    "medellin": "Medellín", "medellin antioquia": "Medellín", "belen": "Medellín",
    "bogota": "Bogotá", "bogota dc": "Bogotá",
    "cucuta": "Cúcuta",
    "barranquilla": "Barranquilla",
    "santa marta": "Santa Marta",
    "cali": "Cali",
    "cartagena": "Cartagena",
    "bucaramanga": "Bucaramanga",
    "ipiales": "Ipiales",
    "pasto": "Pasto",
    "riohacha": "Riohacha", "maicao": "Maicao",
    "soacha": "Soacha", "soacha cundinamarca": "Soacha",
    "necocli": "Necoclí",
}
# tokens that are regions/countries, not a priority city
NON_CITY: set[str] = {"colombia", "cundinamarca", "antioquia", "otra", "nan", ""}
# short/ambiguous aliases that must only match exactly, never as a "<key> <tail>" prefix
# (e.g. "Belen de Umbria" and "Calima" are distinct municipalities, not Medellín/Cali)
EXACT_ONLY: set[str] = {"belen", "cali"}


def fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def is_non_city(name) -> tuple[bool, str]:
    """Return (excluded, reason). Reason is '' when it is a mappable city."""
    if name is None:
        return True, "missing"
    key = fold(name)
    if key == "" or key == "nan":
        return True, "missing"
    if key.isdigit():
        return True, "numeric token"
    if key in NON_CITY:
        return True, "country/region, not a city"
    return False, ""


def city_canon(name) -> str:
    excluded, _ = is_non_city(name)
    if excluded:
        return "Otra"
    key = fold(name)
    if key in CITY_CANON:
        return CITY_CANON[key]
    for k, v in CITY_CANON.items():  # startswith match for "<city> <tail>"
        if k in EXACT_ONLY:
            continue
        if key.startswith(k + " "):  # exact matches already returned above
            return v
    return "Otra"


def clean_city(raw_city, city_other) -> str:
    raw = ("" if raw_city is None else str(raw_city)).strip()
    other = "" if city_other is None or pd.isna(city_other) else str(city_other).strip()
    if raw == "Otra" and other:
        return other.title()
    return raw


# --- nationality --------------------------------------------------------------
# Measured July export: Venezuela 905, Ecuador 9, Peru 3, United States 2.
# Values stay in the source language of the field (English country names here);
# only chart text is translated. Keyed on fold() so accents/case never matter.
NATIONALITY_CANON: dict[str, str] = {
    "venezuela": "Venezuela", "venezolana": "Venezuela", "venezolano": "Venezuela",
    "ecuador": "Ecuador", "ecuatoriana": "Ecuador", "ecuatoriano": "Ecuador",
    "peru": "Peru", "peruana": "Peru", "peruano": "Peru",
    "colombia": "Colombia", "colombiana": "Colombia", "colombiano": "Colombia",
    "united states": "United States", "estados unidos": "United States",
    "cuba": "Cuba", "cubana": "Cuba", "cubano": "Cuba",
    "panama": "Panama", "panamena": "Panama", "panameno": "Panama",
    "chile": "Chile", "chilena": "Chile", "chileno": "Chile",
    "argentina": "Argentina",
    "brasil": "Brazil", "brazil": "Brazil", "brasilena": "Brazil", "brasileno": "Brazil",
    "haiti": "Haiti", "haitiana": "Haiti", "haitiano": "Haiti",
    "mexico": "Mexico", "mexicana": "Mexico", "mexicano": "Mexico",
    "nicaragua": "Nicaragua", "costa rica": "Costa Rica",
    "el salvador": "El Salvador",
    "republica dominicana": "Dominican Republic",
    "noruega": "Norway", "norway": "Norway",
    "bulgaria": "Bulgaria", "india": "India",
    "mexico mexicana": "Mexico",
    # Bare "Otro"/"Otra" with no *_other elaboration (clean_nationality only
    # substitutes *_other when the raw field IS "Otra"/"Otro" -- see there):
    # a respondent who picked the free-text option and then left it blank.
    # Without these two entries the value survives is_plausible_nationality
    # (single alpha word, no junk marker) and title-cases to its own literal
    # "Otro" bucket, sitting apart from -- and duplicating the meaning of --
    # the real Desconocida/Unknown catch-all every other non-answer lands in.
    # Measured 2026-08-20 real export: 6 rows.
    "otro": "Desconocida", "otra": "Desconocida",
}

UNKNOWN_NATIONALITY = "Desconocida"

# Longest real entry above is "republica dominicana" (2 words). Three allows
# headroom for e.g. "trinidad and tobago" without admitting free-text answers.
_MAX_NATIONALITY_WORDS = 3

# Free-text survey answers announce themselves with first-person / verb words a
# country name never contains ("Soy Colombovenezolana" -> folded tokens "soy",
# "colombovenezolana"). Deliberately NOT articles/prepositions ("de", "la",
# "el", "y") -- those appear inside real country names ("Costa de Marfil",
# "República de Corea", "Trinidad y Tobago") and would reject them. Country
# names that are two or three words - "costa rica", "republica dominicana",
# "estados unidos", "trinidad and tobago" - contain none of these sentence
# markers, so the guard is safe to apply on top of the word-count check rather
# than instead of it.
_NON_COUNTRY_TOKENS = frozenset({"soy", "yo", "mi", "me", "era"})


def is_plausible_nationality(key: str) -> bool:
    """Could `key` (already fold()ed) be a country name we simply don't list?

    `nationality_canon` passes unlisted values through so a legitimate country
    missing from the map is not destroyed. Without a guard that also preserves
    the survey's junk: the 2026-08-03 export carried the literal strings "1",
    "3", "4" and "Soy Colombovenezolana" as distinct nationalities, which is
    what makes the column unusable as a report slicer.

    Rejects input with no letters (numeric codes), input too long to be a
    country name (free-text sentences), and input containing a Spanish
    first-person/function word (free-text sentences that happen to be short,
    like "Soy Colombovenezolana"). Everything else passes.
    """
    key = fold(key)
    if not key or not any(ch.isalpha() for ch in key):
        return False
    words = key.split()
    if len(words) > _MAX_NATIONALITY_WORDS:
        return False
    return not (set(words) & _NON_COUNTRY_TOKENS)


def clean_nationality(raw, other) -> str:
    """Consolidate Nationality with its *_other free-text fallback (P4)."""
    raw_s = ("" if raw is None or pd.isna(raw) else str(raw)).strip()
    other_s = "" if other is None or pd.isna(other) else str(other).strip()
    if raw_s in ("", "Otra", "Otro") and other_s:
        raw_s = other_s
    return raw_s


def nationality_canon(name) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return UNKNOWN_NATIONALITY
    key = fold(name)
    if key in ("", "nan", "none"):
        return UNKNOWN_NATIONALITY
    if key in NATIONALITY_CANON:
        return NATIONALITY_CANON[key]
    if not is_plausible_nationality(key):
        return UNKNOWN_NATIONALITY
    return str(name).strip().title()


# --- department of the priority cities (for the choropleth) --------------------
DEPARTMENT_OF_CITY: dict[str, str] = {
    "Medellín": "Antioquia",
    "Bogotá": "Bogotá",  # Natural Earth names the capital district "Bogota" (fold-matched in geo.py)
    "Cúcuta": "Norte de Santander",
    "Barranquilla": "Atlántico",
    "Santa Marta": "Magdalena",
    "Cali": "Valle del Cauca",
    "Cartagena": "Bolívar",
    "Bucaramanga": "Santander",
    "Ipiales": "Nariño",
    "Pasto": "Nariño",
    "Riohacha": "La Guajira",
    "Maicao": "La Guajira",
    "Soacha": "Cundinamarca",
    "Necoclí": "Antioquia",
}


# Canonical city coordinates (lat, lon, decimal degrees) for the dashboard bubble
# map — the spec forbids geocoding-by-name. Keys must match DEPARTMENT_OF_CITY.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Bogotá": (4.7110, -74.0721),
    "Medellín": (6.2442, -75.5812),
    "Cali": (3.4516, -76.5320),
    "Barranquilla": (10.9685, -74.7813),
    "Cúcuta": (7.8939, -72.5078),
    "Cartagena": (10.3910, -75.4794),
    "Bucaramanga": (7.1193, -73.1227),
    "Santa Marta": (11.2408, -74.1990),
    "Ipiales": (0.8303, -77.6450),
    "Pasto": (1.2136, -77.2811),
    "Riohacha": (11.5444, -72.9072),
    "Maicao": (11.3776, -72.2389),
    "Soacha": (4.5794, -74.2140),
    "Necoclí": (8.4256, -76.7789),
}


def department_of(city_canon_name) -> str | None:
    """Department for a canonical city name; None for 'Otra'/unknown."""
    return DEPARTMENT_OF_CITY.get(city_canon_name)


# --- away-from-origin duration (ordered; NB1 time-away figure) -----------------
# The 5 measured Away_duration buckets, least -> most time away. Order index
# lets the notebook plot an ordered axis; EN display translates chart text only.
AWAY_DURATION_ORDER: list[str] = [
    "Menos de 1 mes",
    "Entre 1 a 3 meses",
    "Entre 3 meses y 1 año",
    "Entre 1 a 5 años",
    "Hace más de 5 años",
]
_AWAY_BY_FOLD: dict[str, str] = {fold(v): v for v in AWAY_DURATION_ORDER}
AWAY_DURATION_DISPLAY_EN: dict[str, str] = {
    "Menos de 1 mes": "< 1 month",
    "Entre 1 a 3 meses": "1–3 months",
    "Entre 3 meses y 1 año": "3–12 months",
    "Entre 1 a 5 años": "1–5 years",
    "Hace más de 5 años": "5+ years",
}


def away_duration_canon(raw) -> str | None:
    """Canonical Spanish label for an Away_duration value; None if unrecognized."""
    return _AWAY_BY_FOLD.get(fold(raw))


def away_duration_order(raw) -> int | None:
    """Sort index (0 = least time away) or None if unrecognized."""
    label = away_duration_canon(raw)
    return AWAY_DURATION_ORDER.index(label) if label is not None else None


# --- time in current city (ordered; NB2 §3 duration×city cut) ------------------
# The five structured City_duration survey buckets, verbatim from the export
# (the field also carries free-text answers, which canonicalize to None).
CITY_DURATION_ORDER: list[str] = [
    "Menos de 1 mes",
    "Entre 1 y 3 meses",
    "Entre 4 y 6 meses",
    "Entre 7 meses y 1 año",
    "Más de 1 año",
]
_CITY_BY_FOLD: dict[str, str] = {fold(v): v for v in CITY_DURATION_ORDER}
CITY_DURATION_DISPLAY_EN: dict[str, str] = {
    "Menos de 1 mes": "< 1 month",
    "Entre 1 y 3 meses": "1–3 months",
    "Entre 4 y 6 meses": "4–6 months",
    "Entre 7 meses y 1 año": "7–12 months",
    "Más de 1 año": "1+ year",
}


def city_duration_canon(raw) -> str | None:
    """Canonical Spanish label for a City_duration value; None if unrecognized."""
    return _CITY_BY_FOLD.get(fold(raw))


def city_duration_order(raw) -> int | None:
    """Sort index (0 = least time in city) or None if unrecognized."""
    label = city_duration_canon(raw)
    return CITY_DURATION_ORDER.index(label) if label is not None else None


# --- gender EN display --------------------------------------------------------
# `clean_gender` lets free text from Gender_other through verbatim, so the field
# carries self-reported variants ("transgenero", "Soy una mujer trans", "lgtbQ+",
# "Gay"). gender_display folds those into the closed EN legend the dashboard uses,
# which is four labels wide: Woman / Man / LGBTQ+ / Other or prefer not to say.
#
# Two merges, both driven by cell size rather than by taxonomy.
#
# 1. 2026-07-29 dashboard review: trans and non-binary self-descriptions join
#    **LGBTQ+** rather than standing as their own slice. Measured, they were 4 and
#    2 people; a named cell that small is re-identifying in a migrant population,
#    and the T is already inside the umbrella, so nothing is misrepresented.
#
# 2. 2026-07-30, owner request: "Otro" and "Prefiero no responder" merge into a
#    single bucket. This REVERSES the previous note here, which kept them apart on
#    the grounds that a stated identity and a refusal are different answers. That
#    reasoning was sound and is not what changed -- the counts are. "Other" is
#    3 people, below even the LGBTQ+ cell the review had already judged too small
#    to name.
#
#    The merged label is "Other or prefer not to say", NOT "Prefer not to say".
#    Folding a stated answer into a refusal label would report 3 people as having
#    declined when they did not. The joint label keeps both readings honest and
#    still removes the n = 3 cell.
#
# "Other" also absorbs unrecognized free text, so the bucket must never be read as
# "chose Other" alone -- another reason the label does not claim a specific answer.
GENDER_OTHER_OR_UNSTATED = "Other or prefer not to say"

GENDER_DISPLAY: dict[str, str] = {
    "Mujer": "Woman",
    "Hombre": "Man",
    "Prefiero no responder": GENDER_OTHER_OR_UNSTATED,
    "Otro": GENDER_OTHER_OR_UNSTATED,
}
_GENDER_VARIANTS: dict[str, str] = {
    "mujer": "Woman", "femenino": "Woman", "f": "Woman",
    "hombre": "Man", "masculino": "Man", "m": "Man",
    "transgenero": "LGBTQ+", "trans": "LGBTQ+",
    "mujer trans": "LGBTQ+", "soy una mujer trans": "LGBTQ+",
    "hombre trans": "LGBTQ+", "no binario": "LGBTQ+",
    "lgtbq+": "LGBTQ+", "lgbtq+": "LGBTQ+", "lgtbiq+": "LGBTQ+", "lgbtiq+": "LGBTQ+",
    "gay": "LGBTQ+", "lesbiana": "LGBTQ+", "bisexual": "LGBTQ+",
    "prefiero no responder": GENDER_OTHER_OR_UNSTATED,
    "otro": GENDER_OTHER_OR_UNSTATED, "otra": GENDER_OTHER_OR_UNSTATED,
}


def gender_display(raw) -> str:
    """Closed-set EN gender label for the dashboard legend.

    Empty/NA stays empty; anything unrecognized falls into the joint
    other/unstated bucket so the legend never grows an unplanned slice (and so
    free text can never leak to a chart)."""
    key = fold(raw)
    if key in ("", "nan", "none"):
        return ""
    return _GENDER_VARIANTS.get(key, GENDER_OTHER_OR_UNSTATED)


def clean_gender(raw, other) -> str:
    """Consolidate Gender with its *_other free-text fallback (P4)."""
    raw_s = ("" if raw is None or pd.isna(raw) else str(raw)).strip()
    other_s = "" if other is None or pd.isna(other) else str(other).strip()
    if raw_s in ("", "Otro", "Otra") and other_s:
        return other_s
    return raw_s


# --- remaining Spanish survey vocabularies -> EN dashboard display -------------
# The gold layer is English end-to-end (the analysis frames keep the Spanish
# source values; only export.to_english applies these).
YES_NO_DISPLAY_EN: dict[str, str] = {
    "si": "Yes", "sí": "Yes", "s": "Yes",
    "no": "No",
    "prefiero no responder": "Prefer not to say",
}
USEFULNESS_DISPLAY_EN: dict[str, str] = {
    "Muy útil": "Very useful",
    "Útil": "Useful",
    "Medianamente útil": "Moderately useful",
    "Poco útil": "Slightly useful",
    "Nada útil": "Not useful",
}
DISCOVERY_DISPLAY_EN: dict[str, str] = {
    # Short, non-redundant labels: the chart title already says "How Users
    # Find Sami," so "Referral from" on every bar was repeated context, and
    # the longer strings were the ones truncating in the bar chart's category
    # axis ("Referral from anot...", "Referral from an N...").
    "Recomendación de otro migrante": "Another migrant",
    "Recomendación de una ONG": "An NGO",
    "Cartelera en un punto de atención": "Service point poster",
    "Redes sociales": "Social media",
    "Otro": "Other",
    # v2 reworded these three options; both vintages map to one label so a
    # pooled chart does not split the same answer in multiple slices.
    "Otro migrante": "Another migrant",
    "Recomendación de ONG": "An NGO",
    "Punto de atención": "Service point poster",
}
# 'Otra' (city) / 'Desconocida' (nationality) are the two catch-all buckets that
# the canon functions themselves emit.
OTHER_BUCKET_EN: dict[str, str] = {"Otra": "Other", "Desconocida": "Unknown"}

DISCOVERY_CANONICAL_EN = frozenset(DISCOVERY_DISPLAY_EN.values())


def discovery_channel_display(raw):
    """EN label for a discovery_channel answer, defaulting unknowns to 'Other'.

    The survey's 'Otro' option lets a respondent type free text, and some rows
    have that free text sitting directly in `discovery_channel` instead of the
    literal string 'Otro' -- each one a singleton, several with encoding noise.
    They are still answers to the 'other' option, so they collapse to the same
    'Other' bucket rather than each drawing its own bar. Unlike `_mapper`
    (value-preserving passthrough, used elsewhere), this closed-set lookup
    NEVER passes an unrecognized string through raw.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return raw
    if raw in DISCOVERY_DISPLAY_EN:
        return DISCOVERY_DISPLAY_EN[raw]
    if raw in DISCOVERY_CANONICAL_EN:
        return raw
    return "Other"


# The interface-language selector (v2-only -- v1 users have no language
# field, hence the volume of blanks). Currently only `es`/`en` appear in the
# data (94.9%/0.2%, the rest blank), but the selector's own option set
# includes French, so it's mapped here even with zero current usage -- it
# must display correctly the moment it appears, not need a code change.
LANGUAGE_DISPLAY_EN: dict[str, str] = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
}
LANGUAGE_CANONICAL_EN = frozenset(LANGUAGE_DISPLAY_EN.values())


def language_display(raw):
    """EN label for an interface-language code.

    Closed-set lookup, same discipline as `discovery_channel_display`: blank
    (v1 users, who were never asked) and any unrecognized code both become
    'Not specified' rather than showing a raw 2-letter code or an empty slice
    with no label in a chart."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "Not specified"
    key = str(raw).strip().lower()
    if key in LANGUAGE_DISPLAY_EN:
        return LANGUAGE_DISPLAY_EN[key]
    if raw in LANGUAGE_CANONICAL_EN:
        return raw
    return "Not specified"


# MMC's standard age brackets. Replaces the raw survey's own self-reported
# bucket ("Age Ranges": 0-17 / 18-35 / 36-50 / 50 and above), which is
# coarser than these six bands and can't be split into them after the fact --
# the source has to move to the continuous `age_num` field, not a relabeling
# of the existing categorical answer.
AGE_RANGE_BINS = [0, 18, 25, 35, 45, 55, 150]
AGE_RANGE_LABELS = ["0-17", "18-24", "25-34", "35-44", "45-54", "55+"]
AGE_RANGE_NOT_SPECIFIED = "Not specified"
AGE_RANGE_ORDER = {label: i for i, label in enumerate(AGE_RANGE_LABELS)}
AGE_RANGE_ORDER[AGE_RANGE_NOT_SPECIFIED] = len(AGE_RANGE_LABELS)


def age_range_bucket(age_num):
    """MMC bracket for a numeric age; missing/out-of-range ages become
    'Not specified' rather than an empty slice with no label.

    NOTE: `age_flag == "unreliable_sub18"` marks every age under 18 as
    self-report noise the pipeline does not trust (see `load.py`) -- exactly
    the population that lands in the '0-17' bucket here. This function does
    not filter on that flag; whoever builds a chart on this bucket must
    decide whether to exclude or visibly caveat those ~50 users, the same
    way every other known-unreliable field in this export is handled (stated
    on the chart, not silently dropped or silently trusted)."""
    if age_num is None or pd.isna(age_num):
        return AGE_RANGE_NOT_SPECIFIED
    age = float(age_num)
    for lo, hi, label in zip(AGE_RANGE_BINS[:-1], AGE_RANGE_BINS[1:], AGE_RANGE_LABELS):
        if lo <= age < hi:
            return label
    return AGE_RANGE_NOT_SPECIFIED


def age_range_order_of(label) -> int:
    return AGE_RANGE_ORDER.get(label, len(AGE_RANGE_LABELS))


def yes_no_display(raw) -> str:
    """EN label for a Sí/No survey answer; unrecognized values pass through."""
    key = fold(raw)
    if key in ("", "nan", "none"):
        return ""
    return YES_NO_DISPLAY_EN.get(key, str(raw).strip())
