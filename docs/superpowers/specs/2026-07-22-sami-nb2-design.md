# SAMI NB2 — Demand, behaviour & experience (Acts 2–3 quantitative) — Design

Sub-project 3 of the SAMI pipeline rework (foundation merged `e8d4fab`; NB1 merged
`deb0e2b`). Reads with `requirements/01_storytelling_and_analysis_scope.md` §Act2–3 and
`requirements/02_notebook_requirements.md` §5. Branch: `feature/sami-nb2`.

**Mandate:** the quantitative middle of the story — what users need, where and when, and
whether they're getting it — carried with statistical discipline (every comparative claim
earns a test + effect size or is tagged directional-only). Hard cap **12 figures**.

**Decisions locked (user, 2026-07-23):**
- **Design approved as-is.** Build the §1–§5 figures now (figures 1–11).
- **Priority matrix (§6) deferred.** The matrix is NB2's climax but its unmet-need axis
  needs NB3's validated negative-sentiment cache, which does not exist yet. Build figures
  1–11 now; leave the matrix as a **clearly-marked deferred placeholder cell** (markdown
  stub stating the dependency + the intended 3-axis blend), wired in after NB3 lands. No
  provisional 2-axis figure, no stub cache — the matrix simply is not rendered this pass.
- Render engine: **matplotlib** (theme.py template), following NB1. New notebook file
  `notebooks/02_demand_behaviour_experience.ipynb`.
- Gold exports still **deferred** to the later `run_pipeline` + `src/sami/exports.py`
  sub-project. NB2 is purely analytical (figures + reconciliation). No notebook `to_csv`.

---

## 1. Module changes (notebooks consume, modules compute — Rule 3)

### New `src/sami/stats.py`
Statistical primitives so no test lives inline in the notebook.
- `cramers_v(confusion: pd.DataFrame) -> float` — bias-corrected Cramér's V from a
  contingency table.
- `assoc_test(a: pd.Series, b: pd.Series) -> dict` — builds the contingency table and
  runs **chi-square**, switching to **Fisher's exact** when any expected cell < 5 (2×2)
  or flagging low-expected-cell tables otherwise. Returns
  `{stat, p, dof, test, cramers_v, min_expected, n, meaningful}` where
  `meaningful = (cramers_v >= 0.1 and min_expected >= 5)`.
- `bootstrap_ci(values, statistic=np.mean, n_boot=1000, ci=0.95, random_state=0) -> (lo, hi, point)`
  — deterministic percentile bootstrap for the mean-rating CI.

### New `src/sami/metrics.py`
Reusable metric frames (single compute path — the same functions the later
`run_pipeline` will call).
- `funnel_stages(responses, messages, meal) -> pd.DataFrame` — ordered stages with
  absolute n and stage-to-stage conversion:
  arrived (users) → asked ≥1 question → single-touch vs engaged (≥2 msgs) →
  repeat-asker → surveyed (Survey sent / MEAL responded) → satisfied (rating in top band).
  Every stage-n must trace to the P10 reconciliation table.
- `weekly_category_counts(messages, top_n=4) -> pd.DataFrame` — messages per ISO week ×
  top-N category (rest folded to "Other"), at record-arrival granularity (see grain note).
- `category_share(frame, col="dominant_category") -> pd.Series` — normalized share.
- `city_category_mix(messages, top_cities=5) -> pd.DataFrame` — 100%-stacked source frame,
  top-5 cities + Other.
- `priority_matrix_frame(...)` — **stubbed/deferred this pass**: signature defined with an
  optional `neg_by_category` param and a docstring documenting the deferred 3-axis blend,
  but not called by the notebook until NB3 exists. (Keep it importable; do not render.)

### `taxonomy.py` extension
- `ENTITY_KIND: dict[str, str]` — tag each `ENTITY_PATTERNS` key as `"institution"` or
  `"procedure"` (e.g. ACNUR/SENA/ICBF/Migración Colombia/Registraduría → institution;
  PPT/PEP/Visa/Cédula/Pasaporte/EPS/SISBÉN → procedure). Powers the §1 two-panel split.
- `entity_counts_by_kind(texts) -> dict[str, pd.Series]` — thin wrapper over the existing
  `entity_counts`, partitioned by `ENTITY_KIND`.

### `canon.py` extension (if needed for §3)
- `city_duration_canon()` + order — the §3 duration×city cut uses **`City_duration`**
  (settlement time in current city), which `load.py` does not yet derive. Add
  `CITY_DURATION_CANON` (+ order) and derive `city_duration_canon`/`_order` in
  `load.load_responses`, mirroring the existing `away_duration_*` treatment. Reuse the
  same fold-keyed, mojibake-fixing approach.

### `theme.py`
- Unchanged. Add small helpers only if a figure needs them (e.g. a 100%-stacked bar color
  cycle keyed to the 7 categories, so category colors are stable across figures).

### Tests
- New `tests/test_stats.py` — Cramér's V against a hand-computed table; `assoc_test`
  chi-square↔Fisher switch on a thin-cell table; `bootstrap_ci` determinism (fixed seed →
  fixed interval) and coverage sanity.
- New `tests/test_metrics.py` — funnel stages monotic-non-increasing and top stage ==
  reconciliation users; weekly counts sum to message total; city mix columns sum to 1.0.
- Extend `tests/test_taxonomy.py` — every `ENTITY_PATTERNS` key has an `ENTITY_KIND`;
  `entity_counts_by_kind` partitions exhaustively.
- Full suite stays green.

---

## 2. Grain & small-n discipline (doc 02 §5 guardrails)

- **Grain note (stated in-notebook):** messages have no per-message timestamp — each
  inherits its response-record `ts`. Weekly/daily trends are therefore at
  **record-arrival granularity**, not true per-message send time. Say so on the time figures.
- **Small-n rule:** the MEAL join is ≈69 users. No chart cell renders with n<20 without a
  **visible warning** in the subtitle. Per-category MEAL rating **falls back to the overall
  rating** where a category's n<20 (annotated), rather than plotting an unstable per-category mean.
- **Statistical bar (§3):** a cross-cut figure is shown **only if** `assoc_test(...)["meaningful"]`
  is True (Cramér's V ≥ 0.1 and min expected cell ≥ 5). Otherwise the finding is rendered as
  a one-line "no meaningful difference (V=…, p=…)" statement — which is itself a valid result —
  and the figure is dropped. Don't pad to hit 12.

---

## 3. Notebook structure (12-figure hard cap — doc 02 §5; matrix deferred → 11 built)

| # | Section | Figure | Source |
|---|---------|--------|--------|
| — | top | Reconciliation table (P10) + identity card (file, rows, window) | facade |
| 1 | Demand mix | Category share overall (bar) | `category_share(messages)` |
| 2 | Demand mix | Category mix by city — 100%-stacked, top-5 + Other | `city_category_mix` |
| 3 | Demand mix | Institutions vs procedures — two-panel | `entity_counts_by_kind(messages.message)` |
| 4 | Over time | Weekly messages by top-4 categories — raw points **under** spline | `weekly_category_counts` |
| 5 | Over time | Daily usage + annotated spikes (no policy-alignment claim unless dated register given) | messages `ts` |
| 6 | Cross-cuts | Settlement duration × city — **conditional** on `assoc_test.meaningful` | `city_duration_canon` × `city_canon` |
| 7 | Cross-cuts | Gender × nationality — **conditional** on `assoc_test.meaningful` | `gender_clean` × `nationality_canon` |
| 8 | Funnel | The funnel centerpiece — absolute n + stage conversions | `funnel_stages` |
| 9 | Satisfaction | Usefulness distribution + would-recommend (n in title) | meal |
| 10 | Satisfaction | Mean usefulness rating — bootstrap 95% CI (~1,000 resamples) | `bootstrap_ci` |
| 11 | Satisfaction | Satisfaction over time — **indicative only**, reach-vs-satisfaction separation kept | meal `ts` |
| 12 | Priority matrix | **DEFERRED** — markdown placeholder stating NB3 dependency + intended 3-axis blend | (after NB3) |
| — | close | 5-bullet "what we now know" + reconciliation (must match top) | facade |

Conditional figures 6/7: if not `meaningful`, replace the figure with the one-line
"no meaningful difference" finding and note that the age×destination cut was killed
(cells n≤6, doc 02 §5). Final rendered figure count is 9–11 depending on which cross-cuts
survive — under the 12 cap by design.

Every figure: assertion-evidence title; subtitle with metric + n + window; `theme.py`
palette (category colors stable across figs 1/2/4); source note.

---

## 4. QA gates & acceptance (doc 02 §5 + §7)
- `Run All` clean kernel succeeds, < 15 min; reconciliation printed top and bottom, identical.
- Every figure's n traces to P10; **funnel stages sum correctly against P10**.
- Every comparative claim carries a test + effect size, or an explicit "directional only" tag.
- Small-n rule enforced: no chart cell with n<20 lacks a visible warning.
- Rendered figure count ≤ 12 (matrix deferred; 9–11 expected).
- Zero PII: `qa.pii_scan` over notebook data + grep rendered outputs for `whatsapp:` /
  7+-digit runs → 0.
- No inlined loaders/logic: notebook imports `from sami import load_sami` +
  `sami.stats` / `sami.metrics` / `sami.taxonomy` / `sami.theme` only; any logic >15 lines
  is in a module.
- All new module code covered by pytest; full suite green.
- Whole-branch Opus review before merge (as foundation + NB1).
