"""Reusable metric frames for NB2 (single compute path; run_pipeline reuses these)."""
from __future__ import annotations
import numpy as np
import pandas as pd


def cluster_share(frame: pd.DataFrame, col: str = "cluster_id") -> pd.Series:
    """Normalized cluster share (descending). Nothing is excluded."""
    return frame[col].value_counts(normalize=True).sort_values(ascending=False)


def city_cluster_mix(messages: pd.DataFrame, top_cities: int = 5) -> pd.DataFrame:
    """100%-stacked source frame: rows = top-N cities + 'Other', cols = clusters, rows sum to 1."""
    m = messages.copy()
    top = list(m["city_canon"].value_counts().head(top_cities).index)
    m["city_grp"] = np.where(m["city_canon"].isin(top), m["city_canon"], "Other")
    ct = pd.crosstab(m["city_grp"], m["cluster_id"])
    # order rows: top cities in frequency order, then Other last
    order = [c for c in top if c in ct.index] + (["Other"] if "Other" in ct.index else [])
    ct = ct.reindex(order)
    return ct.div(ct.sum(axis=1), axis=0)


def weekly_cluster_counts(messages: pd.DataFrame) -> pd.DataFrame:
    """Messages per week (Monday-start, via W-SUN periods) x cluster.

    Record-arrival grain. Columns are ordered by descending total volume.

    EVERY cluster gets its own column. The retired category version folded the
    tail into an "Other" bucket, which was harmless when the key was a string;
    with integer cluster ids it makes the exported key column mixed-type, and
    Power BI cannot relate a mixed-type column to dim_cluster[cluster_id] -- so
    the chart would lose the names, colours and sort order that dim_cluster
    exists to supply. If k ever grows past the readable ceiling, theme's
    K_SOFT_CAP warning is what says so; silently hiding clusters here is not.

    NOTE the reading this carries: clusters are assigned per USER, so a message
    counts under its author's cluster. The series is "messages written this week
    by users of this type", not "messages about this topic this week".
    """
    m = messages.dropna(subset=["ts"]).copy()
    m["week_start"] = m["ts"].dt.to_period("W-SUN").dt.start_time
    wk = m.pivot_table(index="week_start", columns="cluster_id", values="user_id",
                       aggfunc="count", fill_value=0)
    return wk.reindex(columns=wk.sum(axis=0).sort_values(ascending=False).index)


def funnel_stages(responses: pd.DataFrame, messages: pd.DataFrame,
                  meal: pd.DataFrame) -> pd.DataFrame:
    """Ordered engagement funnel with absolute n and stage-to-stage conversion.

    The first four stages sit on a single, strictly nested engagement axis —
    message volume — so each is a genuine subset of the prior (mixing the
    questions axis from `responses` with the messages axis broke monotonicity):

        Arrived -> Sent a message -> Sent 2 or more messages ->
        Sent N or more messages

    The fifth stage, ``Answered the survey``, is **off that nested axis**: it is
    the MEAL respondent cohort, which is not a subset of the heaviest messagers
    (a respondent need not be a heavy messager). It is appended for context only,
    so its ``conversion_from_prev`` is deliberately NaN — a "% of heavy users"
    figure there would be analytically false. The first stage n equals the
    reconciliation user count; every n traces to the P10 reconciliation table.

    **Labels are dashboard-facing prose, not analyst shorthand** (2026-07-29).
    They are sentence case, spell out "2 or more" rather than "≥2", and name the
    heavy-user stage by its *actual message threshold* instead of by the
    percentile that produced it — "Sent 7 or more messages", not "power user
    (≥p90 messages)". The threshold is still the 90th percentile underneath; a
    reader should not have to know that to read the chart. Because the label
    carries the number, it is derived from the same variable the count uses, so
    the two can never disagree, and it re-derives itself when the distribution
    moves.
    """
    users = responses["user_id"].nunique()
    msgs_per_user = messages.groupby("user_id")["n_msgs_user"].first()
    sent_1 = int((msgs_per_user >= 1).sum())
    engaged = int((msgs_per_user >= 2).sum())
    # ceil, so the threshold is a whole number of messages a user can actually
    # have sent -- the label quotes it verbatim and the count must match it.
    has_msgs = bool(msgs_per_user.notna().any())
    heavy_min = int(np.ceil(msgs_per_user.quantile(0.90))) if has_msgs else 2
    heavy = int((msgs_per_user >= heavy_min).sum()) if has_msgs else 0
    surveyed = meal["user_id"].nunique()
    stages = [
        ("Arrived", users),
        ("Sent a message", sent_1),
        ("Sent 2 or more messages", engaged),
        (f"Sent {heavy_min} or more messages", heavy),
        ("Answered the survey", surveyed),
    ]
    df = pd.DataFrame(stages, columns=["stage", "n"])
    df["conversion_from_prev"] = df["n"] / df["n"].shift(1)
    # surveyed is off the nested engagement axis — not a conversion from power users
    df.loc[df.index[-1], "conversion_from_prev"] = np.nan
    return df


def negative_by_cluster(messages: pd.DataFrame, sentiment: pd.DataFrame,
                        col: str = "cluster_id") -> pd.Series:
    """Share of messages classified negative, per cluster.

    `sentiment` must be index-aligned to `messages` (as `nlp.sentiment_messages`
    returns). This is the priority matrix's unmet-need axis. Whether the
    resulting numbers may be *quoted* depends on the NB3 validation gate
    (`validation.validation_report(...)['gate_passed']`); below the kappa bar the
    caller must use it directionally only.
    """
    neg = (sentiment.loc[messages.index, "label"] == "negative")
    return neg.groupby(messages[col]).mean().sort_values(ascending=False)


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and np.isfinite(sd) and sd > 0 else s * 0.0


def priority_matrix_frame(messages: pd.DataFrame, meal: pd.DataFrame,
                          neg_by_cluster: pd.Series | None = None,
                          min_meal_n: int = 20) -> pd.DataFrame:
    """NB2 §6 climax: per-cluster priority frame — which needs are big AND badly served.

    x = message volume, y = `unmet_need` (mean of the z-scores of % repeat-askers,
    % negative sentiment, and *inverted* mean MEAL rating), bubble = users.

    Two guards matter more than the blend itself:

    - **Small-n MEAL fallback.** The MEAL join is ~69 users across the clusters, so a
      per-cluster mean rating is often built on a handful of responses. Clusters with
      fewer than `min_meal_n` responses fall back to the overall mean rating (column
      `rating_is_fallback` marks them) rather than contributing an unstable per-cluster
      mean to the score.
    - **The sentiment axis is optional.** Without `neg_by_cluster` the score is built
      from the two axes that remain, and `n_axes` records how many were used. Callers
      must not present a 2-axis score as if it were the 3-axis one.

    Whether the sentiment axis may be quoted as a *rate* depends on NB3's validation gate;
    below the kappa bar the caller must label the axis directional.
    """
    vol = messages["cluster_id"].value_counts()
    frame = pd.DataFrame({"messages": vol})
    frame.index.name = "cluster_id"
    frame["users"] = messages.groupby("cluster_id")["user_id"].nunique()

    # repeat askers: users at or above the p90 message volume, as a share of the cluster
    per_user = messages.groupby("user_id").agg(
        n=("message", "size"), cid=("cluster_id", "first"))
    p90 = per_user["n"].quantile(0.90)
    frame["pct_repeat"] = (per_user["n"] >= p90).groupby(per_user["cid"]).mean().reindex(frame.index)

    # mean MEAL rating per cluster, with the small-n fallback
    m = meal.dropna(subset=["rating_num"]) if "rating_num" in meal.columns else meal.iloc[0:0]
    if len(m) and "cluster_id" in m.columns:
        grp = m.groupby("cluster_id")["rating_num"]
        cat_mean, cat_n = grp.mean(), grp.size()
        overall = float(m["rating_num"].mean())
        rating = cat_mean.reindex(frame.index)
        n_resp = cat_n.reindex(frame.index).fillna(0)
        fallback = n_resp < min_meal_n
        frame["mean_rating"] = rating.where(~fallback, overall)
        frame["meal_n"] = n_resp.astype(int)
        frame["rating_is_fallback"] = fallback
    else:
        frame["mean_rating"] = np.nan
        frame["meal_n"] = 0
        frame["rating_is_fallback"] = True

    axes = [_zscore(frame["pct_repeat"])]
    if neg_by_cluster is not None:
        frame["pct_negative"] = neg_by_cluster.reindex(frame.index)
        axes.append(_zscore(frame["pct_negative"]))
    if frame["mean_rating"].notna().any():
        axes.append(_zscore(-frame["mean_rating"]))   # inverted: worse rating -> higher need

    frame["n_axes"] = len(axes)
    frame["unmet_need"] = pd.concat(axes, axis=1).mean(axis=1)
    return frame.sort_values("messages", ascending=False)
