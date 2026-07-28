import pytest
from sami import config


def test_paths_point_to_v2_export():
    # Task 12 repointed config.py at the v2 platform's export filenames. The
    # exact filename is one download's detail, not a contract the pipeline
    # depends on -- but config.py declaring *some* concrete default, inside
    # DATA_DIR, with the historical header-row offset, is worth locking in.
    assert config.RESPONSES_PATH.parent == config.DATA_DIR
    assert config.MEAL_PATH.parent == config.DATA_DIR
    assert config.RESPONSES_PATH.suffix == ".xlsx"
    assert config.MEAL_PATH.suffix == ".xlsx"
    assert config.DATA_HEADER_ROW == 2


def test_get_salt_reads_env(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", "deadbeef")
    assert config.get_salt() == "deadbeef"


def test_get_salt_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SAMI_SALT", raising=False)
    monkeypatch.setattr(config, "_DOTENV", {}, raising=False)
    with pytest.raises(RuntimeError, match="SAMI_SALT"):
        config.get_salt()
