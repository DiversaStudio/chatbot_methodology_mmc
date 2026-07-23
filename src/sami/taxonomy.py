"""Official MMC category taxonomy + dictionary extraction of institutions/procedures."""
from __future__ import annotations
from collections import Counter
from typing import Iterable
import re
import unicodedata
import pandas as pd

OFFICIAL_CATEGORIES: list[str] = [
    "legal_documentation",
    "humanitarian_assistance",
    "protection",
    "employment",
    "organization_search",
    "journey_information",
    "services",
]

# folded, separator-free aliases -> canonical category
_CATEGORY_ALIASES: dict[str, str] = {
    "legaldocumentation": "legal_documentation",
    "humanitarianassistance": "humanitarian_assistance",
    "protection": "protection",
    "employment": "employment",
    "organizationsearch": "organization_search",
    "journeyinformation": "journey_information",
    "services": "services",
}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def normalize_category(raw) -> str:
    """Map a raw Chat_summary value to one official category or 'unclassified'.

    Handles '#' hashtags, '_'/space separators, case; multi-label (comma) and
    the leftover prompt instruction row both resolve to 'unclassified'.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "unclassified"
    text = str(raw).strip()
    if text == "" or "," in text:  # blank or multi-label
        return "unclassified"
    if len(text) > 60:  # the prompt-leftover instruction row is long
        return "unclassified"
    key = _fold(text).lstrip("#").strip()
    key = re.sub(r"[\s_]+", "", key)  # drop spaces and underscores
    return _CATEGORY_ALIASES.get(key, "unclassified")


# ---- institutions / procedures dictionary ----
ENTITY_PATTERNS: dict[str, list[str]] = {
    "PPT": [r"\bppt\b", r"permiso por proteccion temporal"],
    "PEP": [r"\bpep\b", r"permiso especial de permanencia"],
    "Visa": [r"\bvisa\b", r"\bvisas\b"],
    "Cédula de extranjería": [r"cedula de extranjeria"],
    "Pasaporte": [r"\bpasaporte\b"],
    "EPS": [r"\beps\b", r"afiliacion en salud", r"seguro de salud"],
    "SISBÉN": [r"\bsisben\b"],
    "Migración Colombia": [r"migracion colombia", r"\bmigracion\b"],
    "ACNUR": [r"\bacnur\b", r"\bunhcr\b"],
    "Cancillería": [r"cancilleria"],
    "Registraduría": [r"registraduria"],
    "SENA": [r"\bsena\b"],
    "ICBF": [r"\bicbf\b"],
    "Refugio/Asilo": [r"\brefugio\b", r"\basilo\b", r"solicitante de refugio"],
    "Trabajo/Empleo": [r"\bempleo\b", r"\btrabajo\b", r"permiso de trabajo"],
    "Educación": [r"\beducacion\b", r"\bcolegio\b", r"\bestudios?\b", r"convalidacion"],
    "Vivienda/Arriendo": [r"\barriendo\b", r"\bvivienda\b", r"subsidio de arriendo"],
    "Ayuda humanitaria": [r"ayuda humanitaria", r"asistencia humanitaria"],
}
_COMPILED = {k: [re.compile(p) for p in pats] for k, pats in ENTITY_PATTERNS.items()}


def extract_entities(text: str) -> set[str]:
    t = _fold(text)
    return {name for name, pats in _COMPILED.items() if any(p.search(t) for p in pats)}


def entity_counts(texts: Iterable[str]) -> pd.Series:
    c: Counter = Counter()
    for t in texts:
        if t is None or (isinstance(t, float) and pd.isna(t)):
            continue
        for ent in extract_entities(t):
            c[ent] += 1
    return pd.Series(c, dtype="int64").sort_values(ascending=False)


# ---- institution vs procedure split (NB2 §1 two-panel) ----
ENTITY_KIND: dict[str, str] = {
    "PPT": "procedure", "PEP": "procedure", "Visa": "procedure",
    "Cédula de extranjería": "procedure", "Pasaporte": "procedure",
    "EPS": "procedure", "SISBÉN": "procedure",
    "Refugio/Asilo": "procedure", "Trabajo/Empleo": "procedure",
    "Vivienda/Arriendo": "procedure", "Ayuda humanitaria": "procedure",
    "Educación": "procedure",
    "Migración Colombia": "institution", "ACNUR": "institution",
    "Cancillería": "institution", "Registraduría": "institution",
    "SENA": "institution", "ICBF": "institution",
}


def entity_counts_by_kind(texts) -> dict[str, pd.Series]:
    """Split entity_counts into an institution Series and a procedure Series."""
    counts = entity_counts(texts)
    out: dict[str, pd.Series] = {}
    for kind in ("institution", "procedure"):
        names = [k for k, v in ENTITY_KIND.items() if v == kind]
        out[kind] = counts[counts.index.isin(names)].sort_values(ascending=False)
    return out


# ---- candidate emergent intents (NB3 §3) ----
# Needs the 7 official categories have no slot for. These are the vocabulary the
# NB3 coverage-gap section may assign to a cluster.
CANDIDATE_INTENT_SLUGS: list[str] = [
    "transport_logistics",
    "human_handoff",
    "connectivity",
    "out_of_scope",
    "other_emergent",
]

# Probes for candidate emergent needs. THESE ARE NOT A CLASSIFIER. NB3 drops LLM
# per-message classification (design §0.1), so nothing here is validated: matches are
# a *floor* on how often a need appears (recall is unknown), never a rate. Findings
# sourced from this map are tagged "directional only" and no percentage is quoted.
# They exist to corroborate, in users' own words, the needs the c-TF-IDF cluster terms
# surfaced — and to let a hypothesised need be honestly reported as ABSENT.
CANDIDATE_INTENT_PROBES: dict[str, str] = {
    "transport_logistics": r"\b(pasaje|terminal|transporte|bus|viajar|ruta|traslado|trocha)\b",
    "entrepreneurship": r"\b(emprendimiento|emprender|negocio propio|capital semilla|microcr[eé]dito)\b",
    "procedure_troubleshooting": r"\b(rumv|biom[eé]trico|no me aparece|no carga|verificar|duplicado)\b",
    "human_handoff": r"(hablar con (un|una|alguien|alguno|persona)|asesor|un humano|una persona real|comunicarme con)",
    "fraud_protection": r"\b(estafa|estafaron|fraude|enga[nñ]o|me robaron)\b",
    "connectivity": r"\b(recarga|datos m[oó]viles|saldo|internet|wifi)\b",
}

# Named archetypes for the k=4 solution at random_state=0 (NB3 §2). Cluster ids are
# deterministic under that seed; `marker` is a term that MUST appear in the cluster's
# top c-TF-IDF terms, so `assert_archetype_mapping` fails loudly if a data refresh
# reshuffles the ids rather than letting mislabelled archetypes ship.
ARCHETYPE_NAMES: dict[int, dict[str, str]] = {
    3: {"name": "Regularising from scratch",
        "marker": "pasaporte",
        "blurb": "No Colombian papers yet — passports, cédulas, birth records, witnesses."},
    0: {"name": "Urgent humanitarian need",
        "marker": "humanitaria",
        "blurb": "Food, shelter, disability and transport support, often stated as urgent."},
    2: {"name": "Building a livelihood",
        "marker": "emprendimiento",
        "blurb": "Work, training and enterprise support — planning ahead, not in crisis."},
    1: {"name": "Stuck mid-procedure",
        "marker": "rumv",
        "blurb": "Already inside the RUMV/PPT pipeline and blocked: biometrics, verification, collection."},
}


def assert_archetype_mapping(terms: dict[int, "pd.Series"]) -> None:
    """Fail loudly if cluster ids no longer match ARCHETYPE_NAMES (seed/data drift)."""
    for cid, meta in ARCHETYPE_NAMES.items():
        if cid not in terms:
            raise AssertionError(f"cluster {cid} missing from solution — archetype mapping is stale")
        if meta["marker"] not in set(terms[cid].index):
            raise AssertionError(
                f"cluster {cid} no longer contains marker '{meta['marker']}' "
                f"(top terms: {list(terms[cid].index[:6])}). Re-read the clusters and "
                "update ARCHETYPE_NAMES before reporting archetypes."
            )

