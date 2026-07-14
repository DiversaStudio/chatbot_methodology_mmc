# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## Overview

This repo holds the data analysis work behind the chatbot's evaluation and methodology. The analysis is organized as a **three-part "SAMI" narrative** — three self-contained notebooks that move from *"what data do we have and who is the audience?"* through investigative cross-cuts to automatic NLP theme discovery. Each notebook opens with explicit objectives, guiding questions, and hypotheses, and documents the cleaning steps it applies.

- [`notebooks/01_eda_perfil_y_satisfaccion.ipynb`](notebooks/01_eda_perfil_y_satisfaccion.ipynb) — **Notebook 1 · Input & user profile.** Deliberately descriptive univariate EDA: characterizes the two sources (chatbot *responses* + the *MEAL* survey) — size, completeness, reliability — then profiles the audience (nationality, gender, age, care responsibilities), geography (users per city, a Colombia map), and the migration journey (time away, origin → onward routes on Americas maps).
- [`notebooks/02_analisis_general_comportamiento_necesidades.ipynb`](notebooks/02_analisis_general_comportamiento_necesidades.ipynb) — **Notebook 2 · Behaviour, needs & satisfaction.** Everything investigative that is *not* NLP: variable cross-cuts (gender × nationality, engagement by city, age × destination), usage and MEAL satisfaction over time, the most-requested needs and where/when demand concentrates, needs by the original MMC category, and depth-of-use / abandonment.
- [`notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb`](notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb) — **Notebook 3 · Emergent themes & emotion (NLP).** Discovers the semantic structure of the messages automatically and contrasts it with the official 7-category taxonomy: KMeans over sentence embeddings (primary) and lemmatized TF-IDF (comparison), the cluster-vs-taxonomy agreement, the **emergent themes** the taxonomy misses, PCA-tinted 2D/3D embedding maps, qualitative voices (word cloud + thematic read), per-message **sentiment** as an unsolicited distress signal, and a closing geographic synthesis of need + tone by city. The NLP runs **inline on the GPU** (CUDA; automatic CPU fallback) and is not cached; it downloads the embedding/sentiment models and lemmatizes with spaCy's Spanish `es_core_news_sm` on first run.

Source data lives in [`data_&_docs/`](data_&_docs/) (Excel exports from the chatbot platform and Kobo, plus project documentation). The three notebooks are **self-contained** — each inlines its own loaders and brand palette and does not import from [`src/`](src/). The `src/` modules (`mmc_data`, `mmc_entities`, `mmc_text`, `palette`) and the earlier exploratory notebooks in [`notebooks/arxiv/`](notebooks/arxiv/) are retained for reference.

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

Run the notebooks in order (01 → 02 → 03) from the `notebooks/` directory. Each is self-contained — it inlines its own data loaders and brand palette, so no `src/` import or path setup is required.

## Contributing

_Add contribution guidelines here._
