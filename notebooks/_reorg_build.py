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


def src(name, idx, replace=None):
    """A code cell copied from an arxiv notebook, outputs cleared.

    `replace` is an optional list of (old, new) string substitutions applied to
    the cell source (e.g. to reconcile differing column names).
    """
    cell = copy.deepcopy(_load(name)["cells"][idx])
    assert cell["cell_type"] == "code", f"{name}[{idx}] is not code"
    text = "".join(cell["source"])
    for old, new in (replace or []):
        assert old in text, f"replace target not found in {name}[{idx}]: {old!r}"
        text = text.replace(old, new)
    cell["source"] = text.splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None
    cell.setdefault("metadata", {})
    return cell


def md_src(name, idx):
    """A markdown cell copied verbatim from an arxiv notebook."""
    cell = copy.deepcopy(_load(name)["cells"][idx])
    assert cell["cell_type"] == "markdown", f"{name}[{idx}] is not markdown"
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
BLUE_SEQ = BLUES = _CYCLE
EARTH    = _CYCLE
CAT      = _CYCLE
# brand color names -> matplotlib defaults, so cells referencing them still run
AGUA, ARBOL, AMEBA, MADERA, HONGO, NEGRO = (
    _CYCLE[0], _CYCLE[2], _CYCLE[4], _CYCLE[1], "#dddddd", "black")
INK = INK2 = "black"
MUTED = "gray"
GRID  = "#cccccc"
SURFACE = "white"

def cat_colors(n):
    """n distinct matplotlib default colors (categorical)."""
    return [_CYCLE[i % len(_CYCLE)] for i in range(n)]

def bar_colors(n):
    """alias of cat_colors -- n distinct matplotlib default colors."""
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


# ---------------------------------------------------------------------------
# NB2 -- 02_analisis_general_comportamiento_necesidades.ipynb
# ---------------------------------------------------------------------------
def build_nb2():
    ER = "eda_responses.ipynb"
    EM = "eda_meal.ipynb"
    AR = "analysis_responses.ipynb"
    AM = "analysis_meal.ipynb"
    cells = [
        md("# SAMI — Notebook 2 · Comportamiento general y necesidades\n\n"
           "**Todo lo complejo que no es NLP:** cruces de variables, tendencias "
           "temporales, primeras voces cualitativas, necesidades más solicitadas, "
           "profundidad de uso. El notebook operativo — empieza a mostrar fricción.\n\n"
           "*Las categorías de necesidad requieren clasificación (NLP) y viven en el "
           "Notebook 3, junto con el clustering, la comparación con la clasificación "
           "original y el sentimiento.*"),
        md("## Setup"),
        code('''\
# Imports. Collapsed on purpose -- no analysis here.
import sys, warnings
sys.path.insert(0, "../src")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from collections import Counter
from wordcloud import WordCloud

import geopandas as gpd
import contextily as cx
from shapely.geometry import Point
from adjustText import adjust_text

import mmc_data, mmc_entities'''),
        NEUTRAL_STYLE,
        md("### Data\n\n"
           "Two cleaning conventions coexist here. `df` / `meal` come from the EDA "
           "cleaning (rich display columns: `city_display`, `nationality_clean`, "
           "durations, destinations). `msgs` is the message-level spine from "
           "`mmc_data` (one row per user turn)."),
        # EDA-cleaned responses df (city_display, nationality_clean, durations, ...)
        src(ER, 6),
        # EDA-style MEAL (recommendation_text, rating_num, Timestamp)
        src(EM, 5),
        # message spine (message-level)
        code('''\
# Message-level spine: one row per user turn (mmc_data cleaning: city_canon, phone).
_resp = mmc_data.load_responses()
msgs = mmc_data.load_messages(_resp)
print(f"df users: {len(df)}  |  meal: {len(meal)}  |  messages: {len(msgs)}")'''),
        # --- 1. Cross-cuts ---
        md("## 1. Cross-cuts — demographics & geography\n\n"
           "*Patterns that only appear when variables are crossed — invisible to the "
           "univariate EDA.*"),
        md("### 1.1 How settled are users, city by city?"),
        src(ER, 27),
        md("### 1.2 Where are the users? (map)"),
        src(ER, 29),
        src(ER, 30),
        md("### 1.3 Migration routes — origin → destination"),
        src(ER, 36),
        src(ER, 37),
        md("### 1.4 Gender composition by nationality"),
        src(ER, 51),
        md("### 1.5 Engagement by city"),
        src(ER, 53),
        md("### 1.6 Age by intended destination"),
        src(ER, 55),
        # --- 2. Trends over time ---
        md("## 2. Trends over time"),
        md("### 2.1 Daily chatbot usage"),
        src(ER, 47),
        md("### 2.2 MEAL responses over time"),
        src(EM, 20),
        # --- 3. Qualitative voices ---
        md("## 3. Qualitative voices\n\n*The first human break in the notebook — what "
           "users say in their own words.*"),
        md("### 3.1 Word cloud of recommendations"),
        src(EM, 18),
        md("### 3.2 Free-text recommendations (thematic read)\n\n"
           "**What this shows.** What respondents wrote when asked what could be "
           "improved, after filtering out non-answers (e.g. \"no\", \"ninguna\"). "
           "**Why it matters.** Free text is the only place respondents can raise "
           "something the closed-ended questions didn't anticipate.\n\n"
           "> **Technical note — qualitative only.** With few substantive rows, the "
           "free text is read manually below rather than topic-modeled or embedded — "
           "there isn't enough volume for that to be meaningful."),
        src(AM, 11, replace=[('meal["recommendation"]', 'meal["recommendation_text"]')]),
        # --- 4. Most-requested needs ---
        md("## 4. Most-requested needs (message level)\n\n"
           "*Dictionary matching of procedures & institutions — not NLP clustering.*"),
        md("### 4.1 Procedures & institutions mentioned"),
        src(AR, 17),
        md("### 4.2 Messages by city"),
        src(AR, 19),
        # --- 5. Engagement depth ---
        md("## 5. Engagement depth\n\n"
           "*How far users go — the bridge to Notebook 3, where we ask **what** they "
           "asked about and **how** they felt.*"),
        src(AR, 29),
    ]
    write("notebooks/02_analisis_general_comportamiento_necesidades.ipynb", cells)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "nb1"
    if target == "nb1":
        build_nb1()
    elif target == "nb2":
        build_nb2()
