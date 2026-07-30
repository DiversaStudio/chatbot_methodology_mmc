# SAMI Analysis — Dashboard Requirements (Power BI, .pbix deliverable)

Requirements, build steps, UX conventions and quality checks for the decision dashboard. Audience: MMC Executive Director + programme/MEAL/content teams — non-technical, time-poor.

**The deliverable is a .pbix that MMC operates alone:** drop new exports → run one pipeline command → Refresh → everything updates, ready and clean. Nothing is rebuilt, retyped or re-styled at refresh time. The mechanics of that guarantee live in `02_notebook_requirements.md` §9 (parity) and Rule 4 (headless pipeline); this document assumes them.

---

## 1. Purpose and editorial rule

Three standing questions, one tab each, mirroring the narrative arc:

1. **Who is SAMI reaching?** (Act 1 — audience & coverage)
2. **What do they need?** (Act 2 — demand)
3. **Is it working?** (Act 3 — experience & gaps)

**Editorial rule — top of the top only.** The notebooks may hold up to 29 figures; the dashboard holds **12 visuals total across 3 tabs (≤4 per tab, plus a KPI band)**. The dashboard is not the analysis republished — it shows outcomes, never mechanics (no clusters math, no validation stats, no annex material). If a visual can't be defended as one of the twelve most decision-relevant views, it stays in the notebooks/report.

Recommendations, quotes, methodology → report. Deep dives → notebooks. The dashboard is the operational pulse.

---

## 2. Reproducibility architecture (what makes "just update the inputs" true)

1. **Single interface:** the .pbix reads only the gold CSVs in `exports/` (frozen schema, doc 02 §8). It never touches the raw Excel. All cleaning, categories, NLP-derived fields and metric logic are computed upstream in Python — Power Query does file loading, typing and the calendar table, nothing else.
2. **Parameterized path:** one Power Query parameter `DataFolder` points to `exports/`. Changing that single parameter relocates the whole model — no per-table source editing. Document it on the About page.
3. **Schema tolerance:** queries select columns **by name**, never by position; added columns don't break refresh; missing/renamed columns fail loudly (that's correct — schema is a contract).
4. **DAX only aggregates.** Flags and classifications (`is_repeat_asker`, `intent_ext`, `sentiment`, `archetype`, `age_flag`) are Python-computed columns. If a new metric needs logic, it is added to the gold layer and the pipeline, not invented in DAX. This is what keeps notebook numbers and dashboard numbers identical by construction.
5. **Dynamic everything:** titles/subtitles that carry n, window, or export date are measures fed by `meta_run` — never typed text. The only manually curated text is the "This period in 3 bullets" tile (explicitly marked as editorial).
6. **Refresh runbook (3 steps, on the About page):** ① copy the new exports into `datasets/responses/` and `datasets/meal/` → ② `python run_pipeline.py` → ③ open .pbix, Refresh. Then eyeball the About page parity table (Python-computed KPIs vs live measures side by side).
7. **Acceptance test before handover:** simulate a refresh with a different export (the May snapshot) end-to-end without touching the .pbix. Any manual intervention = not done.

---

## 3. Data model

Star schema from `exports/`:

- **Facts:** `fact_message` (grain: message; no text content), `fact_meal` (grain: survey response).
- **Dimensions:** `dim_user`, `dim_date` (generated, marked as date table), `dim_city` (with lat/lon), `dim_category` (7 official + extended intents; display order + color hex as data, so palette updates flow from the pipeline).
- **Support:** `meta_run` (freshness, window, schema version, model versions), `parity_check` (loaded but only surfaced on the About page).

Rules: single-direction relationships; no bidirectional filters; no calculated columns where a Python column or a measure works; all measures in one table, every measure with a filled description (feeds tooltips).

**Core measures:** `Users`, `Messages`, `% Legal Documentation`, `Median Messages per User` (`MEDIANX` over users — never an average of averages), `% Zero-question Users`, `% Repeat Askers`, `MEAL n`, `MEAL Response Rate` (numerator and denominator under the same filter context — test it), `Mean Usefulness (1–5)`, `% Would Recommend`, `% Negative Tone`, `% Outside Official Taxonomy`, plus vs-previous-4-weeks variants.

---

## 4. Information architecture — 3 tabs + hidden About

Global synced slicers on all tabs (left rail): **date range, city**. Category as a slicer only on Tabs 2–3. Nothing else global. Each tab: KPI band (3–4 cards) on top, ≤4 visuals below, question-as-title.

### Tab 1 — Who is SAMI reaching?
KPI band: Users · New users this period · Cities covered · % intending to stay in Colombia.
1. **Map — users by department/city** (bubble map from `agg_city`/`dim_city` lat/lon). The coverage view: where SAMI is present and, visibly, where it isn't.
2. **Weekly active users line** — reach over time, annotated peak (dynamic annotation via measure).
3. **Profile bar** — age ranges (sub-18-flagged records excluded, footnote), with gender as a legend or a paired small bar. One compact visual, not four.
4. **Settlement bar** — time in city / away duration: the "settled, not in transit" evidence.

### Tab 2 — What do they need?
KPI band: Messages · % Legal documentation · Top category this period · Fastest-growing category.
1. **Category mix bar** — the demand headline, official category colors.
2. **Category × city matrix** — share within city; cells with n<20 blanked ("·" + footnote). The localization view.
3. **Weekly trend by category** — top-4 + Other, direct labels, raw weekly points visible.
4. **Top procedures & institutions** — one ranked bar with a procedures/institutions toggle (bookmark or field parameter), rather than two visuals.

### Tab 3 — Is it working?
KPI band: MEAL mean rating (n in caption) · % Would recommend · % Negative tone · % Repeat askers.
1. **The funnel** — arrived → asked → engaged → not-repeat → surveyed → satisfied (built as a horizontal bar with conversion labels; clearer than the native funnel visual).
2. **Priority matrix** — scatter: volume × unmet-need score, bubble = users, quadrant labels in plain language. The single most important visual in the product.
3. **Coverage gaps bar** — % of messages outside the official taxonomy, by candidate intent.
4. **Negative tone by category** — the distress signal, linked by color to Tab 2's categories.

### Hidden — About the data *(reached via an ⓘ button on every tab; not a visible tab)*
Export date + window + row counts (`meta_run`) · parity table (Python KPIs vs live measures) · limitations in plain language (MEAL 7.5% → indicative; self-reported fields; sentiment validation κ) · metric glossary · 3-step refresh runbook · `DataFolder` parameter note.

**Cut from the previous 5-page design:** the separate Overview tab (its KPI role is absorbed by the per-tab bands; the "3 bullets" editorial tile moves to Tab 1's corner) and Data notes as a visible page (now hidden About). Satisfaction-over-time, discovery channel, archetype table, quotes drill-through → report only. Twelve visuals means saying no; these are the noes.

---

## 5. UX conventions (hard requirements)

- **5-second rule per tab:** title = the question; Z-pattern layout answers it; KPI band top, evidence below.
- **12-col grid**, aligned, generous whitespace; no free-floating visuals; fits 16:9 without scroll.
- **One interaction pattern:** slicers filter; click cross-highlights; ⓘ opens About. No mixed drill behaviors; no drill-through pages except About.
- **Titles:** visual titles are assertions where stable, questions where data shifts per refresh; subtitles carry metric + n + window via measures.
- **Color:** theme JSON generated from the same palette as `theme.py` (one source of truth); blue = magnitude; category hues fixed and identical to notebooks/report (driven by `dim_category.color_hex`); negative tone = madera grey-brown, never red/green alone; small-n/unreliable = grey + asterisk.
- **Numbers:** whole percentages; ratings to 1 decimal; Spanish data values, English UI; dates "25 Mar 2026."
- **Trust cues:** every MEAL-based visual shows n; tooltips explain metrics (from measure descriptions); empty filter states show "No data for this selection."
- **Accessibility:** contrast ≥ 4.5:1; alt text on all visuals; tab order set; mobile layout for Tab 1 only.

---

## 6. Build sequence

1. Theme JSON from palette; workspace + naming.
2. Power Query: `DataFolder` parameter, gold CSV queries (columns by name), types, calendar; QA page comparing row counts vs `meta_run` (kept hidden after build).
3. Model: relationships, hide keys, measure table with descriptions.
4. Tab 1 → approval by Francisco → Tabs 2–3 → About.
5. Interactions pass: synced slicers, KPI cards ignore cross-highlight, ⓘ navigation, tooltips.
6. Polish: dynamic titles, alt text, mobile Tab 1.
7. **Refresh simulation** (§2.7) and UAT (§7).

---

## 7. QA & acceptance checklist

**Reproducibility (release blockers)**
- [ ] Refresh simulation with a second export passes with zero manual edits to the .pbix.
- [ ] About-page parity table matches live measures exactly for every KPI.
- [ ] Filter to one city → users + messages reconcile with a Python groupby on the gold files.
- [ ] No hand-typed number or date anywhere (search the report for static text tiles; only the editorial bullets tile is allowed).
- [ ] `DataFolder` re-point test: move exports, change one parameter, refresh works.

**Data & UX**
- [ ] MEAL visuals never show a metric without n; response-rate measure recomputes correctly under filters.
- [ ] Small-n suppression verified on a tiny city.
- [ ] No message text or phone-derived value in the model.
- [ ] Task-based UAT, non-technical tester, <60s each: "Which city has most users?" · "What does Cúcuta ask about most?" · "Is humanitarian demand growing?" · "How satisfied are users and how much should I trust it?" · "Which need is big but badly served?"
- [ ] Page load <3s; interactions <1s.
- [ ] Handover: runbook executed once by someone other than the builder; theme, measures, glossary documented.

---

## 8. Methods, alternatives & pitfalls

- **Maps:** bubble map on provided lat/lon (no geocoding-by-name). Department choropleth needs a Colombia TopoJSON shape map — nice-to-have; don't burn days, the bubble map is acceptable.
- **Funnel:** horizontal bars + conversion labels, not the native funnel visual.
- **Priority matrix:** native scatter + constant-line quadrants; direct bubble labels; ≤8 categories.
- **Toggle visuals:** field parameters (procedures/institutions) keep Tab 2 at four visuals without losing content.
- **Pitfall — refresh-breaking visuals:** custom visuals from AppSource add governance and update risk; use native visuals only.
- **Pitfall — averaged averages** and **filter leakage** on rate measures: covered by the parity and filter tests above.
- **Alternative:** Looker Studio on the same gold CSVs if Power BI licensing becomes a constraint — the frozen gold contract makes the tool swappable. Build only one.
