# Emergent-topic detection — redesign of Section 2/3 (analysis_responses.ipynb)

**Date:** 2026-07-07
**Branch:** feature/analysis-notebooks
**Supersedes:** the original BERTopic Section 2 ("Topic modeling & clustering") and
Section 3 ("Mixed coding") which produced noisy, English-keyword topics and an
unexplained cluster map.

## Problem

The shipped Section 2/3 embedded `df["Text"]` (an **English machine translation**
of the user message) with `paraphrase-multilingual-MiniLM-L12-v2`, then ran
BERTopic (UMAP→HDBSCAN) to invent ~19 topics and crosswalked them back to MMC
categories. Three defects:

1. **Garbage topics.** Keywords came out in English ("3_hello_you_good_questions")
   because the translation `Text` often dropped content (row 2: `Messages` =
   "Hola\nQuiero informacion de los servicios" → `Text` = just "Hello").
2. **Unexplained map.** A second UMAP colored by crosswalked category; the
   clusters were not interpretable and the crosswalk threshold was arbitrary.
3. **Wrong question.** BERTopic re-derived topics that mostly duplicate the 7
   existing MMC categories, instead of answering the actual goal.

## Goal

Determine **which themes people ask the bot that are NOT cleanly covered by the
existing MMC categories** — how many messages, which messages, and *why* they
don't fit — with fast, reproducible, interpretable output.

## Data facts (verified 2026-07-07)

- `Messages` — the **real user question**, Spanish original (835 non-null). This
  is what we embed.
- `Text` — English translation of `Messages`; lossy. **Not used.**
- `Text 1` — bot-generated intent summary (row 0 leaks the prompt
  "Summarize the intent of the question"). **Not used.**
- `Chat_summary` — categorical label, 7 MMC categories with dirty variants
  (`#legal_documentation`, `legaldocumentation`, …); likely bot-assigned.
  Used **only** as a cross-check / label-consensus signal, never as ground truth.
- MMC taxonomy (7): legal documentation, humanitarian assistance, employment,
  services, protection, journey information, organization search.

## Method

### 1. Load & filter
Load `mmc_data.load_responses()`. Keep `Messages` that are real questions; drop a
tiny noise set (`undefined`, `?`, pure numbers, `< 3` chars). ~829 docs. No
aggressive greeting filter is needed once we embed Spanish `Messages` (median
length 133 chars).

### 2. Embed (once, GPU)
`intfloat/multilingual-e5-large` on the Spanish `Messages`, with the required
`"query: "` prefix and `normalize_embeddings=True`. Runs on CUDA (RTX 3050 Ti,
`batch_size` 16, fp16). Embeddings cached to `cache/emb_e5.npy`.

### 3. Cluster all messages (data-driven sub-themes)
UMAP(n_neighbors=15, n_components=5, min_dist=0.0, cosine, random_state=42) →
HDBSCAN(min_cluster_size=12, min_samples=5). Yields ~16 coherent clusters plus a
noise bucket (~272, label −1). Each cluster gets Spanish c-TF-IDF keywords
(CountVectorizer/TfidfVectorizer with a Spanish stopword list, 1–2 grams).

### 4. Category prototypes + fit signals
Embed a one-line Spanish description of each of the 7 MMC categories
(`"passage: …"`). Per cluster compute:
- `near_cat` / `fit` = cosine of the cluster centroid to the nearest prototype.
- `dom_botlabel` / `dom_share` = the most common normalized `Chat_summary` in the
  cluster and its share (label **consensus**).

**Note:** e5 cosine similarities are compressed (all clusters 0.86–0.90), so
cosine `fit` alone does NOT separate emergent from covered. The decisive signal
is **label consensus** (`dom_share`), optionally confirmed by a per-cluster
zero-shot entailment check run on only the ~16 cluster medoids (instant) — NOT on
all 829 messages (that was the mistake that took ~2h on CPU).

### 5. Emergent / cross-cutting verdict
A cluster is **emergent / cross-cutting** when its messages do not concentrate in
a single existing category: `dom_share < 0.60`, plus any cluster that is a clear
**operational complaint** the intent taxonomy has no bucket for (e.g. "trámite
hecho pero no llegó"). Everything else is reported as a **sub-theme** of its
parent MMC category.

Validated emergent set (2026-07-07):

| Theme | n | Why it doesn't fit |
|---|---|---|
| Ayuda: a dónde acudir | 59 | humanitarian 47% / services 24% / employment 12% |
| Salvoconducto + salud (mixto) | 20 | legal 55% / humanitarian 30% / services |
| SISBÉN / EPS / salud | 15 | services 53% / humanitarian 27% / legal |
| PPT que no llega (RUMV) | 12 | operational: biometría hecha, PPT nunca entregado |

**Headline finding:** the 7 MMC categories cover the volume well — there is no
large fully-out-of-taxonomy topic. Value = (a) 16 named sub-themes, (b) these 4
cross-cutting / operational themes single-label coding misses.

### 6. Charts (interpretable)
1. **Map** — 2D UMAP (random_state=42) of the embeddings; covered themes muted
   grey, emergent clusters highlighted + labeled with counts.
2. **Counts** — horizontal bar of emergent themes by message count.
3. **Why-it-doesn't-fit** — stacked bar of each emergent theme's composition
   across the existing `Chat_summary` labels.

Palette from `src/palette.py`; sub-theme table grouped by parent MMC category.

## What is dropped vs the old notebook
- No English `Text`, no MiniLM, no invented BERTopic topic ids as the headline.
- No arbitrary "emergent = c-TF-IDF share < 0.5" crosswalk. Emergent is now
  defined by label consensus + operational reading.
- No per-message zero-shot (the 2h mistake). Zero-shot, if used, only on medoids.

## Non-goals
Turn-level / fallback analysis (no bot-output records — unchanged from prior
data-gaps note). Re-labeling the full dataset into the taxonomy.

## Reproducibility / env
torch CUDA build (cu124) pinned in `pyproject.toml`; embeddings cached under
`cache/`. Fixed `random_state=42` for UMAP. Runs in seconds once embeddings are
cached; first embed pass runs on GPU.
