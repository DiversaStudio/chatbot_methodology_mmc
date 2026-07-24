# SAMI Power BI Export Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `src/sami/export.py` + a `run_pipeline.py` father script that regenerate an `exports/` gold CSV layer from which every plot in NB1–NB3 can be reproduced in Power BI.

**Architecture:** `export.py` holds pure `build_*(frames) -> DataFrame` functions plus a `write_all()` orchestrator that PII-scans each frame and writes CSV + `_manifest.csv`. `run_pipeline.py` runs `load_sami()`, then (unless `--skip-nlp`) the GPU NLP via existing `nlp`/`clusters` modules, then `export.write_all()`. Notebooks and the script call the same `src/sami` functions — no logic duplication, only compute.

**Tech Stack:** Python 3.11+, pandas, existing `sami` package (`load_sami`, `metrics`, `taxonomy`, `clusters`, `nlp`, `validation`, `qa`), pytest, `uv`.

## Global Constraints

- **No notebook `to_csv`.** Export logic lives only in `export.py` / `run_pipeline.py` (spec R6). The one exception already in the repo — NB3 writing `validation/tone_gold_labels.csv` — stays.
- **PII gate.** Every frame passes `qa.pii_scan(frame) == []` before it is written; any hit aborts the whole write (spec R8).
- **Dimensional naming:** `dim_*` / `fact_*` / `agg_*` / `nlp_*` / `meta_run` / `parity_check` (spec R3).
- **Tone suppressed.** κ fails the 0.7 gate; `meta_run` carries `tone_gate_passed=false` and `sentiment_quotable=false` (spec R7). Sentiment ships as a label column, never as a published %.
- **`exports/` is committed** (user decision), alongside `_manifest.csv`.
- **Derivable-in-PBI charts are NOT exported as their own table.** Gender / age / minors / away-duration / nationality → from `dim_user`; category share, city×category mix, negative-by-category, 3-class-tone-by-category, sentiment distribution → from `fact_message` (carries `dominant_category`, `city_canon`, `sentiment_label`). Only tables Power BI cannot faithfully recompute get a CSV.
- **`build_*` functions are pure and I/O-free.** Only `write_all` and `run_pipeline.py` touch disk.
- Run every command from the repo root. Tests run with `PYTHONPATH=src`. Env: `.venv/Scripts/python.exe` (Windows).
- Reconciliation metric labels (exact strings, from `qa.reconciliation_table`): `users`, `records`, `messages`, `users_with_text`, `meal_responses`, `meal_response_rate_pct`, `legal_documentation_pct`, `repeat_askers_pct`, `negative_tone_pct`.

---

## File Structure

- Create `src/sami/export.py` — all `build_*` functions, module constants (`CAT_EN`, `PROBE_EN`, `RATING_NUM`), `write_all`.
- Create `run_pipeline.py` (repo root) — CLI father script; the only caller of `export.write_all`.
- Create `tests/test_export.py` — schema / PII / parity / determinism / manifest tests.
- Create `exports/.gitkeep` and `exports/_schema.md` — committed output dir + human schema doc.
- Modify `README.md` — add an "Export layer / Power BI" section.

---

### Task 1: Scaffold `export.py` + `dim_category` + `dim_user`

**Files:**
- Create: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `sami.load_sami` (`SD.responses`, `SD.messages`), `qa.pii_scan`.
- Produces:
  - `CAT_EN: dict[str,str]`, `PROBE_EN: dict[str,str]`, `RATING_NUM: dict[str,int]`
  - `build_dim_category() -> DataFrame[category_key, category_es, category_en]`
  - `build_dim_user(responses, messages, lab=None) -> DataFrame` (1 row/user)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export.py
import numpy as np
import pandas as pd
import pytest
from sami import load_sami, export


@pytest.fixture(scope="module")
def SD():
    return load_sami()


def test_dim_category_schema():
    d = export.build_dim_category()
    assert list(d.columns) == ["category_key", "category_es", "category_en"]
    assert "legal_documentation" in set(d["category_key"])
    assert d["category_key"].is_unique


def test_dim_user_one_row_per_user(SD):
    d = export.build_dim_user(SD.responses, SD.messages)
    assert d["user_id"].is_unique
    assert d["user_id"].nunique() == SD.responses["user_id"].nunique()
    for col in ["user_id", "gender_clean", "age_num", "department",
                "n_msgs_user", "has_text", "cluster_id"]:
        assert col in d.columns
    # has_text == user appears in the message spine
    assert int(d["has_text"].sum()) == SD.messages["user_id"].nunique()
    # cluster_id is null without an NLP label map
    assert d["cluster_id"].isna().all()


def test_dim_user_no_pii(SD):
    from sami import qa
    assert qa.pii_scan(export.build_dim_user(SD.responses, SD.messages)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sami.export'` (or AttributeError).

- [ ] **Step 3: Write minimal implementation**

```python
# src/sami/export.py
"""Power BI gold-layer builders + writer.

Pure `build_*(frames) -> DataFrame` functions (no I/O) plus `write_all`, the only
function that touches disk. `run_pipeline.py` is the sole production caller. See
docs/superpowers/specs/2026-07-24-sami-exports-powerbi-design.md.
"""
from __future__ import annotations
import pandas as pd

from . import metrics, taxonomy, qa

# EN display for the official categories (chart text only) — mirrors the notebooks.
CAT_EN = {
    "legal_documentation": "Legal & documentation",
    "humanitarian_assistance": "Humanitarian assistance",
    "protection": "Protection",
    "employment": "Employment",
    "organization_search": "Finding organizations",
    "journey_information": "Journey information",
    "services": "Services",
    "unclassified": "Unclassified",
}
# EN display for the emergent-need probes (mirrors NB3).
PROBE_EN = {
    "transport_logistics": "Transport & movement",
    "entrepreneurship": "Enterprise & livelihood",
    "procedure_troubleshooting": "Stuck in a procedure",
    "human_handoff": "Reach a person",
    "fraud_protection": "Fraud & scams",
    "connectivity": "Connectivity / phone",
}
# Ordinal 1-5 keyed to the observed MEAL usefulness vocabulary (mirrors NB2).
RATING_NUM = {
    "Muy útil": 5, "Útil": 4, "Medianamente útil": 3, "Poco útil": 2, "Nada útil": 1,
}

# Profile columns collapsed one-row-per-user (first non-null in ts order).
_PROFILE_COLS = [
    "gender_clean", "age_num", "age_flag", "city_canon", "department",
    "nationality_canon", "away_duration_canon", "away_duration_order",
    "city_duration_canon", "city_duration_order", "dominant_category", "n_questions",
]
# Raw survey columns that carry into dim_user under friendlier names.
_RAW_RENAME = {"Minors": "minors", "Age Ranges": "age_range",
               "Destination_Country": "destination_country"}


def build_dim_category() -> pd.DataFrame:
    return pd.DataFrame(
        [{"category_key": k, "category_es": k, "category_en": v} for k, v in CAT_EN.items()]
    )


def build_dim_user(responses: pd.DataFrame, messages: pd.DataFrame,
                   lab: "pd.Series | None" = None) -> pd.DataFrame:
    """One row per user. `lab` (Series indexed by user_id -> archetype) fills
    `cluster_id`; None leaves it null (the --skip-nlp contract)."""
    r = responses.sort_values("ts", kind="stable")
    cols = [c for c in _PROFILE_COLS if c in r.columns]
    agg = r.groupby("user_id")[cols].first()
    for raw, new in _RAW_RENAME.items():
        if raw in r.columns:
            agg[new] = r.groupby("user_id")[raw].first()
    mpu = messages.groupby("user_id").size()
    agg["n_msgs_user"] = agg.index.to_series().map(mpu).fillna(0).astype(int)
    agg["has_text"] = agg["n_msgs_user"] > 0
    agg["cluster_id"] = (agg.index.to_series().map(lab.to_dict())
                         if lab is not None else pd.NA)
    return agg.reset_index()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): export.py scaffold + dim_category, dim_user"
```

---

### Task 2: `fact_message` + `fact_meal`

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `SD.messages` (index = message_id), `SD.meal`; optional `sentiment` (from `nlp.sentiment_messages`, index-aligned to messages, col `label`) and `lab`.
- Produces:
  - `build_fact_message(messages, sentiment=None, lab=None) -> DataFrame[message_id, user_id, ts, city_canon, dominant_category, seq, n_msgs_user, message, sentiment_label, cluster_id]`
  - `build_fact_meal(meal) -> DataFrame[user_id, ts, usefulness_rating, rating_num, would_recommend, recommendation_text, discovery_channel]`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
def test_fact_message_grain_and_join(SD):
    f = export.build_fact_message(SD.messages)
    assert len(f) == len(SD.messages)
    assert f["message_id"].is_unique
    assert list(f["message_id"]) == list(SD.messages.index)
    assert f["sentiment_label"].isna().all()   # no sentiment passed
    assert f["cluster_id"].isna().all()


def test_fact_message_sentiment_join(SD):
    # synthetic sentiment aligned to the messages index
    sent = pd.DataFrame({"label": ["negative"] * len(SD.messages)}, index=SD.messages.index)
    f = export.build_fact_message(SD.messages, sentiment=sent)
    assert (f["sentiment_label"] == "negative").all()


def test_fact_meal_rating_num(SD):
    f = export.build_fact_meal(SD.meal)
    assert f["user_id"].is_unique
    assert "rating_num" in f.columns
    # rating_num is 1-5 or NaN, never a raw string
    vals = f["rating_num"].dropna().unique()
    assert set(vals).issubset({1, 2, 3, 4, 5})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "fact" -q`
Expected: FAIL — `AttributeError: module 'sami.export' has no attribute 'build_fact_message'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/sami/export.py
_FACT_MSG_COLS = ["message_id", "user_id", "ts", "city_canon",
                  "dominant_category", "seq", "n_msgs_user", "message"]


def build_fact_message(messages: pd.DataFrame, sentiment: "pd.DataFrame | None" = None,
                       lab: "pd.Series | None" = None) -> pd.DataFrame:
    f = messages.reset_index().rename(columns={"index": "message_id"})
    f = f[[c for c in _FACT_MSG_COLS if c in f.columns]].copy()
    f["sentiment_label"] = (sentiment.loc[messages.index, "label"].values
                            if sentiment is not None else pd.NA)
    f["cluster_id"] = (f["user_id"].map(lab.to_dict()) if lab is not None else pd.NA)
    return f


_FACT_MEAL_COLS = ["user_id", "ts", "usefulness_rating", "rating_num",
                   "would_recommend", "recommendation_text", "discovery_channel"]


def build_fact_meal(meal: pd.DataFrame) -> pd.DataFrame:
    f = meal.copy()
    f["rating_num"] = f["usefulness_rating"].map(RATING_NUM)
    return f[[c for c in _FACT_MEAL_COLS if c in f.columns]].copy()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "fact" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): fact_message + fact_meal builders"
```

---

### Task 3: Computed aggregates (`agg_*`)

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `metrics.funnel_stages`, `metrics.weekly_category_counts`, `metrics.priority_matrix_frame`, `taxonomy.entity_counts_by_kind`; `build_dim_user`/`build_fact_meal` outputs.
- Produces:
  - `build_agg_city(dim_user) -> [city_canon, department, n_users]`
  - `build_agg_funnel(responses, messages, meal) -> [stage_order, stage, n, conversion_from_prev]`
  - `build_agg_entities_by_kind(messages) -> [kind, entity, n]`
  - `build_agg_weekly_category(messages) -> [week, category, n]`
  - `build_agg_daily_volume(messages) -> [day, n]`
  - `build_agg_weekly_rating(fact_meal) -> [week, mean_rating, n]`
  - `build_agg_priority_matrix(messages, fact_meal, dim_user, neg_by_cat=None) -> [category, messages, users, pct_repeat, mean_rating, meal_n, rating_is_fallback, n_axes, unmet_need, (pct_negative)]`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
def test_agg_city(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    c = export.build_agg_city(du)
    assert list(c.columns) == ["city_canon", "department", "n_users"]
    assert c["n_users"].sum() == len(du)


def test_agg_funnel_top_equals_users(SD):
    f = export.build_agg_funnel(SD.responses, SD.messages, SD.meal)
    assert list(f.columns[:3]) == ["stage_order", "stage", "n"]
    assert int(f["n"].iloc[0]) == SD.responses["user_id"].nunique()


def test_agg_entities_by_kind(SD):
    e = export.build_agg_entities_by_kind(SD.messages)
    assert set(e.columns) == {"kind", "entity", "n"}
    assert (e["n"] > 0).all()


def test_agg_weekly_category_long(SD):
    w = export.build_agg_weekly_category(SD.messages)
    assert set(w.columns) == {"week", "category", "n"}


def test_agg_daily_volume(SD):
    d = export.build_agg_daily_volume(SD.messages)
    assert set(d.columns) == {"day", "n"}
    assert d["n"].sum() == SD.messages["ts"].notna().sum()


def test_agg_priority_matrix_no_sentiment(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    fm = export.build_fact_meal(SD.meal)
    pm = export.build_agg_priority_matrix(SD.messages, fm, du)
    assert "category" in pm.columns and "unmet_need" in pm.columns
    assert "unclassified" not in set(pm["category"])   # excluded
    assert (pm["n_axes"] <= 2).all()                    # no sentiment axis
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "agg" -q`
Expected: FAIL — `AttributeError: ... has no attribute 'build_agg_city'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/sami/export.py
def build_agg_city(dim_user: pd.DataFrame) -> pd.DataFrame:
    return (dim_user.groupby(["city_canon", "department"], dropna=False)
            .size().reset_index(name="n_users"))


def build_agg_funnel(responses, messages, meal) -> pd.DataFrame:
    f = metrics.funnel_stages(responses, messages, meal).reset_index(drop=True)
    f.insert(0, "stage_order", range(len(f)))
    return f


def build_agg_entities_by_kind(messages: pd.DataFrame) -> pd.DataFrame:
    by_kind = taxonomy.entity_counts_by_kind(messages["message"])
    rows = [{"kind": kind, "entity": ent, "n": int(n)}
            for kind, s in by_kind.items() for ent, n in s.items()]
    return pd.DataFrame(rows, columns=["kind", "entity", "n"])


def build_agg_weekly_category(messages: pd.DataFrame) -> pd.DataFrame:
    wk = metrics.weekly_category_counts(messages, top_n=4)
    return (wk.reset_index()
            .melt(id_vars="week_start", var_name="category", value_name="n")
            .rename(columns={"week_start": "week"}))


def build_agg_daily_volume(messages: pd.DataFrame) -> pd.DataFrame:
    d = messages.dropna(subset=["ts"]).set_index("ts").resample("D").size()
    return d.reset_index(name="n").rename(columns={"ts": "day"})


def build_agg_weekly_rating(fact_meal: pd.DataFrame) -> pd.DataFrame:
    m = (fact_meal.dropna(subset=["ts", "rating_num"]).set_index("ts")
         .resample("W")["rating_num"].agg(["mean", "count"]))
    return m.reset_index().rename(columns={"ts": "week", "mean": "mean_rating",
                                           "count": "n"})


def build_agg_priority_matrix(messages, fact_meal, dim_user,
                              neg_by_cat: "pd.Series | None" = None) -> pd.DataFrame:
    msgs_pm = messages[messages["dominant_category"] != "unclassified"]
    meal_cat = fact_meal.merge(
        dim_user[["user_id", "dominant_category"]].drop_duplicates("user_id"),
        on="user_id", how="left")
    pm = metrics.priority_matrix_frame(msgs_pm, meal_cat, neg_by_category=neg_by_cat)
    return pm.reset_index().rename(columns={"dominant_category": "category"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "agg" -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): computed aggregate builders (funnel, entities, time series, priority matrix)"
```

---

### Task 4: NLP builders (`dim_cluster`, `nlp_*`)

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `clusters.archetype_profiles` output (`prof`, index `archetype`), `clusters.project_2d` (`XY` ndarray), `clusters.ctfidf_terms` (`terms` dict), `validation.validation_report` (`report`, `report["confusion"]` with index name `human`, cols name `model`, labels `negative`/`not_negative`), `SD.messages` merged with labels, `taxonomy.ARCHETYPE_NAMES` / `CANDIDATE_INTENT_PROBES`.
- Produces:
  - `build_dim_cluster(prof, names) -> [cluster_id, name, n_users, n_messages, median_age, top_categories]`
  - `build_nlp_umap(XY, labels, user_ids) -> [user_id, x, y, cluster_id]`
  - `build_nlp_cluster_terms(terms) -> [cluster_id, rank, term, weight]`
  - `build_nlp_emergent_themes(messages) -> [theme, slug, n_messages, n_users]`
  - `build_nlp_tone_confusion(report) -> [human_label, model_label, n]`
  - `build_nlp_voices(msgs_lab, names) -> [cluster_id, name, message]`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
def test_nlp_umap_synthetic():
    XY = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
    labels = np.array([0, 1, 0])
    user_ids = ["u1", "u2", "u3"]
    u = export.build_nlp_umap(XY, labels, user_ids)
    assert list(u.columns) == ["user_id", "x", "y", "cluster_id"]
    assert list(u["user_id"]) == user_ids
    assert u["x"].iloc[1] == 0.3


def test_nlp_cluster_terms_synthetic():
    terms = {0: pd.Series({"cita": 0.9, "pasaporte": 0.7}),
             1: pd.Series({"trabajo": 0.8})}
    t = export.build_nlp_cluster_terms(terms)
    assert set(t.columns) == {"cluster_id", "rank", "term", "weight"}
    assert t[(t.cluster_id == 0) & (t["rank"] == 0)]["term"].iloc[0] == "cita"


def test_nlp_tone_confusion_synthetic():
    cats = ["negative", "not_negative"]
    cm = pd.DataFrame([[5, 2], [3, 90]], index=cats, columns=cats)
    cm.index.name, cm.columns.name = "human", "model"
    report = {"confusion": cm}
    c = export.build_nlp_tone_confusion(report)
    assert set(c.columns) == {"human_label", "model_label", "n"}
    assert int(c[(c.human_label == "negative") & (c.model_label == "negative")]["n"].iloc[0]) == 5
    assert c["n"].sum() == 100


def test_nlp_emergent_themes(SD):
    e = export.build_nlp_emergent_themes(SD.messages)
    assert set(e.columns) == {"theme", "slug", "n_messages", "n_users"}
    assert (e["n_users"] >= 0).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "nlp" -q`
Expected: FAIL — `AttributeError: ... has no attribute 'build_nlp_umap'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/sami/export.py
def build_dim_cluster(prof: pd.DataFrame, names: dict) -> pd.DataFrame:
    d = prof.reset_index().rename(columns={"archetype": "cluster_id"})
    d["name"] = d["cluster_id"].map(names)
    cols = ["cluster_id", "name", "n_users", "n_messages", "median_age", "top_categories"]
    return d[[c for c in cols if c in d.columns]]


def build_nlp_umap(XY, labels, user_ids) -> pd.DataFrame:
    return pd.DataFrame({"user_id": list(user_ids), "x": XY[:, 0], "y": XY[:, 1],
                         "cluster_id": list(labels)})


def build_nlp_cluster_terms(terms: dict) -> pd.DataFrame:
    rows = [{"cluster_id": cid, "rank": rank, "term": term, "weight": float(w)}
            for cid, s in terms.items()
            for rank, (term, w) in enumerate(s.items())]
    return pd.DataFrame(rows, columns=["cluster_id", "rank", "term", "weight"])


def build_nlp_emergent_themes(messages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for slug, pat in taxonomy.CANDIDATE_INTENT_PROBES.items():
        hit = messages["message"].str.contains(pat, case=False, regex=True, na=False)
        rows.append({"theme": PROBE_EN.get(slug, slug), "slug": slug,
                     "n_messages": int(hit.sum()),
                     "n_users": int(messages.loc[hit, "user_id"].nunique())})
    return (pd.DataFrame(rows).sort_values("n_users", ascending=False)
            .reset_index(drop=True))


def build_nlp_tone_confusion(report: dict) -> pd.DataFrame:
    cm = report["confusion"]
    long = (cm.reset_index()
            .melt(id_vars=cm.index.name, var_name=cm.columns.name, value_name="n"))
    return long.rename(columns={cm.index.name: "human_label",
                                cm.columns.name: "model_label"})


def build_nlp_voices(msgs_lab: pd.DataFrame, names: dict) -> pd.DataFrame:
    rows = []
    for cid in sorted(msgs_lab["archetype"].unique()):
        marker = taxonomy.ARCHETYPE_NAMES[cid]["marker"]
        g = (msgs_lab[(msgs_lab["archetype"] == cid)
                      & msgs_lab["message"].str.len().between(60, 190)
                      & msgs_lab["message"].str.contains(marker, case=False, na=False)]
             .sort_values(["user_id", "seq"], kind="stable"))
        rows.append({"cluster_id": int(cid), "name": names.get(cid),
                     "message": g["message"].iloc[0] if len(g) else "—"})
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "nlp" -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): NLP builders (dim_cluster, umap, cluster_terms, emergent_themes, tone_confusion, voices)"
```

---

### Task 5: `meta_run` + `parity_check`

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `SD.run_meta` (dict), `SD.reconciliation` (`metric`/`value`), `build_dim_user`/`build_fact_message`/`build_fact_meal` outputs.
- Produces:
  - `build_meta_run(run_meta, nlp_meta=None) -> [key, value]`
  - `build_parity_check(reconciliation, dim_user, fact_message, fact_meal) -> [metric, exported_value, reconciliation_value, match]`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
def test_meta_run_flags():
    m = export.build_meta_run({"responses_file": "x.xlsx", "checks": [("P1", True)]},
                              nlp_meta={"tone_gate_passed": False,
                                        "sentiment_quotable": False, "nlp_included": True})
    kv = dict(zip(m["key"], m["value"]))
    assert "checks" not in kv                          # dropped (not scalar)
    assert kv["tone_gate_passed"] == "False"
    assert kv["sentiment_quotable"] == "False"


def test_parity_check_all_match(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    fmsg = export.build_fact_message(SD.messages)
    fmeal = export.build_fact_meal(SD.meal)
    p = export.build_parity_check(SD.reconciliation, du, fmsg, fmeal)
    assert set(p.columns) == {"metric", "exported_value", "reconciliation_value", "match"}
    assert p["match"].all(), p[~p["match"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "meta or parity" -q`
Expected: FAIL — `AttributeError: ... has no attribute 'build_meta_run'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/sami/export.py
def build_meta_run(run_meta: dict, nlp_meta: "dict | None" = None) -> pd.DataFrame:
    merged = {k: v for k, v in run_meta.items() if k != "checks"}
    if nlp_meta:
        merged.update(nlp_meta)
    return pd.DataFrame([{"key": k, "value": str(v)} for k, v in merged.items()])


# exported-key -> reconciliation metric label
_PARITY_MAP = {
    "users": "users",
    "messages": "messages",
    "users_with_text": "users_with_text",
    "meal_responses": "meal_responses",
}


def build_parity_check(reconciliation, dim_user, fact_message, fact_meal) -> pd.DataFrame:
    recon = reconciliation.set_index("metric")["value"].to_dict()
    exported = {
        "users": dim_user["user_id"].nunique(),
        "messages": len(fact_message),
        "users_with_text": int(dim_user["has_text"].sum()),
        "meal_responses": len(fact_meal),
    }
    rows = []
    for key, val in exported.items():
        rv = recon.get(_PARITY_MAP[key])
        rows.append({"metric": key, "exported_value": int(val),
                     "reconciliation_value": rv,
                     "match": rv is not None and int(rv) == int(val)})
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "meta or parity" -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): meta_run + parity_check builders"
```

---

### Task 6: `write_all` orchestrator (PII gate + manifest)

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: every `build_*` from Tasks 1-5, `qa.pii_scan`.
- Produces: `write_all(out_dir, tables) -> DataFrame` (the manifest). `tables` is a `dict[str, DataFrame]` of `{table_name: frame}`. Writes `<name>.csv` (UTF-8, no index) for each + `_manifest.csv`. Raises `ValueError` if any frame fails the PII scan (nothing is written).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
def test_write_all_writes_and_manifests(tmp_path):
    tables = {
        "dim_category": export.build_dim_category(),
        "tiny": pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}),
    }
    manifest = export.write_all(tmp_path, tables)
    assert (tmp_path / "dim_category.csv").exists()
    assert (tmp_path / "tiny.csv").exists()
    assert (tmp_path / "_manifest.csv").exists()
    assert set(manifest["table"]) == {"dim_category", "tiny"}
    assert int(manifest.set_index("table").loc["tiny", "rows"]) == 2


def test_write_all_aborts_on_pii(tmp_path):
    bad = pd.DataFrame({"txt": ["reach me at whatsapp:+573001234567"]})
    with pytest.raises(ValueError, match="PII"):
        export.write_all(tmp_path, {"bad": bad})
    assert not (tmp_path / "bad.csv").exists()          # nothing partially written
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "write_all" -q`
Expected: FAIL — `AttributeError: ... has no attribute 'write_all'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/sami/export.py
import hashlib
from pathlib import Path


def write_all(out_dir, tables: dict) -> pd.DataFrame:
    """PII-scan every frame, then write each as CSV + a _manifest.csv. Scans run
    before any write, so a violation leaves the directory untouched."""
    out = Path(out_dir)
    for name, frame in tables.items():
        hits = qa.pii_scan(frame)
        if hits:
            raise ValueError(f"PII in table '{name}': {hits[:3]}")
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, frame in tables.items():
        path = out / f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8")
        sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
        manifest.append({"table": name, "rows": len(frame),
                         "columns": ",".join(map(str, frame.columns)), "sha1": sha1})
    man = pd.DataFrame(manifest).sort_values("table").reset_index(drop=True)
    man.to_csv(out / "_manifest.csv", index=False, encoding="utf-8")
    return man
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -q`
Expected: PASS (all tests, ~21).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): write_all orchestrator with PII gate and manifest"
```

---

### Task 7: `run_pipeline.py` father script

**Files:**
- Create: `run_pipeline.py`
- Create: `exports/.gitkeep`

**Interfaces:**
- Consumes: `load_sami`, `nlp`, `clusters`, `validation`, `metrics`, `taxonomy`, all `export.build_*`, `export.write_all`.
- Produces: CLI `python run_pipeline.py [--out exports] [--skip-nlp] [--responses PATH] [--meal PATH]`. Exits non-zero if any `parity_check` row is `match=False`.

- [ ] **Step 1: Write the script**

```python
# run_pipeline.py
"""Father script: run the whole SAMI pipeline and regenerate the exports/ gold layer.

    python run_pipeline.py                 # full run incl. GPU NLP -> all tables
    python run_pipeline.py --skip-nlp      # fast CPU run, non-NLP tables only

Every table Power BI cannot recompute (UMAP, c-TF-IDF, confusion, funnel,
priority matrix, entity extraction) is written here; simple aggregates are left
for Power BI to derive from dim_user / fact_message / fact_meal.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from sami import load_sami, nlp, clusters, validation, metrics, taxonomy, export  # noqa: E402

RANDOM_STATE = 0


def _nlp_tables(SD):
    """Run the GPU NLP once and build every NLP-dependent table. Returns
    (tables_dict, nlp_meta_dict, sentiment_frame, lab_series)."""
    docs = nlp.user_documents(SD.messages)
    X = nlp.embed_documents(docs["doc"].tolist())

    scan = clusters.k_scan(X, k_range=range(4, 13), random_state=RANDOM_STATE)
    stab_curve = clusters.stability_curve(X, k_range=range(3, 9), n_boot=30,
                                          random_state=RANDOM_STATE)
    K = clusters.choose_k(scan, stability_by_k=stab_curve)
    labels = KMeans(n_clusters=K, n_init=10, random_state=RANDOM_STATE).fit(X).labels_
    lab = pd.Series(labels, index=docs["user_id"].values, name="archetype")

    terms = clusters.ctfidf_terms(docs["doc"].tolist(), labels, top_n=40)
    taxonomy.assert_archetype_mapping(terms)
    names = {c: taxonomy.ARCHETYPE_NAMES[c]["name"] for c in sorted(terms)}
    XY = clusters.project_2d(X, method="umap", random_state=RANDOM_STATE)

    sent = nlp.sentiment_messages(SD.messages)
    prof = clusters.archetype_profiles(lab, SD.responses, SD.messages)
    msgs_lab = SD.messages.merge(lab, left_on="user_id", right_index=True, how="inner")

    analyst = pd.read_csv("validation/tone_labels_analyst.csv", encoding="utf-8")
    report = validation.validation_report(
        analyst["label_analyst"], sent.loc[analyst["message_id"], "label"])
    stab = clusters.stability_ari(X, K, n_boot=50, random_state=RANDOM_STATE)
    dev = nlp.device_report()

    tables = {
        "dim_cluster": export.build_dim_cluster(prof, names),
        "nlp_umap": export.build_nlp_umap(XY, labels, docs["user_id"].values),
        "nlp_cluster_terms": export.build_nlp_cluster_terms(terms),
        "nlp_emergent_themes": export.build_nlp_emergent_themes(SD.messages),
        "nlp_tone_confusion": export.build_nlp_tone_confusion(report),
        "nlp_voices": export.build_nlp_voices(msgs_lab, names),
    }
    nlp_meta = {
        "embed_model": dev["embed_model"], "sentiment_model": dev["sentiment_model"],
        "chosen_k": K, "stability_ari": round(stab["mean_ari"], 3),
        "tone_kappa": round(report["kappa"], 3),
        "tone_gate_passed": report["gate_passed"], "sentiment_quotable": report["gate_passed"],
        "nlp_included": True,
    }
    return tables, nlp_meta, sent, lab


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Regenerate the SAMI exports/ gold layer.")
    ap.add_argument("--out", default="exports")
    ap.add_argument("--skip-nlp", action="store_true")
    ap.add_argument("--responses", default=None)
    ap.add_argument("--meal", default=None)
    args = ap.parse_args(argv)

    SD = load_sami(responses_path=args.responses, meal_path=args.meal)

    sent = lab = None
    nlp_tables, nlp_meta = {}, {"nlp_included": False,
                               "tone_gate_passed": False, "sentiment_quotable": False}
    if not args.skip_nlp:
        nlp_tables, nlp_meta, sent, lab = _nlp_tables(SD)

    neg_by_cat = None
    if sent is not None:
        msgs_pm = SD.messages[SD.messages["dominant_category"] != "unclassified"]
        neg_by_cat = metrics.negative_by_category(msgs_pm, sent)

    dim_user = export.build_dim_user(SD.responses, SD.messages, lab=lab)
    fact_message = export.build_fact_message(SD.messages, sentiment=sent, lab=lab)
    fact_meal = export.build_fact_meal(SD.meal)

    tables = {
        "dim_user": dim_user,
        "fact_message": fact_message,
        "fact_meal": fact_meal,
        "dim_category": export.build_dim_category(),
        "agg_city": export.build_agg_city(dim_user),
        "agg_funnel": export.build_agg_funnel(SD.responses, SD.messages, SD.meal),
        "agg_entities_by_kind": export.build_agg_entities_by_kind(SD.messages),
        "agg_weekly_category": export.build_agg_weekly_category(SD.messages),
        "agg_daily_volume": export.build_agg_daily_volume(SD.messages),
        "agg_weekly_rating": export.build_agg_weekly_rating(fact_meal),
        "agg_priority_matrix": export.build_agg_priority_matrix(
            SD.messages, fact_meal, dim_user, neg_by_cat=neg_by_cat),
        "meta_run": export.build_meta_run(SD.run_meta, nlp_meta=nlp_meta),
        "parity_check": export.build_parity_check(
            SD.reconciliation, dim_user, fact_message, fact_meal),
    }
    tables.update(nlp_tables)

    manifest = export.write_all(args.out, tables)
    parity = tables["parity_check"]
    print(manifest.to_string(index=False))
    print("\nparity_check:")
    print(parity.to_string(index=False))
    if not parity["match"].all():
        print("\nPARITY FAILED", file=sys.stderr)
        return 1
    print(f"\nwrote {len(tables)} tables to {args.out}/ · NLP={'no' if args.skip_nlp else 'yes'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Create the committed output dir marker**

```bash
mkdir -p exports && touch exports/.gitkeep
```

- [ ] **Step 3: Acceptance run — fast path (no GPU)**

Run: `.venv/Scripts/python.exe run_pipeline.py --skip-nlp`
Expected: prints a manifest of 13 tables + a `parity_check` where every `match` is `True`; exit 0; `exports/*.csv` + `exports/_manifest.csv` written; no `nlp_*` files.

- [ ] **Step 4: Acceptance run — full path (GPU NLP)**

Run: `.venv/Scripts/python.exe run_pipeline.py`
Expected: additionally writes `dim_cluster`, `nlp_umap`, `nlp_cluster_terms`, `nlp_emergent_themes`, `nlp_tone_confusion`, `nlp_voices`; `dim_user.cluster_id` / `fact_message.sentiment_label` populated; parity still all-match; exit 0. (First run downloads the embedding/sentiment models; needs the CUDA build for speed, CPU fallback works but is slow.)

- [ ] **Step 5: Verify no PII slipped into the written CSVs**

Run:
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import pandas as pd, glob; from sami import qa; [print(f, qa.pii_scan(pd.read_csv(f))) for f in glob.glob('exports/*.csv')]"
```
Expected: every file prints `[]`.

- [ ] **Step 6: Commit**

```bash
git add run_pipeline.py exports/
git commit -m "feat(sami): run_pipeline.py father script + generated exports/ gold layer"
```

---

### Task 8: Docs + schema reference + memory

**Files:**
- Create: `exports/_schema.md`
- Modify: `README.md`

- [ ] **Step 1: Write the schema reference**

Create `exports/_schema.md` documenting each table: its grain, columns, the notebook plot(s) it feeds, and the note that gender/age/minors/away-duration/nationality and all sentiment-by-category charts are built in Power BI from `dim_user` / `fact_message`. Include the §3 traceability table from the design spec verbatim, plus a one-line "regenerate with `python run_pipeline.py`".

- [ ] **Step 2: Add a README section**

Add an "## Export layer (Power BI)" section after "Getting Started" describing: `python run_pipeline.py` regenerates `exports/`; `--skip-nlp` for a fast CPU run; tone is directional-only (κ gate); `exports/` is committed; point to `exports/_schema.md` and the design spec.

- [ ] **Step 3: Run the full test suite green**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (existing suite + `tests/test_export.py`).

- [ ] **Step 4: Commit**

```bash
git add exports/_schema.md README.md
git commit -m "docs(sami): exports/ schema reference + README export-layer section"
```

- [ ] **Step 5: Update memory**

Update `sami_pipeline_rework.md` (mark the exports + run_pipeline sub-project done, list the table set) and reconcile `feedback_self_contained_notebooks.md` / `feedback_no_cache_inline_gpu.md` (note the foundation spec's direction note supersedes them for the SAMI project). Add the one-line pointers to `MEMORY.md` if a new memory file is created.

---

## Self-Review

**1. Spec coverage:**
- R1 all plots reproducible → Tasks 1-6 build every non-derivable table; Global Constraints list the PBI-derivable ones. Task 8 schema doc makes the plot→table map explicit. ✓
- R2 hybrid grain → row-level `dim_user`/`fact_message`/`fact_meal` (Tasks 1-2) + computed/NLP tables (Tasks 3-4). ✓
- R3 dimensional naming → used throughout. ✓
- R4 run_pipeline + `--skip-nlp` default-on NLP → Task 7. ✓
- R5 parity verification → Task 5 `build_parity_check`, enforced non-zero exit in Task 7. ✓
- R6 no notebook to_csv → Global Constraints; nothing in the plan edits notebooks. ✓
- R7 tone suppression → `nlp_meta` flags in Task 7, asserted in Task 5 test. ✓
- R8 PII gate → Task 6 `write_all`, tested; Task 7 Step 5 re-scans written files. ✓

**2. Placeholder scan:** No TBD/TODO. Task 8 Steps 1-2 describe doc prose (not code) — acceptable, they are documentation steps with explicit content requirements. All code steps carry full implementations.

**3. Type consistency:** `build_*` signatures in each task's Interfaces match their Task 7 call sites (`build_dim_user(..., lab=lab)`, `build_fact_message(..., sentiment=sent, lab=lab)`, `build_agg_priority_matrix(SD.messages, fact_meal, dim_user, neg_by_cat=...)`, `build_meta_run(run_meta, nlp_meta=...)`). Confusion melt uses `cm.index.name`/`cm.columns.name` which are `human`/`model` per `validation_report`. `lab` is a Series indexed by user_id in both `build_dim_user`/`build_fact_message` (`.to_dict()`) and `archetype_profiles`/`build_nlp_voices` (merge on index). Consistent. ✓
