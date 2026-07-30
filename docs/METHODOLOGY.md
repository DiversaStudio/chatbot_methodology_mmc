# Methodology

This document traces every number in `exports/` back to the code that
produces it, so a figure in the Power BI report or in one of the CSVs can be
defended or reproduced. It assumes the input contract in
[`DATA_SOURCES.md`](DATA_SOURCES.md) and the run mechanics in
[`OPERATIONS.md`](OPERATIONS.md) — both are linked from here rather than
repeated. The table-by-table column reference lives in
[`exports/_schema.md`](../exports/_schema.md).

All figures below are read out of the tables in `exports/` as committed on
this branch, from `Users_Group_Title_2807.xlsx` (1,460 rows) and
`Survey_Responses_Group_Title_2807.xlsx` (142 rows). The exact run this
document describes is recorded in `exports/meta_run.csv`'s `generated_at`
value — that field is a timestamp written fresh on every run, so it changes
whenever the exports are regenerated; read it from the committed file rather
than from this document, which would go stale the moment it quoted a
specific value.

## 1. Pseudonymization

`src/sami/load.py` turns the identifying column (`Name`) into `user_id`
before anything else touches the data:

```text
user_id = sha256(salt + digits(name))[:12]
```

`digits()` (in `load.py`) strips a trailing float tail (`.0`) before pulling
out the numeric characters, so an id stored as text in one export
(`"whatsapp:+573154047912"`) and as a number in another (`573154047912.0`)
hash to the same `user_id`. The hash is salted with `SAMI_SALT`, resolved by
`config.get_salt()` and never committed to the repository (see `SAMI_SALT` in
`OPERATIONS.md`); it is deterministic for a given salt and input, and
non-reversible — there is no function that recovers a name from a `user_id`.
`exports/dim_user.csv` carries 1,392 pseudonymised users (`exports/_manifest.csv`).

Every table written to `exports/` is scanned for raw phone numbers and
`whatsapp:`-prefixed identifiers before it is written. `export.write_all`
calls `qa.pii_scan` on each table first; if any table has a hit, `write_all`
raises and nothing is written — a failed scan leaves the previous `exports/`
directory untouched rather than producing a partially-clean refresh. The scan
(`qa.pii_scan`) checks every string/object column except `user_id` and
`message_id` (both are hashes this pipeline computes, not source text) for
the literal `whatsapp:` or a match of the pattern `\b\d{7,}\b` — a run of 7
or more digits set off by a word boundary on each side, so it catches a
phone number written with no separators but not, say, a digit run fused to
surrounding letters or underscores in a filename-like token. `load.py` also
runs a best-effort redaction pass (`_redact_pii_runs`) on the responses and
MEAL frames as they are loaded, replacing any 7+-digit run in an open-text
column (e.g. a pasted phone number or cédula) with the literal token
`[redacted]`; the authoritative gate is the scan at write time, not this
earlier pass.

## 2. The message spine

A response record carries one `Messages` field — a text blob holding an
entire conversation. `load.load_messages` (`src/sami/load.py`) turns each
record into one row per message:

1. `split_messages` splits the blob on newlines and strips whitespace from
   each line.
2. Noise lines are dropped (`_is_noise`): a line under 3 characters, a line
   that is purely digits, or a line that folds to `undefined` or `?` (or is
   empty).
3. Before a line reaches the noise check, any run of 7+ digits has already
   been replaced by `[redacted]` (the same redaction described in §1);
   `_is_noise` strips that token back out before measuring length, so a
   redacted phone number does not accidentally read as a short, content-free
   line.

Because some users have more than one response record (a returning user
produces 2-3 records), `seq` (the message's position in that user's
timeline) and `n_msgs_user` (that user's total message count) are computed
per **user**, across all of that user's records combined, not per record.
The spine is sorted by `(user_id, ts)` before these are assigned. `fact_message`
carries `4663` rows (`exports/_manifest.csv`), one per surviving message.

Each message's id (`fact_message.message_id`) is
`sha1(user_id \x00 seq \x00 message_text)[:16]` (`export.message_key`) — a
content-and-position key, not a row number, so it survives the corpus
growing as long as no earlier message is ever backfilled into an existing
user's timeline (which would renumber that user's `seq` and change their
message ids).

## 3. The category taxonomy

`src/sami/taxonomy.py` defines the seven official MMC categories:

- `legal_documentation`
- `humanitarian_assistance`
- `protection`
- `employment`
- `organization_search`
- `journey_information`
- `services`

Every response record's `Chat_summary` value is passed through
`taxonomy.normalize_category`, which folds accents/case, strips a leading
`#`, drops space/underscore separators, and looks the result up against the
seven categories' aliases. The result becomes `dominant_category` for that
record (`load.load_responses`) and is carried onto every message split from
it (`load.load_messages`).

A `Chat_summary` value maps to `unclassified` when it is null, blank,
contains a comma (a multi-label value), is longer than 60 characters (a
leftover prompt-instruction row), or simply does not match any of the seven
aliases — which is also what happens to the free-prose conversation
summaries the platform started emitting from July 2026 onward, since
`normalize_category` is an exact-match lookup and prose is not a label.
`unclassified` is displayed in the exported tables as `Suggestion`
(`export.CAT_EN`): this bucket holds every record whose topic the taxonomy
could not place, whatever the reason, and it is presented as a suggestion
for a future category rather than as ground truth.

## 4. Archetypes

Archetypes are built from one document per user (their concatenated
messages), embedded with the sentence-embedding model named in
`meta_run.csv` (`embed_model`: `intfloat/multilingual-e5-large`).

`k` (the number of clusters) is chosen by `clusters.choose_k`, which scans a
range of candidate `k` and does not fix `k` by hand. On this corpus the
silhouette score cannot discriminate between candidate `k` values
(`clusters.silhouette_is_flat`), so `choose_k` falls back to a stability
criterion: `clusters.stability_curve` bootstrap-resamples the users (80% of
rows, without replacement, 30-50 resamples per `k`) and refits KMeans on
each resample; `clusters.stability_ari` computes the mean pairwise Adjusted
Rand Index between resamples' cluster assignments, restricted to the users
two resamples share. `choose_k` selects the **largest** `k` whose stability
score clears `STABILITY_BAR` (0.6) by at least one standard deviation —
maximal resolution subject to a robust bar, not the `k` with the single
highest score. Every fit uses `random_state=0`.

For the committed exports, `chosen_k = 6` and `stability_ari = 0.836`
(`exports/meta_run.csv`). `nlp_umap.csv` carries `1198` user rows — the
number of users with enough message text to embed and cluster.

KMeans at the chosen `k` (`random_state=0`) assigns each of those users to
one archetype (`cluster_id`). Per-cluster vocabulary is computed with
class-based TF-IDF (`clusters.ctfidf_terms`, exported as
`nlp_cluster_terms.csv`): each cluster's messages are pooled into one
document per cluster, and a term's score is weighted down the more clusters
it appears in, so a word common to every cluster scores near zero however
often it occurs. A term must appear in at least `min_user_df` (5) distinct
users' documents before it can be reported — this both drops vocabulary too
rare to represent a real theme and keeps a name reaching only one or two
users from surfacing in a rendered term list. `dim_cluster.csv` carries each
cluster's size, message count, top categories and median age (excluding
records flagged `unreliable_sub18`, see §1 of `DATA_SOURCES.md` on the `Age`
column); `nlp_voices.csv` carries one example message per cluster, matched
against that cluster's marker term.

## 5. Cohorts

`dim_user` carries an `instrument_version` column (`v1` or `v2`) because the
registration survey the chatbot presents to a new user was rewritten in July
2026. `cohort.instrument_version` (`src/sami/cohort.py`) reads the
`Migrated From v1` marker column: a record carrying that marker is `v1`;
everything else — including every record in an export where the marker
column is entirely absent — is `v2`. A user's `instrument_version` in
`dim_user` is taken from their earliest response record
(`export.build_dim_user`).

Every field that reaches `dim_user` or `fact_meal` is classified in a fixed
policy table, `cohort.POLICY`, as one of four kinds
(`cohort.Policy`):

- `POOLABLE` — reported as a single combined total across both versions.
- `SPLIT` — reported separately per `instrument_version`, never combined.
- `V1_ONLY` — the underlying question was retired in v2; the series is
  frozen at whatever v1 respondents produced.
- `V2_ONLY` — the underlying question was added in v2; there is no v1
  history for it.

`cohort.policy_for(column)` looks a column up in this table and raises
`CohortError` — naming the column and the fix (classify it in
`cohort.POLICY`) — if the column has no entry. This classification is
enforced by the test suite: `tests/test_export.py` calls `cohort.policy_for`
for every column of `dim_user` and every column of `fact_meal`, so a field
reaching either table without a policy entry fails the tests rather than
shipping unclassified. Aggregate builders elsewhere in `export.py` that are
not routed through `dim_user`/`fact_meal` (for example
`build_agg_registration_funnel` and `build_agg_language`) implement their
own per-cohort split directly.

## 6. Sentiment

A full run (not `--skip-nlp`) computes a per-message sentiment signal using
the model named in `meta_run.csv`'s `sentiment_model` field:
`cardiffnlp/twitter-xlm-roberta-base-sentiment`. The output lands in
`fact_message.sentiment_label`, one value per message row. A run started
with `--skip-nlp` leaves this column null for every row.

A full run also writes `nlp_tone_confusion.csv`, produced by
`src/sami/validation.py` from the model's own labels compared against
`validation/tone_labels_analyst.csv`, the committed comparison set described
in [`DATA_SOURCES.md`](DATA_SOURCES.md). Its columns are documented in
[`exports/_schema.md`](../exports/_schema.md).

## 7. Quality checks

`qa.run_checks` (`src/sami/qa.py`) runs a fixed set of checks after loading
and before export, each returning a name, a pass/fail boolean, and a detail
message:

| Check | What it verifies |
| --- | --- |
| `P1_pii_responses` | The loaded responses frame has no PII hit (`qa.pii_scan`). |
| `P1_pii_messages` | The message spine has no PII hit. |
| `P6_spine_invariant` | The sum of each user's message count equals the total row count of the message spine — the spine was built correctly. |
| `P8_meal_unique` | `fact_meal` has exactly one row per user. |
| `P7_unclassified_share` | Of the response records that carry a `Chat_summary` at all, fewer than 10% are `unclassified`. |
| `P9_summary_format` | Of the `Chat_summary` values that are label-shaped (not the v2 timestamped-prose format), no more than 5% (`validation.SUMMARY_PROSE_THRESHOLD`) fail to map to a category. |

The `P1_`, `P6_`, and `P9_` families are critical: `facade.load_sami` raises
`RuntimeError` the moment any check whose name starts with one of those
prefixes fails, before any table is built or written. `export.write_all`
additionally scans every table
immediately before writing it (§1) and raises, refusing to write any file,
if that scan finds a hit — this is independent of, and runs later than, the
`P1_` checks in `qa.run_checks`.

`export.build_parity_check` (written as `parity_check.csv`) is a further,
independent cross-check: it recomputes user count, message count,
users-with-text count, MEAL response count, and the repeat-asker share
directly from the exported tables and compares each against
`qa.reconciliation_table`'s independently computed value. `run_pipeline.py`
prints this table and exits non-zero if any row's `match` column is
`False` — see [the parity gate in `OPERATIONS.md`](OPERATIONS.md#the-parity-gate).

## 8. Reproducibility

Every stochastic step in the pipeline — KMeans clustering, the bootstrap
resampling used for stability, and the 2D UMAP/PCA projection used for
`nlp_umap.csv` — is seeded with `random_state=0`. Given the same input files
and the same `SAMI_SALT`, a run reproduces the same tables. The two
device-dependent exceptions (a timestamp column, and the 2D projection
coordinates) are documented in
[the CPU and GPU section of `OPERATIONS.md`](OPERATIONS.md#cpu-and-gpu).
