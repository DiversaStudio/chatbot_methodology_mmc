# Notebook Reorganization Implementation Plan

> **For agentic workers:** This is a notebook-assembly task, not TDD. "Tests" = structural checks (valid nbformat, expected sections present, no palette symbols, outputs cleared). Final correctness (top-to-bottom run) is done by the user, who has the GPU/data/models.

**Goal:** Reorganize 4 source notebooks (`notebooks/arxiv/*.ipynb`) into 3 narrative notebooks per the design spec.

**Architecture:** A Python assembly script per notebook reads specified cells from the arxiv sources, strips outputs, strips the brand palette (falls back to matplotlib defaults via a small neutral placeholder), rewrites each notebook's self-contained setup preamble, adds section markdown, and writes a valid `.ipynb`. NB1/NB2 are pure reorganization; NB3 is re-designed to a simpler NLP stack.

**Tech Stack:** Python, `nbformat`/JSON, pandas/matplotlib/seaborn (notebook runtime), sentence-transformers + spaCy + sklearn KMeans (NB3 runtime only).

## Global Constraints

- **No palette.** Remove `from palette import *`; charts fall to matplotlib defaults. Provide a small, clearly-labeled neutral placeholder cell for functional helpers (`pct_count_autopct`, `bar_colors`, sequential ramps) so cells still run. Real palette added later by user.
- **All outputs cleared.** Every cell `outputs: []`, `execution_count: null`.
- **Keep documentation traditions:** `##`/`###` section headers, a guiding-question comment at the top of each code cell, collapsed setup, no analysis in setup.
- **No new analysis in NB1/NB2.** NB3 changes method per spec.
- **Do not execute notebooks here** (GPU/data/models absent). Verify structurally only.
- Sources stay in `notebooks/arxiv/`. Commit after each notebook.

---

### Task 1: Neutral styling placeholder + assembly helper

**Files:**
- Create: `notebooks/_reorg_build.py` (throwaway assembly helper, deleted at end)

**Steps:**
- [ ] Write a helper that loads an arxiv notebook, returns cells by index, clears outputs/execution_count, and can substitute a `NEUTRAL_STYLE` setup cell.
- [ ] `NEUTRAL_STYLE` defines matplotlib-default equivalents for referenced palette names: color constants → `None`; `bar_colors(n)/cat_colors(n)/seq_colors(n)` → `[None]*n`; `pct_count_autopct(values)` kept verbatim (it is a label formatter, not color). Header comment: `# Temporary neutral styling -- brand palette added later.`
- [ ] Verify: `python -c "import ast; ast.parse(open('notebooks/_reorg_build.py').read())"` → no error.

### Task 2: NB1 — `01_eda_perfil_y_satisfaccion.ipynb`

**Files:**
- Create: `notebooks/01_eda_perfil_y_satisfaccion.ipynb`
- Delete: `notebooks/1_eda_perfil_y_satisfaccion.ipynb` (old stub)

**Cells (from spec):** setup (fresh, `df=load_responses()`, `meal=load_meal()`), then eda_responses c10-11, c15, c17, c19-20, c22, c26, c34, c41, c43, c45; then eda_meal c5, c7, c9, c11, c13, c16. Section markdown between blocks.

**Steps:**
- [ ] Build the notebook via helper; strip palette refs in moved cells.
- [ ] Verify valid: `python -c "import nbformat; nbformat.read('notebooks/01_eda_perfil_y_satisfaccion.ipynb',4)"`.
- [ ] Verify no `import palette`/`from palette` and all outputs empty (script check).
- [ ] Verify sections present: Data Load, Data Quality, 3.1-3.4, Cities, Time away, Topics, Questions per user, Survey, MEAL usefulness/recommend/channel/length.
- [ ] Commit.

### Task 3: NB2 — `02_analisis_general_comportamiento_necesidades.ipynb`

**Files:**
- Create: `notebooks/02_analisis_general_comportamiento_necesidades.ipynb`

**Cells (narrative order from spec):** setup (`df`, `meal`, `msgs=load_messages(df)`, `mmc_entities`, `MMC_LABELS`, `NON_TOPIC_CATS`, helpers) → eda_responses c27, c29-30, c36-37, c51, c53, c55 → eda_responses c47 → eda_meal c20 → eda_meal c18 → analysis_meal c11 → analysis_responses c17 → c19-20 → c22-23 → c25-27 → c29 → c31 → c36-37.

**Steps:**
- [ ] Build; strip palette; pull needed helper defs (`MMC_LABELS`, `NON_TOPIC_CATS`, cross-tab/heatmap helpers) from analysis_responses setup cells into NB2 setup.
- [ ] Verify valid nbformat, no palette, outputs cleared.
- [ ] Verify reformulation cell (analysis_responses c32) is NOT present.
- [ ] Commit.

### Task 4: NB3 — `03_nlp_clustering_usuario_y_sentimiento.ipynb`

**Files:**
- Create: `notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb`

**Content (re-designed, mostly new cells):**
- Setup: imports + sentence-transformers, spaCy(es) for lemmatization, sentiment model; `msgs=load_messages(df)`; aggregate to per-user documents (concat messages by `phone`).
- Sec 1 Features: e5-large user-document embeddings (primary); TF-IDF of lemmatized text (comparison).
- Sec 2 KMeans (user level): KMeans(k=7) on embeddings; KMeans(k=7) on TF-IDF.
- Sec 3 Clusters vs original: per-user dominant MMC category / Chat_summary; ARI, NMI, purity, confusion matrix, for both feature sets.
- Sec 4 Sentiment: 3-class sentiment per message → aggregate by user/cluster/category (reuse the 3-class sentiment code from analysis_responses c34, drop the 7-class emotion cell c35).
- Sec 5 Geographic synthesis map: dominant need + sentiment tone per city (adapt analysis_responses c39-41, drop the embedding/cluster-tinting inputs).

**Steps:**
- [ ] Build the setup + user-aggregation cells (new code).
- [ ] Build features, KMeans, agreement, sentiment, synthesis-map cells (new + adapted from analysis_responses c34, c39-41).
- [ ] Strip palette; clear outputs.
- [ ] Verify valid nbformat, no palette, outputs cleared, no UMAP/HDBSCAN/zero-shot/emergent/reformulation references.
- [ ] Commit.

### Task 5: Cleanup & final check

- [ ] Delete `notebooks/_reorg_build.py`.
- [ ] Verify all three notebooks parse and `notebooks/arxiv/` sources untouched.
- [ ] Update memory (analysis_notebooks / project_overview) with the 3-notebook structure.
- [ ] Final commit.

## Self-Review

- Spec coverage: NB1 cells ✓, NB2 cells + city-map-moved + reformulation-dropped ✓, NB3 simplified stack (embeddings+TF-IDF KMeans, agreement, 3-class sentiment, synthesis map) ✓, palette strip ✓, outputs cleared ✓, sources preserved ✓.
- No placeholders except the intentional NEUTRAL_STYLE (documented).
- Naming consistent: `01_/02_/03_` prefixes; NB3 `_sentimiento`.
