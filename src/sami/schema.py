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
# The exports carry two banner rows above the real header, so the header is the
# 3rd row today. Detected rather than assumed: a re-export with one more or fewer
# banner rows silently shifts it.
#
# The v2 platform renamed the key columns, so each source accepts several marker
# sets. The legacy sets are kept because they cost nothing and let a v1-shaped
# file still be read (fixtures, archives) — the pipeline targets v2.
HEADER_MARKERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "responses": (("address", "created at"), ("name", "timestamp")),
    "meal": (("respondent", "recorded at"), ("name", "timestamp")),
}
HEADER_SCAN_ROWS = 8


def detect_header_row(path, source: str = "responses",
                      max_scan: int = HEADER_SCAN_ROWS) -> int:
    """0-indexed row holding the real column header.

    Finds the first row containing every marker of any accepted marker set for
    `source`. Raises SchemaError showing the rows actually seen when none match.
    """
    marker_sets = HEADER_MARKERS.get(source, HEADER_MARKERS["responses"])
    probe = pd.read_excel(path, header=None, nrows=max_scan)
    for i in range(len(probe)):
        cells = {fold(v) for v in probe.iloc[i] if not pd.isna(v)}
        if any(all(m in cells for m in markers) for markers in marker_sets):
            return i
    expected = " or ".join("+".join(m) for m in marker_sets)
    seen = "\n".join(
        f"    row {i}: {[str(v)[:24] for v in probe.iloc[i, :5] if not pd.isna(v)]}"
        for i in range(len(probe)))
    raise SchemaError(_fmt(
        f"No header row found in the first {max_scan} rows — expected a row "
        f"containing {expected}.",
        path,
        "Confirm this is a raw platform export (banner rows above the header, "
        "header not yet promoted). If the platform renamed its key columns "
        "again, add the new marker set to HEADER_MARKERS in "
        "src/sami/schema.py. Rows seen:\n" + seen))


# ---- source column maps -------------------------------------------------------
# The v2 platform renamed most fields. Rather than propagate the new names
# through every module, they are mapped back onto the canonical names the
# pipeline has always used. `normalize_columns` is the single place this happens.
RESPONSES_COLUMN_MAP: dict[str, str] = {
    "Address": "Name",
    "Created At": "Timestamp",
    "QA Messages": "Messages",
    "QA Summary": "Chat_summary",
    "consent": "Consent",
    "nationality": "Nationality",
    "nationality (raw)": "Nationality_other",
    "city": "City",
    "time_in_city": "City_duration",
    "gender": "Gender",
    "age": "Age",
    "children": "Minors",
    "destination": "Destination",
    "Survey Sent": "Survey sent",
}
MEAL_COLUMN_MAP: dict[str, str] = {
    "Respondent": "Name",
    "Recorded At": "Timestamp",
}
_COLUMN_MAPS = {"responses": RESPONSES_COLUMN_MAP, "meal": MEAL_COLUMN_MAP}


def normalize_columns(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    """Rename a raw v2 export's columns to the pipeline's canonical names.

    Unmapped columns pass through untouched — new v2 fields are read by their
    own names downstream. Idempotent: a frame already carrying canonical names
    is returned unchanged. A rename that would collide with an existing column
    is skipped, so a hybrid export cannot produce duplicate column labels.
    """
    mapping = _COLUMN_MAPS.get(source, {})
    present = set(frame.columns)
    rename = {src: dst for src, dst in mapping.items()
              if src in present and dst not in present}
    return frame.rename(columns=rename) if rename else frame


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
    "Language", "Registration Status", "Registration Started",
    "Registration Completed", "Attempts", "Is Returning User",
    "Safety Alert", "Escalation Status", "Migrated From v1", "Survey Completed",
    # KPI2 (average session time) differences this against Timestamp. Absent or
    # unparseable, session_minutes is null and the KPI reports on fewer users —
    # it never breaks the run. See load.last_message_ts.
    "Last Message At",
)
# Present in the export and deliberately unused. Listed so `report_unknown_columns`
# stays quiet on a known-good export and only speaks up for genuinely NEW fields —
# a warning that fires every run is a warning nobody reads.
RESPONSES_IGNORED = (
    "Subitems", "Consent", "City Location", "Prev_country", "Prev_country_other",
    "Destination", "Destination_other", "Survey sent", "Summarize", "Text",
    "Text 1",
    "Drop-off Question", "Re-engagement Sent At", "transit", "origin_country",
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
# The survey questions are long Spanish sentences, matched by a distinctive
# fold-normalized fragment rather than exact text (which carries punctuation and
# gets reworded) and rather than POSITION.
#
# Each field accepts several fragments because the v2 export carries BOTH
# question vintages. Two rules matter:
#
#   1. The v1 duplicates come FIRST and are EMPTY. Binding to the first match
#      produced all-null ratings with no error, and the old positional fallback
#      then relabelled the real usefulness data as discovery_other. So when a
#      marker matches several columns, the one CARRYING DATA wins.
#   2. There is no positional fallback. A field that cannot be matched is absent
#      from the mapping and raises a warning naming it. Absent-and-loud beats
#      present-and-wrong.
MEAL_QUESTION_MARKERS: dict[str, tuple[str, ...]] = {
    "usefulness_rating":    ("que tan util",),
    "would_recommend":      ("recomendarias este servicio", "v1 recomendarias"),
    "recommendation_text":  ("alguna recomendacion para mejorar",),
    "discovery_channel":    ("como conociste",),
    "discovery_other":      ("escribe el medio", "v1 medio otro"),
    "no_usefulness_reason": ("por que la informacion entregada no fue util",),
}


def meal_column_map(columns, path=None, frame=None) -> tuple[dict[str, str], list[str]]:
    """Map MEAL survey columns to their canonical names.

    Returns `({source_column: canonical_name}, warnings)`.

    When `frame` is supplied and a marker matches several columns, the populated
    one is chosen; ties break on the LAST occurrence, which is the newer vintage
    in every export seen. Without a frame the last match wins, which is still
    right for the v2 layout.
    """
    cols = [str(c) for c in columns]
    folded = [fold(c) for c in cols]
    mapping: dict[str, str] = {}
    warnings: list[str] = []
    taken: set[int] = set()

    def _populated(i: int) -> bool:
        if frame is None:
            return False
        try:
            return bool(frame.iloc[:, i].notna().sum())
        except (IndexError, KeyError):
            return False

    for canonical, markers in MEAL_QUESTION_MARKERS.items():
        hits = [i for i, f in enumerate(folded)
                if i not in taken and any(m in f for m in markers)]
        if not hits:
            warnings.append(
                f"MEAL column '{canonical}' not found by question text "
                f"(looked for {' | '.join(markers)}); it will be absent from "
                "fact_meal. If the platform reworded the question, add the new "
                "fragment to MEAL_QUESTION_MARKERS in src/sami/schema.py.")
            continue
        with_data = [i for i in hits if _populated(i)]
        chosen = (with_data or hits)[-1]
        taken.add(chosen)
        mapping[cols[chosen]] = canonical
        if len(hits) > 1 and not with_data and frame is not None:
            warnings.append(
                f"MEAL column '{canonical}' matched {len(hits)} columns and "
                f"none carry data; bound to {cols[chosen][:70]!r}. The question "
                "may have been retired.")
    return mapping, warnings
