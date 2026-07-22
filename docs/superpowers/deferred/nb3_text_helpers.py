# Deferred from mmc_text.py for the NB3 spec — do not import yet.
from __future__ import annotations
import numpy as np


def _cosine_consecutive(embeddings: np.ndarray) -> np.ndarray:
    emb = np.asarray(embeddings, dtype="float64")
    if emb.shape[0] < 2:
        return np.array([])
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = emb / norms
    return np.sum(unit[:-1] * unit[1:], axis=1)


def max_consecutive_similarity(embeddings: np.ndarray) -> float:
    sims = _cosine_consecutive(embeddings)
    return float(sims.max()) if sims.size else 0.0


def count_reformulations(embeddings: np.ndarray, threshold: float = 0.75) -> int:
    sims = _cosine_consecutive(embeddings)
    return int((sims >= threshold).sum())


def load_emotion_pipeline(model_id: str = "pysentimiento/robertuito-emotion-analysis"):
    """Return f(texts) -> list[{'label','score'}] using a 7-class Spanish emotion model."""
    from transformers import pipeline
    import torch
    dev = 0 if torch.cuda.is_available() else -1
    pipe = pipeline("text-classification", model=model_id, device=dev, top_k=1, truncation=True)

    def _run(texts):
        if isinstance(texts, str):
            texts = [texts]
        res = pipe([t[:256] for t in texts])
        # top_k=1 → each item is a list with one dict
        return [r[0] if isinstance(r, list) else r for r in res]

    return _run
