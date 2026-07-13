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


# ---------------------------------------------------------------------------
# NB3 -- 03_nlp_clustering_usuario_y_sentimiento.ipynb
# ---------------------------------------------------------------------------
def build_nb3():
    AR = "analysis_responses.ipynb"
    cells = [
        md("# SAMI — Notebook 3 · Clustering de usuarios, clasificación y sentimiento\n\n"
           "**NLP simplificado a nivel usuario.** KMeans sobre embeddings de oraciones "
           "(primario) y TF-IDF de texto lematizado (comparación); contraste contra la "
           "**clasificación original** de la base (Chat_summary → 7 categorías MMC); "
           "sentimiento como señal de malestar; y el **mapa síntesis** de necesidad + "
           "tono por ciudad como cierre de todo el análisis.\n\n"
           "*Se abandonaron los métodos más pesados del pipeline anterior (UMAP/HDBSCAN, "
           "zero-shot tinting, temas emergentes, reformulación por embeddings, emoción de "
           "7 clases).*"),
        md("## 0. Setup, data & original classification"),
        code('''\
# Imports. Collapsed on purpose -- no analysis here.
import sys, warnings
sys.path.insert(0, "../src")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch

import mmc_data

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
GPU = 0 if DEVICE == "cuda" else -1'''),
        NEUTRAL_STYLE,
        # MMC labels + CAT_COLORS + cat_palette + NON_TOPIC_CATS
        src(AR, 2, replace=[
            ("the hypotheses fed to the Spanish zero-shot\n# classifier.",
             "aligned with the bot's original Chat_summary labels."),
            ("collapsed the\n# classifier onto one or two categories. "
             "Edit the wording to steer the classifier.",
             "collapsed onto one or two categories."),
        ]),
        code('''\
df   = mmc_data.load_responses()          # one row per user (has Chat_summary)
meal = mmc_data.load_meal()               # MEAL survey (satisfaction)
msgs = mmc_data.load_messages(df)         # one row per user message (the spine)
print(f"users: {len(df)}  |  messages: {len(msgs)}  |  device: {DEVICE}"
      + (f" ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else ""))'''),
        md("### 0.1 Original classification (from the bot's `Chat_summary`)\n\n"
           "The bot already tags each user with a `Chat_summary` of MMC categories — "
           "the database's **original classification**. We map it to the 7 canonical "
           "categories and attach one dominant category per user (broadcast to their "
           "messages). This is the ground truth the KMeans clusters are checked against "
           "later. *Per-message nuance is lost — every message of a user shares that "
           "user's dominant category.*"),
        code('''\
TOPIC_MAP_LC = {
    "legal documentation":     "legal documentation",
    "humanitarian assistance": "humanitarian assistance",
    "employment":              "employment",
    "services":                "services",
    "protection":              "protection",
    "organization search":     "organization search",
    "journey information":     "journey information",
}
UNCLASSIFIED = "unclassified"

def _user_category(summary):
    """Dominant canonical MMC category from a user's Chat_summary free text."""
    if not isinstance(summary, str) or "Use exactly one of these hashtags" in summary:
        return UNCLASSIFIED
    cats = []
    for t in summary.replace("''", ",").split(","):
        t = t.strip().lstrip("#").replace("_", " ").lower()
        if t in TOPIC_MAP_LC:
            cats.append(TOPIC_MAP_LC[t])
    if not cats:
        return UNCLASSIFIED
    return pd.Series(cats).value_counts().index[0]

df["mmc_category"] = df["Chat_summary"].map(_user_category)
_cat_by_phone = df.set_index("phone")["mmc_category"]
msgs["mmc_category"] = msgs["phone"].map(_cat_by_phone).fillna(UNCLASSIFIED)

CAT_COLORS[UNCLASSIFIED] = "#cfcfcf"
NON_TOPIC_CATS = NON_TOPIC_CATS + [UNCLASSIFIED]
print(msgs["mmc_category"].value_counts())'''),
        # ---- 1. Descriptive category slices (moved from NB2) ----
        md("## 1. What users need — by the original classification\n\n"
           "*Descriptive slices of the DB's own categories. The interpretable, named "
           "view of demand, before we ask whether unsupervised clustering recovers it.*"),
        md("### 1.1 Category mix by city"),
        code('''\
# top cities by message volume (needed by the category-mix chart below)
top_cities = msgs.loc[msgs["city_canon"] != "Otra", "city_canon"].value_counts().head(10)'''),
        src(AR, 20),
        md("### 1.2 Categories over time"),
        src(AR, 22),
        src(AR, 23),
        md("### 1.3 Category by demographics"),
        src(AR, 25),
        src(AR, 26),
        src(AR, 27),
        md("### 1.4 Where users drop off, by category"),
        src(AR, 31),
        md("### 1.5 Satisfaction (MEAL) × category\n\n"
           "**What this shows.** MEAL utility ratings joined to the category each user "
           "mostly asked about. **Why it matters.** It flags which needs produce the "
           "worst experience.\n\n"
           "> **Technical note — small overlap.** Only users who completed the MEAL "
           "survey appear (dozens). Each user is assigned their dominant message "
           "category, joined on WhatsApp phone number. Read proportions as directional."),
        src(AR, 37),
        # ---- 2. User-level clustering ----
        md("## 2. User-level clustering\n\n"
           "*One document per user (all their messages concatenated). Cluster **users**, "
           "not messages. Primary features: sentence embeddings. Comparison: TF-IDF of "
           "lemmatized text.*"),
        md("### 2.1 User documents & lemmatization"),
        code('''\
# One document per user = all their messages concatenated. Lemmatize (spaCy es)
# for the TF-IDF comparison; the embeddings use the raw text.
import spacy
try:
    nlp = spacy.load("es_core_news_sm", disable=["ner", "parser"])
except OSError:
    from spacy.cli import download as _sp_dl
    _sp_dl("es_core_news_sm")
    nlp = spacy.load("es_core_news_sm", disable=["ner", "parser"])

user_docs = (msgs.groupby("phone")["message"]
             .apply(lambda s: " ".join(s.astype(str))).rename("doc").reset_index())
user_docs["category"] = user_docs["phone"].map(_cat_by_phone).fillna(UNCLASSIFIED)

def _lemmatize(text):
    return " ".join(tok.lemma_.lower() for tok in nlp(text)
                    if tok.is_alpha and not tok.is_stop and len(tok) > 2)

user_docs["lemmas"] = [_lemmatize(t) for t in user_docs["doc"]]
print(f"{len(user_docs)} user documents")
user_docs.head(3)'''),
        md("### 2.2 KMeans on sentence embeddings (primary)"),
        code('''\
# Primary features: multilingual-e5-large embeddings of each user document.
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

_embedder = SentenceTransformer("intfloat/multilingual-e5-large", device=DEVICE)
if DEVICE == "cuda":
    _embedder = _embedder.half()
emb = _embedder.encode(["query: " + d for d in user_docs["doc"]],
                       batch_size=16, normalize_embeddings=True, show_progress_bar=False)
emb = np.asarray(emb, dtype="float32")
del _embedder
if DEVICE == "cuda":
    torch.cuda.empty_cache()

K = 7   # match the 7 official MMC categories
km_emb = KMeans(n_clusters=K, random_state=42, n_init=10).fit(emb)
user_docs["cluster_emb"] = km_emb.labels_
print("embeddings:", emb.shape)
print(user_docs["cluster_emb"].value_counts().sort_index().to_string())'''),
        md("### 2.3 Comparison — KMeans on TF-IDF of lemmatized text"),
        code('''\
# A lighter, fully interpretable comparison: TF-IDF over lemmatized user docs.
from sklearn.feature_extraction.text import TfidfVectorizer

tfidf = TfidfVectorizer(max_features=2000, min_df=2)
X_tfidf = tfidf.fit_transform(user_docs["lemmas"])
km_tfidf = KMeans(n_clusters=K, random_state=42, n_init=10).fit(X_tfidf)
user_docs["cluster_tfidf"] = km_tfidf.labels_
print("tfidf matrix:", X_tfidf.shape)
print(user_docs["cluster_tfidf"].value_counts().sort_index().to_string())'''),
        # ---- 3. Agreement ----
        md("## 3. Do the clusters match the original classification?\n\n"
           "*How well does unsupervised clustering recover the 7 categories the bot "
           "already assigned? ARI / NMI / purity, plus a confusion heatmap.*"),
        code('''\
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

def _purity(clusters, labels):
    ct = pd.crosstab(clusters, labels)
    return ct.max(axis=1).sum() / ct.values.sum()

known = user_docs["category"] != UNCLASSIFIED
truth = user_docs.loc[known, "category"]
rows = []
for name, col in [("embeddings", "cluster_emb"), ("TF-IDF", "cluster_tfidf")]:
    cl = user_docs.loc[known, col]
    rows.append({"features": name,
                 "ARI": adjusted_rand_score(truth, cl),
                 "NMI": normalized_mutual_info_score(truth, cl),
                 "purity": _purity(cl, truth)})
agreement = pd.DataFrame(rows).set_index("features").round(3)
print(f"users with a known original category: {int(known.sum())} / {len(user_docs)}")
agreement'''),
        code('''\
# Which original category dominates each embedding cluster? (row-normalized)
conf = pd.crosstab(user_docs.loc[known, "cluster_emb"],
                   user_docs.loc[known, "category"], normalize="index")
fig, ax = plt.subplots(figsize=(10, 5))
sns.heatmap(conf, annot=True, fmt=".0%", cmap="Blues", ax=ax, cbar_kws={"label": "share"})
ax.set_title("Embedding clusters vs original category (row-normalized)")
ax.set_xlabel("original category"); ax.set_ylabel("KMeans cluster")
plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
plt.tight_layout()'''),
        # ---- 4. Sentiment ----
        md("## 4. Sentiment — an unsolicited distress signal\n\n"
           "*3-class sentiment on every message (not just the few MEAL respondents). "
           "The 7-class emotion model from the old pipeline is dropped.*"),
        code('''\
# 3-class sentiment per message.
from transformers import pipeline

texts = msgs["message"].astype(str).tolist()
sent_clf = pipeline("sentiment-analysis",
                    model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                    device=GPU, truncation=True, max_length=256)

def _norm_sent(label):
    l = label.lower()
    if "neg" in l or l.endswith("0"):
        return "negative"
    if "pos" in l or l.endswith("2"):
        return "positive"
    return "neutral"

preds = sent_clf([t[:256] for t in texts], batch_size=32)
msgs["sentiment"] = [_norm_sent(p["label"]) for p in preds]
del sent_clf
if DEVICE == "cuda":
    torch.cuda.empty_cache()

SENT_ORDER = ["negative", "neutral", "positive"]
SENT_COLORS = {"negative": "#c9788f", "neutral": HONGO, "positive": AGUA}
fig, ax = plt.subplots(figsize=(7, 3.2))
sd = msgs["sentiment"].value_counts().reindex(SENT_ORDER)
ax.barh(SENT_ORDER, sd.values, color=[SENT_COLORS[s] for s in SENT_ORDER],
        edgecolor=NEGRO, lw=.5)
ax.set_title("Message sentiment"); ax.set_xlabel("messages")
plt.tight_layout()
print("sentiment:", dict(sd), f"|  negative share: {sd['negative']/sd.sum()*100:.1f}%")'''),
        md("### 4.1 Sentiment by category"),
        code('''\
# Which needs arrive with the most negative tone?
cats6 = (msgs[~msgs["mmc_category"].isin(NON_TOPIC_CATS)]["mmc_category"]
         .value_counts().head(6).index)
sub = msgs[msgs["mmc_category"].isin(cats6)]
tabS = (pd.crosstab(sub["mmc_category"], sub["sentiment"], normalize="index")
        .reindex(index=cats6, columns=SENT_ORDER, fill_value=0))
tabS.plot(kind="barh", stacked=True, figsize=(10, 5),
          color=[SENT_COLORS[s] for s in SENT_ORDER])
plt.title("Sentiment mix by category (share of messages)")
plt.xlabel("share"); plt.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
plt.tight_layout()'''),
        # ---- 5. Synthesis map ----
        md("## 5. Geographic synthesis — need + tone by city\n\n"
           "**The closer of the whole analysis (EDA + General + NLP).** Colombia with, "
           "per city, its **dominant need** (MMC category) and the **average tone** of "
           "its messages — where a need concentrates and where people write in with the "
           "most negative tone, to target field response.\n\n"
           "> **Technical note.** One bubble per city (size = messages), positioned from "
           "a curated coordinate table; only cities with ≥ 15 mapped messages are shown. "
           "Sentiment is the mean per-message polarity (−1 / 0 / +1); category is the "
           "most common per city. A light CartoDB Positron basemap grounds the bubbles."),
        src(AR, 39),
        src(AR, 40),
        src(AR, 41),
    ]
    write("notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb", cells)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "nb1"
    if target == "nb1":
        build_nb1()
    elif target == "nb2":
        build_nb2()
    elif target == "nb3":
        build_nb3()
