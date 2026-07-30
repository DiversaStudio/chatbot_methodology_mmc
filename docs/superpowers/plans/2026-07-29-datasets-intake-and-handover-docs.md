# Datasets Intake + Handover Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let MMC drop a newly-named platform export into `datasets/<role>/` and re-run the pipeline with no code edits, and rewrite the documentation so they can install, run, and re-point Power BI without asking the author anything.

**Architecture:** A new `src/sami/datasets.py` resolves a *role* (`responses`, `meal`) to a file by globbing `datasets/<role>/*.xlsx` and taking the newest by modification time. The two hardcoded path constants in `config.py` become functions delegating to it. Everything downstream — the schema contract, loaders, metrics, exports — is unchanged, because the pipeline is already tolerant of column and header drift; only *finding* the file was brittle.

**Tech Stack:** Python 3.11+, pandas, pytest, uv, git-filter-repo.

**Spec:** [docs/superpowers/specs/2026-07-29-datasets-intake-and-handover-docs-design.md](../specs/2026-07-29-datasets-intake-and-handover-docs-design.md)

## Global Constraints

- Python `>=3.11`. Run everything through the project venv: `.venv/Scripts/python.exe` (Windows) — never a bare `python`.
- Install and lock with `uv` only. Never `pip`, `venv`, or `pyenv` as standalone tools.
- Git commit messages carry **no** `Co-Authored-By` trailer.
- `data_&_docs/` is never renamed, moved, or deleted. It stays gitignored and physically untouched. Reading from it is allowed; writing to it is not.
- No raw `.xlsx` is ever committed. `datasets/**/*.xls*` must be gitignored before any data file is copied in.
- Documentation text must contain **no** mention of: sentiment/tone reliability, kappa (κ), the 0.7 quotability gate, "directional", "quotable", or the v1/v2 nationality-poolability rationale (that v1 screened out Colombians). The *code* enforcing these — `meta_run.tone_gate_passed`, `meta_run.sentiment_quotable`, `src/sami/cohort.py` — is unchanged. No documentation example, template, or Power BI measure may present a sentiment percentage.
- Documentation is declarative and describes current behaviour. No "TBD", no placeholders, no hedged or provisional wording, no questions addressed to the reader.
- The force-push of rewritten history is **not** executed by the implementer. Task 13 stops after local verification.

---

### Task 1: `datasets.py` — role-to-file resolution

**Files:**
- Create: `src/sami/datasets.py`
- Test: `tests/test_datasets.py`

**Interfaces:**
- Consumes: `schema.SchemaError` from `src/sami/schema.py`.
- Produces: `datasets.ROLES`, `datasets.DATASETS_DIR`, `datasets.DatasetError`, `datasets.folder(role) -> Path`, `datasets.candidates(role) -> list[Path]`, `datasets.resolve(role) -> Path | None`, `datasets.require(role) -> Path`, `datasets.missing_message(role) -> str`, `datasets.describe(role) -> str`. Tasks 2 and 3 depend on these exact names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_datasets.py`:

```python
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
    assert "datasets/meal" in msg.replace("\\", "/")
    assert "fix:" in msg


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_datasets.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'sami.datasets'`.

- [ ] **Step 3: Write the implementation**

Create `src/sami/datasets.py`:

```python
"""Resolve a dataset role to the file this run should read.

The recipient's action is "save the new export into datasets/<role>/". Role is
declared by the folder, not by the filename, and the newest file wins -- so a
re-export under any name runs without anyone editing code.

Modification time is used rather than a manifest or a filename convention
because it is a property of the act of saving the file: there is no second step
that can be silently skipped. Older files may be left in place as an archive,
and every run prints which file it used (see `describe`), so the choice is
auditable after the fact.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .schema import SchemaError

_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = _ROOT / "datasets"
ROLES = ("responses", "meal")

_LOCK_PREFIX = "~$"  # Excel writes these while a workbook is open
_SUFFIX = ".xlsx"


class DatasetError(SchemaError):
    """No usable file for a dataset role. The message carries the fix.

    Subclasses SchemaError so run_pipeline.py's existing handler prints the
    message instead of a traceback.
    """


def folder(role: str) -> Path:
    """The drop folder for `role`. Raises DatasetError on an unknown role."""
    if role not in ROLES:
        raise DatasetError(
            f"Unknown dataset role {role!r}.\n"
            f"  fix:  Use one of: {', '.join(ROLES)}.")
    return DATASETS_DIR / role


def candidates(role: str) -> list[Path]:
    """Usable .xlsx files in the role folder, newest modification first.

    Excel lock files (~$*) and every non-.xlsx entry are skipped. Name is the
    tie-break so the result is deterministic when two files share an mtime.
    """
    directory = folder(role)
    if not directory.is_dir():
        return []
    found = [
        p for p in directory.iterdir()
        if p.is_file()
        and p.suffix.lower() == _SUFFIX
        and not p.name.startswith(_LOCK_PREFIX)
    ]
    return sorted(found, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def resolve(role: str) -> Path | None:
    """The file to use for `role`, or None when the folder holds none.

    Returns None rather than raising so preflight can report a clean FAIL and
    so importing this module never depends on the folder's contents.
    """
    found = candidates(role)
    return found[0] if found else None


def require(role: str) -> Path:
    """Like `resolve`, but raises DatasetError with the fix when absent."""
    path = resolve(role)
    if path is None:
        raise DatasetError(missing_message(role))
    return path


def missing_message(role: str) -> str:
    """Why the role is unresolved and exactly what to do about it."""
    directory = folder(role)
    return (
        f"No .xlsx found for the {role!r} dataset.\n"
        f"  looked in: {directory}\n"
        f"  fix:  Save the {role} export into that folder. The filename does "
        f"not matter and the most recently modified .xlsx is used. "
        f"Alternatively pass an explicit path:\n"
        f"        python run_pipeline.py --{role} PATH.xlsx")


def describe(role: str) -> str:
    """One line naming the chosen file, its date, and what was passed over."""
    found = candidates(role)
    if not found:
        return f"no .xlsx in {folder(role)}"
    chosen = found[0]
    stamp = datetime.fromtimestamp(chosen.stat().st_mtime).strftime("%Y-%m-%d")
    line = f"{chosen} (modified {stamp}"
    others = len(found) - 1
    if others:
        line += f", {others} older file{'s' if others > 1 else ''} ignored"
    return line + ")"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_datasets.py -v`
Expected: all 16 PASS.

- [ ] **Step 5: Confirm no import cycle**

Run: `.venv/Scripts/python.exe -c "from sami import datasets, config, load, facade; print('ok')"`
Expected: prints `ok`. If it raises `ImportError: cannot import name`, `datasets.py` has created a cycle — it may import only from `.schema`.

- [ ] **Step 6: Commit**

```bash
git add src/sami/datasets.py tests/test_datasets.py
git commit -m "feat(sami): resolve dataset files by role folder, newest first"
```

---

### Task 2: Wire the resolver into config, loaders, preflight and the CLI

**Files:**
- Modify: `src/sami/config.py:6-14`
- Modify: `src/sami/facade.py:20-21`
- Modify: `src/sami/load.py:173`, `src/sami/load.py:238`
- Modify: `src/sami/preflight.py:51-58`, `src/sami/preflight.py:91-97`
- Modify: `run_pipeline.py:107-112`, `run_pipeline.py:127-128`
- Modify: `tests/conftest.py:18-20`
- Modify: `tests/test_config.py`
- Modify: `tests/test_export.py:16`, `tests/test_metrics.py:14`, `tests/test_validation.py:144`, `tests/test_load_meal.py:42-43`, `tests/test_qa.py:66`
- Test: `tests/test_config.py`, `tests/test_datasets.py` (extended)

**Interfaces:**
- Consumes: everything Task 1 produced.
- Produces: `config.DATASETS_DIR`, `config.responses_path() -> Path | None`, `config.meal_path() -> Path | None`. `config.RESPONSES_PATH`, `config.MEAL_PATH` and `config.DATA_DIR` cease to exist. `config.DATA_HEADER_ROW` is unchanged and still `2`.

- [ ] **Step 1: Write the failing tests**

Replace the body of `tests/test_config.py`'s path test. The old test asserted the hardcoded filenames — that is exactly what made the paths hard to change, so it is replaced with behaviour:

```python
from pathlib import Path

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
```

Append to `tests/test_datasets.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_datasets.py -v`
Expected: `test_paths_resolve_inside_the_datasets_dir` fails with `AttributeError: module 'sami.config' has no attribute 'DATASETS_DIR'`; `test_old_hardcoded_constants_are_gone` fails because the constants still exist.

- [ ] **Step 3: Rewrite the head of `config.py`**

Replace lines 6-14 of `src/sami/config.py`:

```python
from . import datasets

_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = datasets.DATASETS_DIR

# 0-indexed; the real header is the 3rd row of the export. Kept for qa.py's
# fixture-tolerant reader. The loaders do NOT rely on it -- they call
# schema.detect_header_row(), so a re-export with a different number of banner
# rows still loads.
DATA_HEADER_ROW = 2


def responses_path() -> Path | None:
    """The responses export to use, or None if datasets/responses/ is empty.

    A function, not a constant: resolution depends on folder contents, which
    can change between import and use, and an empty folder must not raise at
    import time.
    """
    return datasets.resolve("responses")


def meal_path() -> Path | None:
    """The MEAL export to use, or None if datasets/meal/ is empty."""
    return datasets.resolve("meal")
```

- [ ] **Step 4: Update `facade.py:20-21`**

```python
    responses_path = Path(responses_path) if responses_path else datasets.require("responses")
    meal_path = Path(meal_path) if meal_path else datasets.require("meal")
```

Add `datasets` to the `from . import config, load, qa` line and `from pathlib import Path` to the imports. The `Path(...)` coercion is load-bearing: `run_pipeline.py` passes `args.responses` as a **str**, and `run_meta` later calls `responses_path.name`, so `--responses PATH` raises `AttributeError` without it.

- [ ] **Step 5: Update `load.py:173` and `load.py:238`**

Line 173 (in `load_responses`):

```python
    path = Path(path) if path else datasets.require("responses")
```

Line 238 (in `load_meal`):

```python
    path = Path(path) if path else datasets.require("meal")
```

Add `datasets` to the `from . import config, canon, taxonomy, schema` line.

- [ ] **Step 6: Update `preflight.py`**

`Context` (lines 51-58) — the fields become optional, because an empty folder is a reportable FAIL rather than a crash:

```python
@dataclass
class Context:
    """What the run is about to do. Paths are the effective ones (CLI, or
    resolved from datasets/). None means nothing was dropped into the folder."""
    responses_path: Path | None = field(
        default_factory=lambda: datasets.resolve("responses"))
    meal_path: Path | None = field(
        default_factory=lambda: datasets.resolve("meal"))
    out_dir: Path = field(default_factory=lambda: Path("exports"))
    skip_nlp: bool = False
```

`_check_export` (lines 91-97) — handle `None`, and replace the `data_&_docs/` fix text:

```python
def _check_export(path: Path | None, source: str, required) -> Result:
    if path is None:
        return Result(source, FAIL, f"no .xlsx in {datasets.folder(source)}",
                      "\n        ".join(
                          datasets.missing_message(source).splitlines()[1:]))
    if not path.exists():
        return Result(source, FAIL, f"not found: {path}",
                      "Save the export into datasets/%s/ (the filename does "
                      "not matter; the newest .xlsx is used), or pass an "
                      "explicit path:\n"
                      "        python run_pipeline.py --%s PATH" % (source, source))
```

Add `datasets` to preflight's `from . import config, nlp, schema` import line.

- [ ] **Step 7: Update `run_pipeline.py`**

Lines 107-112:

```python
    ctx = preflight.Context(
        responses_path=Path(args.responses) if args.responses else datasets.resolve("responses"),
        meal_path=Path(args.meal) if args.meal else datasets.resolve("meal"),
        out_dir=Path(args.out),
        skip_nlp=args.skip_nlp,
    )
```

Lines 127-128 — state which files the run is actually reading, so an output is never ambiguous about its input:

```python
    with pr.stage("loading responses + MEAL"):
        for role, override in (("responses", args.responses), ("meal", args.meal)):
            chosen = override if override else datasets.describe(role)
            print(f"  {role + ':':<11}{chosen}", file=sys.stderr)
        SD = load_sami(responses_path=args.responses, meal_path=args.meal)
```

Add `datasets` to the `from sami import (...)` list.

Update the `--responses` / `--meal` argparse help so it names the default source:

```python
    ap.add_argument("--responses", default=None,
                    help="path to the responses .xlsx "
                         "(default: newest in datasets/responses/)")
    ap.add_argument("--meal", default=None,
                    help="path to the MEAL .xlsx "
                         "(default: newest in datasets/meal/)")
```

- [ ] **Step 8: Update the test guards**

`tests/conftest.py:18-20`:

```python
requires_real_data = pytest.mark.skipif(
    not (config.responses_path() and config.meal_path()),
    reason="real export not present (datasets/ holds no .xlsx)")
```

In `tests/test_export.py:16`, `tests/test_metrics.py:14`, `tests/test_validation.py:144`, replace
`if not (Path(config.RESPONSES_PATH).exists() and Path(config.MEAL_PATH).exists()):`
with
`if not (config.responses_path() and config.meal_path()):`.

In `tests/test_load_meal.py:42-43` and `tests/test_qa.py:66`, replace `config.MEAL_PATH` / `load.config.RESPONSES_PATH` with `config.meal_path()` / `config.responses_path()`.

- [ ] **Step 9: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass. Real-data tests skip until Task 6 populates `datasets/`; that is correct at this point.

- [ ] **Step 10: Confirm nothing still references the removed constants**

Run: `git grep -n "RESPONSES_PATH\|MEAL_PATH\|DATA_DIR\|data_&_docs" -- src tests run_pipeline.py`
Expected: no output. (Matches under `docs/superpowers/`, `notebooks/arxiv/` and `.superpowers/` are historical records and stay.)

- [ ] **Step 11: Commit**

```bash
git add src/sami/config.py src/sami/facade.py src/sami/load.py src/sami/preflight.py run_pipeline.py tests/
git commit -m "refactor(sami): resolve source exports from datasets/, drop hardcoded paths"
```

---

### Task 3: Scaffold the `datasets/` folder and its README

**Files:**
- Create: `datasets/responses/.gitkeep`, `datasets/meal/.gitkeep`, `datasets/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `datasets.ROLES` from Task 1.
- Produces: the tracked folder skeleton every later task and the recipient depend on.

- [ ] **Step 1: Update `.gitignore` FIRST**

Before any data file can exist locally. Append:

```gitignore
# Dataset intake: the folder structure and its docs are tracked, the data never
# is (the raw platform exports carry users' WhatsApp phone numbers).
datasets/**/*.xls
datasets/**/*.xlsx
datasets/**/*.xlsm
datasets/**/*.csv
!datasets/README.md
!datasets/**/.gitkeep
```

Remove the now-inaccurate comment above `data_&_docs/` and replace it:

```gitignore
# Author's local working folder: superseded by datasets/, never referenced by
# code or documentation, never version controlled.
data_&_docs/
```

- [ ] **Step 2: Verify the ignore rules actually work**

```bash
mkdir -p datasets/responses datasets/meal
touch datasets/responses/probe.xlsx
git check-ignore -v datasets/responses/probe.xlsx
rm datasets/responses/probe.xlsx
```

Expected: `check-ignore` prints the matching `.gitignore` line. If it prints nothing, the rule does not match and no data may be copied in until it does.

- [ ] **Step 3: Create the folder skeleton**

```bash
touch datasets/responses/.gitkeep datasets/meal/.gitkeep
```

- [ ] **Step 4: Write `datasets/README.md`**

`````markdown
# Datasets

Put the chatbot's data exports here. This is the only folder the pipeline reads
data from.

```text
datasets/
  responses/    <- the chatbot users / responses export
  meal/         <- the MEAL survey export
```

## Adding a new export

1. Save the responses export into `datasets/responses/`.
2. Save the MEAL survey export into `datasets/meal/`.
3. Verify the setup:

   ```powershell
   .venv/Scripts/python.exe run_pipeline.py --check
   ```

   It names the two files it will read and confirms every column it needs is
   present. It does no work, so it takes seconds.

4. Run the pipeline:

   ```powershell
   .venv/Scripts/python.exe run_pipeline.py
   ```

## What the folder guarantees

**The filename does not matter.** The folder declares what a file is, so the
platform can rename its exports freely.

**The newest file is used.** Within each folder the most recently modified
`.xlsx` is read. Older exports may be left in place as an archive; they are
ignored. Every run prints which file it used, so any output can be traced back
to its input:

```text
[1/9] loading responses + MEAL
  responses: datasets/responses/Users_Group_Title_1509.xlsx (modified 2026-09-15, 1 older file ignored)
  meal:      datasets/meal/Survey_1509.xlsx (modified 2026-09-15)
```

**Only `.xlsx` is read.** Other file types are ignored, as are the `~$...xlsx`
lock files Excel creates while a workbook is open. Close the workbook in Excel
before running.

**The data is never committed.** `.gitignore` excludes every spreadsheet in this
folder. The raw exports contain users' WhatsApp phone numbers and must not enter
version control.

## Using a file from somewhere else

To read a one-off file without putting it in the folder:

```powershell
.venv/Scripts/python.exe run_pipeline.py --responses PATH.xlsx --meal PATH.xlsx
```

An explicit path always takes precedence over the folder contents.

## Also required: `SAMI_SALT`

User identifiers are salted hashes, so the pipeline needs the salt that
produced the existing exports. Put it in a `.env` file at the repository root:

```text
SAMI_SALT=<the value provided out-of-band>
```

`.env` is gitignored. The salt is never committed. Using a different salt
produces different `user_id` values, and the new exports will not join against
the previous ones.

## What each export must contain

See [`docs/DATA_SOURCES.md`](../docs/DATA_SOURCES.md) for the required columns
of each file and what happens when one is missing.
`````

- [ ] **Step 5: Confirm the skeleton is tracked and the ignores hold**

Run: `git status --porcelain datasets/`
Expected: exactly three additions — `datasets/README.md`, `datasets/responses/.gitkeep`, `datasets/meal/.gitkeep`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore datasets/
git commit -m "feat(datasets): tracked intake folder for responses and MEAL exports"
```

---

### Task 4: Declare the three undeclared runtime dependencies

**Files:**
- Modify: `pyproject.toml` (`[project.dependencies]`)
- Modify: `requirements.txt`
- Modify: `uv.lock` (regenerated)
- Test: `tests/test_requirements.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by later tasks.

`scikit-learn`, `scipy` and `transformers` are imported directly by `run_pipeline.py`, `src/sami/clusters.py`, `src/sami/stats.py` and `src/sami/nlp.py`, but reach the environment only as transitive dependencies of `bertopic` / `sentence-transformers` / `umap-learn`. An upstream resolver change would break the install with no signal.

- [ ] **Step 1: Write the failing test**

Create `tests/test_requirements.py`:

```python
"""Every third-party package imported by src/ must be declared, not transitive."""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Import name -> distribution name, for the packages whose names differ.
DIRECTLY_IMPORTED = {
    "pandas": "pandas", "numpy": "numpy", "sklearn": "scikit-learn",
    "scipy": "scipy", "matplotlib": "matplotlib", "geopandas": "geopandas",
    "contextily": "contextily", "wordcloud": "wordcloud",
    "transformers": "transformers",
    "sentence_transformers": "sentence-transformers", "umap": "umap-learn",
}


def _declared() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = {re.split(r"[<>=!~ \[]", d)[0].lower()
             for d in data["project"]["dependencies"]}
    for group in data.get("dependency-groups", {}).values():
        names |= {re.split(r"[<>=!~ \[]", d)[0].lower() for d in group}
    return names


def test_every_directly_imported_package_is_declared():
    missing = sorted(dist for dist in DIRECTLY_IMPORTED.values()
                     if dist.lower() not in _declared())
    assert not missing, f"imported but not declared in pyproject.toml: {missing}"


def test_requirements_txt_mirrors_pyproject_runtime_deps():
    """requirements.txt is the pip path; it must not drift from pyproject."""
    txt = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    listed = {re.split(r"[<>=!~ @\[]", line)[0].strip().lower()
              for line in txt.splitlines()
              if line.strip() and not line.startswith("#")}
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {re.split(r"[<>=!~ \[]", d)[0].strip().lower()
                for d in data["project"]["dependencies"]}
    # torch is deliberately absent from requirements.txt (CPU/GPU choice).
    assert declared - listed == set(), f"in pyproject but not requirements.txt: {declared - listed}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_requirements.py -v`
Expected: `test_every_directly_imported_package_is_declared` FAILS listing `['scikit-learn', 'scipy', 'transformers']`.

- [ ] **Step 3: Add the three to `pyproject.toml`**

In `[project.dependencies]`, after `"numpy>=1.26",`:

```toml
    "scikit-learn>=1.5",
    "scipy>=1.13",
```

and after `"sentence-transformers>=5.6.0",`:

```toml
    "transformers>=5.0",
```

- [ ] **Step 4: Mirror them in `requirements.txt`**

After `numpy>=1.26`:

```text
scikit-learn>=1.5
scipy>=1.13
```

After `sentence-transformers>=5.6.0`:

```text
transformers>=5.0
```

- [ ] **Step 5: Verify the floors are satisfiable before locking**

Run: `.venv/Scripts/python.exe -c "import sklearn, scipy, transformers; print(sklearn.__version__, scipy.__version__, transformers.__version__)"`
Expected: three versions, each at or above the floor written in Step 3. If any installed version is *below* a floor, lower the floor to the installed version rather than forcing an upgrade — this task declares what is already in use, it does not upgrade anything.

- [ ] **Step 6: Re-lock and verify the environment still resolves**

```bash
uv lock
uv sync
```

Expected: `uv lock` reports the three added; `uv sync` makes no destructive change. If `uv sync` removes `src/`, `tool.uv.package = false` was lost — restore it before continuing.

- [ ] **Step 7: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, including both new requirement tests.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml requirements.txt uv.lock tests/test_requirements.py
git commit -m "build: declare scikit-learn, scipy and transformers as direct deps"
```

---

### Task 5: Track the Power BI report and custom visual

**Files:**
- Add to git: `mmc_dashboard.pbix`, `docs/WordCloud.1.2.9.pbiviz`
- Modify: `.gitignore` (only if a rule currently excludes them)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

- [ ] **Step 1: Confirm neither file is ignored and check the sizes**

```bash
git check-ignore -v mmc_dashboard.pbix docs/WordCloud.1.2.9.pbiviz
ls -l mmc_dashboard.pbix docs/WordCloud.1.2.9.pbiviz
```

Expected: `check-ignore` prints nothing (exit 1 — neither is ignored). Sizes ≈3.6 MB and ≈466 KB. If either exceeds 50 MB, stop and report before committing — that would change the LFS decision made in the spec.

- [ ] **Step 2: Confirm the `.pbix` is not currently open in Power BI Desktop**

A `.pbix` held open by the application can be committed mid-write. Close Power BI Desktop before staging.

- [ ] **Step 3: Commit both**

```bash
git add mmc_dashboard.pbix docs/WordCloud.1.2.9.pbiviz
git commit -m "chore(powerbi): track the report and the word cloud custom visual"
```

- [ ] **Step 4: Verify they are tracked**

Run: `git ls-files mmc_dashboard.pbix docs/WordCloud.1.2.9.pbiviz`
Expected: both paths listed.

---

### Task 6: End-to-end intake verification against the real exports

**Files:**
- No source changes. This task produces evidence, and a fix only if evidence contradicts the design.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: the confirmation that later documentation tasks describe real behaviour.

This is the task that proves filename independence. Do not skip it and do not substitute the fixtures — the fixtures cannot detect a resolution bug against real files.

- [ ] **Step 1: Copy the current exports into the intake folder**

Copy — never move. `data_&_docs/` must be left untouched.

```bash
cp "data_&_docs/Users_Group_Title_2807.xlsx" datasets/responses/
cp "data_&_docs/Survey_Responses_Group_Title_2807.xlsx" datasets/meal/
```

- [ ] **Step 2: Confirm git still ignores them**

Run: `git status --porcelain datasets/`
Expected: **no output**. If either `.xlsx` appears, stop immediately and fix `.gitignore` — a phone-number-bearing file is one `git add -A` away from history.

- [ ] **Step 3: Preflight**

Run: `.venv/Scripts/python.exe run_pipeline.py --check`
Expected: all ten checks OK or WARN (a CPU-only machine WARNs on `device`, which is fine). The `responses` and `meal` lines name the two copied files.

- [ ] **Step 4: Full run**

Run: `.venv/Scripts/python.exe run_pipeline.py`
Expected: exit 0; the load stage prints both resolved paths; `parity_check` all `True`.

- [ ] **Step 5: Diff against the committed exports**

Run: `git diff --stat exports/`
Expected: changes confined to `exports/meta_run.csv` (the `generated_at` timestamp, and the `responses_file` / `meal_file` names if they differ) and the `x`/`y` columns of `exports/nlp_umap.csv`. Any other table differing means the intake change altered results — stop and investigate before proceeding.

- [ ] **Step 6: Restore the exports and rename the inputs**

```bash
git checkout -- exports/
mv "datasets/responses/Users_Group_Title_2807.xlsx" "datasets/responses/renamed-by-the-platform-9999.xlsx"
mv "datasets/meal/Survey_Responses_Group_Title_2807.xlsx" "datasets/meal/totally different name.xlsx"
```

- [ ] **Step 7: Re-run with the renamed files**

Run: `.venv/Scripts/python.exe run_pipeline.py --skip-nlp`
Expected: exit 0. The load stage names the renamed files. `parity_check` all `True`. **This is the proof**: a re-export under any name runs with no code edit.

- [ ] **Step 8: Verify the empty-folder failure is legible**

```bash
mkdir -p ../_intake_holding
mv "datasets/meal/totally different name.xlsx" ../_intake_holding/
.venv/Scripts/python.exe run_pipeline.py --check
mv "../_intake_holding/totally different name.xlsx" datasets/meal/
```

Expected: `--check` exits 1 and the `meal` line reads `no .xlsx in ...datasets/meal` with the fix naming the folder. No traceback.

- [ ] **Step 9: Restore the exports and record the evidence**

```bash
git checkout -- exports/
git status --porcelain
```

Expected: clean apart from any legitimately-modified tracked file. `exports/` restored to its committed state; the pipeline is re-run for real in Task 12.

- [ ] **Step 10: Report**

Record for the coordinator: the two preflight outputs, the diff scope from Step 5, and the Step 7 exit code. If any expectation above was not met, do not proceed to the documentation tasks — they would document behaviour that does not exist.

---

### Task 7: `docs/DATA_SOURCES.md` — what each export must contain

**Files:**
- Create: `docs/DATA_SOURCES.md`
- Read for content: `src/sami/schema.py` (the whole file)

**Interfaces:**
- Consumes: verified behaviour from Task 6.
- Produces: a document `datasets/README.md` and `README.md` link to.

Every statement in this document must be read out of `src/sami/schema.py` rather than recalled. Where the document names a column, that column must appear in `RESPONSES_REQUIRED`, `RESPONSES_OPTIONAL`, `MEAL_REQUIRED`, `RESPONSES_COLUMN_MAP` or `MEAL_COLUMN_MAP`.

- [ ] **Step 1: Read the schema contract in full**

Run: `.venv/Scripts/python.exe -c "from sami import schema; print(schema.RESPONSES_REQUIRED); print(schema.RESPONSES_OPTIONAL); print(schema.MEAL_REQUIRED); print(schema.HEADER_MARKERS)"`

Also read `schema.meal_column_map` and `schema.require_columns` to describe their behaviour accurately.

- [ ] **Step 2: Write the document**

Cover, in this order:

1. **The two sources** — one paragraph each: what the responses export is (one row per chatbot user, with the conversation in `QA Messages`) and what the MEAL export is (one row per survey respondent).
2. **How a file is located** — the role folder, newest-wins, `--responses`/`--meal` override. Link to `datasets/README.md` rather than repeating it.
3. **The header row** — the exports carry banner rows above the real header; the header is *detected* by looking for a row containing a known marker set (list the marker sets from `HEADER_MARKERS`), scanning the first `HEADER_SCAN_ROWS` rows. A re-export with a different number of banner rows loads unchanged.
4. **Column names are mapped** — a table of `RESPONSES_COLUMN_MAP` and `MEAL_COLUMN_MAP` (platform name → the name the pipeline uses). State that unmapped columns pass through untouched.
5. **Required columns** — a table per source, from `RESPONSES_REQUIRED` and `MEAL_REQUIRED`, each with one line on what it feeds. A missing required column stops the run with a message naming the file, the column, and the columns the file does have.
6. **Optional columns** — from `RESPONSES_OPTIONAL`, with what each one adds. Absence degrades a figure; it never stops the run.
7. **The MEAL question columns** — matched by their question text, not by position. Give the five question texts. State that when a question is reworded past recognition the loader falls back to position and warns, naming the column it used.
8. **New columns** — reported, never fatal. A refreshed export gaining a field is normal.
9. **When something is wrong** — the shape of a `SchemaError`: the problem, the file, the fix. Show one real example, produced by actually triggering it (delete a required column from a copy of the fixture and capture the message).

State mechanically that `dim_user` carries `instrument_version` (`v1` / `v2`) and that fields differing between the two questionnaire versions are reported per cohort. Give no rationale for that split, and do not discuss which fields are or are not comparable across versions.

- [ ] **Step 3: Verify every column named exists**

Run a check that each column name mentioned in the document appears in the schema module:

```bash
.venv/Scripts/python.exe - <<'PY'
import re, pathlib
from sami import schema
doc = pathlib.Path("docs/DATA_SOURCES.md").read_text(encoding="utf-8")
known = set(schema.RESPONSES_REQUIRED) | set(schema.RESPONSES_OPTIONAL) \
    | set(schema.MEAL_REQUIRED) | set(schema.RESPONSES_COLUMN_MAP) \
    | set(schema.RESPONSES_COLUMN_MAP.values()) | set(schema.MEAL_COLUMN_MAP) \
    | set(schema.MEAL_COLUMN_MAP.values())
cited = set(re.findall(r"`([A-Z][A-Za-z _()]+)`", doc))
unknown = sorted(c for c in cited if c not in known)
print("cited but not in schema.py:", unknown)
PY
```

Expected: an empty list, or only entries that are demonstrably not column names (table names, file names). Fix any real mismatch in the document.

- [ ] **Step 4: Run the forbidden-topic check**

Run: `git grep -niE "kappa|κ|quotab|directional|0\.7 gate|poolab|Colombian" -- docs/DATA_SOURCES.md`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add docs/DATA_SOURCES.md
git commit -m "docs: source export contract for the two input files"
```

---

### Task 8: `docs/OPERATIONS.md` — the refresh runbook

**Files:**
- Create: `docs/OPERATIONS.md`
- Read for content: `src/sami/preflight.py` (all ten checks), `run_pipeline.py`

**Interfaces:**
- Consumes: Task 6's verified runtimes and outputs; Task 7's document (linked, not repeated).
- Produces: a document `README.md` links to.

- [ ] **Step 1: Enumerate the checks from the source**

Run: `.venv/Scripts/python.exe -c "from sami import preflight; print([c.__name__ for c in preflight.CHECKS])"`

The document must describe exactly these, in this order, with no additions.

- [ ] **Step 2: Capture real output to quote**

Run: `.venv/Scripts/python.exe run_pipeline.py --check`

Quote the actual rendered block in the document rather than an invented one.

- [ ] **Step 3: Write the document**

Cover, in this order:

1. **Install** — `uv sync`; the optional CUDA opt-in `uv sync --no-group cpu --group gpu`; the plain pip + venv path. Move this content out of `README.md` (Task 10 trims it there and links here).
2. **The first run downloads models** — roughly 4 GB from Hugging Face, once, cached in the user's Hugging Face cache directory. Subsequent runs are offline for the models.
3. **Refresh runbook** — the numbered end-to-end sequence: save new exports into `datasets/<role>/`, `--check`, run, inspect `parity_check`, refresh Power BI. Each step with its exact command and what success looks like.
4. **The three run modes** — `run_pipeline.py`, `--skip-nlp`, `--check` — with what each does and roughly how long it takes. Use the measured figures: full run 2m11s on an RTX 3050 Ti, 5m22s on CPU, `--skip-nlp` seconds.
5. **The ten preflight checks** — a table: check name, what it verifies, what to do when it fails. Take each fix string from `preflight.py` so the document and the program agree.
6. **The parity gate** — `parity_check.csv` reconciles exported row counts against `qa.reconciliation`; the script exits non-zero on a mismatch and the run must not be published.
7. **CPU and GPU** — 17 of the 19 tables are byte-identical between devices; `meta_run` differs in `generated_at`, and `nlp_umap` differs in its `x`/`y` coordinates while every `user_id` and `cluster_id` matches. No count or percentage anywhere depends on those coordinates.
8. **`SAMI_SALT`** — required, out-of-band, in `.env` at the repository root. Using a different salt produces different `user_id` values and the exports will not join against the previous ones.
9. **The `.pbix` is a tracked binary** — each saved version adds its full size to the repository, so commit it on meaningful revisions rather than on every save.
10. **Troubleshooting** — a table of the failure modes actually observed: `SAMI_SALT is not set`; `no .xlsx in datasets/<role>/`; a `~$` lock file present because the workbook is open in Excel; a `SchemaError` naming a missing column; parity failure; `uv sync` deleting `src/` when `tool.uv.package = false` is lost; Windows Smart App Control blocking uv-managed Python (`spawn UNKNOWN`), fixed by `python-preference = "only-system"`.

- [ ] **Step 4: Execute every command the document contains**

Each command in the document must be run as written and its output must match what the document claims. Correct the document where it does not.

- [ ] **Step 5: Run the forbidden-topic check**

Run: `git grep -niE "kappa|κ|quotab|directional|0\.7 gate|poolab|Colombian" -- docs/OPERATIONS.md`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add docs/OPERATIONS.md
git commit -m "docs: operations runbook — install, refresh, preflight, troubleshooting"
```

---

### Task 9: `docs/METHODOLOGY.md` — how the numbers are produced

**Files:**
- Create: `docs/METHODOLOGY.md`
- Read for content: `src/sami/load.py`, `src/sami/taxonomy.py`, `src/sami/clusters.py`, `src/sami/cohort.py`, `src/sami/metrics.py`, `src/sami/qa.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a document `README.md` and `exports/_schema.md` link to.

- [ ] **Step 1: Write the document**

Cover, in this order:

1. **Pseudonymization** — `user_id = sha256(salt + digits(name))[:12]`. Deterministic, salted, non-reversible. `digits()` strips a float tail so an id stored as a number in one export and as text in another yields the same hash. All 1,392 users are pseudonymised and the exports pass a PII scan before any file is written; `export.write_all` refuses to write if a scan hits.
2. **The message spine** — how one row per user with a `Messages` blob becomes one row per message: splitting, noise removal (lines under 3 characters, bare digits, `undefined`, `?`), and redaction of digit runs before splitting.
3. **The category taxonomy** — the seven official MMC categories from `taxonomy.py`, how a message is assigned a `dominant_category`, and the `Suggestion` bucket for messages that match none.
4. **Archetypes** — user documents are embedded, `k` is chosen by scanning a range with a stability criterion rather than fixed by hand, and KMeans at the chosen `k` assigns each user an archetype. Give the current chosen `k` and the stability ARI from the committed `meta_run.csv`, read from the file rather than recalled.
5. **Cohorts** — `dim_user` carries `instrument_version` (`v1` / `v2`) because the registration survey was rewritten in July 2026. Every field that can reach `dim_user` or `fact_meal` is classified in `src/sami/cohort.py` as poolable, split-by-cohort, or version-only, and the pipeline refuses to aggregate a column with no policy rather than pooling it silently. State the mechanism. Give no rationale for any individual field's classification, and do not name nationality as an example.
6. **Sentiment** — a per-message signal produced by the sentiment model named in `meta_run`. State what it is and where it lands (`fact_message`). Say nothing about its reliability, and give no percentage, table, or example of sentiment output.
7. **Quality checks** — the checks `qa.run_checks` runs, and that failures of the critical `P1_` / `P6_` / `P9_` families stop the run.
8. **Reproducibility** — `random_state=0` throughout; the same salt and the same input files produce the same tables, with the two device-dependent exceptions noted in `docs/OPERATIONS.md`.

- [ ] **Step 2: Verify the quoted figures against the committed exports**

Run: `.venv/Scripts/python.exe -c "import pandas as pd; m=pd.read_csv('exports/meta_run.csv'); print(m.to_string())"`

Every number the document quotes for `k`, stability, row counts and model names must match this output exactly. Do not quote `tone_kappa`, `tone_gate_passed` or `sentiment_quotable`.

- [ ] **Step 3: Run the forbidden-topic check**

Run: `git grep -niE "kappa|κ|quotab|directional|0\.7 gate|poolab|Colombian" -- docs/METHODOLOGY.md`
Expected: no output.

- [ ] **Step 4: Confirm no sentiment percentage appears**

Run: `git grep -nE "[0-9]+(\.[0-9]+)? ?%" -- docs/METHODOLOGY.md`
Expected: no line where the percentage refers to sentiment, tone, positive, negative or neutral.

- [ ] **Step 5: Commit**

```bash
git add docs/METHODOLOGY.md
git commit -m "docs: methodology — how each exported number is produced"
```

---

### Task 10: Rewrite `README.md` as the front door

**Files:**
- Modify: `README.md` (full rewrite)

**Interfaces:**
- Consumes: `docs/DATA_SOURCES.md`, `docs/OPERATIONS.md`, `docs/METHODOLOGY.md`, `datasets/README.md`, `docs/powerbi_guide.md`, `exports/_schema.md`.
- Produces: the entry point for every other document.

The current `README.md` is 221 lines and carries the install detail, the reproduction procedure, the questionnaire-version discussion and the refresh instructions. Those move to the guides; the README links to them.

- [ ] **Step 1: Write the new README**

Structure:

1. **What this is** — two or three sentences: the analysis behind the MMC WhatsApp chatbot evaluation, delivering three notebooks, a `exports/` gold layer of CSVs, and a Power BI report.
2. **What is in the repository** — a table: `datasets/` (input), `notebooks/` (the three-part narrative), `src/sami/` (shared pipeline), `run_pipeline.py` (regenerates the exports), `exports/` (gold layer), `mmc_dashboard.pbix` (the report), `docs/` (the guides), `tests/`.
3. **Quick start** — four commands and nothing else: `uv sync`; put the salt in `.env`; save the exports into `datasets/responses/` and `datasets/meal/`; `run_pipeline.py --check`; `run_pipeline.py`. Each with one line of explanation, linking to `docs/OPERATIONS.md` for detail.
4. **Updating the data** — three sentences pointing at `datasets/README.md`: role folders, filenames do not matter, newest wins.
5. **The three notebooks** — keep the existing one-paragraph descriptions of notebooks 01, 02 and 03, edited to remove any sentiment-reliability wording.
6. **The export layer** — what `exports/` is, that it is generated and never hand-edited, and links to `exports/_schema.md` and `docs/powerbi_guide.md`.
7. **Documentation index** — a table of the five guides with one line each.
8. **Requirements** — Python 3.11+, `uv`, and the note that a GPU is optional. Link to `docs/OPERATIONS.md`.

Delete the "Contributing" section — it currently reads `_Add contribution guidelines here._`, which is a placeholder and violates the global constraints.

- [ ] **Step 2: Verify every relative link resolves**

```bash
.venv/Scripts/python.exe - <<'PY'
import pathlib, re
for doc in pathlib.Path(".").glob("*.md"):
    for text, target in re.findall(r"\[([^\]]+)\]\(([^)#]+)", doc.read_text(encoding="utf-8")):
        if target.startswith("http"):
            continue
        p = (doc.parent / target).resolve()
        if not p.exists():
            print(f"BROKEN  {doc}: [{text}]({target})")
print("link check done")
PY
```

Expected: `link check done` with no `BROKEN` lines. Repeat over `docs/*.md` and `datasets/*.md`.

- [ ] **Step 3: Run the forbidden-topic check across all deliverable docs**

Run: `git grep -niE "kappa|κ|quotab|directional|0\.7 gate|poolab|Colombian" -- README.md datasets/ docs/DATA_SOURCES.md docs/OPERATIONS.md docs/METHODOLOGY.md docs/powerbi_guide.md exports/_schema.md`
Expected: no output.

- [ ] **Step 4: Confirm no placeholder wording survives**

Run: `git grep -niE "TBD|TODO|_Add .* here_|coming soon|for now|we think|probably|should be" -- README.md datasets/ docs/DATA_SOURCES.md docs/OPERATIONS.md docs/METHODOLOGY.md`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README as the handover front door"
```

---

### Task 11: Update `docs/powerbi_guide.md` and `exports/_schema.md`

**Files:**
- Modify: `docs/powerbi_guide.md:92-98` (§3.1), `docs/powerbi_guide.md:1755-1773` (§12.2), and any section carrying a removed topic
- Modify: `exports/_schema.md`

**Interfaces:**
- Consumes: `datasets/README.md`, `docs/OPERATIONS.md`.
- Produces: the last two documents the recipient reads.

- [ ] **Step 1: Find every occurrence of the stale data path and the removed topics**

```bash
git grep -n "data_&_docs" -- docs/powerbi_guide.md exports/_schema.md
git grep -niE "kappa|κ|quotab|directional|0\.7 gate|poolab|Colombian" -- docs/powerbi_guide.md exports/_schema.md
```

Both lists must be empty when this task ends.

- [ ] **Step 2: Update §3.1 and §12.2 of the Power BI guide**

§3.1 defines the `DataFolder` parameter — confirm it points at `exports/` and that its description does not reference `data_&_docs/`.

§12.2, the refresh runbook, currently begins "Copy the new export workbooks into `data_&_docs/`" (line 1763). Replace that step with: save the responses export into `datasets/responses/` and the MEAL export into `datasets/meal/`, then run `run_pipeline.py`. Link to `datasets/README.md` and `docs/OPERATIONS.md` instead of restating them.

- [ ] **Step 3: Remove the two topics from the guide's measures and text**

Section 5.4 is titled "Tone". Rewrite it so it describes only the measures that exist, with no reliability discussion and no sentiment percentage in any measure, title, subtitle, or editorial tile. If a measure's DAX computes a sentiment percentage, leave the DAX and remove the surrounding commentary — this task edits documentation, not the report's logic.

Check §5.5 "Dynamic text", §10 "The hidden About page" and §11.2 "Dynamic subtitles" for the same wording.

- [ ] **Step 4: Reconcile `exports/_schema.md` against the actual exports**

```bash
.venv/Scripts/python.exe - <<'PY'
import pathlib, pandas as pd
doc = pathlib.Path("exports/_schema.md").read_text(encoding="utf-8")
for csv in sorted(pathlib.Path("exports").glob("*.csv")):
    name = csv.stem
    if name.startswith("_"):
        continue
    cols = list(pd.read_csv(csv, nrows=1).columns)
    missing = [c for c in cols if f"`{c}`" not in doc]
    if name not in doc:
        print(f"TABLE MISSING FROM DOC: {name}")
    elif missing:
        print(f"{name}: columns not documented -> {missing}")
print("schema doc check done")
PY
```

Fix every reported gap. This branch changed `agg_funnel`, `dim_user` and `meta_run`, so expect hits there.

- [ ] **Step 5: Re-run both greps from Step 1**

Expected: both empty.

- [ ] **Step 6: Commit**

```bash
git add docs/powerbi_guide.md exports/_schema.md
git commit -m "docs(powerbi): point the refresh runbook at datasets/, reconcile the schema reference"
```

---

### Task 12: Full verification, then merge to `main`

**Files:**
- No file changes beyond a possible `exports/` regeneration.

**Interfaces:**
- Consumes: Tasks 1-11.
- Produces: a `main` branch carrying the whole deliverable.

- [ ] **Step 1: Full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q -rs`
Expected: all pass. With `datasets/` populated from Task 6, the real-data tests now run rather than skip. Read the skip reasons; none should be `datasets/ holds no .xlsx`.

- [ ] **Step 2: Regenerate the exports and confirm parity**

Run: `.venv/Scripts/python.exe run_pipeline.py`
Expected: exit 0, `parity_check` all `True`.

Run: `git diff --stat exports/`
Expected: only `meta_run.csv` and `nlp_umap.csv` differ, per Task 6 Step 5. Commit the regenerated exports if they differ:

```bash
git add exports/
git commit -m "chore(exports): regenerate from datasets/ intake"
```

- [ ] **Step 3: Fresh-clone install check**

```bash
git clone . ../_fresh_clone_check
cd ../_fresh_clone_check
uv sync
.venv/Scripts/python.exe -m pytest -q -rs
.venv/Scripts/python.exe run_pipeline.py --check
cd -
rm -rf ../_fresh_clone_check
```

Expected: `uv sync` resolves including the three dependencies added in Task 4. Tests pass, with the real-data tests skipping (the clone has no `datasets/` content — that is correct and is what a recipient sees). `--check` FAILs on `responses`, `meal` and `salt` with the intake and salt instructions, and no traceback. **That failure output is the first thing MMC will see; read it and confirm it is self-explanatory.**

- [ ] **Step 4: Final documentation sweep**

```bash
git grep -niE "kappa|κ|quotab|directional|0\.7 gate|poolab|Colombian" -- README.md datasets/ docs/DATA_SOURCES.md docs/OPERATIONS.md docs/METHODOLOGY.md docs/powerbi_guide.md exports/_schema.md
git grep -niE "TBD|TODO|_Add .* here_" -- README.md datasets/ docs/DATA_SOURCES.md docs/OPERATIONS.md docs/METHODOLOGY.md
git grep -n "data_&_docs" -- README.md datasets/ docs/DATA_SOURCES.md docs/OPERATIONS.md docs/METHODOLOGY.md docs/powerbi_guide.md exports/_schema.md src tests run_pipeline.py
```

Expected: all three produce no output.

- [ ] **Step 5: Merge to `main`**

`feature/pipeline-replicability` is a strict ancestor of this branch, and the other six local feature branches are already contained in `main`, so this one merge leaves nothing unmerged.

```bash
git checkout main
git merge --no-ff feature/v2-export-migration -m "merge: v2 export migration, datasets/ intake and handover documentation"
.venv/Scripts/python.exe -m pytest -q
git branch --no-merged main
```

Expected: the merge succeeds, the suite passes on `main`, and `git branch --no-merged main` prints nothing.

- [ ] **Step 6: Do not push yet**

The push happens after Task 13, so history is rewritten once. Report the merge result and stop.

---

### Task 13: Purge the two PII files from git history

**Files:**
- Rewrites all of git history. No working-tree file changes.

**Interfaces:**
- Consumes: Task 12's merged `main`.
- Produces: a verified local history with the two blobs gone, and a force-push command handed to the project owner.

Targets:
- `data_&_docs/Base de datos MEAL Sami_060526.xlsx`
- `data_&_docs/Base de datos respuestas Sami_060526.xlsx`

Both carry raw WhatsApp phone numbers. They are untracked today, but their blobs remain reachable from history.

**This task does not push.** `origin` is the shared organisation repository `DiversaStudio/chatbot_methodology_mmc`, carrying four other pushed branches including a contributor's `copilot/add-surface-readme`. Rewriting it invalidates every existing clone, so the force-push is the project owner's to run once the team has been told.

- [ ] **Step 1: Record the blob SHAs to verify against afterwards**

```bash
git rev-list --all --objects | grep "Base de datos" | tee ../_pii_blobs_before.txt
```

Expected: at least two lines. Keep the file — Step 6 checks these exact SHAs are unreachable.

- [ ] **Step 2: Take a full mirror backup outside the repository**

```bash
git clone --mirror . ../_backup_before_purge.git
git -C ../_backup_before_purge.git rev-list --all --count
```

Expected: a commit count matching `git rev-list --all --count` in the working repository. Do not proceed until this matches — it is the only way back.

- [ ] **Step 3: Confirm `git-filter-repo` is available**

Run: `.venv/Scripts/python.exe -m pip show git-filter-repo || uv pip install git-filter-repo`
Then: `.venv/Scripts/python.exe -m git_filter_repo --version`
Expected: a version prints.

- [ ] **Step 4: Confirm the working tree is clean and every branch is committed**

Run: `git status --porcelain && git stash list`
Expected: both empty. `git filter-repo` refuses to run on a dirty tree, and a stash would not survive the rewrite.

- [ ] **Step 5: Run the purge**

```bash
.venv/Scripts/python.exe -m git_filter_repo --force \
  --invert-paths \
  --path "data_&_docs/Base de datos MEAL Sami_060526.xlsx" \
  --path "data_&_docs/Base de datos respuestas Sami_060526.xlsx"
```

- [ ] **Step 6: Verify the blobs are gone**

```bash
git rev-list --all --objects | grep "Base de datos" ; echo "exit=$?"
git log --all --diff-filter=A --name-only --format="" -- "data_&_docs/*" | sort -u
while read -r sha _; do git cat-file -e "$sha" 2>/dev/null && echo "STILL REACHABLE: $sha"; done < ../_pii_blobs_before.txt
```

Expected: the first grep prints nothing (`exit=1`); the second prints nothing; the third prints no `STILL REACHABLE` line.

- [ ] **Step 7: Verify nothing legitimate was lost**

```bash
git ls-files tests/fixtures/
.venv/Scripts/python.exe -m pytest -q
git log --oneline -5
git branch -a
```

Expected: both `.xlsx` fixtures still tracked; the suite passes; `main` carries the Task 12 merge; every branch still present. **If the suite fails here, restore from `../_backup_before_purge.git` and stop.**

- [ ] **Step 8: Restore the `origin` remote**

`git filter-repo` removes it by design.

```bash
git remote add origin https://github.com/DiversaStudio/chatbot_methodology_mmc
git remote -v
```

- [ ] **Step 9: Stop and hand off**

Do not push. Report to the project owner:

- that the purge is verified locally and every SHA has changed;
- that the mirror backup is at `../_backup_before_purge.git` and must be kept until the push is confirmed good;
- that everyone with a clone must re-clone after the push, and any unpushed work they hold must be saved as patches first;
- the exact commands to run when the team has been told:

  ```bash
  git push --force origin main
  git push --force origin feature/v2-export-migration
  ```

- that the four other branches on `origin` (`copilot/add-surface-readme`, `feature/analysis-notebooks`, `feature/diana-review-fixes`, `feature/sami-nb3`) still hold pre-purge history and must be deleted from the remote or force-pushed from their rewritten local counterparts, or the purged blobs remain reachable on the server.

- [ ] **Step 10: Delete the backup only after the owner confirms the push succeeded**

Not part of this task. Leave `../_backup_before_purge.git` in place.

---

## Verification Summary

| Claim | Command that proves it |
| --- | --- |
| Resolution is correct | `pytest tests/test_datasets.py -v` |
| No hardcoded paths remain | `git grep -n "RESPONSES_PATH\|MEAL_PATH\|data_&_docs" -- src tests run_pipeline.py` |
| A renamed export still runs | Task 6 Step 7 |
| An empty folder fails legibly | Task 6 Step 8 |
| Data cannot be committed | Task 6 Step 2 (`git status --porcelain datasets/` empty) |
| Results are unchanged | Task 6 Step 5 (`git diff --stat exports/`) |
| Dependencies are declared | `pytest tests/test_requirements.py -v` |
| A fresh clone installs | Task 12 Step 3 |
| The two topics are absent | Task 12 Step 4, grep 1 |
| No placeholders survive | Task 12 Step 4, grep 2 |
| Nothing is left unmerged | `git branch --no-merged main` empty |
| The PII blobs are gone | Task 13 Step 6 |
