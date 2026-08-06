"""run_pipeline.py itself: guards on the CLI surface that unit tests on the
sami package can't see, since the script is never imported as a module.
"""
import functools
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans


def test_run_pipeline_has_no_skip_nlp_argument():
    """Clustering IS the categorisation now, so a non-NLP run cannot produce
    a valid export — the flag must not exist, not even as dead text."""
    src = Path(__file__).resolve().parents[1] / "run_pipeline.py"
    text = src.read_text(encoding="utf-8")
    assert "--skip-nlp" not in text
    assert "skip_nlp" not in text


def test_nlp_meta_carries_the_subcluster_keys():
    """The five meta_run keys schema v6 promises. Guards against a wiring change
    that drops one silently — meta_run is the run's identity card and a missing
    key is invisible until someone asks the dashboard a question it can't answer.
    """
    import inspect
    import run_pipeline

    src = inspect.getsource(run_pipeline._nlp_tables)
    for key in ("n_subclusters", "n_parents_split", "n_provisional_subnames",
                "subcluster_min_users", "subcluster_stability_ari"):
        assert f'"{key}"' in src, f"{key} missing from nlp_meta"


# ---- _nlp_tables integration fixture -----------------------------------
#
# The test above only regexes _nlp_tables' SOURCE TEXT, so it cannot catch a
# bug in what the function actually DOES at runtime -- specifically the two
# silent-failure modes flagged in Task 7 review: passing cluster-level terms
# where sibling-EXCLUSIVE terms belong, and a sub_names dict missing an id
# sub_lab actually contains. Both are runtime data-flow bugs; a source-text
# assertion is structurally blind to them.
#
# _nlp_tables' only expensive external calls are nlp.embed_documents,
# nlp.sentiment_messages, and the gold-label CSV read -- everything else
# (clusters.k_scan, KMeans, clusters.ctfidf_terms, subclusters.subcluster_all,
# subclusters.exclusive_terms, taxonomy.resolve_names) is cheap and
# deterministic on a small synthetic matrix, so this fixture monkeypatches
# only those three plus (see note below) clusters.choose_k, and lets
# everything else run for real.
#
# Geometry: 4 macro-clusters (30 users each), placed thousands of units
# apart in dims 0-1 so KMeans trivially recovers them regardless of noise.
# `clusters.choose_k` is ALSO forced to 4 -- not one of the three calls the
# review named, but empirically necessary: with only 120 points, choose_k's
# real "largest k clearing the stability bar" rule keeps picking k=12,
# because with this few points even an over-split remains "stable enough"
# (shared macro membership dominates the ARI). At k=12 the macro groups
# fragment and there is no parent left for the subclustering pass to act on.
# Fixing k=4 lets every other real function -- k_scan, stability_curve,
# stability_ari, ctfidf_terms, subcluster_all, exclusive_terms, resolve_names
# -- run unmodified and exercise the real wiring.
#
# One of the four macro-clusters (KMeans label 0 by construction, via a
# small deterministic offset in dim 2) carries a genuine bimodal
# sub-structure; SUBCLUSTER_MIN_USERS is overridden down to 11 (from the
# production floor of 30 -- reported explicitly, per Task 7 review) so a
# 30-user parent can actually split under it. Which parent(s) end up split
# is read back from the real `subclusters.subcluster_all` output before
# building message text, rather than assumed, so the fixture stays correct
# even if more than one parent happens to clear the bar.
_MIN_USERS = 11
_PER_PARENT = 30


def _build_nlp_tables_fixture():
    """Deterministic synthetic SD + the real (parent, child) grouping it
    produces. Returns (SD, analyst, X, user_ids)."""
    rng = np.random.default_rng(12345)
    centers = [(0, 0), (10000, 0), (0, 10000), (10000, 10000)]
    rows, user_ids = [], []
    uid = 0
    half = _PER_PARENT // 2
    for pi, (cx, cy) in enumerate(centers):
        for i in range(_PER_PARENT):
            dim2 = ((3.0 if i < half else -3.0) + rng.normal(0, 0.3) if pi == 0
                    else rng.normal(0, 3.0))
            rows.append([cx + rng.normal(0, 300), cy + rng.normal(0, 300),
                         dim2, rng.normal(0, 3.0), rng.normal(0, 3.0)])
            user_ids.append(f"u{uid:03d}")  # sorts lexically == insertion order
            uid += 1
    X = np.array(rows, dtype=np.float64)

    from sami import subclusters as sub_mod

    lab = pd.Series(KMeans(n_clusters=4, n_init=10, random_state=0).fit(X).labels_,
                    index=user_ids, name="archetype")
    sub_lab, _ = sub_mod.subcluster_all(X, lab, user_ids, random_state=0,
                                        min_users=_MIN_USERS)

    # Pure alphabetic tokens only -- ctfidf's tokenizer strips digits, so a
    # numeric suffix ("parent0" vs "parent1") collapses to the same token.
    parent_words = ["parentceibo", "parentlimon", "parenttamar", "parentguaya"]
    child_words = {(p, c): f"{stem}{suffix}"
                   for p, suffix in enumerate(["alfa", "beta", "gama", "delt"])
                   for c, stem in enumerate(["childwordone", "childwordtwo"])}

    msg_rows, resp_rows = [], []
    for u in user_ids:
        parent, child = int(lab[u]), int(sub_lab[u]) % 10
        text = f"{parent_words[parent]} {parent_words[parent]} {parent_words[parent]} " \
               f"{child_words[(parent, child)]} {child_words[(parent, child)]}"
        msg_rows.append({"user_id": u, "message": text, "seq": 0,
                         "ts": pd.Timestamp("2026-01-01"), "city_canon": "Bogotá",
                         "n_msgs_user": 1})
        resp_rows.append({"user_id": u, "ts": pd.Timestamp("2026-01-01"),
                          "city_canon": "Bogotá"})
    messages = pd.DataFrame(msg_rows)
    responses = pd.DataFrame(resp_rows)

    from sami import export as export_mod
    analyst_rows = []
    for u in user_ids[:10]:
        m = messages[messages["user_id"] == u].iloc[0]
        analyst_rows.append({
            "message_id": export_mod.message_key(u, m["seq"], m["message"]),
            "label_analyst": "neutral"})
    analyst = pd.DataFrame(analyst_rows)

    from sami.facade import SamiData
    SD = SamiData(responses=responses, messages=messages, meal=pd.DataFrame(),
                  reconciliation=pd.DataFrame(), run_meta={})
    return SD, analyst, X, user_ids


def _run_nlp_tables_with_fixture(monkeypatch):
    """Run the real `run_pipeline._nlp_tables` against the synthetic fixture,
    with only the three heavy calls (+ choose_k, see the module note above)
    monkeypatched. Everything else is the genuine implementation."""
    import run_pipeline
    from sami import nlp, clusters, subclusters, progress

    SD, analyst, X, user_ids = _build_nlp_tables_fixture()

    def fake_embed(docs):
        assert len(docs) == len(user_ids)
        return X

    def fake_sentiment(messages_df, batch_size=64):
        return pd.DataFrame({"label": ["neutral"] * len(messages_df),
                             "score": [1.0] * len(messages_df)},
                            index=messages_df.index)

    def fake_read_csv(path, *a, **kw):
        assert "tone_labels_analyst" in str(path)
        return analyst

    monkeypatch.setattr(nlp, "embed_documents", fake_embed)
    monkeypatch.setattr(nlp, "sentiment_messages", fake_sentiment)
    monkeypatch.setattr(pd, "read_csv", fake_read_csv)
    monkeypatch.setattr(clusters, "choose_k", lambda *a, **kw: 4)
    monkeypatch.setattr(subclusters, "subcluster_all",
                        functools.partial(subclusters.subcluster_all,
                                          min_users=_MIN_USERS))

    pr = progress.Progress(6, enabled=False)
    return run_pipeline._nlp_tables(SD, pr)


def test_nlp_tables_subcluster_wiring(monkeypatch):
    """Actually CALLS `_nlp_tables`, unlike the source-text test above, so it
    can catch the two runtime data-flow bugs Task 7 review flagged:

    (a) `sub_names` must be total over `sub_lab`'s domain, including the
        NO_SUBCLUSTER_ID (-10) fallback bucket `build_dim_user` /
        `build_fact_message` fall back to for users with no message text.
        Dropping that explicit assignment leaves the id/name pair invisible
        rather than erroring.

    (b) The terms reaching `nlp_subcluster_terms` (and `build_dim_subcluster`)
        must be `subclusters.exclusive_terms`' output, not the raw
        `clusters.ctfidf_terms` output. Siblings of one parent share most of
        their vocabulary, so substituting the raw terms should make a
        parent-level term (shared across the whole parent, and hence across
        both its children before filtering) survive into BOTH children's
        entries -- exactly what `exclusive_terms` exists to strip.
    """
    from sami import subclusters

    tables, nlp_meta, sent, lab, dim_cluster, sub_lab, sub_names = \
        _run_nlp_tables_with_fixture(monkeypatch)

    # (a) sub_names is total over sub_lab's domain, including the sentinel.
    assert subclusters.NO_SUBCLUSTER_ID in sub_names
    for sid in sub_lab.unique():
        assert sid in sub_names, f"subcluster {sid} present in sub_lab but missing from sub_names"

    # At least one real parent must have split, or (b) below is vacuous --
    # every subcluster would be an only child and "no shared term between
    # siblings" would hold trivially regardless of exclusive_terms.
    n_children_by_parent = defaultdict(int)
    for sid in tables["nlp_subcluster_terms"]["subcluster_id"].unique():
        if sid >= 0:
            n_children_by_parent[sid // 10] += 1
    assert any(n >= 2 for n in n_children_by_parent.values()), \
        "fixture produced no split parent -- (b) cannot be exercised"

    # (b) no term appears in two different children's entries for children
    # sharing a parent.
    by_parent = defaultdict(dict)
    for sid, grp in tables["nlp_subcluster_terms"].groupby("subcluster_id"):
        if sid < 0:
            continue
        by_parent[sid // 10][sid] = set(grp["term"])
    violations = []
    for parent, children in by_parent.items():
        ids = list(children)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                shared = children[ids[i]] & children[ids[j]]
                if shared:
                    violations.append((ids[i], ids[j], shared))
    assert not violations, f"sibling children share terms after exclusive_terms: {violations}"

    # (c) meta_run's subcluster figures are real, executing wiring checks, not
    # just the source-text regex above. This fixture is known to produce a mix
    # of split and unsplit parents (some of centers[0..3] split, some don't),
    # so `split_aris` is guaranteed non-trivial: dropping the `is_split` filter
    # on run_pipeline.py:106 would let unsplit parents' `stability_ari` (nan by
    # construction) into the mean, turning `subcluster_stability_ari` into nan.
    assert isinstance(nlp_meta["subcluster_stability_ari"], float)
    assert math.isfinite(nlp_meta["subcluster_stability_ari"]), (
        "subcluster_stability_ari is not a finite float -- an unsplit parent's "
        "nan stability_ari likely leaked into the mean (run_pipeline.py:106)")

    # `n_subclusters` must equal the real count of subcluster_id >= 0 rows in
    # the dim_subcluster THIS RUN ACTUALLY BUILT (tables["dim_subcluster"]),
    # not merely be present. Dropping the `>= 0` mask on run_pipeline.py:119
    # would fold the -10 sentinel row into the count.
    dim_subcluster = tables["dim_subcluster"]
    assert nlp_meta["n_subclusters"] == int((dim_subcluster["subcluster_id"] >= 0).sum())
