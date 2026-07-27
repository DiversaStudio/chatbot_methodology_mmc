"""Source-export schema contract: header detection, required columns, MEAL mapping.

The two Excel exports are produced by a third-party platform and their shape
drifts between downloads. Everything this pipeline assumes about that shape is
declared *here*, so a drifted export fails with a message naming the file, the
column, and the fix — instead of a `KeyError`, or worse, silently correct-looking
numbers (see `meal_column_map`, which replaces positional column picking).
"""
from __future__ import annotations

import pandas as pd

from .canon import fold


class SchemaError(Exception):
    """A source export does not match the contract. Message carries the fix."""


def _fmt(problem: str, path, fix: str) -> str:
    return f"{problem}\n  file: {path}\n  fix:  {fix}"


# ---- header row ---------------------------------------------------------------
# The exports carry two banner rows above the real header ("MMC bot - responses",
# "Try it free ->"), so the header is the 3rd row today. Detected rather than
# assumed: a re-export with one more or fewer banner rows silently shifts it.
HEADER_MARKERS = ("name", "timestamp")
HEADER_SCAN_ROWS = 8


def detect_header_row(path, max_scan: int = HEADER_SCAN_ROWS) -> int:
    """0-indexed row holding the real column header.

    Finds the first row containing both `Name` and `Timestamp`. Raises
    SchemaError showing the rows actually seen when no row matches.
    """
    probe = pd.read_excel(path, header=None, nrows=max_scan)
    for i in range(len(probe)):
        cells = {fold(v) for v in probe.iloc[i] if not pd.isna(v)}
        if all(m in cells for m in HEADER_MARKERS):
            return i
    seen = "\n".join(
        f"    row {i}: {[str(v)[:24] for v in probe.iloc[i, :5] if not pd.isna(v)]}"
        for i in range(len(probe)))
    raise SchemaError(_fmt(
        f"No header row found in the first {max_scan} rows — expected a row "
        f"containing both 'Name' and 'Timestamp'.",
        path,
        "Confirm this is a raw platform export (banner rows above the header, "
        "header not yet promoted). Rows seen:\n" + seen))


# ---- responses ----------------------------------------------------------------
# Columns load_responses reads unguarded. Everything else it accesses through
# `_col()`, which tolerates absence, so it does not belong here.
RESPONSES_REQUIRED = ("Name", "Timestamp", "City", "Age", "Messages", "Chat_summary")
# Present in the current export and used when available; absence degrades a
# figure but never breaks the run.
RESPONSES_OPTIONAL = (
    "Nationality", "Nationality_other", "City_other", "City_duration", "Gender",
    "Gender_other", "Minors", "Away_duration", "Destination_Country",
    "Age Ranges", "Questions per user",
)
# Present in the export and deliberately unused. Listed so `report_unknown_columns`
# stays quiet on a known-good export and only speaks up for genuinely NEW fields —
# a warning that fires every run is a warning nobody reads.
RESPONSES_IGNORED = (
    "Subitems", "Consent", "City Location", "Prev_country", "Prev_country_other",
    "Destination", "Destination_other", "Survey sent", "Summarize", "Text",
    "Text 1", "Last Message At",
)

# Every export, whichever source, must carry these two — pseudonymization keys
# off Name and the whole pipeline is time-indexed on Timestamp.
BASE_REQUIRED = ("Name", "Timestamp")
# MEAL needs nothing else by name; its survey fields are matched below.
MEAL_REQUIRED = BASE_REQUIRED


def require_columns(frame: pd.DataFrame, required, path, source: str) -> None:
    """Raise SchemaError naming every missing column, not just the first."""
    missing = [c for c in required if c not in frame.columns]
    if not missing:
        return
    raise SchemaError(_fmt(
        f"{source} export is missing required column(s): {', '.join(missing)}",
        path,
        f"This export has: {', '.join(map(str, frame.columns))}\n"
        "        If the platform renamed a field, map it back to the expected "
        "name, or update RESPONSES_REQUIRED / MEAL_REQUIRED in src/sami/schema.py."))


def report_unknown_columns(frame: pd.DataFrame, source: str) -> list[str]:
    """New columns the contract does not know about. Informational only — a
    refreshed export gaining a field is normal and must not fail the run."""
    if source != "responses":
        return []
    known = set(RESPONSES_REQUIRED) | set(RESPONSES_OPTIONAL) | set(RESPONSES_IGNORED)
    return [str(c) for c in frame.columns if str(c) not in known]


# ---- MEAL survey columns ------------------------------------------------------
# The five survey questions are long Spanish sentences, so they are matched by a
# distinctive fold-normalized fragment rather than by exact text (which carries
# punctuation and could be reworded) and rather than by POSITION (which is what
# this replaces: a single inserted column used to shift every rating one field
# to the left, with no error raised).
MEAL_QUESTION_MARKERS: dict[str, str] = {
    "usefulness_rating": "que tan util",
    "would_recommend": "recomendarias este servicio",
    "recommendation_text": "alguna recomendacion para mejorar",
    "discovery_channel": "como conociste",
    "discovery_other": "escribe el medio",
}
# Column positions these fields occupied in every export seen so far. Used only
# as a last resort, and never silently.
MEAL_FALLBACK_POSITIONS: dict[str, int] = {
    "usefulness_rating": 2, "would_recommend": 3, "recommendation_text": 4,
    "discovery_channel": 5, "discovery_other": 6,
}


def meal_column_map(columns, path=None) -> tuple[dict[str, str], list[str]]:
    """Map MEAL survey columns to their canonical names.

    Returns `({source_column: canonical_name}, warnings)`. Matches on question
    text first; any field that does not match falls back to its historical
    position and emits a warning naming the exact column it guessed, so a wrong
    guess is visible in the run log instead of silently mislabelling ratings.
    """
    cols = [str(c) for c in columns]
    folded = [fold(c) for c in cols]
    mapping: dict[str, str] = {}
    warnings: list[str] = []
    taken: set[int] = set()

    for canonical, marker in MEAL_QUESTION_MARKERS.items():
        hit = next((i for i, f in enumerate(folded)
                    if marker in f and i not in taken), None)
        if hit is not None:
            taken.add(hit)
            mapping[cols[hit]] = canonical
            continue
        pos = MEAL_FALLBACK_POSITIONS[canonical]
        if pos < len(cols) and pos not in taken:
            taken.add(pos)
            mapping[cols[pos]] = canonical
            warnings.append(
                f"MEAL column '{canonical}' did not match its question text "
                f"(looked for {marker!r}); fell back to position {pos}: "
                f"{cols[pos][:70]!r}. VERIFY THIS IS THE RIGHT FIELD.")
        else:
            warnings.append(
                f"MEAL column '{canonical}' not found by question text or "
                f"position {pos}; it will be absent from fact_meal.")
    return mapping, warnings
