# SAMI NB1 — The input & the audience (Act 1) — Design

Sub-project 2 of the SAMI pipeline rework (foundation = merged at `e8d4fab`).
Reads with `requirements/01_storytelling_and_analysis_scope.md` §Act1 and
`requirements/02_notebook_requirements.md` §4. Branch: `feature/sami-nb1`.

**Mandate:** descriptive EDA done with authority — source reliability + audience
profile, one variable at a time, no cross-cuts (those are NB2). Hard cap **9 figures**.

**Decisions locked (user):**
- Render engine: **matplotlib** (theme.py template) + geopandas/cartopy for maps. NB2/NB3 follow.
- Department choropleth: **included** in NB1.
- Gold exports: **deferred** to the later `run_pipeline` + `src/sami/exports.py` sub-project.
  NB1 is purely analytical (figures + reconciliation). No notebook `to_csv`.
- New notebook file `notebooks/01_input_and_audience.ipynb`; old inlined notebooks untouched.

---

## 1. Module changes (notebooks consume, modules compute — Rule 3)

### `canon.py` extensions
- `NATIONALITY_CANON` + `nationality_canon()` — Venezuela 905 / Ecuador 9 / Peru 3 /
  United States 2 (measured). Consolidates `Nationality_other`. Supports the ~96% VE claim.
- `DEPARTMENT_OF_CITY` — priority-city → department (Medellín→Antioquia,
  Bogotá→Bogotá D.C., Cúcuta→Norte de Santander, Barranquilla→Atlántico,
  Santa Marta→Magdalena, Cali→Valle del Cauca, Cartagena→Bolívar,
  Bucaramanga→Santander, Ipiales→Nariño, Riohacha/Maicao→La Guajira,
  Soacha→Cundinamarca, Necoclí→Antioquia). "Otra" → `None`.
- `DURATION_CANON` — **fixes mojibake** (`M�s de 5 a�os`→`Más de 5 años`) and attaches an
  **order index** for ordered plotting. Keyed on `fold()` (encoding-robust). Covers the
  `Away_duration` vocabulary (5 buckets) and `City_duration` vocabulary.
- `GENDER_DISPLAY` — Mujer→Woman / Hombre→Man / Prefiero no responder→Prefer not to say /
  Otro→Other.

### `load.py` extensions
- `*_other` consolidation for Gender, Nationality, Destination (P4 gap — today only City).
- Derived columns computed at load so the notebook never does: `nationality_canon`,
  `away_duration_canon` (+ `away_duration_order`), `department`.

### New `src/sami/geo.py`
- `load_colombia_departments()`, `load_americas_countries()` — read **bundled local
  GeoJSON only** (no runtime network).
- `dept_choropleth(ax, counts)` — users-by-department choropleth on a matplotlib axis.
- `americas_flow_map(ax, origin, hub, onward)` — single-frame origin-fill / stay-hub /
  onward-arrows map (the "best figure in the set", kept).

### `theme.py`
- Unchanged matplotlib template. Optionally re-export an `EN_DISPLAY` convenience map.

### `qa.py`
- Confirm `reconciliation_table` carries `users_with_text`; add `unmapped_city_share`
  and `sub18_count` if absent.

### Tests
- Extend `tests/test_canon.py` (nationality/duration/department), extend
  `tests/test_load_responses.py` (new consolidated cols), new `tests/test_geo.py`
  (asset load + counts alignment). Full suite stays green.

## 2. Geographic assets & determinism (Rule 2)
Bundle versioned geometry under `data_&_docs/geo/`: a Colombia-departments GeoJSON and
an Americas-countries GeoJSON (Natural Earth admin-1 / admin-0, simplified). Generated
once from cartopy Natural Earth, trimmed, committed. `geo.py` reads local files only —
deterministic, offline, no network on refresh.

## 3. Notebook structure (9-figure hard cap — doc 02 §4)

| # | Section | Figure | Source |
|---|---------|--------|--------|
| — | top | Reconciliation table (P10) + identity card (file, rows, window) | facade |
| 1 | Sources & reliability | Field-completeness bar (responses + MEAL) | both |
| 2 | Sources & reliability | MEAL response-rate big-number callout (7.5%, 69/917) — not a chart | facade |
| 3 | Audience profile | Gender — horizontal bar (replaces radial) | `Gender`+display |
| 4 | Audience profile | Age distribution, sub-18 flagged band + honesty note | `age_num`/`age_flag` |
| 5 | Audience profile | Care responsibilities — one bar (Minors Si/No) | `Minors` |
| 6 | Audience profile | City top-10 bar | `city_canon` |
| 7 | Audience profile | Department choropleth (users by dept) | `department` + geo |
| 8 | Migration journey | Time-away distribution (ordered) | `away_duration_canon` |
| 9 | Migration journey | Americas flow map (origin/hub/onward) | nationality→Colombia→`Destination_Country` |
| — | close | 5-bullet "what we now know" + reconciliation (must match top) | facade |

Every figure: assertion-evidence title; subtitle with metric + n + window; `theme.py`
palette; source note. One variable per chart. No cross-cuts.

## 4. QA gates & acceptance (doc 02 §4 + §7)
- `Run All` clean kernel succeeds, < 15 min; reconciliation printed top and bottom, identical.
- Every figure n traces to P10; figure count ≤ 9.
- Zero PII: `qa.pii_scan` over notebook data + grep rendered outputs for `whatsapp:` / digit runs → 0.
- No inlined loaders: notebook imports `from sami import load_sami` + `sami.geo`/`sami.theme` only.
- All new module code covered by pytest; full suite green.
- Whole-branch review before merge (as foundation).
