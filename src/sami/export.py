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


def build_agg_city(dim_user: pd.DataFrame) -> pd.DataFrame:
    return (dim_user.groupby(["city_canon", "department"], dropna=False)
            .size().reset_index(name="n_users"))


def build_agg_funnel(responses, messages, meal) -> pd.DataFrame:
    f = metrics.funnel_stages(responses, messages, meal).reset_index(drop=True)
    f.insert(0, "stage_order", range(len(f)))
    return f


def build_agg_entities_by_kind(messages: pd.DataFrame) -> pd.DataFrame:
    by_kind = taxonomy.entity_counts_by_kind(messages["message"])
    rows = [{"kind": kind, "entity": ent, "n": int(n)}
            for kind, s in by_kind.items() for ent, n in s.items()]
    return pd.DataFrame(rows, columns=["kind", "entity", "n"])


def build_agg_weekly_category(messages: pd.DataFrame) -> pd.DataFrame:
    wk = metrics.weekly_category_counts(messages, top_n=4)
    return (wk.reset_index()
            .melt(id_vars="week_start", var_name="category", value_name="n")
            .rename(columns={"week_start": "week"}))


def build_agg_daily_volume(messages: pd.DataFrame) -> pd.DataFrame:
    d = messages.dropna(subset=["ts"]).set_index("ts").resample("D").size()
    return d.reset_index(name="n").rename(columns={"ts": "day"})


def build_agg_weekly_rating(fact_meal: pd.DataFrame) -> pd.DataFrame:
    m = (fact_meal.dropna(subset=["ts", "rating_num"]).set_index("ts")
         .resample("W")["rating_num"].agg(["mean", "count"]))
    return m.reset_index().rename(columns={"ts": "week", "mean": "mean_rating",
                                           "count": "n"})


def build_agg_priority_matrix(messages, fact_meal, dim_user,
                              neg_by_cat: "pd.Series | None" = None) -> pd.DataFrame:
    msgs_pm = messages[messages["dominant_category"] != "unclassified"]
    meal_cat = fact_meal.merge(
        dim_user[["user_id", "dominant_category"]].drop_duplicates("user_id"),
        on="user_id", how="left")
    pm = metrics.priority_matrix_frame(msgs_pm, meal_cat, neg_by_category=neg_by_cat)
    return pm.reset_index().rename(columns={"dominant_category": "category"})


def build_dim_cluster(prof: pd.DataFrame, names: dict) -> pd.DataFrame:
    d = prof.reset_index().rename(columns={"archetype": "cluster_id"})
    d["name"] = d["cluster_id"].map(names)
    cols = ["cluster_id", "name", "n_users", "n_messages", "median_age", "top_categories"]
    return d[[c for c in cols if c in d.columns]]


def build_nlp_umap(XY, labels, user_ids) -> pd.DataFrame:
    return pd.DataFrame({"user_id": list(user_ids), "x": XY[:, 0], "y": XY[:, 1],
                         "cluster_id": list(labels)})


def build_nlp_cluster_terms(terms: dict) -> pd.DataFrame:
    rows = [{"cluster_id": cid, "rank": rank, "term": term, "weight": float(w)}
            for cid, s in terms.items()
            for rank, (term, w) in enumerate(s.items())]
    return pd.DataFrame(rows, columns=["cluster_id", "rank", "term", "weight"])


def build_nlp_emergent_themes(messages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for slug, pat in taxonomy.CANDIDATE_INTENT_PROBES.items():
        hit = messages["message"].str.contains(pat, case=False, regex=True, na=False)
        rows.append({"theme": PROBE_EN.get(slug, slug), "slug": slug,
                     "n_messages": int(hit.sum()),
                     "n_users": int(messages.loc[hit, "user_id"].nunique())})
    return (pd.DataFrame(rows).sort_values("n_users", ascending=False)
            .reset_index(drop=True))


def build_nlp_tone_confusion(report: dict) -> pd.DataFrame:
    cm = report["confusion"]
    long = (cm.reset_index()
            .melt(id_vars=cm.index.name, var_name=cm.columns.name, value_name="n"))
    return long.rename(columns={cm.index.name: "human_label",
                                cm.columns.name: "model_label"})


def build_nlp_voices(msgs_lab: pd.DataFrame, names: dict) -> pd.DataFrame:
    rows = []
    for cid in sorted(msgs_lab["archetype"].unique()):
        marker = taxonomy.ARCHETYPE_NAMES[cid]["marker"]
        g = (msgs_lab[(msgs_lab["archetype"] == cid)
                      & msgs_lab["message"].str.len().between(60, 190)
                      & msgs_lab["message"].str.contains(marker, case=False, na=False)]
             .sort_values(["user_id", "seq"], kind="stable"))
        rows.append({"cluster_id": int(cid), "name": names.get(cid),
                     "message": g["message"].iloc[0] if len(g) else "—"})
    return pd.DataFrame(rows)
