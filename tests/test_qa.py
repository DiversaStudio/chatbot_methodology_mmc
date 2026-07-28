from pathlib import Path
import pandas as pd
import pytest
from sami import qa, load, schema

SALT = "test_salt"
FIX = Path(__file__).resolve().parent / "fixtures"


def test_pii_scan_flags_phone_and_whatsapp():
    bad = pd.DataFrame({"x": ["whatsapp:+573001188778", "hola"]})
    violations = qa.pii_scan(bad)
    assert len(violations) >= 1


def test_pii_scan_clean_on_loaded_frames():
    resp = load.load_responses(salt=SALT)
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


def test_validate_schema_responses_ok():
    info = qa.validate_schema(load.config.RESPONSES_PATH, kind="responses")
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


def test_reconciliation_table():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    meal = load.load_meal(salt=SALT)
    table = qa.reconciliation_table(resp, msgs, meal)
    d = dict(zip(table["metric"], table["value"]))
    assert d["users"] == 917
    assert d["records"] == 946
    assert d["messages"] == 2991
    assert d["meal_responses"] == 69
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


def test_summary_prose_share_detects_the_v2_format():
    df = pd.DataFrame({"Chat_summary": [
        "#legal documentation",
        "humanitarian assistance",
        "[2026-07-24 14:15] El usuario preguntó sobre X, Y y Z.",
        None,
    ]})
    # 1 prose of 3 non-null
    assert abs(qa.summary_prose_share(df) - 1 / 3) < 1e-9


def test_summary_prose_share_is_zero_without_the_column():
    assert qa.summary_prose_share(pd.DataFrame({"a": [1]})) == 0.0


def test_summary_format_check_passes_below_threshold():
    df = pd.DataFrame({"Chat_summary": ["#employment"] * 99
                       + ["[2026-07-24 10:00] prosa"]})
    name, ok, _ = [c for c in _checks_for(df) if c[0] == "P9_summary_format"][0]
    assert ok is True


def test_summary_format_check_fails_above_threshold():
    df = pd.DataFrame({"Chat_summary": ["#employment"] * 5
                       + ["[2026-07-24 10:00] prosa"] * 5})
    name, ok, detail = [c for c in _checks_for(df) if c[0] == "P9_summary_format"][0]
    assert ok is False
    assert "50" in detail or "0.5" in detail


def _checks_for(responses):
    """run_checks needs three frames; build the minimal messages/meal shapes."""
    responses = responses.assign(
        user_id=[f"u{i}" for i in range(len(responses))],
        dominant_category="employment",
        n_questions=1)
    messages = pd.DataFrame({"user_id": responses["user_id"],
                             "n_msgs_user": 1, "message": "x"})
    meal = pd.DataFrame({"user_id": responses["user_id"]})
    return qa.run_checks(responses, messages, meal)
