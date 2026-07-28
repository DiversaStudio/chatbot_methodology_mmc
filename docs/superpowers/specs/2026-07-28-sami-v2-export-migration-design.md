# SAMI v2 export migration — design

**Date:** 2026-07-28
**Status:** approved
**Scope:** `src/sami/` (`schema`, `load`, `canon`, `cohort` (new), `export`, `qa`,
`config`, `metrics`), `run_pipeline.py`, `tests/`, `notebooks/01`, `notebooks/02`

## Problem

The chatbot platform was replaced. The exports it produces are a different shape
and, in three places, measure different things. The pipeline does not run against
them at all, and several of the ways it *would* fail are silent.

### The new files

| | retired | current |
|---|---|---|
| responses | `MMC_bot_responses_1783087815.xlsx` | `Users_Group_Title_2807.xlsx` |
| survey | `MMC_MEAL_1783087939.xlsx` | `Survey_Responses_Group_Title_2807.xlsx` |

Measured, not assumed: 1,460 response rows / 1,392 users (was 946 / 917), 4,975
raw message lines (was 3,207), 142 survey responses / 115 users (was 78 / 69),
range extended from Jul 3 to Jul 28.

### Hard failures — the pipeline cannot read the files

1. **Renamed keys.** `Name`→`Address`, `Timestamp`→`Created At`,
   `Messages`→`QA Messages`, `Chat_summary`→`QA Summary`, and the profile
   fields lowercased (`City`→`city`, …). `schema.HEADER_MARKERS` looks for
   `name`+`timestamp`, so `detect_header_row` raises on both files.
   `RESPONSES_REQUIRED` is 6/6 missing.
2. **No channel prefix.** `load._read_whatsapp` keeps rows where `Name` starts
   with `whatsapp`. The v2 `Address` is a bare number, so every row is dropped
   and the loader raises "no WhatsApp rows".
3. **MEAL reads `Name`/`Timestamp` directly** (`load.load_meal`) → `KeyError`.
3b. **`qa.py` holds a second copy of the contract.** `qa._SHEET` expects sheets
   `mmc bot - responses` / `mmc-meal`; the v2 files are `users` /
   `survey responses`. `qa._CRITICAL` lists the old column names. Both are
   checked by `qa.validate_schema`, which `facade.load_sami` calls *before* the
   loaders — so this fails first, ahead of defects 1–3.

### Silent failures — worse, because they produce numbers

4. **Duplicate survey columns.** The survey file carries both v1 and v2 variants
   of four questions, v1 first and **empty**. `schema.meal_column_map` matches
   on first hit, so `usefulness_rating`, `would_recommend` and
   `discovery_channel` all bind to empty columns, and the position-6 fallback
   then labels the *real* usefulness data as `discovery_other`. One warning
   fires. This is the most dangerous defect in the set.
5. **Phone key parses as float.** `Address` reads as `573154047912.0`;
   `load.digits` yields a 13-char key against the old 12. Every `user_id`
   changes, breaking the tone-label join and any comparison with prior runs.
6. **`message_id` is positional.** `export.build_fact_message` derives it from
   `messages.reset_index()`, and `load.load_messages` sorts the spine by
   `["user_id","ts"]`. Adding 1,768 lines re-sorts it, so every `message_id`
   shifts and `validation/tone_gold_labels.csv` (200 rows) silently re-attaches
   to different messages.

### Measurement changes — the instrument itself changed

Confirmed against `data_&_docs/Encuesta + componente MERA chatbot(1).xlsx`,
whose `EncuestaV1`/`EncuestaV2` sheets are the authoritative questionnaire diff.

7. **v1 screened Colombians out.** V1 **Q3** — *"Lastimosamente no cuento con
   información para población colombiana, por lo que no podemos continuar"* —
   terminated the survey when Q2 was Colombia. Absent from V2. Colombians are
   not rare in v1 rows, they are **impossible**: 0 across all 1,355 migrated
   rows, 22 of the 105 v2 rows. Nationality therefore cannot be pooled across
   cohorts, and every future export keeps carrying the v1 rows, so this does not
   age out.
8. **Questions retired.** V2 drops Q9 `Away_duration`, Q10 `Prev_country`,
   Q13 `would_recommend`, Q14 `recommendation_text`. Their totals freeze while
   every other total grows — which reads as collapse, not retirement.
9. **New question with broken skip logic.** V2 **Q12a** — *"¿Por qué la
   información entregada no fue útil?"* — is specified to fire only for
   Nada/Poco/Medianamente útil (44 users). It was asked of **118**, including 75
   who rated the service Útil or Muy útil, who answered with negations
   (`No`, `Todo bien gracias`). Only the 43 responses from dissatisfied users
   are analytically usable.
10. **Summary field changed format.** v1 rows carry a short taxonomy label
    (`#legal documentation`); v2 rows carry LLM prose
    (`[2026-07-24 14:15] El usuario preguntó sobre X, Y y Z`), which lists
    several needs per user and has no dominance signal.
    `taxonomy.normalize_category` is an exact-match lookup, so prose returns
    `unclassified`: 19 rows today (1.4%), every future row later. v2
    `QA Summary` is also only 18% populated against 84% for v1.
11. **City option list widened**, 3 → 8 (`Cucutá/Medellín/Otra` →
    `Bogotá, Cali, Cúcuta, Ipiales, Medellín, Necoclí, Pasto, Otra`). Largely
    absorbed: `canon.clean_city` already merges `City` with the `City_other`
    free text and recovers 391 of the 549 v1 "Otra" responses. Residual is a
    quality gap (v1 29% unresolved vs v2 17%), not a comparability blocker.

### New capability

The v2 export adds a registration funnel (`Registration Status` — Completed
1,449 / In Progress 8 / Abandoned 2 — plus `Registration Started`,
`Registration Completed`, `Attempts`, `Drop-off Question`), `Language`
(es 1,445 / en 4 / no fr), `Safety Alert` and `Escalation Status` (5 each), and
`Is Returning User`.

Note: the language selector is **not** documented in `EncuestaV2` despite being
live, and V2 retains an orphaned `Q10_1` whose skip condition references the
deleted Q10 — a dead branch that can never fire.

## Decisions

| Question | Decision |
|---|---|
| Spec boundary | Ingestion + cohort semantics. **NLP re-validation is a separate spec** (needs a GPU run and its own κ gate). |
| Support both file formats? | **No — one reader, v2 only.** Verified: the v2 export contains the v1 data. For the 917 carried-over users it holds *more* message text (3,371 lines vs 3,207 — the old file stopped at Jul 3), preserves the `Chat_summary` labels (903 identical), and `Prev_country`, the one dropped column, was **empty in the old file anyway** (0 non-null). Total loss is 18 message lines for one user. Analyzing v1 is a filter on `instrument_version`, not a second reader. |
| Where does comparability knowledge live? | **In the code, as a hard guard.** MMC re-runs this pipeline themselves; a caveat in a notebook they don't read prevents nothing. Non-poolable variables are split automatically; unclassified variables raise. |
| `dominant_category` | **Keep the label, add a tripwire.** Prose rows → `unclassified`; the run fails when prose exceeds 5% of non-null summaries. Rejected: multi-label parsing (redefines every existing percentage, built on 19 examples) and retiring the field (NB2's demand mix and priority matrix are built on it). |
| New v2 fields | **Full analysis this pass**, per user direction — carried into the gold layer *and* given notebook figures. |
| Test data | **Synthetic fixtures + invariants.** |

### Relationship to the replicability spec

`2026-07-27-sami-pipeline-replicability-design.md` decided "no synthetic
fixture". That decision was about **delivering data** — the repo stays code-only
and real exports travel out-of-band. It is unchanged. The fixtures added here
are **test doubles** with fabricated phone numbers, carrying no real data, and
exist so the suite stays green on an export we have never seen. The two do not
conflict.

## Design

### 1 · Ingestion — declarative column contract

Extends `schema.py`, which already owns every assumption about export shape.
Rejected alternatives: adapter classes per platform version (machinery for a v3
that does not exist), and inline renames in `load.py` (scatters shape knowledge
across loaders — exactly what `schema.py` was created to prevent).

- `RESPONSES_COLUMN_MAP` / `MEAL_COLUMN_MAP`: source → canonical name.
- Per-source header markers: responses `Address`+`Created At`, survey
  `Respondent`+`Recorded At`.
- `normalize_columns(df, source)` applied immediately after `read_excel`.
  Everything downstream keeps today's canonical names and is untouched.
- `load.py`: drop the `whatsapp:` prefix filter; strip the float `.0` from the
  phone key **before** hashing, so `user_id` is byte-identical to today's for
  all 917 carried-over users.
- `MEAL_QUESTION_MARKERS` resolution changes from first-match to: among columns
  matching a marker, **prefer the one carrying data**; tie-break on last
  occurrence. Fixes defect 4.

### 2 · `cohort.py` — new module

```python
class Policy(Enum):
    POOLABLE, SPLIT, V1_ONLY, V2_ONLY

POLICY: dict[str, Policy] = {
    "nationality_canon":    SPLIT,     # v1 Q3 terminated Colombians
    "away_duration_canon":  V1_ONLY,   # Q9 retired in v2
    "would_recommend":      V1_ONLY,   # Q13 retired
    "recommendation_text":  V1_ONLY,   # Q14 retired
    "no_usefulness_reason": V2_ONLY,   # Q12a added
    "city_canon": POOLABLE, "age_num": POOLABLE, ...
}
```

**Completeness rule:** every column written to `dim_user` and `fact_meal` must
appear in `POLICY`. A test enumerates those columns and fails on any that is
unclassified, so the table cannot drift behind the schema.

```python

def instrument_version(df) -> pd.Series   # 'Migrated From v1' notna -> v1 else v2
def guarded(frame, col) -> pd.DataFrame   # raises CohortError if unclassified
```

`CohortError` names the variable, the reason it cannot be pooled, and the file
to edit — the same "message carries the fix" contract as `SchemaError`. A future
export gaining a field cannot be aggregated until someone classifies it.

`instrument_version` derives from `Migrated From v1` and degrades correctly: an
export with no migrated rows yields all-v2.

### 3 · Value canon

Checked against the running code rather than inferred from the export, which
cut this section down to two changes:

- **`CITY_CANON` + `CITY_COORDS` gain `Pasto`.** The other 11 relevant cities
  already canonicalize and already have coordinates — the table was built from
  the v1 `City_other` free text, which already contained Bogotá, Cali, Soacha,
  Barranquilla and the rest. Pasto is the one v2 dropdown option nobody had
  ever typed, so it fell into `Otra` and had no coordinates (which would
  silently drop it from `dim_city` and the NB1 maps).
- **`DISCOVERY_DISPLAY_EN` gains the two v2 wordings** (`Otro migrante`,
  `Recomendación de ONG`), mapped to the same English labels as their v1
  equivalents. Unmapped values pass through untranslated, so without this one
  answer renders as two slices.

Three changes that looked necessary are **not**, because the existing code
already contains the problem: `gender_display` is a closed-set lookup, so junk
(`bhdhb`, `jj`) already renders as `Other` and `Trans` as `Transgender`;
`yes_no_display` already folds accents, so `Sí` and `Si` are one bar; and
`nationality_canon("Colombia")` already works.

### 4 · Gold layer

- **`message_id` becomes a content hash**, not a positional index. Fixes defect
  6 and is required regardless of the NLP spec.
  **Consequence:** this orphans the 200 existing rows in
  `validation/tone_gold_labels.csv`, which are keyed on the old positional ids.
  That is intentional — those ids are already invalid against the new corpus, and
  a stable key is a precondition for re-keying them. The follow-up NLP spec owns
  re-keying and re-scoping that file. Until it lands, the tone gate is not
  runnable, which is why NB3 is out of scope here.
- `dim_user` gains `instrument_version`, `language`, `registration_status`,
  `attempts`, `is_returning`, `safety_alert`, `escalation_status`.
- `fact_meal` gains `no_usefulness_reason` **and `reason_is_valid`**. The flag
  encodes defect 9 in the data rather than in a memo, so a Power BI user cannot
  count 118 "reasons for failure" when only 43 are real.
- New `agg_registration_funnel` (Started → Completed / Abandoned, with attempts
  and drop-off question) and `agg_language`.
- Agg tables built on a `SPLIT` variable gain an `instrument_version` dimension.
- `qa.py` prose tripwire: fail the run above 5% prose-format summaries.
- `schema_version` bumped `"2"` → `"3"` in `export.build_meta_run`;
  `exports/_schema.md` regenerated.

### 5 · Notebooks

**NB1** — reconciliation counts refreshed top and bottom (946→1,460 records,
917→1,392 users, 2,991→~4,975 messages, 69→115 MEAL); §1 sources-and-reliability
chart marks retired fields rather than showing them as missing data;
§2 minors plot picks up the accent fold; §3 nationality figure **split by
cohort** with the Q3 screen-out stated in the narrative; §3 `away_duration`
marked v1-only/frozen; **new sections** for the registration funnel and language.

**NB2** — §5 MEAL n 69→115; `would_recommend` becomes a v1-only frozen panel;
**new** "why wasn't it useful" themes over the 43 valid responses; §6 priority
matrix `min_meal_n=20` fallback re-checked against the larger MEAL sample, and
v2 users' `unclassified` category means they are excluded at
`export.build_agg_priority_matrix` — this must be stated, not silent.

**Caveat recorded:** the v2 cohort is 105 users over 5 days. The registration
and language figures are built now per user direction and will want redrawing as
the sample grows.

**NB3 is out of scope.** It will fail loudly at
`taxonomy.assert_archetype_mapping` once the corpus grows — by design, that
guard exists to prevent mislabelled archetypes shipping. The follow-up spec
covers archetype re-mapping and tone re-validation. This spec verifies via
`run_pipeline.py --skip-nlp`.

### 6 · Testing

Synthetic fixtures committed under `tests/fixtures/`: a users export and a
survey export with fabricated phone numbers, banner rows, the duplicate v1/v2
survey columns, and both a migrated and a v2-native row. Exact-count assertions
move onto them.

Tests against the real export become invariants that hold for *any* export:
totals reconcile, no PII leaks, `user_id` is stable, the schema contract is
satisfied. These skip cleanly when the real file is absent.

New coverage: cohort policy and `CohortError`; the MEAL duplicate-column pick
(a fixture where the v1 column is empty and the v2 column has data); `message_id`
stability under re-sort; phone `.0` normalization producing the pre-migration
`user_id`; the Q12a validity filter; the prose tripwire firing above threshold.

## Verification

1. `pytest` green.
2. `python run_pipeline.py --check` passes on the v2 files.
3. `python run_pipeline.py --skip-nlp` writes all tables; `parity_check.csv`
   all-match; PII scan clean.
4. `user_id` for the 917 carried-over users identical to the pre-migration
   exports — the concrete proof that defect 5 is fixed.
5. NB1 and NB2 execute end to end via nbconvert.

## Out of scope

NB3 and all NLP re-validation (archetype re-mapping, tone gold re-keying and
re-labelling, the κ gate); the Power BI `.pbix` rebuild; purging the two
PII-bearing xlsx from git history (tracked separately); reporting the Q12a skip
-logic bug to the platform team (a message, not code).
