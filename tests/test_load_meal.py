import re
import pandas as pd
from sami import load, config, schema
from conftest import requires_real_data

SALT = "test_salt"


def test_meal_columns_renamed(survey_fixture):
    df = load.load_meal(survey_fixture, salt=SALT)
    for col in ["user_id", "usefulness_rating", "would_recommend",
                "recommendation_text", "discovery_channel", "discovery_other"]:
        assert col in df.columns
    assert "Name" not in df.columns


def test_meal_dedup_one_row_per_user(survey_fixture):
    # Exact count against the committed synthetic fixture: 4 of the 5 raw rows
    # carry a valid respondent id (the 5th is the null-id row _read_export
    # rejects). See requires_real_data below for the property that must hold
    # on the real, gitignored export instead.
    df = load.load_meal(survey_fixture, salt=SALT)
    assert df["user_id"].is_unique
    assert len(df) == 4


@requires_real_data
def test_meal_one_row_per_user_on_real_export():
    df = load.load_meal(salt=SALT)
    assert df["user_id"].is_unique


@requires_real_data
def test_meal_keeps_most_recent():
    # P8: for a user with multiple raw MEAL rows, the kept row must be the most
    # recent one (max ts). Reconstruct the raw per-user timestamps using the
    # SAME schema machinery the loader uses (detect_header_row + normalize_columns)
    # rather than re-implementing the read -- the v2 export's id column is
    # "Respondent", not "Name", and only normalize_columns knows that mapping.
    # No committed fixture has a duplicate respondent id, so this stays on real
    # data.
    header_row = schema.detect_header_row(config.meal_path(), source="meal")
    raw = pd.read_excel(config.meal_path(), header=header_row)
    raw = schema.normalize_columns(raw, "meal")
    raw = raw[raw["Name"].map(lambda x: bool(load.digits(x)), na_action="ignore").fillna(False)].copy()
    raw["uid"] = raw["Name"].map(lambda n: load.pseudonymize(n, SALT))
    raw["ts"] = pd.to_datetime(raw["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    sizes = raw.groupby("uid").size()
    dup_uids = sizes[sizes > 1].index
    assert len(dup_uids) > 0, "expected at least one user with duplicate raw MEAL rows"

    df = load.load_meal(salt=SALT)
    kept = df.set_index("user_id")["ts"]
    for uid in dup_uids:
        expected_max = raw.loc[raw["uid"] == uid, "ts"].max()
        assert kept.loc[uid] == expected_max


def test_meal_no_raw_identifiers(survey_fixture):
    df = load.load_meal(survey_fixture, salt=SALT)
    # user_id is the intended pseudonymized hex hash: a 12-char hex string can
    # incidentally contain a run of 7+ digit characters by chance (hex digits
    # are 0-9a-f), which is not a PII leak. Exclude it from the raw-digit scan.
    scan_cols = [c for c in df.columns if c != "user_id"]
    joined = " ".join(df[scan_cols].astype(str).fillna("").values.ravel())
    assert "whatsapp:" not in joined
    assert not re.search(r"\d{7,}", joined)
