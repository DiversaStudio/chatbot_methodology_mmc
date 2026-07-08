# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## Overview

This repo holds the data analysis work behind the chatbot's evaluation and methodology. The work proceeds in two stages: exploratory data analysis (EDA), followed by deeper advanced analysis built on top of it.

**EDA notebooks** clean and characterize the raw survey/response data so later stages (e.g. indicator design, reporting, infographics) can build on a well-understood, documented dataset. Each notebook section states which questions about the data it answers, and documents the cleaning steps applied.

- [`notebooks/eda_responses.ipynb`](notebooks/eda_responses.ipynb) — EDA of the chatbot **interaction responses** dataset (demographics, geography, migration routes, engagement, and cross-cuts).
- [`notebooks/eda_meal.ipynb`](notebooks/eda_meal.ipynb) — EDA of the **MEAL (Monitoring, Evaluation, Accountability & Learning)** dataset.

**Analysis notebooks** build on the cleaned EDA data to answer more targeted methodology questions, using shared, tested code in [`src/`](src/) (`mmc_data`, `mmc_entities`, `mmc_text`).

- [`notebooks/analysis_responses.ipynb`](notebooks/analysis_responses.ipynb) — advanced **message-level** analysis of the **interaction responses** dataset. The `Messages` field is exploded into one row per user turn (~3k messages), and each message is embedded (`multilingual-e5-large`) and clustered (UMAP → HDBSCAN). Each cluster is "tinted" with an MMC category by the consensus of the bot's `Chat_summary` labels, and clusters without a clear consensus are surfaced as **emergent / cross-cutting** themes. It then cross-cuts message topics with needs/entities, geography (city maps), time, demographics, engagement, drop-off & reformulation, **sentiment + 7-class emotion**, and MEAL satisfaction, closing with data-gap limitations. The NLP runs **inline on the GPU** (CUDA; CPU fallback) and is not cached — the whole pass takes a couple of minutes. Downloads the embedding/zero-shot/sentiment/emotion models on first run.
- [`notebooks/analysis_meal.ipynb`](notebooks/analysis_meal.ipynb) — descriptive analysis of MEAL **satisfaction** data: utility rating, would-recommend, how respondents heard about the chatbot, and a thematic read of free-text recommendations.

Source data lives in [`data_&_docs/`](data_&_docs/) (Excel exports from the chatbot platform and Kobo, plus project documentation). Shared plotting utilities (the Diversa brand color palette) live in [`src/palette.py`](src/palette.py).

## Getting Started

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

```powershell
# Create the virtual environment and install dependencies
uv sync
```

This creates a `.venv` with all dependencies declared in `pyproject.toml` (pandas, numpy, matplotlib, seaborn, missingno, wordcloud, geopandas, osmnx, shapely, openpyxl, python-docx, Jupyter/JupyterLab, and the sentence-transformers/transformers/UMAP/HDBSCAN stack used for the message-level NLP in `analysis_responses.ipynb`).

`torch` is pinned to a **CUDA (cu128) GPU build** via `[tool.uv.sources]` so `analysis_responses.ipynb` runs its embedding/classification/emotion models on an NVIDIA GPU; the notebook falls back to CPU automatically if CUDA is unavailable (just slower).

## Usage

Run the notebooks with the project's environment, e.g. from VS Code (select the `.venv` kernel) or from the command line:

```powershell
uv run jupyter lab
```

Notebooks expect to be run from the `notebooks/` directory (they add `../src` to `sys.path` to import `palette.py`).

## Contributing

_Add contribution guidelines here._
