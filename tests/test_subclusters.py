import numpy as np
import pandas as pd
import pytest

from sami import subclusters


def _blobs(sizes, dim=8, spread=0.15, seed=0):
    """Well-separated gaussian blobs, one per entry in `sizes`."""
    rng = np.random.default_rng(seed)
    parts = []
    for i, n in enumerate(sizes):
        centre = np.zeros(dim)
        centre[i % dim] = 10.0 * (1 + i)
        parts.append(centre + spread * rng.standard_normal((n, dim)))
    return np.vstack(parts)


def test_subcluster_id_is_composite():
    assert subclusters.subcluster_id(3, 1) == 31
    assert subclusters.subcluster_id(0, 2) == 2
    assert subclusters.subcluster_id(-1, 0) == subclusters.NO_SUBCLUSTER_ID


def test_child_index_must_fit_the_composite():
    with pytest.raises(ValueError):
        subclusters.subcluster_id(3, 10)


def test_parent_below_eligibility_floor_is_not_split():
    X = _blobs([25, 25])          # 50 users, floor is 2 * 30 = 60
    labels, meta = subclusters.split_parent(X)
    assert labels is None
    assert meta["n_users"] == 50
    assert meta["k"] is None


def test_parent_splits_when_every_child_clears_the_floor():
    # 70 users: clears the k=2 floor (2 * 30 = 60) but a k=3 split is excluded
    # structurally -- 70 < 3 * 30 = 90, so k=3/4 never even reach clustering.
    # k=2 is the only candidate in range, by construction, not by chance.
    X = _blobs([35, 35])
    labels, meta = subclusters.split_parent(X)
    assert labels is not None
    assert meta["k"] == 2
    sizes = np.bincount(labels)
    assert sizes.min() >= subclusters.SUBCLUSTER_MIN_USERS


def test_parent_is_not_split_when_a_child_would_be_too_small():
    # 120 users, but the true structure is 115 + 5: no k in range can produce
    # two children that both clear 30 without cutting a real blob in half.
    X = _blobs([115, 5], spread=0.05)
    labels, meta = subclusters.split_parent(X)
    assert labels is None


def test_split_is_deterministic():
    X = _blobs([90, 90])
    a, _ = subclusters.split_parent(X, random_state=0)
    b, _ = subclusters.split_parent(X, random_state=0)
    assert np.array_equal(a, b)


def test_subcluster_all_covers_every_user_and_ranks_by_size():
    X = np.vstack([_blobs([100, 40]), _blobs([50], seed=5) + 100.0])
    user_ids = [f"u{i}" for i in range(X.shape[0])]
    lab = pd.Series([0] * 140 + [1] * 50, index=user_ids)

    sub, meta = subclusters.subcluster_all(X, lab, user_ids)

    assert len(sub) == len(user_ids)
    assert sub.notna().all()
    assert sub.dtype == np.int64
    # parent 0 splits (100 + 40, both over 30); parent 1 has 50 users, below the
    # 2 * 30 eligibility floor -> unsplit, child 0
    assert meta[0]["is_split"] is True
    assert meta[1]["is_split"] is False
    assert set(sub[lab == 1]) == {subclusters.subcluster_id(1, 0)}
    # child index 0 is the LARGEST child of parent 0
    counts = sub[lab == 0].value_counts()
    assert counts.idxmax() == subclusters.subcluster_id(0, 0)


def test_unsplit_parent_still_gets_a_child_zero():
    X = _blobs([40])
    user_ids = [f"u{i}" for i in range(40)]
    lab = pd.Series([2] * 40, index=user_ids)
    sub, meta = subclusters.subcluster_all(X, lab, user_ids)
    assert meta[2]["is_split"] is False
    assert set(sub) == {subclusters.subcluster_id(2, 0)}


def test_no_text_users_get_the_no_subcluster_bucket():
    X = _blobs([70])
    user_ids = [f"u{i}" for i in range(70)]
    lab = pd.Series([-1] * 70, index=user_ids)
    sub, meta = subclusters.subcluster_all(X, lab, user_ids)
    assert set(sub) == {subclusters.NO_SUBCLUSTER_ID}
    assert -1 not in meta


def test_exclusive_terms_drops_shared_vocabulary():
    terms = {
        0: pd.Series({"visa": 0.9, "pasaporte": 0.5, "cita": 0.2}),
        1: pd.Series({"visa": 0.8, "arriendo": 0.4}),
    }
    ex = subclusters.exclusive_terms(terms)
    assert "visa" not in ex[0].index
    assert "pasaporte" in ex[0].index
    assert "arriendo" in ex[1].index


def test_exclusive_terms_falls_back_when_nothing_is_exclusive():
    terms = {0: pd.Series({"visa": 0.9}), 1: pd.Series({"visa": 0.8})}
    ex = subclusters.exclusive_terms(terms)
    assert list(ex[0].index) == ["visa"]
    assert list(ex[1].index) == ["visa"]
