import re
import numpy as np
import pandas as pd
import pytest
from sami import metrics, load_sami, config


@pytest.fixture(scope="module")
def data():
    # metrics.py's functions are exercised here against the full facade output;
    # there is no fixture-based substitute small enough to be worth building.
    # Skip cleanly rather than error when the real, gitignored export is absent.
    if not (config.responses_path() and config.meal_path()):
        pytest.skip("real export not present (datasets/ holds no .xlsx)")
    return load_sami()


@pytest.fixture
def clustered():
    """Minimal message spine carrying cluster_id, spanning three weeks."""
    ts = pd.to_datetime(
        ["2026-06-01", "2026-06-02", "2026-06-08", "2026-06-09",
         "2026-06-15", "2026-06-16", "2026-06-16", "2026-06-17"])
    return pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u3", "u4", "u5", "u6", "u6"],
        # 5 distinct clusters (was 4, which sat exactly on the retired top_n=4
        # threshold and let the old rollup pass through unexercised): the
        # last row is cluster 4, not a repeat of cluster 3.
        "cluster_id": [0, 0, 0, 1, 1, 2, 3, 4],
        "city_canon": ["Bogotá", "Bogotá", "Medellín", "Cali",
                       "Cúcuta", "Cali", "Otra", "Otra"],
        "message": ["a", "b", "c", "d", "e", "f", "g", "h"],
        "ts": ts,
    })


def test_cluster_share_sums_to_one(clustered):
    s = metrics.cluster_share(clustered)
    assert s.sum() == pytest.approx(1.0, abs=1e-9)
    assert (s.values[:-1] >= s.values[1:]).all()   # descending


def test_city_cluster_mix_rows_sum_to_one(clustered):
    mix = metrics.city_cluster_mix(clustered, top_cities=2)
    assert "Other" in mix.index
    assert mix.shape[0] == 3   # 2 cities + Other
    for _, row in mix.iterrows():
        assert row.sum() == pytest.approx(1.0, abs=1e-9)


def test_weekly_cluster_counts_emits_every_cluster(clustered):
    """No 'Other' rollup: a mixed int/str key column cannot relate to dim_cluster."""
    wk = metrics.weekly_cluster_counts(clustered)
    assert wk.to_numpy().sum() == len(clustered)
    assert set(wk.columns) == set(clustered["cluster_id"].unique())
    assert all(isinstance(c, (int, np.integer)) for c in wk.columns)
    assert "Other" not in wk.columns


def test_weekly_cluster_counts_orders_columns_by_volume(clustered):
    wk = metrics.weekly_cluster_counts(clustered)
    totals = wk.sum(axis=0)
    assert list(totals.values) == sorted(totals.values, reverse=True)


def test_funnel_is_monotonic_and_tops_at_users(data):
    f = metrics.funnel_stages(data.responses, data.messages, data.meal)
    n = f["n"].to_numpy()
    # first four stages sit on the nested message-volume axis -> strictly non-increasing
    nested = n[:4]
    assert (nested[:-1] >= nested[1:]).all()
    assert int(n[0]) == data.responses["user_id"].nunique()
    assert pd.isna(f["conversion_from_prev"].iloc[0])       # first stage has no prior
    # surveyed is off the nested axis -> its conversion is deliberately NaN
    assert pd.isna(f["conversion_from_prev"].iloc[-1])


def test_funnel_labels_are_plain_language(data):
    """Dashboard-facing labels: sentence case, no jargon, no percentile notation."""
    f = metrics.funnel_stages(data.responses, data.messages, data.meal)
    stages = list(f["stage"])
    assert stages[0] == "Arrived"
    assert stages[1] == "Sent a message"
    assert stages[2] == "Sent 2 or more messages"
    assert stages[4] == "Answered the survey"
    # the heavy-user stage names its actual threshold instead of naming a percentile
    assert re.fullmatch(r"Sent \d+ or more messages", stages[3]), stages[3]
    for s in stages:
        assert s[0].isupper(), f"{s!r} is not sentence case"
        assert s == s[0] + s[1:].replace("SAMI", "SAMI"), s
        for banned in ("p90", "percentile", "≥", ">=", "power user", "MEAL"):
            assert banned not in s, f"{banned!r} leaked into label {s!r}"


def test_funnel_heavy_stage_threshold_matches_its_label(data):
    """The number in the label must be the threshold actually applied."""
    f = metrics.funnel_stages(data.responses, data.messages, data.meal)
    label = f["stage"].iloc[3]
    threshold = int(re.search(r"\d+", label).group())
    msgs_per_user = data.messages.groupby("user_id")["n_msgs_user"].first()
    assert int(f["n"].iloc[3]) == int((msgs_per_user >= threshold).sum())


def test_priority_matrix_frame_importable_but_deferred():
    # signature exists; calling without neg cache returns frame lacking the sentiment axis
    assert callable(metrics.priority_matrix_frame)


def test_negative_by_cluster_is_a_bounded_share(clustered):
    sent = pd.DataFrame(
        {"label": ["negative", "neutral", "negative", "neutral",
                   "neutral", "negative", "neutral", "neutral"]},
        index=clustered.index)
    s = metrics.negative_by_cluster(clustered, sent)
    assert ((s >= 0) & (s <= 1)).all()
    assert set(s.index) <= set(clustered["cluster_id"].unique())


def test_priority_matrix_is_keyed_on_cluster_id(clustered):
    meal = pd.DataFrame({"user_id": ["u1", "u3"], "rating_num": [5.0, 2.0],
                         "cluster_id": [0, 1]})
    pm = metrics.priority_matrix_frame(clustered, meal)
    assert pm.index.name == "cluster_id"
    assert set(pm.index) == {0, 1, 2, 3, 4}
    assert pm["messages"].sum() == len(clustered)
    # Exactly two axes here: repeat-asker share, and the (fallback) MEAL rating.
    # `>= 1` would pass even if the axis-counting logic broke entirely, and
    # n_axes is what stops a caller presenting a 2-axis score as the 3-axis one.
    assert (pm["n_axes"] == 2).all()


def test_priority_matrix_n_axes_counts_the_axes_actually_used(clustered):
    """n_axes must move with the inputs, not sit at a constant.

    It is the guard that stops a 2-axis unmet-need score being read as the
    3-axis one, so a test that merely asserts it is positive guards nothing.
    """
    meal = pd.DataFrame({"user_id": ["u1"], "rating_num": [4.0], "cluster_id": [0]})
    no_meal = meal.iloc[0:0]
    neg = pd.Series({0: 0.5, 1: 0.1, 2: 0.0, 3: 0.2, 4: 0.3})

    # repeat-asker only
    assert (metrics.priority_matrix_frame(clustered, no_meal)["n_axes"] == 1).all()
    # + MEAL rating
    assert (metrics.priority_matrix_frame(clustered, meal)["n_axes"] == 2).all()
    # + sentiment
    assert (metrics.priority_matrix_frame(
        clustered, meal, neg_by_cluster=neg)["n_axes"] == 3).all()


def test_priority_matrix_falls_back_on_small_meal_samples(clustered):
    """Fewer than min_meal_n responses in a cluster -> overall mean, flagged."""
    meal = pd.DataFrame({"user_id": ["u1", "u3"], "rating_num": [5.0, 1.0],
                         "cluster_id": [0, 1]})
    pm = metrics.priority_matrix_frame(clustered, meal, min_meal_n=20)
    assert pm["rating_is_fallback"].all()
    assert pm["mean_rating"].nunique() == 1   # everyone got the overall mean


def test_priority_matrix_uses_three_axes_when_sentiment_supplied(clustered):
    meal = pd.DataFrame({"user_id": ["u1"], "rating_num": [4.0], "cluster_id": [0]})
    neg = pd.Series({0: 0.5, 1: 0.1, 2: 0.0, 3: 0.2})
    pm = metrics.priority_matrix_frame(clustered, meal, neg_by_cluster=neg)
    assert (pm["n_axes"] == 3).all()
    assert "pct_negative" in pm.columns
