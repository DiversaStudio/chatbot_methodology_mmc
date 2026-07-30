# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## What this is

This repo holds the data analysis behind the chatbot's evaluation and methodology: a **three-part "SAMI" narrative** of notebooks, a generated `exports/` gold layer of CSVs, and a Power BI report built on top of that gold layer.

## What is in the repository

| Path | What it is |
| --- | --- |
| [`datasets/`](datasets/README.md) | Input — drop the two source exports here; see the guide for the mechanism. |
| [`notebooks/`](notebooks/) | The three-part narrative (`01_input_and_audience`, `02_demand_behaviour_experience`, `03_text_insights_nlp`). |
| [`src/sami/`](src/sami/) | The shared pipeline: loaders, cleaning, schema, cohort policy, clustering, NLP, export. |
| `run_pipeline.py` | Regenerates every table in `exports/` from the current data. |
| [`exports/`](exports/_schema.md) | The gold layer — tidy CSVs the notebooks and the Power BI report both read. Generated, never hand-edited. |
| `mmc_dashboard.pbix` | The Power BI report, bound to `exports/`. Built per [`docs/powerbi_guide.md`](docs/powerbi_guide.md). |
| [`docs/`](#documentation-index) | The guides: data sources, operations, methodology, Power BI build. |
| `tests/` | The test suite covering `src/sami/`. |

## Quick start

```powershell
uv sync                                                # install dependencies
# put SAMI_SALT=<value> in a .env file at the repo root, obtained out-of-band
# save the responses export into datasets/responses/, the MEAL export into datasets/meal/
.venv\Scripts\python.exe run_pipeline.py --check       # preflight: verify the machine and the files
.venv\Scripts\python.exe run_pipeline.py               # full run -> exports/
```

See [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for what each step does, what a passing preflight looks like, and how to diagnose a failure.

## Updating the data

Drop a new export into `datasets/responses/` or `datasets/meal/` — the folder declares the file's role, not its name, and the newest `.xlsx` in each folder is the one the pipeline reads. See [`datasets/README.md`](datasets/README.md) for the full mechanism, and [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for what each file must contain.

## The three notebooks

- [`notebooks/01_input_and_audience.ipynb`](notebooks/01_input_and_audience.ipynb) — **Notebook 1 · Input & user profile.** Deliberately descriptive univariate EDA: characterizes the two sources (chatbot *responses* + the *MEAL* survey) — size and completeness — then profiles the audience (nationality, gender, age, care responsibilities), geography (users per city, a Colombia map), and the migration journey (time away, origin → onward routes on Americas maps).
- [`notebooks/02_demand_behaviour_experience.ipynb`](notebooks/02_demand_behaviour_experience.ipynb) — **Notebook 2 · Behaviour, needs & satisfaction.** Everything investigative that is *not* NLP: variable cross-cuts (gender × nationality, engagement by city, age × destination), usage and MEAL satisfaction over time, the most-requested needs and where/when demand concentrates, needs by the original MMC category, and depth-of-use / abandonment.
- [`notebooks/03_text_insights_nlp.ipynb`](notebooks/03_text_insights_nlp.ipynb) — **Notebook 3 · Emergent themes & emotion (NLP).** Discovers the semantic structure of the messages automatically and contrasts it with the official 7-category taxonomy: KMeans over sentence embeddings (primary) and lemmatized TF-IDF (comparison), the cluster-vs-taxonomy agreement, the **emergent themes** the taxonomy misses, PCA-tinted 2D/3D embedding maps, qualitative voices (word cloud + thematic read), per-message sentiment, and a closing geographic synthesis of need and tone by city. The NLP runs **inline on the GPU** (CUDA; automatic CPU fallback) and is not cached; it downloads the embedding/sentiment models and lemmatizes with spaCy's Spanish `es_core_news_sm` on first run.

The three notebooks import their shared loaders, cleaning, metrics, and NLP logic from [`src/sami/`](src/sami/). Earlier, fully self-contained exploratory notebooks are retained for reference in [`notebooks/arxiv/`](notebooks/arxiv/).

They run on the project's `.venv` in order 01 → 02 → 03 — see [Running the notebooks in `docs/OPERATIONS.md`](docs/OPERATIONS.md#running-the-notebooks) for how to launch them.

## The export layer

`exports/` is the gold layer the Power BI report binds to: a set of tidy CSVs (dimensional `dim_*` / `fact_*` / `agg_*` / `nlp_*` tables, plus `meta_run` and `parity_check`) from which every plot in the three notebooks can also be reproduced. It is generated — never hand-edited — by `run_pipeline.py`, via `src/sami/export.py`. `dim_user` carries an `instrument_version` column (`v1` / `v2`) recording which questionnaire version produced each user's registration record.

- [`exports/_schema.md`](exports/_schema.md) — the full table-by-table reference: grain, columns, which notebook plot each table feeds.
- [`docs/powerbi_guide.md`](docs/powerbi_guide.md) — how `mmc_dashboard.pbix` is built on top of `exports/`, and how to refresh it.

## Documentation index

| Guide | Covers |
| --- | --- |
| [`datasets/README.md`](datasets/README.md) | How to drop in a new export: folder roles, filenames, newest-file-wins. |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | What the responses and MEAL exports must contain, column by column. |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Install, the refresh runbook, the preflight checks, troubleshooting. |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | How every number in `exports/` is produced, traced back to code. |
| [`docs/powerbi_guide.md`](docs/powerbi_guide.md) | How `mmc_dashboard.pbix` is built and refreshed. |

## Requirements

Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) for environment and dependency management. A GPU is optional — the pipeline and notebooks run on CPU, the NLP stage is just slower. See [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for install steps, including a plain pip + venv alternative.
