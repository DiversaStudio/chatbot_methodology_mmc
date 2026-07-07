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


import re, unicodedata

_BASE_STOP = (
    "a al algo algunas algunos ante antes como con contra cual cuando de del "
    "desde donde dos el ella ellas ellos en entre era es esa ese eso esta este "
    "esto ha hasta hay la las le les lo los mas me mi mis mucho muy nada ni no "
    "nos o os para pero poco por porque que quien se sin sobre soy su sus te "
    "tener tengo ti tu tus un una uno unos y ya yo".split()
)
_COURTESY_TOKENS = (
    "hola buenas buenos dias tardes noches gracias muchas mil bendiga bendiciones "
    "amen dios saludos hi hello ok okay bien vale adios chao hasta luego favor "
    "porfavor porfa disculpa disculpe perdon le".split()
)
SPANISH_STOPWORDS = sorted(set(_BASE_STOP) | set(_COURTESY_TOKENS))


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def is_courtesy(text: str) -> bool:
    """True when a turn is only greeting/thanks/blessing words (no substantive content)."""
    folded = _fold(text)
    words = re.findall(r"[a-zñ]+", folded)
    if not words:
        return True  # emoji/punctuation only
    non_courtesy = [w for w in words if w not in _COURTESY_TOKENS]
    return len(non_courtesy) == 0
