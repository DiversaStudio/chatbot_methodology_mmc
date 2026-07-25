# SAMI · Gold-layer additions for the Power BI dashboard — design

**Date:** 2026-07-24
**Follows:** the export layer (`2026-07-24-sami-exports-powerbi-design.md`, built &
merged). This adds the fields `requirements/03_dashboard_requirements.md` needs but
the current `exports/` doesn't provide, so the 3-tab / 12-visual dashboard can be
built "numbers-identical-by-construction" (dashboard Rule 4: flags/classifications
are Python-computed, DAX only aggregates).

## 1. Purpose & the gaps it closes

`03_dashboard_requirements.md` assumes gold-layer fields absent from the shipped
exports. This sub-project adds exactly those, and nothing more (YAGNI):

| Gap (dashboard spec) | Fix here |
|---|---|
| Bubble map on provided lat/lon, "no geocoding-by-name" (§8); `dim_city` w/ lat/lon | New `dim_city` table with canonical city coordinates |
| Category hues driven by `dim_category.color_hex` + display order (§3/§5) | Add `color_hex` + `display_order` to `dim_category` |
| KPIs "New users this period", "% Repeat Askers", "% intending to stay" as Python flags (§2.4/§4) | Add `first_seen`, `is_repeat_asker`, `intends_to_stay` to `dim_user` |
| "No message text … in the model" (§7) | Drop `message` from `fact_message` |
| Schema-version assertion on About page (§3) | Add `schema_version` to `meta_run` |

Explicitly **not** built here (dashboard builds them in Power BI, per spec): the
`dim_date` calendar (Power Query), all rate / vs-previous-4-weeks measures (DAX),
the theme JSON. The coverage-gaps bar uses existing `nlp_emergent_themes` + a
`% Outside Official Taxonomy` DAX measure — no new table.

## 2. Changes to the gold layer

### 2.1 New table `dim_city` (replaces `agg_city`)
One row per canonical city (the "Otra"/Other bucket is excluded — it has no
location). Columns: `city_canon, department, lat, lon`.
- Source: a new `canon.CITY_COORDS: dict[str, tuple[float, float]]` (lat, lon) for
  the 13 canonical cities; `department` from the existing `canon.DEPARTMENT_OF_CITY`.
- A pure `export.build_dim_city()` builds it from those two `canon` dicts.
- `agg_city` is **removed** (`build_agg_city` deleted): users-per-city and the map
  bubbles are a live `Users` measure over `dim_city[city_canon] → dim_user`.

Coordinates (decimal degrees, offline/deterministic):

```
Bogotá 4.7110,-74.0721 · Medellín 6.2442,-75.5812 · Cali 3.4516,-76.5320
Barranquilla 10.9685,-74.7813 · Cúcuta 7.8939,-72.5078 · Cartagena 10.3910,-75.4794
Bucaramanga 7.1193,-73.1227 · Santa Marta 11.2408,-74.1990 · Ipiales 0.8303,-77.6450
Riohacha 11.5444,-72.9072 · Maicao 11.3776,-72.2389 · Soacha 4.5794,-74.2140
Necoclí 8.4256,-76.7789
```

### 2.2 `dim_category` — add `color_hex`, `display_order`
`build_dim_category` gains two columns, driven by the same palette the notebooks
use (`theme.CAT`, fixed order) over `taxonomy.OFFICIAL_CATEGORIES + ["unclassified"]`:
- `display_order` = index in that ordered list (0…7).
- `color_hex` = `theme.CAT[i]` for that index. The 8th slot (`unclassified`) lands on
  `theme.CAT[7]` = `#b7b7b7` (grey) — semantically correct for the data-quality bucket.

### 2.3 `dim_user` — add `first_seen`, `is_repeat_asker`, `intends_to_stay`
`build_dim_user` gains three Python-computed columns:
- `first_seen` — earliest `SD.messages.ts` for the user (NaT if the user has no
  text). Grain-safe: computed from the message spine, then mapped by `user_id`.
- `is_repeat_asker` — boolean, **using the exact definition behind
  `reconciliation.repeat_askers_pct`**: `q = responses.groupby("user_id")["n_questions"].max()`,
  `p90 = q.quantile(0.90)`, flag = `q >= p90`. Mapped by `user_id`. This keeps the
  dashboard KPI identical to the reconciliation figure by construction.
- `intends_to_stay` — boolean, `destination_country` is null/blank **or** folds to
  Colombia (mirrors NB1's stay-in-Colombia framing: onward destination not stated,
  or stated as Colombia, = staying).

### 2.4 `fact_message` — drop `message`
`build_fact_message` no longer emits the `message` text column. Remaining columns:
`message_id, user_id, ts, city_canon, dominant_category, seq, n_msgs_user,
sentiment_label, cluster_id`. The model is text-free by construction (spec §7).
Verbatim quotes remain available to the *report* via `nlp_voices`; word-cloud terms
via `nlp_cluster_terms` (neither needs raw message text). `run_pipeline.py`'s
`build_nlp_voices` still reads `SD.messages` (in-memory), unaffected.

### 2.5 `meta_run` — add `schema_version`
`run_pipeline.py` passes `schema_version = "2"` into `meta_run` (via the existing
`nlp_meta`/meta merge or a dedicated arg). "2" marks the post-additions contract.

### 2.6 `parity_check` — add `repeat_askers_pct`
Add a row comparing the exported repeat-asker share
(`round(100 * dim_user["is_repeat_asker"].mean(), 1)`) to
`reconciliation.repeat_askers_pct`. Extends the existing 4-metric gate; run_pipeline
still exits non-zero on any mismatch.

## 3. Non-goals / invariants

- No change to the 15 other tables' schemas.
- PII gate unchanged and still green on every frame (dropping `message` only
  shrinks the surface; `dim_city` coords are numeric).
- Determinism preserved (only `meta_run.generated_at` varies between runs).
- Table count stays **19** (`dim_city` replaces `agg_city`).

## 4. Testing (`tests/test_export.py` additions)

1. `build_dim_city`: columns `[city_canon, department, lat, lon]`; one row per
   canonical city with non-null numeric coords; excludes "Otra"; `department`
   matches `canon.DEPARTMENT_OF_CITY`.
2. `canon.CITY_COORDS` covers every canonical city except "Otra" (guards against a
   new canon city shipping without coordinates).
3. `build_dim_category`: has `color_hex` (valid `#rrggbb`) + `display_order`
   (0…7, unique); `unclassified` → `#b7b7b7`, order 7.
4. `build_dim_user`: has the 3 new columns; `is_repeat_asker` **count/share equals**
   the reconciliation `repeat_askers_pct` derivation on real data; `first_seen` is a
   datetime; `intends_to_stay` is boolean.
5. `build_fact_message`: **no `message` column**; other columns intact.
6. `build_parity_check`: includes a `repeat_askers_pct` row, `match=True` on real data.
7. PII scan clean on `dim_city`, the new `dim_user`, `dim_category`, `fact_message`.

## 5. Acceptance

1. `python run_pipeline.py` writes 19 tables incl. `dim_city` (not `agg_city`);
   parity all-match incl. `repeat_askers_pct`; `meta_run.schema_version = "2"`;
   `fact_message.csv` has no `message` column.
2. `pytest tests/test_export.py` green.
3. `exports/_schema.md` updated: `dim_city` documented, `agg_city` removed, new
   columns noted, `fact_message` text-free.
4. Regenerated `exports/` committed.

## 6. Out of scope

The dashboard `.pbix`, its DAX measures, calendar table, theme JSON, and the
`docs/dashboard_build_guide.md` (the exact 3-tab/12-visual guide) — the guide is the
immediate follow-on after this lands, written against these spec-compliant exports.
