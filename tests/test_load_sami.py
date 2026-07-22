import pandas as pd
from sami import load_sami, SamiData
from sami import qa

SALT = "test_salt"  # facade reads config.get_salt(); ensure .env or env has SAMI_SALT


def test_load_sami_returns_populated_bundle(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    assert isinstance(d, SamiData)
    assert len(d.responses) == 946
    assert d.responses["user_id"].nunique() == 917
    assert len(d.messages) == 2991
    assert d.meal["user_id"].is_unique
    assert not d.reconciliation.empty
    assert d.run_meta["salt_present"] is True


def test_load_sami_is_pii_free(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    assert qa.pii_scan(d.responses) == []
    assert qa.pii_scan(d.messages) == []
    assert qa.pii_scan(d.meal) == []


def test_load_sami_is_deterministic(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    a = load_sami()
    b = load_sami()
    pd.testing.assert_frame_equal(a.responses, b.responses)
    pd.testing.assert_frame_equal(a.messages, b.messages)
    pd.testing.assert_frame_equal(a.meal, b.meal)


def test_load_sami_frozen(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.responses = None
