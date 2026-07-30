# SAMI Analysis — Notebook Implementation Requirements

Requirements for the three `.ipynb` notebooks, the shared processing module, validations and quality gates. Read together with `01_storytelling_and_analysis_scope.md` — the narrative defines *what* each notebook must prove; this document defines *how*.

---

## 1. Repository & pipeline structure

```
chatbot_methodology_mmc/
├── datasets/                     # raw exports, role-by-folder (responses/, meal/); gitignored, never modified
├── src/
│   └── sami/
│       ├── load.py               # loaders + cleaning (single source of truth)
│       ├── canon.py              # canonical dictionaries (city, dept, nationality, labels)
│       ├── taxonomy.py           # MMC categories, entity patterns, extended intents
│       ├── theme.py              # palette, plotly/mpl templates, EN display maps
│       └── qa.py                 # validation & reconciliation checks
├── notebooks/
│   ├── 01_input_and_audience.ipynb
│   ├── 02_demand_behaviour_experience.ipynb
│   └── 03_text_insights_nlp.ipynb
├── exports/                      # gold CSVs for the dashboard (generated, PII-free)
├── run_pipeline.py               # headless: raw exports -> gold CSVs, one command
├── environment.yml               # pinned env (or requirements.txt + python version)
└── tests/                        # pytest on load/canon/taxonomy
```

**Rule 1 — no inlined loaders.** The current notebooks paste the same loading/cleaning code three times with drifting dictionaries (NB1's city canon ≠ NB2/NB3's). One `load.py`, imported by all three. Divergent cleaning is how numbers stop reconciling.

**Rule 2 — deterministic end-to-end.** `random_state` fixed everywhere; model versions pinned; `Run All` on a clean kernel must reproduce every number. Cache heavy artifacts (embeddings, sentiment) to parquet keyed by export hash + model name; loading from cache must be logged visibly.

**Rule 3 — notebooks consume, modules compute.** Notebooks contain narrative, function calls and figures. Any logic >15 lines lives in `src/sami/`.

**Rule 4 — the pipeline is headless.** `run_pipeline.py` calls the same `src/sami/` functions the notebooks use and writes every gold CSV in `exports/` without opening a notebook. This is the reproducibility guarantee for the .pbix deliverable: MMC's refresh path is `drop new exports in datasets/responses/ and datasets/meal/ → python run_pipeline.py → Refresh in Power BI`. Notebooks are for the analyst; the pipeline is for operations. If a number can only be produced inside a notebook, it cannot exist in the dashboard — treat that as a build error. Heavy model steps (embeddings, sentiment, LLM classification) run inside the pipeline with the same caches; the pinned environment ships with the repo so the pipeline runs identically on MMC's side.

---

## 2. Data contract (inputs)

Two Excel exports (snapshots; schema can drift between exports — the May snapshot has 28 columns, the July one 33):

**Responses** — sheet `mmc bot - responses`, real header at row 3 (`header=2`).
Key fields: `Name` (WhatsApp id), `Timestamp` (ISO, UTC), `Consent`, `Nationality`(+`_other`), `City`(+`_other`), `City_duration`, `Gender`(+`_other`), `Age`, `Minors`, `Away_duration`, `Destination`(+`_other`), `Destination_Country`, `Messages` (raw user text, Spanish), `Text` (machine EN translation — do not analyse, translation quality unverified), `Text 1` (leftover prompt junk — drop), `Chat_summary` (LLM label source), `Survey sent`, `Questions per user`, `Age Ranges`.

**MEAL** — sheet `mmc-meal`, `header=2`. Columns renamed to: `Name`, `Timestamp`, `usefulness_rating`, `would_recommend`, `recommendation_text`, `discovery_channel`, `discovery_other`.

**Schema validation (must run before anything else):** assert sheet names, header row, expected column set (warn on additions, fail on missing critical fields), dtypes after coercion, timestamp parse rate = 100% of non-null. Log export filename + row count + min/max timestamp as the run's identity card.

---

## 3. Processing requirements (with paired validations)

Each step ships with its check. A step without a check is not done.

| # | Step | Requirement | Validation |
|---|---|---|---|
| P1 | **Pseudonymize** | At load: `user_id = sha256(salt + digits(Name))[:12]`. Raw `Name` dropped immediately after. Salt in env var, not in repo. | Grep all notebook outputs and exports for `whatsapp:` and 9+ digit runs → must be zero hits (automate in `qa.py`). |
| P2 | Banner rows / empty rows | `header=2`, drop all-NaN rows, drop artifact rows (no `Name`). | Row count logged; dropped-row count ≤ known artifacts (currently 1). |
| P3 | Type coercion | `Timestamp`→UTC datetime, `Age`/`Questions per user`→numeric, `errors='coerce'`. | Coercion-failure count per column reported; unexpected failures (>0 where previously 0) fail loudly. |
| P4 | `*_other` consolidation | Fall back to free text when main field is `Otra`/NaN. | Consolidated-field non-null ≥ original main field. |
| P5 | Canonicalization | City/nationality/duration mapped via `canon.py` (accent/case-insensitive keys). Non-cities (departments, "Colombia", digits) → excluded with reason. | Unmapped share reported (< 3% of records; currently 13/929). New unmapped values listed for dictionary growth — never silently bucketed. |
| P6 | Message spine | Parse `Messages` into one row per message: `user_id, ts, message, seq`. | `sum(per-user messages) == len(msgs)`; spot-check 10 users end-to-end; empty/whitespace messages dropped and counted. |
| P7 | Category from `Chat_summary` | Normalize (strip prompt leftovers, `''` separators, hashtags, case) → 7 canonical categories + `unclassified`. One dominant category per user, broadcast to messages. | Unclassified share reported (currently 12/2,993 messages); distribution printed and compared against previous run. |
| P8 | MEAL keying & dedup | Key by phone hash; MEAL has repeat responders (9 duplicate phones) — keep most recent response per user for any per-user join. | Assert one row per `user_id` post-dedup; joined-population size printed (currently 58 with both category and rating). |
| P9 | Age reliability flag | `age_flag = 'unreliable_sub18'` where Age<18 (36 records, 28 ≤12). Never deleted, never plotted as a real cohort. | Flag count stable vs export size; flagged records excluded from age means (report both if materially different). |
| P10 | Reconciliation table | One function emits the canonical-numbers table (doc 01 §7) from data. | Every figure's n must trace to this table. Run at top AND bottom of each notebook — both must match. |

---

## 4. Notebook 1 — The input & the audience (Act 1)

**Question:** what data do we have, can we trust it, who is SAMI reaching?
**Hard cap: 9 figures.** Structure:

1. **Sources & reliability** (2 figures max): field-completeness bar per source (keep current design); MEAL response-rate statement rendered as a big-number callout, not a chart. Missingness framed as expected (conditional `_other`) vs real.
2. **Audience profile** (4 figures): gender (plain horizontal bar — replaces radial), age distribution with sub-18 flagged band (keep current design, keep the honesty note), care responsibilities (one bar, not a donut), city top-10 + department choropleth (choropleth optional if the dashboard carries the map — don't do both here and there at equal fidelity).
3. **Migration journey** (2 figures): time-away distribution; the single-frame Americas map (origin fill / stay hub / onward arrows — keep as is).
4. **Close:** 5-bullet "what we now know" + the canonical numbers table.

**Analytical quality bar:** descriptive ≠ shallow. Each figure's caption answers "so what for MMC." No cross-cuts here (they belong to NB2) — discipline the current NB1 already has; keep it.

**QA gate NB1:** runs clean top-to-bottom; every n printed traces to P10; assertion-evidence titles on all figures; no raw phone anywhere; figure count ≤ 9.

---

## 5. Notebook 2 — Demand, behaviour & experience (Acts 2–3 quantitative)

**Questions:** what do users need, where/when; are they getting it?
**Hard cap: 12 figures.** Structure:

1. **Demand mix** (3): category share overall; category mix by city (one 100%-stacked view, top-5 cities + Other — the single geography×demand figure, replacing both treemaps); institutions vs procedures dictionary extraction (keep the two-panel split).
2. **Demand over time** (2): weekly messages by top-4 categories (smoothed, but plot raw points under the spline — never a spline alone); daily usage with annotated spikes. If MMC provides a dated event register, overlay it; otherwise state that no policy-alignment claim is made (keep current discipline).
3. **Cross-cuts that earned their place** (2–3): settlement duration × city; gender × nationality — only if the difference is material. **Statistical bar:** for any claimed difference, report chi-square (or Fisher where cells are thin) + Cramér's V; if V < 0.1 or any expected cell < 5 without correction, the claim is "no meaningful difference" — which can itself be the finding. Kill the age × destination cut (cells n≤6).
4. **The funnel** (1 — the centerpiece): arrived (918) → asked ≥1 question (~65%) → single-touch vs engaged → repeat-asker (13%) → surveyed → satisfied. Absolute numbers + conversion between stages.
5. **Satisfaction pulse** (2): usefulness distribution + would-recommend (n always in title; bootstrap 95% CI on mean rating, ~1,000 resamples); satisfaction over time only as indicative with the reach-vs-satisfaction separation kept.
6. **Priority matrix** (1): per category — x = message volume, y = unmet-need score (z-scored blend of % repeat-askers, % negative sentiment from NB3 cache, mean MEAL rating inverted), bubble = users. Quadrant labels in plain language ("big and badly served"). This figure is the deliverable's climax; iterate on it.

**QA gate NB2:** same as NB1 plus — every comparative claim carries a test + effect size or an explicit "directional only" tag; small-n rule enforced (no chart cell where n<20 without visible warning); funnel stages sum correctly against P10.

---

## 6. Notebook 3 — What the text says (Act 3 semantic)

**Question:** what do conversations reveal that the taxonomy and the structured fields miss?
**Hard cap: 8 figures.** The NLP exists to produce three named things: **archetypes**, **missing intents**, and a **validated tone signal**.

1. **Representation:** user-level documents (all messages per user, 800 docs). Embeddings: `intfloat/multilingual-e5-large` (pinned revision, normalized). TF-IDF comparison → annex only.
2. **Clustering (discovery, not headline):**
   - Choose k by silhouette + Davies-Bouldin scanned over k=4..12, not k=7 by fiat. Report the scan (annex figure).
   - **Stability requirement:** 50 bootstrap resamples (80% of users), mean pairwise ARI between solutions ≥ 0.6 for the chosen k; otherwise report clusters as "soft structure" and lean on the LLM classification instead. Current single-run KMeans with ARI 0.24 vs taxonomy is a starting point, not a finding.
   - Deliverable: 3–5 **named archetypes** — for each: size, demographic skew, dominant categories, top distinctive terms (c-TF-IDF style: cluster centroid TF-IDF, not raw frequency), one verbatim quote (Spanish, anonymized). One summary table + one 2D map (PCA or UMAP, one view only, tinted by archetype).
3. **Gap detection (the headline — LLM-assisted):**
   - Build extended taxonomy: 7 official categories + candidate intents from clustering/eyeballing (minimum: `transport/movement logistics`, `human handoff request`, `connectivity/phone services`, `out_of_scope`, `other_emergent`).
   - LLM classifies each of the 2,993 messages (multilingual model; batched; temperature 0; structured output; prompt versioned in repo).
   - **Validation protocol (mandatory):** stratified random sample of 200 messages hand-labeled (analyst + one reviewer). Report Cohen's κ between LLM and human; κ ≥ 0.7 required to report percentages; below that, report only directional findings. Publish the confusion matrix vs `Chat_summary` — where they disagree, note that `Chat_summary` was uncontrolled LLM output, so disagreement is expected and diagnostic.
   - Output figure: **coverage-gap bar** — share of messages that fall outside the 7 official categories, broken by candidate new intent. This replaces cluster-purity charts as the public-facing evidence.
4. **Tone (validated, then used):** current model `cardiffnlp/twitter-xlm-roberta-base-sentiment` (pinned). Validate on the same 200-message sample (κ or accuracy vs human "negative / not negative"; report it). Then: negative share overall (~16%), by category and by city — feeding the NB2 priority matrix. One figure + the city synthesis map (keep, single version).
5. **Voices** (1 figure/panel): 6–10 curated verbatim MEAL recommendations + message quotes, grouped by theme (unmet info, human contact, gratitude, urgency). Quotes in Spanish, translation in caption. This panel does more for the Executive Director than any wordcloud — the §9 wordcloud grids are cut; a top-distinctive-terms table per city/month goes to annex if needed.
6. **Repeat-asker vocabulary** (annex): what the 13% keep asking about — direct input to the intent roadmap.

**QA gate NB3:** pinned model versions + cached artifacts keyed by export hash; validation sample + κ reported before any percentage from LLM/sentiment models is quoted; clustering stability reported; every archetype has n, quote, and profile; no raw phone in any output.

---

## 7. Cross-cutting quality gates (all notebooks)

- [ ] `Run All` on clean kernel succeeds; runtime < 15 min excluding cached model inference.
- [ ] Reconciliation table (P10) printed at top and bottom; all figures' n trace to it.
- [ ] Figure budget respected (9 / 12 / 8); annex material clearly separated.
- [ ] Every figure: assertion-evidence title, subtitle with metric + n + window, brand palette via `theme.py`, source note.
- [ ] Zero PII in outputs (automated check).
- [ ] Peer review: second person runs all notebooks from a fresh clone and reproduces the canonical numbers before anything ships.

---

## 8. Exports for the dashboard (gold layer)

Generated by a final cell in each notebook into `exports/` (CSV, UTF-8, snake_case, PII-free). These are the **only** interface to Power BI — the dashboard never touches raw Excel.

| File | Grain | Key columns |
|---|---|---|
| `dim_user.csv` | user | `user_id`, `gender`, `age`, `age_flag`, `age_range`, `nationality`, `city_canon`, `department`, `city_duration`, `away_duration`, `destination_country`, `intends_to_stay`, `first_seen`, `n_messages`, `n_questions`, `dominant_category`, `archetype`, `is_repeat_asker`, `survey_sent`, `meal_responded` |
| `fact_message.csv` | message | `message_id`, `user_id`, `ts`, `date`, `category`, `intent_ext`, `sentiment`, `city_canon` (message text itself **excluded**) |
| `fact_meal.csv` | response | `user_id`, `ts`, `usefulness_rating`, `rating_num`, `would_recommend`, `discovery_channel`, `has_recommendation` |
| `agg_city.csv` | city | `city_canon`, `department`, `lat`, `lon`, `users`, `messages`, `dominant_category`, `pct_negative`, `mean_rating` |
| `agg_weekly.csv` | week × category | `week_start`, `category`, `messages`, `users` |
| `meta_run.csv` | run | export filename, row counts, window, generated_at, model versions |

Export validation: row counts match reconciliation table; no nulls in keys; `fact_message.user_id` ⊆ `dim_user.user_id`; a `qa.py` function signs off before files are written.

**Schema freeze:** the gold CSV schemas above are a frozen contract with the .pbix. Columns may be added; never renamed, retyped or removed without versioning (`meta_run.schema_version`) and a coordinated dashboard update. `run_pipeline.py` validates its own output against the frozen schema before finishing.

---

## 9. Notebook ↔ Power BI parity guarantee

The deliverable promise is: **every number on the dashboard is reproducible from the notebooks, and a new export refreshes the dashboard with zero rework.** That is guaranteed by construction plus verification:

**By construction**
1. One compute path: notebooks and `run_pipeline.py` import the same `src/sami/` functions — cleaning, categories, models, metrics are defined once.
2. One interface: the dashboard reads only `exports/` gold CSVs (frozen schema). No cleaning, no business logic in Power Query beyond types and the calendar table.
3. Metric definitions live in doc 01 §7 and are implemented once in Python; DAX only aggregates pre-computed columns (e.g. `is_repeat_asker` is computed in Python, DAX just averages it). If a metric needs logic, it goes to the gold layer, not to DAX.

**By verification (parity test, run before every delivery)**
- `run_pipeline.py` emits `exports/parity_check.csv`: the canonical-numbers table plus every dashboard KPI computed in Python (users, messages, % legal doc, mean rating + n, % negative, % repeat-askers, % outside taxonomy, per-city users/messages).
- After Power BI refresh, each KPI on screen is compared against `parity_check.csv` (manual check on the hidden About page, which displays the parity table side-by-side with live measures). Any mismatch is a release blocker.
- Full drill test on one city and one category: filtered dashboard counts must equal a Python groupby from the same gold files.

**Refresh simulation (acceptance test for the .pbix):** before handover, run the whole loop with the *old* May export as if it were new data — pipeline, refresh, parity check — touching nothing in the .pbix. If any visual breaks or any number needs manual editing, the guarantee is not met.
