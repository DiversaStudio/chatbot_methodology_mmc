# Message-level Analysis Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `notebooks/analysis_responses.ipynb` on a message-level spine (one row per user turn), with zero-shot MMC tinting + emergent detection, 7-class emotion, and clean geographic maps.

**Architecture:** New `src/mmc_data.load_messages()` explodes `Messages` on `\n` into a `msgs` DataFrame linked to each user's full interaction. Per-message topic tinting uses a deterministic zero-shot NLI classifier (`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`); e5-large embeddings + HDBSCAN group and name emergent themes. All expensive outputs are cached under `cache/` for reproducibility. Cross-cut sections aggregate message labels back to the user where needed.

**Tech Stack:** pandas, sentence-transformers (e5-large), transformers (zero-shot NLI + emotion), umap-learn, hdbscan, geopandas/osmnx, matplotlib, pytest, uv.

## Global Constraints

- Python env managed by **uv** only (`uv sync`, `uv add`, `uv run`); never standalone pip/venv. `tool.uv.package = false` and `python-preference = "only-system"` must stay in `pyproject.toml`.
- **Device:** `device = "cuda" if torch.cuda.is_available() else "cpu"` everywhere a model runs. CPU must always work.
- **Reproducibility:** UMAP `random_state=42`; classifier/sentiment/emotion by argmax. Cache embeddings/labels to `cache/` and load-if-exists.
- Notebooks run from `notebooks/` with `sys.path.insert(0, '../src')`. Palette from `src/palette.py`. Per-section markdown paragraph stating which questions it answers (existing repo convention).
- Do **not** use `Text` (English MT) or `Text 1` (bot summary) for modeling. `Chat_summary` is a weak cross-check only.
- Git commits: no `Co-Authored-By` trailer.
- MMC taxonomy (7): legal documentation, humanitarian assistance, employment, services, protection, journey information, organization search.

---

### Task 1: Environment & dependencies

**Files:**
- Modify: `pyproject.toml` (add `emoji`)

- [ ] **Step 1: Sync existing deps**

Run: `uv sync`
Expected: resolves, `.venv` populated, no removal of `src/`.

- [ ] **Step 2: Add emoji helper for emotion preprocessing**

Run: `uv add emoji`
Expected: `emoji` added to `pyproject.toml` dependencies, lock updated.

- [ ] **Step 3: Verify torch + cached models load**

Run:
```bash
uv run python -c "import torch,transformers,sentence_transformers as st; print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
```
Expected: prints torch version; `cuda False` on CPU-only env is acceptable.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add emoji dep for emotion preprocessing"
```

---

### Task 2: `load_messages()` — message-level spine

**Files:**
- Modify: `src/mmc_data.py`
- Test: `tests/test_load_messages.py`

**Interfaces:**
- Consumes: `load_responses()` (existing) → user-level `df` with `phone`, `city_clean`, `ts`, `age_num`, `Messages`, demographics.
- Produces: `load_messages(df=None) -> pd.DataFrame` with columns `phone, msg_idx (int, 0-based), n_msgs_user (int), message (str), city_clean, ts, Gender, "Age Ranges", Nationality, age_num`. One row per non-noise user turn. Noise dropped: `len(strip) < 3`, pure digits, `undefined`, `?` (case-insensitive).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_load_messages.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
import mmc_data


def _fake_df():
    return pd.DataFrame({
        "phone": ["1", "2"],
        "Messages": ["Hola\nQuiero informacion de los servicios", "12\n?\nNecesito ayuda con el PPT urgente"],
        "city_clean": ["Medellín", "Bogotá"],
        "ts": pd.to_datetime(["2026-04-01", "2026-04-02"]),
        "Gender": ["F", "M"],
        "Age Ranges": ["18-25", "26-35"],
        "Nationality": ["Venezuela", "Venezuela"],
        "age_num": [22.0, 30.0],
    })


def test_explode_and_noise_filter():
    msgs = mmc_data.load_messages(_fake_df())
    # user 1: "Hola" (kept, len>=3) + "Quiero..." = 2 msgs
    # user 2: "12" dropped (digits), "?" dropped, "Necesito..." kept = 1 msg
    assert list(msgs["message"]) == [
        "Hola",
        "Quiero informacion de los servicios",
        "Necesito ayuda con el PPT urgente",
    ]
    assert list(msgs["msg_idx"]) == [0, 1, 0]
    assert list(msgs["n_msgs_user"]) == [2, 2, 1]
    assert list(msgs["phone"]) == ["1", "1", "2"]
    assert msgs.loc[0, "city_clean"] == "Medellín"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_load_messages.py -v`
Expected: FAIL (`load_messages` not defined).

- [ ] **Step 3: Implement `load_messages`**

```python
# src/mmc_data.py — append
_NOISE = {"undefined", "?", ""}


def _is_noise(t: str) -> bool:
    t = t.strip()
    return len(t) < 3 or t.isdigit() or t.lower() in _NOISE


def load_messages(df=None) -> pd.DataFrame:
    """Explode the per-user `Messages` blob into one row per user turn."""
    if df is None:
        df = load_responses()
    carry = ["phone", "city_clean", "ts", "Gender", "Age Ranges", "Nationality", "age_num"]
    carry = [c for c in carry if c in df.columns]
    rows = []
    for _, r in df.iterrows():
        blob = r.get("Messages")
        if not isinstance(blob, str):
            continue
        parts = [p.strip() for p in blob.split("\n")]
        parts = [p for p in parts if not _is_noise(p)]
        for i, p in enumerate(parts):
            row = {c: r[c] for c in carry}
            row["msg_idx"] = i
            row["n_msgs_user"] = len(parts)
            row["message"] = p
            rows.append(row)
    out = pd.DataFrame(rows).reset_index(drop=True)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_load_messages.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke-check on real data**

Run:
```bash
uv run python -c "import sys; sys.path.insert(0,'src'); import mmc_data; m=mmc_data.load_messages(); print(m.shape); print(m['n_msgs_user'].describe())"
```
Expected: ~2900–3000 rows; mean `n_msgs_user` ≈ 3.9.

- [ ] **Step 6: Commit**

```bash
git add src/mmc_data.py tests/test_load_messages.py
git commit -m "Add load_messages(): message-level spine"
```

---

### Task 3: `city_canon` normalization for clean maps

**Files:**
- Modify: `src/mmc_data.py`
- Test: `tests/test_city_canon.py`

**Interfaces:**
- Produces: `city_canon(name: str) -> str` — accent/case-insensitive canonicalization to the MMC priority cities; non-cities → `"Otra"`. `load_responses()` gains a `city_canon` column; `load_messages()` carries it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_city_canon.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_data


def test_city_canon_variants():
    assert mmc_data.city_canon("Bogota") == "Bogotá"
    assert mmc_data.city_canon("bogotá") == "Bogotá"
    assert mmc_data.city_canon("Soacha Cundinamarca") == "Soacha"
    assert mmc_data.city_canon("Cucuta") == "Cúcuta"
    assert mmc_data.city_canon("Medellín") == "Medellín"
    assert mmc_data.city_canon("Colombia") == "Otra"
    assert mmc_data.city_canon("Cundinamarca") == "Otra"
    assert mmc_data.city_canon(None) == "Otra"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_city_canon.py -v`
Expected: FAIL (`city_canon` not defined).

- [ ] **Step 3: Implement `city_canon`**

```python
# src/mmc_data.py — append
import unicodedata

# 10 MMC priority cities + common variants -> canonical display name
_CITY_CANON = {
    "medellin": "Medellín", "medellin antioquia": "Medellín", "belen": "Medellín",
    "bogota": "Bogotá", "bogota dc": "Bogotá",
    "cucuta": "Cúcuta",
    "barranquilla": "Barranquilla",
    "santa marta": "Santa Marta",
    "cali": "Cali",
    "cartagena": "Cartagena",
    "bucaramanga": "Bucaramanga",
    "ipiales": "Ipiales",
    "riohacha": "Riohacha", "maicao": "Maicao",
    "soacha": "Soacha", "soacha cundinamarca": "Soacha",
    "necocli": "Necoclí",
}
# tokens that are regions/countries, not a priority city -> Otra
_NON_CITY = {"colombia", "cundinamarca", "antioquia", "otra", "nan"}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def city_canon(name) -> str:
    if name is None:
        return "Otra"
    key = _fold(name)
    if key in _NON_CITY or key == "":
        return "Otra"
    if key in _CITY_CANON:
        return _CITY_CANON[key]
    # startswith match for "<city> <extra>" tails
    for k, v in _CITY_CANON.items():
        if key.startswith(k):
            return v
    return "Otra"
```

Then wire it into `load_responses()` (add after `city_clean` is built):

```python
    df["city_canon"] = df["city_clean"].map(city_canon)
```

And add `"city_canon"` to the `carry` list in `load_messages()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_city_canon.py -v`
Expected: PASS.

- [ ] **Step 5: Check coverage on real data**

Run:
```bash
uv run python -c "import sys; sys.path.insert(0,'src'); import mmc_data; d=mmc_data.load_responses(); print(d['city_canon'].value_counts().head(12))"
```
Expected: consolidated counts; `Medellín` largest, `Otra` present, no duplicate `Bogota/Bogotá`.

- [ ] **Step 6: Commit**

```bash
git add src/mmc_data.py tests/test_city_canon.py
git commit -m "Add city_canon normalization for clean maps"
```

---

### Task 4: Spanish stopwords + courtesy/social-noise detection

**Files:**
- Modify: `src/mmc_text.py`
- Test: `tests/test_courtesy.py`

**Interfaces:**
- Produces:
  - `SPANISH_STOPWORDS: list[str]` — Spanish stopwords + courtesy tokens, for c-TF-IDF `CountVectorizer(stop_words=...)`.
  - `is_courtesy(text: str) -> bool` — True for greeting/thanks/blessing-only turns.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_courtesy.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_text


def test_is_courtesy():
    assert mmc_text.is_courtesy("Hola")
    assert mmc_text.is_courtesy("Muchas gracias, Dios le bendiga")
    assert mmc_text.is_courtesy("buenos días")
    assert mmc_text.is_courtesy("AMÉN 🙏")
    assert not mmc_text.is_courtesy("Necesito ayuda con el PPT")
    assert not mmc_text.is_courtesy("Cómo solicitar el salvoconducto")


def test_stopwords_present():
    assert "de" in mmc_text.SPANISH_STOPWORDS
    assert "gracias" in mmc_text.SPANISH_STOPWORDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_courtesy.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement in `src/mmc_text.py`**

```python
# src/mmc_text.py — append
import re, unicodedata

_BASE_STOP = (
    "a al algo algunas algunos ante antes como con contra cual cuando de del "
    "desde donde dos el ella ellas ellos en entre era es esa ese eso esta este "
    "esto ha hasta hay la las le les lo los mas me mi mis mucho muy nada ni no "
    "nos o os para pero poco por porque que quien se sin sobre soy su sus te "
    "tener tengo ti tu tus un una uno unos y ya yo".split()
)
_COURTESY_TOKENS = (
    "hola buenas buenos dias tardes noches gracias muchas mil bendiga bendiciones "
    "amen dios saludos hi hello ok okay bien vale adios chao hasta luego favor "
    "porfavor porfa disculpa disculpe perdon".split()
)
SPANISH_STOPWORDS = sorted(set(_BASE_STOP) | set(_COURTESY_TOKENS))


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def is_courtesy(text: str) -> bool:
    """True when a turn is only greeting/thanks/blessing words (no substantive content)."""
    folded = _fold(text)
    words = re.findall(r"[a-zñ]+", folded)
    if not words:
        return True  # emoji/punctuation only
    non_courtesy = [w for w in words if w not in _COURTESY_TOKENS]
    return len(non_courtesy) == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_courtesy.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite green**

Run: `uv run pytest -q`
Expected: all tests pass (existing + 3 new files).

- [ ] **Step 6: Commit**

```bash
git add src/mmc_text.py tests/test_courtesy.py
git commit -m "Add Spanish stopwords + courtesy detection"
```

---

### Task 5: Validate & wrap the emotion model

**Files:**
- Create: `notebooks/_emotion_probe.py` (throwaway validation; delete after)
- Modify: `src/mmc_text.py` (add `load_emotion_pipeline`)
- Test: `tests/test_emotion.py`

**Interfaces:**
- Produces: `load_emotion_pipeline()` → a callable returning, for a list of texts, a list of dicts `{"label": str, "score": float}` with labels in the 7-class set (`joy, sadness, anger, fear, surprise, disgust, others`). Model `pysentimiento/robertuito-emotion-analysis` (direct via transformers), CPU/GPU auto.

- [ ] **Step 1: Validate the model on real Spanish messages**

Create `notebooks/_emotion_probe.py`:
```python
import sys; sys.path.insert(0, "src")
import mmc_data
from transformers import pipeline
import torch
dev = 0 if torch.cuda.is_available() else -1
clf = pipeline("text-classification", model="pysentimiento/robertuito-emotion-analysis", device=dev, top_k=1)
m = mmc_data.load_messages()
for t in m["message"].head(15):
    print(clf(t[:200])[0], "|", t[:70])
```
Run: `PYTHONIOENCODING=utf-8 uv run python notebooks/_emotion_probe.py`
Expected: sensible emotions (distress messages → sadness/fear/anger). If the model fails to load under transformers 5.x, switch model id to `daveni/twitter-xlm-roberta-emotion-es` and re-run.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_emotion.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_text


def test_emotion_labels():
    clf = mmc_text.load_emotion_pipeline()
    out = clf(["Estoy muy feliz, gracias por la ayuda", "Tengo miedo, me van a deportar"])
    assert len(out) == 2
    assert all(set(o) >= {"label", "score"} for o in out)
    assert all(0.0 <= o["score"] <= 1.0 for o in out)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_emotion.py -v`
Expected: FAIL (`load_emotion_pipeline` not defined).

- [ ] **Step 4: Implement wrapper**

```python
# src/mmc_text.py — append
def load_emotion_pipeline(model_id: str = "pysentimiento/robertuito-emotion-analysis"):
    """Return f(texts) -> list[{'label','score'}] using a 7-class Spanish emotion model."""
    from transformers import pipeline
    import torch
    dev = 0 if torch.cuda.is_available() else -1
    pipe = pipeline("text-classification", model=model_id, device=dev, top_k=1, truncation=True)

    def _run(texts):
        if isinstance(texts, str):
            texts = [texts]
        res = pipe([t[:256] for t in texts])
        # top_k=1 → each item is a list with one dict
        return [r[0] if isinstance(r, list) else r for r in res]

    return _run
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_emotion.py -v`
Expected: PASS.

- [ ] **Step 6: Clean up probe + commit**

```bash
rm notebooks/_emotion_probe.py
git add src/mmc_text.py tests/test_emotion.py
git commit -m "Validate + wrap 7-class emotion model"
```

---

### Task 6: Cached artifact builders (embeddings, zero-shot, emotion)

**Files:**
- Create: `src/mmc_nlp.py`
- Test: `tests/test_mmc_nlp_smoke.py`

**Interfaces:**
- Produces (all cache-if-exists under `cache/`):
  - `embed_messages(messages: list[str], cache="cache/emb_msg_e5.npy") -> np.ndarray` — e5-large, `"query: "` prefix, normalized.
  - `MMC_LABELS: dict[str,str]` (7 Spanish hypotheses) and `zeroshot_tint(messages, cache="cache/zeroshot_labels.parquet") -> pd.DataFrame[message, mmc_category, conf]`.
  - `emotion_label(messages, cache="cache/emotion.parquet") -> pd.DataFrame[message, emotion, emo_score]`.
- Consumes: `mmc_text.load_emotion_pipeline`.

- [ ] **Step 1: Write the smoke test (tiny input, no cache)**

```python
# tests/test_mmc_nlp_smoke.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_nlp


def test_zeroshot_small(tmp_path):
    msgs = ["Cómo solicitar el salvoconducto", "Para empleo formal"]
    out = mmc_nlp.zeroshot_tint(msgs, cache=str(tmp_path / "z.parquet"))
    assert list(out["message"]) == msgs
    assert out.loc[0, "mmc_category"] == "legal documentation"
    assert out.loc[1, "mmc_category"] == "employment"
    assert (out["conf"] > 0.5).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mmc_nlp_smoke.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `src/mmc_nlp.py`**

```python
# src/mmc_nlp.py
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]


def _device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def embed_messages(messages, cache="cache/emb_msg_e5.npy") -> np.ndarray:
    p = _ROOT / cache
    if p.exists():
        emb = np.load(p)
        if emb.shape[0] == len(messages):
            return emb
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-large", device=_device())
    emb = model.encode(["query: " + m for m in messages],
                       normalize_embeddings=True, batch_size=16, show_progress_bar=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, emb)
    return emb


MMC_LABELS = {
    "legal documentation": "documentos y trámites legales (PPT, cédula, pasaporte, visa, regularización, salvoconducto)",
    "humanitarian assistance": "ayuda humanitaria (comida, dinero, arriendo, subsidios, vivienda)",
    "employment": "empleo y trabajo",
    "services": "servicios de salud, educación, EPS o SISBÉN",
    "protection": "protección, seguridad, violencia o refugio",
    "journey information": "información de ruta, viaje, retorno o frontera",
    "organization search": "búsqueda de organizaciones o dónde acudir para ayuda",
}


def zeroshot_tint(messages, cache="cache/zeroshot_labels.parquet") -> pd.DataFrame:
    p = _ROOT / cache
    if p.exists():
        cached = pd.read_parquet(p)
        if list(cached["message"]) == list(messages):
            return cached
    from transformers import pipeline
    dev = 0 if _device() == "cuda" else -1
    clf = pipeline("zero-shot-classification",
                   model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", device=dev)
    cand = list(MMC_LABELS.values())
    inv = {v: k for k, v in MMC_LABELS.items()}
    res = clf(list(messages), cand, multi_label=False,
              hypothesis_template="Este mensaje trata sobre {}.")
    res = res if isinstance(res, list) else [res]
    rows = [{"message": m, "mmc_category": inv[r["labels"][0]], "conf": float(r["scores"][0])}
            for m, r in zip(messages, res)]
    out = pd.DataFrame(rows)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p)
    return out


def emotion_label(messages, cache="cache/emotion.parquet") -> pd.DataFrame:
    p = _ROOT / cache
    if p.exists():
        cached = pd.read_parquet(p)
        if list(cached["message"]) == list(messages):
            return cached
    import sys
    sys.path.insert(0, str(_ROOT / "src"))
    import mmc_text
    run = mmc_text.load_emotion_pipeline()
    res = run(list(messages))
    out = pd.DataFrame({"message": list(messages),
                        "emotion": [r["label"] for r in res],
                        "emo_score": [float(r["score"]) for r in res]})
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mmc_nlp_smoke.py -v`
Expected: PASS (downloads models on first run).

- [ ] **Step 5: Commit**

```bash
git add src/mmc_nlp.py tests/test_mmc_nlp_smoke.py
git commit -m "Add cached NLP builders: embeddings, zero-shot tint, emotion"
```

---

### Task 7: Build & cache full-corpus artifacts

**Files:**
- Create: `notebooks/_build_cache.py` (throwaway)

- [ ] **Step 1: Build all caches once (slow, ~30–40 min CPU)**

Create `notebooks/_build_cache.py`:
```python
import sys; sys.path.insert(0, "src")
import mmc_data, mmc_nlp
m = mmc_data.load_messages()
msgs = list(m["message"])
print("messages:", len(msgs))
mmc_nlp.embed_messages(msgs)
mmc_nlp.zeroshot_tint(msgs)
mmc_nlp.emotion_label(msgs)
print("caches built")
```
Run: `PYTHONIOENCODING=utf-8 uv run python notebooks/_build_cache.py`
Expected: creates `cache/emb_msg_e5.npy`, `cache/zeroshot_labels.parquet`, `cache/emotion.parquet`. Note the message count for later shape asserts.

- [ ] **Step 2: Sanity-check tint distribution**

Run:
```bash
uv run python -c "import pandas as pd; z=pd.read_parquet('cache/zeroshot_labels.parquet'); print(z['mmc_category'].value_counts()); print('low-conf share', (z['conf']<0.45).mean().round(3))"
```
Expected: 7 categories represented; low-conf share plausibly ~0.2–0.4 (the emergent/courtesy residual).

- [ ] **Step 3: Clean up + commit caches**

```bash
rm notebooks/_build_cache.py
git add cache/emb_msg_e5.npy cache/zeroshot_labels.parquet cache/emotion.parquet
git commit -m "Build + cache message-level NLP artifacts"
```

---

### Task 8: Notebook §1–§2 — spine, embedding, clustering

**Files:**
- Modify: `notebooks/analysis_responses.ipynb` (replace §1 and §2 cells)

- [ ] **Step 1: Rewrite §1 (Loading & cleaning) cell**

Load both `df` (user) and `msgs` (message) via `mmc_data`; attach cached zero-shot + emotion columns by exact message alignment; print shapes and `n_msgs_user` distribution. Include the "questions answered" markdown paragraph. Add `is_courtesy` column via `mmc_text.is_courtesy`.

- [ ] **Step 2: Rewrite §2 (Embedding & clustering) cell**

```python
import numpy as np, umap, hdbscan
emb = mmc_nlp.embed_messages(list(msgs["message"]))
reducer = umap.UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42)
red = reducer.fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5).fit_predict(red)
msgs["cluster"] = labels
print("n clusters:", len(set(labels)) - (1 if -1 in labels else 0), "| noise:", (labels == -1).sum())
```

- [ ] **Step 3: Add c-TF-IDF keyword helper cell**

Use `sklearn.feature_extraction.text.CountVectorizer(stop_words=mmc_text.SPANISH_STOPWORDS, ngram_range=(1,2))` per cluster to print top keywords.

- [ ] **Step 4: Execute the two sections**

Run: `cd notebooks && PYTHONIOENCODING=utf-8 uv run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 analysis_responses.ipynb`
Expected: runs without error; §2 prints a sensible cluster count (~12–20) using cached embeddings (fast).

- [ ] **Step 5: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Rebuild notebook §1–§2 on message-level spine"
```

---

### Task 9: Notebook §3 — MMC tinting + emergent detection + map

**Files:**
- Modify: `notebooks/analysis_responses.ipynb` (§3, §3.1)

- [ ] **Step 1: §3 tinting cell**

Attach `mmc_category`, `conf` from cache. Overwrite category with `"cortesía / no sustantivo"` where `is_courtesy` OR `conf < 0.45` AND courtesy. Build the per-cluster verdict table: for each cluster, dominant `mmc_category`, mean `conf`, share of `conf<0.45`, centroid→prototype margin (embed `MMC_LABELS` with `"passage: "`), keywords. Flag emergent = high low-conf share + low margin, or operational keywords.

- [ ] **Step 2: §3.1 2D cluster map cell**

```python
red2 = umap.UMAP(n_components=2, metric="cosine", random_state=42).fit_transform(emb)
# covered clusters muted grey; emergent clusters highlighted + labeled with counts (palette.py)
```

- [ ] **Step 3: Execute + eyeball emergent table**

Run the nbconvert execute command from Task 8 Step 4.
Expected: emergent table lists a small set of cross-cutting/operational themes with counts; map renders covered=grey, emergent=highlighted.

- [ ] **Step 4: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Rebuild §3 tinting + emergent detection + cluster map"
```

---

### Task 10: Notebook §4–§7 — needs, geo, temporal, demographics

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

- [ ] **Step 1: §4 needs/entities** — `mmc_entities.entity_counts(msgs["message"])`; cross with `mmc_category`; bar chart.
- [ ] **Step 2: §5 geographic** — per-message category volume across top `city_canon`; grouped bar / heatmap.
- [ ] **Step 3: §6 temporal** — category counts over `ts` with the per-user-ts caveat in markdown; event overlay.
- [ ] **Step 4: §7 demographics** — aggregate `mmc_category` to user; heatmaps by Gender / Age Ranges / Nationality.
- [ ] **Step 5: Execute** (nbconvert execute command). Expected: all render, no errors.
- [ ] **Step 6: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Rebuild §4–§7 cross-cuts on message spine"
```

---

### Task 11: Notebook §8–§9 — engagement, drop-off & reformulation

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

- [ ] **Step 1: §8 engagement depth** — `n_msgs_user` distribution (hist), median/quartiles.
- [ ] **Step 2: §9 drop-off + reformulation**:
  - Conversation-length distribution; `mmc_category` + `emotion` of the **last** message per user (`msg_idx == n_msgs_user-1`).
  - Reformulation: within each user, cosine similarity between consecutive message embeddings; flag pairs > 0.9 as repeats; report rate by category. Markdown states this is user-side only (no bot turns).
- [ ] **Step 3: Execute** (nbconvert). Expected: renders; last-message category/emotion table sensible.
- [ ] **Step 4: Commit**

```bash
git add notebooks/analysis_responses.ipynb
git commit -m "Rebuild §8–§9 engagement, drop-off & reformulation"
```

---

### Task 12: Notebook §10–§11 — sentiment+emotion, MEAL

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`

- [ ] **Step 1: §10 sentiment + emotion**:
  - 3-class valence via `cardiffnlp/twitter-xlm-roberta-base-sentiment` on `msgs["message"]` (cache to `cache/sentiment.parquet`, same pattern as `mmc_nlp`).
  - 7-class `emotion` from cache. Charts: emotion distribution, emotion×`mmc_category` heatmap, emotion×`city_canon`.
- [ ] **Step 2: §11 MEAL × topic** — `mmc_data.load_meal()`; join by `phone`; user's dominant `mmc_category` vs MEAL `utility`; stacked bar.
- [ ] **Step 3: Execute** (nbconvert). Expected: renders; sentiment/emotion cross-tabs populated.
- [ ] **Step 4: Commit**

```bash
git add notebooks/analysis_responses.ipynb cache/sentiment.parquet
git commit -m "Rebuild §10–§11 sentiment+emotion and MEAL cross-cut"
```

---

### Task 13: Notebook §12–§13 — geographic maps, data gaps, full run

**Files:**
- Modify: `notebooks/analysis_responses.ipynb`
- Modify: `README.md` (note the message-level rebuild)

- [ ] **Step 1: §12 geographic maps** — reuse cached `cache/colombia_boundary.gpkg`; curated `CITY_COORDS` for the priority `city_canon` cities. Three maps: (1) message volume per city (bubble size), (2) dominant `mmc_category` per city (MMC categorical palette), (3) mean sentiment/emotion per city (diverging). Clean labels, legends, Colombia basemap.
- [ ] **Step 2: §13 data gaps** — keep honest limitations: no bot output ⇒ no true fallback/consistency/turn-level drop-off; per-user timestamp; heuristic reformulation; `City Location` empty (curated coords).
- [ ] **Step 3: Full end-to-end execution**

Run: `cd notebooks && PYTHONIOENCODING=utf-8 uv run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=2400 analysis_responses.ipynb`
Expected: all 13 sections execute clean top-to-bottom using caches.

- [ ] **Step 4: Update README + commit**

```bash
git add notebooks/analysis_responses.ipynb README.md
git commit -m "Rebuild §12–§13 maps + data gaps; document message-level analysis"
```

---

### Task 14: Final verification

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 2: Confirm notebook has no stale user-level cells**

Grep the notebook JSON for leftover `df["Text"]` / old BERTopic usage; confirm none remain in modeling cells.

Run: `uv run python - <<'PY'`
```python
import json
nb = json.load(open("notebooks/analysis_responses.ipynb", encoding="utf-8"))
src = "\n".join("".join(c["source"]) for c in nb["cells"])
for bad in ['df["Text"]', "BERTopic(", "paraphrase-multilingual-MiniLM"]:
    print(bad, "->", src.count(bad))
```
Expected: all `-> 0`.

- [ ] **Step 3: Final commit if needed**

```bash
git add -A && git commit -m "Final message-level analysis verification" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage:** §1 spine (Task 2), city_canon/maps (Tasks 3, 13), stopwords/courtesy (Task 4), emotion model + validation (Task 5), embeddings/zero-shot/emotion caches (Tasks 6–7), §2 clustering (Task 8), §3 tinting+emergent+map (Task 9), §4–§7 (Task 10), §8–§9 drop-off/reformulation (Task 11), §10–§11 sentiment+emotion+MEAL (Task 12), §12–§13 maps+gaps (Task 13), GPU/CPU device + reproducibility caches (global constraint, Task 6), deps (Task 1). All spec sections mapped.

**Placeholder scan:** notebook-cell steps in Tasks 8–13 describe cells with concrete code for the load-bearing ones (spine, clustering, tinting, maps) and precise column/chart specs for the descriptive cells, matching the existing notebook's charting conventions; no "TBD/handle edge cases".

**Type consistency:** `load_messages` columns (`message, msg_idx, n_msgs_user, phone, city_canon, ts, ...`), `zeroshot_tint`→(`message, mmc_category, conf`), `emotion_label`→(`message, emotion, emo_score`), `city_canon`/`is_courtesy`/`SPANISH_STOPWORDS`/`load_emotion_pipeline` names are consistent across Tasks 2–13.
