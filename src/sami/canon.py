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
    "ecuador": "Ecuador", "ecuatoriana": "Ecuador",
    "peru": "Peru", "peruana": "Peru",
    "colombia": "Colombia", "colombiana": "Colombia",
    "united states": "United States", "estados unidos": "United States",
}


def clean_nationality(raw, other) -> str:
    """Consolidate Nationality with its *_other free-text fallback (P4)."""
    raw_s = ("" if raw is None or pd.isna(raw) else str(raw)).strip()
    other_s = "" if other is None or pd.isna(other) else str(other).strip()
    if raw_s in ("", "Otra", "Otro") and other_s:
        raw_s = other_s
    return raw_s


def nationality_canon(name) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return "Desconocida"
    key = fold(name)
    if key in ("", "nan", "none"):
        return "Desconocida"
    return NATIONALITY_CANON.get(key, str(name).strip().title())


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
    "Riohacha": "La Guajira",
    "Maicao": "La Guajira",
    "Soacha": "Cundinamarca",
    "Necoclí": "Antioquia",
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


# --- gender EN display --------------------------------------------------------
GENDER_DISPLAY: dict[str, str] = {
    "Mujer": "Woman",
    "Hombre": "Man",
    "Prefiero no responder": "Prefer not to say",
    "Otro": "Other",
}


def clean_gender(raw, other) -> str:
    """Consolidate Gender with its *_other free-text fallback (P4)."""
    raw_s = ("" if raw is None or pd.isna(raw) else str(raw)).strip()
    other_s = "" if other is None or pd.isna(other) else str(other).strip()
    if raw_s in ("", "Otro", "Otra") and other_s:
        return other_s
    return raw_s
