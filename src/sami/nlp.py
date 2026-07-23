"""Pinned NLP models: user-level documents, embeddings, per-message sentiment.

Every model id and revision is a module constant so no notebook ever names a
model inline. Reproducibility here rests on pinned revisions + fixed seeds +
`device_report()` rendered in the notebook, NOT on a disk cache: with the LLM
classification step out of scope, inference is a few minutes on a local GPU,
so an export-hash cache would add a stale-results failure mode and buy nothing
(NB3 design §4).
"""
from __future__ import annotations

import re
from typing import Iterable

import numpy as np
import pandas as pd

# ---- pinned models (revisions resolved 2026-07-23) ----
EMBED_MODEL = "intfloat/multilingual-e5-large"
EMBED_REVISION = "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
SENTIMENT_REVISION = "f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8"

SENTIMENT_LABELS = ("negative", "neutral", "positive")

_WS = re.compile(r"\s+")


def _device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def normalize_text(text) -> str:
    """Collapse whitespace; return '' for null. Values stay Spanish (doc 01 §5.6)."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return _WS.sub(" ", str(text)).strip()


def user_documents(messages: pd.DataFrame) -> pd.DataFrame:
    """One document per user: all of that user's messages concatenated.

    Returns `user_id`, `doc`, `n_msgs`. Users whose messages are all empty after
    normalization are dropped (counted by the caller via the row-count delta).
    Expected ~800 docs — the users-with-text figure in the P10 reconciliation.
    """
    m = messages.copy()
    m["_norm"] = m["message"].map(normalize_text)
    m = m[m["_norm"] != ""]
    docs = (
        m.groupby("user_id")
        .agg(doc=("_norm", lambda s: " ".join(s)), n_msgs=("_norm", "size"))
        .reset_index()
        .sort_values("user_id", kind="stable")
        .reset_index(drop=True)
    )
    return docs


def embed_documents(docs: Iterable[str], batch_size: int = 16) -> np.ndarray:
    """L2-normalized e5-large embeddings.

    The e5 model card requires a task prefix; user documents are treated as
    queries. Inference is deterministic (eval mode, no dropout, fixed order).
    """
    from sentence_transformers import SentenceTransformer

    texts = [f"query: {normalize_text(d)}" for d in docs]
    model = SentenceTransformer(
        EMBED_MODEL, revision=EMBED_REVISION, device=_device()
    )
    emb = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(emb, dtype=np.float32)


def sentiment_messages(messages: pd.DataFrame, batch_size: int = 64) -> pd.DataFrame:
    """Per-message sentiment, index-aligned to the message spine.

    Returns a frame indexed like `messages` with `label` in SENTIMENT_LABELS and
    `score` (max softmax probability). Empty messages get label 'neutral' and
    score NaN so the frame stays aligned rather than silently shorter.
    """
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    texts = messages["message"].map(normalize_text).tolist()
    keep = [i for i, t in enumerate(texts) if t != ""]

    tok = AutoTokenizer.from_pretrained(SENTIMENT_MODEL, revision=SENTIMENT_REVISION)
    model = AutoModelForSequenceClassification.from_pretrained(
        SENTIMENT_MODEL, revision=SENTIMENT_REVISION
    )
    device = _device()
    model.to(device).eval()

    id2label = {i: model.config.id2label[i].lower() for i in range(model.config.num_labels)}
    labels = np.array(["neutral"] * len(texts), dtype=object)
    scores = np.full(len(texts), np.nan, dtype=float)

    with torch.no_grad():
        for start in range(0, len(keep), batch_size):
            idx = keep[start : start + batch_size]
            batch = [texts[i] for i in idx]
            enc = tok(batch, padding=True, truncation=True, max_length=256, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = torch.softmax(model(**enc).logits, dim=-1).cpu().numpy()
            for j, i in enumerate(idx):
                labels[i] = id2label[int(probs[j].argmax())]
                scores[i] = float(probs[j].max())

    return pd.DataFrame({"label": labels, "score": scores}, index=messages.index)


def device_report() -> dict:
    """Reproducibility identity card: device, versions, pinned model revisions."""
    import torch

    return {
        "device": _device(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "embed_model": EMBED_MODEL,
        "embed_revision": EMBED_REVISION,
        "sentiment_model": SENTIMENT_MODEL,
        "sentiment_revision": SENTIMENT_REVISION,
    }
