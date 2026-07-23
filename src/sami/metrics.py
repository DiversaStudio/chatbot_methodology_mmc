"""Reusable metric frames for NB2 (single compute path; run_pipeline reuses these)."""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import taxonomy


def category_share(frame: pd.DataFrame, col: str = "dominant_category") -> pd.Series:
    """Normalized category share (descending), excluding nothing — 'unclassified' shown."""
    return frame[col].value_counts(normalize=True).sort_values(ascending=False)


def _top_categories(messages: pd.DataFrame, top_n: int) -> list[str]:
    return list(messages["dominant_category"].value_counts().head(top_n).index)


def city_category_mix(messages: pd.DataFrame, top_cities: int = 5) -> pd.DataFrame:
    """100%-stacked source frame: rows = top-N cities + 'Other', cols = categories, rows sum to 1."""
    m = messages.copy()
    top = list(m["city_canon"].value_counts().head(top_cities).index)
    m["city_grp"] = np.where(m["city_canon"].isin(top), m["city_canon"], "Other")
    ct = pd.crosstab(m["city_grp"], m["dominant_category"])
    # order rows: top cities in frequency order, then Other last
    order = [c for c in top if c in ct.index] + (["Other"] if "Other" in ct.index else [])
    ct = ct.reindex(order)
    return ct.div(ct.sum(axis=1), axis=0)


def weekly_category_counts(messages: pd.DataFrame, top_n: int = 4) -> pd.DataFrame:
    """Messages per week (Monday-start, via W-SUN periods) x top-N category + 'Other'. Record-arrival grain."""
    m = messages.dropna(subset=["ts"]).copy()
    top = _top_categories(m, top_n)
    m["cat_grp"] = np.where(m["dominant_category"].isin(top), m["dominant_category"], "Other")
    m["week_start"] = m["ts"].dt.to_period("W-SUN").dt.start_time
    wk = m.pivot_table(index="week_start", columns="cat_grp", values="user_id",
                       aggfunc="count", fill_value=0)
    cols = [c for c in top if c in wk.columns] + (["Other"] if "Other" in wk.columns else [])
    return wk.reindex(columns=cols, fill_value=0)


def funnel_stages(responses: pd.DataFrame, messages: pd.DataFrame,
                  meal: pd.DataFrame) -> pd.DataFrame:
    """Ordered engagement funnel with absolute n and stage-to-stage conversion.

    The first four stages sit on a single, strictly nested engagement axis —
    message volume — so each is a genuine subset of the prior (mixing the
    questions axis from `responses` with the messages axis broke monotonicity):

        arrived (users) -> sent ≥1 message -> engaged (≥2 messages) ->
        power user (≥p90 messages)

    The fifth stage, ``surveyed (MEAL)``, is **off that nested axis**: it is the
    MEAL respondent cohort, which is not a subset of power users (a respondent
    need not be a heavy messager). It is appended for context only, so its
    ``conversion_from_prev`` is deliberately NaN — a "% of power users" figure
    there would be analytically false. The first stage n equals the
    reconciliation user count; every n traces to the P10 reconciliation table.
    """
    users = responses["user_id"].nunique()
    msgs_per_user = messages.groupby("user_id")["n_msgs_user"].first()
    sent_1 = int((msgs_per_user >= 1).sum())
    engaged = int((msgs_per_user >= 2).sum())
    p90 = msgs_per_user.quantile(0.90)
    power = int((msgs_per_user >= p90).sum()) if msgs_per_user.notna().any() else 0
    surveyed = meal["user_id"].nunique()
    stages = [
        ("arrived", users),
        ("sent ≥1 message", sent_1),
        ("engaged (≥2 messages)", engaged),
        ("power user (≥p90 messages)", power),
        ("surveyed (MEAL, separate cohort)", surveyed),
    ]
    df = pd.DataFrame(stages, columns=["stage", "n"])
    df["conversion_from_prev"] = df["n"] / df["n"].shift(1)
    # surveyed is off the nested engagement axis — not a conversion from power users
    df.loc[df.index[-1], "conversion_from_prev"] = np.nan
    return df


def negative_by_category(messages: pd.DataFrame, sentiment: pd.DataFrame,
                         col: str = "dominant_category") -> pd.Series:
    """Share of messages classified negative, per official category.

    `sentiment` must be index-aligned to `messages` (as `nlp.sentiment_messages`
    returns). This is the series NB2's priority matrix has been waiting on — its
    unmet-need axis. Whether the resulting numbers may be *quoted* depends on the
    NB3 validation gate (`validation.validation_report(...)['gate_passed']`);
    below the kappa bar the caller must use it directionally only.
    """
    neg = (sentiment.loc[messages.index, "label"] == "negative")
    return neg.groupby(messages[col]).mean().sort_values(ascending=False)


def priority_matrix_frame(messages: pd.DataFrame, meal: pd.DataFrame,
                          neg_by_category: pd.Series | None = None) -> pd.DataFrame:
    """DEFERRED (NB2 §6 climax): per-category priority frame.

    x = message volume, y = unmet-need score (z-scored blend of % repeat-askers,
    % negative sentiment, inverted mean MEAL rating), bubble = users. The
    negative-sentiment axis (`neg_by_category`) comes from NB3's validated
    sentiment cache, which does not exist yet — this function is importable and
    unit-covered but is NOT rendered by NB2 until NB3 lands. Do not call from the
    notebook this pass.
    """
    vol = messages["dominant_category"].value_counts()
    frame = pd.DataFrame({"messages": vol})
    frame["users"] = messages.groupby("dominant_category")["user_id"].nunique()
    if neg_by_category is not None:
        frame["pct_negative"] = neg_by_category.reindex(frame.index)
    return frame
