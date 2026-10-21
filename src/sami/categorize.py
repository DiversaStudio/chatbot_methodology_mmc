"""Message categorisation: the client's 10 categories + "Ninguna", on frozen e5-large embeddings.

The client (MMC) labelled part of the chatbot messages in `messages_category_original.xlsx`
(sheet `Messages`, column `Category 1`) and listed the messages that carry no need of their own
(greetings, thanks, "si", a bare place...) in sheet `Mensajes_NA`. Those are the 11th class,
"Ninguna". This module turns that workbook into a supervised problem and measures how well a
light classifier on the pipeline's own embeddings (`nlp.embed_documents`) can reproduce it.

Design choices that the numbers depend on, so they live here and not in a notebook:

* **Single label.** Only `Category 1`; 345 rows also carry a `Category 2`, which is ignored.
* **Ninguna is one row per distinct text.** `Mensajes_NA` has 1,316 rows but 433 distinct texts
  ("si" x161, "gracias" x143...). Left as is, whichever side of the split "si" lands on would
  dominate the score.
* **One frozen test set.** 20% of the labelled rows, chosen once (seed 42) and grouped by
  normalised text so a duplicated message can never sit on both sides. Every model in the
  notebook is scored on it, once; model selection uses cross-validation on the rest.
* **Macro-F1** is the metric: the classes are very unbalanced (Documentos 890 rows, Entidades 57)
  and accuracy would reward ignoring the small ones.

The labels are client data: the workbook lives in the gitignored `datasets/labels/`, like the
other raw exports, and nothing here writes message text anywhere.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from scipy.sparse import csr_matrix, hstack

from . import datasets

LABELS_FILE = "messages_category_original.xlsx"
SYNTH_FILE = "messages_category_synthetic_haiku.xlsx"      # review workbook of the synthetic messages
NONE = "Ninguna"

#: The client's 10 categories, in the order of the workbook's `Lista` sheet.
CATEGORIES = (
    "Asistencia Humanitaria",
    "Acceso a documentos y regularización",
    "Empleabilidad",
    "Emprendimiento",
    "Entidades del Estado",
    "Acceso a la nacionalidad",
    "Acceso a la protección internacional y asilo",
    "Riesgos de protección",
    "Recomendaciones para un viaje seguro",
    "Acceso a servicios del Estado",
)
CLASSES = CATEGORIES + (NONE,)

#: Short names for tables and axes.
SHORT = {
    "Asistencia Humanitaria": "Asist. Humanitaria",
    "Acceso a documentos y regularización": "Documentos",
    "Empleabilidad": "Empleabilidad",
    "Emprendimiento": "Emprendimiento",
    "Entidades del Estado": "Entidades",
    "Acceso a la nacionalidad": "Nacionalidad",
    "Acceso a la protección internacional y asilo": "Asilo",
    "Riesgos de protección": "Riesgos",
    "Recomendaciones para un viaje seguro": "Viaje seguro",
    "Acceso a servicios del Estado": "Servicios",
    NONE: NONE,
}

SPLIT_SEED = 42      # frozen test set
CV_SEED = 0          # cross-validation folds on the rest
TEST_FRACTION = 0.2


def labels_path() -> Path:
    """Where the client's workbook is expected: `datasets/labels/messages_category_original.xlsx`."""
    return datasets.DATASETS_DIR / "labels" / LABELS_FILE


def synthetic_path() -> Path:
    """Where the synthetic review workbook is expected: `datasets/labels/messages_category_synthetic_haiku.xlsx`."""
    return datasets.DATASETS_DIR / "labels" / SYNTH_FILE


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().str.strip()


def load_labeled(path: str | Path | None = None) -> pd.DataFrame:
    """Every message of the workbook, one row each, with its class where it has one.

    Columns: `row` (position in the `Messages` sheet), `Conversation ID`, `Message #`, `text`
    (the message as the user wrote it), `label` (one of `CLASSES`, or NaN when the client did not
    label it) and `in_na_sheet` (the message is listed in `Mensajes_NA`).

    "Ninguna" is assigned to the first row of every distinct `Mensajes_NA` text; the repeats keep
    NaN so they are neither training nor test examples.
    """
    path = Path(path) if path else labels_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found.\n  fix:  save the client's labelled workbook as "
            f"datasets/labels/{LABELS_FILE} (the folder is gitignored, like the other raw exports).")
    msgs = pd.read_excel(path, sheet_name="Messages")
    na = pd.read_excel(path, sheet_name="Mensajes_NA")
    out = pd.DataFrame({
        "row": np.arange(len(msgs)),
        "Conversation ID": msgs["Conversation ID"].to_numpy(),
        "Message #": msgs["Message #"].to_numpy(),
        "text": msgs["Message"].astype(str).to_numpy(),
        "label": msgs["Category 1"].to_numpy(),
    })
    key = pd.MultiIndex.from_frame(out[["Conversation ID", "Message #"]])
    out["in_na_sheet"] = key.isin(pd.MultiIndex.from_frame(na[["Conversation ID", "Message #"]]))
    first = out["in_na_sheet"] & ~_norm(out["text"]).where(out["in_na_sheet"]).duplicated()
    out.loc[first & out["label"].isna(), "label"] = NONE
    unknown = set(out["label"].dropna()) - set(CLASSES)
    if unknown:
        raise ValueError(f"unexpected labels in {path.name}: {sorted(unknown)}")
    return out


def frozen_split(df: pd.DataFrame) -> pd.Series:
    """Boolean mask over `df`: True for the frozen test rows.

    Topic rows: the first fold of a 5-fold StratifiedGroupKFold (seed 42), grouped by normalised
    text. Ninguna rows: 20% of the distinct texts, drawn with seed 42. Both are properties of the
    data alone, so the test set is the same on every machine and every run.
    """
    test = pd.Series(False, index=df.index)
    topic = df[df["label"].notna() & (df["label"] != NONE)]
    groups = pd.factorize(_norm(topic["text"]))[0]
    _, te = next(StratifiedGroupKFold(5, shuffle=True, random_state=SPLIT_SEED)
                 .split(np.zeros(len(topic)), topic["label"].to_numpy(), groups))
    test.loc[topic.index[te]] = True
    none_rows = df.index[df["label"] == NONE].to_numpy()
    pick = np.random.default_rng(SPLIT_SEED).choice(
        none_rows, size=round(len(none_rows) * TEST_FRACTION), replace=False)
    test.loc[pick] = True
    return test


def cv_folds(y: np.ndarray, groups: np.ndarray, n_splits: int = 5):
    """Grouped, stratified folds over the development rows (never the test set)."""
    return list(StratifiedGroupKFold(n_splits, shuffle=True, random_state=CV_SEED)
                .split(np.zeros(len(y)), y, groups))


def cached_embeddings(texts: list[str], cache: str | Path) -> np.ndarray:
    """`nlp.embed_documents(texts)`, computed once and stored at `cache` (.npz).

    The cache is keyed on a hash of the texts and the pinned model revision, so a changed
    workbook or model recomputes instead of silently reusing stale vectors. CPU: about 14 minutes
    for the client's 6,263 messages; a GPU takes a fraction of that.
    """
    from . import nlp

    cache = Path(cache)
    key = hashlib.sha256(("\n".join(texts) + nlp.EMBED_REVISION).encode("utf-8")).hexdigest()
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        if str(z["key"]) == key:
            return z["emb"]
    emb = nlp.embed_documents(texts, batch_size=16)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, emb=emb, key=np.array(key))
    return emb


def ngram_features(texts_tr, texts_te, emb_tr, emb_te, *, emb_weight: float = 2.0,
                   word: bool = True, char: bool = True):
    """Embeddings (times `emb_weight`; 0 drops them) next to TF-IDF word (1,2) / character (2,5) n-grams.

    The vectorisers are fitted on the training texts only. Returns sparse (train, test) matrices.
    """
    lo_tr, lo_te = [str(t).lower() for t in texts_tr], [str(t).lower() for t in texts_te]
    blocks_tr, blocks_te = [], []
    if emb_weight:
        blocks_tr.append(csr_matrix(emb_tr * emb_weight)); blocks_te.append(csr_matrix(emb_te * emb_weight))
    for on, kw in ((word, dict(ngram_range=(1, 2))), (char, dict(analyzer="char_wb", ngram_range=(2, 5)))):
        if on:
            v = TfidfVectorizer(min_df=2, sublinear_tf=True, strip_accents="unicode", **kw)
            blocks_tr.append(v.fit_transform(lo_tr)); blocks_te.append(v.transform(lo_te))
    return hstack(blocks_tr).tocsr(), hstack(blocks_te).tocsr()


def load_synthetic(path: str | Path | None = None, batches: str | Path | None = None,
                   all_rows: bool = False) -> pd.DataFrame:
    """The synthetic messages, one row each: `text`, `label`, `batch`.

    Reads the `Sinteticos` sheet of the synthetic review workbook. By default a row is kept when `Revisar`
    is empty (the target class and the LLM's check label agree) and its label is `Categoría corregida`
    when a reviewer filled it, else `Categoría objetivo`. With `all_rows=True` every row is kept, flagged
    ones included, and the label is always `Categoría objetivo` (the class the message was written for).
    Rows with no message text are dropped either way. `batch` is the generation batch (from
    `llm_haiku_synth/synthetic.csv`, joined on the workbook's `id`), so cross-validation can keep a
    batch's near-twin messages on one side; NaN when that file is absent.
    """
    path = Path(path) if path else synthetic_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found.\n  fix:  run `python -m sami.llm_labels --version synth synthreport` "
            f"(writes datasets/labels/{SYNTH_FILE}).")
    x = pd.read_excel(path, sheet_name="Sinteticos")
    x = x[x["Mensaje sintético"].notna()]                               # a blank message cannot be embedded
    if all_rows:
        label = x["Categoría objetivo"]
    else:
        x = x[x["Revisar"] != "sí"]
        label = x["Categoría corregida"].where(x["Categoría corregida"].notna(), x["Categoría objetivo"])
    unknown = set(label) - set(CLASSES)
    if unknown:
        raise ValueError(f"unexpected classes in {path.name}: {sorted(unknown)}")
    out = pd.DataFrame({"id": x["id"].to_numpy(), "text": x["Mensaje sintético"].astype(str).to_numpy(),
                        "label": label.to_numpy()})
    b = Path(batches) if batches else path.parent / "llm_haiku_synth" / "synthetic.csv"
    out["batch"] = out["id"].map(pd.read_csv(b)["batch"]) if b.exists() else np.nan
    return out.drop(columns="id").reset_index(drop=True)


def embeddings_with_memo(texts: list[str], cache: str | Path, memo: str | Path | None = None) -> np.ndarray:
    """Like `cached_embeddings`, but reuses vectors already computed for the same texts.

    `memo` is a pickle `{text: vector}` written by `llm_labels.cached_embedder` while the synthetic
    messages were deduplicated (our own file, local and gitignored). Texts it holds are taken from
    it; only the rest go through `nlp.embed_documents`. Same pinned model, so the vectors are the ones
    a full run would produce.
    """
    import pickle

    from . import nlp

    cache = Path(cache)
    key = hashlib.sha256(("\n".join(texts) + nlp.EMBED_REVISION).encode("utf-8")).hexdigest()
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        if str(z["key"]) == key:
            return z["emb"]
    known = pickle.loads(Path(memo).read_bytes()) if memo and Path(memo).exists() else {}
    missing = [t for t in dict.fromkeys(texts) if t not in known]
    if missing:
        known = {**known, **dict(zip(missing, nlp.embed_documents(missing, batch_size=16)))}
    emb = np.array([known[t] for t in texts])
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, emb=emb, key=np.array(key))
    return emb


def scores(y_true, y_pred, classes=None) -> dict:
    """Macro-F1 over `classes`, macro-F1 over the topics among them (no Ninguna), and accuracy.

    `classes` defaults to the classes present in `y_true`, so a 10-class run is not penalised for
    the absent "Ninguna".
    """
    classes = list(classes) if classes is not None else [c for c in CLASSES if c in set(y_true)]
    topics = [c for c in classes if c != NONE]
    return {
        "macro_f1": f1_score(y_true, y_pred, average="macro", labels=classes, zero_division=0),
        "macro_f1_topics": f1_score(y_true, y_pred, average="macro", labels=topics, zero_division=0),
        "accuracy": accuracy_score(y_true, y_pred),
    }


def evaluate(make, X, y, groups, dev: np.ndarray, test: np.ndarray, *, folds=None) -> dict:
    """Cross-validate `make()` on the development rows, then score it once on the test rows.

    `X` is a dense/sparse matrix, or a callable `features(train_rows, test_rows) -> (A, B)` for
    features that must be fitted on the training rows only (TF-IDF). `dev` and `test` are integer
    row positions into `y`. Returns CV mean/sd of macro-F1 and the frozen-test scores.
    """
    y, groups = np.asarray(y), np.asarray(groups)
    classes = [c for c in CLASSES if c in set(y[np.r_[dev, test]])]
    folds = folds or cv_folds(y[dev], groups[dev])

    def fit_predict(tr, te):
        A, B = X(tr, te) if callable(X) else (X[tr], X[te])
        return make().fit(A, y[tr]).predict(B)

    cv = [f1_score(y[dev[va]], fit_predict(dev[tr], dev[va]), average="macro", labels=classes, zero_division=0)
          for tr, va in folds]
    return {"cv_macro_f1": float(np.mean(cv)), "cv_sd": float(np.std(cv)),
            **{f"test_{k}": v for k, v in scores(y[test], fit_predict(dev, test), classes).items()}}


def confidence_gap(model, X) -> np.ndarray:
    """Gap between the best and second-best class score (LinearSVC decision function).

    Not a probability: it ranks messages by how clear-cut the call was. Used to show that the
    messages the model is surest about are right far more often than the rest.
    """
    s = np.sort(model.decision_function(X), axis=1)
    return s[:, -1] - s[:, -2]


# ---- the pipeline's use of the chosen classifier ---------------------------------------------------
#
# Notebooks 5 and 6 chose the setting below. `run_pipeline.py` fits it once per run (about two minutes
# on CPU), labels every message and gives each user the category they wrote about most.

#: Stable `dim_cluster.cluster_id` of each topic: the position in `CATEGORIES`, so the id (and the colour
#: the dashboard binds to it) does not change between runs. "Ninguna" has no id: it is never a user's category.
CATEGORY_IDS = {c: i for i, c in enumerate(CATEGORIES)}

FINAL_FILE = "messages_category_haiku_final.xlsx"     # Haiku's labels with the human corrections on top
SYNTH_MEMO = "llm_haiku_synth/embeddings.pkl"          # vectors computed while the synthetic set was deduplicated

#: The pipeline's setting: Corrected + all synthetic messages, the synthetic ones at HALF weight, RBF SVM,
#: balanced classes. Notebook 6 measured it on the frozen test (final labels) at accuracy 83.7%, macro-F1 0.772,
#: against 83.2% / 0.769 at full weight. That gap is inside the noise (95% interval of the accuracy difference
#: -0.4 to +1.4 points, better in 63% of resamples) and the notebook's own adoption rule did not select it; it
#: was chosen by the team. `frozen_test_scores` re-measures it on every run.
PRODUCTION_SYNTH_WEIGHT = 0.5
PRODUCTION_SVC = {"C": 10, "class_weight": "balanced", "cache_size": 1000}


def required_training_files() -> list[Path]:
    """Files `fit_production` reads, so preflight can name what is missing before any work starts."""
    d = datasets.DATASETS_DIR / "labels"
    return [labels_path(), d / FINAL_FILE, synthetic_path()]


class Production:
    """The fitted classifier plus what it was trained on.

    `train_texts` (normalised) lets a caller tell the messages the model has seen from the ones it has not.
    """

    def __init__(self, model, n_train: int, train_texts: set[str]):
        self.model, self.n_train, self.train_texts = model, n_train, train_texts

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)


def training_set(cache_dir: str | Path, *, include_test: bool = False):
    """Corrected + all synthetic messages, rebuilt as in notebook 5: `(X, y, texts, weight)`.

    `weight` is 1 for a Corrected message and `PRODUCTION_SYNTH_WEIGHT` for a synthetic one (`sample_weight`).

    Corrected = the final labels (Haiku's with the human corrections) of the client's workbook, without the
    frozen test messages, without the unreviewed Haiku/client disagreements, each distinct text once.
    Synthetic = every synthetic message, labelled with the class it was written for. `include_test=True`
    adds the frozen test messages back (a model for production use once its score has been measured).
    """
    cache_dir = Path(cache_dir)
    labels_dir = datasets.DATASETS_DIR / "labels"
    df = load_labeled()
    X_all = cached_embeddings(df["text"].tolist(), cache_dir / "category_embeddings.npz")
    test = frozen_split(df).to_numpy() & df["label"].notna().to_numpy()
    test_texts = set(_norm(df["text"].iloc[np.flatnonzero(test)]))

    final = pd.read_excel(labels_dir / FINAL_FILE, usecols=["id", "Etiqueta final", "Fuente final", "split"])
    keep = final["Fuente final"] != "LLM, discrepa (sin revisar)"
    if not include_test:
        keep &= final["split"] != "prueba"
    cand = final[keep]
    norm = _norm(df["text"].iloc[cand["id"].to_numpy()])
    if not include_test:
        seen_in_test = norm.isin(test_texts).to_numpy()
        cand, norm = cand[~seen_in_test], norm[~seen_in_test]
    cand = cand[~norm.duplicated().to_numpy()]
    rows = cand["id"].to_numpy()
    unknown = set(cand["Etiqueta final"].dropna()) - set(CLASSES)
    if unknown:
        raise ValueError(f"unexpected labels in {FINAL_FILE}: {sorted(unknown)}")

    syn = load_synthetic(all_rows=True)
    X_syn = embeddings_with_memo(syn["text"].tolist(), cache_dir / "synthetic_embeddings.npz",
                                 labels_dir / SYNTH_MEMO)
    X = np.vstack([X_all[rows], X_syn])
    y = np.r_[cand["Etiqueta final"].to_numpy(), syn["label"].to_numpy()]
    texts = pd.concat([df["text"].iloc[rows], syn["text"]], ignore_index=True)
    if not include_test and test_texts & set(_norm(texts)):
        raise AssertionError("a frozen-test text is in the training set")
    weight = np.r_[np.ones(len(rows)), np.full(len(syn), PRODUCTION_SYNTH_WEIGHT)]
    return X, y, texts, weight


def fit_production(cache_dir: str | Path, *, include_test: bool = False) -> Production:
    from sklearn.svm import SVC

    X, y, texts, weight = training_set(cache_dir, include_test=include_test)
    return Production(SVC(**PRODUCTION_SVC).fit(X, y, sample_weight=weight), len(y), set(_norm(texts)))


def frozen_test_scores(prod: Production, cache_dir: str | Path) -> dict:
    """Accuracy and macro-F1 of `prod` on the frozen test messages, against the final labels (notebook 5/6's
    scoring). Only meaningful for a model fitted with `include_test=False`; the messages without a final label
    are left out, as in the notebooks."""
    cache_dir = Path(cache_dir)
    df = load_labeled()
    X_all = cached_embeddings(df["text"].tolist(), cache_dir / "category_embeddings.npz")
    test = np.flatnonzero(frozen_split(df).to_numpy() & df["label"].notna().to_numpy())
    final = pd.read_excel(datasets.DATASETS_DIR / "labels" / FINAL_FILE, usecols=["id", "Etiqueta final"])
    truth = df["row"].map(final.set_index("id")["Etiqueta final"]).to_numpy()[test]
    has = pd.notna(truth)
    sc = scores(truth[has], prod.predict(X_all[test])[has], list(CLASSES))
    return {"accuracy": float(sc["accuracy"]), "macro_f1": float(sc["macro_f1"]), "n": int(has.sum())}


def classify(prod: Production, texts, cache: str | Path) -> np.ndarray:
    """One class of `CLASSES` per text. Embeddings are cached at `cache` (keyed on the texts)."""
    texts = [str(t) for t in texts]
    return prod.predict(cached_embeddings(texts, cache))


def dominant_categories(messages: pd.DataFrame, labels) -> pd.DataFrame:
    """One row per user: the topic they wrote about most.

    `messages` has `user_id`, `ts` and `seq`; `labels` holds one class per message, in the same order.
    `dominant` is the most frequent class other than "Ninguna". When several share the top count the
    one of the user's most recent message among them wins (`tied` marks those users). A user with no
    topic message gets `dominant = NaN`. `n_categories` counts the distinct topics the user wrote about.
    """
    m = pd.DataFrame({"user_id": messages["user_id"].to_numpy(), "ts": messages["ts"].to_numpy(),
                      "seq": messages["seq"].to_numpy(), "label": np.asarray(labels)})
    m = m.sort_values(["user_id", "ts", "seq"], kind="stable")
    topic = m[m["label"] != NONE]
    rows = []
    for uid, g in topic.groupby("user_id", sort=True):
        n = g["label"].value_counts()
        best = set(n.index[n == n.iloc[0]])
        rows.append((uid, g.loc[g["label"].isin(best), "label"].iloc[-1], len(n), len(best) > 1))
    out = pd.DataFrame(rows, columns=["user_id", "dominant", "n_categories", "tied"]).set_index("user_id")
    rest = pd.Index(m["user_id"].unique(), name="user_id").difference(out.index)
    none = pd.DataFrame({"dominant": np.nan, "n_categories": 0, "tied": False}, index=rest)
    return pd.concat([out, none]).sort_index()


def resolve_categories(terms: dict) -> dict:
    """`taxonomy.resolve_cluster_names`' shape for the fixed categories: `{id: {name, marker, description, provisional}}`.

    `marker` is the category's strongest distinctive term, which `export.build_nlp_voices` searches first
    when it picks the quoted message. No name is provisional: the names are the client's.
    """
    out = {}
    for name, cid in CATEGORY_IDS.items():
        top = list(terms[cid].index[:1]) if cid in terms and len(terms[cid]) else []
        out[cid] = {"name": name, "marker": top[0] if top else "", "provisional": False,
                    "description": f"MMC category (message classifier): {name}"}
    return out
