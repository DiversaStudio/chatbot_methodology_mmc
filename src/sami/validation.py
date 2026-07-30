"""Tone validation protocol: blind stratified sample, Cohen's kappa, gate.

The protocol must survive a reviewer asking "who labelled this, and did they
peek?". `stratified_sample` therefore refuses to emit the model prediction:
a labeller who sees model output produces a kappa that measures anchoring, not
agreement (NB3 design §5).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KAPPA_GATE = 0.7  # doc 02 §6.4: below this, percentages are suppressed
SAMPLE_COLUMNS = ["message_id", "user_id", "message"]


class GoldLabelError(Exception):
    """Gold tone labels cannot be aligned to the current message spine."""


def align_gold(gold_ids, messages: pd.DataFrame, sentiment: pd.DataFrame) -> pd.Series:
    """Model labels for `gold_ids`, matched by message_id — never by position.

    The caller used to do `sentiment.loc[gold["message_id"], "label"]`. Because
    `sentiment` is aligned POSITIONALLY to the spine, and the gold file was
    written when `message_id` was still a row number, that expression silently
    looked up rows 20, 25, … of whatever the spine happens to hold today and
    compared an analyst's judgement of one message against the model's judgement
    of an unrelated one. It produced a plausible-looking kappa from noise
    (κ = -0.075 on the v2 corpus, versus 0.604 when the positions still lined
    up). Nothing errored, because integer row labels always resolve.

    So this refuses to guess: ids are resolved against the content-hash
    `message_id`, and anything unresolvable raises rather than degrading the
    measurement. A kappa is a claim about a model; it must not be computable
    from mismatched rows.
    """
    from . import export  # local import: export imports validation-adjacent modules

    ids = pd.Series(list(gold_ids)).astype(str)
    spine = pd.Series(
        [export.message_key(u, s, m) for u, s, m in
         zip(messages["user_id"], messages["seq"], messages["message"])],
        index=messages.index, name="message_id")

    if spine.duplicated().any():
        raise GoldLabelError(
            "the message spine contains duplicate message_ids; the gold join "
            "would be ambiguous. Investigate export.message_key before validating tone.")

    pos = pd.Series(range(len(spine)), index=spine.values)
    unknown = ids[~ids.isin(pos.index)]
    if len(unknown):
        raise GoldLabelError(
            f"{len(unknown)} of {len(ids)} gold tone labels do not match any "
            f"message in the current spine (first: {unknown.iloc[0]!r}).\n"
            "  why:  the gold file is keyed on message_id. Old files are keyed on "
            "the pre-migration ROW NUMBER, which is not a message identity — "
            "re-keying them by position would measure noise.\n"
            "  fix:  re-key the gold labels onto the content-hash message_id by "
            "matching on message text (validation/tone_gold_labels.csv carries the "
            "text), dropping rows whose text is not unique in the corpus. Then "
            "re-run. Never fall back to positional alignment.")

    return pd.Series(
        sentiment["label"].to_numpy()[pos.loc[ids.values].to_numpy()],
        index=ids.values, name="label")


def binarize(labels) -> pd.Series:
    """Collapse three-class sentiment to the negative / not-negative axis doc 02 gates on."""
    s = pd.Series(labels).astype(str).str.lower()
    return s.where(s == "negative", "not_negative")


def stratified_sample(
    messages: pd.DataFrame,
    sentiment: pd.DataFrame,
    n: int = 200,
    random_state: int = 0,
) -> pd.DataFrame:
    """Blind validation sample, stratified by category x predicted sentiment.

    Proportional allocation with a floor of one row per non-empty stratum, so
    rare strata (e.g. negative + protection) cannot vanish. The returned frame
    contains SAMPLE_COLUMNS only — the prediction is deliberately withheld.
    """
    frame = messages.copy()
    frame["_strat_sent"] = sentiment.loc[frame.index, "label"].values
    frame["_strat"] = (
        frame["dominant_category"].astype(str) + "|" + frame["_strat_sent"].astype(str)
    )
    frame = frame[frame["message"].astype(str).str.strip() != ""]

    rng = np.random.default_rng(random_state)
    groups = list(frame.groupby("_strat"))
    total = len(frame)

    picks: list[pd.DataFrame] = []
    for _, g in groups:
        want = max(1, int(round(n * len(g) / total)))
        want = min(want, len(g))
        take = rng.choice(g.index.values, size=want, replace=False)
        picks.append(frame.loc[take])

    out = pd.concat(picks)
    if len(out) > n:  # trim deterministically, keeping stratum coverage
        keep = rng.choice(out.index.values, size=n, replace=False)
        out = out.loc[keep]

    out = out.sort_index()
    out = out.assign(message_id=out.index.astype(int))
    return out[SAMPLE_COLUMNS].reset_index(drop=True)


def cohens_kappa(a, b) -> float:
    """Cohen's kappa between two label sequences over their shared label set."""
    a = pd.Series(a).astype(str).reset_index(drop=True)
    b = pd.Series(b).astype(str).reset_index(drop=True)
    if len(a) != len(b):
        raise ValueError(f"label sequences differ in length: {len(a)} vs {len(b)}")
    cats = sorted(set(a) | set(b))
    ct = pd.crosstab(pd.Categorical(a, cats), pd.Categorical(b, cats), dropna=False)
    ct = ct.reindex(index=cats, columns=cats, fill_value=0).to_numpy(dtype=float)
    n = ct.sum()
    if n == 0:
        return float("nan")
    p_obs = np.trace(ct) / n
    p_exp = float((ct.sum(axis=0) * ct.sum(axis=1)).sum()) / (n * n)
    if np.isclose(p_exp, 1.0):
        return 1.0 if np.isclose(p_obs, 1.0) else float("nan")
    return float((p_obs - p_exp) / (1 - p_exp))


def validation_report(human, model) -> dict:
    """Kappa + accuracy + confusion on the binary negative / not-negative collapse.

    `gate_passed` is doc 02 §6.4's bar. When it is False the notebook must
    suppress every sentiment percentage and report tone directionally.
    """
    h = binarize(human).reset_index(drop=True)
    m = binarize(model).reset_index(drop=True)
    kappa = cohens_kappa(h, m)
    cats = ["negative", "not_negative"]
    confusion = pd.crosstab(
        pd.Categorical(h, cats), pd.Categorical(m, cats), dropna=False
    ).reindex(index=cats, columns=cats, fill_value=0)
    confusion.index.name = "human"
    confusion.columns.name = "model"
    return {
        "kappa": kappa,
        "accuracy": float((h == m).mean()),
        "confusion": confusion,
        "n": int(len(h)),
        "gate_passed": bool(kappa >= KAPPA_GATE),
    }
