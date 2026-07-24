# Dashboard Gold-Layer Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the gold-layer fields the Power BI dashboard spec needs (`dim_city` with coordinates, category colors, per-user flags, text-free `fact_message`, `schema_version`) so the 3-tab/12-visual dashboard is buildable numbers-identical-by-construction.

**Architecture:** Extend the existing pure `build_*` functions in `src/sami/export.py` + one `canon` constant; rewire `run_pipeline.py` to emit `dim_city` instead of `agg_city`. Everything additive; table count stays 19.

**Tech Stack:** Python 3.11+, pandas, existing `sami` package, pytest, `uv`.

## Global Constraints

- All new fields are **Python-computed in the gold layer**, never in DAX (dashboard Rule 4 — keeps notebook/dashboard numbers identical by construction).
- `is_repeat_asker` MUST use the exact definition behind `reconciliation.repeat_askers_pct`: `q = responses.groupby("user_id")["n_questions"].max()`; `p90 = q.quantile(0.90)`; flag = `q >= p90`.
- `build_*` functions stay PURE and I/O-free; only `write_all`/`run_pipeline.py` touch disk.
- PII scan stays green on every frame; determinism preserved (only `meta_run.generated_at` varies).
- Category colors/order come from `theme.CAT` (fixed order) over `taxonomy.OFFICIAL_CATEGORIES + ["unclassified"]`; `unclassified` → `theme.CAT[7]` = `#b7b7b7`, order 7.
- Table count stays **19**: `dim_city` replaces `agg_city`.
- Env: repo root `c:/Users/sedig/Desktop/DIVERSA/chatbot_methodology_mmc`; interpreter `.venv/Scripts/python.exe`; tests run `PYTHONPATH=src .venv/Scripts/python.exe -m pytest`; git bash for shell.
- City coordinates (decimal degrees), for `canon.CITY_COORDS`:
  Bogotá (4.7110,-74.0721), Medellín (6.2442,-75.5812), Cali (3.4516,-76.5320), Barranquilla (10.9685,-74.7813), Cúcuta (7.8939,-72.5078), Cartagena (10.3910,-75.4794), Bucaramanga (7.1193,-73.1227), Santa Marta (11.2408,-74.1990), Ipiales (0.8303,-77.6450), Riohacha (11.5444,-72.9072), Maicao (11.3776,-72.2389), Soacha (4.5794,-74.2140), Necoclí (8.4256,-76.7789).

---

## File Structure

- Modify `src/sami/canon.py` — add `CITY_COORDS`.
- Modify `src/sami/export.py` — add `build_dim_city`; extend `build_dim_category`, `build_dim_user`, `build_meta_run`, `build_parity_check`; drop `message` from `build_fact_message`; remove `build_agg_city` (Task 6).
- Modify `run_pipeline.py` — emit `dim_city` not `agg_city`.
- Modify `tests/test_export.py` — new/updated tests.
- Modify `exports/_schema.md` + regenerate `exports/` (Task 6).

---

### Task 1: `dim_city` + `canon.CITY_COORDS`

**Files:**
- Modify: `src/sami/canon.py`
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `canon.CITY_COORDS`, `canon.DEPARTMENT_OF_CITY`, `canon.department_of`.
- Produces: `canon.CITY_COORDS: dict[str, tuple[float, float]]`; `export.build_dim_city() -> DataFrame[city_canon, department, lat, lon]`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
def test_dim_city_schema_and_coords():
    from sami import canon
    d = export.build_dim_city()
    assert list(d.columns) == ["city_canon", "department", "lat", "lon"]
    assert "Otra" not in set(d["city_canon"])
    assert d["lat"].notna().all() and d["lon"].notna().all()
    assert d["city_canon"].is_unique
    for _, r in d.iterrows():
        assert r["department"] == canon.department_of(r["city_canon"])


def test_city_coords_cover_all_departmented_cities():
    from sami import canon
    # every city with a known department must have coordinates, and vice-versa
    assert set(canon.DEPARTMENT_OF_CITY) == set(canon.CITY_COORDS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "city" -q`
Expected: FAIL — `AttributeError: module 'sami.canon' has no attribute 'CITY_COORDS'` / `build_dim_city`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/sami/canon.py` (near `DEPARTMENT_OF_CITY`):

```python
# Canonical city coordinates (lat, lon, decimal degrees) for the dashboard bubble
# map — spec forbids geocoding-by-name. Keys must match DEPARTMENT_OF_CITY.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Bogotá": (4.7110, -74.0721),
    "Medellín": (6.2442, -75.5812),
    "Cali": (3.4516, -76.5320),
    "Barranquilla": (10.9685, -74.7813),
    "Cúcuta": (7.8939, -72.5078),
    "Cartagena": (10.3910, -75.4794),
    "Bucaramanga": (7.1193, -73.1227),
    "Santa Marta": (11.2408, -74.1990),
    "Ipiales": (0.8303, -77.6450),
    "Riohacha": (11.5444, -72.9072),
    "Maicao": (11.3776, -72.2389),
    "Soacha": (4.5794, -74.2140),
    "Necoclí": (8.4256, -76.7789),
}
```

In `src/sami/export.py`, update the top import to add `canon` and `theme` (both are used by this and later tasks):

```python
from . import metrics, taxonomy, qa, canon, theme
```

Add the builder:

```python
def build_dim_city() -> pd.DataFrame:
    """One row per canonical city with coordinates for the dashboard bubble map.
    The 'Otra'/Other bucket is excluded — it has no location."""
    rows = [{"city_canon": city, "department": canon.department_of(city),
             "lat": lat, "lon": lon}
            for city, (lat, lon) in canon.CITY_COORDS.items()]
    return pd.DataFrame(rows, columns=["city_canon", "department", "lat", "lon"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "city" -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/canon.py src/sami/export.py tests/test_export.py
git commit -m "feat(sami): dim_city + canon.CITY_COORDS for the dashboard map"
```

---

### Task 2: `dim_category` colors + order

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `CAT_EN` (module constant, ordered `legal_documentation` … `unclassified`), `theme.CAT`.
- Produces: `build_dim_category() -> DataFrame[category_key, category_es, category_en, color_hex, display_order]`.

- [ ] **Step 1: Write the failing test + update the existing schema test**

Replace the existing `test_dim_category_schema` body and add a colors test:

```python
def test_dim_category_schema():
    d = export.build_dim_category()
    assert list(d.columns) == ["category_key", "category_es", "category_en",
                               "color_hex", "display_order"]
    assert "legal_documentation" in set(d["category_key"])
    assert d["category_key"].is_unique


def test_dim_category_colors_and_order():
    import re
    d = export.build_dim_category()
    assert d["color_hex"].str.match(r"^#[0-9a-fA-F]{6}$").all()
    assert sorted(d["display_order"]) == list(range(len(d)))
    unc = d[d["category_key"] == "unclassified"].iloc[0]
    assert unc["color_hex"].lower() == "#b7b7b7"
    assert int(unc["display_order"]) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "dim_category" -q`
Expected: FAIL — column list mismatch / missing `color_hex`.

- [ ] **Step 3: Write minimal implementation**

Replace `build_dim_category` in `src/sami/export.py`:

```python
def build_dim_category() -> pd.DataFrame:
    # CAT_EN is ordered like taxonomy.OFFICIAL_CATEGORIES + ["unclassified"];
    # theme.CAT is the fixed categorical palette (unclassified → grey #b7b7b7).
    return pd.DataFrame(
        [{"category_key": k, "category_es": k, "category_en": v,
          "color_hex": theme.CAT[i], "display_order": i}
         for i, (k, v) in enumerate(CAT_EN.items())])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "dim_category" -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): dim_category color_hex + display_order from theme palette"
```

---

### Task 3: `dim_user` flags (`first_seen`, `is_repeat_asker`, `intends_to_stay`)

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `SD.responses`, `SD.messages`, `canon.fold`.
- Produces: `build_dim_user(responses, messages, lab=None)` now also emits `first_seen`, `is_repeat_asker`, `intends_to_stay`.

- [ ] **Step 1: Write the failing test**

```python
def test_dim_user_new_flags(SD):
    d = export.build_dim_user(SD.responses, SD.messages)
    for c in ["first_seen", "is_repeat_asker", "intends_to_stay"]:
        assert c in d.columns
    assert d["is_repeat_asker"].dtype == bool
    assert d["intends_to_stay"].dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(d["first_seen"])
    # is_repeat_asker matches the reconciliation.repeat_askers_pct derivation
    q = SD.responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    assert int(d["is_repeat_asker"].sum()) == int((q >= p90).sum())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "new_flags" -q`
Expected: FAIL — `KeyError`/`assert 'first_seen' in ...`.

- [ ] **Step 3: Write minimal implementation**

In `src/sami/export.py`, inside `build_dim_user`, after the `has_text` line and before the `cluster_id` line, add:

```python
    # first message timestamp per user (NaT if the user has no text)
    first = messages.groupby("user_id")["ts"].min()
    agg["first_seen"] = agg.index.to_series().map(first)
    # repeat asker — the exact definition behind reconciliation.repeat_askers_pct
    q = responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    agg["is_repeat_asker"] = agg.index.to_series().map(q >= p90).fillna(False).astype(bool)
    # intends to stay: no onward destination stated, or destination folds to Colombia
    def _stay(v):
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
            return True
        return canon.fold(str(v)) == canon.fold("Colombia")
    dest = agg["destination_country"] if "destination_country" in agg.columns else pd.Series(index=agg.index, dtype=object)
    agg["intends_to_stay"] = dest.map(_stay).astype(bool)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "dim_user" -q`
Expected: PASS (all dim_user tests).

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): dim_user first_seen + is_repeat_asker + intends_to_stay flags"
```

---

### Task 4: `fact_message` text-free

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `build_fact_message(...)` no longer emits the `message` column.

- [ ] **Step 1: Write the failing test**

```python
def test_fact_message_no_text(SD):
    f = export.build_fact_message(SD.messages)
    assert "message" not in f.columns
    # the analytical columns remain
    for c in ["message_id", "user_id", "ts", "dominant_category"]:
        assert c in f.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "no_text" -q`
Expected: FAIL — `assert 'message' not in ...` (message currently present).

- [ ] **Step 3: Write minimal implementation**

In `src/sami/export.py`, remove `"message"` from `_FACT_MSG_COLS`:

```python
_FACT_MSG_COLS = ["message_id", "user_id", "ts", "city_canon",
                  "dominant_category", "seq", "n_msgs_user"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "fact_message or no_text" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): drop message text from fact_message (text-free dashboard model)"
```

---

### Task 5: `meta_run.schema_version` + `parity_check.repeat_askers_pct`

**Files:**
- Modify: `src/sami/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `build_meta_run(run_meta, nlp_meta=None, schema_version="2")`; `build_parity_check(...)` adds a `repeat_askers_pct` row.

- [ ] **Step 1: Write the failing test**

```python
def test_meta_run_schema_version():
    m = export.build_meta_run({"responses_file": "x.xlsx"})
    kv = dict(zip(m["key"], m["value"]))
    assert kv["schema_version"] == "2"


def test_parity_check_includes_repeat_askers(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    fmsg = export.build_fact_message(SD.messages)
    fmeal = export.build_fact_meal(SD.meal)
    p = export.build_parity_check(SD.reconciliation, du, fmsg, fmeal)
    assert "repeat_askers_pct" in set(p["metric"])
    assert p["match"].all(), p[~p["match"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "schema_version or repeat_askers" -q`
Expected: FAIL — no `schema_version` key / no `repeat_askers_pct` row.

- [ ] **Step 3: Write minimal implementation**

Replace `build_meta_run` in `src/sami/export.py`:

```python
def build_meta_run(run_meta: dict, nlp_meta: "dict | None" = None,
                   schema_version: str = "2") -> pd.DataFrame:
    merged = {k: v for k, v in run_meta.items() if k != "checks"}
    merged["schema_version"] = schema_version
    if nlp_meta:
        merged.update(nlp_meta)
    return pd.DataFrame([{"key": k, "value": str(v)} for k, v in merged.items()])
```

In `build_parity_check`, before `return pd.DataFrame(rows)`, append the repeat-asker row (float, not int):

```python
    rap_exp = round(100 * float(dim_user["is_repeat_asker"].mean()), 1)
    rap_rec = recon.get("repeat_askers_pct")
    rows.append({"metric": "repeat_askers_pct", "exported_value": rap_exp,
                 "reconciliation_value": rap_rec,
                 "match": rap_rec is not None and float(rap_rec) == rap_exp})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -k "schema_version or repeat_askers or parity" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): meta_run schema_version + parity_check repeat_askers_pct"
```

---

### Task 6: Rewire `run_pipeline.py`, remove `agg_city`, regenerate + document

**Files:**
- Modify: `run_pipeline.py`
- Modify: `src/sami/export.py` (remove `build_agg_city`)
- Modify: `tests/test_export.py` (remove `test_agg_city`)
- Modify: `exports/_schema.md` + regenerate `exports/`

**Interfaces:**
- Consumes: `export.build_dim_city`.
- Produces: `run_pipeline.py` emits `dim_city` (not `agg_city`); refreshed `exports/`.

- [ ] **Step 1: Remove `build_agg_city` and its test**

In `src/sami/export.py`, delete the `build_agg_city` function. In `tests/test_export.py`, delete `test_agg_city`.

- [ ] **Step 2: Rewire run_pipeline.py**

In `run_pipeline.py`, in the `tables` dict, replace the `agg_city` line:

```python
        # was: "agg_city": export.build_agg_city(dim_user),
        "dim_city": export.build_dim_city(),
```

- [ ] **Step 3: Run the full test suite**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_export.py -q`
Expected: PASS (no reference to the removed `build_agg_city`/`test_agg_city`).

- [ ] **Step 4: Full pipeline acceptance run + verify**

Run: `.venv/Scripts/python.exe run_pipeline.py`
Expected: 19 tables printed including **`dim_city`** and NOT `agg_city`; `parity_check` all-match **including a `repeat_askers_pct` row**; exit 0.

Verify the key invariants:
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import pandas as pd; \
print('dim_city' , 'agg_city.csv exists:', __import__('pathlib').Path('exports/agg_city.csv').exists()); \
print('fact_message cols:', list(pd.read_csv('exports/fact_message.csv', nrows=1).columns)); \
print('schema_version:', dict(zip(*pd.read_csv('exports/meta_run.csv').values.T.tolist())).get('schema_version')); \
print(pd.read_csv('exports/dim_city.csv').to_string(index=False))"
```
Expected: `agg_city.csv exists: False`; `fact_message cols` has no `message`; `schema_version` = `2`; `dim_city` lists 13 cities with lat/lon.

- [ ] **Step 5: Remove the stale `agg_city.csv`**

```bash
git rm exports/agg_city.csv
```
(The pipeline no longer writes it; remove the committed stale copy.)

- [ ] **Step 6: Update `exports/_schema.md`**

Edit `exports/_schema.md`: replace the `agg_city` entry with a **`dim_city`** entry (grain: one row per canonical city; cols `city_canon, department, lat, lon`; feeds the Tab-1 bubble map + top-cities bar via a `Users` measure). Add `color_hex`/`display_order` to the `dim_category` entry; add `first_seen`/`is_repeat_asker`/`intends_to_stay` to `dim_user`; note `fact_message` is now text-free (no `message`); note `meta_run.schema_version` and the new `parity_check.repeat_askers_pct` row. Update the top count line if it names tables.

- [ ] **Step 7: Commit**

```bash
git add run_pipeline.py src/sami/export.py tests/test_export.py exports/ exports/_schema.md
git commit -m "feat(sami): pipeline emits dim_city (replaces agg_city); regenerate gold exports + schema doc"
```

---

## Self-Review

**1. Spec coverage:**
- `dim_city` + coords → Task 1. ✓
- `dim_category` color/order → Task 2. ✓
- `dim_user` flags (first_seen/is_repeat_asker/intends_to_stay) with reconciliation-matched repeat-asker → Task 3. ✓
- `fact_message` text-free → Task 4. ✓
- `meta_run.schema_version` + `parity_check.repeat_askers_pct` → Task 5. ✓
- `agg_city` removed, run_pipeline rewired, regenerate + `_schema.md` → Task 6. ✓
- Table count stays 19 (dim_city replaces agg_city) → Task 6 verify. ✓

**2. Placeholder scan:** No TBD/TODO. Task 6 Step 6 describes doc prose with explicit content requirements — acceptable (documentation step). All code steps carry full code.

**3. Type consistency:** `build_dim_city()` (no args) called in run_pipeline Task 6; `build_meta_run(run_meta, nlp_meta=None, schema_version="2")` keeps the existing 2-arg call sites working (default schema_version); `build_parity_check` still `(reconciliation, dim_user, fact_message, fact_meal)` — the new row uses `dim_user["is_repeat_asker"]` added in Task 3, so Task 5's parity test depends on Task 3 (sequential order respected). `is_repeat_asker` dtype forced to `bool` via `.astype(bool)`, matching the Task 3 test. Import line adds `canon, theme` once in Task 1, used by Tasks 1–3. ✓
