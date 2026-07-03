# MMC Chatbot — Two Analysis Notebooks (Design)

**Date:** 2026-07-03
**Status:** Approved

## Goal

Build two new, self-contained Jupyter notebooks that take the MMC chatbot data
beyond the existing descriptive EDA into topic modeling, mixed coding, and
cross-cutting analysis. The existing `eda_responses.ipynb` and `eda_meal.ipynb`
are left untouched.

## Data sources

- `data_&_docs/MMC_bot_responses_Grupo_nuevo_1783087815.xlsx` — monday.com export,
  header on row 3 (0-indexed row 2), **946 user rows** (one row per WhatsApp
  phone number). Relevant fields:
  - Profile: `Nationality` (+ `Nationality_other`), `City` (+ `City_other`),
    `Gender` (+ `Gender_other`), `Age`, `Age Ranges`, `Minors`,
    `City_duration`, `Away_duration`, `Destination` / `Destination_Country`.
  - Conversation: `Messages` (raw user messages, concatenated, Spanish),
    `Text` (English translation), `Text 1` (LLM intent summary),
    `Chat_summary` (existing topic label, e.g. "humanitarian assistance",
    "legal documentation").
  - Engagement/time: `Questions per user`, `Timestamp` (first contact),
    `Last Message At` (sparse), `Survey sent`.
- `data_&_docs/MMC_MEAL_Group_Title_1783087939.xlsx` — monday.com export,
  header on row 3, **78 response rows**. Fields: utility rating, would-recommend,
  free-text recommendation, how-they-heard channel (+ free-text medium).

Join key between the two datasets: the `Name` field (`whatsapp:+<number>`).

## Key decisions (from brainstorming)

1. **Topic modeling method:** Embeddings + BERTopic
   (`paraphrase-multilingual-MiniLM-L12-v2` → UMAP → HDBSCAN).
2. **Infeasible analyses:** dropped, with an explicit "data gap" section
   explaining what extra data would be required. Data cannot support:
   fallback / no-response rate, response consistency (no bot output text),
   and true turn-level drop-off point (no per-turn logs).
3. **Notebook layout:** two new separate notebooks; existing EDA notebooks
   untouched.
4. **Cross-analyses (satisfaction × topic, demographics × topic):** live in the
   responses notebook, which joins MEAL in by phone number. The MEAL notebook
   stays focused on satisfaction descriptives.

## Conventions

- Reuse `src/palette.py` (monochrome blue ramp, `bar_colors()`), imported via
  `sys.path.insert(0, '../src')`, matching the existing notebooks.
- Dual-audience narrative: each section opens with plain-language
  **What this shows / Why it matters**, with **Technical note** callouts for
  non-obvious choices. Follows the tone of `eda_responses.ipynb`.
- Charts follow the `dataviz` skill guidance and the shared blue palette.

## Notebook A — `notebooks/analysis_responses.ipynb`

Covers 9 of the 12 requested analyses plus the two cross-cuts.

1. **Load & clean** — parse the monday.com export (header row 3, keep
   `whatsapp:` rows), normalize `City` (fold in `City_other`), `Age` /
   `Age Ranges`, timestamps. Build clean analysis text from `Text` (EN),
   keeping `Messages` (ES) for display.
2. **Topic modeling & clustering (BERTopic)** — multilingual embeddings → UMAP →
   HDBSCAN; report topic sizes, labels, representative messages. The
   topic-per-user assignment is persisted and reused by all downstream sections.
3. **Mixed coding (MMC + emergent)** — crosswalk BERTopic topics onto the MMC
   taxonomy (seeded from existing `Chat_summary` labels and the 10 documentary
   bases) and flag emergent topics; validate on a small hand-checked sample.
4. **Needs & entities** — keyword/dictionary extraction of trámites and
   institutions (PPT, EPS, Migración Colombia, ACNUR, SISBÉN, …); frequency
   ranking overall and by city.
5. **Geographic analysis** — query volume + topic mix across the 10 priority
   cities; reuse the existing Colombia map from the EDA notebook.
6. **Temporal analysis** — topic trends over time from `Timestamp`
   (first-contact date), weekly/monthly, with a manually curated
   migration-policy event overlay.
7. **Demographics × topic** — nationality / gender / age-range / city vs topic
   (proportion heatmaps).
8. **Engagement depth** — `Questions per user` distribution and single-question
   share. **Explicitly documented as engagement depth, not turn-level
   drop-off.**
9. **Repeated / reformulated questions (heuristic)** — split a user's `Messages`
   on line breaks, flag semantically similar consecutive messages via
   embeddings; labeled as an approximation.
10. **Satisfaction × topic** — join MEAL by phone number; utility and
    recommendation by topic (small-n caveat).
11. **Data gaps & limitations** — dedicated closing section stating that
    fallback rate, response consistency, true drop-off point, and content-gap
    *quality* all require turn-level logs + bot output text not present in the
    data.

## Notebook B — `notebooks/analysis_meal.ipynb`

Satisfaction descriptives only (78 responses; small-sample caveats throughout).

1. Load & clean.
2. Utility-rating distribution.
3. Would-recommend distribution.
4. How-they-heard channel (+ free-text medium).
5. Light thematic read of the free-text recommendations.

## Dependencies & risks

- Add to `pyproject.toml`: `bertopic`, `sentence-transformers`, `umap-learn`,
  `hdbscan`.
- **Main risk:** `torch` (a `sentence-transformers` dependency, CPU build,
  large) installing cleanly under `uv` on Windows, and the one-time embedding
  model download needing internet on first run. Verify the install and a
  minimal embed/BERTopic run **early**, before building sections around it.
- Existing env constraints (from project memory): `tool.uv.package = false`
  and `python-preference = only-system` must remain; Smart App Control blocks
  unsigned uv-managed Python.

## Out of scope

- Fallback / no-response rate by topic (no bot output data).
- Response consistency (no bot output data).
- True turn-level drop-off / abandonment point (no per-turn logs).
- Modifying the existing EDA notebooks.
