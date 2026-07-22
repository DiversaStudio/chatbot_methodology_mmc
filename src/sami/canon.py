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
        if key == k or key.startswith(k + " "):
            return v
    return "Otra"


def clean_city(raw_city, city_other) -> str:
    raw = ("" if raw_city is None else str(raw_city)).strip()
    other = "" if city_other is None or pd.isna(city_other) else str(city_other).strip()
    if raw == "Otra" and other:
        return other.title()
    return raw
