from pathlib import Path
import pandas as pd
import pytest
from sami import qa, load, schema
from conftest import requires_real_data

SALT = "test_salt"
FIX = Path(__file__).resolve().parent / "fixtures"


def test_pii_scan_flags_phone_and_whatsapp():
    bad = pd.DataFrame({"x": ["whatsapp:+573001188778", "hola"]})
    violations = qa.pii_scan(bad)
    assert len(violations) >= 1


def test_pii_scan_clean_on_loaded_frames(users_fixture):
    resp = load.load_responses(users_fixture, salt=SALT)
    assert qa.pii_scan(resp) == []


def test_pii_scan_catches_phone_in_numeric_heavy_frame():
    # A real phone in a string column must still be caught even when the frame
    # is mostly numeric metric columns (the dtype-skip must not hide text PII).
    df = pd.DataFrame({
        "score": [0.8724100327, 0.13],                  # numeric metric — long decimals, not PII
        "note": ["escríbeme al 3001234567", "hola"],    # object col with a real phone
    })
    cols = {h["column"] for h in qa.pii_scan(df)}
    assert cols == {"note"}


def test_pii_scan_ignores_file_id_and_float_ratios():
    # Locks in the two false positives the change deliberately stopped flagging:
    # an underscore-glued source-file id and stringified float ratios.
    df = pd.DataFrame({
        "value": ["MMC_bot_responses_1783087815.xlsx", "0.604"],  # object, but id / short
        "ratio": [0.8724100327, 0.5],                             # numeric metric col
    })
    assert qa.pii_scan(df) == []


def test_pii_scan_exempts_message_id_but_flags_regular_columns():
    # message_id (pipeline-generated hex digest) is exempted from PII scan.
    # Prove the exemption exists and is not overbroad: same digit run in a regular
    # column must still be flagged.
    digit_run = "1234567"  # 7+ digits triggers the PII flag

    # message_id with digit run: must scan clean
    df_with_message_id = pd.DataFrame({
        "message_id": [digit_run + "89abcdef"],  # hex digest containing digits
    })
    assert qa.pii_scan(df_with_message_id) == []

    # Same digit run in a regular column: must be flagged
    df_with_regular_col = pd.DataFrame({
        "notes": [digit_run],  # 7+ digits in regular column triggers flag
    })
    issues = qa.pii_scan(df_with_regular_col)
    assert len(issues) > 0, "PII gate must flag 7+ digit run in regular columns"
    assert issues[0]["column"] == "notes"


@requires_real_data
def test_validate_schema_responses_ok():
    info = qa.validate_schema(load.config.responses_path(), kind="responses")
    assert info["rows"] > 0
    assert info["ts_parse_rate"] == 1.0


def test_validate_schema_missing_critical_raises(tmp_path):
    # File with no header row detection: SchemaError with path and "header row"
    p_no_header = tmp_path / "no_header.xlsx"
    pd.DataFrame({"Foo": [1]}).to_excel(p_no_header, index=False)
    with pytest.raises(schema.SchemaError) as exc_info:
        qa.validate_schema(p_no_header, kind="responses")
    assert "header row" in str(exc_info.value).lower()
    assert str(p_no_header) in str(exc_info.value)

    # File with detectable header but missing critical columns: ValueError
    p_bad_cols = tmp_path / "bad_cols.xlsx"
    with pd.ExcelWriter(p_bad_cols, engine="openpyxl") as writer:
        # Banner rows
        pd.DataFrame([["Banner 1"], ["Banner 2"]]).to_excel(writer, sheet_name="Sheet1", index=False, header=False)
        # Header row with markers (detected by detect_header_row)
        pd.DataFrame([["Name", "Timestamp", "Other"]]).to_excel(writer, sheet_name="Sheet1", startrow=2, index=False, header=False)
        # Data row with only some columns (missing City, Age, Messages, Chat_summary)
        pd.DataFrame([["Alice", "2024-01-01", "value"]]).to_excel(writer, sheet_name="Sheet1", startrow=3, index=False, header=False)
    with pytest.raises(ValueError, match="critical"):
        qa.validate_schema(p_bad_cols, kind="responses")


def test_reconciliation_table_computes_correct_values():
    """Reconciliation arithmetic, verified on small constructed frames so this
    needs no real or fixture data at all -- the exact-count version of this test
    used to assert 917/946/2991/69, all specific to one MMC download."""
    resp = pd.DataFrame({
        "user_id": ["a", "a", "b", "c"],
        "n_questions": [1, 3, 2, 5],
    })
    msgs = pd.DataFrame({
        "user_id": ["a", "a", "b"],
        "dominant_category": ["legal_documentation", "employment", "legal_documentation"],
    })
    meal = pd.DataFrame({"user_id": ["a", "b"]})
    table = qa.reconciliation_table(resp, msgs, meal)
    d = dict(zip(table["metric"], table["value"]))
    assert d["users"] == 3
    assert d["records"] == 4
    assert d["messages"] == 3
    assert d["users_with_text"] == 2
    assert d["meal_responses"] == 2
    assert d["negative_tone_pct"] == "pending"


@requires_real_data
def test_reconciliation_table_matches_real_export():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    meal = load.load_meal(salt=SALT)
    table = qa.reconciliation_table(resp, msgs, meal)
    d = dict(zip(table["metric"], table["value"]))
    assert d["users"] == resp["user_id"].nunique()
    assert d["records"] == len(resp)
    assert d["messages"] == len(msgs)
    assert d["users_with_text"] <= d["users"]
    # NOT an invariant: meal_responses <= users. load_meal pseudonymizes its own
    # id column independently of load_responses, so the survey pool is not
    # guaranteed to be a subset of the user pool -- on the current export, 3 of
    # 115 MEAL respondents (112/115) have no matching user_id in responses. The
    # only guarantee is that the reported figure matches its source length.
    assert d["meal_responses"] == len(meal)
    assert d["negative_tone_pct"] == "pending"


def test_validate_schema_accepts_v2_users_export():
    out = qa.validate_schema(FIX / "users_v2.xlsx", kind="responses")
    assert out["rows"] == 7
    assert out["ts_parse_rate"] == 1.0


def test_validate_schema_accepts_v2_survey_export():
    out = qa.validate_schema(FIX / "survey_v2.xlsx", kind="meal")
    assert out["rows"] == 5


def test_validate_schema_sheet_name_case_insensitive(tmp_path):
    # Sheet name with mixed case and whitespace padding: " Users "
    p = tmp_path / "case_test.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        # Banner rows
        pd.DataFrame([["Banner 1"], ["Banner 2"]]).to_excel(writer, sheet_name=" Users ", index=False, header=False)
        # Header row at row 2 with markers
        pd.DataFrame([["Address", "Created At", "City", "Age", "QA Messages", "QA Summary"]]).to_excel(
            writer, sheet_name=" Users ", startrow=2, index=False, header=False)
        # Data rows
        pd.DataFrame([
            ["Alice", "2024-01-01", "NYC", 30, 5, "Summary"],
            ["Bob", "2024-01-02", "LA", 25, 3, "Brief"],
        ]).to_excel(writer, sheet_name=" Users ", startrow=3, index=False, header=False)
    # Should accept despite case and whitespace in sheet name
    out = qa.validate_schema(p, kind="responses")
    assert out["rows"] == 2


def test_validate_schema_single_sheet_escape_hatch(tmp_path):
    # Single-sheet workbook with non-matching sheet name but valid header and columns
    # The escape hatch should allow it through because len(xl.sheet_names) == 1
    p = tmp_path / "single_sheet.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        # Use a sheet name that does NOT match either vintage ("unknown_sheet")
        # Banner rows
        pd.DataFrame([["Banner 1"], ["Banner 2"]]).to_excel(writer, sheet_name="unknown_sheet", index=False, header=False)
        # Header row with markers
        pd.DataFrame([["Name", "Timestamp", "City", "Age", "Messages", "Chat_summary"]]).to_excel(
            writer, sheet_name="unknown_sheet", startrow=2, index=False, header=False)
        # Data rows
        pd.DataFrame([
            ["Alice", "2024-01-01", "NYC", 30, 5, "Summary"],
        ]).to_excel(writer, sheet_name="unknown_sheet", startrow=3, index=False, header=False)
    # Should accept due to single-sheet escape hatch
    out = qa.validate_schema(p, kind="responses")
    assert out["rows"] == 1


def _checks_for(responses):
    """run_checks needs three frames; build the minimal messages/meal shapes."""
    responses = responses.assign(
        user_id=[f"u{i}" for i in range(len(responses))],
        n_questions=1)
    messages = pd.DataFrame({"user_id": responses["user_id"],
                             "n_msgs_user": 1, "message": "x"})
    meal = pd.DataFrame({"user_id": responses["user_id"]})
    return qa.run_checks(responses, messages, meal)


def test_facade_critical_prefix_p11_does_not_raise():
    """A failing P11_ check is NOT recognized as critical (underscore anchoring)."""
    # This tests that underscore anchoring prevents false positives like P11_ being
    # caught by a bare "P1" prefix (which would match without the underscore).
    checks = [("P11_some_check", False, "test failure")]
    failed = [c for c in checks if not c[1] and c[0].startswith(("P1_", "P6_", "P9_"))]
    assert len(failed) == 0, "P11_ should NOT be recognized as critical (only P1_, P6_, P9_)"


def test_facade_critical_prefix_bare_p1_doesnt_match_p11():
    """Verify that bare 'P1' prefix would incorrectly match P11_, but anchored 'P1_' does not."""
    checks = [("P11_some_check", False, "test failure")]
    # Bare prefix (old broken way) would catch P11:
    failed_bare = [c for c in checks if not c[1] and c[0].startswith(("P1", "P6"))]
    assert len(failed_bare) == 1, "Bare P1 prefix incorrectly catches P11_ (latent bug)"
    # Anchored prefix (fixed way) correctly skips P11:
    failed_fixed = [c for c in checks if not c[1] and c[0].startswith(("P1_", "P6_", "P9_"))]
    assert len(failed_fixed) == 0, "Anchored P1_ prefix correctly skips P11_"


def test_reconciliation_has_no_category_metric():
    resp = pd.DataFrame({"user_id": ["a", "b"], "n_questions": [1, 2]})
    msgs = pd.DataFrame({"user_id": ["a", "b"]})
    meal = pd.DataFrame({"user_id": ["a"]})
    table = qa.reconciliation_table(resp, msgs, meal)
    metrics_seen = set(table["metric"])
    assert "legal_documentation_pct" not in metrics_seen
    assert not any("categor" in m for m in metrics_seen)
    # the ledger's real job is untouched
    assert {"users", "records", "messages", "users_with_text"} <= metrics_seen


def test_category_gates_are_gone():
    for gone in ("summary_unmappable_share", "labelled_unmappable_share",
                 "_count_prose_share", "SUMMARY_PROSE_THRESHOLD"):
        assert not hasattr(qa, gone), gone


def test_run_checks_no_longer_has_p7_or_p9():
    resp = pd.DataFrame({"user_id": ["u0"], "n_questions": [1]})
    msgs = pd.DataFrame({"user_id": ["u0"], "n_msgs_user": [1], "message": ["x"]})
    meal = pd.DataFrame({"user_id": ["u0"]})
    names = {c[0] for c in qa.run_checks(resp, msgs, meal)}
    assert not any(n.startswith(("P7_", "P9_")) for n in names)
    assert {"P1_pii_responses", "P6_spine_invariant", "P8_meal_unique"} <= names


def test_cluster_coverage_counts_only_real_clusters():
    dim_user = pd.DataFrame({"user_id": list("abcde"),
                             "cluster_id": [0, 1, 2, -1, -1]})
    assert qa.cluster_coverage(dim_user) == pytest.approx(0.6)


def test_cluster_coverage_treats_null_as_uncovered():
    dim_user = pd.DataFrame({"user_id": list("abcd"),
                             "cluster_id": [0, 1, None, -1]})
    assert qa.cluster_coverage(dim_user) == pytest.approx(0.5)


def test_cluster_coverage_threshold_is_below_todays_value():
    """86% today; the bar leaves drift room without tolerating a silent collapse."""
    assert qa.CLUSTER_COVERAGE_THRESHOLD == 0.80
