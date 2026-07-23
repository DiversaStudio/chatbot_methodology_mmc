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
