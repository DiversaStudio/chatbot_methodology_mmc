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
