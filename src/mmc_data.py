"""Loaders and cleaning for the MMC monday.com exports."""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = _ROOT / "data_&_docs"
RESPONSES_PATH = DATA_DIR / "MMC_bot_responses_Grupo_nuevo_1783087815.xlsx"
MEAL_PATH = DATA_DIR / "MMC_MEAL_Group_Title_1783087939.xlsx"
DATA_HEADER_ROW = 2  # 0-indexed; header is the 3rd row of the export


def _phone(name: str) -> str:
    return re.sub(r"\D", "", str(name))


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
