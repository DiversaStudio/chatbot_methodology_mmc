"""The fixtures are test infrastructure — assert their shape so a broken
regeneration is caught here, not as a confusing failure in another module."""
from pathlib import Path
import pandas as pd

FIX = Path(__file__).resolve().parent / "fixtures"
USERS = FIX / "users_v2.xlsx"
SURVEY = FIX / "survey_v2.xlsx"


def test_fixtures_exist():
    assert USERS.exists() and SURVEY.exists()


def test_users_fixture_shape():
    df = pd.read_excel(USERS, header=2)
    assert len(df) == 7  # 6 data rows + 1 empty-id row
    assert "Address" in df.columns and "Created At" in df.columns
    # Null-id row must be present and pinned (Task 4 relies on float64 inference from NA)
    assert df["Address"].isna().sum() == 1, "fixture must have exactly one null Address"
    assert df["Address"].dtype == "float64", "Address column must be float64 (for .0 parsing)"
    # Cohort counts against non-null rows only
    non_null_rows = df[df["Address"].notna()]
    assert non_null_rows[non_null_rows["Migrated From v1"].notna()].shape[0] == 4  # v1 cohort
    assert non_null_rows[non_null_rows["Migrated From v1"].isna()].shape[0] == 2   # v2-native cohort


def test_users_fixture_reproduces_float_phone_parsing():
    """The real export stores Address as a number, so pandas yields 5.7e11
    and str() gives a trailing '.0'. The loader must survive that."""
    df = pd.read_excel(USERS, header=2)
    assert str(df["Address"].iloc[0]).endswith(".0")


def test_survey_fixture_has_empty_v1_duplicate_columns():
    """Defect 4: the v1 variants come first and are empty; the v2 variants
    carry the data. The column picker must prefer the populated one."""
    df = pd.read_excel(SURVEY, header=2)
    useful = [c for c in df.columns if "qué tan útil" in str(c)]
    assert len(useful) == 2, "fixture must carry BOTH usefulness columns"
    assert df[useful[0]].notna().sum() == 0, "first (v1) must be empty"
    assert df[useful[1]].notna().sum() == 4, "second (v2) must carry data"


def test_survey_fixture_shape():
    """Survey fixture must have null-id row pinned (Task 4 relies on float64 inference)."""
    df = pd.read_excel(SURVEY, header=2)
    assert df["Respondent"].isna().sum() == 1, "fixture must have exactly one null Respondent"
    assert df["Respondent"].dtype == "float64", "Respondent column must be float64 (for .0 parsing)"


def test_fixtures_contain_no_real_phone_numbers():
    for path in (USERS, SURVEY):
        joined = pd.read_excel(path, header=2).astype(str).to_string()
        assert "whatsapp:" not in joined
        # every fabricated number is in the 5711100000xx block
        assert "573" not in joined
