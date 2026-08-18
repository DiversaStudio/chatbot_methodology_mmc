# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SAMI analytics pipeline and dashboard for the MMC WhatsApp chatbot serving migrants in Colombia. Not an installable library — a notebook/analysis project (`tool.uv.package = false`). The pipeline reads two Excel exports (chatbot responses + MEAL survey), cleans/pseudonymizes/clusters/analyzes them, and writes a gold layer of CSVs to `exports/` that feed both the three Jupyter notebooks and the Power BI report (`powerbi/mmc_dashboard.pbix`).

## Commands

```bash
uv sync                                     # install deps (CPU torch by default)
uv sync --no-group cpu --group gpu          # NVIDIA machines: install CUDA torch instead
                                             # (a bare `uv sync` after this reinstalls CPU torch over it — re-sync with this flag again)

uv run python run_pipeline.py --check       # preflight only, no work, seconds
uv run python run_pipeline.py               # full pipeline run, ~3 min on GPU, ~5 min CPU-only

uv run python -m pytest                     # full test suite
uv run python -m pytest tests/test_export.py                    # one file
uv run python -m pytest tests/test_export.py::test_name -v      # one test
uv run python -m pytest -m "not slow"       # skip tests needing real model download/inference
uv run jupyter lab                          # run notebooks (or open in VS Code with the .venv kernel)
```

Requires `SAMI_SALT` in a `.env` file at repo root (out-of-band value; never committed — it salts the `user_id` hash, so a different salt breaks joins against existing exports) and real `.xlsx` exports dropped into `datasets/responses/` and `datasets/meal/` (also gitignored — they carry WhatsApp phone numbers). Without real data, tests that need it are skipped via the `requires_real_data` marker in `tests/conftest.py`; everything else runs against the committed synthetic fixtures in `tests/fixtures/` (regenerate with `uv run python tests/fixtures/make_fixtures.py`).

Full operational detail — preflight checks, the parity gate, troubleshooting table, CPU/GPU determinism guarantees — lives in `OPERATIONS.md`; read it before touching pipeline internals or diagnosing a run failure rather than duplicating that knowledge here.

## Architecture

**Entry point / compute path.** `sami.load_sami()` (`src/sami/facade.py`) is the single entry point both notebooks and `run_pipeline.py` use — it validates schema, loads + pseudonymizes the two exports, builds the message-grain frame, runs QA checks, and returns a frozen `SamiData` bundle (`responses`, `messages`, `meal`, `reconciliation`, `run_meta`). Anything that needs the cleaned data goes through this, not through re-parsing Excel directly.

**Pipeline stages** (`run_pipeline.py`, orchestrating `src/sami/*`):
1. `load_sami()` — load + validate + pseudonymize (`datasets.py` resolves which file to read; `load.py`, `schema.py`, `qa.py` do the work)
2. Build dimension/fact tables
3. NLP block (not optional — clustering *is* the dashboard's categorization axis): embed user documents → choose k / cluster (`clusters.py`) → cluster terms + UMAP projection → sub-clustering (`subclusters.py`) → sentiment + emotion → archetype profiles/tone validation (`taxonomy.py`, `theme.py`, `validation.py`)
4. Bot replies + coverage gap (`bot_replies.py`, optional `datasets/bot_log/` input)
5. Aggregate tables (`metrics.py`, `cohort.py`, `stats.py`, `canon.py` for entity canonicalization)
6. PII scan (`redact.py`) + write (`export.py::write_all`, the only function in the codebase that touches disk for outputs)

`export.py` is deliberately pure `build_*(frames) -> DataFrame` functions with no I/O, aside from `write_all`. `run_pipeline.py` is its sole production caller.

**The parity gate.** Every run reconciles `exports/` row counts/metrics against `qa.reconciliation`, an independently computed count from the loaded data, and writes/prints `exports/parity_check.csv`. A run where any row's `match` is `False` prints `PARITY FAILED` and exits non-zero — its `exports/` output must not be committed or used to refresh Power BI. Don't bypass or silence this.

**Determinism.** Clustering and UMAP are seeded (`RANDOM_STATE = 0`); two runs on the same machine/inputs produce byte-identical exports except `meta_run.csv`'s timestamp. Across CPU vs GPU, only `meta_run.csv` and `nlp_umap.csv`'s x/y projection coordinates differ — no count or percentage in the exports depends on those coordinates.

**Schema is versioned and self-documenting.** `exports/_schema.md` is the Power BI data contract (grain, columns, which notebook/dashboard page consumes each table) and carries a changelog at the top explaining *why* each `schema_version` bump happened — read recent entries before changing a table's shape, since dashboard filter-wiring depends on which column carries `user_id`/`message_id` for relationship joins. `exports/_manifest.csv` lists every generated table.

**Redaction/pseudonymization is layered, not optional.** `user_id` is a salted hash (`config.get_salt()` / `SAMI_SALT`); `redact.py` does a PII scan before write; entity/name matching in `canon.py` has a documented "distrust" policy for openers that produced false positives (see git log for the layer-1 distrust-rule history) — don't loosen it without checking why it exists.

**Tests mirror `src/sami/*` files 1:1** (`test_canon.py`, `test_export.py`, etc.). Fixtures are synthetic and committed (`tests/fixtures/*.xlsx`, generated by `tests/fixtures/make_fixtures.py`); tests needing the real (gitignored) export are marked `requires_real_data` and skip cleanly otherwise. `pytest.ini_options` sets `pythonpath = ["src"]`, so tests import `sami` directly.

**The `.pbix` is a tracked binary** — git can't diff it, so each save adds full file size to history. Commit it on meaningful report changes, not every iteration.

## Notes for changes

- `torch` CPU/GPU are mutually exclusive `uv` dependency groups (`default-groups = ["cpu", "dev"]`); don't add torch as a plain dependency.
- `[tool.uv] package = false` is required — `src/` is not an installable package root; don't revert this or `uv sync` will misbehave.
- If a required column is missing from a source export, extend `RESPONSES_REQUIRED` / `MEAL_REQUIRED` in `src/sami/schema.py`, and check `docs/DATA_SOURCES.md` for the source contract (gitignored locally but should exist in your checkout — ask if absent).
