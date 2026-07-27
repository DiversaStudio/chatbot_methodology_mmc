# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## Overview

This repo holds the data analysis work behind the chatbot's evaluation and methodology. The analysis is organized as a **three-part "SAMI" narrative** — three self-contained notebooks that move from *"what data do we have and who is the audience?"* through investigative cross-cuts to automatic NLP theme discovery. Each notebook opens with explicit objectives, guiding questions, and hypotheses, and documents the cleaning steps it applies.

- [`notebooks/01_input_and_audience.ipynb`](notebooks/01_input_and_audience.ipynb) — **Notebook 1 · Input & user profile.** Deliberately descriptive univariate EDA: characterizes the two sources (chatbot *responses* + the *MEAL* survey) — size, completeness, reliability — then profiles the audience (nationality, gender, age, care responsibilities), geography (users per city, a Colombia map), and the migration journey (time away, origin → onward routes on Americas maps).
- [`notebooks/02_demand_behaviour_experience.ipynb`](notebooks/02_demand_behaviour_experience.ipynb) — **Notebook 2 · Behaviour, needs & satisfaction.** Everything investigative that is *not* NLP: variable cross-cuts (gender × nationality, engagement by city, age × destination), usage and MEAL satisfaction over time, the most-requested needs and where/when demand concentrates, needs by the original MMC category, and depth-of-use / abandonment.
- [`notebooks/03_text_insights_nlp.ipynb`](notebooks/03_text_insights_nlp.ipynb) — **Notebook 3 · Emergent themes & emotion (NLP).** Discovers the semantic structure of the messages automatically and contrasts it with the official 7-category taxonomy: KMeans over sentence embeddings (primary) and lemmatized TF-IDF (comparison), the cluster-vs-taxonomy agreement, the **emergent themes** the taxonomy misses, PCA-tinted 2D/3D embedding maps, qualitative voices (word cloud + thematic read), per-message **sentiment** as an unsolicited distress signal, and a closing geographic synthesis of need + tone by city. The NLP runs **inline on the GPU** (CUDA; automatic CPU fallback) and is not cached; it downloads the embedding/sentiment models and lemmatizes with spaCy's Spanish `es_core_news_sm` on first run.

Source data lives in [`data_&_docs/`](data_&_docs/) (Excel exports from the chatbot platform and Kobo, plus project documentation). The three notebooks import their shared loaders, cleaning, metrics, and NLP logic from the [`src/sami/`](src/sami/) package (see the export-layer section below for the CSV outputs built on top of it). Earlier, fully self-contained exploratory notebooks are retained for reference in [`notebooks/arxiv/`](notebooks/arxiv/).

## Getting Started

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

```powershell
# Create the virtual environment and install dependencies (CPU torch)
uv sync
```

This creates a `.venv` with all dependencies declared in `pyproject.toml` (pandas, numpy, matplotlib, seaborn, missingno, wordcloud, geopandas, osmnx, shapely, cartopy, contextily, openpyxl, python-docx, Jupyter/JupyterLab, spaCy + the Spanish `es_core_news_sm` model, and the sentence-transformers/transformers/BERTopic/UMAP/HDBSCAN stack used for the NLP in notebook 03).

### GPU is optional

**`uv sync` installs the CPU build of `torch`, which works on every platform** — Windows, Linux, Intel and Apple Silicon Macs — and is about 200 MB. Everything in this repo runs on it; the NLP is just slower.

On a machine with an NVIDIA GPU, opt into the CUDA build instead:

```powershell
uv sync --no-group cpu --group gpu     # torch +cu128, ~3 GB, NVIDIA only
```

The two are declared as mutually exclusive dependency groups, so you can switch between them at any time by re-running the other command. Code never hardcodes a device: `nlp.cuda_usable()` checks that CUDA is both available *and* has a visible device, and everything falls back to CPU otherwise.

> CUDA 12.8 (not 12.4) is required because the GPU build must match the torch 2.10+ ABI that transformers 5.x / sentence-transformers 5.x need. There is no cu128 wheel for macOS or ARM at all, which is why the CUDA build can never be the default.

### Alternative: plain pip + venv (no uv, no Anaconda)

If you'd rather not use `uv`, you can install everything with the standard-library `venv` and `pip`. You need **Python 3.11+** already installed.

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate

# 2. Upgrade pip
python -m pip install --upgrade pip

# 3. Install PyTorch. CPU build — works on any machine:
pip install "torch>=2.10"
#    ...or, on a machine with an NVIDIA GPU (faster NLP):
#    pip install "torch>=2.10" --index-url https://download.pytorch.org/whl/cu128

# 4. Install everything else (mirrors pyproject.toml; includes the spaCy
#    Spanish model used by notebook 03)
pip install -r requirements.txt
```

`requirements.txt` is kept in sync with the runtime dependencies in `pyproject.toml`. `torch` is installed in a separate step so you can choose the GPU or CPU build — installing it before `requirements.txt` means pip keeps the wheel you picked. The `geopandas` / `shapely` / `cartopy` / `contextily` geospatial stack installs from prebuilt wheels on Windows, macOS, and Linux, so no system GEOS/PROJ libraries are required.

## Export layer (Power BI)

The project deliverable includes a refreshable Power BI report. `exports/` is
the **gold layer** it binds to: a set of tidy CSVs (dimensional `dim_*` /
`fact_*` / `agg_*` / `nlp_*` tables, plus `meta_run` and `parity_check`) from
which every plot in the three notebooks can be reproduced in Power BI. It is
generated — never hand-edited — by the "father" script:

```powershell
.venv/Scripts/python.exe run_pipeline.py             # full run incl. NLP -> all tables
.venv/Scripts/python.exe run_pipeline.py --skip-nlp  # no models -> non-NLP tables only
.venv/Scripts/python.exe run_pipeline.py --check     # preflight only, do no work
```

`run_pipeline.py` re-runs the same load/embed/cluster/sentiment pipeline the
notebooks do (GPU when one is present, CPU otherwise), then writes the tables
via `src/sami/export.py`, PII-scanning every frame first and refusing to write
anything if a scan hits. It prints a `parity_check` reconciliation and exits
non-zero if any metric fails to match, so a bad export never gets committed
silently.

**Tone is directional-only.** The sentiment model's agreement with the human
gold labels (κ=0.604) falls below the 0.7 quotability gate, so `meta_run`
carries `tone_gate_passed=false` / `sentiment_quotable=false`. Sentiment
signal ships in the exports but must be read as directional, never as a
published percentage.

### Reproducing `exports/` on another machine

Two things the pipeline needs are deliberately **not** in this repository, because
the raw platform exports contain users' WhatsApp phone numbers:

| What | Where it goes | Why it isn't committed |
| --- | --- | --- |
| The two `.xlsx` exports | `data_&_docs/` (gitignored) | `Name` holds raw `whatsapp:+57…` numbers |
| `SAMI_SALT` | `.env` at the repo root (gitignored), or the environment | It is the pseudonymization salt; committing it would make `user_id` reversible |

Both travel **out-of-band** — ask the project owner. Then:

```powershell
uv sync
.venv/Scripts/python.exe run_pipeline.py --check     # verify the machine first
.venv/Scripts/python.exe run_pipeline.py
```

`--check` runs ten preflight checks — Python version, packages, salt, both data
files and their columns, tone gold labels, device, model cache or network, disk,
output directory — and prints a concrete fix for anything that fails. It does no
work and downloads nothing, so it costs seconds. **Every run runs these checks
first**, which is why a missing file or absent salt stops the pipeline
immediately instead of twenty minutes in.

**Use the same salt as the original run.** `user_id` is
`sha256(salt + digits(name))[:12]`; a different salt produces different hashes,
so the exports will be internally consistent but will not match the committed
ones row-for-row.

Measured end-to-end on this project's data (917 users / 800 documents / 2991
messages), model cache warm — the first run additionally downloads ~4 GB:

| Run | GPU (RTX 3050 Ti) | CPU only |
| --- | --- | --- |
| full run | 2m11s | 5m22s |
| `--skip-nlp` | seconds | seconds |

The run prints numbered, timed stages (`[5/9] sentiment over 2991 messages …`),
so a slow stage is visibly working rather than hung.

**Does CPU give the same answers as GPU?** Yes, for everything the analysis
rests on. Running the full pipeline both ways, **17 of the 19 tables are
byte-identical**, including `dim_user`, `fact_message`, `dim_cluster`,
`nlp_cluster_terms` and `parity_check`. The two that differ:

- `meta_run` — differs only in its `generated_at` timestamp.
- `nlp_umap` — identical `user_id` and `cluster_id` for every row; only the 2D
  `x`/`y` coordinates move (up to ~4 units). UMAP amplifies the last-bit
  floating-point differences between CPU and GPU matrix kernels, so the
  *shape* of the scatter is stable but the exact coordinates are not
  reproducible across devices. No cluster assignment, count or percentage
  anywhere in the exports depends on it.

### Refreshing with a newer export

Point the pipeline at new files — nothing else needs editing:

```powershell
.venv/Scripts/python.exe run_pipeline.py --responses PATH.xlsx --meal PATH.xlsx
```

What the pipeline assumes about those files is declared in one place,
[`src/sami/schema.py`](src/sami/schema.py), and violations fail loudly:

- **The header row is detected, not assumed.** The exports carry banner rows
  above the real header; a re-export with a different number of them still loads.
- **Required columns are checked up front**, and the error names every missing
  one plus the columns the file actually has.
- **The five MEAL survey columns are matched by their question text**, not by
  position. This matters: they used to be picked positionally, so a single
  inserted column would have shifted every rating one field to the left and
  produced plausible, wrong numbers with no error. If a question is reworded past
  recognition the loader still falls back to position, but warns and names the
  exact column it guessed.
- **New columns are reported, not fatal** — a refreshed export gaining a field is
  normal.

After refreshing, check `parity_check.csv` (also printed at the end of the run):
it reconciles exported row counts against `qa.reconciliation`, and the script
exits non-zero on any mismatch.

`exports/` (the CSVs + `_manifest.csv`) is committed to the repo so the Power
BI report always has a known-good source to point at. See
[`exports/_schema.md`](exports/_schema.md) for the full table-by-table
reference (grain, columns, which notebook plot each table feeds), and
[`docs/superpowers/specs/2026-07-24-sami-exports-powerbi-design.md`](docs/superpowers/specs/2026-07-24-sami-exports-powerbi-design.md)
for the design rationale.

## Usage

Run the notebooks with the project's environment, e.g. from VS Code (select the `.venv` kernel) or from the command line:

```powershell
uv run jupyter lab
```

If you set up the environment with plain pip + venv (above), activate it first and launch Jupyter directly:

```powershell
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
jupyter lab
```

Run the notebooks in order (01 → 02 → 03). They import shared loaders and analysis logic from [`src/sami/`](src/sami/), so use the project's `.venv` (via `uv sync`, above) rather than a bare Python environment. Each notebook's setup cell locates `src/` by walking up from the working directory, so it works whether the kernel starts in `notebooks/` (JupyterLab) or at the repo root (VS Code).

The notebooks read the same out-of-band raw data as the pipeline, so they need `data_&_docs/` populated and `SAMI_SALT` set — see [Reproducing `exports/`](#reproducing-exports-on-another-machine) above. `run_pipeline.py --check` is the quickest way to confirm both before opening Jupyter.

## Contributing

_Add contribution guidelines here._
