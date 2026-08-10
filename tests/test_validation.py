import numpy as np
import pandas as pd
import pytest

from sami import validation


@pytest.fixture
def toy():
    rng = np.random.default_rng(0)
    n = 400
    msgs = pd.DataFrame(
        {
            "user_id": [f"u{i % 40}" for i in range(n)],
            "message": [f"mensaje numero {i}" for i in range(n)],
            "cluster_id": rng.choice([0, 1, 2], size=n),
        }
    )
    sent = pd.DataFrame(
        {
            "label": rng.choice(["negative", "neutral", "positive"], size=n),
            "score": rng.random(n),
        },
        index=msgs.index,
    )
    return msgs, sent


def test_sample_never_leaks_the_model_prediction(toy):
    msgs, sent = toy
    s = validation.stratified_sample(msgs, sent, n=100)
    assert list(s.columns) == validation.SAMPLE_COLUMNS
    # the whole point of the protocol: no prediction reaches the labeller
    assert not any("label" in c or "sent" in c or "score" in c for c in s.columns)


def test_sample_is_deterministic_and_sized(toy):
    msgs, sent = toy
    a = validation.stratified_sample(msgs, sent, n=100, random_state=0)
    b = validation.stratified_sample(msgs, sent, n=100, random_state=0)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) <= 100
    assert a["message_id"].is_unique


def test_sample_covers_every_non_empty_stratum(toy):
    msgs, sent = toy
    s = validation.stratified_sample(msgs, sent, n=100, random_state=0)
    picked = msgs.loc[s["message_id"]]
    # every cluster present in the corpus survives into the sample
    assert set(picked["cluster_id"]) == set(msgs["cluster_id"])


def test_stratified_sample_floor_survives_heavy_trimming():
    """Regression: when many small strata each claim their floor-of-1 row and
    the proportional allocation oversubscribes n, the trim step used to draw
    uniformly across every picked row -- including floor rows -- so a
    stratum's only row could be silently trimmed away despite the docstring's
    "cannot vanish" guarantee. Build a corpus with many tiny, single-message
    strata plus one big stratum so the allocation reliably overshoots n, and
    confirm every stratum still survives across several seeds.
    """
    rows = []
    for i in range(30):
        rows.append({
            "user_id": f"tiny{i}",
            "message": f"mensaje corto {i} con texto",
            "cluster_id": i,
            "_label": "negative" if i % 2 else "neutral",
        })
    for i in range(200):
        rows.append({
            "user_id": f"big{i}",
            "message": f"mensaje grande {i} con texto suficiente",
            "cluster_id": 100,
            "_label": "positive",
        })
    df = pd.DataFrame(rows)
    messages = df[["user_id", "message", "cluster_id"]].reset_index(drop=True)
    sentiment = pd.DataFrame({"label": df["_label"].values}, index=messages.index)

    n_strata = len(set(zip(messages["cluster_id"], sentiment["label"])))
    for seed in range(10):
        out = validation.stratified_sample(messages, sentiment, n=60, random_state=seed)
        picked_ids = out["message_id"]
        picked_strata = set(zip(messages.loc[picked_ids, "cluster_id"],
                                 sentiment.loc[picked_ids, "label"]))
        assert len(picked_strata) == n_strata, (
            f"seed {seed}: lost {n_strata - len(picked_strata)} stratum/strata")


def test_binarize_collapses_to_two_classes():
    b = validation.binarize(["negative", "neutral", "positive", "NEGATIVE"])
    assert list(b) == ["negative", "not_negative", "not_negative", "negative"]


def test_kappa_perfect_agreement():
    a = ["negative", "not_negative"] * 10
    assert validation.cohens_kappa(a, a) == pytest.approx(1.0)


def test_kappa_hand_computed():
    # 2x2: a=20, b=5, c=10, d=15 -> p_obs=.7, p_exp=.5 -> kappa=.4
    human = ["negative"] * 25 + ["not_negative"] * 25
    model = ["negative"] * 20 + ["not_negative"] * 5 + ["negative"] * 10 + ["not_negative"] * 15
    assert validation.cohens_kappa(human, model) == pytest.approx(0.4, abs=1e-9)


def test_kappa_chance_agreement_is_about_zero():
    rng = np.random.default_rng(3)
    a = rng.choice(["negative", "not_negative"], size=4000)
    b = rng.choice(["negative", "not_negative"], size=4000)
    assert abs(validation.cohens_kappa(a, b)) < 0.06


def test_kappa_rejects_length_mismatch():
    with pytest.raises(ValueError):
        validation.cohens_kappa(["negative"], ["negative", "not_negative"])


def test_validation_report_gate():
    human = ["negative"] * 25 + ["not_negative"] * 25
    poor = ["negative"] * 20 + ["not_negative"] * 5 + ["negative"] * 10 + ["not_negative"] * 15
    rep = validation.validation_report(human, poor)
    assert rep["kappa"] == pytest.approx(0.4, abs=1e-9)
    assert rep["gate_passed"] is False           # 0.4 < 0.7 -> percentages suppressed
    assert rep["n"] == 50
    assert rep["confusion"].to_numpy().sum() == 50

    rep_ok = validation.validation_report(human, human)
    assert rep_ok["gate_passed"] is True
    assert rep_ok["accuracy"] == pytest.approx(1.0)


def test_stratified_sample_strata_are_cluster_by_sentiment():
    n_rows = 40
    messages = pd.DataFrame({
        "user_id": [f"u{i}" for i in range(n_rows)],
        "message": [f"mensaje numero {i} con texto suficiente" for i in range(n_rows)],
        "cluster_id": [i % 4 for i in range(n_rows)],
        "seq": list(range(n_rows)),
    })
    sentiment = pd.DataFrame(
        {"label": ["negative" if i % 2 else "neutral" for i in range(n_rows)]},
        index=messages.index)

    out = validation.stratified_sample(messages, sentiment, n=16, random_state=0)

    assert len(out) <= 16
    assert "dominant_category" not in out.columns
    # every cluster survives the allocation floor. stratified_sample returns a
    # frame reset to a fresh 0..k-1 index, so out.index cannot be used to look
    # messages back up -- message_id (the original messages.index, carried
    # through as a column) is the only reliable join key.
    picked = messages.loc[out["message_id"], "cluster_id"]
    assert set(picked) == {0, 1, 2, 3}


# ---- gold-label alignment (the positional-join bug) ---------------------------
def _spine():
    """Three messages whose message_ids are content hashes, not row numbers."""
    return pd.DataFrame({
        "user_id": ["u1", "u1", "u2"],
        "seq": [0, 1, 0],
        "message": ["necesito ayuda urgente", "gracias", "como saco el ppt"],
    })


def _ids(spine):
    from sami import export
    return [export.message_key(u, s, m)
            for u, s, m in zip(spine["user_id"], spine["seq"], spine["message"])]


def test_align_gold_matches_on_message_id_not_position():
    spine = _spine()
    ids = _ids(spine)
    sent = pd.DataFrame({"label": ["negative", "neutral", "positive"]})
    # ask for the LAST message first -- a positional join would return 'negative'
    out = validation.align_gold([ids[2], ids[0]], spine, sent)
    assert list(out) == ["positive", "negative"]


def test_align_gold_raises_on_pre_migration_row_numbers():
    """The exact bug: gold files keyed on row numbers must fail, not resolve."""
    spine = _spine()
    sent = pd.DataFrame({"label": ["negative", "neutral", "positive"]})
    with pytest.raises(validation.GoldLabelError, match="do not match any message"):
        validation.align_gold([0, 1, 2], spine, sent)


def test_align_gold_raises_when_only_some_ids_are_unknown():
    spine = _spine()
    ids = _ids(spine)
    sent = pd.DataFrame({"label": ["negative", "neutral", "positive"]})
    with pytest.raises(validation.GoldLabelError, match="1 of 2"):
        validation.align_gold([ids[0], "deadbeefdeadbeef"], spine, sent)


def test_shipped_gold_labels_align_to_the_real_spine():
    """The committed gold file must be joinable to the current corpus."""
    from pathlib import Path
    from sami import config, facade
    if not (config.responses_path() and config.meal_path()):
        pytest.skip("real export not present (datasets/ holds no .xlsx)")
    gold = pd.read_csv("validation/tone_labels_analyst.csv", encoding="utf-8")
    SD = facade.load_sami()
    sent = pd.DataFrame({"label": ["neutral"] * len(SD.messages)})
    out = validation.align_gold(gold["message_id"], SD.messages, sent)  # must not raise
    assert len(out) == len(gold)
