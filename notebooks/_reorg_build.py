"""Throwaway assembly helper for the 4->3 notebook reorganization.

Builds new notebooks from cells of the arxiv sources: pulls chosen cells,
clears outputs, and assembles a fresh self-contained notebook. Deleted at the
end of the reorg.
"""
import json, copy, sys

ARXIV = "notebooks/arxiv/"
_cache = {}


def _load(name):
    if name not in _cache:
        with open(ARXIV + name, encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def src(name, idx):
    """A code cell copied verbatim from an arxiv notebook, outputs cleared."""
    cell = copy.deepcopy(_load(name)["cells"][idx])
    assert cell["cell_type"] == "code", f"{name}[{idx}] is not code"
    cell["outputs"] = []
    cell["execution_count"] = None
    cell.setdefault("metadata", {})
    return cell


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": text.rstrip("\n").splitlines(keepends=True)}


def md(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.rstrip("\n").splitlines(keepends=True)}


# Neutral styling placeholder: exposes the old palette names bound to genuine
# matplotlib defaults, so moved cells run unchanged. Replace this cell with the
# real brand palette later.
NEUTRAL_STYLE = code('''\
# Temporary neutral styling -- brand palette removed; matplotlib defaults for now.
# These names shadow the old palette so moved cells run unchanged. Re-add the
# real palette later by replacing THIS cell (nothing else references the brand).
_CYCLE = plt.rcParams["axes.prop_cycle"].by_key()["color"]   # matplotlib defaults
PRIMARY = _CYCLE[0]
BLUE_SEQ = _CYCLE
EARTH    = _CYCLE
CAT      = _CYCLE
INK = INK2 = "black"
MUTED = "gray"
GRID  = "#cccccc"
SURFACE = "white"

def cat_colors(n):
    """n distinct matplotlib default colors (categorical)."""
    return [_CYCLE[i % len(_CYCLE)] for i in range(n)]

def seq_colors(n):
    """single default color repeated (ordered magnitude -- one hue for now)."""
    return [_CYCLE[0]] * n

def pct_count_autopct(values, min_pct=3.0):
    """Pie label 'xx.x%\\n(n)'; blank under min_pct. Label formatter, not color."""
    total = float(sum(values))
    def _fmt(pct):
        if pct < min_pct:
            return ""
        return f"{pct:.1f}%\\n({int(round(pct/100*total))})"
    return _fmt
''')


def write(path, cells):
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f"wrote {path}  ({len(cells)} cells)")


# ---------------------------------------------------------------------------
# NB1 -- 01_eda_perfil_y_satisfaccion.ipynb
# ---------------------------------------------------------------------------
def build_nb1():
    ER = "eda_responses.ipynb"
    EM = "eda_meal.ipynb"
    cells = [
        md("# SAMI — Notebook 1 · Perfil de usuarios y línea base de satisfacción\n\n"
           "**EDA puro — solo \"qué datos tenemos\".** Distribuciones univariadas: una "
           "variable a la vez, sin cruces, sin eje temporal, sin lectura temática, sin "
           "mapas. Frío y factual.\n\n"
           "Fuentes: log de interacciones del chatbot (respuestas) y formulario MEAL."),
        md("## Setup"),
        code('''\
# Imports. Collapsed on purpose -- no analysis here.
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde'''),
        NEUTRAL_STYLE,
        # --- Responses ---
        md("## 1. Data Load — Responses"),
        src(ER, 6),
        code("df.head(3)"),
        md("## 2. Data Quality — Responses"),
        src(ER, 10),
        src(ER, 11),
        md("## 3. Demographics"),
        md("### 3.1 Nationality"),
        src(ER, 15),
        md("### 3.2 Gender"),
        src(ER, 17),
        md("### 3.3 Age"),
        src(ER, 19),
        src(ER, 20),
        md("### 3.4 Care responsibilities"),
        src(ER, 22),
        md("## 4. Geography"),
        md("### 4.1 Cities — users per city\n\n"
           "*Only the simple user count per top city. Antiquity-by-city and the map "
           "are bivariate/spatial and live in Notebook 2.*"),
        src(ER, 26),
        md("## 5. Migration routes"),
        md("### 5.1 Time away from country of origin"),
        src(ER, 34),
        md("## 6. Chatbot engagement"),
        md("### 6.1 Topics discussed — simple frequency"),
        src(ER, 41),
        md("### 6.2 Questions per user"),
        src(ER, 43),
        md("### 6.3 Survey sent"),
        src(ER, 45),
        # --- MEAL ---
        md("## 7. MEAL Feedback — Data Load & Quality"),
        src(EM, 5),
        src(EM, 7),
        md("## 8. Satisfaction baseline\n\n"
           "*Simple counts only — no trend, no qualitative reading. Response rate is "
           "low, so read these as indicative, not representative.*"),
        md("### 8.1 Usefulness rating"),
        src(EM, 9),
        md("### 8.2 Would recommend"),
        src(EM, 11),
        md("### 8.3 Discovery channel"),
        src(EM, 13),
        md("### 8.4 Length of recommendations\n\n*How much users write — not what they say.*"),
        src(EM, 16),
    ]
    write("notebooks/01_eda_perfil_y_satisfaccion.ipynb", cells)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "nb1"
    if target == "nb1":
        build_nb1()
