import pandas as pd
import pytest
from sami import cohort


def test_instrument_version_splits_on_migration_marker():
    df = pd.DataFrame({cohort.V1_MARKER_COLUMN: ["v1:100", None, "v1:102", None]})
    assert list(cohort.instrument_version(df)) == ["v1", "v2", "v1", "v2"]


def test_instrument_version_all_v2_when_marker_column_absent():
    """A future export with no migrated rows must not crash."""
    df = pd.DataFrame({"user_id": ["a", "b"]})
    assert list(cohort.instrument_version(df)) == ["v2", "v2"]


def test_nationality_requires_split():
    """v1 survey Q3 terminated Colombian respondents, so a pooled nationality
    total measures the old exit rule, not the user base."""
    assert cohort.policy_for("nationality_canon") is cohort.Policy.SPLIT
    assert cohort.requires_split("nationality_canon") is True


def test_retired_questions_are_v1_only():
    for col in ("away_duration_canon", "would_recommend", "recommendation_text"):
        assert cohort.policy_for(col) is cohort.Policy.V1_ONLY


def test_new_question_is_v2_only():
    assert cohort.policy_for("no_usefulness_reason") is cohort.Policy.V2_ONLY


def test_ordinary_variables_are_poolable():
    for col in ("city_canon", "age_num", "gender_clean", "usefulness_rating"):
        assert cohort.policy_for(col) is cohort.Policy.POOLABLE


def test_unclassified_column_raises_with_the_fix():
    with pytest.raises(cohort.CohortError) as e:
        cohort.policy_for("some_new_field")
    msg = str(e.value)
    assert "some_new_field" in msg
    assert "src/sami/cohort.py" in msg


def test_requires_split_is_false_for_poolable():
    assert cohort.requires_split("city_canon") is False
