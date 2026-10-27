# Message classifier

How the pipeline assigns each chatbot message to one of MMC's 10 categories (or *Ninguna*).
Code: `src/sami/categorize.py` (model, split, scoring), `src/sami/llm_labels.py` (label and synthetic data),
`run_pipeline.py::_category_tables` (export). Evidence: notebooks 04, 05, 06.

## What it does

- **Classes:** the client's 10 categories + *Ninguna* (messages with no need of their own: greetings, thanks, "si", a bare place).
  Classes stay in Spanish inside the model; the export uses English display names (`categorize.DISPLAY_EN`).
- **Input:** the pipeline's own `multilingual-e5-large` embedding of the message (pinned revision `3d7cfbdacd47`), no extra features.
- **Model:** RBF SVM, `C=10`, `class_weight="balanced"`, scikit-learn `SVC`.
- **Output:** one class per message, and per user the topic they wrote about most.

## Data

| Source | Rows | Role |
|---|---|---|
| Client labels (`messages_category_original.xlsx`) | 2,932 labelled of 6,263 | Starting point and test truth |
| Final labels (`messages_category_haiku_final.xlsx`) | 6,040 | Training labels (below) |
| Synthetic messages (`messages_category_synthetic_haiku.xlsx`) | 26,057 | Extra training data |

Training set: 4,191 corrected + 26,057 synthetic = **30,248 rows**. All three files are client data, gitignored, in `datasets/labels/`.

**Client labels.** Single label (`Category 1`; `Category 2` is ignored). *Ninguna* is the `Mensajes_NA` sheet, one row per distinct text (433 of 1,316 rows), so a repeated "si" cannot dominate a split.

**Final labels.** Claude Haiku 5.5 (via `claude -p`) labelled every scrubbed message with a closed category list, nine disambiguation rules and 8 development examples per class, plus the 3 previous messages for context. The frozen test set was labelled blind; Haiku agrees with the client on about 81% of it (kappa 0.75-0.77). A reviewer then checked the client-vs-Haiku disagreements (capped per class): 328 corrections, 93% in Haiku's favour. Resulting sources of the final label:

| `Final source` | Rows |
|---|---|
| LLM, agrees with client | 3,148 |
| LLM, client never labelled | 2,355 |
| Human correction | 328 |
| LLM, disagrees with client, unreviewed | 209 (excluded from training) |

**Synthetic messages.** Haiku wrote them from real non-test examples: 3x the real count for the three biggest classes (Documentos, Ninguna, Asistencia Humanitaria), 10x for the rest. Near-duplicates (e5 cosine >= 0.97 within a class) and exact copies of real text were dropped. Result: 26,057 of a 27,055 target; the main shortfall is *Ninguna* (3,731 of 4,713) because short messages repeat. Each message carries the class it was written for. Haiku re-labelled them as a check: 1,258 (4.8%) disagreed; they are kept, and notebook 6 showed dropping them changes nothing.

**Privacy.** Only text scrubbed by `redact.scrub` is sent to Haiku; messages the scrubber drops are never sent. Test texts never reach a prompt (`assert_no_test_text`). Notebooks print counts and scores only.

## Training and evaluation

- **Frozen test set:** 588 messages (566 with a final label). Topic rows are one fold of a 5-fold `StratifiedGroupKFold` (seed 42) grouped by normalised text; *Ninguna* is 20% of distinct texts. No test text may appear in training (asserted).
- **Metric:** macro-F1, with accuracy beside it. Classes range from 877 messages (Documentos) to 58 (Emprendimiento).
- **Synthetic weight:** 0.5 (`sample_weight`), real corrected messages at 1.0.
- **Choices made in the notebooks:**
  - NB4: linear and RBF SVMs lead on frozen embeddings; TF-IDF n-grams add nothing.
  - NB5: Corrected labels beat the client's raw labels as training data, and synthetic data helps the RBF SVM slightly. Synthetic-only transfers poorly (0.58-0.60 macro-F1).
  - NB6: no C/gamma or weighting variant beat the baseline; the best region is flat.

**Score of the saved model** (frozen test, final labels, n=566): **accuracy 83.7%, macro-F1 0.772.** It is stored with the model and written to `meta_run` (`classifier_test_accuracy`, `classifier_test_macro_f1`).

## In the pipeline

`run_pipeline.py` loads `models/category_classifier.joblib`, embeds the run's messages (cached in `outputs/cache`), classifies them, and builds the category tables next to the existing k-means ones (schema v23):

- `dim_category`, `nlp_category_terms`, `nlp_category_voices`, `agg_weekly_category`, `agg_priority_matrix_category`.
- New columns: `dim_user[category_id, n_categories, category_tied]`, `fact_message[message_category, message_category_id, category_id]`.
- **User category** = most frequent non-*Ninguna* topic among their messages; a tie goes to the most recent message among the tied (`category_tied`). Users with only *Ninguna* get `-1`.
- Category ids are fixed (position in `categorize.CATEGORIES`) and so are their colours (`theme.CATEGORY_COLORS`).
- Met/Unmet per user: unmet if any of a negative message, repeat asker, or MEAL rating <= 2.

## Retraining

A normal run needs no label data. Retrain only if the labels change or the embedding model is updated (the run refuses a model fitted on another embedding revision):

```
python run_pipeline.py --retrain-classifier
```

This needs the three workbooks in `datasets/labels/` (`--check --retrain-classifier` verifies them), refits, re-measures on the frozen test and overwrites the `.joblib`. Commit the new model with the exports. Model and `scikit-learn` version are stored in the file.

## Limits

- **Small classes:** Entidades, Riesgos and Viaje seguro have under 15 test messages each, and few users (15-27); read their scores and terms as indicative.
- **Main confusions** are between neighbours: Asistencia Humanitaria <-> Servicios, Documentos <-> Nacionalidad/Servicios. These are boundaries of intent, and the client's labels are a single annotator's, so agreement ceiling is unknown.
- **Half synthetic weight** (0.5 vs the 1.0 measured in notebook 6) was a team choice: +0.003 macro-F1, inside the noise.
