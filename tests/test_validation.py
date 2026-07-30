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
            "dominant_category": rng.choice(
                ["legal_documentation", "employment", "protection"], size=n
            ),
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
    # every category present in the corpus survives into the sample
    assert set(picked["dominant_category"]) == set(msgs["dominant_category"])


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
