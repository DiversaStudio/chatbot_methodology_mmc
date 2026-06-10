# chatbot_methodology_mmc

Methodology, exploratory data analysis (EDA), and supporting code for the Mixed Migration Centre (MMC) WhatsApp chatbot for migrants in Colombia.

## Overview

This repo holds the data analysis work behind the chatbot's evaluation and methodology. The current stage is exploratory data analysis (EDA) of the chatbot's pilot data:

- [`notebooks/eda_responses.ipynb`](notebooks/eda_responses.ipynb) — EDA of the chatbot **interaction responses** dataset (demographics, geography, migration routes, engagement, and cross-cuts).
- [`notebooks/eda_meal.ipynb`](notebooks/eda_meal.ipynb) — EDA of the **MEAL (Monitoring, Evaluation, Accountability & Learning)** dataset.

These EDA notebooks are the first stage of the methodology: they clean and characterize the raw survey/response data so later stages (e.g. indicator design, reporting, infographics) can build on a well-understood, documented dataset. Each notebook section states which questions about the data it answers, and documents the cleaning steps applied.

Source data lives in [`data_&_docs/`](data_&_docs/) (Excel exports from the chatbot platform and Kobo, plus project documentation). Shared plotting utilities (the Diversa brand color palette) live in [`src/palette.py`](src/palette.py).

## Getting Started

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

```powershell
# Create the virtual environment and install dependencies
uv sync
```

This creates a `.venv` with all dependencies declared in `pyproject.toml` (pandas, numpy, matplotlib, seaborn, missingno, wordcloud, geopandas, osmnx, shapely, openpyxl, python-docx, and Jupyter/JupyterLab).

## Usage

Run the notebooks with the project's environment, e.g. from VS Code (select the `.venv` kernel) or from the command line:

```powershell
uv run jupyter lab
```

Notebooks expect to be run from the `notebooks/` directory (they add `../src` to `sys.path` to import `palette.py`).

## Contributing

_Add contribution guidelines here._
