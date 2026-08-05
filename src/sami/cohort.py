"""Questionnaire-version cohorts and which variables may be pooled across them.

The chatbot's registration survey was rewritten between v1 and v2. Three kinds
of change make a naive total wrong, and none of them announce themselves:

- **v1 excluded people.** Q3 terminated the survey for anyone answering
  "Colombia", so v1 rows contain no Colombians *by construction* — 0 of 1,355.
  A pooled nationality share measures that exit rule, not the user base.
- **Questions were retired.** Q9 (away_duration), Q10 (prev_country),
  Q13 (would_recommend) and Q14 (recommendation_text) are gone in v2. Their
  totals freeze while every other total grows, which reads as collapse.
- **A question was added.** Q12a exists only for v2 respondents.

Every export MMC downloads keeps carrying the v1 rows, so none of this ages
out. The policy below is therefore a permanent part of the contract, not a
migration artifact. See
docs/superpowers/specs/2026-07-28-sami-v2-export-migration-design.md.
"""
from __future__ import annotations

from enum import Enum

import pandas as pd


class Policy(str, Enum):
    """How a variable may be aggregated across questionnaire versions."""

    POOLABLE = "poolable"    # same question and options in both — total is valid
    SPLIT = "split"          # must be reported per instrument_version
    V1_ONLY = "v1_only"      # question retired in v2; series is frozen
    V2_ONLY = "v2_only"      # question added in v2; no v1 history


class CohortError(Exception):
    """A variable has no comparability policy. Message carries the fix."""


# The column the platform writes on rows carried over from the v1 bot.
V1_MARKER_COLUMN = "Migrated From v1"

POLICY: dict[str, Policy] = {
    # --- not comparable across versions ---
    "nationality_canon": Policy.SPLIT,
    "nationality_clean": Policy.SPLIT,
    # --- retired in v2 ---
    "away_duration_canon": Policy.V1_ONLY,
    "away_duration_order": Policy.V1_ONLY,
    "would_recommend": Policy.V1_ONLY,
    "recommendation_text": Policy.V1_ONLY,
    # --- added in v2 ---
    "no_usefulness_reason": Policy.V2_ONLY,
    "reason_is_valid": Policy.V2_ONLY,
    "language": Policy.V2_ONLY,
    "registration_status": Policy.V2_ONLY,
    "attempts": Policy.V2_ONLY,
    "is_returning": Policy.V2_ONLY,
    "safety_alert": Policy.V2_ONLY,
    "escalation_status": Policy.V2_ONLY,
    # --- identical question and options in both versions ---
    "user_id": Policy.POOLABLE,
    "ts": Policy.POOLABLE,
    "instrument_version": Policy.POOLABLE,
    "gender_clean": Policy.POOLABLE,
    "age_num": Policy.POOLABLE,
    "age_flag": Policy.POOLABLE,
    "age_range": Policy.POOLABLE,
    "minors": Policy.POOLABLE,
    "destination_country": Policy.POOLABLE,
    "intends_to_stay": Policy.POOLABLE,
    # City's option list widened 3 -> 8, but canon.clean_city already merges
    # City with the City_other free text and recovers most of the v1 "Otra"
    # bucket, so the canonical distribution is comparable.
    "city_canon": Policy.POOLABLE,
    "city_clean": Policy.POOLABLE,
    "department": Policy.POOLABLE,
    "city_duration_canon": Policy.POOLABLE,
    "city_duration_order": Policy.POOLABLE,
    "n_questions": Policy.POOLABLE,
    "n_msgs_user": Policy.POOLABLE,
    "has_text": Policy.POOLABLE,
    "first_seen": Policy.POOLABLE,
    # Stamped by the platform on the response record, not asked by either
    # questionnaire, so the version a user registered under does not change how
    # it is recorded.
    "registered_at": Policy.POOLABLE,
    "is_repeat_asker": Policy.POOLABLE,
    # Not a survey answer — derived from conversation text, which both
    # instrument versions collect identically. The v1/v2 rewrite changed the
    # registration questionnaire, not the chat, so "same question and options
    # in both" holds trivially here.
    # The remaining worry — that the two cohorts' TEXT-BEARING populations
    # differ in composition, the way nationality_canon does — was checked, not
    # assumed: a crosstab of cluster_id by instrument_version over the 1,198
    # has_text users (v1: 1,142, v2: 56) in the 2026-08-05 export shows no
    # association (chi2 = 3.86, dof = 5, p = 0.57, Cramer's V = 0.057).
    # Honest limit: v2 contributes only 56 users with text, so this test has
    # little power to detect a small difference. If the v2 with-text cohort
    # grows substantially, re-run that crosstab before continuing to lean on
    # it.
    "cluster_id": Policy.POOLABLE,
    "subcluster_id": Policy.POOLABLE,
    "subcluster_name": Policy.POOLABLE,
    # Session time is timed by the PLATFORM, not asked by either questionnaire,
    # so the registration cohort does not change how it is measured — and the
    # only timestamps the loader trusts are the v2-platform ISO ones, which means
    # both cohorts' values come from the same mechanism. Poolable.
    # Coverage is lopsided though (57 of 78 v2 users vs 13 of 1,314 v1 users, the
    # v1 ones being returning users who came back after the platform switch), so
    # a cohort-SPLIT reading of this column compares 13 people to 57. Pool it.
    "session_minutes": Policy.POOLABLE,
    "last_message_ts": Policy.POOLABLE,
    "usefulness_rating": Policy.POOLABLE,
    "rating_num": Policy.POOLABLE,
    "discovery_channel": Policy.POOLABLE,
    "discovery_other": Policy.POOLABLE,
}


def instrument_version(frame: pd.DataFrame) -> pd.Series:
    """`"v1"` where the migration marker is present, else `"v2"`.

    An export with no marker column at all yields all-`"v2"` — the correct
    reading once the v1 rows have aged out of the platform.
    """
    if V1_MARKER_COLUMN not in frame.columns:
        return pd.Series(["v2"] * len(frame), index=frame.index, dtype="object")
    marker = frame[V1_MARKER_COLUMN]
    return pd.Series(
        ["v1" if present else "v2" for present in marker.notna()],
        index=frame.index, dtype="object")


def policy_for(column: str) -> Policy:
    """The comparability policy for `column`, or raise naming the fix."""
    try:
        return POLICY[column]
    except KeyError:
        raise CohortError(
            f"'{column}' has no cohort policy, so it cannot be aggregated.\n"
            "  why:  the v1 and v2 registration surveys differ — some variables "
            "cannot be pooled across them (v1 excluded Colombian respondents; "
            "several questions were retired or added).\n"
            "  fix:  classify it in POLICY in src/sami/cohort.py as one of "
            "POOLABLE / SPLIT / V1_ONLY / V2_ONLY. See "
            "docs/superpowers/specs/2026-07-28-sami-v2-export-migration-design.md"
        ) from None


def requires_split(column: str) -> bool:
    """True when `column` must be reported per instrument version."""
    return policy_for(column) is Policy.SPLIT
