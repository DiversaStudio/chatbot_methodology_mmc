"""Message splitting and reformulation-similarity helpers."""
from __future__ import annotations
import numpy as np


def split_messages(blob) -> list[str]:
    if blob is None or (isinstance(blob, float)):
        return []
    parts = [p.strip() for p in str(blob).split("\n")]
    return [p for p in parts if p and p.lower() != "undefined"]


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
