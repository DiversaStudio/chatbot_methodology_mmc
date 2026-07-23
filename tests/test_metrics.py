import numpy as np
import pandas as pd
import pytest
from sami import metrics, load_sami


@pytest.fixture(scope="module")
def data():
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
