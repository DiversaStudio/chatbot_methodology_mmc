"""Loaders and cleaning for the MMC monday.com exports."""
from __future__ import annotations
from pathlib import Path
import re
import unicodedata
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = _ROOT / "data_&_docs"
RESPONSES_PATH = DATA_DIR / "MMC_bot_responses_Grupo_nuevo_1783087815.xlsx"
MEAL_PATH = DATA_DIR / "MMC_MEAL_Group_Title_1783087939.xlsx"
DATA_HEADER_ROW = 2  # 0-indexed; header is the 3rd row of the export


def _phone(name: str) -> str:
    return re.sub(r"\D", "", str(name))


# 10 MMC priority cities + common variants -> canonical display name
_CITY_CANON = {
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
# tokens that are regions/countries, not a priority city -> Otra
_NON_CITY = {"colombia", "cundinamarca", "antioquia", "otra", "nan"}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def city_canon(name) -> str:
    if name is None:
        return "Otra"
    key = _fold(name)
    if key in _NON_CITY or key == "":
        return "Otra"
    if key in _CITY_CANON:
        return _CITY_CANON[key]
    # startswith match for "<city> <extra>" tails
    for k, v in _CITY_CANON.items():
        if key.startswith(k):
            return v
    return "Otra"


def clean_city(raw_city, city_other) -> str:
    raw = ("" if raw_city is None else str(raw_city)).strip()
    other = "" if city_other is None or pd.isna(city_other) else str(city_other).strip()
    if raw == "Otra" and other:
        return other.title()
    return raw


def _read_whatsapp(path) -> pd.DataFrame:
    df = pd.read_excel(path, header=DATA_HEADER_ROW)
    df = df[df["Name"].astype(str).str.startswith("whatsapp")].copy()
    df.reset_index(drop=True, inplace=True)
    return df


def load_responses(path=RESPONSES_PATH) -> pd.DataFrame:
    df = _read_whatsapp(path)
    df["phone"] = df["Name"].map(_phone)
    df["city_clean"] = [clean_city(c, o) for c, o in zip(df["City"], df["City_other"])]
    df["city_canon"] = df["city_clean"].map(city_canon)
    df["age_num"] = pd.to_numeric(df["Age"], errors="coerce")
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    df["n_questions"] = pd.to_numeric(df["Questions per user"], errors="coerce")
    return df


def load_meal(path=MEAL_PATH) -> pd.DataFrame:
    df = _read_whatsapp(path)
    df["phone"] = df["Name"].map(_phone)
    cols = list(df.columns)
    rename = {
        cols[2]: "utility",
        cols[3]: "would_recommend",
        cols[4]: "recommendation",
        cols[5]: "heard_channel",
        cols[6]: "heard_medium",
    }
    df = df.rename(columns=rename)
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    return df


_NOISE = {"undefined", "?", ""}


def _is_noise(t: str) -> bool:
    t = t.strip()
    return len(t) < 3 or t.isdigit() or t.lower() in _NOISE


def load_messages(df=None) -> pd.DataFrame:
    """Explode the per-user `Messages` blob into one row per user turn."""
    if df is None:
        df = load_responses()
    carry = ["phone", "city_clean", "city_canon", "ts", "Gender", "Age Ranges", "Nationality", "age_num"]
    carry = [c for c in carry if c in df.columns]
    rows = []
    for _, r in df.iterrows():
        blob = r.get("Messages")
        if not isinstance(blob, str):
            continue
        parts = [p.strip() for p in blob.split("\n")]
        parts = [p for p in parts if not _is_noise(p)]
        for i, p in enumerate(parts):
            row = {c: r[c] for c in carry}
            row["msg_idx"] = i
            row["n_msgs_user"] = len(parts)
            row["message"] = p
            rows.append(row)
    out = pd.DataFrame(rows).reset_index(drop=True)
    return out
