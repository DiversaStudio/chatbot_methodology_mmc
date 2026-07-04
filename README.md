# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## Overview

This repo holds the data analysis work behind the chatbot's evaluation and methodology. The work proceeds in two stages: exploratory data analysis (EDA), followed by deeper advanced analysis built on top of it.

**EDA notebooks** clean and characterize the raw survey/response data so later stages (e.g. indicator design, reporting, infographics) can build on a well-understood, documented dataset. Each notebook section states which questions about the data it answers, and documents the cleaning steps applied.

- [`notebooks/eda_responses.ipynb`](notebooks/eda_responses.ipynb) — EDA of the chatbot **interaction responses** dataset (demographics, geography, migration routes, engagement, and cross-cuts).
- [`notebooks/eda_meal.ipynb`](notebooks/eda_meal.ipynb) — EDA of the **MEAL (Monitoring, Evaluation, Accountability & Learning)** dataset.

**Analysis notebooks** build on the cleaned EDA data to answer more targeted methodology questions, using shared, tested code in [`src/`](src/) (`mmc_data`, `mmc_entities`, `mmc_text`).

- [`notebooks/analysis_responses.ipynb`](notebooks/analysis_responses.ipynb) — advanced analysis of the **interaction responses** dataset: topic modeling & clustering (BERTopic), mixed coding against the MMC taxonomy, most-requested needs, geographic/temporal/demographic cross-cuts, engagement depth, reformulated-question detection, satisfaction-by-topic, and data-gap limitations. Requires the BERTopic/sentence-transformers stack and downloads a sentence-embedding model on first run.
- [`notebooks/analysis_meal.ipynb`](notebooks/analysis_meal.ipynb) — descriptive analysis of MEAL **satisfaction** data: utility rating, would-recommend, how respondents heard about the chatbot, and a thematic read of free-text recommendations.

Source data lives in [`data_&_docs/`](data_&_docs/) (Excel exports from the chatbot platform and Kobo, plus project documentation). Shared plotting utilities (the Diversa brand color palette) live in [`src/palette.py`](src/palette.py).

## Getting Started

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

```powershell
# Create the virtual environment and install dependencies
uv sync
```

This creates a `.venv` with all dependencies declared in `pyproject.toml` (pandas, numpy, matplotlib, seaborn, missingno, wordcloud, geopandas, osmnx, shapely, openpyxl, python-docx, Jupyter/JupyterLab, and the BERTopic/sentence-transformers/UMAP/HDBSCAN stack used for topic modeling in `analysis_responses.ipynb`).

## Usage

Run the notebooks with the project's environment, e.g. from VS Code (select the `.venv` kernel) or from the command line:

```powershell
uv run jupyter lab
```

Notebooks expect to be run from the `notebooks/` directory (they add `../src` to `sys.path` to import `palette.py`).

## Contributing

_Add contribution guidelines here._
