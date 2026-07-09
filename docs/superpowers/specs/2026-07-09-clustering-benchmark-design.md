# Clustering benchmark notebook — design

**Date:** 2026-07-09
**Branch:** `feature/analysis-notebooks`
**Deliverable:** `notebooks/clustering_benchmark.ipynb`

## Purpose

A single notebook that compares **all viable clustering approaches** for the MMC
chatbot data, at both the **message** and **user** level, on both **semantic
(e5-large embeddings)** and **lexical (TF-IDF)** representations. For every
method it produces: a 2D cluster plot, per-cluster example messages, suggested
cluster names (three methods), and a rich set of evaluation metrics — so we can
decide which clustering approach is best for this corpus.

This is exploratory/benchmark work. It does **not** replace
`analysis_responses.ipynb`; it is the sandbox where we justify the clustering
choices made there.

## Data & infrastructure (reused, not rebuilt)

- `src/mmc_data.load_messages()` → ~2993 message rows (one per user turn), with
  carried `phone`, `city_canon`, `Gender`, `Age Ranges`, `Nationality`, `ts`.
- User level: aggregate messages per `phone` (concatenate turns) → ~946 rows.
- `Chat_summary` (bot's own labels, from `load_responses()`) is the pseudo
  ground-truth for external validation. **Normalize + dedupe on `phone` via
  `.map`, never `merge`** (29 duplicate phones — documented gotcha).
- Palette from `src/palette.py` (`cat_colors`, `CAT`, `BLUE_SEQ`, rcParams).
- GPU: torch cu128, `DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'`.
  Free VRAM (`del model; torch.cuda.empty_cache()`) after embedding on the 4GB
  card. **No disk cache** — everything computed inline (project rule).

## Notebook structure

### §0 Setup (collapsed)
Imports, `sys.path.insert(0, '../src')`, palette, seeds. Load messages + build
user-level frame. **Compute once, reuse everywhere:**
- e5-large fp16 embeddings (prefix `"query: "` per e5 convention), L2-normalized.
- UMAP → 2D (plots) and UMAP → ~15D (clustering input), `random_state=42`.
- PCA → 50D (alternate reducer, for methods that prefer linear/global structure).
- TF-IDF matrix (Spanish stopwords from `mmc_text.SPANISH_STOPWORDS`,
  `min_df`, uni+bigrams) + TruncatedSVD(100) for algorithms needing dense input.

### §1 Representations
Short markdown + a couple of diagnostic cells contrasting semantic vs lexical
spaces (e.g. nearest-neighbour sanity check, explained variance of PCA/SVD).

### §2 Algorithm benchmark
A uniform `fit_and_eval(name, labels, X_for_metrics, ...)` helper that computes
all internal/external/stability metrics and appends one row to a **leaderboard
DataFrame**. Methods run:

| Method | Representation(s) | k selection |
|---|---|---|
| KMeans | embeddings (UMAP-15D, PCA-50), TF-IDF-SVD | k sweep + elbow/silhouette |
| GaussianMixture | embeddings, PCA-50 | BIC/AIC sweep |
| HDBSCAN | embeddings (UMAP-15D) | auto (min_cluster_size sweep) |
| Agglomerative | embeddings, TF-IDF-SVD | dendrogram + k |
| Spectral | embeddings | eigengap heuristic |
| BERTopic | raw text (its own e5→UMAP→HDBSCAN) | auto |
| LDA (sklearn) | TF-IDF/count | perplexity sweep |

The chosen `k` for parametric methods is driven by §4 diagnostics, not hardcoded.

### §3 Cluster plots
Grid of 2D UMAP scatters, one panel per method, points colored by that method's
labels (brand `cat_colors`; noise = light grey). Shared projection so panels are
visually comparable. Cluster centroids annotated with the method's cluster id.

### §4 Evaluation metrics — "what else we can evaluate per method"
**Internal (label-free):** silhouette (cosine + euclidean), Davies-Bouldin,
Calinski-Harabasz, n_clusters, cluster-size balance (Gini/entropy), noise % (for
density methods).
**External (vs normalized `Chat_summary`):** ARI, NMI, homogeneity,
completeness, V-measure.
**Stability:** mean pairwise ARI across N bootstrap subsamples.
**Per-method deep-dives:**
- KMeans — inertia/elbow curve, silhouette-vs-k.
- GMM — BIC/AIC-vs-k, soft-assignment entropy (uncertainty histogram).
- HDBSCAN — min_cluster_size sensitivity, condensed tree, GLOSH outlier scores,
  cluster persistence.
- Agglomerative — dendrogram, cophenetic correlation, ward/average/complete
  linkage comparison.
- Spectral — eigengap plot of the affinity Laplacian.
- BERTopic — hierarchical topic tree, intertopic distance map, topic coherence
  (c-TF-IDF based) + topic diversity.
- LDA — perplexity-vs-topics, top-words-per-topic, c-TF-IDF coherence.

### §5 Cluster interpretation (best 1–2 methods)
Per cluster: representative messages (closest-to-centroid/medoid + random
sample), top c-TF-IDF terms, and **three suggested names**:
1. **Chat_summary consensus** — dominant normalized bot label (share ≥ 0.40 else
   "emergente"). Project-validated method.
2. **Top TF-IDF terms** — most distinctive words joined into a label.
3. **LLM summary (optional, auto-skip)** — if `ANTHROPIC_API_KEY` is set, send a
   sample of each cluster's messages to the Claude API for a short Spanish name;
   otherwise print a notice and skip. Never blocks execution / offline runs.

### §6 Recommendation
Leaderboard summary + a short written verdict: which method wins at message level
and at user level, and why (metric trade-offs + qualitative coherence).

### §7 User-level benchmark
Full benchmark repeated on the ~946 aggregated-user profiles (same helpers).
Per user decision: **full scope, not trimmed.**

## Non-goals / YAGNI
- No disk caching of embeddings or models.
- No `gensim` dependency — LDA via `sklearn.LatentDirichletAllocation`, coherence
  via c-TF-IDF (no external coherence lib). `pyLDAvis` optional at most.
- Does not modify `analysis_responses.ipynb` or `src/` public APIs. If a small
  shared helper is genuinely reused (e.g. `Chat_summary` normalization), it may be
  added to `src/` with a unit test, following existing patterns.

## Execution notes
- Run from `notebooks/`. Build via the project's builder pattern, then
  `uv run jupyter nbconvert --execute` with ~25 min timeout.
- `PYTHONIOENCODING=utf-8` for Spanish output on the cp1252 Windows console.
- Restart kernel before executing after external edits (Jupyter autosave clobber).

## Success criteria
- Notebook executes end-to-end on GPU without manual intervention (LLM cell may
  self-skip).
- Leaderboard renders with all methods and all metric columns populated.
- §3 shows one comparable cluster plot per method.
- §5 shows example messages + 3 suggested names for each cluster of the best
  method(s).
- §6 states a clear recommendation.
