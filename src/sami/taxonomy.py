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
