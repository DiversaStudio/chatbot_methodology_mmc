# SAMI Pipeline Foundation — Design Spec

**Date:** 2026-07-22
**Branch:** `feature/sami-pipeline-foundation`
**Scope:** Sub-project 1 of 5 in the SAMI notebook rework. This spec covers **only** the shared `src/sami/` modules, pseudonymization, the reconciliation table, and the pytest suite. The three notebooks, `run_pipeline.py`, the `exports/` gold layer, and NLP/LLM/sentiment caching are each deferred to their own later specs.

**Reference docs:** `requirements/01_storytelling_and_analysis_scope.md`, `requirements/02_notebook_requirements.md`. Where this spec and those docs disagree, the docs win; this spec only narrows scope to the foundation.

---

## 1. Motivation & direction

The current repo has three inline notebooks that each paste their own loading/cleaning code with drifting dictionaries — the failure mode doc 02 Rule 1 names ("divergent cleaning is how numbers stop reconciling"). This foundation replaces that with **one compute path**: a `src/sami/` package that notebooks and the future headless pipeline both import.

**Direction note (supersedes prior preference):** earlier sessions settled on "self-contained notebooks, inline everything, no `src` imports, no cache." That is explicitly reversed here per user decision on 2026-07-22 — the deliverable is a refreshable Power BI (.pbix), which requires a shared, headless compute path. The self-contained-notebook and no-cache memories no longer apply to this project.

## 2. Data contract (confirmed against real files)

- **Responses:** `data_&_docs/MMC_bot_responses_1783087815.xlsx`, sheet `mmc bot - responses`, `header=2`, 29 columns (doc mentions up to 33 — loader must tolerate drift). Confirmed July 2026 export.
- **MEAL:** `data_&_docs/MMC_MEAL_1783087939.xlsx`, sheet `mmc-meal`, `header=2`, 7 columns (Spanish question headers renamed to `usefulness_rating`, `would_recommend`, `recommendation_text`, `discovery_channel`, `discovery_other`).
- The `_060526` files are the older May snapshot and are **not** used.
- The 7 official categories are data-determined (a leftover prompt row in `Chat_summary` names them): `legal_documentation`, `humanitarian_assistance`, `Protection`, `employment`, `organization_search`, `journey_information`, `services`, plus `unclassified`.

## 3. Architecture (Approach B: faithful modules + one facade)

```
src/sami/
├── __init__.py        # exposes load_sami(), SamiData
├── config.py          # paths, DATA_HEADER_ROW=2, SAMI_SALT loading from .env
├── load.py            # Excel → cleaned frames; pseudonymize; message spine; category
├── canon.py           # city/dept/nationality/duration canonical dicts + fold/map fns
├── taxonomy.py        # 7 official categories + normalizer; entity/institution patterns
├── theme.py           # brand palette, plotly/mpl templates, EN display maps (port palette.py)
└── qa.py              # schema validation, reconciliation table, PII scan, P1–P10 checks
```

Ports and then **deletes** the old modules:
- `load.py` ← `mmc_data.py` (+ `mmc_text.py`: `split_messages`, `is_courtesy`, `SPANISH_STOPWORDS`).
- `taxonomy.py` ← `mmc_entities.py` `ENTITY_PATTERNS` + a new `Chat_summary` → 7-category normalizer.
- `theme.py` ← `palette.py`.

The reformulation-similarity / emotion-pipeline helpers in `mmc_text.py` belong to NB3; they are carried into `taxonomy.py`/`theme.py` only if trivially reusable, otherwise deferred to the NB3 spec (not deleted-then-lost — noted for migration).

### 3.1 The facade

```python
load_sami(responses_path=None, meal_path=None) -> SamiData
```

Runs the full sequence **once**, deterministically (fixed sort, no randomness). Both notebooks and `run_pipeline.py` call this and receive identical frames.

`SamiData` — frozen dataclass:
| Attribute | Grain | Notes |
|---|---|---|
| `responses` | one row per user-record | cleaned, canon, age-flagged, dominant category, `user_id` |
| `messages` | one row per parsed message | P6 spine: `user_id, ts, message, seq, n_msgs_user` |
| `meal` | one row per user | P8 deduped, renamed columns |
| `reconciliation` | metric table | doc §7 canonical numbers (P10), computed from data |
| `run_meta` | dict/record | export filename, row counts, min/max ts, salt-present flag, per-check results, generated_at |

### 3.2 Processing order (inside `load_sami`)

schema-validate → drop banner/all-NaN/artifact rows → **pseudonymize (drop `Name`)** → type coercion → `_other` consolidation → canonicalization → message spine → category from `Chat_summary` → MEAL keying & dedup → age reliability flag → reconciliation table. Each step logs its validation counter into `run_meta`.

## 4. Pseudonymization & PII gate (P1)

- `user_id = sha256(SAMI_SALT + digits(Name))[:12]`, computed in `load.py`; raw `Name` and any digit/phone column dropped in the same function before the frame is returned. No raw identifier ever exists on a `SamiData` frame.
- `SAMI_SALT` read from gitignored `.env` via `config.py`. A random salt is generated into `.env` during setup. If `SAMI_SALT` is missing/empty, `load_sami()` raises a clear error — never a silent empty-salt fallback.
- `.env` added to `.gitignore`.
- `qa.pii_scan(obj)` scans all string columns of a DataFrame (or a file) for `whatsapp:` and any 7+ digit run; returns violation records. Zero hits required. Used in tests and before any future export.

## 5. QA & reconciliation

- `qa.validate_schema(path, kind)` — asserts sheet name, `header=2`, critical columns present (**fail** on missing critical, **warn** on extra), 100% timestamp parse on non-null. Logs export filename + row count + min/max timestamp as the run's identity card.
- `qa.reconciliation_table(SamiData)` — emits the doc §7 table from data. Rows requiring NB3 outputs (`% negative tone`, and any sentiment-derived value) render as `pending` in the foundation; `% legal documentation` and `repeat-askers` (volume-based p90 proxy) are computable now.
- P2–P9 each map to a small check function in `qa.py` returning `(name, passed, detail)`. `load_sami()` runs them; critical failures raise, soft failures warn. Reported counters: dropped-row count (≤ known artifacts), coercion-failure counts per column, `_other` consolidation non-null ≥ original, unmapped-city share (< 3% target; new unmapped values listed, never silently bucketed), unclassified-category share, MEAL post-dedup one-row-per-user assertion, age-flag count.

## 6. Testing (exhaustive — full P1–P10 coverage)

pytest in `tests/`, extending the existing suite:

- **Reconciliation:** users/records/messages/users-with-text land at the values from a first real run (pinned exactly during implementation; doc targets 918 / 947 / 2,993 / 800).
- **P1 PII:** `pii_scan` zero on all `SamiData` frames; `user_id` matches `^[0-9a-f]{12}$`; raw `Name`/phone columns absent; same salt → stable ids; different salt → different ids; missing salt → raises.
- **P6 spine:** `sum(n_msgs_user unique per user) == len(messages)`; empty/whitespace/courtesy-noise dropped and counted.
- **P4/P5 canon:** `_other` consolidation non-null ≥ original main field; known city variants (`medellin antioquia`, `bogota dc`, accent/case folds) map correctly; non-cities (`colombia`, departments, digits) → excluded with reason; unmapped values listed.
- **P7 taxonomy:** `#legal_documentation`, `legal documentation`, `#legaldocumentation`, `#legal documentation` all → `legal_documentation`; prompt-leftover row → dropped or `unclassified`; comma multi-label → dominant or `unclassified`.
- **P8 MEAL dedup:** one row per `user_id`; most-recent timestamp kept.
- **P9 age flag:** Age<18 → `unreliable_sub18`; count reported; excluded from age means.
- **P3 coercion:** timestamp→UTC datetime, Age/Questions→numeric with `errors='coerce'`; failure counts reported; unexpected new failures fail loudly.
- **Determinism:** two `load_sami()` calls produce frame-equal outputs.

## 7. Deliverables

- `src/sami/` package (7 files) with `load_sami()` + `SamiData`.
- Old `src/mmc_*.py` deleted; `src/palette.py` ported and deleted.
- Generated `.env` (gitignored) with `SAMI_SALT`; `.gitignore` updated.
- `tests/` exhaustive suite, green.
- No notebook changes in this sub-project (notebooks still reference old modules and will break until their own specs — acceptable and expected; called out so it is not a surprise).

## 8. Out of scope (later sub-projects)

`run_pipeline.py`; `exports/` gold CSVs (`dim_user`, `fact_message`, `fact_meal`, `agg_city`, `agg_weekly`, `meta_run`, `parity_check`); the three notebooks; embeddings/sentiment/LLM classification + caching; Power BI parity verification.

## 9. Acceptance criteria

1. `from sami import load_sami; d = load_sami()` returns a `SamiData` with all five attributes populated (starred reconciliation rows `pending`).
2. `pytest` green, including PII scan returning zero and reconciliation numbers pinned.
3. No raw phone number or `whatsapp:` string present in any `SamiData` frame.
4. Old `mmc_*.py` / `palette.py` removed; nothing in `src/sami/` imports them.
5. `load_sami()` is deterministic across runs.
