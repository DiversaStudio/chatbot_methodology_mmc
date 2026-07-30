from pathlib import Path
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


def test_category_share_sums_to_one(data):
    s = metrics.category_share(data.messages)
    assert s.sum() == pytest.approx(1.0, abs=1e-9)
    assert (s.values[:-1] >= s.values[1:]).all()  # descending


def test_city_category_mix_rows_sum_to_one(data):
    mix = metrics.city_category_mix(data.messages, top_cities=5)
    assert "Other" in mix.index
    assert mix.shape[0] == 6  # 5 cities + Other
    for _, row in mix.iterrows():
        assert row.sum() == pytest.approx(1.0, abs=1e-9)


def test_weekly_counts_sum_to_message_total(data):
    wk = metrics.weekly_category_counts(data.messages, top_n=4)
    assert wk.to_numpy().sum() == len(data.messages)
    assert wk.shape[1] == 5  # top-4 + Other


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


def test_negative_by_category_is_a_bounded_share(data):
    rng = np.random.default_rng(0)
    sent = pd.DataFrame(
        {"label": rng.choice(["negative", "neutral", "positive"], size=len(data.messages))},
        index=data.messages.index,
    )
    s = metrics.negative_by_category(data.messages, sent)
    assert ((s >= 0) & (s <= 1)).all()
    assert set(s.index) <= set(data.messages["dominant_category"].unique())
    assert (s.values[:-1] >= s.values[1:]).all()  # descending


def _matrix_fixture():
    messages = pd.DataFrame({
        "user_id": ["a"] * 6 + ["b"] * 5 + ["c"] + ["d"] + ["e"] * 2,
        "message": ["m"] * 15,
        "dominant_category": ["legal_documentation"] * 11 + ["employment"] * 4,
    })
    meal = pd.DataFrame({
        "user_id": ["a", "b", "c", "d"],
        "rating_num": [1.0, 2.0, 5.0, 5.0],
        "dominant_category": ["legal_documentation"] * 2 + ["employment"] * 2,
    })
    return messages, meal


def test_priority_matrix_blends_available_axes():
    messages, meal = _matrix_fixture()
    neg = pd.Series({"legal_documentation": 0.30, "employment": 0.05})
    f = metrics.priority_matrix_frame(messages, meal, neg_by_category=neg)
    assert f["n_axes"].eq(3).all()                       # repeat + negative + rating
    assert f.loc["legal_documentation", "messages"] == 11
    assert f.loc["legal_documentation", "users"] == 2
    # the category that is heavier, angrier and worse-rated must score higher unmet need
    assert f.loc["legal_documentation", "unmet_need"] > f.loc["employment", "unmet_need"]


def test_priority_matrix_without_sentiment_uses_two_axes():
    messages, meal = _matrix_fixture()
    f = metrics.priority_matrix_frame(messages, meal)
    assert f["n_axes"].eq(2).all()
    assert "pct_negative" not in f.columns


def test_priority_matrix_small_n_meal_falls_back_to_overall():
    messages, meal = _matrix_fixture()
    f = metrics.priority_matrix_frame(messages, meal, min_meal_n=20)
    # every category has < 20 MEAL responses -> all fall back to the single overall mean
    assert f["rating_is_fallback"].all()
    assert f["mean_rating"].nunique() == 1
    assert f["mean_rating"].iloc[0] == pytest.approx(meal["rating_num"].mean())
    # with the bar dropped, real per-category means are used instead
    g = metrics.priority_matrix_frame(messages, meal, min_meal_n=1)
    assert not g["rating_is_fallback"].any()
    assert g["mean_rating"].nunique() == 2
