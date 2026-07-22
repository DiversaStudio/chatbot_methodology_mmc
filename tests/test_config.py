import pytest
from sami import config


def test_paths_point_to_july_export():
    assert config.RESPONSES_PATH.name == "MMC_bot_responses_1783087815.xlsx"
    assert config.MEAL_PATH.name == "MMC_MEAL_1783087939.xlsx"
    assert config.DATA_HEADER_ROW == 2


def test_get_salt_reads_env(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", "deadbeef")
    assert config.get_salt() == "deadbeef"


def test_get_salt_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SAMI_SALT", raising=False)
    monkeypatch.setattr(config, "_DOTENV", {}, raising=False)
    with pytest.raises(RuntimeError, match="SAMI_SALT"):
        config.get_salt()
