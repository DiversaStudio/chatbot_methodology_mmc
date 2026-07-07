# src/mmc_nlp.py
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]


def _device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def embed_messages(messages, cache="cache/emb_msg_e5.npy") -> np.ndarray:
    p = _ROOT / cache
    if p.exists():
        emb = np.load(p)
        if emb.shape[0] == len(messages):
            return emb
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-large", device=_device())
    emb = model.encode(["query: " + m for m in messages],
                       normalize_embeddings=True, batch_size=16, show_progress_bar=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, emb)
    return emb


MMC_LABELS = {
    "legal documentation": "documentos y trámites legales (PPT, cédula, pasaporte, visa, regularización, salvoconducto)",
    "humanitarian assistance": "ayuda humanitaria (comida, dinero, arriendo, subsidios, vivienda)",
    "employment": "empleo y trabajo",
    "services": "servicios de salud, educación, EPS o SISBÉN",
    "protection": "protección, seguridad, violencia o refugio",
    "journey information": "información de ruta, viaje, retorno o frontera",
    "organization search": "búsqueda de organizaciones o dónde acudir para ayuda",
}


def zeroshot_tint(messages, cache="cache/zeroshot_labels.parquet") -> pd.DataFrame:
    p = _ROOT / cache
    if p.exists():
        cached = pd.read_parquet(p)
        if list(cached["message"]) == list(messages):
            return cached
    from transformers import pipeline
    dev = 0 if _device() == "cuda" else -1
    clf = pipeline("zero-shot-classification",
                   model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", device=dev)
    cand = list(MMC_LABELS.values())
    inv = {v: k for k, v in MMC_LABELS.items()}
    res = clf(list(messages), cand, multi_label=False,
              hypothesis_template="Este mensaje trata sobre {}.")
    res = res if isinstance(res, list) else [res]
    rows = [{"message": m, "mmc_category": inv[r["labels"][0]], "conf": float(r["scores"][0])}
            for m, r in zip(messages, res)]
    out = pd.DataFrame(rows)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p)
    return out


def emotion_label(messages, cache="cache/emotion.parquet") -> pd.DataFrame:
    p = _ROOT / cache
    if p.exists():
        cached = pd.read_parquet(p)
        if list(cached["message"]) == list(messages):
            return cached
    import sys
    sys.path.insert(0, str(_ROOT / "src"))
    import mmc_text
    run = mmc_text.load_emotion_pipeline()
    res = run(list(messages))
    out = pd.DataFrame({"message": list(messages),
                        "emotion": [r["label"] for r in res],
                        "emo_score": [float(r["score"]) for r in res]})
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p)
    return out
