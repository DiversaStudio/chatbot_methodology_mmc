# Task 2 report: wire the resolver into config, loaders, preflight and the CLI

## Files touched

- `src/sami/config.py` — replaced `DATA_DIR`/`RESPONSES_PATH`/`MEAL_PATH` constants with
  `DATASETS_DIR = datasets.DATASETS_DIR` plus `responses_path()` / `meal_path()` functions
  that call `datasets.resolve(...)`. `_ROOT`, `_load_dotenv`, `get_salt` untouched.
- `src/sami/facade.py` — added `from pathlib import Path` and `datasets` to the `from . import`
  line; `load_sami`'s path resolution now does
  `Path(responses_path) if responses_path else datasets.require("responses")` (and same for meal).
- `src/sami/load.py` — added `datasets` to the import line; `load_responses`/`load_meal` now do
  `Path(path) if path else datasets.require(role)`. Also updated the stale `data_&_docs`-era fix
  text in `_read_export`'s "export not found" `SchemaError` to point at `datasets/<role>/` instead
  (see Decisions below).
- `src/sami/preflight.py` — added `datasets` import; `Context.responses_path`/`meal_path` are now
  `Path | None`, defaulted via `datasets.resolve(...)`; `_check_export` handles `path is None` as a
  FAIL naming `datasets.folder(source)` and reusing `datasets.missing_message`'s fix lines, and the
  not-found fix text now tells the user to drop the file in `datasets/<role>/`.
- `run_pipeline.py` — added `datasets` to the `from sami import (...)` list; `Context` construction
  resolves `args.responses`/`args.meal` via `datasets.resolve(...)` when not given; the loading
  stage now prints which file was chosen (`datasets.describe(role)` or the explicit override) before
  calling `load_sami`; `--responses`/`--meal` argparse help text now names the datasets/ default.
- `tests/conftest.py` — `requires_real_data` now checks `config.responses_path() and
  config.meal_path()`, reason `"real export not present (datasets/ holds no .xlsx)"`.
- `tests/test_config.py` — rewritten per the brief: behavioural tests for `DATASETS_DIR`,
  `responses_path()`/`meal_path()`, `DATA_HEADER_ROW`, and a test asserting
  `RESPONSES_PATH`/`MEAL_PATH`/`DATA_DIR` no longer exist on `config`. Kept the existing
  `test_get_salt_reads_env` / `test_get_salt_raises_when_missing`.
- `tests/test_datasets.py` — appended `test_facade_raises_dataset_error_when_folder_is_empty` and
  `test_explicit_path_wins_over_folder_contents`, verbatim from the brief.
- `tests/test_export.py`, `tests/test_metrics.py`, `tests/test_validation.py` — the
  `Path(config.RESPONSES_PATH).exists() and Path(config.MEAL_PATH).exists()` guards became
  `config.responses_path() and config.meal_path()`; the accompanying `pytest.skip(...)` reason
  strings were also updated from `"... (data_&_docs/ is gitignored)"` to
  `"... (datasets/ holds no .xlsx)"` for consistency with conftest (see Decisions).
- `tests/test_load_meal.py` — `config.MEAL_PATH` → `config.meal_path()` (both occurrences at the
  `detect_header_row`/`read_excel` call).
- `tests/test_qa.py` — `load.config.RESPONSES_PATH` → `load.config.responses_path()`.
- `tests/test_load_sami.py` — updated a comment that named `config.RESPONSES_PATH /
  config.MEAL_PATH` (the removed attributes) to name the new functions instead. No code change.

## Test command and full output

```
.venv/Scripts/python.exe -m pytest -q
```

```
......................................................................ss [ 25%]
.ssssssssssssss...s....s..s.......s.............................ss...... [ 50%]
s...s.......s....ssss....sssssss.s..................................s..s [ 75%]
.......................................................................s [100%]
============================== warnings summary ===============================
tests/test_nlp.py::test_embeddings_are_l2_normalized
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

tests/test_nlp.py::test_embeddings_are_l2_normalized
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
248 passed, 40 skipped, 2 warnings in 65.20s (0:01:05)
```

Note on the count: the brief's baseline was 284 tests / 0 skips. Total here is 288 (248 passed + 40
skipped) because the brief's own Step 1 adds 2 new tests to `tests/test_datasets.py` and the
rewritten `tests/test_config.py` has 5 tests where the old file had 3 (net +2). 284 + 4 = 288,
consistent.

All 40 skips carry the exact reason string set in `tests/conftest.py`
(`"real export not present (datasets/ holds no .xlsx)"`), confirmed with:

```
.venv/Scripts/python.exe -m pytest -rs -q | grep -c "^SKIPPED"
# 40
```

and every `SKIPPED` line ends with that same reason (spot-checked the full list — one per test
across test_export.py, test_load_meal.py, test_load_responses.py, test_load_sami.py,
test_message_spine.py, test_metrics.py, test_qa.py, test_validation.py).

Ran `tests/test_config.py tests/test_datasets.py -v` alone first: 24/24 passed (5 + 19).

## `git grep` check (brief Step 10)

```
git grep -n "RESPONSES_PATH\|MEAL_PATH\|DATA_DIR\|data_&_docs" -- src tests run_pipeline.py
```

Output:

```
src/sami/geo.py:5:Natural Earth layers committed under data_&_docs/geo/.
src/sami/geo.py:41:# Assets live inside the package (data_&_docs/ is gitignored) so they travel
tests/test_config.py:29:    """RESPONSES_PATH/MEAL_PATH/DATA_DIR are removed, not deprecated -- a stale
tests/test_config.py:31:    for name in ("RESPONSES_PATH", "MEAL_PATH", "DATA_DIR"):
tests/test_load_responses.py:175:    old_export = Path(__file__).resolve().parent.parent / "data_&_docs" / "MMC_bot_responses_1783087815.xlsx"
```

This is not empty, but every remaining hit is a deliberate exception (see Decisions):
- `geo.py` — an unrelated feature (bundled Natural Earth shapefiles), never in Task 2's file list,
  nothing to do with the responses/MEAL export paths this task migrates.
- `test_config.py` — the brief's own verbatim test text literally names the three removed
  attributes inside a docstring and a tuple, to assert they are gone. Required output, not a stale
  reference.
- `test_load_responses.py:175` — a legacy v1-export regression test that reads a specific historical
  file by its own hardcoded path (not `config.RESPONSES_PATH`), guarded by its own `.exists()` skip.
  Out of Task 2's file list; not a reference to the removed config constants.

## Decisions

1. **`load.py`'s `_read_export` "export not found" fix text** was not explicitly named in the
   brief's Step 5 (which only touches lines 173/238), but the brief's context note says the change
   "removes all references to it [`data_&_docs/`] from `src/`, `tests/` and `run_pipeline.py`", and
   leaving the old `data_&_docs`-era advice in that error message would both fail the Step 10 grep
   and mislead a user who passes an explicit but wrong `--responses PATH` (the message would tell
   them to drop it in a folder the pipeline no longer reads from). Reworded it to point at
   `datasets/<role>/`, consistent with `preflight.py`'s new fix text and `datasets.missing_message`.
2. **Skip-reason strings** in `test_export.py`/`test_metrics.py`/`test_validation.py` (inline
   guards, not the shared `requires_real_data` marker) were updated to match the new reason text for
   the same two reasons: Step 10's grep would otherwise still flag `data_&_docs`, and a skip message
   telling the reader to look in the wrong folder would be actively wrong now.
3. **`test_load_sami.py`'s comment** naming `config.RESPONSES_PATH / config.MEAL_PATH` was corrected
   to the new function names since it directly documents (incorrectly, post-change) the removed
   attributes; this is a comment-only edit, no behavior change.
4. Left `src/sami/geo.py` and `tests/test_load_responses.py:175` untouched — both reference
   `data_&_docs/` for reasons unrelated to the responses/MEAL path resolution this task migrates
   (bundled geo assets; a legacy v1-export regression test keyed to its own literal path), and
   neither appears in Task 2's file list.

## Commit

```
git add src/sami/config.py src/sami/facade.py src/sami/load.py src/sami/preflight.py run_pipeline.py tests/
git commit -m "refactor(sami): resolve source exports from datasets/, drop hardcoded paths"
```

SHA: see final report to caller.

---

## Fix round 1 of 5 (review returned spec FAIL)

Coordinator ruled the leftover `data_&_docs` references were in scope, not exempt: the plan's
global constraint is that no reference remains in `src/`, `tests/` or `run_pipeline.py`, and no
later task fixes them. Four findings addressed:

1. **`src/sami/geo.py:5`** — module docstring said assets are "committed under
   `data_&_docs/geo/`", which is factually wrong (`GEO_DIR` resolves to
   `src/sami/assets/geo/`, where the two `.geojson` files actually live). Corrected the sentence to
   name the real location.
2. **`src/sami/geo.py:41`** — comment "(data_&_docs/ is gitignored)" rewritten to keep the
   rationale (assets travel with the code so the pipeline stays deterministic and offline) without
   naming the folder.
3. **`tests/test_load_responses.py`** — deleted `test_load_responses_old_export_has_917_users` in
   full (a v1-export regression test keyed to a literal `data_&_docs/...` path; that file is not in
   the repo, is being purged from git history entirely by a later task, and the test is dead
   coverage for everyone but the author). Its `Path`/`pytest` imports were local to the function
   body, so no other import needed removal.
4. **Dead imports**: removed `from pathlib import Path` from `tests/test_export.py` and
   `tests/test_metrics.py` — both were left over from the earlier `Path(config.RESPONSES_PATH)`
   guards that Task 2 round 1 already replaced with `config.responses_path()`, and `Path` had no
   other use in either file (confirmed with `grep -n Path` on each before removing).

### Step 10 grep re-run

```
git grep -n "RESPONSES_PATH\|MEAL_PATH\|DATA_DIR\|data_&_docs" -- src tests run_pipeline.py
```

```
tests/test_config.py:29:    """RESPONSES_PATH/MEAL_PATH/DATA_DIR are removed, not deprecated -- a stale
tests/test_config.py:31:    for name in ("RESPONSES_PATH", "MEAL_PATH", "DATA_DIR"):
```

The `src/sami/geo.py` and `tests/test_load_responses.py` hits from round 1 are gone. The two
remaining hits are the brief's own verbatim `test_old_hardcoded_constants_are_gone` text (Step 1 of
the original Task 2 brief), which names the three removed attributes inside a docstring and a tuple
specifically to assert they no longer exist on `config`. This is assertion-of-absence, not a
leftover reference to a path or folder, and the coordinator's four findings for this round did not
include it, so it was left as-is.

### Covering tests

```
.venv/Scripts/python.exe -m pytest tests/test_load_responses.py tests/test_export.py tests/test_metrics.py tests/test_geo.py -v
```

Result: `64 passed, 30 skipped` — no failures.

### Full suite

```
.venv/Scripts/python.exe -m pytest -q
```

```
247 passed, 40 skipped, 2 warnings in 73.88s (0:01:13)
```

Pass count dropped from 248 to 247 (the deleted test was actually running and passing on this
machine, since the author's local `data_&_docs/` happens to hold the legacy file — it was not
counted among the skips). Skip count unchanged at 40, confirmed again with
`pytest -rs -q | grep -c "^SKIPPED"` -> `40`. Net test count 287 (was 288), matching "drop by 1".

### Commit

```
git add src/sami/geo.py tests/test_load_responses.py tests/test_export.py tests/test_metrics.py .superpowers/sdd/2026-07-29-datasets-intake-and-handover-docs/task-2-report.md
git commit -m "fix(sami): remove remaining data_&_docs references flagged in review"
```
