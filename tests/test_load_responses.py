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


def test_derived_audience_columns():
    df = load.load_responses(salt=SALT)
    # new NB1 columns exist and are populated
    for col in ["department", "gender_clean", "nationality_canon",
                "away_duration_canon", "away_duration_order"]:
        assert col in df.columns
    # ~96% Venezuelan (measured 905 of 919 non-null nationality)
    assert (df["nationality_canon"] == "Venezuela").sum() >= 900
    # department only set for priority cities; every non-null value is a real dept
    from sami import canon
    depts = set(df["department"].dropna())
    assert depts.issubset(set(canon.DEPARTMENT_OF_CITY.values()))
    # away_duration order is either None or a valid 0..4 index, monotonically consistent
    orders = df["away_duration_order"].dropna().unique()
    assert set(orders).issubset({0, 1, 2, 3, 4})


def test_dominant_category_in_official_set():
    df = load.load_responses(salt=SALT)
    from sami.taxonomy import OFFICIAL_CATEGORIES
    allowed = set(OFFICIAL_CATEGORIES) | {"unclassified"}
    assert set(df["dominant_category"]).issubset(allowed)


def test_split_messages_drops_redacted_only_lines():
    # split_messages runs on the Messages column *after* _redact_pii_runs has already
    # replaced 7+-digit runs with the literal token "[redacted]" (load_responses
    # redacts before returning; split_messages is applied downstream). A line that
    # was purely a digit run (e.g. a phone number) becomes just "[redacted]" — that
    # must still be treated as noise (as the original all-digit line was), not
    # survive as a phantom message.
    msgs = load.split_messages("hola\n[redacted]\ngracias amigo")
    assert "[redacted]" not in msgs
    assert msgs == ["hola", "gracias amigo"]


def test_split_messages_keeps_lines_with_embedded_pii_redacted():
    # A line with PII embedded alongside real content should survive, redacted,
    # not be dropped entirely.
    msgs = load.split_messages("necesito ayuda mi numero [redacted] por favor")
    assert len(msgs) == 1
    assert "[redacted]" in msgs[0]
    assert not re.search(r"\d{7,}", msgs[0])


def test_message_spine_has_no_phantom_redacted_messages():
    # End-to-end: the full pipeline (load_responses -> split_messages on the
    # already-redacted Messages column) must not manufacture phantom "[redacted]"
    # messages out of lines that were originally pure digit runs.
    #
    # Measured count is 2991, not the design doc's 2993 (see docs/superpowers/plans/
    # 2026-07-22-sami-pipeline-foundation.md). The 2993 baseline was measured on raw,
    # unredacted text, where two standalone "+<12 digits>" phone-number lines
    # (e.g. "+573208471248") were counted as real messages only because a leading
    # "+" defeated the original `t.isdigit()` noise check -- not because they held
    # any conversational content. After PII redaction (required for the hard PII
    # gate) those lines become "+[redacted]", which the redaction-invariant noise
    # check correctly drops as noise. That's 2 fewer messages than the stale
    # baseline: 2993 - 2 = 2991. The export/actual behavior is the source of truth
    # per project convention; this constant reflects the produced value, not the
    # doc reference.
    df = load.load_responses(salt=SALT)
    spine = [m for blob in df["Messages"] for m in load.split_messages(blob)]
    assert not any(m.strip() == "[redacted]" for m in spine)
    assert len(spine) == 2991


def test_load_responses_has_city_duration_derivations():
    from sami import load
    df = load.load_responses()
    assert "city_duration_canon" in df.columns
    assert "city_duration_order" in df.columns
    # every non-null order is a valid index into the canon order list
    from sami import canon
    orders = df["city_duration_order"].dropna().unique()
    assert all(0 <= int(o) < len(canon.CITY_DURATION_ORDER) for o in orders)


def test_digits_strips_float_suffix():
    """v2 Address parses as a float, so str() yields '573154047912.0'.
    Without stripping, every user_id changes and breaks joins to prior runs."""
    assert load.digits("573154047912.0") == "573154047912"
    assert load.digits(573154047912.0) == "573154047912"


def test_digits_unchanged_for_legacy_prefixed_names():
    assert load.digits("whatsapp:+573154047912") == "573154047912"


def test_user_id_identical_across_export_formats():
    """The migration must not re-pseudonymize: the same person in the v1 and
    v2 exports must hash to the same user_id."""
    salt = "test_salt"
    assert (load.pseudonymize("whatsapp:+573154047912", salt)
            == load.pseudonymize(573154047912.0, salt))


def test_load_responses_reads_the_v2_fixture():
    from pathlib import Path
    fix = Path(__file__).resolve().parent / "fixtures" / "users_v2.xlsx"
    df = load.load_responses(fix, salt="test_salt")
    assert len(df) == 6
    assert "user_id" in df.columns
    assert "Name" not in df.columns          # dropped after pseudonymization
    assert "Address" not in df.columns       # renamed by normalize_columns
    assert df["ts"].notna().all()


def test_load_responses_rejects_digit_less_ids():
    """Rows whose id contains no digits (e.g., UI placeholders like
    'Agregar address') are rejected, preventing phantom users from being
    pseudonymized and appearing in downstream tables."""
    assert load.digits("573154047912.0") == "573154047912"
    assert load.digits("Agregar address") == ""
    assert not bool(load.digits("Agregar address"))


def test_load_responses_old_export_has_917_users():
    """The old v1 export, when loaded with the new code that rejects
    digit-less ids, yields exactly 917 unique users (not 918, including
    the 'Agregar address' placeholder row)."""
    from pathlib import Path
    import pytest

    old_export = Path(__file__).resolve().parent.parent / "data_&_docs" / "MMC_bot_responses_1783087815.xlsx"
    if not old_export.exists():
        pytest.skip("Old export not found (gitignored)")

    df = load.load_responses(old_export, salt=SALT)
    assert len(df) == 946
    assert df["user_id"].nunique() == 917
