"""Power BI gold-layer builders + writer.

Pure `build_*(frames) -> DataFrame` functions (no I/O) plus `write_all`, the only
function that touches disk. `run_pipeline.py` is the sole production caller. See
docs/superpowers/specs/2026-07-24-sami-exports-powerbi-design.md.
"""
from __future__ import annotations
import pandas as pd

from . import metrics, taxonomy, qa

# EN display for the official categories (chart text only) — mirrors the notebooks.
CAT_EN = {
    "legal_documentation": "Legal & documentation",
    "humanitarian_assistance": "Humanitarian assistance",
    "protection": "Protection",
    "employment": "Employment",
    "organization_search": "Finding organizations",
    "journey_information": "Journey information",
    "services": "Services",
    "unclassified": "Unclassified",
}
# EN display for the emergent-need probes (mirrors NB3).
PROBE_EN = {
    "transport_logistics": "Transport & movement",
    "entrepreneurship": "Enterprise & livelihood",
    "procedure_troubleshooting": "Stuck in a procedure",
    "human_handoff": "Reach a person",
    "fraud_protection": "Fraud & scams",
    "connectivity": "Connectivity / phone",
}
# Ordinal 1-5 keyed to the observed MEAL usefulness vocabulary (mirrors NB2).
RATING_NUM = {
    "Muy útil": 5, "Útil": 4, "Medianamente útil": 3, "Poco útil": 2, "Nada útil": 1,
}

# Profile columns collapsed one-row-per-user (first non-null in ts order).
_PROFILE_COLS = [
    "gender_clean", "age_num", "age_flag", "city_canon", "department",
    "nationality_canon", "away_duration_canon", "away_duration_order",
    "city_duration_canon", "city_duration_order", "dominant_category", "n_questions",
]
# Raw survey columns that carry into dim_user under friendlier names.
_RAW_RENAME = {"Minors": "minors", "Age Ranges": "age_range",
               "Destination_Country": "destination_country"}


def build_dim_category() -> pd.DataFrame:
    return pd.DataFrame(
        [{"category_key": k, "category_es": k, "category_en": v} for k, v in CAT_EN.items()]
    )


def build_dim_user(responses: pd.DataFrame, messages: pd.DataFrame,
                   lab: "pd.Series | None" = None) -> pd.DataFrame:
    """One row per user. `lab` (Series indexed by user_id -> archetype) fills
    `cluster_id`; None leaves it null (the --skip-nlp contract)."""
    r = responses.sort_values("ts", kind="stable")
    cols = [c for c in _PROFILE_COLS if c in r.columns]
    agg = r.groupby("user_id")[cols].first()
    for raw, new in _RAW_RENAME.items():
        if raw in r.columns:
            agg[new] = r.groupby("user_id")[raw].first()
    mpu = messages.groupby("user_id").size()
    agg["n_msgs_user"] = agg.index.to_series().map(mpu).fillna(0).astype(int)
    agg["has_text"] = agg["n_msgs_user"] > 0
    agg["cluster_id"] = (agg.index.to_series().map(lab.to_dict())
                         if lab is not None else pd.NA)
    return agg.reset_index()


_FACT_MSG_COLS = ["message_id", "user_id", "ts", "city_canon",
                  "dominant_category", "seq", "n_msgs_user", "message"]


def build_fact_message(messages: pd.DataFrame, sentiment: "pd.DataFrame | None" = None,
                       lab: "pd.Series | None" = None) -> pd.DataFrame:
    f = messages.reset_index().rename(columns={"index": "message_id"})
    f = f[[c for c in _FACT_MSG_COLS if c in f.columns]].copy()
    f["sentiment_label"] = (sentiment.loc[messages.index, "label"].values
                            if sentiment is not None else pd.NA)
    f["cluster_id"] = (f["user_id"].map(lab.to_dict()) if lab is not None else pd.NA)
    return f


_FACT_MEAL_COLS = ["user_id", "ts", "usefulness_rating", "rating_num",
                   "would_recommend", "recommendation_text", "discovery_channel"]


def build_fact_meal(meal: pd.DataFrame) -> pd.DataFrame:
    f = meal.copy()
    f["rating_num"] = f["usefulness_rating"].map(RATING_NUM)
    return f[[c for c in _FACT_MEAL_COLS if c in f.columns]].copy()
