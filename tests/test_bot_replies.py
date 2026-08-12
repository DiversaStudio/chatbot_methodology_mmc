"""Spec 4: bot-reply ingestion, the probes, and the Coverage Gap Rate.

Every test here runs on a synthetic fixture. The real log
(`datasets/bot_log/`) is out-of-band and gitignored, so no test may depend on
it -- a suite that only passes on the author's machine is not a suite.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sami import bot_replies, export, taxonomy, validation, qa

SALT = "test-salt"

GAP_REPLY = "Lo siento, no tengo información sobre albergues en Cúcuta."
GAP_REPLY_2 = "En este momento no cuento con información específica sobre ese trámite."
HANDOFF_REPLY = "Te recomiendo comunicarte con un asesor del equipo."
PLAIN_REPLY = "El PPT se solicita en la página de Migración Colombia."


def _log(rows) -> pd.DataFrame:
    """A raw, HEADERLESS four-column log, exactly as the platform exports it."""
    return pd.DataFrame(rows)


def _write(tmp_path, rows):
    path = tmp_path / "log.xlsx"
    _log(rows).to_excel(path, header=False, index=False)
    return path


BASE_ROWS = [
    ["2026-07-23T10:00:00.000Z", "whatsapp:+573001112233", "hola", PLAIN_REPLY],
    ["2026-07-24T10:00:00.000Z", "whatsapp:+573001112233", "albergue?", GAP_REPLY],
    ["2026-08-04T10:00:00.000Z", "whatsapp:+573004445566", "ayuda", HANDOFF_REPLY],
]


# ---- probes ----
def test_gap_probe_matches_the_common_phrasings():
    flags = bot_replies.flag([GAP_REPLY, GAP_REPLY_2, PLAIN_REPLY])
    assert list(flags["gap_flag"]) == [True, True, False]


def test_handoff_probe_is_independent_of_the_gap_probe():
    """A reply can route to a human without stating an information gap."""
    flags = bot_replies.flag([HANDOFF_REPLY])
    assert bool(flags["handoff_flag"].iloc[0]) is True
    assert bool(flags["gap_flag"].iloc[0]) is False


def test_gap_probe_is_accent_and_case_insensitive():
    """Production replies use both 'información' and, occasionally, 'informacion'."""
    flags = bot_replies.flag(["NO TENGO INFORMACION SOBRE ESO",
                              "no tengo información sobre eso"])
    assert list(flags["gap_flag"]) == [True, True]


# ---- identity ----
def test_reply_key_is_content_addressed_not_positional():
    """The tone gold set's expensive lesson: identity must survive a re-order."""
    a = bot_replies.reply_key(GAP_REPLY)
    b = bot_replies.reply_key("  " + GAP_REPLY.upper() + "\n")
    assert a == b, "whitespace/case normalisation must not change identity"
    assert a != bot_replies.reply_key(PLAIN_REPLY)


def test_user_id_matches_the_survey_pseudonym(tmp_path):
    """The whole join rests on this: same phone, same salt -> same user_id."""
    from sami import load
    turns = bot_replies.load_bot_log(_write(tmp_path, BASE_ROWS), SALT)
    assert turns["user_id"].iloc[0] == load.pseudonymize("whatsapp:+573001112233", SALT)


# ---- loading ----
def test_load_reads_a_headerless_log(tmp_path):
    turns = bot_replies.load_bot_log(_write(tmp_path, BASE_ROWS), SALT)
    assert len(turns) == 3
    assert turns["user_id"].nunique() == 2
    assert list(turns["gap_flag"]) == [False, True, False]


def test_load_rejects_a_file_with_a_header_row(tmp_path):
    """A header row shifts every column; failing loudly beats flagging a header."""
    path = tmp_path / "log.xlsx"
    pd.DataFrame(BASE_ROWS, columns=["a", "b", "c"] + ["d"]).to_excel(
        path, index=False)  # 4 cols but a header -> parses as 4 cols + header row
    turns = bot_replies.load_bot_log(path, SALT)
    # The header row's 'a' is not a timestamp, so it is dropped rather than
    # silently counted as a turn.
    assert len(turns) == 3


def test_load_rejects_the_wrong_column_count(tmp_path):
    path = tmp_path / "log.xlsx"
    pd.DataFrame([["x", "y"]]).to_excel(path, header=False, index=False)
    with pytest.raises(Exception, match="exactly 4 columns"):
        bot_replies.load_bot_log(path, SALT)


def test_load_sorts_by_timestamp(tmp_path):
    rows = list(reversed(BASE_ROWS))
    turns = bot_replies.load_bot_log(_write(tmp_path, rows), SALT)
    assert turns["ts"].is_monotonic_increasing


# ---- gold candidates ----
def test_gold_candidates_censuses_matched_and_samples_the_rest(tmp_path):
    rows = BASE_ROWS + [
        [f"2026-07-25T10:0{i}:00.000Z", "whatsapp:+57300777{i}", f"q{i}",
         f"{PLAIN_REPLY} variante {i}"] for i in range(9)
    ]
    turns = bot_replies.load_bot_log(_write(tmp_path, rows), SALT)
    cand = bot_replies.gold_candidates(turns, n_unmatched=5, random_state=0)
    assert (cand["stratum"] == "matched").sum() == 1  # census: every flagged reply
    assert (cand["stratum"] == "unmatched").sum() == 5
    assert (cand["human_label"] == "").all(), "the label column is the human's job"


def test_gold_candidates_deduplicates_identical_replies(tmp_path):
    rows = BASE_ROWS + [
        ["2026-07-26T10:00:00.000Z", "whatsapp:+573009998877", "otra", GAP_REPLY],
    ]
    turns = bot_replies.load_bot_log(_write(tmp_path, rows), SALT)
    cand = bot_replies.gold_candidates(turns, n_unmatched=0)
    assert len(cand) == 1, "identical text must be labelled once, not twice"


# ---- probe_report maths ----
def _gold(matched_pos, matched_neg, sampled_pos, sampled_neg) -> pd.DataFrame:
    rows = ([{"stratum": "matched", "human_label": "gap"}] * matched_pos
            + [{"stratum": "matched", "human_label": "not_gap"}] * matched_neg
            + [{"stratum": "unmatched", "human_label": "gap"}] * sampled_pos
            + [{"stratum": "unmatched", "human_label": "not_gap"}] * sampled_neg)
    return pd.DataFrame(rows)


def test_probe_report_precision_is_a_census():
    rep = validation.probe_report(_gold(80, 20, 0, 100), n_unmatched_total=100)
    assert rep["precision"] == pytest.approx(0.8)
    assert rep["tp"] == 80 and rep["fp"] == 20


def test_probe_report_scales_misses_to_the_whole_unmatched_population():
    """5 misses in 100 sampled, over 1000 unmatched -> 50 estimated misses."""
    rep = validation.probe_report(_gold(50, 0, 5, 95), n_unmatched_total=1000)
    assert rep["recall"] == pytest.approx(50 / (50 + 50))


def test_probe_report_recall_interval_inverts_the_miss_interval():
    """A HIGH miss rate means LOW recall — the bounds must cross over."""
    rep = validation.probe_report(_gold(50, 0, 5, 95), n_unmatched_total=1000)
    assert rep["recall_lo"] < rep["recall"] < rep["recall_hi"]


def test_probe_report_perfect_recall_is_not_a_floor():
    rep = validation.probe_report(_gold(50, 0, 0, 100), n_unmatched_total=1000)
    assert rep["recall"] == pytest.approx(1.0)
    assert rep["rate_is_floor"] is False


def test_probe_report_gate_fails_on_poor_precision():
    rep = validation.probe_report(_gold(50, 50, 0, 100), n_unmatched_total=100)
    assert rep["precision"] == pytest.approx(0.5)
    assert rep["gate_passed"] is False


# ---- export tables ----
def _turns(tmp_path, rows=None):
    return bot_replies.load_bot_log(_write(tmp_path, rows or BASE_ROWS), SALT)


def test_fact_bot_turn_carries_no_message_text(tmp_path):
    """Structural, not incidental: pii_scan would pass this text."""
    out = export.build_fact_bot_turn(_turns(tmp_path), pd.DataFrame({"user_id": []}))
    assert "bot_reply" not in out.columns and "user_message" not in out.columns
    assert list(out.columns) == export.FACT_BOT_TURN_COLUMNS


def test_fact_bot_turn_flags_survey_membership_without_dropping_anyone(tmp_path):
    from sami import load
    known = load.pseudonymize("whatsapp:+573001112233", SALT)
    out = export.build_fact_bot_turn(_turns(tmp_path),
                                     pd.DataFrame({"user_id": [known]}))
    assert len(out) == 3, "users without a survey record must not be dropped"
    assert list(out["has_survey_record"]) == [True, True, False]


def test_fact_bot_turn_passes_the_pii_gate(tmp_path):
    out = export.build_fact_bot_turn(_turns(tmp_path), pd.DataFrame({"user_id": []}))
    assert qa.pii_scan(out) == []


def test_agg_coverage_gap_reports_both_grains(tmp_path):
    rep = validation.probe_report(_gold(9, 1, 0, 100), n_unmatched_total=100)
    out = export.build_agg_coverage_gap(_turns(tmp_path), gap_probe=rep)
    users = out[(out.metric == "coverage_gap") & (out.grain == "users")].iloc[0]
    turns = out[(out.metric == "coverage_gap") & (out.grain == "turns")].iloc[0]
    assert (users.numerator, users.denominator) == (1, 2)
    assert (turns.numerator, turns.denominator) == (1, 3)


def test_agg_coverage_gap_suppresses_the_rate_when_precision_fails(tmp_path):
    rep = validation.probe_report(_gold(5, 5, 0, 100), n_unmatched_total=100)
    out = export.build_agg_coverage_gap(_turns(tmp_path), gap_probe=rep)
    gap = out[out.metric == "coverage_gap"]
    assert gap["rate_pct"].isna().all(), "a failed gate must withhold the rate"
    assert (~gap["rate_quotable"]).all()
    assert (gap["numerator"] > 0).any(), "counts stay so the reader sees it was withheld"


def test_agg_coverage_gap_marks_handoff_unquotable(tmp_path):
    """No gold set covers the handoff probe, so its rate is never quotable."""
    rep = validation.probe_report(_gold(9, 1, 0, 100), n_unmatched_total=100)
    out = export.build_agg_coverage_gap(_turns(tmp_path), gap_probe=rep)
    handoff = out[out.metric == "human_handoff"]
    assert (~handoff["rate_quotable"]).all()
    assert handoff["precision"].isna().all()


def test_agg_coverage_gap_without_a_gold_set_is_unquotable(tmp_path):
    out = export.build_agg_coverage_gap(_turns(tmp_path), gap_probe=None)
    assert (~out["rate_quotable"]).all()
    assert out["rate_pct"].isna().all()


def test_empty_tables_keep_their_headers():
    """A clone with no bot log must still produce loadable, column-complete tables."""
    empty = export.build_agg_coverage_gap(
        pd.DataFrame(columns=["turn_id", "user_id", "ts", "gap_flag", "handoff_flag"]))
    assert list(empty.columns) == export.AGG_COVERAGE_GAP_COLUMNS
    assert len(empty) == 0


# ---- agg_bot_gap_entities: the topic breakdown behind NB2 Figure 8 ----
# Five distinct users each mention "PPT" (a procedure entity); two of the five
# get a gap reply, so PPT clears the mention floor at gap_count=2, total=5,
# pct_gap=40.0. A sixth user with no PPT mention is noise the count must not pick up.
PPT_ROWS = [
    ["2026-07-23T10:00:00.000Z", "whatsapp:+573001112231", "necesito el PPT", GAP_REPLY],
    ["2026-07-23T10:01:00.000Z", "whatsapp:+573001112232", "quiero saber del PPT", GAP_REPLY_2],
    ["2026-07-23T10:02:00.000Z", "whatsapp:+573001112233", "el PPT ya vence", PLAIN_REPLY],
    ["2026-07-23T10:03:00.000Z", "whatsapp:+573001112234", "como saco el PPT", PLAIN_REPLY],
    ["2026-07-23T10:04:00.000Z", "whatsapp:+573001112235", "info del PPT porfa", PLAIN_REPLY],
    ["2026-07-23T10:05:00.000Z", "whatsapp:+573001112236", "hola", PLAIN_REPLY],
]


def test_agg_bot_gap_entities_computes_the_rate_above_the_floor(tmp_path):
    out = export.build_agg_bot_gap_entities(_turns(tmp_path, PPT_ROWS))
    row = out[(out.kind == "procedure") & (out.entity == "PPT")]
    assert len(row) == 1
    r = row.iloc[0]
    assert (r.gap_count, r.total_count) == (2, 5)
    assert r.pct_gap == pytest.approx(40.0)


def test_agg_bot_gap_entities_drops_entities_below_the_mention_floor(tmp_path):
    """BASE_ROWS mentions each entity at most once -- well under the floor of 5."""
    out = export.build_agg_bot_gap_entities(_turns(tmp_path))
    assert out.empty


def test_agg_bot_gap_entities_carries_no_message_text(tmp_path):
    """Structural, like fact_bot_turn: this table is counts, never text."""
    out = export.build_agg_bot_gap_entities(_turns(tmp_path, PPT_ROWS))
    assert list(out.columns) == export.AGG_BOT_GAP_ENTITIES_COLUMNS
    assert "user_message" not in out.columns


def test_agg_bot_gap_entities_passes_the_pii_gate(tmp_path):
    out = export.build_agg_bot_gap_entities(_turns(tmp_path, PPT_ROWS))
    assert qa.pii_scan(out) == []


def test_agg_bot_gap_entities_empty_log_keeps_headers():
    """A clone with no bot log must still produce a loadable, column-complete table."""
    empty = export.build_agg_bot_gap_entities(
        pd.DataFrame(columns=["gap_flag", "user_message"]))
    assert list(empty.columns) == export.AGG_BOT_GAP_ENTITIES_COLUMNS
    assert len(empty) == 0


# ---- the shipped gold set ----
def test_shipped_gold_set_clears_the_precision_gate():
    """Guards the real measurement, not a fixture.

    If someone edits COVERAGE_GAP_PROBE without re-labelling, precision drifts
    from what this file recorded and the KPI silently changes meaning. This is
    the test that notices.
    """
    gold = pd.read_csv("validation/gap_gold_labels.csv", encoding="utf-8")
    rep = validation.probe_report(gold, n_unmatched_total=872)
    assert rep["n_matched"] == 84 and rep["n_sampled"] == 200
    assert rep["precision"] >= validation.GAP_PRECISION_GATE
    assert rep["gate_passed"] is True
    assert rep["rate_is_floor"] is True, "10 known misses -> the rate is a floor"


def test_shipped_gold_labels_agree_with_the_probe_on_the_matched_stratum():
    """Every 'matched' row must actually match the current probe.

    A row labelled under an older pattern is a row whose precision contribution
    is meaningless. This catches a probe edit that silently drops a matched
    reply out of the flagged set.
    """
    gold = pd.read_csv("validation/gap_gold_labels.csv", encoding="utf-8")
    matched = gold[gold["stratum"] == "matched"]
    flags = bot_replies.flag(matched["bot_reply"])
    assert flags["gap_flag"].all(), (
        "a gold 'matched' reply no longer matches COVERAGE_GAP_PROBE — "
        "the probe changed, so re-run the labelling pass")


def test_shipped_gold_unmatched_rows_still_do_not_match():
    gold = pd.read_csv("validation/gap_gold_labels.csv", encoding="utf-8")
    unmatched = gold[gold["stratum"] == "unmatched"]
    flags = bot_replies.flag(unmatched["bot_reply"])
    assert not flags["gap_flag"].any(), (
        "a gold 'unmatched' reply now matches COVERAGE_GAP_PROBE — the probe "
        "widened, so its precision census is stale")


def test_probes_live_in_taxonomy_beside_the_other_probes():
    assert isinstance(taxonomy.COVERAGE_GAP_PROBE, str)
    assert isinstance(taxonomy.HUMAN_HANDOFF_PROBE, str)
