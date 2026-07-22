import re
import pandas as pd
from sami import load, config

SALT = "test_salt"


def test_meal_columns_renamed():
    df = load.load_meal(salt=SALT)
    for col in ["user_id", "usefulness_rating", "would_recommend",
                "recommendation_text", "discovery_channel", "discovery_other"]:
        assert col in df.columns
    assert "Name" not in df.columns


def test_meal_dedup_one_row_per_user():
    df = load.load_meal(salt=SALT)
    assert df["user_id"].is_unique
    assert len(df) == 69  # unique MEAL users; 78 raw rows


def test_meal_keeps_most_recent():
    # P8: for a user with multiple raw MEAL rows, the kept row must be the most
    # recent one (max ts). Reconstruct the raw per-user timestamps the same way
    # the loader does and compare against load_meal's surviving row.
    raw = pd.read_excel(config.MEAL_PATH, header=config.DATA_HEADER_ROW)
    raw = raw[raw["Name"].astype(str).str.startswith("whatsapp")].copy()
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


def test_meal_no_raw_identifiers():
    df = load.load_meal(salt=SALT)
    # user_id is the intended pseudonymized hex hash: a 12-char hex string can
    # incidentally contain a run of 7+ digit characters by chance (hex digits
    # are 0-9a-f), which is not a PII leak. Exclude it from the raw-digit scan
    # (4 of the 69 real MEAL user_id hashes do contain such a run by chance).
    scan_cols = [c for c in df.columns if c != "user_id"]
    joined = " ".join(df[scan_cols].astype(str).fillna("").values.ravel())
    assert "whatsapp:" not in joined
    assert not re.search(r"\d{7,}", joined)
