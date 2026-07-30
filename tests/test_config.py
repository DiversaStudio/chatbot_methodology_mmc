from pathlib import Path

import pytest

from sami import config, datasets


def test_paths_resolve_inside_the_datasets_dir():
    """The resolvers return a Path under datasets/<role>/, or None when the
    recipient has not dropped a file in yet. Deliberately asserts no filename:
    the whole point of the intake folder is that filenames may change."""
    assert config.DATASETS_DIR == datasets.DATASETS_DIR
    assert config.DATASETS_DIR.name == "datasets"
    for getter, role in ((config.responses_path, "responses"),
                         (config.meal_path, "meal")):
        path = getter()
        assert path is None or isinstance(path, Path)
        if path is not None:
            assert path.parent == datasets.folder(role)
            assert path.suffix.lower() == ".xlsx"


def test_header_row_default_is_unchanged():
    # qa.py's fixture-tolerant reader still uses this; the loaders detect it.
    assert config.DATA_HEADER_ROW == 2


def test_old_hardcoded_constants_are_gone():
    """RESPONSES_PATH/MEAL_PATH/DATA_DIR are removed, not deprecated -- a stale
    reference must fail loudly rather than read a file nobody expects."""
    for name in ("RESPONSES_PATH", "MEAL_PATH", "DATA_DIR"):
        assert not hasattr(config, name), f"config.{name} should be removed"


def test_get_salt_reads_env(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", "deadbeef")
    assert config.get_salt() == "deadbeef"


def test_get_salt_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SAMI_SALT", raising=False)
    monkeypatch.setattr(config, "_DOTENV", {}, raising=False)
    with pytest.raises(RuntimeError, match="SAMI_SALT"):
        config.get_salt()
