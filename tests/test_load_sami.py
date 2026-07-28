import pandas as pd
from sami import load_sami, SamiData
from sami import qa
from conftest import requires_real_data

SALT = "test_salt"  # facade reads config.get_salt(); ensure .env or env has SAMI_SALT

# load_sami() runs the full facade (schema validation, the P1/P6/P9 critical QA
# gate) against config.RESPONSES_PATH / config.MEAL_PATH -- there is no override
# here to point it at the small committed fixture, and the fixture's deliberately
# mixed summary formats would trip the P9 critical check anyway. So every test in
# this module needs the real, gitignored export and is marked accordingly; counts
# are checked as invariants, never exact numbers, so they survive MMC's future
# refreshes.


@requires_real_data
def test_load_sami_returns_populated_bundle(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    assert isinstance(d, SamiData)
    assert len(d.responses) > 0
    assert d.responses["user_id"].nunique() > 0
    assert len(d.messages) > 0
    assert d.meal["user_id"].is_unique
    assert not d.reconciliation.empty
    assert d.run_meta["salt_present"] is True
    # reconciliation figures must match their sources, whatever the export size
    recon = d.reconciliation.set_index("metric")["value"].to_dict()
    assert recon["users"] == d.responses["user_id"].nunique()
    assert recon["records"] == len(d.responses)
    assert recon["messages"] == len(d.messages)
    assert recon["users_with_text"] <= recon["users"]


@requires_real_data
def test_load_sami_is_pii_free(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    assert qa.pii_scan(d.responses) == []
    assert qa.pii_scan(d.messages) == []
    assert qa.pii_scan(d.meal) == []


@requires_real_data
def test_load_sami_is_deterministic(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    a = load_sami()
    b = load_sami()
    pd.testing.assert_frame_equal(a.responses, b.responses)
    pd.testing.assert_frame_equal(a.messages, b.messages)
    pd.testing.assert_frame_equal(a.meal, b.meal)


@requires_real_data
def test_load_sami_frozen(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.responses = None
