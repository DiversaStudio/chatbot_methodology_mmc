import numpy as np
import pandas as pd
import pytest
from sami import load_sami, export


@pytest.fixture(scope="module")
def SD():
    return load_sami()


def test_dim_category_schema():
    d = export.build_dim_category()
    assert list(d.columns) == ["category_key", "category_es", "category_en"]
    assert "legal_documentation" in set(d["category_key"])
    assert d["category_key"].is_unique


def test_dim_user_one_row_per_user(SD):
    d = export.build_dim_user(SD.responses, SD.messages)
    assert d["user_id"].is_unique
    assert d["user_id"].nunique() == SD.responses["user_id"].nunique()
    for col in ["user_id", "gender_clean", "age_num", "department",
                "n_msgs_user", "has_text", "cluster_id"]:
        assert col in d.columns
    # has_text == user appears in the message spine
    assert int(d["has_text"].sum()) == SD.messages["user_id"].nunique()
    # cluster_id is null without an NLP label map
    assert d["cluster_id"].isna().all()


def test_dim_user_no_pii(SD):
    from sami import qa
    assert qa.pii_scan(export.build_dim_user(SD.responses, SD.messages)) == []


def test_fact_message_grain_and_join(SD):
    f = export.build_fact_message(SD.messages)
    assert len(f) == len(SD.messages)
    assert f["message_id"].is_unique
    assert list(f["message_id"]) == list(SD.messages.index)
    assert f["sentiment_label"].isna().all()   # no sentiment passed
    assert f["cluster_id"].isna().all()


def test_fact_message_sentiment_join(SD):
    # synthetic sentiment aligned to the messages index
    sent = pd.DataFrame({"label": ["negative"] * len(SD.messages)}, index=SD.messages.index)
    f = export.build_fact_message(SD.messages, sentiment=sent)
    assert (f["sentiment_label"] == "negative").all()


def test_fact_meal_rating_num(SD):
    f = export.build_fact_meal(SD.meal)
    assert f["user_id"].is_unique
    assert "rating_num" in f.columns
    # rating_num is 1-5 or NaN, never a raw string
    vals = f["rating_num"].dropna().unique()
    assert set(vals).issubset({1, 2, 3, 4, 5})
