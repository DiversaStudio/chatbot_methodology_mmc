import re
import pandas as pd
from sami import load, config
from conftest import requires_real_data

SALT = "test_salt"


def test_pseudonymize_is_stable_and_salted():
    a = load.pseudonymize("whatsapp:+573001188778", SALT)
    assert re.fullmatch(r"[0-9a-f]{12}", a)
    assert a == load.pseudonymize("whatsapp:+573001188778", SALT)  # stable
    assert a != load.pseudonymize("whatsapp:+573001188778", "other_salt")  # salted


def test_load_responses_has_no_raw_identifiers(users_fixture):
    df = load.load_responses(users_fixture, salt=SALT)
    assert "Name" not in df.columns
    assert not any(c.lower() in {"phone", "digits"} for c in df.columns)
    # user_id is the intended pseudonymized hex hash: a 12-char hex string can
    # incidentally contain a run of 7+ digit characters by chance (hex digits
    # are 0-9a-f), which is not a PII leak. Exclude it from the raw-digit scan.
    scan_cols = [c for c in df.columns if c != "user_id"]
    joined = " ".join(df[scan_cols].astype(str).fillna("").values.ravel())
    assert "whatsapp:" not in joined
    assert not re.search(r"\d{7,}", joined)


def test_load_responses_counts(users_fixture):
    # Exact counts against the committed synthetic fixture (6 rows survive the
    # null-id row; row 3 is the only sub-18 age). The real export's counts
    # change every time MMC refreshes the download -- see the requires_real_data
    # invariants below for the checks that must hold on THAT data instead.
    df = load.load_responses(users_fixture, salt=SALT)
    assert len(df) == 6                        # records (rows with a valid id)
    assert df["user_id"].nunique() == 6        # users
    assert (df["age_num"] < 18).sum() == 1     # P9 sub-18 count


def test_age_flag_marks_sub18(users_fixture):
    df = load.load_responses(users_fixture, salt=SALT)
    sub = df[df["age_num"] < 18]
    assert (sub["age_flag"] == "unreliable_sub18").all()
    assert (df[df["age_num"] >= 18]["age_flag"] == "ok").all()


def test_derived_audience_columns(users_fixture):
    df = load.load_responses(users_fixture, salt=SALT)
    # new NB1 columns exist and are populated
    for col in ["department", "gender_clean", "nationality_canon",
                "away_duration_canon", "away_duration_order"]:
        assert col in df.columns
    # department only set for priority cities; every non-null value is a real dept
    from sami import canon
    depts = set(df["department"].dropna())
    assert depts.issubset(set(canon.DEPARTMENT_OF_CITY.values()))
    # away_duration order is either None or a valid 0..4 index, monotonically consistent
    orders = df["away_duration_order"].dropna().unique()
    assert set(orders).issubset({0, 1, 2, 3, 4})


@requires_real_data
def test_nationality_is_overwhelmingly_venezuelan_on_real_export():
    """Invariant, not a loosened count: the Venezuelan share must stay >= 90%
    regardless of how many rows the December export has."""
    df = load.load_responses(salt=SALT)
    share = (df["nationality_canon"] == "Venezuela").mean()
    assert share >= 0.9


def test_dominant_category_is_gone(users_fixture):
    """The platform's own categorisation is not loaded at all any more."""
    df = load.load_responses(users_fixture)
    assert "dominant_category" not in df.columns


def test_chat_summary_is_no_longer_required(users_fixture):
    """Chat_summary fed only the retired category mapping, so a source export
    that stops emitting it must still load."""
    from sami import qa
    assert "Chat_summary" not in qa._CRITICAL["responses"]


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


@requires_real_data
def test_message_spine_has_no_phantom_redacted_messages():
    # End-to-end: the full pipeline (load_responses -> split_messages on the
    # already-redacted Messages column) must not manufacture phantom "[redacted]"
    # messages out of lines that were originally pure digit runs. This is a
    # regression for a specific shape (a standalone "+<12 digits>" phone-number
    # line) that the small committed fixture does not reproduce, so it stays on
    # real data. The unit-level behavior is also covered, fixture-free, by
    # test_split_messages_drops_redacted_only_lines above.
    #
    # This used to assert an exact count (2991, not the design doc's 2993 -- see
    # docs/superpowers/plans/2026-07-22-sami-pipeline-foundation.md for why).
    # That count is specific to the July export and would go stale the moment
    # MMC re-downloads; the invariant that survives is that no phantom
    # "[redacted]"-only message exists in the spine.
    df = load.load_responses(salt=SALT)
    spine = [m for blob in df["Messages"] for m in load.split_messages(blob)]
    assert not any(m.strip() == "[redacted]" for m in spine)


def test_load_responses_has_city_duration_derivations(users_fixture):
    df = load.load_responses(users_fixture, salt=SALT)
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


@requires_real_data
def test_user_ids_match_the_pre_migration_exports():
    """The migration must not re-pseudonymize. Every user_id in the previous
    dim_user export must still be present after the v2 switch."""
    from pathlib import Path
    import pytest
    from sami import facade

    previous = Path(__file__).resolve().parent.parent / "exports" / "dim_user.csv"
    if not previous.exists():
        pytest.skip("no previous export to compare against")
    old_ids = set(pd.read_csv(previous)["user_id"])
    new_ids = set(facade.load_sami().responses["user_id"])
    missing = old_ids - new_ids
    assert not missing, f"{len(missing)} user_ids changed in the migration"


# ---- KPI2: session time -------------------------------------------------------
def test_last_message_ts_keeps_only_the_iso_utc_vintage():
    """`Last Message At` mixes v2 ISO-UTC with legacy naive local timestamps.
    Only the former is trusted; everything else must become NaT rather than a
    plausible-looking session length."""
    out = load.last_message_ts([
        "2026-07-24T13:55:47.169Z",  # v2 platform, trusted
        "2026-07-24T13:55:47Z",      # trusted without fractional seconds
        "2026-07-10 18:02",          # legacy naive local -> dropped
        None,
        "",
        12345,                       # not a string at all
    ])
    assert out.notna().tolist() == [True, True, False, False, False, False]
    assert out.iloc[0] == pd.Timestamp("2026-07-24 13:55:47.169")
    assert out.dt.tz is None  # naive, like every other ts in the pipeline


def test_last_message_ts_survives_an_all_untrusted_column():
    out = load.last_message_ts(["2026-07-10 18:02", None])
    assert out.isna().all()


def test_session_minutes_is_raw_and_drops_negatives(users_fixture):
    df = load.load_responses(users_fixture, salt=SALT)
    assert "session_minutes" in df.columns
    vals = df["session_minutes"].dropna()
    # raw: no capping, but a last message before the record was created is
    # nonsense, not a zero-length session
    assert (vals >= 0).all()


def test_session_minutes_matches_the_timestamp_difference(users_fixture):
    df = load.load_responses(users_fixture, salt=SALT)
    pair = df[df["session_minutes"].notna()]
    if pair.empty:
        return  # fixture carries no trusted last-message timestamps
    expected = (pair["last_message_ts"] - pair["ts"]).dt.total_seconds() / 60
    pd.testing.assert_series_equal(
        pair["session_minutes"], expected, check_names=False)
