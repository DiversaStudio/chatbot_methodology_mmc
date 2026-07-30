"""Role-to-file resolution for the datasets/ intake folder.

These tests never touch the real datasets/ folder -- each one points
datasets.DATASETS_DIR at a tmp_path, so they pass on a machine with no data.
"""
import os
import time
from pathlib import Path

import pytest

from sami import datasets


@pytest.fixture
def fake_datasets(tmp_path, monkeypatch):
    """Redirect DATASETS_DIR at a tmp dir with both role folders created."""
    for role in datasets.ROLES:
        (tmp_path / role).mkdir(parents=True)
    monkeypatch.setattr(datasets, "DATASETS_DIR", tmp_path)
    return tmp_path


def _touch(path: Path, mtime: float | None = None) -> Path:
    path.write_bytes(b"not really xlsx")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_roles_are_responses_and_meal():
    assert datasets.ROLES == ("responses", "meal")


def test_empty_folder_resolves_to_none(fake_datasets):
    assert datasets.resolve("responses") is None


def test_missing_folder_resolves_to_none(tmp_path, monkeypatch):
    monkeypatch.setattr(datasets, "DATASETS_DIR", tmp_path / "nope")
    assert datasets.resolve("responses") is None


def test_single_file_is_resolved(fake_datasets):
    f = _touch(fake_datasets / "responses" / "Whatever They Called It.xlsx")
    assert datasets.resolve("responses") == f


def test_newest_file_wins(fake_datasets):
    old = _touch(fake_datasets / "responses" / "old.xlsx", mtime=time.time() - 9000)
    new = _touch(fake_datasets / "responses" / "new.xlsx", mtime=time.time())
    assert datasets.resolve("responses") == new
    assert datasets.candidates("responses") == [new, old]


def test_excel_lock_files_are_ignored(fake_datasets):
    real = _touch(fake_datasets / "responses" / "export.xlsx",
                  mtime=time.time() - 9000)
    _touch(fake_datasets / "responses" / "~$export.xlsx", mtime=time.time())
    assert datasets.resolve("responses") == real


def test_non_xlsx_files_are_ignored(fake_datasets):
    real = _touch(fake_datasets / "responses" / "export.xlsx",
                  mtime=time.time() - 9000)
    _touch(fake_datasets / "responses" / "notes.csv", mtime=time.time())
    _touch(fake_datasets / "responses" / "README.md", mtime=time.time())
    assert datasets.resolve("responses") == real


def test_uppercase_extension_is_accepted(fake_datasets):
    f = _touch(fake_datasets / "meal" / "EXPORT.XLSX")
    assert datasets.resolve("meal") == f


def test_roles_are_independent(fake_datasets):
    r = _touch(fake_datasets / "responses" / "r.xlsx")
    m = _touch(fake_datasets / "meal" / "m.xlsx")
    assert datasets.resolve("responses") == r
    assert datasets.resolve("meal") == m


def test_unknown_role_raises(fake_datasets):
    with pytest.raises(datasets.DatasetError) as exc:
        datasets.folder("nonsense")
    assert "nonsense" in str(exc.value)
    assert "responses" in str(exc.value)


def test_require_raises_with_folder_and_fix(fake_datasets):
    with pytest.raises(datasets.DatasetError) as exc:
        datasets.require("meal")
    msg = str(exc.value)
    # Message must contain the resolved directory (tmp_path for this test)
    assert str(datasets.folder("meal")).replace("\\", "/") in msg.replace("\\", "/")
    assert "fix:" in msg
    assert "datasets/meal/" in msg


def test_require_returns_path_when_present(fake_datasets):
    f = _touch(fake_datasets / "meal" / "m.xlsx")
    assert datasets.require("meal") == f


def test_dataset_error_is_a_schema_error():
    from sami import schema
    assert issubclass(datasets.DatasetError, schema.SchemaError)


def test_describe_names_the_file_and_counts_alternatives(fake_datasets):
    _touch(fake_datasets / "responses" / "old.xlsx", mtime=time.time() - 9000)
    _touch(fake_datasets / "responses" / "new.xlsx", mtime=time.time())
    line = datasets.describe("responses")
    assert "new.xlsx" in line
    assert "1 older file ignored" in line


def test_describe_when_single_file_mentions_no_alternatives(fake_datasets):
    _touch(fake_datasets / "responses" / "only.xlsx")
    line = datasets.describe("responses")
    assert "only.xlsx" in line
    assert "ignored" not in line


def test_describe_when_empty_says_so(fake_datasets):
    assert "no .xlsx" in datasets.describe("responses")


def test_missing_message_contains_resolved_directory(fake_datasets):
    """Regression: message must report the resolved DATASETS_DIR, not a hardcoded literal.

    When Task 2 makes config.py depend on datasets.py and overrides DATASETS_DIR,
    the error message must show the actual directory on the user's disk, not a
    hardcoded "datasets/role" that could be misleading.
    """
    with pytest.raises(datasets.DatasetError) as exc:
        datasets.require("responses")
    msg = str(exc.value)
    # The message must contain the actual resolved tmp_path
    resolved_dir = str(datasets.folder("responses")).replace("\\", "/")
    assert resolved_dir in msg.replace("\\", "/"), \
        f"Message must contain resolved directory {resolved_dir}, but got: {msg}"


def test_facade_raises_dataset_error_when_folder_is_empty(fake_datasets,
                                                          monkeypatch):
    """load_sami with nothing dropped in fails with the fix, not a KeyError."""
    from sami import facade
    monkeypatch.setenv("SAMI_SALT", "test-salt")
    with pytest.raises(datasets.DatasetError) as exc:
        facade.load_sami()
    assert "fix:" in str(exc.value)


def test_explicit_path_wins_over_folder_contents(fake_datasets, monkeypatch,
                                                 users_fixture):
    """An explicit --responses path is used even when the folder has a file."""
    from sami import load
    _touch(fake_datasets / "responses" / "should_not_be_read.xlsx")
    monkeypatch.setenv("SAMI_SALT", "test-salt")
    frame = load.load_responses(users_fixture, salt="test-salt")
    assert len(frame) > 0
