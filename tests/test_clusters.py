import numpy as np
import pandas as pd
import pytest

from sami import clusters


@pytest.fixture
def blobs():
    """Four well-separated blobs: the known-stable case."""
    from sklearn.datasets import make_blobs

    X, y = make_blobs(n_samples=240, centers=4, cluster_std=0.35,
                      n_features=8, random_state=0)
    return X.astype(np.float32), y


@pytest.fixture
def cloud():
    """Structureless uniform cloud: the known-unstable case."""
    rng = np.random.default_rng(0)
    return rng.random((240, 8)).astype(np.float32)


def test_k_scan_one_row_per_k_with_finite_metrics(blobs):
    X, _ = blobs
    scan = clusters.k_scan(X, k_range=range(2, 7))
    assert list(scan.index) == [2, 3, 4, 5, 6]
    assert np.isfinite(scan[["silhouette", "davies_bouldin"]].to_numpy()).all()


def test_choose_k_finds_the_true_k(blobs):
    X, _ = blobs
    assert clusters.choose_k(clusters.k_scan(X, k_range=range(2, 8))) == 4


def test_choose_k_breaks_ties_on_davies_bouldin():
    scan = pd.DataFrame(
        {"silhouette": [0.5, 0.5, 0.3], "davies_bouldin": [1.2, 0.4, 0.1]},
        index=pd.Index([4, 5, 6], name="k"),
    )
    assert clusters.choose_k(scan) == 5   # same silhouette, lower DB wins


def test_stability_high_on_real_structure(blobs):
    X, _ = blobs
    res = clusters.stability_ari(X, k=4, n_boot=12, random_state=0)
    assert res["mean_ari"] > 0.9
    assert res["stable"] is True
    assert res["n_pairs"] == 12 * 11 // 2


def test_stability_low_on_structureless_cloud(cloud):
    res = clusters.stability_ari(cloud, k=6, n_boot=12, random_state=0)
    assert res["mean_ari"] < clusters.STABILITY_BAR
    assert res["stable"] is False


def test_stability_is_deterministic(blobs):
    X, _ = blobs
    a = clusters.stability_ari(X, k=4, n_boot=8, random_state=0)
    b = clusters.stability_ari(X, k=4, n_boot=8, random_state=0)
    assert a == b


def test_ctfidf_prefers_distinctive_over_globally_frequent():
    # "gracias" is in every doc (should score ~0); each cluster has its own marker
    docs = (
        [f"gracias necesito pasaporte tramite documento {i}" for i in range(5)]
        + [f"gracias busco empleo trabajo vacante {i}" for i in range(5)]
    )
    labels = [0] * 5 + [1] * 5
    terms = clusters.ctfidf_terms(docs, labels, top_n=5)
    assert set(terms) == {0, 1}
    assert "pasaporte" in terms[0].index
    assert "empleo" in terms[1].index
    # the universally-present term must not lead either cluster
    assert "gracias" not in terms[0].index[:3]
    assert "gracias" not in terms[1].index[:3]


def test_ctfidf_drops_sami_stopwords():
    docs = ["hola buenos dias necesito informacion pasaporte"] * 4
    terms = clusters.ctfidf_terms(docs, [0, 0, 1, 1], top_n=10, min_user_df=1)
    for s in terms.values():
        assert not (set(s.index) & clusters.SAMI_STOPWORDS)


def test_ctfidf_min_user_df_drops_rare_terms_including_names():
    # "javier" appears for a single user -> must never reach a rendered term list;
    # "pasaporte" is shared across users -> must survive.
    docs = [f"pasaporte tramite documento {i}" for i in range(6)] + ["pasaporte javier tramite"]
    labels = [0] * 6 + [1]
    terms = clusters.ctfidf_terms(docs, labels, top_n=10, min_user_df=5)
    assert not any("javier" in s.index for s in terms.values())
    assert any("pasaporte" in s.index for s in terms.values())
    # with the floor lowered the rare token comes back -> proves the floor did the work
    loose = clusters.ctfidf_terms(docs, labels, top_n=10, min_user_df=1)
    assert any("javier" in s.index for s in loose.values())


def test_project_2d_shapes():
    rng = np.random.default_rng(0)
    X = rng.random((60, 10)).astype(np.float32)
    assert clusters.project_2d(X, method="pca").shape == (60, 2)


def test_archetype_profiles_sizes_and_terms():
    labels = pd.Series([0, 0, 1], index=["u1", "u2", "u3"], name="archetype")
    responses = pd.DataFrame(
        {
            "user_id": ["u1", "u2", "u3"],
            "city_canon": ["Medellín", "Medellín", "Bogotá"],
            "age_num": [30.0, 40.0, 10.0],
            "age_flag": ["ok", "ok", "unreliable_sub18"],
        }
    )
    messages = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2", "u3"],
            "message": ["a", "b", "c", "d"],
        }
    )
    terms = {
        0: pd.Series({"rumv": 3.0, "biometrico": 2.0, "cita": 1.0}),
        1: pd.Series({"emprendimiento": 2.0, "negocio": 1.0}),
    }
    prof = clusters.archetype_profiles(labels, responses, messages, terms=terms)

    assert prof.loc[0, "n_users"] == 2 and prof.loc[0, "n_messages"] == 3
    assert prof.loc[0, "median_age"] == pytest.approx(35.0)
    # sub-18 flagged record is excluded from the age read (P9)
    assert np.isnan(prof.loc[1, "median_age"])
    assert prof.loc[0, "top_terms"] == "rumv, biometrico, cita"
    assert "top_categories" not in prof.columns


def test_archetype_profiles_without_terms_leaves_top_terms_blank():
    labels = pd.Series([0, 0], index=["u1", "u2"], name="archetype")
    responses = pd.DataFrame({"user_id": ["u1", "u2"], "city_canon": ["Bogotá"] * 2})
    messages = pd.DataFrame({"user_id": ["u1", "u2"], "message": ["a", "b"]})
    prof = clusters.archetype_profiles(labels, responses, messages)
    assert prof.loc[0, "top_terms"] == ""


def test_silhouette_is_flat_detects_noise_level_curve():
    flat = pd.DataFrame({"silhouette": [0.038, 0.039, 0.040], "davies_bouldin": [3.9, 3.8, 3.7]},
                        index=pd.Index([4, 6, 8], name="k"))
    peaked = pd.DataFrame({"silhouette": [0.10, 0.62, 0.20], "davies_bouldin": [3.9, 0.8, 3.7]},
                          index=pd.Index([4, 6, 8], name="k"))
    assert clusters.silhouette_is_flat(flat) is True
    assert clusters.silhouette_is_flat(peaked) is False


def test_choose_k_prefers_largest_robustly_stable_k():
    scan = pd.DataFrame({"silhouette": [0.038, 0.037, 0.039, 0.040],
                         "davies_bouldin": [3.9, 3.9, 3.8, 3.7]},
                        index=pd.Index([3, 4, 5, 8], name="k"))
    stability = {                       # mirrors the real SAMI curve
        3: {"mean_ari": 0.817, "std_ari": 0.073},
        4: {"mean_ari": 0.805, "std_ari": 0.076},
        5: {"mean_ari": 0.675, "std_ari": 0.102},   # fails by one-sd margin
        8: {"mean_ari": 0.536, "std_ari": 0.081},
    }
    # largest k clearing the bar by 1 sd -> 4, NOT the argmax-silhouette 8
    assert clusters.choose_k(scan, stability_by_k=stability) == 4
    assert clusters.choose_k(scan) == 8          # no stability info -> silhouette rules


def test_choose_k_falls_back_when_nothing_is_stable():
    scan = pd.DataFrame({"silhouette": [0.03, 0.05], "davies_bouldin": [3.0, 2.0]},
                        index=pd.Index([4, 6], name="k"))
    unstable = {4: {"mean_ari": 0.2, "std_ari": 0.05}, 6: {"mean_ari": 0.3, "std_ari": 0.05}}
    assert clusters.choose_k(scan, stability_by_k=unstable) == 6   # argmax silhouette


def test_stability_curve_covers_the_range(blobs):
    X, _ = blobs
    curve = clusters.stability_curve(X, k_range=range(3, 6), n_boot=6)
    assert set(curve) == {3, 4, 5}
    assert all("mean_ari" in v and "std_ari" in v for v in curve.values())
