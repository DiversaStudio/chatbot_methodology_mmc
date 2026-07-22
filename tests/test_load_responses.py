import re
import pandas as pd
from sami import load, config

SALT = "test_salt"


def test_pseudonymize_is_stable_and_salted():
    a = load.pseudonymize("whatsapp:+573001188778", SALT)
    assert re.fullmatch(r"[0-9a-f]{12}", a)
    assert a == load.pseudonymize("whatsapp:+573001188778", SALT)  # stable
    assert a != load.pseudonymize("whatsapp:+573001188778", "other_salt")  # salted


def test_load_responses_has_no_raw_identifiers():
    df = load.load_responses(salt=SALT)
    assert "Name" not in df.columns
    assert not any(c.lower() in {"phone", "digits"} for c in df.columns)
    # user_id is the intended pseudonymized hex hash: a 12-char hex string can
    # incidentally contain a run of 7+ digit characters by chance (hex digits
    # are 0-9a-f), which is not a PII leak. Exclude it from the raw-digit scan.
    scan_cols = [c for c in df.columns if c != "user_id"]
    joined = " ".join(df[scan_cols].astype(str).fillna("").values.ravel())
    assert "whatsapp:" not in joined
    assert not re.search(r"\d{7,}", joined)


def test_load_responses_counts():
    df = load.load_responses(salt=SALT)
    assert len(df) == 946                      # records (whatsapp rows)
    assert df["user_id"].nunique() == 917      # users; doc reference ~918
    assert (df["age_num"] < 18).sum() == 36    # P9 sub-18 count


def test_age_flag_marks_sub18():
    df = load.load_responses(salt=SALT)
    sub = df[df["age_num"] < 18]
    assert (sub["age_flag"] == "unreliable_sub18").all()
    assert (df[df["age_num"] >= 18]["age_flag"] == "ok").all()


def test_dominant_category_in_official_set():
    df = load.load_responses(salt=SALT)
    from sami.taxonomy import OFFICIAL_CATEGORIES
    allowed = set(OFFICIAL_CATEGORIES) | {"unclassified"}
    assert set(df["dominant_category"]).issubset(allowed)
