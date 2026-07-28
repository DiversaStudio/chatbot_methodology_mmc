from pathlib import Path
import pandas as pd
import pytest
from sami import qa, load

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
    p = tmp_path / "bad.xlsx"
    pd.DataFrame({"Foo": [1]}).to_excel(p, index=False)
    with pytest.raises(ValueError, match="critical"):
        qa.validate_schema(p, kind="responses")


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
