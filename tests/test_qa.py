import pandas as pd
import pytest
from sami import qa, load

SALT = "test_salt"


def test_pii_scan_flags_phone_and_whatsapp():
    bad = pd.DataFrame({"x": ["whatsapp:+573001188778", "hola"]})
    violations = qa.pii_scan(bad)
    assert len(violations) >= 1


def test_pii_scan_clean_on_loaded_frames():
    resp = load.load_responses(salt=SALT)
    assert qa.pii_scan(resp) == []


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
