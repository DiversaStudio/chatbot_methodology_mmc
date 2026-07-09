# Clustering Benchmark Notebook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build `notebooks/clustering_benchmark.ipynb` — a single notebook that benchmarks all viable clustering approaches on the MMC chatbot messages and users, with cluster plots, per-cluster examples, three name-suggestion methods, and rich per-method metrics.

**Architecture:** A throwaway builder script (`scratchpad/build_clustering_nb.py`) assembles the notebook via `nbformat`, following the repo's established "builder pattern". Embeddings/TF-IDF are computed once in §0 and reused. A uniform `fit_and_eval` helper drives every algorithm into one leaderboard. Then per-method deep-dives, interpretation, and a user-level repeat. Executed with `uv run jupyter nbconvert --execute`.

**Tech Stack:** sentence-transformers (e5-large, GPU cu128), umap-learn, hdbscan, scikit-learn (KMeans, GMM, Agglomerative, Spectral, LDA, metrics), bertopic, matplotlib/seaborn, `src/palette.py`, `src/mmc_data.py`, `src/mmc_text.py`, optional anthropic SDK.

## Global Constraints
- Python via `uv` only. Run notebooks from `notebooks/`. `sys.path.insert(0, '../src')`.
- GPU: `DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'`; e5 uses `"query: "` prefix, fp16 on cuda, free VRAM after embed. **No disk cache.**
- `random_state=42` everywhere reproducible (UMAP, KMeans, GMM, etc.).
- `Chat_summary` normalization must **dedupe on `phone` via `.map`, never `merge`**.
- Palette from `src/palette.py` only (`cat_colors`/`CAT`/`BLUE_SEQ`); noise = light grey `#e0dedb`.
- LLM naming cell must **auto-skip** when `ANTHROPIC_API_KEY` is unset — never block execution.
- No `gensim`. LDA via `sklearn`; coherence via c-TF-IDF.
- `PYTHONIOENCODING=utf-8` when executing. Do not modify `analysis_responses.ipynb`.

---

### Task 1: Builder scaffold + §0 setup/representations
**Files:**
- Create: `scratchpad/build_clustering_nb.py` (throwaway builder)
- Create (output): `notebooks/clustering_benchmark.ipynb`

**Interfaces — Produces (globals defined in §0, relied on by later cells):**
- `msgs` (DataFrame, message-level, cols incl. `message`, `phone`, `Chat_summary`-derived `cs`), `users` (DataFrame, aggregated per phone with `text`).
- `emb` (float32 [n,1024]), `emb_u` (user embeddings).
- `red2` / `red2_u` (UMAP 2D), `red15` / `red15_u` (UMAP 15D), `pca50` / `pca50_u`.
- `tfidf` (sparse), `tfsvd` (dense 100D), and user equivalents `tfidf_u`, `tfsvd_u`.
- `norm_cs(v)` helper + `cs_map`; `MMC_CATS` set.
- `LEADER` = [] list of metric dicts; `NOISE_COLOR = "#e0dedb"`.

- [ ] **Step 1:** Write `build_clustering_nb.py` that appends cells to an `nbformat.v4` notebook via a `md(txt)` / `code(src)` helper, and writes `notebooks/clustering_benchmark.ipynb`. Add the title markdown + §0 setup code cell: imports, palette, seeds, `msgs = load_messages()`, build `users` (groupby phone, join messages with `"\n"`, carry demographics), `norm_cs` + `cs_map` + `msgs["cs"]`/`users["cs"]`.
- [ ] **Step 2:** Add the embedding cell: e5-large fp16, `"query: "` prefix, encode `msgs["message"]` → `emb` and `users["text"]` → `emb_u`; free VRAM. Print shapes + timing.
- [ ] **Step 3:** Add reductions cell: UMAP 2D/15D (cosine, rs=42) and PCA-50 for both `emb`/`emb_u`; TF-IDF (`SPANISH_STOPWORDS`, uni+bi, `min_df=3`) + TruncatedSVD(100) for both. Store all globals.
- [ ] **Step 4:** Add §1 representation-diagnostics cell: PCA/SVD explained-variance bars (brand palette) + a nearest-neighbour sanity print contrasting semantic vs lexical.
- [ ] **Step 5:** Run builder, then execute just §0+§1: `cd notebooks && PYTHONIOENCODING=utf-8 uv run jupyter nbconvert --to notebook --execute --inplace clustering_benchmark.ipynb`. Expected: no errors, embeddings shape printed. Fix any failures before continuing.
- [ ] **Step 6:** Commit: `git add scratchpad/build_clustering_nb.py notebooks/clustering_benchmark.ipynb docs/ && git commit -m "clustering nb: setup, embeddings, representations (§0-1)"`

### Task 2: §2 uniform benchmark + §3 cluster plots
**Interfaces — Consumes:** all §0 globals. **Produces:** `LEADER` populated; `LABELS` dict `{method_name: labels_array}` at message level; leaderboard DataFrame `board`.

- [ ] **Step 1:** Add `fit_and_eval(name, labels, X_metric, rep)` helper cell: computes silhouette (cosine+euclid), Davies-Bouldin, Calinski-Harabasz, n_clusters, size-entropy, noise%, and external ARI/NMI/homogeneity/completeness/V-measure vs `cs` (on non-null rows); appends dict to `LEADER`, stores `LABELS[name]`.
- [ ] **Step 2:** Add algorithm cells (message level), each calling `fit_and_eval`: KMeans (k from Task 3 sweep, on red15/pca50/tfsvd), GaussianMixture, HDBSCAN (red15), Agglomerative (ward on red15 + on tfsvd), Spectral (red15), BERTopic (raw text), LDA (count matrix). Use try/except per method so one failure doesn't abort the leaderboard (print a warning row).
- [ ] **Step 3:** Add leaderboard render cell: `board = pd.DataFrame(LEADER)` sorted by silhouette; styled/plain table print.
- [ ] **Step 4:** Add §3 plot cell: grid of 2D UMAP scatters (`red2`), one panel per method in `LABELS`, colored by `cat_colors`, noise grey; titled with method + n_clusters.
- [ ] **Step 5:** Run builder + execute full notebook so far. Expected: leaderboard table with all methods, plot grid renders. Fix failures.
- [ ] **Step 6:** Commit: `clustering nb: algorithm benchmark + cluster plots (§2-3)`

### Task 3: §4 per-method deep-dives
**Interfaces — Consumes:** §0 globals, `LABELS`. **Produces:** chosen `k` values used by Task 2 (elbow/BIC feed KMeans/GMM/Spectral k — builder orders these cells before the parametric fits, or uses a k chosen in a preceding sweep cell).

- [ ] **Step 1:** Add k-selection sweep cell BEFORE the parametric fits: KMeans inertia/elbow + silhouette-vs-k (k=2..15), GMM BIC/AIC-vs-k, Spectral eigengap plot; set `K_EMB` used by Task 2 parametric methods.
- [ ] **Step 2:** Add density/hierarchical diagnostics: HDBSCAN min_cluster_size sensitivity + GLOSH outlier hist + persistence; Agglomerative dendrogram + cophenetic correlation across ward/average/complete.
- [ ] **Step 3:** Add topic-model diagnostics: BERTopic hierarchical tree + intertopic distance (or fallback bar of topic sizes) + c-TF-IDF coherence & topic diversity; LDA perplexity-vs-topics + top-words-per-topic + c-TF-IDF coherence.
- [ ] **Step 4:** Add stability cell: mean pairwise ARI across N=5 bootstrap subsamples for KMeans/HDBSCAN/Agglomerative; append to `board`.
- [ ] **Step 5:** Run builder + execute. Expected: all diagnostic plots render, no crash. Fix failures.
- [ ] **Step 6:** Commit: `clustering nb: per-method deep-dive metrics (§4)`

### Task 4: §5 interpretation + §6 recommendation
**Interfaces — Consumes:** `LABELS`, `board`, `emb`, `tfidf`, `cs_map`. **Produces:** per-cluster name table; written recommendation.

- [ ] **Step 1:** Add `describe_clusters(labels, name)` helper: for each cluster, representative messages (closest to centroid + random), top c-TF-IDF terms, Chat_summary consensus name (share≥0.40 else "emergente"), TF-IDF-term name. Print a tidy table + examples.
- [ ] **Step 2:** Call it for the best 1–2 methods (by leaderboard).
- [ ] **Step 3:** Add optional LLM-naming cell: if `os.environ.get("ANTHROPIC_API_KEY")`, call Claude API (`claude-haiku-4-5`) with a sample of each cluster's messages for a short Spanish name; else print skip notice. Wrap in try/except.
- [ ] **Step 4:** Add §6 recommendation markdown+code: summarize leaderboard, name the winning method(s) at message level, with reasoning.
- [ ] **Step 5:** Run builder + execute. Expected: example messages + 3 names per cluster; LLM cell skips cleanly without key. Fix failures.
- [ ] **Step 6:** Commit: `clustering nb: cluster interpretation + names + recommendation (§5-6)`

### Task 5: §7 user-level benchmark + final full run
**Interfaces — Consumes:** all user-level globals (`emb_u`, `red*_u`, `tfsvd_u`, `users`).

- [ ] **Step 1:** Add §7 cells mirroring §2–§5 on user-level data (full scope): `fit_and_eval` into a second leaderboard `board_u`, user-level plot grid, deep-dives (lighter where identical math), interpretation with names.
- [ ] **Step 2:** Add closing markdown comparing message-level vs user-level winners.
- [ ] **Step 3:** Full clean run: restart-execute the whole notebook `PYTHONIOENCODING=utf-8 uv run jupyter nbconvert --to notebook --execute --inplace clustering_benchmark.ipynb` (~25 min timeout). Expected: end-to-end success, all sections populated.
- [ ] **Step 4:** Update `MEMORY.md` + `analysis_notebooks.md` memory with the new notebook + winning method finding.
- [ ] **Step 5:** Commit: `clustering nb: user-level benchmark + full executed run (§7)`

## Self-Review
- Spec §0–§7 each map to Tasks 1–5. ✓
- No placeholders; each task lists concrete cells and the exact execute command. ✓
- Global names (`emb`, `red15`, `LABELS`, `board`, `fit_and_eval`, `describe_clusters`, `norm_cs`) are defined before use and consistent across tasks. ✓
- Constraints (no cache, GPU, dedupe-via-map, auto-skip LLM, no gensim) captured in Global Constraints. ✓
