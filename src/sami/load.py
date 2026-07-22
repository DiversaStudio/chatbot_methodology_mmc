"""Loaders + cleaning + pseudonymization: the single source of truth for SAMI data."""
from __future__ import annotations
import hashlib
import re
import unicodedata
import pandas as pd

from . import config, canon, taxonomy

_NOISE = {"undefined", "?", ""}


def digits(s) -> str:
    return re.sub(r"\D", "", str(s))


def pseudonymize(name, salt: str) -> str:
    """sha256(salt + digits(name))[:12]. Deterministic, salted, non-reversible."""
    return hashlib.sha256((salt + digits(name)).encode("utf-8")).hexdigest()[:12]


# ---- text helpers (ported from mmc_text.py) ----
def split_messages(blob) -> list[str]:
    if not isinstance(blob, str):
        return []
    parts = [p.strip() for p in blob.split("\n")]
    return [p for p in parts if not _is_noise(p)]


def _is_noise(t: str) -> bool:
    # Redaction-invariant: a line whose only content was a PII digit run has
    # already been replaced with the literal "[redacted]" token by the time
    # split_messages sees it (load_responses redacts before returning). Strip
    # that token before the length/digit checks so the noise decision reflects
    # the real underlying content, not the redaction placeholder.
    t = t.replace("[redacted]", " ").strip()
    return len(t) < 3 or t.isdigit() or t.lower() in _NOISE


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


_BASE_STOP = (
    "a al algo algunas algunos ante antes como con contra cual cuando de del "
    "desde donde dos el ella ellas ellos en entre era es esa ese eso esta este "
    "esto ha hasta hay la las le les lo los mas me mi mis mucho muy nada ni no "
    "nos o os para pero poco por porque que quien se sin sobre soy su sus te "
    "tener tengo ti tu tus un una uno unos y ya yo".split()
)
_COURTESY_TOKENS = (
    "hola buenas buenos dias tardes noches gracias muchas mil bendiga bendiciones "
    "amen dios saludos hi hello ok okay bien vale adios chao hasta luego favor "
    "porfavor porfa disculpa disculpe perdon le".split()
)
SPANISH_STOPWORDS = sorted(set(_BASE_STOP) | set(_COURTESY_TOKENS))


def is_courtesy(text: str) -> bool:
    words = re.findall(r"[a-zñ]+", _fold(text))
    if not words:
        return True
    return all(w in _COURTESY_TOKENS for w in words)


# ---- responses loader ----
def _read_whatsapp(path) -> pd.DataFrame:
    df = pd.read_excel(path, header=config.DATA_HEADER_ROW)
    df = df[df["Name"].astype(str).str.startswith("whatsapp")].copy()
    df.reset_index(drop=True, inplace=True)
    return df


_PII_RUN = re.compile(r"\d{7,}")


def _redact_pii_runs(df: pd.DataFrame) -> pd.DataFrame:
    """Belt-and-suspenders for the PII gate: users sometimes paste a phone number or
    cedula into an open-text field (Messages, Chat_summary, ...). Redact any run of
    7+ consecutive digits from string columns. Excludes user_id, the intentional
    pseudonymized hash, whose hex digits may incidentally contain such a run.

    Best-effort scrub; qa.pii_scan is the authoritative PII gate (it scans a
    wider surface — every non-user_id column coerced to str)."""
    for col in df.columns:
        if col == "user_id" or not pd.api.types.is_string_dtype(df[col]):
            continue
        df[col] = df[col].map(lambda v: _PII_RUN.sub("[redacted]", v) if isinstance(v, str) else v)
    return df


def load_responses(path=None, salt=None) -> pd.DataFrame:
    path = path or config.RESPONSES_PATH
    salt = salt if salt is not None else config.get_salt()
    df = _read_whatsapp(path)
    df["user_id"] = df["Name"].map(lambda n: pseudonymize(n, salt))
    df = df.drop(columns=[c for c in ["Name"] if c in df.columns])
    def _col(name):  # missing-column-safe accessor (schema drifts between exports)
        return df[name] if name in df.columns else pd.Series([None] * len(df))
    df["city_clean"] = [canon.clean_city(c, o) for c, o in zip(df["City"], _col("City_other"))]
    df["city_canon"] = df["city_clean"].map(canon.city_canon)
    df["department"] = df["city_canon"].map(canon.department_of)
    df["age_num"] = pd.to_numeric(df["Age"], errors="coerce")
    df["age_flag"] = df["age_num"].map(lambda a: "unreliable_sub18" if pd.notna(a) and a < 18 else "ok")
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    df["n_questions"] = pd.to_numeric(df.get("Questions per user"), errors="coerce")
    df["dominant_category"] = df["Chat_summary"].map(taxonomy.normalize_category)
    # P4: *_other consolidation (city already done above) + display-ready derivations
    df["gender_clean"] = [canon.clean_gender(g, o) for g, o in zip(_col("Gender"), _col("Gender_other"))]
    df["nationality_clean"] = [canon.clean_nationality(n, o) for n, o in zip(_col("Nationality"), _col("Nationality_other"))]
    df["nationality_canon"] = df["nationality_clean"].map(canon.nationality_canon)
    df["away_duration_canon"] = _col("Away_duration").map(canon.away_duration_canon)
    df["away_duration_order"] = _col("Away_duration").map(canon.away_duration_order)
    df = _redact_pii_runs(df)
    return df


# ---- message spine loader ----
def load_messages(responses_df: pd.DataFrame) -> pd.DataFrame:
    """Explode each response record's `Messages` blob into one row per message
    (the analysis spine). Note some users have multiple response records
    (2-3 records for 26 of 917 users in the real export); `n_msgs_user` and
    `seq` are computed per USER (across all of that user's records), not per
    record, so the P6 invariant (sum of per-user counts == total rows) holds."""
    carry = [c for c in ["user_id", "ts", "city_canon", "dominant_category",
                         "Gender", "Age Ranges", "Nationality", "age_num"]
             if c in responses_df.columns]
    rows = []
    for _, r in responses_df.iterrows():
        parts = split_messages(r.get("Messages"))
        for p in parts:
            row = {c: r[c] for c in carry}
            row["message"] = p
            rows.append(row)
    df = pd.DataFrame(rows)
    df = df.sort_values(["user_id", "ts"], kind="stable").reset_index(drop=True)
    df["seq"] = df.groupby("user_id").cumcount()
    df["n_msgs_user"] = df.groupby("user_id")["message"].transform("size")
    return df


# ---- MEAL survey loader ----
def load_meal(path=None, salt=None) -> pd.DataFrame:
    path = path or config.MEAL_PATH
    salt = salt if salt is not None else config.get_salt()
    df = _read_whatsapp(path)
    df["user_id"] = df["Name"].map(lambda n: pseudonymize(n, salt))
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    cols = list(df.columns)
    rename = {                    # positional: the 5 survey question columns
        cols[2]: "usefulness_rating",
        cols[3]: "would_recommend",
        cols[4]: "recommendation_text",
        cols[5]: "discovery_channel",
        cols[6]: "discovery_other",
    }
    df = df.rename(columns=rename)
    keep = ["user_id", "ts", "usefulness_rating", "would_recommend",
            "recommendation_text", "discovery_channel", "discovery_other"]
    df = df[[c for c in keep if c in df.columns]].copy()
    # P8: keep most recent response per user (stable sort so ties are well-defined)
    df = df.sort_values("ts", kind="stable").drop_duplicates("user_id", keep="last").reset_index(drop=True)
    df = _redact_pii_runs(df)
    return df
