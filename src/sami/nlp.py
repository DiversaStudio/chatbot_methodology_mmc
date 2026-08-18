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
# Spanish-native (RoBERTuito), 7-class: others, joy, sadness, anger, surprise,
# disgust, fear. A richer axis than the 3-class tone above -- added 2026-08-14,
# unvalidated (no gold set yet; see meta_run["emotion_validated"]).
EMOTION_MODEL = "pysentimiento/robertuito-emotion-analysis"
EMOTION_REVISION = "bcd6835f4d1ab1a061bd7437c9d762623c8437ad"

SENTIMENT_LABELS = ("negative", "neutral", "positive")
EMOTION_LABELS = ("others", "joy", "sadness", "anger", "surprise", "disgust", "fear")

# RoBERTuito was trained on Twitter, where an absence of strong emotion is
# rare -- so on short administrative/informational text like this corpus's,
# "others" wins argmax even when a real emotion is a close second. Below this
# margin over the runner-up, fall back to the runner-up instead of taking
# "others" at face value. Unvalidated heuristic (no gold set), same posture as
# EMOTION_MODEL itself -- see emotion_messages().
EMOTION_OTHERS_MARGIN = 0.15

# Only these runner-ups are trusted as the fallback target. A 2026-08-17 audit
# of every "others" message's runner-up on the real corpus (~4.3k dashboard-
# window messages) found "sadness"/"fear"/"anger" near-misses read as real on
# manual review (e.g. "no me alcanza para la comida" -> sadness), but "joy"
# and "surprise" did not: "joy" fires on short imperative asks ("Necesito
# asilo", "necesito alimentos") that aren't happy, just direct requests, and
# "surprise" fires on almost any "¿Cómo...?" question (50% of all "others"
# messages had it as runner-up) -- neither carries real signal here, so
# promoting them would trade a boring-but-correct "others" for a wrong label.
EMOTION_TRUSTED_FALLBACKS = frozenset({"sadness", "fear", "anger"})

# "surprise"/"disgust" are excluded even as the model's own RAW argmax, not
# just as fallback targets: a 185-message blind gold set labelled by an
# independent agent (validation/emotion_labels_agent.csv, 2026-08-17,
# kappa=0.578 against the trusted-fallback model) found 0/8 of the model's
# own confident "surprise" calls were correct -- "Cómo hago para sacar el
# pasaporte" reads as surprise to this Twitter-trained model, not a real
# emotion. "disgust" never fired once across ~9k real messages in two
# separate runs. Neither carries any reliable signal in this domain at any
# confidence, so both are dropped from the candidate set entirely before
# ranking -- see _resolve_emotion.
EMOTION_UNTRUSTED_RAW = frozenset({"surprise", "disgust"})

# Last-resort override for messages the margin rule above still leaves as
# "others": domain-specific emotional cues this Twitter-trained model doesn't
# reliably associate with the right class on short WhatsApp text. Applied only
# when the model's own (margin-adjusted) call is still "others" -- never
# overrides a confident non-"others" prediction. Case-insensitive substring
# match against normalized text, first hit wins. Curated from the corpus's own
# messages (2026-08-17); extend as new patterns turn up in nlp_voices-style
# spot checks, same maintenance posture as taxonomy.CLUSTER_NAMES.
#
# Tried dropping "no me han ayudado"/"no me ayudan"/"no me atienden" on
# 2026-08-17 after the blind gold set showed some institutional-neglect
# messages using these phrases read as "sadness" to an independent labeller,
# not "anger". Measured, not assumed: removing them cost real anger true
# positives (recall 92%->75%) without improving precision (44%->39%) --
# kappa against the gold set went 0.610->0.590. Reverted; the phrases stay.
#
# Round 2 (250-message "others"-only blind batch, 2026-08-17) found five
# recurring implicit patterns the base model structurally can't see because
# there's no emotion word to weight -- serious-diagnosis mentions, bereavement,
# displacement, explicit danger, psychosocial-support requests (see
# emotion_gold/others_deepdive_notes.md). Added the low-ambiguity ones below;
# skipped the institutional-stonewalling pattern (Pattern 3) since that's the
# same shape as the "no me han ayudado" family already measured as
# anger/sadness-ambiguous, not a safe new marker.
EMOTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("estafa", "fear"), ("temo", "fear"), ("nervios", "fear"),  # nervioso/-a
    ("corre peligro", "fear"), ("corre en peligro", "fear"),
    ("maltrata", "anger"), ("maltrato", "anger"), ("chantaje", "anger"),
    ("no me han ayudado", "anger"), ("no me ayudan", "anger"),
    ("no me atienden", "anger"),
    ("deprimid", "sadness"),  # deprimida/deprimido
    ("muy dificil", "sadness"), ("muy difícil", "sadness"),
    ("cáncer", "sadness"), ("cancer", "sadness"),
    ("fallecid", "sadness"),  # fallecido/fallecida
    ("desplazad", "sadness"),  # desplazado/desplazada
    ("apoyo psicosocial", "sadness"), ("atención psicosocial", "sadness"),
    ("dialisis", "sadness"), ("diálisis", "sadness"),
)

_WS = re.compile(r"\s+")


def cuda_usable() -> bool:
    """True only when CUDA is available *and* a device is actually visible.

    `torch.cuda.is_available()` alone is not enough: with CUDA_VISIBLE_DEVICES=""
    (or a driver/permissions problem) it can return True while `device_count()`
    is 0, and every subsequent call — `.to("cuda")`, `get_device_name(0)` —
    raises 'Invalid device id'. Checking the count keeps the CPU fallback honest.
    """
    import torch

    try:
        return torch.cuda.is_available() and torch.cuda.device_count() > 0
    except Exception:
        return False


def gpu_name() -> str | None:
    import torch

    if not cuda_usable():
        return None
    try:
        return torch.cuda.get_device_name(0)
    except Exception:
        return None


def _device() -> str:
    return "cuda" if cuda_usable() else "cpu"


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


def _resolve_emotion(probs: np.ndarray, id2label: dict, text: str) -> tuple[str, float]:
    """One row's emotion label + score: margin rule, then marker override.

    `probs` is the model's softmax over EMOTION_LABELS. See EMOTION_OTHERS_MARGIN
    and EMOTION_MARKERS above for why either step can move the label off a bare
    argmax "others".
    """
    order = np.argsort(probs)[::-1]
    ranked = [(int(i), id2label[int(i)]) for i in order
             if id2label[int(i)] not in EMOTION_UNTRUSTED_RAW]
    idx, label = ranked[0]
    if label == "others":
        second_i, second_label = ranked[1]
        if (second_label in EMOTION_TRUSTED_FALLBACKS
                and (probs[idx] - probs[second_i]) < EMOTION_OTHERS_MARGIN):
            idx, label = second_i, second_label

    if label == "others":
        text_low = text.lower()
        for marker, marker_label in EMOTION_MARKERS:
            if marker in text_low:
                return marker_label, float(probs[idx])

    return label, float(probs[idx])


def emotion_messages(messages: pd.DataFrame, batch_size: int = 64) -> pd.DataFrame:
    """Per-message emotion, index-aligned to the message spine.

    Same shape and empty-message handling as `sentiment_messages`, but a 7-way
    emotion label (EMOTION_LABELS) instead of 3-way tone. Empty messages get
    label 'others' (that model's neutral-equivalent bucket). The raw model
    argmax is adjusted by `_resolve_emotion` (others-margin rule, then a
    marker-list override) before being written -- see EMOTION_OTHERS_MARGIN /
    EMOTION_MARKERS above.
    """
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    texts = messages["message"].map(normalize_text).tolist()
    keep = [i for i, t in enumerate(texts) if t != ""]

    tok = AutoTokenizer.from_pretrained(EMOTION_MODEL, revision=EMOTION_REVISION)
    model = AutoModelForSequenceClassification.from_pretrained(
        EMOTION_MODEL, revision=EMOTION_REVISION
    )
    device = _device()
    model.to(device).eval()

    id2label = {i: model.config.id2label[i].lower() for i in range(model.config.num_labels)}
    labels = np.array(["others"] * len(texts), dtype=object)
    scores = np.full(len(texts), np.nan, dtype=float)

    # RoBERTuito's max_position_embeddings is 130 (unlike the 512-position
    # sentiment model above) -- 256 silently indexes past the position
    # embedding table and crashes deep in the forward pass, not at tokenize
    # time. 128 stays under that with room for the special tokens.
    with torch.no_grad():
        for start in range(0, len(keep), batch_size):
            idx = keep[start : start + batch_size]
            batch = [texts[i] for i in idx]
            enc = tok(batch, padding=True, truncation=True, max_length=128, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = torch.softmax(model(**enc).logits, dim=-1).cpu().numpy()
            for j, i in enumerate(idx):
                labels[i], scores[i] = _resolve_emotion(probs[j], id2label, texts[i])

    return pd.DataFrame({"label": labels, "score": scores}, index=messages.index)


def device_report() -> dict:
    """Reproducibility identity card: device, versions, pinned model revisions."""
    import torch

    return {
        "device": _device(),
        "torch": torch.__version__,
        "cuda_available": cuda_usable(),
        "gpu": gpu_name(),
        "embed_model": EMBED_MODEL,
        "embed_revision": EMBED_REVISION,
        "sentiment_model": SENTIMENT_MODEL,
        "sentiment_revision": SENTIMENT_REVISION,
        "emotion_model": EMOTION_MODEL,
        "emotion_revision": EMOTION_REVISION,
    }
