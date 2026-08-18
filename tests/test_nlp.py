import numpy as np
import pandas as pd
import pytest

from sami import nlp


@pytest.fixture
def spine():
    return pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2", "u3", "u4"],
            "message": ["hola  necesito   pasaporte", "y la visa", "busco empleo", "", None],
        }
    )


def test_normalize_text_collapses_whitespace_and_nulls():
    assert nlp.normalize_text("hola   mundo\n\t ") == "hola mundo"
    assert nlp.normalize_text(None) == ""
    assert nlp.normalize_text(float("nan")) == ""


def test_user_documents_grain_and_empty_drop(spine):
    docs = nlp.user_documents(spine)
    assert list(docs.columns) == ["user_id", "doc", "n_msgs"]
    assert set(docs["user_id"]) == {"u1", "u2"}      # u3/u4 have no usable text
    assert docs.loc[docs.user_id == "u1", "doc"].iat[0] == "hola necesito pasaporte y la visa"
    assert docs.loc[docs.user_id == "u1", "n_msgs"].iat[0] == 2
    assert docs["n_msgs"].sum() == 3                 # non-empty messages only


def test_user_documents_is_one_row_per_user(spine):
    docs = nlp.user_documents(spine)
    assert docs["user_id"].is_unique


def test_device_report_pins_revisions():
    rep = nlp.device_report()
    assert rep["embed_model"] == nlp.EMBED_MODEL
    assert len(rep["embed_revision"]) == 40        # a real commit sha, not a tag
    assert len(rep["sentiment_revision"]) == 40
    assert rep["device"] in {"cuda", "cpu"}


@pytest.mark.slow
def test_embeddings_are_l2_normalized():
    emb = nlp.embed_documents(["necesito el pasaporte", "busco trabajo"])
    assert emb.shape[0] == 2
    assert np.allclose(np.linalg.norm(emb, axis=1), 1.0, atol=1e-4)


@pytest.mark.slow
def test_sentiment_is_index_aligned_with_closed_label_set(spine):
    sent = nlp.sentiment_messages(spine)
    assert list(sent.index) == list(spine.index)     # empty rows kept, not dropped
    assert set(sent["label"]) <= set(nlp.SENTIMENT_LABELS)
    assert sent.loc[3:4, "score"].isna().all()       # empty messages -> NaN score


def _probs(**by_label):
    """A probs array in EMOTION_LABELS order, zero-filled for unnamed labels."""
    p = np.zeros(len(nlp.EMOTION_LABELS))
    for label, val in by_label.items():
        p[nlp.EMOTION_LABELS.index(label)] = val
    return p


def test_resolve_emotion_keeps_a_confident_others():
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(others=0.9, sadness=0.1)
    label, score = nlp._resolve_emotion(probs, id2label, "cualquier texto")
    assert label == "others"
    assert score == pytest.approx(0.9)


def test_resolve_emotion_falls_back_within_margin():
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(others=0.5, sadness=0.4)      # margin 0.1 < EMOTION_OTHERS_MARGIN
    label, score = nlp._resolve_emotion(probs, id2label, "cualquier texto")
    assert label == "sadness"
    assert score == pytest.approx(0.4)


def test_resolve_emotion_marker_overrides_a_close_others():
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(others=0.9, joy=0.1)          # margin too wide for the fallback rule
    label, _ = nlp._resolve_emotion(probs, id2label, "temo que sea una estafa")
    assert label == "fear"


def test_resolve_emotion_marker_is_case_insensitive():
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(others=0.9, joy=0.1)
    label, _ = nlp._resolve_emotion(probs, id2label, "Mi esposo me MALTRATA")
    assert label == "anger"


def test_resolve_emotion_never_overrides_a_non_others_call():
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(joy=0.6, others=0.35)
    label, _ = nlp._resolve_emotion(probs, id2label, "temo que sea una estafa")
    assert label == "joy"


@pytest.mark.parametrize("untrusted_label", ["joy", "surprise", "disgust"])
def test_resolve_emotion_does_not_fall_back_to_untrusted_labels(untrusted_label):
    """joy/surprise runner-ups were audited against the real corpus and found
    to be noise (joy fires on plain "necesito X" asks, surprise on any
    question) -- only sadness/fear/anger are trusted fallback targets."""
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(others=0.5, **{untrusted_label: 0.4})  # well within margin
    label, score = nlp._resolve_emotion(probs, id2label, "cualquier texto")
    assert label == "others"
    assert score == pytest.approx(0.5)


@pytest.mark.parametrize("untrusted_label", ["surprise", "disgust"])
def test_resolve_emotion_never_returns_untrusted_raw_argmax(untrusted_label):
    """A 185-message blind gold set found 0/8 of the model's own confident
    "surprise" calls correct, and "disgust" never fired once across ~9k real
    messages -- both are dropped even as the model's own top pick, falling
    through to whatever the next-ranked trusted label is."""
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(**{untrusted_label: 0.9}, joy=0.05)
    label, score = nlp._resolve_emotion(probs, id2label, "cualquier texto")
    assert label == "joy"
    assert score == pytest.approx(0.05)


def test_resolve_emotion_untrusted_raw_falls_through_to_others_margin_rule():
    """When the next-ranked trusted label after dropping surprise/disgust is
    "others", the usual margin+marker logic still applies on top."""
    id2label = dict(enumerate(nlp.EMOTION_LABELS))
    probs = _probs(surprise=0.5, others=0.45, sadness=0.40)
    label, _ = nlp._resolve_emotion(probs, id2label, "cualquier texto")
    assert label == "sadness"  # others(0.45) vs sadness(0.40): within margin
