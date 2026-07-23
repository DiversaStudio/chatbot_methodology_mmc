# SAMI NB3 — What the text says (Act 3 semantic) — Design

Sub-project 4 of the SAMI pipeline rework (foundation `e8d4fab`; NB1 `deb0e2b`; NB2 on
`feature/sami-nb2`). Reads with `requirements/01_storytelling_and_analysis_scope.md` §Act3
and `requirements/02_notebook_requirements.md` §6. Branch: `feature/sami-nb3`.

**Mandate:** NLP exists to find what the taxonomy misses — not to demonstrate NLP. NB3
produces exactly three named things: **archetypes**, **candidate missing intents**, and a
**validated tone signal**. Hard cap **8 figures** (annex sits outside the cap).

New notebook file `notebooks/03_text_insights_nlp.ipynb`. Render engine **matplotlib**
(`theme.py` template), following NB1/NB2.

---

## 0. Decisions locked (user, 2026-07-23)

1. **No LLM per-message intent classification.** Doc 02 §6.3 as written — a frontier or
   local LLM labelling all 2,993 messages into an extended taxonomy, with a κ-gated
   coverage-gap percentage — is **dropped from scope**. No API key dependency enters the
   pipeline.
2. **Missing intents are derived from clustering, directional only.** Clusters that do not
   map cleanly onto the 7 official categories become *named candidate intents*, evidenced
   by c-TF-IDF distinctive terms plus verbatim Spanish quotes. **No percentage is ever
   quoted for an emergent intent** — there is no validated classifier behind it. Every such
   finding carries an explicit `directional only` tag.
3. **Tone is validated this pass.** A stratified 200-message sample is hand-labelled by
   Claude as the *analyst* pass; the user is the *reviewer*. Cohen's κ is computed against
   the pinned sentiment model. The notebook prints a standing disclosure that the analyst
   pass was model-generated, so this is **weaker than the independent human validation doc
   02 §6.4 intends**.
4. **NB2's priority matrix is wired in as the final task of this plan**, replacing the
   deferred placeholder cell shipped in NB2 §6.
5. **No disk cache** — deliberate departure from doc 02 Rule 2; see §4.
6. Gold exports remain **deferred** to the later `run_pipeline` + `src/sami/exports.py`
   sub-project. NB3 is purely analytical. No notebook `to_csv` except the validation
   artifacts in §5, which are inputs to the analysis, not gold-layer outputs.

---

## 1. Module changes (Rule 3 — notebooks consume, modules compute)

### New `src/sami/nlp.py`
Model loading and inference. Every model id and revision pinned as a module constant so
the notebook never names a model inline.

- `EMBED_MODEL = "intfloat/multilingual-e5-large"` + `EMBED_REVISION` (pinned commit sha).
- `SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"` + `SENTIMENT_REVISION`.
- `user_documents(messages) -> pd.DataFrame` — concatenate all messages per user into one
  document (`user_id`, `doc`, `n_msgs`). Expected ≈800 docs (users with ≥1 parsed message).
  Whitespace-normalized; empty docs dropped and counted.
- `embed_documents(docs, batch_size=32) -> np.ndarray` — e5-large, **`"query: "` prefix per
  the model card**, L2-normalized, `device="cuda"` when available else CPU. Deterministic
  (no dropout at inference; fixed batch order).
- `sentiment_messages(messages) -> pd.DataFrame` — per-message `label`
  (`negative`/`neutral`/`positive`) + `score`, batched. Returns one row per input message,
  index-aligned to the message spine.
- `device_report() -> dict` — device, torch version, CUDA availability, model ids +
  revisions. Rendered as part of the notebook's identity card (reproducibility evidence).

### New `src/sami/clusters.py`
Clustering, stability and interpretation. No sklearn call lives in the notebook.

- `k_scan(X, k_range=range(4, 13), random_state=0) -> pd.DataFrame` — KMeans per k with
  `silhouette` and `davies_bouldin` columns. Annex figure source.
- `choose_k(scan) -> int` — best silhouette, ties broken by lower Davies-Bouldin. The
  chosen k is **data-driven, never 7 by fiat** (doc 01 §6).
- `stability_ari(X, k, n_boot=50, frac=0.8, random_state=0) -> dict` — 50 bootstrap
  resamples at 80% of users; refit KMeans; mean pairwise Adjusted Rand Index computed on
  the intersection of each resample pair. Returns `{mean_ari, std_ari, n_pairs, stable}`
  where `stable = mean_ari >= 0.6`.
- `ctfidf_terms(docs, labels, top_n=10) -> dict[int, pd.Series]` — class-based TF-IDF
  (cluster centroid TF-IDF, **not raw frequency**), Spanish stopwords + SAMI-specific
  stopwords (greetings, bot boilerplate). Spanish lemmatization via the already-declared
  `es_core_news_sm`.
- `archetype_profiles(labels, responses, messages) -> pd.DataFrame` — per cluster: `n_users`,
  `n_messages`, dominant categories (top 2 + share), demographic skew (gender, median age
  excluding `unreliable_sub18`, top city, top nationality), `pct_negative`.
- `project_2d(X, method="umap", random_state=0) -> np.ndarray` — **one** 2D view. UMAP with
  fixed seed; PCA fallback if UMAP is unstable across runs. No 3D, ever (doc 01 §6).

### New `src/sami/validation.py`
The tone validation protocol, so κ machinery is reusable and unit-tested.

- `stratified_sample(messages, sentiment, n=200, random_state=0) -> pd.DataFrame` — stratified
  by `dominant_category` × predicted sentiment label, proportional allocation with a floor of
  1 per non-empty stratum. Emits `message_id`, `user_id`, `message` **and nothing else** —
  the model prediction is deliberately withheld so labelling is blind (§5).
- `cohens_kappa(a, b) -> float` — Cohen's κ, no sklearn dependency in the signature.
- `validation_report(human, model) -> dict` — `{kappa, accuracy, confusion, n, gate_passed}`
  with `gate_passed = kappa >= 0.7`, on the binary **negative / not-negative** collapse doc
  02 §6.4 specifies.

### `taxonomy.py` extension
- `CANDIDATE_INTENTS: dict[str, str]` — the versioned cluster→candidate-intent naming map
  (e.g. `transport_logistics`, `human_handoff`, `connectivity`, `out_of_scope`,
  `other_emergent`). This is an **analyst judgement recorded in code**, not a classifier;
  its docstring says so explicitly.

### `metrics.py` extension
- `negative_by_category(messages, sentiment) -> pd.Series` — % negative per official
  category. This is the series NB2's `priority_matrix_frame(neg_by_category=...)` has been
  waiting on.

### `theme.py`
Unchanged unless an archetype color cycle is needed; if so, add a stable archetype→color map
so cluster colors match across figures 1, 2 and 3.

### Tests
- `tests/test_nlp.py` — `user_documents` grain (one row per user, message counts sum to the
  spine total); embedding shape + L2 norm ≈ 1; sentiment output index-aligned and label set
  closed. Model calls exercised on a tiny fixture, marked slow where needed.
- `tests/test_clusters.py` — `k_scan` returns one row per k with finite metrics; `choose_k`
  tie-breaking; `stability_ari` determinism under fixed seed and a **known-stable synthetic
  blob scoring ARI ≈ 1.0** plus a known-unstable uniform cloud scoring low; `ctfidf_terms`
  returns cluster-distinctive (not globally frequent) terms on a crafted fixture.
- `tests/test_validation.py` — `stratified_sample` size, stratum coverage, determinism, and
  **that it never leaks the model prediction column**; `cohens_kappa` against hand-computed
  values including the perfect-agreement and chance-agreement edge cases.
- Extend `tests/test_taxonomy.py` — every `CANDIDATE_INTENTS` value is a known intent slug.
- Extend `tests/test_metrics.py` — `negative_by_category` bounded [0,1], index ⊆ official
  categories.
- Full suite stays green.

---

## 2. Notebook structure (8-figure hard cap; 7 built, one slot spare)

| # | Section | Figure | Source |
|---|---|---|---|
| — | top | Reconciliation table (P10) + identity card + `device_report()` | facade / `nlp` |
| — | §1 Representation | method card, **no figure** | `user_documents` |
| 1 | §2 Archetypes | 2D map tinted by archetype (one view only) | `project_2d` |
| 2 | §2 Archetypes | distinctive terms per archetype (c-TF-IDF small-multiple) | `ctfidf_terms` |
| — | §2 Archetypes | summary **table**: size, demo skew, dominant categories, quote | `archetype_profiles` |
| 3 | §3 Coverage gaps | candidate emergent intents — cluster mass with no official slot (**directional**) | `CANDIDATE_INTENTS` |
| 4 | §4 Tone | validation panel: confusion matrix + κ + disclosure | `validation_report` |
| 5 | §4 Tone | negative share by category | `negative_by_category` |
| 6 | §4 Tone | negative share by city (single synthesis version) | `sentiment` × `city_canon` |
| 7 | §5 Voices | 6–10 curated verbatim quotes, Spanish + caption translation | meal + messages |
| — | close | 5-bullet "what we now know" + reconciliation (must match top) | facade |
| — | **Annex** | A1 k-scan + stability ARI; A2 repeat-asker vocabulary | `k_scan`, `stability_ari` |

Every figure: assertion-evidence title; subtitle with metric + n + window; `theme.py`
palette (archetype colors stable across figures 1–3); source note.

**Explicitly cut** (doc 01 §6): 3D PCA scatter; wordcloud grids; TF-IDF vs embeddings
comparison; cluster-purity charts; per-city/month wordclouds.

---

## 3. Honesty gates

These are the spec's core. Each is a normal, reportable result — not a failure mode.

- **Clustering stability.** If `stability_ari()["mean_ari"] < 0.6`, archetypes are reported
  as **"soft structure"**: named cautiously, sized, profiled, but never presented as hard
  segments, and the notebook says the structure is indicative. Given the prior run's weak
  agreement this is the *likely* outcome; the spec treats it as expected, and NB3 still
  ships all seven figures either way. The scan and the ARI are printed regardless.
- **Tone validation.** If `kappa < 0.7`, **all negative-share percentages are suppressed**
  (figures 5 and 6 render as rank order without percentage labels) and findings are
  directional only. κ is printed regardless, prominently.
- **Emergent intents.** Never quoted as a percentage under any κ outcome — the gate is
  structural, not conditional. Sizes are given as cluster user counts with a directional tag.
- **Small-n.** Any archetype or per-city cell with n<20 carries a visible subtitle warning,
  consistent with NB2.
- **No causal language.** "is associated with", never "drives".

---

## 4. Caching — deliberate departure from doc 02 Rule 2

Doc 02 Rule 2 mandates caching heavy artifacts to parquet keyed by export hash + model name.
**NB3 computes inline on GPU with no disk cache.** Rationale, stated in-notebook:

- The heavy step left scope with decision §0.1. What remains is e5-large over ~800 user
  documents and a small XLM-R sentiment model over 2,993 short messages — a few minutes on
  the local RTX 3050 Ti, well inside the 15-minute `Run All` gate.
- A cache keyed by export hash adds an invalidation surface and a stale-results failure mode
  that buys nothing at this runtime, and it conflicts with the standing project preference
  for inline GPU compute in the analysis notebooks.
- Reproducibility is preserved by the mechanism that actually matters: **pinned model
  revisions + fixed seeds + `device_report()` rendered in the notebook**. Rule 4 (headless
  pipeline) is unaffected because all inference lives in `src/sami/nlp.py`, which
  `run_pipeline` will call directly.

If a future export materially grows the corpus, revisit — the cache decision is a runtime
judgement, not a principle.

---

## 5. Tone validation protocol (§0.3 in detail)

The protocol must survive a reviewer asking "who labelled this, and did they peek?"

1. `stratified_sample(n=200, random_state=0)` draws the sample stratified by category ×
   predicted sentiment. **The model prediction column is withheld from the emitted file.**
2. The sample is written to `validation/tone_sample_200.csv` (`message_id`, `user_id`,
   `message`) and committed — the sample is a fixed, auditable artifact.
3. Claude labels each message **blind**, as `negative` / `not_negative`, into
   `validation/tone_labels_analyst.csv`. Blind labelling is what makes κ meaningful; if the
   labeller sees model output, κ measures anchoring rather than agreement.
4. The user reviews and may overwrite any label, producing
   `validation/tone_labels_reviewer.csv`. If the reviewer file is absent, the analyst labels
   stand and the notebook says so.
5. `validation_report()` computes κ, accuracy and the confusion matrix on the binary
   negative / not-negative collapse; figure 4 renders it.
6. **Standing disclosure**, rendered in the notebook next to figure 4 and repeated in the
   close: *the analyst pass was model-generated, so this is inter-model agreement partially
   supervised by a human reviewer — not the independent two-human validation doc 02 §6.4
   specifies. Treat κ as an upper bound on true agreement.*

PII: the sample file and every rendered quote pass `qa.pii_scan` before being written or
displayed. Verbatim quotes are the one place a raw phone number can still leak.

---

## 6. NB2 priority matrix wiring (final task)

Once tone is validated, replace NB2 §6's deferred placeholder with the real figure:
per category — x = message volume, y = unmet-need score (z-scored blend of % repeat-askers,
% negative sentiment, inverted mean MEAL rating), bubble = users, plain-language quadrant
labels ("big and badly served").

- Calls the already-shipped `metrics.priority_matrix_frame(neg_by_category=...)`.
- **Inherits NB3's validation caveat**: if κ < 0.7, the unmet-need axis is directional and
  the figure must say so in its subtitle; axis tick labels drop numeric sentiment values.
- NB2's figure count goes from 9–11 to 10–12, still within its 12 cap.
- Both notebooks re-run clean; both reconciliation tables re-checked.

---

## 7. QA gates & acceptance

- `Run All` clean kernel succeeds, < 15 min; reconciliation printed top and bottom, identical.
- Rendered main-line figure count ≤ 8 (7 expected); annex clearly separated and labelled.
- Every figure's n traces to P10; every archetype has n, profile and a quote.
- Model ids **and revisions** pinned and printed; seeds fixed; `device_report()` rendered.
- Clustering stability (`mean_ari`) reported whatever its value; k chosen from the scan.
- κ reported before any sentiment percentage is quoted; suppression enforced when κ < 0.7.
- Emergent-intent findings carry a `directional only` tag and no percentages.
- Zero PII: `qa.pii_scan` over notebook data, the validation sample, and every quote; grep
  rendered outputs for `whatsapp:` / 7+-digit runs → 0.
- No inlined loaders/logic: notebook imports `from sami import load_sami` plus
  `sami.nlp` / `sami.clusters` / `sami.validation` / `sami.metrics` / `sami.taxonomy` /
  `sami.theme` only; any logic >15 lines lives in a module.
- All new module code covered by pytest; full suite green.
- Whole-branch Opus review before merge (as foundation + NB1 + NB2).
