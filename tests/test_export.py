import re
import warnings

import numpy as np
import pandas as pd
import pytest
from sami import load_sami, export, cohort, config, theme


@pytest.fixture(scope="module")
def SD():
    # Every test using this fixture needs the real, gitignored export -- there
    # is no fixture-based substitute (export.py's builders assume the full
    # facade output, not a 6-row synthetic sample, and would trip the P9
    # critical QA gate on the fixture's deliberately mixed summary formats).
    # Skip cleanly rather than error when the export is absent, same as the
    # requires_real_data marker used elsewhere for the same reason.
    if not (config.responses_path() and config.meal_path()):
        pytest.skip("real export not present (datasets/ holds no .xlsx)")
    return load_sami()


def _empty_lab() -> pd.Series:
    """No cluster-label map. `lab` became a required parameter of `build_dim_user`
    / `build_fact_message` once cluster_id replaced dominant_category as the one
    categorisation dimension; a real clustering run is out of scope for the tests
    below, which exercise columns unrelated to clustering, so every user here
    falls back to NO_CLUSTER_ID."""
    return pd.Series(dtype=int)


def test_dim_city_schema_and_coords():
    from sami import canon
    d = export.build_dim_city()
    assert list(d.columns) == ["city_canon", "department", "lat", "lon"]
    assert "Otra" not in set(d["city_canon"])
    assert d["lat"].notna().all() and d["lon"].notna().all()
    assert d["city_canon"].is_unique
    for _, r in d.iterrows():
        assert r["department"] == canon.department_of(r["city_canon"])


def test_city_coords_cover_all_departmented_cities():
    from sami import canon
    assert set(canon.DEPARTMENT_OF_CITY) == set(canon.CITY_COORDS)


def test_dim_user_new_flags(SD):
    d = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    for c in ["first_seen", "is_repeat_asker", "intends_to_stay"]:
        assert c in d.columns
    assert d["is_repeat_asker"].dtype == bool
    assert d["intends_to_stay"].dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(d["first_seen"])
    q = SD.responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    assert int(d["is_repeat_asker"].sum()) == int((q >= p90).sum())


def test_fact_message_no_text(SD):
    f = export.build_fact_message(SD.messages, lab=_empty_lab())
    assert "message" not in f.columns
    for c in ["message_id", "user_id", "ts", "cluster_id"]:
        assert c in f.columns


def test_meta_run_schema_version():
    m = export.build_meta_run({"responses_file": "x.xlsx"})
    kv = dict(zip(m["key"], m["value"]))
    assert kv["schema_version"] == "5"


def test_meta_run_carries_report_version():
    """The dashboard footer renders this; without it the stamp reads blank."""
    m = export.build_meta_run({"responses_file": "x.xlsx"})
    kv = dict(zip(m["key"], m["value"]))
    assert kv["report_version"] == export.REPORT_VERSION
    assert re.fullmatch(r"\d+\.\d+\.\d+", kv["report_version"])


def test_parity_check_includes_repeat_askers(SD):
    du = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    fmsg = export.build_fact_message(SD.messages, lab=_empty_lab())
    fmeal = export.build_fact_meal(SD.meal)
    p = export.build_parity_check(SD.reconciliation, du, fmsg, fmeal)
    assert "repeat_askers_pct" in set(p["metric"])
    # cluster_coverage_pct is expected to fail here: _empty_lab() intentionally
    # labels no one, so every user falls back to NO_CLUSTER_ID.
    non_cluster = p[p["metric"] != "cluster_coverage_pct"]
    assert non_cluster["match"].all(), non_cluster[~non_cluster["match"]]


def test_dim_user_one_row_per_user(SD):
    d = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    assert d["user_id"].is_unique
    assert d["user_id"].nunique() == SD.responses["user_id"].nunique()
    for col in ["user_id", "gender_clean", "age_num", "department",
                "n_msgs_user", "has_text", "cluster_id"]:
        assert col in d.columns
    # has_text == user appears in the message spine
    assert int(d["has_text"].sum()) == SD.messages["user_id"].nunique()
    # every user falls back to NO_CLUSTER_ID without an NLP label map
    assert (d["cluster_id"] == export.NO_CLUSTER_ID).all()


_SPANISH_TOKENS = ("Mujer", "Hombre", "Otra", "Desconocida", "meses", "años",
                   "útil", "Recomendación", "Redes sociales", "Sí")


def _no_spanish(frame, cols):
    for col in cols:
        vals = {str(v) for v in frame[col].dropna().unique()}
        bad = [v for v in vals if any(t in v for t in _SPANISH_TOKENS)]
        assert not bad, f"{col}: {bad}"


def test_dim_user_registered_at_is_never_null(SD):
    """The whole point of this column: a new-user count built on `first_seen`
    silently drops everyone who registered and never sent a message."""
    d = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    assert d["registered_at"].notna().all()
    assert d["first_seen"].isna().any()             # the gap this column closes
    # registration cannot postdate the user's first message
    both = d.dropna(subset=["first_seen"])
    assert (both["registered_at"] <= both["first_seen"]).all()


def test_dim_user_display_values_are_english(SD):
    d = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    _no_spanish(d, ["gender_clean", "minors", "away_duration_canon",
                    "city_duration_canon", "city_canon", "nationality_canon"])
    from sami import canon
    assert set(d["gender_clean"].dropna()) <= {
        "Woman", "Man", "LGBTQ+", canon.GENDER_OTHER_OR_UNSTATED, ""}
    # the ordering columns still carry the sort after the labels are translated
    if d["away_duration_order"].notna().any():
        pairs = d.dropna(subset=["away_duration_order"])
        assert pairs.groupby("away_duration_canon")["away_duration_order"].nunique().eq(1).all()


def test_duration_scales_name_their_non_response_bucket(SD):
    d = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    for label_col, order_col in (("away_duration_canon", "away_duration_order"),
                                 ("city_duration_canon", "city_duration_order")):
        # no unlabelled bar on the axis, and no null in the sort-by column
        assert d[label_col].notna().all()
        assert (d[label_col].astype(str).str.strip() != "").all()
        assert d[order_col].notna().all()
        # the bucket sorts below the real scale, so it never reads as "longest"
        nr = d[d[label_col] == export.NO_RESPONSE_EN][order_col]
        if len(nr):
            assert (nr == export.NO_RESPONSE_ORDER).all()
            assert nr.iat[0] < d.loc[d[label_col] != export.NO_RESPONSE_EN,
                                     order_col].min()


def test_fact_meal_english_labels_keep_rating_num(SD):
    f = export.build_fact_meal(SD.meal)
    _no_spanish(f, ["usefulness_rating", "would_recommend", "discovery_channel"])
    # rating_num keys off the Spanish vocabulary — translation must not break it
    scored = f.dropna(subset=["usefulness_rating"])
    if len(scored):
        assert scored["rating_num"].notna().all()


def test_dim_user_no_pii(SD):
    from sami import qa
    assert qa.pii_scan(export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())) == []


def test_fact_message_grain_and_join(SD):
    f = export.build_fact_message(SD.messages, lab=_empty_lab())
    assert len(f) == len(SD.messages)
    assert f["message_id"].is_unique
    assert f["message_id"].str.match(r"^[0-9a-f]{16}$").all()  # 16-char hex hash
    assert f["sentiment_label"].isna().all()   # no sentiment passed
    assert (f["cluster_id"] == export.NO_CLUSTER_ID).all()


def test_fact_message_sentiment_join(SD):
    # synthetic sentiment aligned to the messages index
    sent = pd.DataFrame({"label": ["negative"] * len(SD.messages)}, index=SD.messages.index)
    f = export.build_fact_message(SD.messages, sentiment=sent, lab=_empty_lab())
    assert (f["sentiment_label"] == "negative").all()


def test_fact_meal_rating_num(SD):
    f = export.build_fact_meal(SD.meal)
    assert f["user_id"].is_unique
    assert "rating_num" in f.columns
    # rating_num is 1-5 or NaN, never a raw string
    vals = f["rating_num"].dropna().unique()
    assert set(vals).issubset({1, 2, 3, 4, 5})


def test_agg_funnel_top_equals_users(SD):
    f = export.build_agg_funnel(SD.responses, SD.messages, SD.meal)
    assert list(f.columns[:3]) == ["stage_order", "stage", "n"]
    assert int(f["n"].iloc[0]) == SD.responses["user_id"].nunique()


def test_agg_entities_by_kind(SD):
    e = export.build_agg_entities_by_kind(SD.messages)
    assert set(e.columns) == {"kind", "entity", "n"}
    assert (e["n"] > 0).all()


def test_agg_daily_volume(SD):
    d = export.build_agg_daily_volume(SD.messages)
    assert set(d.columns) == {"day", "n"}
    assert d["n"].sum() == SD.messages["ts"].notna().sum()


def test_nlp_umap_synthetic():
    XY = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
    labels = np.array([0, 1, 0])
    user_ids = ["u1", "u2", "u3"]
    u = export.build_nlp_umap(XY, labels, user_ids)
    assert list(u.columns) == ["user_id", "x", "y", "cluster_id"]
    assert list(u["user_id"]) == user_ids
    assert u["x"].iloc[1] == 0.3


def test_nlp_cluster_terms_synthetic():
    terms = {0: pd.Series({"cita": 0.9, "pasaporte": 0.7}),
             1: pd.Series({"trabajo": 0.8})}
    t = export.build_nlp_cluster_terms(terms)
    assert set(t.columns) == {"cluster_id", "rank", "term", "weight"}
    assert t[(t.cluster_id == 0) & (t["rank"] == 0)]["term"].iloc[0] == "cita"


def test_nlp_tone_confusion_synthetic():
    cats = ["negative", "not_negative"]
    cm = pd.DataFrame([[5, 2], [3, 90]], index=cats, columns=cats)
    cm.index.name, cm.columns.name = "human", "model"
    report = {"confusion": cm}
    c = export.build_nlp_tone_confusion(report)
    assert set(c.columns) == {"human_label", "model_label", "n"}
    assert int(c[(c.human_label == "negative") & (c.model_label == "negative")]["n"].iloc[0]) == 5
    assert c["n"].sum() == 100


def test_nlp_emergent_themes(SD):
    e = export.build_nlp_emergent_themes(SD.messages)
    assert set(e.columns) == {"theme", "slug", "n_messages", "n_users"}
    assert (e["n_users"] >= 0).all()


def test_dim_cluster_colours_follow_size_rank_not_cluster_id():
    """Colour must track "biggest cluster", not the id the clusterer handed
    out — otherwise every re-cluster silently re-colours the dashboard."""
    prof = pd.DataFrame(
        {"n_users": [5, 40, 12], "n_messages": [10, 90, 30],
         "median_age": [30.0, 28.0, 33.0],
         "top_terms": ["a", "b", "c"]},
        index=pd.Index([0, 1, 2], name="archetype"))
    resolved = {0: {"name": "S", "marker": "a", "provisional": True},
                1: {"name": "L", "marker": "b", "provisional": True},
                2: {"name": "M", "marker": "c", "provisional": True}}
    d = export.build_dim_cluster(prof, resolved).set_index("cluster_id")

    assert list(d.loc[[0, 1, 2], "display_order"]) == [2, 0, 1]   # smallest is ranked last
    assert d.loc[1, "color_hex"] == theme.CLUSTER_IDENTITY[0]     # largest gets brand teal
    assert d.loc[2, "color_hex"] == theme.CLUSTER_IDENTITY[1]
    assert d.loc[0, "color_hex"] == theme.CLUSTER_IDENTITY[2]
    assert d.loc[[0, 1, 2], "color_hex"].nunique() == 3           # no two clusters share a hue


def test_dim_cluster_size_ties_break_deterministically():
    prof = pd.DataFrame(
        {"n_users": [7, 7], "n_messages": [1, 2], "median_age": [30.0, 31.0],
         "top_terms": ["a", "b"]},
        index=pd.Index([3, 1], name="archetype"))
    resolved = {1: {"name": "A", "marker": "a", "provisional": True},
                3: {"name": "B", "marker": "b", "provisional": True}}
    d = export.build_dim_cluster(prof, resolved).set_index("cluster_id")
    assert d.loc[1, "display_order"] == 0                 # lower cluster_id wins the tie
    assert d.loc[3, "display_order"] == 1


def test_dim_quadrant_schema():
    q = export.build_dim_quadrant()
    assert list(q.columns) == ["quadrant_key", "label", "action", "axis_x",
                               "axis_y", "color_hex", "display_order"]
    assert len(q) == 4
    assert set(zip(q["axis_x"], q["axis_y"])) == {
        ("high", "high"), ("high", "low"), ("low", "high"), ("low", "low")}
    assert q["color_hex"].nunique() == 4
    assert q["color_hex"].str.fullmatch(r"#[0-9a-f]{6}").all()


def test_nlp_voices_picks_marker_quote():
    cid = 0
    marker = "pasaporte"
    resolved = {cid: {"name": "Doc-seeker", "marker": marker, "provisional": False}}
    msg = ((marker + " ") * 20)[:150]          # 60-190 chars, contains the marker
    msgs_lab = pd.DataFrame({"archetype": [cid, cid], "user_id": ["u1", "u2"],
                             "seq": [0, 1], "message": [msg, "corto"]})
    v = export.build_nlp_voices(msgs_lab, resolved)
    assert list(v.columns) == ["cluster_id", "name", "message"]
    assert v.loc[0, "message"] == msg
    assert v.loc[0, "name"] == resolved[cid]["name"]


def test_nlp_voices_dash_fallback_when_no_match():
    cid = 0
    resolved = {cid: {"name": "X", "marker": "pasaporte", "provisional": False}}
    msgs_lab = pd.DataFrame({"archetype": [cid], "user_id": ["u1"],
                             "seq": [0], "message": ["corto"]})   # too short, no marker
    v = export.build_nlp_voices(msgs_lab, resolved)
    assert v.loc[0, "message"] == "—"


def test_meta_run_flags():
    m = export.build_meta_run({"responses_file": "x.xlsx", "checks": [("P1", True)]},
                              nlp_meta={"tone_gate_passed": False,
                                        "sentiment_quotable": False, "nlp_included": True})
    kv = dict(zip(m["key"], m["value"]))
    assert "checks" not in kv                          # dropped (not scalar)
    assert kv["tone_gate_passed"] == "False"
    assert kv["sentiment_quotable"] == "False"


def test_parity_check_all_match(SD):
    du = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    fmsg = export.build_fact_message(SD.messages, lab=_empty_lab())
    fmeal = export.build_fact_meal(SD.meal)
    p = export.build_parity_check(SD.reconciliation, du, fmsg, fmeal)
    assert set(p.columns) == {"metric", "exported_value", "reconciliation_value", "match"}
    # cluster_coverage_pct is expected to fail here: _empty_lab() intentionally
    # labels no one, so every user falls back to NO_CLUSTER_ID.
    non_cluster = p[p["metric"] != "cluster_coverage_pct"]
    assert non_cluster["match"].all(), non_cluster[~non_cluster["match"]]


def test_write_all_writes_and_manifests(tmp_path):
    tables = {
        "tiny": pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}),
        "tiny2": pd.DataFrame({"c": [3, 4, 5], "d": ["p", "q", "r"]}),
    }
    manifest = export.write_all(tmp_path, tables)
    assert (tmp_path / "tiny.csv").exists()
    assert (tmp_path / "tiny2.csv").exists()
    assert (tmp_path / "_manifest.csv").exists()
    assert set(manifest["table"]) == {"tiny", "tiny2"}
    assert int(manifest.set_index("table").loc["tiny", "rows"]) == 2


def test_write_all_aborts_on_pii(tmp_path):
    bad = pd.DataFrame({"txt": ["reach me at whatsapp:+573001234567"]})
    with pytest.raises(ValueError, match="PII"):
        export.write_all(tmp_path, {"bad": bad})
    assert not (tmp_path / "bad.csv").exists()          # nothing partially written


def test_agg_weekly_rating(SD):
    fm = export.build_fact_meal(SD.meal)
    w = export.build_agg_weekly_rating(fm)
    assert set(w.columns) == {"week", "mean_rating", "n"}
    # resample("W") emits a row per week in range — empty weeks have n=0, mean NaN.
    assert w["mean_rating"].dropna().between(1, 5).all()
    assert (w["n"] >= 0).all()
    # counts sum to the rated-and-dated MEAL responses
    rated = fm.dropna(subset=["ts", "rating_num"])
    assert int(w["n"].sum()) == len(rated)


def _spine():
    return pd.DataFrame({
        "user_id": ["u1", "u1", "u2"],
        "ts": pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"]),
        "message": ["hola que tal", "necesito ayuda", "busco empleo"],
        "seq": [0, 1, 0],
        "n_msgs_user": [2, 2, 1],
        "city_canon": ["Medellín", "Medellín", "Cúcuta"],
    })


def test_message_id_is_stable_when_other_users_are_added():
    """Regression: message_id was messages.reset_index(), a POSITIONAL id.
    The spine is sorted by (user_id, ts), so one new user re-numbered every
    row — silently re-pointing anything keyed on it."""
    base = _spine()
    before = export.build_fact_message(base, lab=_empty_lab())
    grown = pd.concat([
        pd.DataFrame({
            "user_id": ["u0"], "ts": pd.to_datetime(["2026-03-01"]),
            "message": ["mensaje nuevo"], "seq": [0], "n_msgs_user": [1],
            "city_canon": ["Bogotá"],
        }), base]).reset_index(drop=True)
    after = export.build_fact_message(grown, lab=_empty_lab())

    got = after.set_index("user_id").loc["u2", "message_id"]
    want = before.set_index("user_id").loc["u2", "message_id"]
    assert got == want


def test_message_id_is_unique_per_row():
    f = export.build_fact_message(_spine(), lab=_empty_lab())
    assert f["message_id"].is_unique


def test_message_id_differs_for_identical_text_from_different_users():
    df = pd.DataFrame({
        "user_id": ["u1", "u2"], "ts": pd.to_datetime(["2026-04-01"] * 2),
        "message": ["gracias", "gracias"], "seq": [0, 0], "n_msgs_user": [1, 1],
        "city_canon": ["Medellín"] * 2,
    })
    f = export.build_fact_message(df, lab=_empty_lab())
    assert f["message_id"].nunique() == 2


def test_message_id_contains_no_pii():
    f = export.build_fact_message(_spine(), lab=_empty_lab())
    assert f["message_id"].str.match(r"^[0-9a-f]{16}$").all()


def test_message_id_changes_on_backfilled_earlier_message():
    """Limitation: seq is based on timestamp order, so a backfilled message
    with an earlier timestamp renumbers the entire user's sequence."""
    base_messages = pd.DataFrame({
        "user_id": ["u1", "u1"],
        "ts": pd.to_datetime(["2026-04-02", "2026-04-03"]),
        "message": ["segunda", "tercera"],
        "seq": [0, 1],
        "n_msgs_user": [2, 2],
        "city_canon": ["Medellín", "Medellín"],
    })
    before = export.build_fact_message(base_messages, lab=_empty_lab())
    # Save message_id for the second row (seq=1, "tercera") before backfill
    tercera_before_seq = 1
    tercera_id_before = before[before["seq"] == tercera_before_seq].iloc[0]["message_id"]

    # Backfill an earlier message. After concat + sort by (user_id, ts),
    # seq will be recomputed: 0=primera, 1=segunda, 2=tercera.
    backfilled = pd.concat([
        pd.DataFrame({
            "user_id": ["u1"],
            "ts": pd.to_datetime(["2026-04-01"]),
            "message": ["primera"],
            "seq": [0],  # This will be wrong after sorting
            "n_msgs_user": [3],
            "city_canon": ["Medellín"],
        }), base_messages
    ]).sort_values(["user_id", "ts"]).reset_index(drop=True)

    # Recompute seq (mimicking load.load_messages behavior)
    backfilled["seq"] = backfilled.groupby("user_id").cumcount()

    after = export.build_fact_message(backfilled, lab=_empty_lab())

    # The "tercera" message was seq=1 before, now it's seq=2 after backfill.
    # Since message_key uses seq, the id must change.
    tercera_after_seq = 2
    tercera_id_after = after[after["seq"] == tercera_after_seq].iloc[0]["message_id"]

    assert tercera_id_before != tercera_id_after, (
        "Backfilled earlier message renumbers seq, so message_ids change"
    )


def _responses_two_cohorts():
    return pd.DataFrame({
        "user_id": ["u1", "u2"],
        "ts": pd.to_datetime(["2026-04-01", "2026-07-25"]),
        "gender_clean": ["Mujer", "Hombre"],
        "age_num": [30.0, 28.0],
        "city_canon": ["Medellín", "Ipiales"],
        "n_questions": [2, 1],
        "Migrated From v1": ["v1:100", None],
        "Language": ["es", "en"],
        "Registration Status": ["Completed", "Completed"],
        "Attempts": [1, 2],
        "Is Returning User": [None, "yes"],
        "Safety Alert": [None, "flagged"],
        "Escalation Status": [None, "escalated"],
        "Destination_Country": ["Colombia", "Chile"],
    })


def _messages_two_users():
    return pd.DataFrame({
        "user_id": ["u1", "u2"], "ts": pd.to_datetime(["2026-04-01", "2026-07-25"]),
        "message": ["hola", "help"], "seq": [0, 0], "n_msgs_user": [1, 1],
    })


def test_dim_user_carries_instrument_version():
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users(), lab=_empty_lab())
    assert dict(zip(d["user_id"], d["instrument_version"])) == {"u1": "v1", "u2": "v2"}


def test_dim_user_carries_the_new_v2_fields():
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users(), lab=_empty_lab())
    for col in ("language", "registration_status", "attempts", "is_returning",
                "safety_alert", "escalation_status"):
        assert col in d.columns, f"{col} missing from dim_user"
    assert d.set_index("user_id").loc["u2", "language"] == "en"


def test_every_dim_user_column_has_a_cohort_policy():
    """The guard is only a guard if it cannot fall behind the schema."""
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users(), lab=_empty_lab())
    for col in d.columns:
        cohort.policy_for(col)   # raises CohortError if unclassified


def _meal_frame():
    return pd.DataFrame({
        "user_id": ["u1", "u2", "u3", "u4"],
        "ts": pd.to_datetime(["2026-07-01"] * 4),
        "usefulness_rating": ["Muy útil", "Nada útil", "Medianamente útil", "Útil"],
        "no_usefulness_reason": ["no", "te confundiste de ciudad",
                                 "faltó info", "Todo bien gracias"],
    })


def test_reason_is_valid_only_for_dissatisfied_ratings():
    """The v2 skip logic misfired: 'why wasn't it useful' was asked of 118
    people, 75 of whom rated it Útil/Muy útil and answered with negations.
    Only the dissatisfied answers are analytically usable."""
    f = export.build_fact_meal(_meal_frame())
    valid = dict(zip(f["user_id"], f["reason_is_valid"]))
    assert valid == {"u1": False, "u2": True, "u3": True, "u4": False}


def test_reason_is_valid_is_false_when_no_reason_given():
    df = _meal_frame().assign(no_usefulness_reason=[None] * 4)
    f = export.build_fact_meal(df)
    assert not f["reason_is_valid"].any()


def test_fact_meal_survives_a_missing_reason_column():
    """A v1-only archive export has no Q12a at all."""
    df = _meal_frame().drop(columns=["no_usefulness_reason"])
    f = export.build_fact_meal(df)
    assert "reason_is_valid" in f.columns
    assert not f["reason_is_valid"].any()


def test_every_fact_meal_column_has_a_cohort_policy():
    f = export.build_fact_meal(_meal_frame())
    for col in f.columns:
        cohort.policy_for(col)


def test_reason_is_valid_ordering_pins_computation_before_translation():
    """CRITICAL: reason_is_valid is computed on Spanish rating values
    BEFORE to_english_meal translates them. If this test fails because
    English labels are being matched, the flag is being computed after
    translation and will silently become all-False. This test pins the
    ordering dependency: the flag MUST be computed on Spanish input."""
    # Input with ENGLISH labels (as if to_english_meal had already run)
    english_frame = pd.DataFrame({
        "user_id": ["u1", "u2", "u3", "u4"],
        "ts": pd.to_datetime(["2026-07-01"] * 4),
        "usefulness_rating": ["Very useful", "Not useful", "Moderately useful", "Useful"],
        "no_usefulness_reason": ["no", "te confundiste de ciudad",
                                 "faltó info", "Todo bien gracias"],
    })
    # The flag won't match on English strings, so all should be False.
    # This proves the code is matching on Spanish input as intended.
    f = export.build_fact_meal(english_frame)
    assert not f["reason_is_valid"].any(), (
        "reason_is_valid matched English labels, meaning it was computed after "
        "translation. It must be computed BEFORE to_english_meal runs, on Spanish input."
    )


def _responses_registration():
    return pd.DataFrame({
        "user_id": ["u1", "u2", "u3", "u4"],
        "ts": pd.to_datetime(["2026-07-25"] * 4),
        "Registration Status": ["Completed", "Completed", "Abandoned",
                                "In Progress"],
        "Registration Started": ["2026-07-25T09:00:00Z"] * 4,
        "Registration Completed": ["2026-07-25T09:05:00Z",
                                   "2026-07-25T09:06:00Z", None, None],
        "Attempts": [1, 2, 3, 1],
        "Language": ["es", "es", "en", "es"],
        "Migrated From v1": [None, None, None, "v1:1"],
    })


def test_agg_registration_funnel_stages_and_counts():
    f = export.build_agg_registration_funnel(_responses_registration())
    # v2 rows: u1, u2 (completed), u3 (abandoned)
    v2_f = f[f["instrument_version"] == "v2"]
    v2_counts = dict(zip(v2_f["stage"], v2_f["n"]))
    assert v2_counts["registration started"] == 3
    assert v2_counts["registration completed"] == 2
    assert v2_counts["abandoned"] == 1
    assert v2_counts["in progress"] == 0
    assert v2_counts["other"] == 0
    # v1 rows: u4 (in progress)
    v1_f = f[f["instrument_version"] == "v1"]
    v1_counts = dict(zip(v1_f["stage"], v1_f["n"]))
    assert v1_counts["registration started"] == 1
    assert v1_counts["registration completed"] == 0
    assert v1_counts["in progress"] == 1


def test_agg_registration_funnel_is_ordered():
    f = export.build_agg_registration_funnel(_responses_registration())
    # Order should be consistent within each cohort
    for cohort_val in ["v1", "v2"]:
        cohort_f = f[f["instrument_version"] == cohort_val]
        if len(cohort_f) > 0:
            assert list(cohort_f["stage_order"]) == sorted(cohort_f["stage_order"])


def test_agg_registration_funnel_pct_is_relative_to_started():
    f = export.build_agg_registration_funnel(_responses_registration())
    # v2 completion rate: 2 out of 3 = 66.67%
    v2_row = f[(f["instrument_version"] == "v2") & (f["stage"] == "registration completed")].iloc[0]
    assert abs(v2_row["pct_of_started"] - 66.7) < 0.2  # Allow small rounding difference


def test_agg_language_splits_by_instrument_version():
    f = export.build_agg_language(_responses_registration())
    got = {(r.language, r.instrument_version): r.n_users
           for r in f.itertuples()}
    assert got[("es", "v2")] == 2
    assert got[("en", "v2")] == 1
    assert got[("es", "v1")] == 1


def test_agg_registration_funnel_empty_without_the_columns():
    """A v1-only archive export has no registration fields."""
    df = pd.DataFrame({"user_id": ["u1"], "ts": pd.to_datetime(["2026-04-01"])})
    f = export.build_agg_registration_funnel(df)
    assert "instrument_version" in f.columns
    assert len(f) == 0


def test_agg_registration_funnel_splits_by_cohort_and_guards_pooling():
    """Split by cohort: v1 all-complete does not contaminate v2 drop-off signal.

    v1 rows are 100% complete by construction (legacy platform never tracked
    partial registration). A pooled completion rate would dilute v2's real
    drop-off signal into rounding error. The table must show separate per-cohort
    rows or the next reader will misinterpret the data.
    """
    # Frame with v1 rows (all complete by construction) + v2 rows with drop-off
    df = pd.DataFrame({
        "user_id": ["v1_user1", "v1_user2", "v2_user1", "v2_user2", "v2_user3"],
        "ts": pd.to_datetime(["2026-01-01", "2026-01-15", "2026-07-20", "2026-07-21", "2026-07-22"]),
        "Registration Status": ["Completed", "Completed", "Completed", "Abandoned", "In Progress"],
        "Registration Started": ["2026-01-01T09:00:00Z"] * 5,
        "Migrated From v1": ["v1:100", "v1:101", None, None, None],
    })

    f = export.build_agg_registration_funnel(df)

    # Split by cohort
    v1_f = f[f["instrument_version"] == "v1"]
    v2_f = f[f["instrument_version"] == "v2"]

    # v1: 2 complete (100%)
    assert (v1_f[v1_f["stage"] == "registration completed"]["n"] == 2).all()
    v1_completion = v1_f[v1_f["stage"] == "registration completed"]["pct_of_started"].iloc[0]
    assert v1_completion == 100.0

    # v2: 1 complete, 1 abandoned, 1 in progress (33.3% complete, not 100%)
    assert (v2_f[v2_f["stage"] == "registration completed"]["n"] == 1).all()
    assert (v2_f[v2_f["stage"] == "abandoned"]["n"] == 1).all()
    assert (v2_f[v2_f["stage"] == "in progress"]["n"] == 1).all()
    v2_completion = v2_f[v2_f["stage"] == "registration completed"]["pct_of_started"].iloc[0]
    assert abs(v2_completion - 33.3) < 0.2  # 1 out of 3

    # Pooled (if it were computed): 3 complete out of 5 = 60% — neither 100% nor 33%
    # This test guards against that pooling by asserting separate rows exist.


def test_agg_registration_funnel_stages_sum_to_started_invariant():
    """Stages must always sum to 'registration started', even with unknown statuses.

    A status the pipeline does not recognise must be visible as 'other', never
    silently dropped.
    """
    df = pd.DataFrame({
        "user_id": ["u1", "u2", "u3", "u4", "u5"],
        "ts": pd.to_datetime(["2026-07-25"] * 5),
        "Registration Status": ["Completed", "Abandoned", "In Progress",
                                "unknown_state", None],  # includes unknown and null
        "Registration Started": ["2026-07-25T09:00:00Z"] * 5,
    })
    f = export.build_agg_registration_funnel(df)
    counts = dict(zip(f["stage"], f["n"]))
    # Stages should sum to "registration started"
    stage_sum = (counts["registration completed"] + counts["abandoned"] +
                 counts["in progress"] + counts["other"])
    assert stage_sum == counts["registration started"]
    assert counts["other"] == 2  # the unknown_state and the null


def test_agg_language_empty_without_the_column():
    """A v1-only archive export has no language selector."""
    df = pd.DataFrame({"user_id": ["u1"], "ts": pd.to_datetime(["2026-04-01"])})
    f = export.build_agg_language(df)
    assert list(f.columns) == ["language", "instrument_version", "n_users"]
    assert len(f) == 0


def test_agg_language_reconciles_with_dim_user_per_cohort():
    """agg_language's per-cohort user counts reconcile with dim_user.

    A user is assigned to ONE cohort (earliest record's instrument_version) in
    both tables. Language is per-record (multilingual users appear in multiple
    rows). This test uses single-language users to check per-cohort totals match.
    """
    # Frame with users in both cohorts; each user speaks one language
    df = pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u3"],
        "ts": pd.to_datetime(["2026-04-01", "2026-07-25", "2026-07-20", "2026-06-15"]),
        "gender_clean": ["Mujer", "Mujer", "Hombre", "Mujer"],
        "age_num": [30.0, 30.0, 28.0, 25.0],
        "city_canon": ["Medellín", "Medellín", "Ipiales", "Bogotá"],
        "n_questions": [2, 2, 1, 1],
        "Migrated From v1": ["v1:100", None, None, None],  # u1 is v1, u2/u3 are v2
        "Language": ["es", "es", "en", "es"],  # each user speaks one language consistently
        "Registration Status": ["Completed", "Completed", "Completed", "Completed"],
        "Registration Started": ["2026-04-01T09:00:00Z"] * 4,
    })
    messages = pd.DataFrame({
        "user_id": ["u1", "u2", "u3"],
        "ts": pd.to_datetime(["2026-04-01", "2026-07-20", "2026-06-15"]),
        "message": ["msg1", "msg2", "msg3"],
        "seq": [0, 0, 0],
        "n_msgs_user": [1, 1, 1],
    })

    du = export.build_dim_user(df, messages, lab=_empty_lab())
    lg = export.build_agg_language(df)

    # dim_user: u1 -> v1, u2/u3 -> v2
    dim_v1 = (du["instrument_version"] == "v1").sum()
    dim_v2 = (du["instrument_version"] == "v2").sum()

    # agg_language per-cohort distinct users must match dim_user per-cohort
    # With single-language users, the sum of n_users per cohort = distinct users per cohort
    lg_v1_total = lg[lg["instrument_version"] == "v1"]["n_users"].sum()
    lg_v2_total = lg[lg["instrument_version"] == "v2"]["n_users"].sum()

    assert lg_v1_total == dim_v1, "v1 per-cohort distinct users must match dim_user"
    assert lg_v2_total == dim_v2, "v2 per-cohort distinct users must match dim_user"


def test_agg_language_counts_multilingual_users_per_language():
    """A multilingual user appears in multiple language rows.

    Language is a per-record attribute. A user using multiple languages appears
    in multiple (language, instrument_version) rows. The sum of n_users > user
    count because multilingual users are counted once per language used.
    """
    # User u1 uses both Spanish and English in the v2 cohort (different records)
    df = pd.DataFrame({
        "user_id": ["u1", "u1"],
        "ts": pd.to_datetime(["2026-07-20", "2026-07-25"]),
        "gender_clean": ["Mujer", "Mujer"],
        "age_num": [30.0, 30.0],
        "city_canon": ["Medellín", "Medellín"],
        "n_questions": [1, 1],
        "Migrated From v1": [None, None],  # v2 user
        "Language": ["es", "en"],
        "Registration Status": ["Completed", "Completed"],
        "Registration Started": ["2026-07-20T09:00:00Z"] * 2,
    })
    messages = pd.DataFrame({
        "user_id": ["u1"],
        "ts": pd.to_datetime(["2026-07-20"]),
        "message": ["msg1"],
        "seq": [0],
        "n_msgs_user": [1],
    })

    du = export.build_dim_user(df, messages, lab=_empty_lab())
    lg = export.build_agg_language(df)

    # dim_user: 1 user (u1) in v2 cohort
    assert (du["instrument_version"] == "v2").sum() == 1

    # agg_language: same user appears in both es/v2 and en/v2 rows
    assert len(lg) == 2  # two language rows
    assert lg["n_users"].sum() == 2  # sum is 2 (user counted twice), but only 1 distinct user
    assert (lg["instrument_version"] == "v2").all()  # both rows are v2
    assert set(lg["language"]) == {"es", "en"}
    # Per-cohort distinct users still matches dim_user (max n_users per cohort)
    assert lg[lg["instrument_version"] == "v2"]["n_users"].max() == 1


def test_every_dim_user_column_has_a_cohort_policy(SD):
    """Regression guard: a column added to dim_user without a POLICY entry
    raises CohortError only when something happens to aggregate it — which can
    be long after the column shipped. `session_minutes` was added and missed
    exactly this way. Fail here instead, where the fix is one line.
    """
    d = export.build_dim_user(SD.responses, SD.messages, lab=_empty_lab())
    missing = []
    for col in d.columns:
        try:
            cohort.policy_for(col)
        except cohort.CohortError:
            missing.append(col)
    assert not missing, (
        f"dim_user columns with no cohort policy: {missing}. "
        "Classify each in POLICY in src/sami/cohort.py.")


def test_write_all_warns_about_tables_it_did_not_write(tmp_path):
    """--skip-nlp leaves the previous run's NLP tables on disk; Power BI loads
    them silently. The run must say so."""
    stale = tmp_path / "nlp_umap.csv"
    stale.write_text("user_id,x,y\na,1,2\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="nlp_umap.csv"):
        export.write_all(tmp_path, {"dim_city": pd.DataFrame({"city_canon": ["Bogotá"]})})
    assert stale.exists(), "the warning must not delete a deliberate skip-NLP artifact"


def test_write_all_is_quiet_when_the_folder_matches_the_run(tmp_path):
    import warnings as _w
    export.write_all(tmp_path, {"dim_city": pd.DataFrame({"city_canon": ["Bogotá"]})})
    with _w.catch_warnings():
        _w.simplefilter("error")  # any warning now becomes a failure
        export.write_all(tmp_path, {"dim_city": pd.DataFrame({"city_canon": ["Cali"]})})


@pytest.fixture
def resolved():
    return {
        0: {"name": "Stuck mid-procedure", "marker": "rumv", "provisional": False},
        1: {"name": "Cluster 1 · visa, cita", "marker": "visa", "provisional": True},
    }


@pytest.fixture
def prof():
    return pd.DataFrame(
        {"n_users": [40, 10], "n_messages": [100, 20], "median_age": [31.0, 27.0],
         "top_terms": ["rumv, biometrico", "visa, cita"]},
        index=pd.Index([0, 1], name="archetype"))


def test_dim_cluster_schema_and_no_category_wording(prof, resolved):
    d = export.build_dim_cluster(prof, resolved)
    assert list(d.columns) == [
        "cluster_id", "name", "top_terms", "n_users", "n_messages", "median_age",
        "display_order", "color_hex", "is_real_cluster", "name_is_provisional"]
    assert not any("categor" in c for c in d.columns)
    assert d["cluster_id"].is_unique


def test_dim_cluster_has_the_no_text_bucket(prof, resolved):
    d = export.build_dim_cluster(prof, resolved).set_index("cluster_id")
    row = d.loc[export.NO_CLUSTER_ID]
    assert row["name"] == export.NO_CLUSTER_NAME
    assert row["is_real_cluster"] is False or row["is_real_cluster"] == False
    assert row["color_hex"] == theme.NO_TEXT_COLOR
    assert row["display_order"] == d["display_order"].max()   # sorts last


def test_dim_cluster_colors_by_size_rank_not_by_id(prof, resolved):
    d = export.build_dim_cluster(prof, resolved).set_index("cluster_id")
    assert d.loc[0, "color_hex"] == theme.CLUSTER_IDENTITY[0]   # biggest = brand teal
    assert d.loc[1, "color_hex"] == theme.CLUSTER_IDENTITY[1]
    assert theme.NO_TEXT_COLOR not in set(d.loc[[0, 1], "color_hex"])


def test_dim_cluster_flags_provisional_names(prof, resolved):
    d = export.build_dim_cluster(prof, resolved).set_index("cluster_id")
    assert bool(d.loc[1, "name_is_provisional"]) is True
    assert bool(d.loc[0, "name_is_provisional"]) is False
    assert bool(d.loc[export.NO_CLUSTER_ID, "name_is_provisional"]) is False


def test_dim_cluster_at_twelve_clusters_still_assigns_distinct_ids():
    big_prof = pd.DataFrame(
        {"n_users": list(range(12, 0, -1)), "n_messages": [10] * 12,
         "median_age": [30.0] * 12, "top_terms": ["t"] * 12},
        index=pd.Index(range(12), name="archetype"))
    big_resolved = {i: {"name": f"C{i}", "marker": "t", "provisional": True}
                    for i in range(12)}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = export.build_dim_cluster(big_prof, big_resolved)
    real = d[d["is_real_cluster"]]
    assert len(real) == 12
    assert theme.NO_TEXT_COLOR not in set(real["color_hex"])
    assert sorted(d["display_order"]) == list(range(len(d)))


def test_dim_user_labels_textless_users_minus_one():
    responses = pd.DataFrame({
        "user_id": ["u1", "u2"], "ts": pd.to_datetime(["2026-06-01", "2026-06-02"]),
        "n_questions": [1, 1], "city_canon": ["Bogotá", "Cali"],
    })
    messages = pd.DataFrame({"user_id": ["u1"], "ts": pd.to_datetime(["2026-06-01"]),
                             "n_msgs_user": [1], "message": ["hola"], "seq": [0]})
    lab = pd.Series([0], index=["u1"], name="archetype")
    du = export.build_dim_user(responses, messages, lab=lab)
    got = dict(zip(du["user_id"], du["cluster_id"]))
    assert got["u1"] == 0
    assert got["u2"] == export.NO_CLUSTER_ID
    assert "dominant_category" not in du.columns


def test_fact_message_has_no_category_column():
    messages = pd.DataFrame({
        "user_id": ["u1"], "ts": pd.to_datetime(["2026-06-01"]),
        "city_canon": ["Bogotá"], "seq": [0], "n_msgs_user": [1],
        "message": ["hola"]})
    lab = pd.Series([0], index=["u1"], name="archetype")
    f = export.build_fact_message(messages, sentiment=None, lab=lab)
    assert "dominant_category" not in f.columns
    assert f["cluster_id"].tolist() == [0]


def test_agg_weekly_cluster_is_long_and_named_without_category():
    ts = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-08"])
    messages = pd.DataFrame({"user_id": ["u1", "u2", "u1"], "cluster_id": [0, 1, 0],
                             "ts": ts, "message": ["a", "b", "c"]})
    w = export.build_agg_weekly_cluster(messages)
    assert list(w.columns) == ["week", "cluster_id", "n"]
    assert w["n"].sum() == len(messages)


def test_agg_priority_matrix_happy_path_excludes_no_text_bucket(prof, resolved):
    """Synthetic replacement for the happy-path coverage that was dropped along
    with the old category-keyed priority-matrix tests: exercises the
    NO_CLUSTER_ID filter at export.py's `real = messages[...]` line (the input
    deliberately contains a -1 row), and checks that a successful return is
    fully labelled from dim_cluster and reports the 2-axis (no-sentiment) score."""
    dim_cluster = export.build_dim_cluster(prof, resolved)
    messages = pd.DataFrame({
        "user_id": ["u1", "u2", "u3"], "cluster_id": [0, 1, export.NO_CLUSTER_ID],
        "message": ["a", "b", "c"],
        "ts": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"])})
    fact_meal = pd.DataFrame({"user_id": ["u1", "u2"], "rating_num": [4.0, 3.0]})
    dim_user = pd.DataFrame({"user_id": ["u1", "u2", "u3"],
                             "cluster_id": [0, 1, export.NO_CLUSTER_ID]})
    pm = export.build_agg_priority_matrix(messages, fact_meal, dim_user, dim_cluster)

    assert export.NO_CLUSTER_ID not in set(pm["cluster_id"])  # the -1 row never reaches the matrix
    assert pm[["name", "top_terms", "color_hex"]].notna().all().all()
    assert (pm["n_axes"] <= 2).all()  # no sentiment axis supplied


def test_agg_priority_matrix_rejects_a_cluster_absent_from_dim_cluster(prof, resolved):
    messages = pd.DataFrame({
        "user_id": ["u1", "u2"], "cluster_id": [0, 99], "message": ["a", "b"],
        "ts": pd.to_datetime(["2026-06-01", "2026-06-02"])})
    fact_meal = pd.DataFrame({"user_id": ["u1"], "rating_num": [4.0]})
    dim_user = pd.DataFrame({"user_id": ["u1", "u2"], "cluster_id": [0, 99]})
    dim_cluster = export.build_dim_cluster(prof, resolved)
    with pytest.raises(KeyError, match="absent from dim_cluster"):
        export.build_agg_priority_matrix(messages, fact_meal, dim_user, dim_cluster)


def test_parity_check_reports_cluster_coverage():
    recon = pd.DataFrame({"metric": ["users", "messages", "users_with_text",
                                     "meal_responses", "repeat_askers_pct"],
                          "value": [2, 1, 1, 1, 50.0]})
    dim_user = pd.DataFrame({"user_id": ["u1", "u2"], "cluster_id": [0, -1],
                             "has_text": [True, False], "is_repeat_asker": [True, False]})
    fact_message = pd.DataFrame({"message_id": ["m1"]})
    fact_meal = pd.DataFrame({"user_id": ["u1"]})
    p = export.build_parity_check(recon, dim_user, fact_message, fact_meal)
    row = p[p["metric"] == "cluster_coverage_pct"].iloc[0]
    assert row["exported_value"] == pytest.approx(50.0)
    assert bool(row["match"]) is False   # 50% is below the 80% threshold
