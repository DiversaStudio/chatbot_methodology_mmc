"""Message categorisation: label loading, the frozen split, scoring.

All synthetic: a tiny workbook is written to tmp_path and embeddings are random, so these tests run on
any clone. They check the properties the notebook's numbers depend on (Ninguna dedupe, a test set no
duplicated text can straddle, determinism), not model quality.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.svm import LinearSVC

from sami import categorize as cz


def _workbook(path, n_per_class=30):
    rng = np.random.default_rng(0)
    rows = []
    for c in cz.CATEGORIES:
        for i in range(n_per_class):
            rows.append((f"{c[:6]} mensaje {i % 25}", c))          # i % 25 -> 5 duplicated texts per class
    # unlabeled rows, and "Ninguna" candidates: 4 distinct texts, repeated
    rows += [(f"sin etiqueta {i}", None) for i in range(10)]
    na = ["si", "gracias", "ok", "hola"]
    rows += [(t, None) for t in na for _ in range(5)]
    rng.shuffle(rows)
    df = pd.DataFrame(rows, columns=["Message", "Category 1"])
    df["Conversation ID"] = [f"c{i // 4}" for i in range(len(df))]
    df["Message #"] = [i % 4 for i in range(len(df))]
    is_na = df["Message"].isin(na)
    with pd.ExcelWriter(path) as xw:
        df.to_excel(xw, sheet_name="Messages", index=False)
        df[is_na][["Conversation ID", "Message #", "Message"]].to_excel(xw, sheet_name="Mensajes_NA", index=False)
    return path


@pytest.fixture
def labeled(tmp_path):
    return cz.load_labeled(_workbook(tmp_path / "labels.xlsx"))


def test_ninguna_is_one_row_per_distinct_text(labeled):
    ninguna = labeled[labeled["label"] == cz.NONE]
    assert len(ninguna) == 4
    assert ninguna["text"].str.lower().is_unique
    # repeats of a Mensajes_NA text stay unlabeled instead of becoming extra examples
    assert labeled["in_na_sheet"].sum() == 20 and labeled["label"].notna().sum() == 10 * 30 + 4


def test_labels_are_closed_set(labeled):
    assert set(labeled["label"].dropna()) <= set(cz.CLASSES)


def test_missing_workbook_names_the_fix(tmp_path):
    with pytest.raises(FileNotFoundError, match="datasets/labels"):
        cz.load_labeled(tmp_path / "nope.xlsx")


def test_unknown_label_is_rejected(tmp_path):
    p = _workbook(tmp_path / "bad.xlsx")
    msgs = pd.read_excel(p, sheet_name="Messages")
    msgs.loc[msgs["Category 1"].notna().idxmax(), "Category 1"] = "Otra cosa"
    na = pd.read_excel(p, sheet_name="Mensajes_NA")
    with pd.ExcelWriter(p) as xw:
        msgs.to_excel(xw, sheet_name="Messages", index=False)
        na.to_excel(xw, sheet_name="Mensajes_NA", index=False)
    with pytest.raises(ValueError, match="unexpected labels"):
        cz.load_labeled(p)


def test_frozen_split_is_deterministic_and_about_a_fifth(labeled):
    a, b = cz.frozen_split(labeled), cz.frozen_split(labeled)
    assert a.equals(b)
    n_labeled = labeled["label"].notna().sum()
    assert 0.1 < a.sum() / n_labeled < 0.35
    assert not labeled.loc[a, "label"].isna().any()                 # only labelled rows are ever test rows


def test_no_text_is_on_both_sides_of_the_split(labeled):
    t = cz.frozen_split(labeled)
    lab = labeled[labeled["label"].notna()]
    norm = cz._norm(lab["text"])
    assert not set(norm[t[lab.index]]) & set(norm[~t[lab.index]])


def test_scores_perfect_and_partial():
    y = np.array(list(cz.CLASSES) * 2)
    s = cz.scores(y, y)
    assert s == {"macro_f1": 1.0, "macro_f1_topics": 1.0, "accuracy": 1.0}
    bad = y.copy(); bad[bad == cz.NONE] = cz.CATEGORIES[0]
    s = cz.scores(y, bad)
    assert s["accuracy"] < 1.0 and s["macro_f1"] < 1.0


def test_scores_ignore_classes_absent_from_the_truth():
    y = np.array(list(cz.CATEGORIES) * 2)                        # a 10-class run: no Ninguna anywhere
    assert cz.scores(y, y)["macro_f1"] == 1.0


def test_evaluate_reports_cv_and_test_scores(labeled):
    lab = labeled[labeled["label"].notna()].reset_index(drop=True)
    rng = np.random.default_rng(1)
    classes = {c: i for i, c in enumerate(cz.CLASSES)}
    centers = rng.normal(size=(len(classes), 16)) * 3
    y = lab["label"].to_numpy()
    X = centers[[classes[c] for c in y]] + rng.normal(size=(len(y), 16))   # separable on purpose
    test = cz.frozen_split(labeled)[labeled["label"].notna()].to_numpy()
    groups = pd.factorize(cz._norm(lab["text"]))[0]
    r = cz.evaluate(lambda: LinearSVC(C=1, class_weight="balanced"), X, y, groups,
                    np.flatnonzero(~test), np.flatnonzero(test))
    assert set(r) == {"cv_macro_f1", "cv_sd", "test_macro_f1", "test_macro_f1_topics", "test_accuracy"}
    assert r["test_macro_f1"] > 0.9 and r["cv_macro_f1"] > 0.9


def test_confidence_gap_is_nonnegative_and_one_per_row():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(120, 8)); y = rng.integers(0, 4, 120)
    gap = cz.confidence_gap(LinearSVC().fit(X, y), X)
    assert gap.shape == (120,) and (gap >= 0).all()


def test_ngram_features_shapes_and_train_only_vocabulary():
    tr = ["necesito comida", "quiero trabajo", "necesito comida ya", "quiero un trabajo"]
    te = ["comida", "palabra nueva"]
    A, B = cz.ngram_features(tr, te, np.ones((4, 3)), np.ones((2, 3)))
    assert A.shape[0] == 4 and B.shape[0] == 2 and A.shape[1] == B.shape[1]


def test_cached_embeddings_reuses_the_cache(tmp_path, monkeypatch):
    from sami import nlp
    calls = []
    monkeypatch.setattr(nlp, "embed_documents", lambda t, batch_size=16: calls.append(len(t)) or np.ones((len(t), 4), "float32"))
    f = tmp_path / "emb.npz"
    a = cz.cached_embeddings(["a", "b"], f)
    b = cz.cached_embeddings(["a", "b"], f)
    cz.cached_embeddings(["a", "c"], f)                              # changed text -> recompute
    assert calls == [2, 2] and a.shape == b.shape == (2, 4)


def test_evaluate_accepts_a_features_callable(labeled):
    lab = labeled[labeled["label"].notna()].reset_index(drop=True)
    y = lab["label"].to_numpy()
    groups = pd.factorize(cz._norm(lab["text"]))[0]
    emb = np.random.default_rng(3).normal(size=(len(lab), 8))
    test = cz.frozen_split(labeled)[labeled["label"].notna()].to_numpy()
    feats = lambda tr, te: cz.ngram_features(lab["text"].iloc[tr], lab["text"].iloc[te], emb[tr], emb[te],
                                             emb_weight=0, char=False)
    r = cz.evaluate(lambda: LinearSVC(C=1, class_weight="balanced"), feats, y, groups,
                    np.flatnonzero(~test), np.flatnonzero(test))
    assert 0.0 <= r["test_macro_f1"] <= 1.0                        # texts name their class, so TF-IDF alone learns it


def _synthetic_workbook(tmp_path, flagged=("dos",), fixed=None):
    """A tiny synthetic review workbook (+ the batch file next to it), like `llm_labels.write_synthetic_workbook`."""
    d = pd.DataFrame({
        "Mensaje sintético": ["uno", "dos", "tres", "cuatro"],
        "Categoría objetivo": ["Empleabilidad", "Emprendimiento", cz.NONE, "Empleabilidad"],
        "Etiqueta LLM": ["Empleabilidad", "Empleabilidad", cz.NONE, "Empleabilidad"],
        "Categoría corregida": [None, None, None, fixed],
        "Comentario": None,
        "Revisar": ["sí" if t in flagged else None for t in ["uno", "dos", "tres", "cuatro"]],
        "id": [0, 1, 2, 3]})
    path = tmp_path / "syn.xlsx"
    with pd.ExcelWriter(path) as xw:
        d.to_excel(xw, sheet_name="Sinteticos", index=False)
    (tmp_path / "llm_haiku_synth").mkdir()
    pd.DataFrame({"text": d["Mensaje sintético"], "category": d["Categoría objetivo"],
                  "batch": ["b0", "b0", "b1", "b1"]}).to_csv(tmp_path / "llm_haiku_synth" / "synthetic.csv", index=False)
    return path


def test_load_synthetic_keeps_only_agreed_rows_with_their_batch(tmp_path):
    s = cz.load_synthetic(_synthetic_workbook(tmp_path))
    assert s["text"].tolist() == ["uno", "tres", "cuatro"]                    # the flagged "dos" is out
    assert s["label"].tolist() == ["Empleabilidad", cz.NONE, "Empleabilidad"]
    assert s["batch"].tolist() == ["b0", "b1", "b1"]


def test_load_synthetic_drops_a_blank_message(tmp_path):
    path = _synthetic_workbook(tmp_path)
    d = pd.read_excel(path, sheet_name="Sinteticos")
    d.loc[2, "Mensaje sintético"] = None                    # e.g. a text such as "null" that a CSV read turned into NaN
    with pd.ExcelWriter(path) as xw:
        d.to_excel(xw, sheet_name="Sinteticos", index=False)
    assert cz.load_synthetic(path)["text"].tolist() == ["uno", "cuatro"]


def test_load_synthetic_prefers_a_reviewers_correction(tmp_path):
    s = cz.load_synthetic(_synthetic_workbook(tmp_path, fixed="Riesgos de protección"))
    assert s.set_index("text").loc["cuatro", "label"] == "Riesgos de protección"


def test_load_synthetic_without_batch_file_and_missing_workbook(tmp_path):
    path = _synthetic_workbook(tmp_path)
    (tmp_path / "llm_haiku_synth" / "synthetic.csv").unlink()
    assert cz.load_synthetic(path)["batch"].isna().all()
    with pytest.raises(FileNotFoundError, match="synthreport"):
        cz.load_synthetic(tmp_path / "nope.xlsx")


def test_embeddings_with_memo_embeds_only_what_the_memo_lacks(tmp_path, monkeypatch):
    import pickle

    from sami import nlp
    calls = []
    monkeypatch.setattr(nlp, "embed_documents",
                        lambda t, batch_size=16: calls.append(list(t)) or np.full((len(t), 3), 2.0, "float32"))
    memo = tmp_path / "memo.pkl"
    memo.write_bytes(pickle.dumps({"a": np.array([1.0, 0, 0], "float32")}))
    cache = tmp_path / "emb.npz"
    e = cz.embeddings_with_memo(["a", "b", "a"], cache, memo)
    assert calls == [["b"]] and e[0, 0] == 1.0 and e[1, 0] == 2.0 and (e[0] == e[2]).all()
    cz.embeddings_with_memo(["a", "b", "a"], cache, memo)                       # cached: no new call
    assert len(calls) == 1
