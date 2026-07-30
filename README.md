# chatbot_methodology_mmc

## What this is

This repo holds the data analysis behind the chatbot's evaluation and methodology: a **three-part "SAMI" narrative** of notebooks, a reproducible Python pipeline, a generated `exports/` gold layer of CSVs, and a Power BI dashboard built on top of that gold layer.

The chain runs in one direction and every link is reproducible from the one before it:

```text
datasets/  ->  run_pipeline.py (src/sami/)  ->  exports/  ->  mmc_dashboard.pbix
   raw            cleaning, NLP,               gold layer      3-page dashboard
 exports          clustering, QA               (tidy CSVs)     + notebooks
```

All derivation lives in Python under `src/sami/`. Power BI reads the exported tables and derives nothing, so any figure on the dashboard traces back to a pipeline run via `exports/meta_run.csv`.

## What is in the repository

| Path | What it is |
| --- | --- |
| [`datasets/`](datasets/README.md) | Input — drop the two source exports here; see the guide for the mechanism. Data itself is never committed. |
| [`notebooks/`](notebooks/) | The three-part narrative (`01_input_and_audience`, `02_demand_behaviour_experience`, `03_text_insights_nlp`). |
| [`src/sami/`](src/sami/) | The shared pipeline: loaders, cleaning, schema, cohort policy, taxonomy, clustering, NLP, QA, export. |
| `run_pipeline.py` | Regenerates every table in `exports/` from the current data. `--check` runs preflight only. |
| [`exports/`](exports/_schema.md) | The gold layer — tidy CSVs the notebooks and the Power BI dashboard both read. Generated, never hand-edited. |
| `mmc_dashboard.pbix` | The Power BI dashboard, bound to `exports/`. Built per [`docs/powerbi_guide.md`](docs/powerbi_guide.md). |
| `validation/` | Human tone labels the pipeline validates the sentiment model against. Committed, because they record prior analyst judgement and cannot be regenerated. |
| [`requirements/`](requirements/) | The agreed scope: analysis storytelling, notebook, dashboard and executive-report requirements. |
| [`docs/`](#documentation-index) | The guides: data sources, operations, methodology, Power BI build. |
| `tests/` | 300 tests covering `src/sami/` — schema, transformations, anonymisation guarantees, end-to-end on fixtures. |

Some working files are deliberately **not** in version control. `report/` holds the executive report written for MMC and the dashboard user manual is an internal Diversa document; both are distributed directly rather than shipped with the code. `datasets/` keeps its folder structure and its README, but never the exports themselves — the raw platform files carry users' WhatsApp phone numbers. See [Data protection](#data-protection) below.

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

## The dashboard

`mmc_dashboard.pbix` is a star-schema Power BI model over `exports/`, with three pages sharing a consistent set of filters (date range, category, city) that persist across navigation:

| Page | Answers |
| --- | --- |
| **Sami User Profile** | Who is using SAMI — counts, age and gender, duration of stay, geography, migratory intention. |
| **Demand & Experience** | What they ask and how they rate it — volume, categories, MEAL satisfaction, the engagement funnel, top institutions and procedures. |
| **Needs & Gaps** | Where the service falls short — met/unmet needs, the priority matrix, the six archetypes, word clouds. |

Measures are defined once in the model rather than per visual, so a figure such as "met needs" carries one definition everywhere. New derived measures belong in the pipeline and reach the dashboard as an exported column; DAX is reserved for display formatting. A footer version stamp and `exports/meta_run.csv` record which run produced the figures on screen.

[`docs/powerbi_guide.md`](docs/powerbi_guide.md) is the guide for whoever rebuilds or refreshes the dashboard. A separate user manual, written for MMC staff reading it, is maintained outside this repository.

## Data protection

The corpus is unsolicited messages from migrants and refugees, so handling is constrained by design rather than by convention:

- **Pseudonymisation at source.** User identifiers become salted hashes before any analytical processing. The salt lives in `.env`, is obtained out of band, and is never committed — without it the mapping cannot be reconstructed from anything in this repository.
- **No personal data leaves the machine.** All NLP runs on locally hosted open-weight models. There is no external inference path for message content.
- **Raw data is never committed.** `datasets/` tracks its structure and README only; the exports themselves are ignored. Repository history has been audited and cleaned so previously committed source files are not recoverable.
- **Automated enforcement.** `run_pipeline.py` scans every table for direct identifiers before writing it and refuses to write on a hit (`P1_*` preflight checks); the test suite covers these guarantees.

One residual risk is worth carrying forward into any public release: messages describing acute individual protection situations can be identifiable from their content alone. Such content is excluded from published outputs — quotes, word clouds and exportable tables — and handled only in aggregate.

## Documentation index

| Guide | Covers |
| --- | --- |
| [`datasets/README.md`](datasets/README.md) | How to drop in a new export: folder roles, filenames, newest-file-wins. |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | What the responses and MEAL exports must contain, column by column. |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Install, the refresh runbook, the preflight checks, troubleshooting. |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | How every number in `exports/` is produced, traced back to code. |
| [`docs/powerbi_guide.md`](docs/powerbi_guide.md) | How `mmc_dashboard.pbix` is built and refreshed. |
| [`exports/_schema.md`](exports/_schema.md) | Table-by-table reference for the gold layer. |
| [`requirements/`](requirements/) | The agreed scope for the analysis, notebooks, dashboard and executive report. |

## Environment

Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) for environment and dependency management. Dependencies and the Python version are pinned through `uv.lock`, so a run is reproducible from the lockfile alone.

A GPU is optional — the pipeline and notebooks run on CPU and only the NLP stage is slower. Torch is installed via dependency groups (CPU by default, GPU opt-in); see [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for install steps, including a plain pip + venv alternative. CPU and GPU runs produce equivalent exports apart from the coordinates of the stochastic dimensionality-reduction step, which do not affect cluster membership — `exports/parity_check.csv` records the comparison.

Run the tests with:

```powershell
.venv\Scripts\python.exe -m pytest
```
