# Data sources

This pipeline reads exactly two Excel files: the chatbot **responses** export
and the **MEAL** survey export. This document states what each one must
contain, how the pipeline reads it, and what happens when it doesn't match.
Every column named below is enforced in code — see `src/sami/schema.py`
(`RESPONSES_REQUIRED`, `RESPONSES_OPTIONAL`, `MEAL_REQUIRED`,
`RESPONSES_COLUMN_MAP`, `MEAL_COLUMN_MAP`, `MEAL_QUESTION_MARKERS`).

## The two sources

**Responses** — one row per chatbot user record (a user who has multiple
conversations produces multiple rows). It carries the user's identifier,
registration/profile fields, and the full conversation transcript in the
`QA Messages` column, which the pipeline splits into one row per message for
text analysis.

**MEAL** — one row per survey respondent, from a short post-conversation
survey (usefulness rating, recommendation, discovery channel, free-text
feedback). It is a separate download from a separate form; a MEAL row and a
responses row are joined only through the shared user identifier.

## Locating the files

The pipeline reads whichever files are placed in `datasets/responses/` and
`datasets/meal/` — role is declared by the folder, not the filename, and the
newest `.xlsx` in each folder wins. An explicit `--responses PATH` /
`--meal PATH` overrides the folder contents. See
[`datasets/README.md`](../datasets/README.md) for the full mechanism.

## The header row

Both exports carry banner rows above the real column header. Rather than
assume a fixed row number, the pipeline detects the header by scanning the
first `HEADER_SCAN_ROWS` (8) rows for the first one that contains every marker
of an accepted marker set:

| Source | Accepted marker sets (`HEADER_MARKERS`) |
|---|---|
| responses | `address` + `created at`, **or** `name` + `timestamp` |
| meal | `respondent` + `recorded at`, **or** `name` + `timestamp` |

Matching is case/accent-insensitive (`sami.canon.fold`). Because the header is
detected rather than assumed, a re-export with a different number of banner
rows above the header loads unchanged — the pipeline finds the header row
wherever it lands, up to row 8.

## Column names are mapped

The platform's export column names are renamed to the names the rest of the
pipeline uses (`schema.normalize_columns`). A column not listed below passes
through untouched, under its original name.

**Responses (`RESPONSES_COLUMN_MAP`):**

| Export column | Pipeline column |
|---|---|
| `Address` | `Name` |
| `Created At` | `Timestamp` |
| `QA Messages` | `Messages` |
| `QA Summary` | `Chat_summary` |
| `consent` | `Consent` |
| `nationality` | `Nationality` |
| `nationality (raw)` | `Nationality_other` |
| `city` | `City` |
| `time_in_city` | `City_duration` |
| `gender` | `Gender` |
| `age` | `Age` |
| `children` | `Minors` |
| `destination` | `Destination` |
| `Survey Sent` | `Survey sent` |

**MEAL (`MEAL_COLUMN_MAP`):**

| Export column | Pipeline column |
|---|---|
| `Respondent` | `Name` |
| `Recorded At` | `Timestamp` |

A rename is skipped if it would collide with a column that already exists
under the target name, so a hybrid export (old and new names both present)
never produces a duplicate column.

## Required columns

Missing any of these stops the run. Names below are the pipeline (post-map)
names.

**Responses (`RESPONSES_REQUIRED`):**

| Column | Feeds |
|---|---|
| `Name` | Pseudonymized into `user_id` (salted hash); the file's identifier. |
| `Timestamp` | Parsed into `ts`, the record's clock reading. Every time-indexed figure, including the session-time KPI, is derived from it. |
| `City` | Cleaned and canonicalized into `city_canon` / `department` for the location breakdowns and dashboard map. |
| `Age` | Parsed into `age_num`; records with `age_num` under 18 are flagged `age_flag = "unreliable_sub18"`. |
| `Messages` | Split into the message-level spine (one row per message) that all text analysis runs on. |
| `Chat_summary` | Mapped to `dominant_category` through the topic taxonomy. |

**MEAL (`MEAL_REQUIRED`, identical to `BASE_REQUIRED`):**

| Column | Feeds |
|---|---|
| `Name` | Pseudonymized into `user_id`; joins MEAL rows to the responses data. |
| `Timestamp` | Parsed into `ts`; used to keep only the most recent survey response per user. |

A missing required column raises `SchemaError` naming the file, the missing
column(s), and every column the file does have — see the example at the end
of this document.

## Optional columns

Present in the current export and used when available (`RESPONSES_OPTIONAL`).
Absence degrades a figure; it never stops the run.

| Column | Adds |
|---|---|
| `Nationality`, `Nationality_other` | Cleaned into `nationality_clean` / `nationality_canon`. |
| `City_other` | Combined with `City` to recover free-text "other city" answers into `city_clean`. |
| `City_duration` | Canonicalized into `city_duration_canon` / `city_duration_order`. |
| `Gender`, `Gender_other` | Cleaned into `gender_clean`. |
| `Minors` | Carried into `dim_user` as `minors`. |
| `Away_duration` | Canonicalized into `away_duration_canon` / `away_duration_order`. |
| `Destination_Country` | Carried into `dim_user` as `destination_country`. |
| `Age Ranges` | Carried into the message spine and into `dim_user` as `age_range`. |
| `Questions per user` | Parsed into `n_questions`, the repeat-asker metric. |
| `Language` | Carried into `dim_user` as `language`; feeds the per-cohort language breakdown. |
| `Registration Status` | Carried into `dim_user` as `registration_status`; feeds the per-cohort registration funnel. |
| `Registration Started` | Counted as the registration funnel's per-cohort denominator. |
| `Registration Completed` | Accepted by the schema; not currently read into a derived figure. |
| `Attempts` | Carried into `dim_user` as `attempts`. |
| `Is Returning User` | Carried into `dim_user` as `is_returning`. |
| `Safety Alert` | Carried into `dim_user` as `safety_alert`. |
| `Escalation Status` | Carried into `dim_user` as `escalation_status`. |
| `Migrated From v1` | Present marks the record as carried over from the prior platform; feeds `instrument_version` (see below). |
| `Survey Completed` | Accepted by the schema; not currently read into a derived figure. |
| `Last Message At` | Parsed by `load.last_message_ts`; differenced against `Timestamp` into `session_minutes`, the session-time KPI. Only its ISO-8601 UTC values are used — other formats parse to null and that record is simply excluded from the KPI. |

## The MEAL question columns

The five MEAL survey questions are matched by their question text, not by
position (`MEAL_QUESTION_MARKERS`). Each canonical field is bound to the
export column whose (fold-normalized) text contains its marker fragment:

| Canonical field | Matched by (fold-normalized fragment) |
|---|---|
| `usefulness_rating` | "que tan util" |
| `would_recommend` | "recomendarias este servicio" |
| `recommendation_text` | "alguna recomendacion para mejorar" |
| `discovery_channel` | "como conociste" |
| `no_usefulness_reason` | "por que la informacion entregada no fue util" |

(A sixth field, `discovery_other`, is the free-text follow-up captured when a
respondent picks "other" for `discovery_channel`; it is matched the same way
but is not itself a survey question.)

When a marker matches more than one column — the export carries both an
empty legacy copy of a question and the live one — the column that actually
carries data is chosen; ties break on the last (newest) match. When a
question has been reworded past recognition, no column matches it: the field
is left absent from `fact_meal` and the loader emits a warning naming the
canonical field it could not find and the fragment it searched for. There is
no positional fallback.

## New columns

A responses column not in `RESPONSES_REQUIRED`, `RESPONSES_OPTIONAL`, or the
schema's list of known-but-unused columns triggers a warning naming it
(`report_unknown_columns`). This is informational only and never fails the
run — a refreshed export gaining a new field is normal. The MEAL loader has
no equivalent check; an unrecognized MEAL column is simply left unmapped and
ignored.

## When something is wrong

A source that does not match this contract raises `schema.SchemaError`. Every
`SchemaError` states the problem, the file, and the fix. Example, produced by
taking the `users_v2` fixture, removing its `Age` column, and loading the
result through `load.load_responses`:

```
responses export is missing required column(s): Age
  file: <path to the export>
  fix:  This export has: Name, Subitems, Timestamp, Messages, Language, Consent, Nationality, City, City_duration, Gender, Minors, Destination, Chat_summary, Escalation Status, Safety Alert, Registration Status, Nationality_other, Registration Started, Registration Completed, Attempts, Drop-off Question, Last Message At, Is Returning User, City_other, Gender_other, Away_duration, Destination_Country, Age Ranges, Questions per user, Migrated From v1, City Location, Destination_other, Prev_country_other, Re-engagement Sent At, Survey Completed, Survey sent, origin_country, transit
        If the platform renamed a field, map it back to the expected name, or update RESPONSES_REQUIRED / MEAL_REQUIRED in src/sami/schema.py.
```

The same shape covers a missing file (names the folder to save into and the
`--responses` / `--meal` override) and a header the detector cannot find
(lists the rows it actually saw in the first 8 rows).

## Instrument version

`dim_user` carries an `instrument_version` column (`v1` or `v2`). Fields that
differ between the two questionnaire versions are reported per cohort — that
is, split by `instrument_version` rather than combined into one total.
