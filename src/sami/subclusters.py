"""Second-level clustering: subcategories inside each discovered cluster.

The discovered clusters (`clusters.py`) are the pipeline's top-level
categorisation axis. This module splits each of them again so the dashboard can
offer a category -> subcategory drill-down.

Nothing here invents a subcategory the data does not support. A parent is split
only when some k exists whose EVERY child clears `SUBCLUSTER_MIN_USERS` at
acceptable stability; a parent that fails that test is reported unsplit rather
than forced apart. Children are less stable across refreshes than parents --
smaller n, and the k choice re-runs per parent -- so `subcluster_all` returns
the per-parent stability alongside the labels and `run_pipeline` surfaces it in
`meta_run`.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from . import clusters

# Minimum users in a subcategory.
#
# NOT a purely statistical knob. The dashboard is gaining nationality, city,
# gender, children-present and destination filters; a subcategory of a dozen
# users crossed with three of those is potentially re-identifying, and the
# export is pseudonymised on the understanding that no cell gets that small.
# Lowering this is a privacy decision, not a tuning decision.
SUBCLUSTER_MIN_USERS = 30

# Candidate child counts. Capped at 4 because `theme.subcluster_colors` cannot
# keep more than four tints of one hue apart.
SUB_K_RANGE = range(2, 5)

# The subcategory of users with no conversation text, mirroring
# `export.NO_CLUSTER_ID` / `NO_CLUSTER_NAME` one level down.
NO_SUBCLUSTER_ID = -10
NO_SUBCLUSTER_NAME = "No conversation text"

# Bootstrap resamples for the per-parent stability check. Lower than the parent
# pass's 50 because this runs once per parent, not once per run.
_STABILITY_BOOT = 20


def subcluster_id(cluster_id: int, child_index: int) -> int:
    """Composite, RUN-SCOPED id: parent 3, child 1 -> 31.

    Parent ids are already an artefact of one clustering run, so an id built on
    one inherits that. Nothing may key a colour, a name or a report object on
    this value -- `dim_subcluster[display_order]` and `[color_hex]` are the
    stable handles.
    """
    if int(cluster_id) < 0:
        return NO_SUBCLUSTER_ID
    if not 0 <= int(child_index) <= 9:
        raise ValueError(
            f"child_index {child_index} does not fit the cluster_id * 10 + child "
            "composite. SUB_K_RANGE caps children at 4; a caller reaching 10 has "
            "changed the id scheme without changing this function.")
    return int(cluster_id) * 10 + int(child_index)


def split_parent(X: np.ndarray, *, min_users: int = SUBCLUSTER_MIN_USERS,
                 k_range=SUB_K_RANGE, random_state: int = 0):
    """Sub-cluster one parent's user embeddings.

    Returns `(labels, meta)`. `labels` is None when the parent must not be
    split -- too few users, or no k whose children all clear `min_users` at
    acceptable stability. `meta` always carries `n_users`, `k` and
    `stability_ari`.

    Among qualifying k the LARGEST wins: maximal resolution subject to
    stability, the same rule `clusters.choose_k` applies one level up.
    """
    n = int(X.shape[0])
    meta: dict = {"n_users": n, "k": None, "stability_ari": float("nan")}
    if n < 2 * min_users:
        return None, meta

    best: tuple[int, np.ndarray, float] | None = None
    for k in k_range:
        if n < k * min_users:
            continue
        labels = KMeans(n_clusters=k, n_init=10,
                        random_state=random_state).fit(X).labels_
        if np.bincount(labels, minlength=k).min() < min_users:
            continue
        stab = clusters.stability_ari(X, k, n_boot=_STABILITY_BOOT,
                                      random_state=random_state)
        if not stab["stable"]:
            continue
        if best is None or k > best[0]:
            best = (int(k), labels, float(stab["mean_ari"]))

    if best is None:
        return None, meta
    k, labels, ari = best
    meta["k"] = k
    meta["stability_ari"] = round(ari, 3)
    return labels, meta


def subcluster_all(X: np.ndarray, lab: pd.Series, user_ids, *,
                   min_users: int = SUBCLUSTER_MIN_USERS, k_range=SUB_K_RANGE,
                   random_state: int = 0):
    """Sub-cluster every real parent.

    `X` is the user embedding matrix, `user_ids` its row labels and `lab` the
    parent assignment (Series indexed by user_id -> cluster_id) -- exactly the
    three objects `run_pipeline._nlp_tables` already builds.

    Returns `(sub_lab, meta_by_parent)`. `sub_lab` is a Series indexed by
    user_id -> subcluster_id covering every row of X, never null: an unsplit
    parent's users all take child index 0, so a drill-down always has one level
    below the category. `meta_by_parent` has one entry per REAL parent (the -1
    bucket is absent -- it is never split).
    """
    user_ids = list(user_ids)
    parent = pd.Series(lab).reindex(user_ids)
    sub = pd.Series(NO_SUBCLUSTER_ID, index=pd.Index(user_ids, name="user_id"),
                    dtype="int64")
    meta: dict[int, dict] = {}

    real = sorted({int(c) for c in parent.dropna().unique() if int(c) >= 0})
    for cid in real:
        rows = np.flatnonzero(parent.values == cid)
        labels, m = split_parent(X[rows], min_users=min_users, k_range=k_range,
                                 random_state=random_state)
        m["is_split"] = labels is not None
        meta[cid] = m
        if labels is None:
            sub.iloc[rows] = subcluster_id(cid, 0)
            continue
        # Child index by SIZE RANK, so index 0 is the largest child and the
        # tint ramp hands it the parent's own colour. Ties break on the KMeans
        # label so the assignment is deterministic.
        order = [int(l) for l, _ in sorted(Counter(labels.tolist()).items(),
                                           key=lambda kv: (-kv[1], kv[0]))]
        rank = {l: i for i, l in enumerate(order)}
        sub.iloc[rows] = [subcluster_id(cid, rank[int(l)]) for l in labels]

    return sub.astype("int64"), meta


def exclusive_terms(terms: dict[int, pd.Series]) -> dict[int, pd.Series]:
    """Drop terms a sibling also ranks.

    Siblings of one parent share most of their vocabulary, so matching a curated
    marker against raw top terms makes every child resolve to the same name.
    Keeping only the terms unique to a child is what makes the marker mechanism
    discriminate one level down.

    A child left with nothing exclusive keeps its full term list -- an empty
    term list would auto-name it "Cluster N · " and lose the fallback quote
    machinery in `export.build_nlp_voices`.
    """
    seen: Counter = Counter()
    for s in terms.values():
        seen.update(set(s.index))
    out: dict[int, pd.Series] = {}
    for cid, s in terms.items():
        keep = s[[t for t in s.index if seen[t] == 1]]
        out[cid] = keep if len(keep) else s
    return out
