# MMC Analysis Notebooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two new Jupyter notebooks — `analysis_responses.ipynb` (topic modeling + cross-cuts over 946 chatbot users) and `analysis_meal.ipynb` (satisfaction descriptives over 78 MEAL responses) — backed by unit-tested `src/` helper modules.

**Architecture:** Reusable, deterministic logic (data loading/cleaning, entity extraction, message-splitting, reformulation similarity) lives in unit-tested `src/` modules. The notebooks are thin narrative orchestration that import those helpers, run BERTopic, and render charts with the shared blue palette. Notebooks are validated by executing them end-to-end with `nbconvert`.

**Tech Stack:** pandas, numpy, matplotlib/seaborn, geopandas (existing); BERTopic + sentence-transformers + umap-learn + hdbscan (new); pytest + nbconvert for validation.

## Global Constraints

- Python `>=3.11`; use `uv` only (`uv add`, `uv pip install`) — never pip/venv/pyenv directly.
- `tool.uv.package = false` and `python-preference = "only-system"`, `python-downloads = "never"` must remain in `pyproject.toml` (do not remove).
- All Python commands run through the project venv: `.venv/Scripts/python.exe` (Windows).
- Notebooks import shared style via `sys.path.insert(0, '../src')` then `from palette import *`.
- Every notebook chart uses **only** the `src/palette.py` blue ramp (`BLUES`, `bar_colors(n)`); black text, white background.
- Dual-audience narrative: each section opens with a markdown **What this shows / Why it matters**; non-obvious choices get a **Technical note**.
- Do NOT modify `notebooks/eda_responses.ipynb` or `notebooks/eda_meal.ipynb`.
- Data files (header on the 3rd row, keep rows where `Name` starts with `whatsapp`):
  - `data_&_docs/MMC_bot_responses_Grupo_nuevo_1783087815.xlsx`
  - `data_&_docs/MMC_MEAL_Group_Title_1783087939.xlsx`
- Join key between datasets: `Name` (`whatsapp:+<number>`).
- Out of scope (document, do not attempt): fallback/no-response rate, response consistency, true turn-level drop-off — no bot-output/turn data exists.

---

## File Structure

- Create `src/mmc_data.py` — loaders + cleaning for both datasets.
- Create `src/mmc_entities.py` — trámite/institution dictionary + extraction.
- Create `src/mmc_text.py` — message splitting + reformulation similarity helpers.
- Create `tests/test_mmc_data.py`, `tests/test_mmc_entities.py`, `tests/test_mmc_text.py`.
- Create `notebooks/analysis_responses.ipynb`, `notebooks/analysis_meal.ipynb`.
- Modify `pyproject.toml` — add analysis + dev dependencies.
- Modify `README.md` — list the two new notebooks.

Notebook cells are added with the **NotebookEdit** tool. Validate a notebook by running:
`.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/<nb>.ipynb`
and confirming it exits 0 with no error outputs.

---

### Task 1: Dependencies + de-risk the BERTopic/torch stack

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: a venv where `import bertopic`, `import sentence_transformers`, `import torch`, `import pytest` all succeed, and a multilingual model can embed text.

- [ ] **Step 1: Add analysis dependencies via uv**

```bash
cd "c:/Users/sedig/Desktop/DIVERSA/chatbot_methodology_mmc"
uv add bertopic sentence-transformers umap-learn hdbscan
uv add --dev pytest
```

- [ ] **Step 2: Confirm `pyproject.toml` still has the guard rails**

Read `pyproject.toml` and verify `[tool.uv]` still contains `package = false`, `python-preference = "only-system"`, `python-downloads = "never"`. If `uv add` removed them, restore them verbatim.

- [ ] **Step 3: Verify imports resolve**

Run:
```bash
.venv/Scripts/python.exe -c "import torch, sentence_transformers, bertopic, umap, hdbscan, pytest; print('all import OK')"
```
Expected: `all import OK` (no traceback). If `torch` fails to install on Windows under uv, fall back to `uv pip install torch --index-url https://download.pytorch.org/whl/cpu` and re-run.

- [ ] **Step 4: Smoke-test a real embedding + tiny BERTopic run**

Run:
```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
v = m.encode(['necesito el PPT','ayuda humanitaria','como saco la cita de migracion'])
print('embed shape', v.shape)
"
```
Expected: downloads the model once, prints `embed shape (3, 384)`. This confirms internet + model works before any notebook depends on it.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add BERTopic/sentence-transformers + pytest dependencies"
```

---

### Task 2: `src/mmc_data.py` — dataset loaders & cleaning

**Files:**
- Create: `src/mmc_data.py`
- Test: `tests/test_mmc_data.py`

**Interfaces:**
- Produces:
  - `load_responses(path: str | Path = RESPONSES_PATH) -> pd.DataFrame` — parsed, `whatsapp:`-filtered, with added columns `phone` (digits only), `city_clean` (str), `age_num` (float), `ts` (datetime64, UTC-naive), `n_questions` (float from `Questions per user`).
  - `load_meal(path: str | Path = MEAL_PATH) -> pd.DataFrame` — parsed, `whatsapp:`-filtered, with `phone` and renamed columns `utility`, `would_recommend`, `recommendation`, `heard_channel`, `heard_medium`, `ts`.
  - `clean_city(raw_city: str, city_other: str | None) -> str` — returns `city_other` (title-cased, trimmed) when `raw_city == 'Otra'` and `city_other` is present, else the trimmed `raw_city`.
  - Module constants `RESPONSES_PATH`, `MEAL_PATH` (relative to repo root), `DATA_HEADER_ROW = 2`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mmc_data.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
import mmc_data as d

def test_clean_city_uses_other_when_otra():
    assert d.clean_city("Otra", " bogota ") == "Bogota"

def test_clean_city_keeps_named_city():
    assert d.clean_city("Medellín", None) == "Medellín"

def test_clean_city_otra_without_other_returns_otra():
    assert d.clean_city("Otra", None) == "Otra"

def test_load_responses_shape_and_columns():
    df = d.load_responses()
    assert len(df) == 946
    for col in ["phone", "city_clean", "age_num", "ts", "n_questions"]:
        assert col in df.columns
    assert df["phone"].str.fullmatch(r"\d+").all()
    assert df["ts"].notna().mean() > 0.9

def test_load_meal_renamed_columns():
    m = d.load_meal()
    assert len(m) == 78
    for col in ["phone", "utility", "would_recommend", "recommendation", "heard_channel"]:
        assert col in m.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mmc_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mmc_data'`.

- [ ] **Step 3: Implement `src/mmc_data.py`**

```python
"""Loaders and cleaning for the MMC monday.com exports."""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = _ROOT / "data_&_docs"
RESPONSES_PATH = DATA_DIR / "MMC_bot_responses_Grupo_nuevo_1783087815.xlsx"
MEAL_PATH = DATA_DIR / "MMC_MEAL_Group_Title_1783087939.xlsx"
DATA_HEADER_ROW = 2  # 0-indexed; header is the 3rd row of the export


def _phone(name: str) -> str:
    return re.sub(r"\D", "", str(name))


def clean_city(raw_city, city_other) -> str:
    raw = ("" if raw_city is None else str(raw_city)).strip()
    other = "" if city_other is None or pd.isna(city_other) else str(city_other).strip()
    if raw == "Otra" and other:
        return other.title()
    return raw


def _read_whatsapp(path) -> pd.DataFrame:
    df = pd.read_excel(path, header=DATA_HEADER_ROW)
    df = df[df["Name"].astype(str).str.startswith("whatsapp")].copy()
    df.reset_index(drop=True, inplace=True)
    return df


def load_responses(path=RESPONSES_PATH) -> pd.DataFrame:
    df = _read_whatsapp(path)
    df["phone"] = df["Name"].map(_phone)
    df["city_clean"] = [clean_city(c, o) for c, o in zip(df["City"], df["City_other"])]
    df["age_num"] = pd.to_numeric(df["Age"], errors="coerce")
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    df["n_questions"] = pd.to_numeric(df["Questions per user"], errors="coerce")
    return df


def load_meal(path=MEAL_PATH) -> pd.DataFrame:
    df = _read_whatsapp(path)
    df["phone"] = df["Name"].map(_phone)
    cols = list(df.columns)
    rename = {
        cols[2]: "utility",
        cols[3]: "would_recommend",
        cols[4]: "recommendation",
        cols[5]: "heard_channel",
        cols[6]: "heard_medium",
    }
    df = df.rename(columns=rename)
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mmc_data.py -v`
Expected: 5 passed. (If MEAL column positions differ, adjust the `rename` index map to match `load_meal`'s actual header order printed by a quick `df.columns` check.)

- [ ] **Step 5: Commit**

```bash
git add src/mmc_data.py tests/test_mmc_data.py
git commit -m "Add MMC dataset loaders with cleaning + tests"
```

---

### Task 3: `src/mmc_entities.py` — trámite/institution extraction

**Files:**
- Create: `src/mmc_entities.py`
- Test: `tests/test_mmc_entities.py`

**Interfaces:**
- Produces:
  - `ENTITY_PATTERNS: dict[str, list[str]]` — canonical entity name → list of lowercase regex alternatives.
  - `extract_entities(text: str) -> set[str]` — canonical entities whose pattern matches `text` (case-insensitive, accent-insensitive).
  - `entity_counts(texts: Iterable[str]) -> pd.Series` — canonical entity → number of texts mentioning it, sorted descending.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mmc_entities.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_entities as e

def test_extract_ppt_variants():
    assert "PPT" in e.extract_entities("Necesito sacar el ppt")
    assert "PPT" in e.extract_entities("informacion sobre el Permiso por Proteccion Temporal")

def test_extract_institution_accent_insensitive():
    assert "Migración Colombia" in e.extract_entities("fui a migracion colombia")

def test_extract_eps():
    assert "EPS" in e.extract_entities("como me afilio a una EPS")

def test_no_false_positive():
    assert e.extract_entities("hola buenos dias") == set()

def test_entity_counts_orders_desc():
    s = e.entity_counts(["ppt", "ppt y eps", "nada"])
    assert s.loc["PPT"] == 2
    assert list(s.index)[0] == "PPT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mmc_entities.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mmc_entities'`.

- [ ] **Step 3: Implement `src/mmc_entities.py`**

```python
"""Dictionary-based extraction of migration trámites & institutions."""
from __future__ import annotations
from collections import Counter
from typing import Iterable
import re
import unicodedata
import pandas as pd


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# canonical name -> list of regex alternatives (already accent-free, lowercase)
ENTITY_PATTERNS: dict[str, list[str]] = {
    "PPT": [r"\bppt\b", r"permiso por proteccion temporal"],
    "PEP": [r"\bpep\b", r"permiso especial de permanencia"],
    "Visa": [r"\bvisa\b", r"\bvisas\b"],
    "Cédula de extranjería": [r"cedula de extranjeria"],
    "Pasaporte": [r"\bpasaporte\b"],
    "EPS": [r"\beps\b", r"afiliacion en salud", r"seguro de salud"],
    "SISBÉN": [r"\bsisben\b"],
    "Migración Colombia": [r"migracion colombia", r"\bmigracion\b"],
    "ACNUR": [r"\bacnur\b", r"\bunhcr\b"],
    "Cancillería": [r"cancilleria"],
    "Registraduría": [r"registraduria"],
    "SENA": [r"\bsena\b"],
    "ICBF": [r"\bicbf\b"],
    "Refugio/Asilo": [r"\brefugio\b", r"\basilo\b", r"solicitante de refugio"],
    "Trabajo/Empleo": [r"\bempleo\b", r"\btrabajo\b", r"permiso de trabajo"],
    "Educación": [r"\beducacion\b", r"\bcolegio\b", r"\bestudios?\b", r"convalidacion"],
    "Vivienda/Arriendo": [r"\barriendo\b", r"\bvivienda\b", r"subsidio de arriendo"],
    "Ayuda humanitaria": [r"ayuda humanitaria", r"asistencia humanitaria"],
}

_COMPILED = {k: [re.compile(p) for p in pats] for k, pats in ENTITY_PATTERNS.items()}


def extract_entities(text: str) -> set[str]:
    t = _norm(text)
    return {name for name, pats in _COMPILED.items() if any(p.search(t) for p in pats)}


def entity_counts(texts: Iterable[str]) -> pd.Series:
    c: Counter = Counter()
    for t in texts:
        if t is None or (isinstance(t, float) and pd.isna(t)):
            continue
        for ent in extract_entities(t):
            c[ent] += 1
    return pd.Series(c, dtype="int64").sort_values(ascending=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mmc_entities.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mmc_entities.py tests/test_mmc_entities.py
git commit -m "Add trámite/institution entity extraction + tests"
```

---

### Task 4: `src/mmc_text.py` — message splitting & reformulation similarity

**Files:**
- Create: `src/mmc_text.py`
- Test: `tests/test_mmc_text.py`

**Interfaces:**
- Produces:
  - `split_messages(blob: str) -> list[str]` — split a user's `Messages` blob on newlines, strip, drop empties and the literal token `undefined`.
  - `max_consecutive_similarity(embeddings: np.ndarray) -> float` — max cosine similarity between consecutive rows (0.0 if fewer than 2 rows).
  - `count_reformulations(embeddings: np.ndarray, threshold: float = 0.75) -> int` — number of consecutive pairs with cosine similarity ≥ threshold.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mmc_text.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import mmc_text as t

def test_split_drops_undefined_and_blanks():
    assert t.split_messages("hola\n\nquiero ppt\nundefined") == ["hola", "quiero ppt"]

def test_split_none_returns_empty():
    assert t.split_messages(None) == []

def test_max_consecutive_similarity_identical():
    emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    assert abs(t.max_consecutive_similarity(emb) - 1.0) < 1e-6

def test_max_consecutive_similarity_single_row():
    assert t.max_consecutive_similarity(np.array([[1.0, 0.0]])) == 0.0

def test_count_reformulations():
    emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    assert t.count_reformulations(emb, threshold=0.9) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_mmc_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mmc_text'`.

- [ ] **Step 3: Implement `src/mmc_text.py`**

```python
"""Message splitting and reformulation-similarity helpers."""
from __future__ import annotations
import numpy as np


def split_messages(blob) -> list[str]:
    if blob is None or (isinstance(blob, float)):
        return []
    parts = [p.strip() for p in str(blob).split("\n")]
    return [p for p in parts if p and p.lower() != "undefined"]


def _cosine_consecutive(embeddings: np.ndarray) -> np.ndarray:
    emb = np.asarray(embeddings, dtype="float64")
    if emb.shape[0] < 2:
        return np.array([])
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = emb / norms
    return np.sum(unit[:-1] * unit[1:], axis=1)


def max_consecutive_similarity(embeddings: np.ndarray) -> float:
    sims = _cosine_consecutive(embeddings)
    return float(sims.max()) if sims.size else 0.0


def count_reformulations(embeddings: np.ndarray, threshold: float = 0.75) -> int:
    sims = _cosine_consecutive(embeddings)
    return int((sims >= threshold).sum())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all tests across the three modules pass.

- [ ] **Step 5: Commit**

```bash
git add src/mmc_text.py tests/test_mmc_text.py
git commit -m "Add message-splitting + reformulation similarity helpers + tests"
```

---

### Task 5: Notebook A — scaffold + Section 1 (Load & clean)

**Files:**
- Create: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `mmc_data.load_responses`, `mmc_data.load_meal`.
- Produces: an executed notebook whose first cells define `df` (946 rows, cleaned) reused by later tasks.

- [ ] **Step 1: Create the notebook with a title markdown cell**

Use NotebookEdit to create `notebooks/analysis_responses.ipynb` with a first markdown cell:

```markdown
# MMC Chatbot — Advanced Analysis (Responses)

Topic modeling, mixed coding, needs mapping, and cross-cuts over the **946
chatbot users** in `MMC_bot_responses`. Companion to `analysis_meal.ipynb`
(satisfaction). Every section opens with **What this shows / Why it matters**;
non-obvious choices get a **Technical note**. Follow it top-to-bottom without
reading code.

> **Technical note — user-level, self-reported data.** One row per WhatsApp
> user; all of a user's messages are concatenated. There is no per-turn log and
> no bot-output text, which bounds what we can measure (see the final
> *Data gaps* section).
```

- [ ] **Step 2: Add the imports/setup code cell**

```python
import sys, warnings
sys.path.insert(0, '../src')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from palette import *          # blue ramp, bar_colors(), rcParams
import mmc_data, mmc_entities, mmc_text

df = mmc_data.load_responses()
meal = mmc_data.load_meal()
print(f"responses: {len(df)} rows  |  meal: {len(meal)} rows")
```

- [ ] **Step 3: Add a Section 1 markdown + cleaning-summary code cell**

Markdown:
```markdown
## 1. Loading & cleaning

**What this shows.** How many users we have, how complete each field is, and
what cleaning was applied. **Why it matters.** Every later number rests on
these records being correctly parsed and de-duplicated.
```
Code:
```python
summary = pd.DataFrame({
    "non_null": df.notna().sum(),
    "pct": (df.notna().mean() * 100).round(1),
})
display(summary.loc[["Nationality","city_clean","age_num","Gender",
                     "Minors","Messages","Chat_summary","n_questions","ts"]])
print("date range:", df["ts"].min(), "→", df["ts"].max())
print("unique phones:", df["phone"].nunique())
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0, no error outputs; the summary table and date range print.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Scaffold responses analysis notebook + load/clean section"
```

---

### Task 6: Notebook A — Section 2 (Topic modeling with BERTopic)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df` from Task 5.
- Produces: `df["topic"]` (int topic id, -1 = outlier) and `df["topic_label"]` (str) reused by Tasks 7–14; a fitted `topic_model` and `topic_info` DataFrame in scope.

- [ ] **Step 1: Add Section 2 markdown cell**

```markdown
## 2. Topic modeling & clustering

**What this shows.** Conversations grouped automatically by theme — no manual
labeling. **Why it matters.** It reveals what people actually ask about and
gives every later section a shared topic dimension.

> **Technical note.** We embed the English translation (`Text`) with the
> multilingual `paraphrase-multilingual-MiniLM-L12-v2` model, then let BERTopic
> (UMAP → HDBSCAN → c-TF-IDF) find clusters. `-1` is the outlier topic. A fixed
> `random_state` makes UMAP reproducible.
```

- [ ] **Step 2: Add the BERTopic fitting code cell**

```python
from sentence_transformers import SentenceTransformer
from umap import UMAP
from bertopic import BERTopic

docs_mask = df["Text"].notna() & (df["Text"].astype(str).str.len() > 0)
docs = df.loc[docs_mask, "Text"].astype(str).tolist()

embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
embeddings = embedder.encode(docs, show_progress_bar=False)

umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0,
                  metric='cosine', random_state=42)
topic_model = BERTopic(umap_model=umap_model, language='multilingual',
                       min_topic_size=10, calculate_probabilities=False)
topics, _ = topic_model.fit_transform(docs, embeddings)

df["topic"] = -2                     # -2 = no text / not modeled
df.loc[docs_mask, "topic"] = topics
topic_info = topic_model.get_topic_info()
label_map = dict(zip(topic_info["Topic"], topic_info["Name"]))
label_map[-2] = "no message"
df["topic_label"] = df["topic"].map(label_map)
topic_info.head(20)
```

- [ ] **Step 3: Add a topic-size bar chart cell**

```python
vis = topic_info[topic_info["Topic"] >= 0].head(12).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 6))
ax.barh(vis["Name"], vis["Count"], color=bar_colors(len(vis)))
ax.set_title("Largest conversation topics (BERTopic)")
ax.set_xlabel("users")
plt.tight_layout()
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; topic table + bar chart render. (First run downloads the model.)

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add BERTopic topic modeling section to responses notebook"
```

---

### Task 7: Notebook A — Section 3 (Mixed coding: MMC + emergent)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["topic"]`, `df["topic_label"]`, `df["Chat_summary"]`.
- Produces: `df["mmc_category"]` (str) — crosswalk of each topic to an MMC category or `"emergent"`.

- [ ] **Step 1: Add Section 3 markdown cell**

```markdown
## 3. Mixed coding — MMC taxonomy + emergent topics

**What this shows.** Each auto-discovered topic mapped onto MMC's own
categories, with topics that don't fit flagged as *emergent*. **Why it matters.**
It keeps results comparable to MMC's existing framework while surfacing new
demand the taxonomy misses.

> **Technical note.** We seed the mapping from the human `Chat_summary` label
> that co-occurs most with each BERTopic topic, then hand-check a small sample.
> The crosswalk below is editable — adjust `TOPIC_TO_MMC` after review.
```

- [ ] **Step 2: Add the crosswalk-seeding code cell**

```python
# normalize the existing human labels as the MMC category vocabulary
df["chat_norm"] = (df["Chat_summary"].astype(str)
                   .str.lower().str.lstrip("#").str.strip())

# for each topic, the most common human label = seed MMC category
seed = (df[df["topic"] >= 0]
        .groupby("topic")["chat_norm"]
        .agg(lambda s: s.value_counts().idxmax()))
TOPIC_TO_MMC = seed.to_dict()   # <-- edit after the sample check below

df["mmc_category"] = df["topic"].map(TOPIC_TO_MMC).fillna("emergent")

# validation sample: 8 random messages with topic + assigned category
sample = (df[df["topic"] >= 0]
          .sample(8, random_state=1)[["Text", "topic_label", "mmc_category"]])
display(sample)
```

- [ ] **Step 3: Add a crosswalk table + emergent-share cell**

```python
crosswalk = (df[df["topic"] >= 0]
             .groupby(["topic", "topic_label", "mmc_category"])
             .size().rename("users").reset_index()
             .sort_values("users", ascending=False))
display(crosswalk)
emergent_share = (df["mmc_category"] == "emergent").mean() * 100
print(f"emergent (outside MMC seed labels): {emergent_share:.1f}% of users")
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; crosswalk and sample tables render.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add mixed-coding crosswalk section"
```

---

### Task 8: Notebook A — Section 4 (Needs & entities)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["Messages"]`, `df["city_clean"]`, `mmc_entities`.
- Produces: `df` gains one boolean column per canonical entity (prefix `ent_`).

- [ ] **Step 1: Add Section 4 markdown cell**

```markdown
## 4. Most-requested needs (trámites & institutions)

**What this shows.** Which documents, procedures, and institutions people
mention most (PPT, EPS, Migración Colombia, …). **Why it matters.** It maps
real demand so MMC can prioritize content and referrals.

> **Technical note.** A curated dictionary (`mmc_entities.ENTITY_PATTERNS`)
> matches accent- and case-insensitively on the raw Spanish `Messages`. A
> message can mention several entities.
```

- [ ] **Step 2: Add the entity-frequency code cell**

```python
counts = mmc_entities.entity_counts(df["Messages"])
fig, ax = plt.subplots(figsize=(8, 6))
top = counts.head(15).iloc[::-1]
ax.barh(top.index, top.values, color=bar_colors(len(top)))
ax.set_title("Most-mentioned trámites & institutions")
ax.set_xlabel("users mentioning")
plt.tight_layout()

# add per-entity boolean columns for later cross-tabs
for ent in counts.index:
    col = "ent_" + ent
    df[col] = df["Messages"].fillna("").map(lambda t, e=ent: e in mmc_entities.extract_entities(t))
```

- [ ] **Step 3: Add an entity-by-city heatmap cell**

```python
ent_cols = [c for c in df.columns if c.startswith("ent_")]
top_cities = df["city_clean"].value_counts().head(10).index
mat = (df[df["city_clean"].isin(top_cities)]
       .groupby("city_clean")[ent_cols].mean().loc[top_cities])
mat.columns = [c[4:] for c in mat.columns]
fig, ax = plt.subplots(figsize=(11, 6))
sns.heatmap(mat, cmap=sns.light_palette(BLUES[5], as_cmap=True),
            ax=ax, cbar_kws={"label": "share of users"})
ax.set_title("Entity mention rate by city (top 10 by volume)")
plt.tight_layout()
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; bar chart + heatmap render.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add needs & entity extraction section"
```

---

### Task 9: Notebook A — Section 5 (Geographic analysis)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["city_clean"]`, `df["mmc_category"]`.
- Produces: (in-notebook only) volume + topic-mix-by-city charts.

- [ ] **Step 1: Add Section 5 markdown cell**

```markdown
## 5. Geographic analysis by city

**What this shows.** Query volume and topic mix across the highest-volume
cities. **Why it matters.** MMC operates in priority cities; this compares
where demand concentrates and how needs differ by place.

> **Technical note.** Cities are ranked by user volume from the data. To pin the
> analysis to MMC's official 10 priority cities, replace `top_cities` with that
> list.
```

- [ ] **Step 2: Add the volume-by-city bar cell**

```python
top_cities = df["city_clean"].value_counts().head(10)
fig, ax = plt.subplots(figsize=(8, 6))
order = top_cities.iloc[::-1]
ax.barh(order.index, order.values, color=bar_colors(len(order)))
ax.set_title("Users by city (top 10)")
ax.set_xlabel("users")
plt.tight_layout()
```

- [ ] **Step 3: Add the topic-mix-by-city stacked cell**

```python
cats = df["mmc_category"].value_counts().head(6).index
sub = df[df["city_clean"].isin(top_cities.index) & df["mmc_category"].isin(cats)]
mix = (pd.crosstab(sub["city_clean"], sub["mmc_category"], normalize="index")
       .loc[top_cities.index])
mix.plot(kind="barh", stacked=True, figsize=(10, 6),
         color=bar_colors(mix.shape[1]))
plt.title("Topic mix by city (share of users)")
plt.xlabel("share")
plt.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
plt.tight_layout()
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; both charts render.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add geographic analysis section"
```

---

### Task 10: Notebook A — Section 6 (Temporal analysis of topics)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["ts"]`, `df["mmc_category"]`.
- Produces: (in-notebook only) weekly volume + topic-trend charts with an event overlay.

- [ ] **Step 1: Add Section 6 markdown cell**

```markdown
## 6. Temporal analysis — topics over time

**What this shows.** How overall volume and specific topics rise and fall by
date. **Why it matters.** Spikes often track migration-policy events; aligning
them helps MMC anticipate demand.

> **Technical note.** Time is the user's first-contact `Timestamp` (one per
> user), bucketed weekly. `EVENTS` is a manually curated overlay — extend it
> with confirmed policy dates.
```

- [ ] **Step 2: Add the weekly-volume + events cell**

```python
EVENTS = {
    # "2026-04-15": "example policy milestone",
}
ts = df.dropna(subset=["ts"]).set_index("ts")
weekly = ts.resample("W").size()
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(weekly.index, weekly.values, color=AGUA, marker="o", ms=3)
for date, label in EVENTS.items():
    ax.axvline(pd.Timestamp(date), color=MADERA, ls="--", lw=1)
    ax.text(pd.Timestamp(date), weekly.max(), label, rotation=90,
            va="top", fontsize=8)
ax.set_title("Weekly user volume")
ax.set_ylabel("users")
plt.tight_layout()
```

- [ ] **Step 3: Add the topic-trend cell**

```python
cats = df["mmc_category"].value_counts().head(4).index
trend = (df.dropna(subset=["ts"])
         .assign(week=lambda d: d["ts"].dt.to_period("W").dt.start_time)
         [lambda d: d["mmc_category"].isin(cats)]
         .groupby(["week", "mmc_category"]).size().unstack(fill_value=0))
fig, ax = plt.subplots(figsize=(11, 5))
for i, c in enumerate(trend.columns):
    ax.plot(trend.index, trend[c], marker="o", ms=3,
            color=BLUES[(i * 2) % len(BLUES)], label=c)
ax.set_title("Top-4 topics over time (weekly)")
ax.legend(fontsize=8)
plt.tight_layout()
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; both time charts render.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add temporal topic analysis section"
```

---

### Task 11: Notebook A — Section 7 (Demographics × topic)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["Nationality"]`, `df["Gender"]`, `df["Age Ranges"]`, `df["mmc_category"]`.
- Produces: (in-notebook only) proportion heatmaps.

- [ ] **Step 1: Add Section 7 markdown cell**

```markdown
## 7. Demographic profile vs. topic

**What this shows.** How topic demand differs by nationality, gender, and age
band. **Why it matters.** It reveals which segments ask about what, so outreach
and content can be tailored.

> **Technical note.** Cells are row-normalized (share of that group's users),
> so rows sum to 1 and small groups aren't visually swamped by large ones.
```

- [ ] **Step 2: Add a reusable heatmap helper + nationality heatmap cell**

```python
top_cats = df["mmc_category"].value_counts().head(6).index

def topic_heatmap(group_col, top_n=6, title=""):
    groups = df[group_col].value_counts().head(top_n).index
    sub = df[df[group_col].isin(groups) & df["mmc_category"].isin(top_cats)]
    mat = pd.crosstab(sub[group_col], sub["mmc_category"], normalize="index").loc[groups]
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(groups) + 2))
    sns.heatmap(mat, cmap=sns.light_palette(BLUES[5], as_cmap=True),
                annot=True, fmt=".0%", ax=ax, cbar_kws={"label": "share"})
    ax.set_title(title)
    plt.tight_layout()

topic_heatmap("Nationality", title="Topic mix by nationality")
```

- [ ] **Step 3: Add gender + age-range heatmap cells**

```python
topic_heatmap("Gender", top_n=4, title="Topic mix by gender")
```
```python
topic_heatmap("Age Ranges", top_n=4, title="Topic mix by age range")
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; three heatmaps render.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add demographics-by-topic section"
```

---

### Task 12: Notebook A — Section 8 (Engagement depth)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["n_questions"]`.
- Produces: (in-notebook only) distribution chart + single-question share.

- [ ] **Step 1: Add Section 8 markdown cell**

```markdown
## 8. Engagement depth (questions per user)

**What this shows.** How many questions each user asks before stopping, and how
many ask only once. **Why it matters.** Shallow engagement can signal friction —
but read it carefully.

> **Data gap — not turn-level drop-off.** We only have a per-user question
> *count*, not the ordered message sequence, so we cannot pinpoint *where* in a
> conversation people abandon. True drop-off analysis needs turn-level logs
> (see the final section).
```

- [ ] **Step 2: Add the distribution cell**

```python
q = df["n_questions"].dropna()
fig, ax = plt.subplots(figsize=(8, 5))
bins = range(0, int(q.max()) + 2)
ax.hist(q, bins=bins, color=AGUA, edgecolor=NEGRO)
ax.set_title("Questions per user")
ax.set_xlabel("questions"); ax.set_ylabel("users")
plt.tight_layout()
print(f"median: {q.median():.0f}  |  single-question share: "
      f"{(q <= 1).mean() * 100:.1f}%")
```

- [ ] **Step 3: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; histogram renders, stats print.

- [ ] **Step 4: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add engagement-depth section"
```

---

### Task 13: Notebook A — Section 9 (Repeated / reformulated questions)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["Messages"]`, `embedder` (from Task 6), `mmc_text`.
- Produces: `df["n_reformulations"]` (int), `df["n_msgs"]` (int).

- [ ] **Step 1: Add Section 9 markdown cell**

```markdown
## 9. Repeated / reformulated questions (heuristic)

**What this shows.** Users who rephrase the same question several times — a hint
they didn't get a useful answer. **Why it matters.** Clusters of reformulation
point at content gaps or unclear bot replies.

> **Technical note — heuristic.** We split each user's messages, embed them, and
> count consecutive pairs with cosine similarity ≥ 0.75. This approximates
> "asked the same thing again"; it is not a verified intent match.
```

- [ ] **Step 2: Add the reformulation-count cell**

```python
def user_reformulations(blob):
    msgs = mmc_text.split_messages(blob)
    if len(msgs) < 2:
        return 0, len(msgs)
    emb = embedder.encode(msgs, show_progress_bar=False)
    return mmc_text.count_reformulations(emb, threshold=0.75), len(msgs)

res = df["Messages"].map(user_reformulations)
df["n_reformulations"] = [r[0] for r in res]
df["n_msgs"] = [r[1] for r in res]

reform_users = (df["n_reformulations"] > 0).mean() * 100
print(f"users with >=1 reformulated pair: {reform_users:.1f}%")
display(df[df["n_reformulations"] > 0]
        .sort_values("n_reformulations", ascending=False)
        [["city_clean", "mmc_category", "n_msgs", "n_reformulations"]].head(10))
```

- [ ] **Step 3: Add a reformulation-by-topic cell**

```python
by_topic = (df[df["n_msgs"] >= 2]
            .groupby("mmc_category")["n_reformulations"]
            .mean().sort_values(ascending=False).head(10).iloc[::-1])
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(by_topic.index, by_topic.values, color=bar_colors(len(by_topic)))
ax.set_title("Avg reformulations per user by topic")
ax.set_xlabel("mean reformulated pairs")
plt.tight_layout()
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; table + chart render. (Slow — embeds per user.)

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add reformulated-questions heuristic section"
```

---

### Task 14: Notebook A — Section 10 (Satisfaction × topic) + Section 11 (Data gaps)

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

**Interfaces:**
- Consumes: `df["phone"]`, `df["mmc_category"]`, `meal` (from Task 5).
- Produces: (in-notebook only) satisfaction-by-topic chart + closing limitations section.

- [ ] **Step 1: Add Section 10 markdown cell**

```markdown
## 10. Satisfaction (MEAL) × topic

**What this shows.** Utility ratings joined to the topic each user asked about.
**Why it matters.** It flags which topics produce the worst experience.

> **Technical note — small overlap.** Only users who completed the MEAL survey
> appear here (dozens, not hundreds). Read proportions as directional, not
> precise. Joined on WhatsApp phone number.
```

- [ ] **Step 2: Add the join + satisfaction-by-topic cell**

```python
UTIL_ORDER = ["Nada útil", "Medianamente útil", "Útil", "Muy útil"]
merged = df.merge(meal[["phone", "utility"]], on="phone", how="inner")
print(f"users with both topic and MEAL rating: {len(merged)}")

merged["utility"] = pd.Categorical(merged["utility"], UTIL_ORDER, ordered=True)
cats = merged["mmc_category"].value_counts().head(6).index
sub = merged[merged["mmc_category"].isin(cats)]
tab = pd.crosstab(sub["mmc_category"], sub["utility"], normalize="index")[UTIL_ORDER]
tab.plot(kind="barh", stacked=True, figsize=(10, 6), color=bar_colors(4))
plt.title("Utility rating by topic (MEAL respondents)")
plt.xlabel("share"); plt.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
plt.tight_layout()
```

- [ ] **Step 3: Add Section 11 (Data gaps) markdown cell**

```markdown
## 11. Data gaps & limitations

Some analyses MMC may want are **not possible with the current export** because
it is user-level and contains no bot output. Documented here so they can be
planned for:

- **Fallback / no-response rate by topic** — needs the bot's replies (or an
  explicit "no answer" flag) per message. Not in the data.
- **Response consistency (same question, different answers)** — needs bot
  output text to compare. Not in the data.
- **True drop-off / abandonment point** — needs the ordered turn-by-turn log
  (which message a user stopped at), not just a per-user question count.

What *would* unlock them: a turn-level conversation log with, per turn, the user
message, the bot response, a fallback flag, and a timestamp.
```

- [ ] **Step 4: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb`
Expected: exits 0; join count prints, chart renders.

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Add satisfaction-by-topic + data-gaps sections"
```

---

### Task 15: Notebook B — `analysis_meal.ipynb` (satisfaction descriptives)

**Files:**
- Create: `notebooks/analysis_meal.ipynb`

**Interfaces:**
- Consumes: `mmc_data.load_meal`.
- Produces: a fully executed MEAL descriptives notebook.

- [ ] **Step 1: Create the notebook with title + setup cells**

Title markdown:
```markdown
# MMC Chatbot — MEAL Satisfaction Analysis

Satisfaction descriptives over the **78 MEAL responses**: how useful the service
was, whether people would recommend it, and how they found it. Companion to
`analysis_responses.ipynb`.

> **Technical note — small sample.** 78 responses. Every proportion is
> directional; read counts alongside percentages.
```
Setup code:
```python
import sys, warnings
sys.path.insert(0, '../src')
warnings.filterwarnings('ignore')
import pandas as pd, matplotlib.pyplot as plt, seaborn as sns
from palette import *
import mmc_data
meal = mmc_data.load_meal()
print(f"{len(meal)} MEAL responses")
```

- [ ] **Step 2: Add Section 1 — utility rating**

Markdown (What this shows / Why it matters) + code:
```python
UTIL_ORDER = ["Nada útil", "Medianamente útil", "Útil", "Muy útil"]
u = meal["utility"].value_counts().reindex(UTIL_ORDER).fillna(0)
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(u.index, u.values, color=bar_colors(len(u)))
ax.set_title("How useful was the information?")
ax.set_ylabel("responses")
plt.xticks(rotation=15); plt.tight_layout()
print((u / u.sum() * 100).round(1))
```

- [ ] **Step 3: Add Section 2 — would-recommend**

```python
r = meal["would_recommend"].value_counts()
fig, ax = plt.subplots(figsize=(7, 5))
ax.bar(r.index, r.values, color=bar_colors(len(r)))
ax.set_title("Would you recommend this service?")
ax.set_ylabel("responses")
plt.xticks(rotation=15); plt.tight_layout()
print((r / r.sum() * 100).round(1))
```

- [ ] **Step 4: Add Section 3 — how they heard (channel + medium)**

```python
h = meal["heard_channel"].value_counts()
fig, ax = plt.subplots(figsize=(8, 5))
order = h.iloc[::-1]
ax.barh(order.index, order.values, color=bar_colors(len(order)))
ax.set_title("How did you hear about the service?")
ax.set_xlabel("responses")
plt.tight_layout()
print("free-text 'other' media:")
print(meal["heard_medium"].dropna().value_counts().head(10))
```

- [ ] **Step 5: Add Section 4 — free-text recommendations (thematic read)**

```python
recs = meal["recommendation"].dropna().astype(str)
recs = recs[~recs.str.strip().str.lower().isin(["no", "ninguna", "ninguno", "nada"])]
print(f"{len(recs)} substantive recommendations\n")
for t in recs.head(20):
    print("•", t)
```
Add a markdown note that with 78 rows this stays a qualitative read, not modeling.

- [ ] **Step 6: Execute the notebook to validate**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_meal.ipynb`
Expected: exits 0; all charts render, prints appear.

- [ ] **Step 7: Commit**

```bash
git add notebooks/analysis_meal.ipynb
git commit -m "Add MEAL satisfaction analysis notebook"
```

---

### Task 16: Final validation + README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 2: Re-execute both notebooks clean, end to end**

Run:
```bash
.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_responses.ipynb
.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/analysis_meal.ipynb
```
Expected: both exit 0 with no error outputs.

- [ ] **Step 3: Add the two notebooks to `README.md`**

Add a bullet under the notebooks/analysis section describing `analysis_responses.ipynb` (topic modeling + cross-cuts) and `analysis_meal.ipynb` (satisfaction descriptives), matching the README's existing style.

- [ ] **Step 4: Commit**

```bash
git add README.md notebooks/analysis_responses.ipynb notebooks/analysis_meal.ipynb
git commit -m "Document analysis notebooks in README; final executed outputs"
```

---

## Notes for the implementer

- Run everything through `.venv/Scripts/python.exe`. Never call bare `python`/`pip`.
- BERTopic/UMAP on ~830 docs takes ~1–2 min; Section 9 embeds per user and is the slowest — expect several minutes on first full run.
- If HDBSCAN puts most docs in topic `-1`, lower `min_topic_size` (e.g. 8) and re-run Task 6 before building dependent sections.
- Keep `df` mutations additive and in section order — later sections read columns earlier ones create.
