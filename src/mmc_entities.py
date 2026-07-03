"""Dictionary-based extraction of migration trámites & institutions."""
from __future__ import annotations
from collections import Counter
from typing import Iterable
import re
import unicodedata
import pandas as pd


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# canonical name -> list of regex alternatives (already accent-free, lowercase)
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
    t = _norm(text)
    return {name for name, pats in _COMPILED.items() if any(p.search(t) for p in pats)}


def entity_counts(texts: Iterable[str]) -> pd.Series:
    c: Counter = Counter()
    for t in texts:
        if t is None or (isinstance(t, float) and pd.isna(t)):
            continue
        for ent in extract_entities(t):
            c[ent] += 1
    return pd.Series(c, dtype="int64").sort_values(ascending=False)
