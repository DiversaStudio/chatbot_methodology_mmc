# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## Overview

This repo holds the data analysis work behind the chatbot's evaluation and methodology. The analysis is organized as a **three-part "SAMI" narrative** — three self-contained notebooks that move from *"what data do we have and who is the audience?"* through investigative cross-cuts to automatic NLP theme discovery. Each notebook opens with explicit objectives, guiding questions, and hypotheses, and documents the cleaning steps it applies.

- [`notebooks/01_eda_perfil_y_satisfaccion.ipynb`](notebooks/01_eda_perfil_y_satisfaccion.ipynb) — **Notebook 1 · Input & user profile.** Deliberately descriptive univariate EDA: characterizes the two sources (chatbot *responses* + the *MEAL* survey) — size, completeness, reliability — then profiles the audience (nationality, gender, age, care responsibilities), geography (users per city, a Colombia map), and the migration journey (time away, origin → onward routes on Americas maps).
- [`notebooks/02_analisis_general_comportamiento_necesidades.ipynb`](notebooks/02_analisis_general_comportamiento_necesidades.ipynb) — **Notebook 2 · Behaviour, needs & satisfaction.** Everything investigative that is *not* NLP: variable cross-cuts (gender × nationality, engagement by city, age × destination), usage and MEAL satisfaction over time, the most-requested needs and where/when demand concentrates, needs by the original MMC category, and depth-of-use / abandonment.
- [`notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb`](notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb) — **Notebook 3 · Emergent themes & emotion (NLP).** Discovers the semantic structure of the messages automatically and contrasts it with the official 7-category taxonomy: KMeans over sentence embeddings (primary) and lemmatized TF-IDF (comparison), the cluster-vs-taxonomy agreement, the **emergent themes** the taxonomy misses, PCA-tinted 2D/3D embedding maps, qualitative voices (word cloud + thematic read), per-message **sentiment** as an unsolicited distress signal, and a closing geographic synthesis of need + tone by city. The NLP runs **inline on the GPU** (CUDA; automatic CPU fallback) and is not cached; it downloads the embedding/sentiment models and lemmatizes with spaCy's Spanish `es_core_news_sm` on first run.

Source data lives in [`data_&_docs/`](data_&_docs/) (Excel exports from the chatbot platform and Kobo, plus project documentation). The three notebooks import their shared loaders, cleaning, metrics, and NLP logic from the [`src/sami/`](src/sami/) package (see the export-layer section below for the CSV outputs built on top of it). Earlier, fully self-contained exploratory notebooks are retained for reference in [`notebooks/arxiv/`](notebooks/arxiv/).

## Getting Started

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

```powershell
# Create the virtual environment and install dependencies
uv sync
```

This creates a `.venv` with all dependencies declared in `pyproject.toml` (pandas, numpy, matplotlib, seaborn, missingno, wordcloud, geopandas, osmnx, shapely, cartopy, contextily, openpyxl, python-docx, Jupyter/JupyterLab, spaCy + the Spanish `es_core_news_sm` model, and the sentence-transformers/transformers/BERTopic/UMAP/HDBSCAN stack used for the NLP in notebook 03).

`torch` is pinned to a **CUDA (cu128) GPU build** via `[tool.uv.sources]` so notebook 03 runs its embedding/sentiment models on an NVIDIA GPU; the notebook falls back to CPU automatically if CUDA is unavailable (just slower).

### Alternative: plain pip + venv (no uv, no Anaconda)

If you'd rather not use `uv`, you can install everything with the standard-library `venv` and `pip`. You need **Python 3.11+** already installed.

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate

# 2. Upgrade pip
python -m pip install --upgrade pip

# 3. Install PyTorch. GPU build (CUDA 12.8):
pip install "torch>=2.10" --index-url https://download.pytorch.org/whl/cu128
#    ...or, for a CPU-only machine (slower, no CUDA needed):
#    pip install "torch>=2.10"

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
.venv/Scripts/python.exe run_pipeline.py            # full run incl. GPU NLP -> all tables
.venv/Scripts/python.exe run_pipeline.py --skip-nlp  # fast CPU run -> non-NLP tables only
```

`run_pipeline.py` re-runs the same load/embed/cluster/sentiment pipeline the
notebooks do (GPU by default, automatic CPU fallback), then writes the tables
via `src/sami/export.py`, PII-scanning every frame first and refusing to write
anything if a scan hits. It prints a `parity_check` reconciliation and exits
non-zero if any metric fails to match, so a bad export never gets committed
silently.

**Tone is directional-only.** The sentiment model's agreement with the human
gold labels (κ=0.604) falls below the 0.7 quotability gate, so `meta_run`
carries `tone_gate_passed=false` / `sentiment_quotable=false`. Sentiment
signal ships in the exports but must be read as directional, never as a
published percentage.

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

Run the notebooks in order (01 → 02 → 03) from the `notebooks/` directory. They import shared loaders and analysis logic from [`src/sami/`](src/sami/), so run them with the project's `.venv` (via `uv sync`, above) rather than a bare Python environment.

## Contributing

_Add contribution guidelines here._
