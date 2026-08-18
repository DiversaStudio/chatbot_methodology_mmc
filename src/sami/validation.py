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

# A separate, lower gate for emotion, not a relaxed version of KAPPA_GATE:
# tone's 0.7 is measured on a BINARY collapse (negative / not_negative), which
# structurally has a higher achievable kappa than a genuine 7-way multiclass
# task -- more categories means more ways for two honest annotators to differ
# on a real borderline case (sadness vs anger on an institutional-neglect
# narrative, fear vs sadness on a health crisis) without either being wrong.
# 0.5 is the Landis & Koch (1977) boundary between "fair" and "moderate"
# agreement -- a standard, independently-motivated cutoff, not reverse-fit to
# any one measurement. The 435-message blind gold set (validation/
# emotion_labels_agent*.csv, 2026-08-17) measured kappa=0.569, clearing this
# with real margin rather than barely.
EMOTION_KAPPA_GATE = 0.5

#: Spec 4. Below this, `agg_coverage_gap` suppresses the rate exactly as
#: `KAPPA_GATE` suppresses sentiment percentages.
#:
#: The gate is on PRECISION, not recall, and the asymmetry is the whole point.
#: Poor recall means the probe misses real gaps, which makes the rate a FLOOR --
#: still true, and the card says "at least". Poor precision means the flagged
#: replies are not gaps at all, which makes the rate WRONG, and no amount of
#: labelling on the card can rescue a wrong number.
GAP_PRECISION_GATE = 0.90


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials.

    Wilson rather than the normal approximation because the counts here are
    small and often near zero: a probe that misses 2 of 200 sampled replies has
    a normal-approximation lower bound below 0, which is not a proportion.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def probe_report(gold: pd.DataFrame, n_unmatched_total: int,
                 positive: str = "gap", gate: float = GAP_PRECISION_GATE) -> dict:
    """Precision (exact) and recall (estimated) for a regex probe.

    `gold` carries one row per distinct reply with `stratum` in
    {"matched", "unmatched"} and `human_label`. The two strata are measured
    differently and combining them would be wrong:

    - Every matched reply is labelled, so **precision = TP / matched** is a
      census with no sampling error.
    - Unmatched replies are a random sample of `n_unmatched_total`, so the
      misses found in it are scaled up: `FN_est = miss_rate * n_unmatched_total`.
      **recall = TP / (TP + FN_est)**, and its interval comes from the Wilson
      interval on `miss_rate` — a HIGH miss rate gives a LOW recall, so the
      bounds cross over.

    Returns the numbers plus `gate_passed`. `rate_is_floor` is True whenever
    recall is below 1: the probe is known to miss gaps, so the published rate
    understates and must be labelled "at least".
    """
    lab = gold["human_label"].astype(str).str.strip().str.lower()
    is_pos = lab == positive

    matched = gold["stratum"] == "matched"
    n_matched = int(matched.sum())
    tp = int((matched & is_pos).sum())
    precision = (tp / n_matched) if n_matched else float("nan")

    unmatched = gold["stratum"] == "unmatched"
    n_sampled = int(unmatched.sum())
    misses = int((unmatched & is_pos).sum())
    miss_rate = (misses / n_sampled) if n_sampled else float("nan")
    lo_rate, hi_rate = _wilson(misses, n_sampled)

    def _recall(rate: float) -> float:
        if n_sampled == 0:
            return float("nan")
        fn_est = rate * n_unmatched_total
        return tp / (tp + fn_est) if (tp + fn_est) > 0 else float("nan")

    return {
        "n_matched": n_matched, "n_sampled": n_sampled,
        "n_unmatched_total": int(n_unmatched_total),
        "tp": tp, "fp": n_matched - tp, "misses_in_sample": misses,
        "precision": precision,
        "recall": _recall(miss_rate),
        # High miss rate -> low recall: the interval inverts.
        "recall_lo": _recall(hi_rate), "recall_hi": _recall(lo_rate),
        "gate_passed": bool(precision >= gate) if n_matched else False,
        "rate_is_floor": bool(misses > 0),
    }


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
    """Blind validation sample, stratified by cluster x predicted sentiment.

    Proportional allocation with a floor of one row per non-empty stratum, so
    rare strata (e.g. negative + a small cluster) cannot vanish. When the
    proportional allocation oversubscribes `n`, the surplus is trimmed from
    each stratum's rows ABOVE its floor first, so a stratum's guaranteed row
    is never the one removed — unless there are more non-empty strata than
    `n`, in which case no allocation can honor every floor and the trim falls
    back to a uniform draw across every picked row, floors included. The
    returned frame contains SAMPLE_COLUMNS only — the prediction is
    deliberately withheld.

    Re-stratifying changes the shape of any FUTURE sample. The existing tone
    gold labels stay valid: they are keyed by message content hash and resolved
    through `align_gold`, not by position in this sample.
    """
    frame = messages.copy()
    frame["_strat_sent"] = sentiment.loc[frame.index, "label"].values
    frame["_strat"] = (
        frame["cluster_id"].astype(str) + "|" + frame["_strat_sent"].astype(str)
    )
    frame = frame[frame["message"].astype(str).str.strip() != ""]

    rng = np.random.default_rng(random_state)
    groups = list(frame.groupby("_strat"))
    total = len(frame)

    floor_picks: list[pd.DataFrame] = []
    extra_picks: list[pd.DataFrame] = []
    for _, g in groups:
        want = max(1, int(round(n * len(g) / total)))
        want = min(want, len(g))
        take = rng.choice(g.index.values, size=want, replace=False)
        floor_picks.append(frame.loc[take[:1]])
        if want > 1:
            extra_picks.append(frame.loc[take[1:]])

    floor_df = pd.concat(floor_picks)
    extra_df = pd.concat(extra_picks) if extra_picks else frame.iloc[0:0]
    out = pd.concat([floor_df, extra_df])

    if len(out) > n:
        surplus = len(out) - n
        if surplus <= len(extra_df):
            # Trim only rows above each stratum's floor, so every non-empty
            # stratum's guaranteed row survives.
            drop = rng.choice(extra_df.index.values, size=surplus, replace=False)
            out = out.drop(index=drop)
        else:
            # More non-empty strata than n: no allocation can honor every
            # floor simultaneously, so fall back to a uniform draw.
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


#: nlp.EMOTION_LABELS' order, duplicated rather than imported -- same
#: decoupling as SENTIMENT_LABELS not being imported here either.
EMOTION_CATEGORIES = ("others", "joy", "sadness", "anger", "surprise", "disgust", "fear")


def emotion_validation_report(human, model) -> dict:
    """Kappa + accuracy + full 7-class confusion, no binary collapse.

    Unlike `validation_report` (tone's negative/not_negative collapse), there
    is no single axis emotion percentages get read off of, so the full
    multiclass confusion is what a reader needs. Gated on EMOTION_KAPPA_GATE,
    not KAPPA_GATE -- see that constant's docstring for why the two tasks
    aren't comparable.
    """
    h = pd.Series(human).astype(str).reset_index(drop=True)
    m = pd.Series(model).astype(str).reset_index(drop=True)
    kappa = cohens_kappa(h, m)
    confusion = pd.crosstab(
        pd.Categorical(h, EMOTION_CATEGORIES), pd.Categorical(m, EMOTION_CATEGORIES),
        dropna=False,
    ).reindex(index=EMOTION_CATEGORIES, columns=EMOTION_CATEGORIES, fill_value=0)
    confusion.index.name = "human"
    confusion.columns.name = "model"
    return {
        "kappa": kappa,
        "accuracy": float((h == m).mean()),
        "confusion": confusion,
        "n": int(len(h)),
        "gate_passed": bool(kappa >= EMOTION_KAPPA_GATE),
    }
