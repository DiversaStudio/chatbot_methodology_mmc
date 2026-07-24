# SAMI · Power BI export layer + `run_pipeline.py` — design

**Date:** 2026-07-24
**Sub-project:** The `exports/` gold layer and the headless pipeline runner, named
as out-of-scope in the foundation spec §8
(`docs/superpowers/specs/2026-07-22-sami-pipeline-foundation-design.md`). This is
the deferred "gold exports + `run_pipeline`" work referenced across all three
notebook specs ("No notebook `to_csv`").

## 1. Purpose & requirements

The project deliverable is a **refreshable Power BI (.pbix)** (foundation spec
"Direction note"). This sub-project produces the tabular layer that .pbix binds
to: a set of CSVs from which **every plot in the three notebooks can be
reproduced in Power BI**, plus a single "father" script that runs the whole
pipeline (including the GPU NLP) and writes them.

Requirements, reconciled from the specs and the user:

- R1. **All notebook plots reproducible in Power BI** from the exported CSVs.
- R2. **Hybrid grain** (user decision 2026-07-24): row-level base tables so Power
  BI recomputes simple charts itself, plus pre-computed CSVs for anything Power
  BI cannot faithfully redo (UMAP coords, c-TF-IDF terms, confusion matrix,
  funnel, priority matrix, entity extraction, resampled time series).
- R3. **Dimensional model** naming from foundation spec §8: `dim_*` / `fact_*` /
  `agg_*` / `meta_run` / `parity_check`.
- R4. **`run_pipeline.py`** father script — one command regenerates the whole
  `exports/` layer. GPU NLP runs by default; `--skip-nlp` opts out.
- R5. **Power BI parity verification** — a `parity_check` table proving the
  exported aggregates reconcile to the run's headline totals.
- R6. **No notebook `to_csv`.** Notebooks stay purely analytical. Export logic
  lives in `src/sami/export.py` and is invoked only by `run_pipeline.py`.
- R7. **Tone suppression carries over.** κ=0.604 fails the 0.7 gate; sentiment is
  directional-only. Sentiment ships but `meta_run` flags it non-quotable.
- R8. **No PII leakage.** Every frame passes `qa.pii_scan` (zero `whatsapp:` / 7+
  digit runs) before being written. `exports/` is committed (user decision;
  matches the already-committed `validation/tone_gold_labels.csv`).

## 2. Architecture

Two new artifacts; everything else reuses existing `src/sami` modules.

```
src/sami/export.py      pure build_*(frames) -> tidy DataFrame  (+ write_all orchestrator)
run_pipeline.py         repo-root father script (CLI); the only caller of export.write_all
exports/                committed gold CSVs + _manifest.csv
```

- **`export.py` functions are pure and I/O-free.** Each `build_*` takes
  already-computed frames/objects and returns a tidy `DataFrame`. This makes each
  table unit-testable in isolation and keeps `run_pipeline.py` a thin wiring
  layer. Notebooks and the script feed these functions the *same* frames, so
  there is no logic duplication — only compute (the script re-runs the GPU NLP
  that NB3 also runs; accepted per the "shared headless compute path" direction).
- **`write_all(out_dir, frames, *, skip_nlp)`** builds every table, runs
  `qa.pii_scan` on each, writes `<name>.csv` (UTF-8, no index), and writes
  `_manifest.csv` (table name, row count, column list, sha1 of the file). Raises
  if any PII scan is non-empty.
- **`run_pipeline.py`**: `load_sami()` → (unless `--skip-nlp`) embed → UMAP →
  choose_k/cluster → c-TF-IDF terms → sentiment → build the validation/tone
  report → `export.write_all(...)`. Prints the manifest + the `parity_check`
  result and exits non-zero if any parity row fails.
  CLI: `python run_pipeline.py [--out exports] [--skip-nlp] [--responses PATH] [--meal PATH]`.

## 3. The export catalog

Grain and source in parentheses. Column lists are the intended schema; exact
dtypes follow the source frames. **Charts not listed here (gender split, age
histogram, minors, away-duration) are built in Power BI directly from
`dim_user`** — they need no dedicated CSV (keeps the file set lean while still
satisfying R1).

### Core star

- **`dim_user`** (1 row/user; from `SD.responses`, one row per user_id — collapse
  the ≤3 multi-record users keeping first non-null profile fields).
  Cols: `user_id, gender_clean, age_num, age_flag, age_range, minors,
  city_canon, department, nationality_canon, away_duration_canon,
  away_duration_order, city_duration_canon, city_duration_order,
  destination_country, n_questions, n_msgs_user, has_text, cluster_id`.
  Feeds: NB1 §2 gender/age/minors/city, §3 away-duration; NB2 cross-cuts;
  archetype-per-user join. `cluster_id` is null when `--skip-nlp`.
- **`fact_message`** (1 row/message; from `SD.messages` + NLP joins).
  Cols: `message_id, user_id, ts, city_canon, dominant_category, seq,
  n_msgs_user, sentiment_label, cluster_id, message`.
  `message_id` = stable row index of `SD.messages`. `sentiment_label`/`cluster_id`
  null when `--skip-nlp`. Feeds: NB2 §1 category share, §2 time series,
  NB3 negative-by-category, sentiment dist, voices.
- **`fact_meal`** (1 row/user; from `SD.meal`).
  Cols: `user_id, ts, usefulness_rating, would_recommend, recommendation_text,
  discovery_channel`. Feeds: NB2 §5 satisfaction, discovery mix.
- **`dim_category`** (1 row/category; from `taxonomy` + `CAT_EN`).
  Cols: `category_key, category_es, category_en`. Lookup for the ES→EN labels the
  notebooks use.
- **`dim_cluster`** (1 row/archetype; from `clusters.archetype_profiles`).
  Cols: `cluster_id, name, n_users, share`. NLP-only (absent when `--skip-nlp`).

### Time series (resampling parity — computed once, not re-derived in DAX)

- **`agg_weekly_category`** (week × category; `metrics.weekly_category_counts`,
  top 4 + "other"). Cols: `week, category, n`. Feeds NB2 §2 lines.
- **`agg_daily_volume`** (day; daily `resample("D").size()`).
  Cols: `day, n`. Feeds NB2 §2 volume line.
- **`agg_weekly_rating`** (week; MEAL weekly mean).
  Cols: `week, mean_rating, n`. Feeds NB2 §5.

### Geo / profile aggregates

- **`agg_city`** (1 row/city; from `dim_user`).
  Cols: `city_canon, department, n_users`. Feeds NB1 top-cities bar + (grouped to
  department) the choropleth.
- **`agg_onward`** (1 row/destination; from `SD.responses.Destination_Country`).
  Cols: `destination_country, n`. Feeds NB1 flow-map arrow weights.

### Computed frames (not reproducible in DAX)

- **`agg_funnel`** (1 row/stage; `metrics.funnel_stages`).
  Cols: `stage_order, stage, n`. Feeds NB2 §4.
- **`agg_priority_matrix`** (1 row/category; `metrics.priority_matrix_frame`).
  Cols: `category, volume, unmet_score, tone_score` (+ whatever the frame
  produces). Feeds NB2 §6.
- **`agg_entities_by_kind`** (1 row/(kind, entity); `taxonomy.entity_counts_by_kind`).
  Cols: `kind, entity, n`. Feeds NB2 §1 entity chart.

### NLP (GPU; absent when `--skip-nlp`)

- **`nlp_umap`** (1 row/user; `clusters.project_2d`).
  Cols: `user_id, x, y, cluster_id`. Feeds NB3 §2 scatter.
- **`nlp_cluster_terms`** (1 row/(cluster, term); `clusters.ctfidf_terms`).
  Cols: `cluster_id, rank, term, weight`. Feeds NB3 word clouds.
- **`nlp_emergent_themes`** (1 row/theme; NB3 §3 probe).
  Cols: `theme, n, example`. Feeds NB3 §3 coverage gaps.
- **`nlp_tone_confusion`** (1 row/(human, model); from the validation report /
  `validation/tone_gold_labels.csv`). Cols: `human_label, model_label, n`.
  Feeds NB3 §4 confusion matrix.
- **`nlp_negative_by_category`** (1 row/category; `metrics.negative_by_category`).
  Cols: `category, n_negative, n_total, share`. Feeds NB3 §4.
- **`nlp_sentiment_dist`** (1 row/label; `sentiment.value_counts`).
  Cols: `sentiment_label, n`. Feeds NB3 annex. Non-quotable (see meta).
- **`nlp_voices`** (1 row/quote; NB3 §5 exemplars).
  Cols: `cluster_id, user_id, message`. Feeds NB3 §5.

### Meta / parity

- **`meta_run`** (key/value; from `SD.run_meta` + NLP metrics).
  Rows include: responses_file, meal_file, responses_rows, meal_rows, ts_min,
  ts_max, generated_at, embed_model, sentiment_model, chosen_k, stability_ari,
  tone_kappa, tone_gate_passed (=false), sentiment_quotable (=false),
  nlp_included. This is the run's identity card + the tone-suppression flags (R7).
- **`parity_check`** (1 row/metric). Cols: `metric, exported_value,
  reconciliation_value, match`. Metrics: records, users, messages, users_with_text,
  meal_rows, meal_users, sub18_flagged. `exported_value` is recomputed from the
  written frames (e.g. `len(fact_message)`), `reconciliation_value` from
  `SD.reconciliation`. `run_pipeline.py` exits non-zero if any `match` is false
  (R5).

## 4. PII & git

- `export.write_all` calls `qa.pii_scan` on every frame; any hit aborts the whole
  write (nothing partially written is trusted). Message text and
  `recommendation_text` ship (they are the analytical content; already
  pseudonymized + PII-run-redacted by the loaders).
- `exports/` is **committed** (user decision), consistent with
  `validation/tone_gold_labels.csv`. `_manifest.csv` travels with it so a
  reviewer can diff row counts/sha1 without opening every CSV.

## 5. Testing (`tests/test_export.py`)

1. **Schema per table** — each `build_*` returns the documented columns, correct
   grain (no duplicate keys where 1-row-per-key is claimed).
2. **PII = 0** — `qa.pii_scan` returns empty for every built frame (uses the test
   fixture / real export as available).
3. **Parity all-match** — `build_parity_check` yields `match=True` for every row
   against `SD.reconciliation`.
4. **Determinism** — two runs of the non-NLP frames are frame-equal.
5. **`--skip-nlp` contract** — NLP tables absent; `cluster_id`/`sentiment_label`
   columns present-but-null in the core star; `meta_run.nlp_included=false`.
6. **Manifest integrity** — `_manifest.csv` lists exactly the written files with
   matching row counts.

NLP-heavy tables are validated for schema on a tiny synthetic frame; the full GPU
path is exercised by running `run_pipeline.py` once, not in unit tests.

## 6. Acceptance criteria

1. `python run_pipeline.py --skip-nlp` writes the non-NLP tables + `meta_run` +
   `parity_check` + `_manifest.csv`; exits 0; parity all-match.
2. `python run_pipeline.py` (GPU) additionally writes every `nlp_*` table and
   `dim_cluster`, populates `cluster_id`/`sentiment_label` in the star, and still
   parity-matches.
3. `pytest tests/test_export.py` green.
4. Every plot in NB1–NB3 maps to at least one exported table (traceability table
   in §3 is complete — spot-checked against each notebook's plotting cells).
5. `meta_run` carries `tone_gate_passed=false` and `sentiment_quotable=false`.

## 7. Out of scope

The `.pbix` file itself and its DAX measures; the actual Power BI visuals; any
cloud/scheduled refresh. This sub-project delivers the CSV contract + generator
only.
