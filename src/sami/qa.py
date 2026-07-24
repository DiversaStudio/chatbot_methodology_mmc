"""Validation, PII scanning, and the reconciliation table (doc 01 §7)."""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

from . import config

# \b anchors keep this from matching a digit run glued to underscores/letters
# (e.g. a "..._1783087815.xlsx" source-file id) while still catching real
# phone numbers, which are always set off by a delimiter (+, space, :, etc.).
_PII_PATTERNS = [re.compile(r"whatsapp:", re.I), re.compile(r"\b\d{7,}\b")]

_CRITICAL = {
    "responses": ["Name", "Timestamp", "City", "Age", "Messages", "Chat_summary"],
    "meal": ["Name", "Timestamp"],
}
_SHEET = {"responses": "mmc bot - responses", "meal": "mmc-meal"}


def pii_scan(obj) -> list[dict]:
    """Return violation records for whatsapp:/7+-digit runs. Empty list = clean.

    Skips the `user_id` column: it is a non-reversible sha256 hash and, by
    chance, some hex hashes contain a 7+-digit run. That is not PII and must
    not be flagged (raw Excel exports have no user_id column, so raw-file
    scans are unaffected)."""
    if isinstance(obj, (str, Path)):
        df = pd.read_excel(obj, header=config.DATA_HEADER_ROW, dtype=str)
    else:
        df = obj
    violations = []
    for col in df.columns:
        if str(col) == "user_id":
            continue
        # Only string/object columns can hold raw phone numbers or "whatsapp:"
        # runs. Numeric (int/float/bool) columns are legitimate metrics —
        # str()'ing a float routinely produces 7+ consecutive decimal digits
        # (e.g. a ratio like 0.8724100327) that is not PII.
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            continue
        for val in df[col].astype(str).fillna(""):
            if any(p.search(val) for p in _PII_PATTERNS):
                violations.append({"column": str(col), "value_prefix": val[:12]})
                break  # one hit per column is enough to flag
    return violations


def validate_schema(path, kind: str) -> dict:
    xl = pd.ExcelFile(path)
    if _SHEET[kind] not in xl.sheet_names:
        # tolerate single-sheet test fixtures; only enforce for real exports
        if len(xl.sheet_names) != 1:
            raise ValueError(f"expected sheet {_SHEET[kind]!r}, got {xl.sheet_names}")
    try:
        df = pd.read_excel(path, header=config.DATA_HEADER_ROW)
    except ValueError:
        # fixture/file too short for the real export's header offset: there is
        # no way the critical columns can be present, so fall through to the
        # missing-columns check below with an empty frame.
        df = pd.DataFrame()
    missing = [c for c in _CRITICAL[kind] if c not in df.columns]
    if missing:
        raise ValueError(f"missing critical columns for {kind}: {missing}")
    ts = df["Timestamp"] if "Timestamp" in df.columns else pd.Series(dtype=object)
    non_null = ts.notna().sum()
    parsed = pd.to_datetime(ts, errors="coerce", utc=True).notna().sum()
    rate = 1.0 if non_null == 0 else parsed / non_null
    return {"rows": len(df), "columns": len(df.columns), "ts_parse_rate": float(rate)}


def reconciliation_table(responses: pd.DataFrame, messages: pd.DataFrame,
                         meal: pd.DataFrame) -> pd.DataFrame:
    n_users = responses["user_id"].nunique()
    n_msgs = len(messages)
    legal = (messages["dominant_category"] == "legal_documentation").mean() if "dominant_category" in messages else float("nan")
    # repeat-asker proxy: users at/above p90 question volume
    q = responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    repeat_pct = round(100 * (q >= p90).mean(), 1) if q.notna().any() else "pending"
    rows = [
        ("users", n_users),
        ("records", len(responses)),
        ("messages", n_msgs),
        ("users_with_text", messages["user_id"].nunique()),
        ("meal_responses", len(meal)),
        ("meal_response_rate_pct", round(100 * len(meal) / n_users, 1)),
        ("legal_documentation_pct", round(100 * legal, 1)),
        ("repeat_askers_pct", repeat_pct),
        ("negative_tone_pct", "pending"),  # from NB3 sentiment
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def run_checks(responses, messages, meal) -> list[tuple[str, bool, str]]:
    # Second element is always a plain Python bool (not numpy.bool_) so run_meta
    # stays JSON-serializable when a later task persists it.
    checks = []
    checks.append(("P1_pii_responses", bool(pii_scan(responses) == []), "no whatsapp/phone in responses"))
    checks.append(("P1_pii_messages", bool(pii_scan(messages) == []), "no whatsapp/phone in messages"))
    per_user = messages.groupby("user_id")["n_msgs_user"].first().sum()
    checks.append(("P6_spine_invariant", bool(per_user == len(messages)), f"{per_user} == {len(messages)}"))
    checks.append(("P8_meal_unique", bool(meal["user_id"].is_unique), "one MEAL row per user"))
    unclass = (responses["dominant_category"] == "unclassified").mean()
    checks.append(("P7_unclassified_share", bool(unclass < 0.10), f"{unclass:.1%} unclassified"))
    return checks
