# Dataset intake + handover documentation — design

**Date:** 2026-07-29
**Branch:** `feature/v2-export-migration`
**Goal:** make the pipeline runnable by MMC on new data drops without editing code, and rewrite the documentation as a self-sufficient handover deliverable.

---

## 1. Problem

The pipeline is already tolerant of *schema* drift: `src/sami/schema.py` detects the
header row, maps v2 column names onto canonical ones, matches the five MEAL
questions by their question text, and treats new columns as non-fatal.

It is not tolerant of *filename* drift. `src/sami/config.py` hardcodes
`data_&_docs/Users_Group_Title_2807.xlsx` and
`data_&_docs/Survey_Responses_Group_Title_2807.xlsx`. A recipient who receives a
newer platform export must either edit `config.py` or remember to pass
`--responses` / `--meal` on every run. `data_&_docs/` also mixes raw exports with
project Word documents and two obsolete v1 exports, so there is no folder whose
contract is "the current data".

The documentation is written for the author. It assumes the reader can ask
questions.

## 2. Scope

In scope: a dataset intake folder with role-based resolution; the documentation
set; declaring three undeclared runtime dependencies; tracking the Power BI
artifacts; purging two PII-bearing files from git history; merging this branch to
`main`.

Out of scope: an offline model bundle (MMC has normal internet); any change to
analysis logic, metrics, or exports content.

---

## 3. Dataset intake

### 3.1 Folder layout

```text
datasets/
  README.md          tracked — the drop instructions
  responses/         the chatbot users/responses export
    .gitkeep
  meal/              the MEAL survey export
    .gitkeep
```

Role is declared by the subfolder, not by the filename. Any `.xlsx` placed in a
role folder is a candidate for that role.

`.gitignore` gains `datasets/**/*.xls*`, with `!datasets/**/README.md` and
`!datasets/**/.gitkeep` negations. The folders and their documentation are
tracked; the data never is.

`data_&_docs/` remains gitignored and is left physically untouched on the author's
machine. No code path and no document references it after this change.

### 3.2 `src/sami/datasets.py`

A new module with one responsibility: resolve a role to a file.

```python
ROLES = ("responses", "meal")

class DatasetError(schema.SchemaError): ...

def folder(role: str) -> Path
def candidates(role: str) -> list[Path]
def resolve(role: str) -> Path | None
def describe(role: str) -> str
```

- `candidates` globs `datasets/<role>/*.xlsx`, excluding Excel lock files
  (`~$*`) and any non-`.xlsx` entry. Sorted by modification time, newest first.
- `resolve` returns the newest candidate, or `None` when the folder is empty.
  Returning `None` rather than raising keeps preflight able to report a clean
  FAIL and keeps module import side-effect-free.
- `describe` returns a one-line human summary used in run output:
  `datasets/responses/Users_Group_Title_1509.xlsx (modified 2026-09-15, 1 older file ignored)`
- `DatasetError` subclasses `schema.SchemaError` so the existing handler at the
  bottom of `run_pipeline.py` prints the message and its fix instead of a
  traceback. It is raised by `facade.load_sami` when a required role resolves to
  `None`, and its message names the folder, lists what was found, and states the
  fix.

**Resolution precedence:** an explicit `--responses` / `--meal` path always wins.
Otherwise the newest file in the role folder is used.

**Why newest-modified rather than a manifest or a filename convention:** the
recipient's action is "save the new export into this folder". Anything requiring
them to also update a manifest, or to preserve the platform's naming, is a step
that can be skipped silently. Modification time is a property of the act of
saving the file. Older files may be left in place as an archive without breaking
the run, and the run states which file it used, so the choice is auditable.

### 3.3 Call-site changes

`config.RESPONSES_PATH` and `config.MEAL_PATH` become functions
`config.responses_path()` and `config.meal_path()`, delegating to
`datasets.resolve`. They must be lazy: resolution now depends on folder contents,
which can change between import and use, and an empty folder must not raise at
import time.

`config.DATA_DIR` becomes `config.DATASETS_DIR = _ROOT / "datasets"`.
`config.DATA_HEADER_ROW` is unchanged — `qa.py` still uses it for its
fixture-tolerant reader.

Every reference updates:

| File | Change |
| --- | --- |
| `src/sami/facade.py:20-21` | call the resolvers; raise `DatasetError` on `None`; coerce to `Path` |
| `src/sami/load.py:173`, `:238` | call the resolvers |
| `src/sami/preflight.py:54-55` | `Context` defaults call the resolvers |
| `run_pipeline.py:108-109` | same, and print `datasets.describe(role)` for both roles at the load stage |
| `tests/conftest.py:19` | skip guard uses the resolvers |
| `tests/test_config.py:10-14` | rewritten against the resolver (see §7) |
| `tests/test_export.py:16`, `test_metrics.py:14`, `test_validation.py:144` | skip guards use the resolvers |
| `tests/test_load_meal.py:42-43`, `test_qa.py:66` | use the resolvers |

### 3.4 Two defects fixed in passing

- `facade.load_sami` builds `run_meta` with `responses_path.name`, but
  `run_pipeline.py` passes `args.responses` as a **str**, so
  `--responses PATH.xlsx` raises `AttributeError` today. The resolver coerces to
  `Path` at the boundary, which closes it.
- `tests/test_config.py` asserts the hardcoded filenames, which is what made the
  paths hard to change. Replaced with behavioural tests of the resolver.

---

## 4. Requirements

Three packages are imported directly but reach the environment only as
transitive dependencies, so an upstream resolver change could break the install
with no signal. Declared explicitly in `pyproject.toml` `[project.dependencies]`
and mirrored in `requirements.txt`:

| Package | Imported by |
| --- | --- |
| `scikit-learn` | `run_pipeline.py`, `src/sami/clusters.py` |
| `scipy` | `src/sami/stats.py`, `src/sami/clusters.py` |
| `transformers` | `src/sami/nlp.py` |

No version floors change. `requirements.txt` gains the `datasets/` note so the
pip path and the uv path describe the same setup.

`uv.lock` is refreshed by `uv lock` and the result committed.

---

## 5. Documentation set

Audience: a non-author technical reader at MMC who must install the project, drop
in a new data export, re-run the pipeline, and re-point the Power BI report —
without asking the author anything.

| File | Action |
| --- | --- |
| `README.md` | Rewritten as the front door: what this is, install, drop data, run, where outputs go, and links to the guides below. The deep material moves out. |
| `datasets/README.md` | New. Which export goes in which subfolder; filenames do not matter; the newest file is used; how to verify with `--check`; the `SAMI_SALT` requirement. |
| `docs/DATA_SOURCES.md` | New. What each export must contain, derived from `src/sami/schema.py`: required and optional columns per source, the five MEAL question texts, the v1→v2 column renames, and the behaviour when each assumption is not met. |
| `docs/OPERATIONS.md` | New. The refresh runbook end to end; all ten preflight checks and the fix for each; the parity gate; CPU and GPU runtimes; the one-time ~4 GB model download. |
| `docs/METHODOLOGY.md` | New. How each published number is produced: pseudonymization, the message spine, the seven-category taxonomy, per-cohort reporting, archetype k-selection. |
| `docs/powerbi_guide.md` | Updated: §3.1 `DataFolder` parameter and §12.2 refresh runbook, which currently instructs the reader to copy new workbooks into `data_&_docs/` (line 1763). |
| `exports/_schema.md` | Reviewed table by table against the current exports. It is hand-maintained, and this branch changed `agg_funnel`, `dim_user` and `meta_run`. |

### 5.1 Editorial rules

Every statement is declarative and describes current behaviour. No "TBD", no
placeholders, no hedged or provisional wording, no open questions addressed to
the reader.

Two topics are absent from all documentation text by decision of the project
owner: the tone/sentiment reliability discussion (the κ measurement, the 0.7
gate, quotability), and the v1/v2 nationality poolability rationale. The code
that governs both is unchanged — `meta_run` still carries `tone_gate_passed` and
`sentiment_quotable`, and `src/sami/cohort.py` still refuses to pool a column
with no policy. Consequently:

- Documentation describes sentiment as a per-message signal the pipeline
  produces. It does not discuss its reliability, and no example, template or
  measure in the documentation presents a sentiment percentage.
- Documentation states mechanically that `dim_user` carries `instrument_version`
  and that certain fields are reported per cohort. It gives no rationale.

### 5.2 Not touched

The two Gemini meeting-note files in `docs/` and everything under
`docs/superpowers/` remain internal history. `requirements/*.md` are inputs to
the work, not handover material. None are edited. If they should be removed from
the recipient's view, they move under `docs/internal/` in a separate change.

---

## 6. Power BI artifacts, history purge, merge

### 6.1 Track the report

`mmc_dashboard.pbix` (3.6 MB) and `docs/WordCloud.1.2.9.pbiviz` (465 KB) are
committed as plain tracked binaries. Both are well under any size threshold that
would justify Git LFS, and LFS would add a client-side prerequisite for the
recipient. `docs/OPERATIONS.md` notes that the `.pbix` is a binary and each saved
version adds its full size to the repository, so it should be committed on
meaningful revisions rather than on every save.

### 6.2 Purge PII from git history

Two files carrying raw WhatsApp phone numbers were committed in earlier history
and are untracked today, but their blobs remain reachable:

- `data_&_docs/Base de datos MEAL Sami_060526.xlsx`
- `data_&_docs/Base de datos respuestas Sami_060526.xlsx`

Procedure, in order:

1. Full backup: `git clone --mirror` of the repository to a path outside it,
   verified restorable before anything is rewritten.
2. `git filter-repo --invert-paths --path <each of the two paths>` over all refs.
3. Verify: the two paths return nothing from `git log --all --diff-filter=A
   --name-only`; `git cat-file` on the recorded pre-purge blob SHAs fails; the
   test fixtures under `tests/fixtures/` are untouched and the suite still
   passes.
4. Restore the `origin` remote, which `git filter-repo` removes by design.
5. **Stop.** The force-push is not executed as part of this work.

`origin` is the shared organisation repository
`DiversaStudio/chatbot_methodology_mmc`, which carries four other pushed
branches including a contributor's `copilot/add-surface-readme`. Rewriting it
invalidates every existing clone. The rewritten history is prepared and verified
locally, and the exact force-push command is handed to the project owner to run
once the team has been told. This is the only step in this design deliberately
left unexecuted.

Every SHA on every local branch changes, including the seven other feature
branches. This is expected and is why the mirror backup is step 1.

### 6.3 Merge to `main`

Once the suite passes and the end-to-end verification in §7 is green,
`feature/v2-export-migration` merges into `main`.

That single merge is sufficient. Of the seven other local feature branches, six
are already contained in `main`, and the seventh —
`feature/pipeline-replicability`, four commits ahead of `main` — is a strict
ancestor of `feature/v2-export-migration`, so this merge carries it. After it,
nothing is left unmerged and no branch sequencing is required.

Ordering: the merge happens **before** the history purge, so there is a single
rewrite event and a single force-push rather than two.

---

## 7. Verification

Nothing in this design is reported as complete without the corresponding command
having been run and its output read.

**Unit — new `tests/test_datasets.py`:**

| Case | Expected |
| --- | --- |
| empty role folder | `resolve` returns `None` |
| one `.xlsx` | that file |
| two `.xlsx` | the newer by mtime |
| an Excel lock file `~$x.xlsx` present | ignored |
| a `.csv` or `.txt` present | ignored |
| unknown role | `DatasetError` |
| `facade.load_sami` with an empty folder | `DatasetError` whose message names the folder and the fix |
| explicit path passed | wins over folder contents |

**Rewritten `tests/test_config.py`:** asserts the resolvers point inside
`DATASETS_DIR`, return `Path` or `None`, and that `DATA_HEADER_ROW == 2`. It no
longer asserts any filename.

**Suite:** `pytest` fully green. The current count is ~172; the guards in
`conftest.py` and four test modules change.

**End-to-end intake proof:**

1. Copy the two current `.xlsx` from `data_&_docs/` into `datasets/responses/`
   and `datasets/meal/`.
2. `run_pipeline.py --check` — all ten checks pass, and the output names the two
   resolved files.
3. `run_pipeline.py` — diff every written table against the committed
   `exports/`. All must be byte-identical except `meta_run.generated_at` and the
   `x`/`y` columns of `nlp_umap`.
4. **Rename both files** to something unlike the platform convention and re-run.
   Output must be identical to step 3 apart from the filenames recorded in
   `meta_run`. This is the actual proof of filename independence.
5. Empty one role folder and run `--check`. It must fail with a message naming
   the folder and the fix.

**Documentation:** every command that appears in the documentation is executed
as written. Every relative link resolves. `grep` confirms no tracked
documentation file contains the two removed topics.

**Install:** a fresh `uv sync` into a clean environment from a clean clone,
confirming the three newly declared dependencies resolve.

---

## 8. Deferred, with reasons

- **Force-pushing the rewritten history** — prepared and verified, handed to the
  owner. §6.2.
- **A clean-machine install and run** — cannot be performed from this
  environment. A fresh clone into a temporary directory with a fresh `uv sync` is
  the closest available proxy and is included in §7.
- **`SAMI_SALT` handover** — an operational task, not a repository change. The
  documentation states that the original salt must be used and that a different
  salt produces different `user_id` values; naming the person responsible for
  transferring it is outside what this repository can enforce.
- **An offline model bundle** — not needed; MMC has normal internet access.
