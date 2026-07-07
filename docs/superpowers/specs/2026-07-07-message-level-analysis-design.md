# Message-level rebuild of `analysis_responses.ipynb`

**Date:** 2026-07-07
**Branch:** feature/analysis-notebooks
**Supersedes:** `2026-07-07-emergent-topic-detection-design.md` (that spec kept
user-level granularity; this one moves the whole notebook to message level and
replaces prototype-similarity tinting with zero-shot NLI, based on empirical
validation below).

## Problem

The shipped notebook analyzes one row per **user**, but `Messages` packs **every
user turn separated by `\n`** (mean 3.87, median 3, max 51 messages/user →
~2,993 individual messages inside 835 blobs). Consequences:

- A single user's `Chat_summary` is often **multi-category** (`"legal
  documentation, employment"`, `"humanitarian assistance, legal documentation,
  protection, services"`) because they asked several distinct questions. A
  per-user label is therefore wrong by construction.
- Topic, sentiment and emergent-theme signals are averaged away at user level.

## Goal

Rebuild all 13 sections on a **message-level spine** (one row per user turn,
linked back to the user's full interaction), so every message is coded
individually while demographics/engagement/MEAL still aggregate to the user.
Deliver reliable, **100% reproducible** topic tinting + emergent detection,
richer sentiment (emotions), and well-defined geographic maps.

## Data facts (verified 2026-07-07)

- `Messages` — real Spanish user turns, `\n`-separated. 835 non-null blobs →
  ~2,993 messages after noise filtering.
- `Chat_summary` — dirty per-user label (`#legal_documentation`,
  `legaldocumentation`, comma-concatenated multi-category, one leaked prompt
  row). Weak cross-check only, never ground truth.
- `Text` (English MT) and `Text 1` (bot intent summary) — lossy, **not used**.
- `City Location` — **100% empty** (no lat/lon). Maps need a curated
  city→coordinate lookup.
- `city_clean` — dirty: 158 distinct values, `Bogotá`/`Bogota`,
  `Soacha`/`Soacha Cundinamarca`, `Cundinamarca`, `Colombia`. Needs canonical
  normalization for clean maps.
- `Timestamp` — **per user session**, not per message. All of a user's messages
  share one `ts` (documented limitation for temporal analysis).
- MMC taxonomy (7): legal documentation, humanitarian assistance, employment,
  services, protection, journey information, organization search.
- Env: torch currently **CPU-only** (`2.10.0+cpu`), no CUDA. Cached HF models:
  `intfloat/multilingual-e5-large`, `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`,
  `cardiffnlp/twitter-xlm-roberta-base-sentiment`.

## Empirical model validation (2026-07-07, real messages)

Ran on live data before committing to a method:

| Signal | top1–top2 margin | Verdict |
|---|---|---|
| e5 prototype cosine (per message) | ~0.005 | Unusable per message — compressed cosines; "Hola"→employment, "gracias"→organization. |
| **Zero-shot NLI** (mDeBERTa-xnli) | **~0.32** | Reliable — "Para empleo formal" p=0.98, "Cómo solicitar el salvoconducto" p=0.95; greetings/thanks collapse to low confidence (p≈0.3–0.4), the exact signal to route them to the emergent/residual bucket. |

**Decision:** per-message **tinting = zero-shot NLI** (deterministic argmax →
reproducible). e5 embeddings are kept only for **clustering + naming** emergent
themes (HDBSCAN density is robust to compressed absolute cosine; centroid
averaging denoises the prototype margin used to confirm emergence).

The emotion model (`pysentimiento/robertuito-emotion-analysis`, Spanish-native,
7 classes) is not yet cached; **validation on Spanish samples is task 1 of
implementation**, with `daveni/twitter-xlm-roberta-emotion-es` as fallback.

## Method

### Compute / reproducibility
- `device = "cuda" if torch.cuda.is_available() else "cpu"` — GPU preferred,
  CPU fallback always works. (GPU requires reinstalling torch `cu124`; optional
  env step, out of the notebook's critical path.)
- Fixed `random_state=42` for UMAP; argmax for zero-shot/sentiment/emotion.
- All expensive outputs cached under `cache/`: `emb_msg_e5.npy` (embeddings),
  `zeroshot_labels.parquet` (per-message NLI scores), `emotion.parquet`. Reruns
  are instant; first pass ~30–40 min on CPU for zero-shot over ~2,993 messages.

### §1 — Message-level spine
New `mmc_data.load_messages()`:
- Split `Messages` on `\n`, strip. Drop hard noise: `len < 3`, pure numbers,
  `undefined`, `?`.
- Emit `msgs` (~2,993 rows): `phone`, `msg_idx` (0-based turn position),
  `n_msgs_user`, `message`, joined user attributes (`city_clean`/`city_canon`,
  `ts`, `Gender`, `Age Ranges`, `Nationality`, `age_num`, MEAL fields via
  `phone`).
- Keep user-level `df` for sections that aggregate back.
- **Social-noise flag:** greetings/thanks/courtesy turns ("hola", "gracias",
  "amén", "buenos días", …) detected via a small lexicon **and** confirmed by
  low zero-shot confidence → `mmc_category = "cortesía / no sustantivo"`.
  Excluded from topic tinting but **retained** for §8/§9 flow & engagement.

### §2 — Embedding & clustering (message level)
`intfloat/multilingual-e5-large`, `"query: "` prefix, `normalize_embeddings=True`,
cached. `UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine",
random_state=42)` → `HDBSCAN(min_cluster_size≈15, min_samples≈5)`. Per-cluster
Spanish c-TF-IDF keywords using a **Spanish stopword list** (extended with the
courtesy lexicon), 1–2 grams.

### §3 — Mixed coding: MMC tinting + emergent detection
- **Tinting (per message):** zero-shot NLI over the 7 MMC categories with
  Spanish hypothesis template (`"Este mensaje trata sobre {}."`) and tuned
  Spanish label descriptions. `mmc_category` = argmax; `conf` = top score.
  `conf < ~0.45` → `emergent_candidate = True`.
- **Cluster verdict:** for each e5+HDBSCAN cluster compute (a) share of
  low-confidence / emergent-candidate messages, (b) centroid→prototype margin,
  (c) weak `Chat_summary` consensus. A cluster is **emergent / cross-cutting**
  when emergent-candidates concentrate in it AND centroid margin is low, or its
  keywords name an operational theme the taxonomy has no bucket for (e.g. "PPT
  que no llega"). Others = **sub-theme** of the nearest MMC category.
- Outputs: table (cluster → keywords → nearest MMC → margin → % low-conf →
  verdict); per-message `mmc_category` + `is_emergent`.
- **§3.1 map:** 2D `UMAP(random_state=42)`; covered themes muted grey, emergent
  clusters highlighted + labeled with counts.

### §4–§13 — cross-cuts on the message spine
- **§4 Needs/entities** — `mmc_entities` per message (PPT, EPS, Migración
  Colombia, SISBÉN…) × `mmc_category`.
- **§5 Geographic by city** — per-message category volume across the top MMC
  cities, using `city_canon` (see Geo below).
- **§6 Temporal** — category counts over session `ts` (caveat: per-user ts) vs
  migration-policy events.
- **§7 Demographic × topic** — aggregate message categories back to user;
  heatmaps by gender, age range, nationality.
- **§8 Engagement depth** — messages/user distribution.
- **§9 Drop-off + reformulation** — conversation-length distribution; category
  & emotion of the **last** message (where users stop); repeated questions by
  the same user (similarity between consecutive turns). Honest: user-side only,
  no bot turns.
- **§10 Sentiment + Emotion** — 3-class valence (`twitter-xlm-roberta`) **plus
  7-class emotion** per message; distribution, emotion×topic, emotion×city.
- **§11 MEAL × topic** — join by `phone`; user's dominant message-category vs
  MEAL utility.
- **§12 Geographic clustering / maps** — see Geo below.
- **§13 Data gaps** — keep honest limits: no bot output ⇒ no true
  fallback/consistency/turn-level drop-off; per-user timestamp; heuristic
  reformulation.

### Geographic maps (well-defined — user requirement)
- **`city_canon` normalization** in `mmc_data`: accent-fold + map variants to
  canonical names (`Bogota`→`Bogotá`, `Soacha Cundinamarca`→`Soacha`, drop
  non-cities like `Colombia`/`Cundinamarca` to `Otra/NA`), consolidating 158 →
  the ~10 MMC priority cities + long tail.
- Curated `CITY_COORDS` lookup (lat/lon) for the priority cities (reuse/extend
  §12's).
- Colombia outline cached at `cache/colombia_boundary.gpkg` (osmnx one-time).
- Maps: (1) message volume per city (bubble size), (2) dominant MMC category per
  city (categorical color = MMC palette), (3) mean sentiment/emotion per city
  (diverging scale). Consistent palette from `src/palette.py`; readable labels,
  legends, and a clean Colombia basemap.

## Non-goals
Turn-level / fallback / response-consistency analysis (no bot-output records).
Re-labeling the full corpus by hand.

## Deliverables
- `src/mmc_data.py`: `load_messages()`, `city_canon` normalization, courtesy
  lexicon helper. Unit tests in `tests/`.
- `notebooks/analysis_responses.ipynb`: all 13 sections rebuilt on `msgs`.
- Cached artifacts under `cache/`.
- `pyproject.toml`: add emotion-model dep if needed (`pysentimiento` or direct
  transformers). Document optional torch `cu124` for GPU.
