import numpy as np
import pandas as pd
import pytest
from sami import load_sami, export, cohort


@pytest.fixture(scope="module")
def SD():
    return load_sami()


def test_dim_category_schema():
    d = export.build_dim_category()
    assert list(d.columns) == ["category_key", "category_es", "category_en",
                               "color_hex", "display_order"]
    assert "legal_documentation" in set(d["category_key"])
    assert d["category_key"].is_unique


def test_dim_category_colors_and_order():
    d = export.build_dim_category()
    assert d["color_hex"].str.match(r"^#[0-9a-fA-F]{6}$").all()
    assert sorted(d["display_order"]) == list(range(len(d)))
    unc = d[d["category_key"] == "unclassified"].iloc[0]
    assert unc["color_hex"].lower() == "#b7b7b7"
    assert int(unc["display_order"]) == 7


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
    d = export.build_dim_user(SD.responses, SD.messages)
    for c in ["first_seen", "is_repeat_asker", "intends_to_stay"]:
        assert c in d.columns
    assert d["is_repeat_asker"].dtype == bool
    assert d["intends_to_stay"].dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(d["first_seen"])
    q = SD.responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    assert int(d["is_repeat_asker"].sum()) == int((q >= p90).sum())


def test_fact_message_no_text(SD):
    f = export.build_fact_message(SD.messages)
    assert "message" not in f.columns
    for c in ["message_id", "user_id", "ts", "dominant_category"]:
        assert c in f.columns


def test_meta_run_schema_version():
    m = export.build_meta_run({"responses_file": "x.xlsx"})
    kv = dict(zip(m["key"], m["value"]))
    assert kv["schema_version"] == "2"


def test_parity_check_includes_repeat_askers(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    fmsg = export.build_fact_message(SD.messages)
    fmeal = export.build_fact_meal(SD.meal)
    p = export.build_parity_check(SD.reconciliation, du, fmsg, fmeal)
    assert "repeat_askers_pct" in set(p["metric"])
    assert p["match"].all(), p[~p["match"]]


def test_dim_user_one_row_per_user(SD):
    d = export.build_dim_user(SD.responses, SD.messages)
    assert d["user_id"].is_unique
    assert d["user_id"].nunique() == SD.responses["user_id"].nunique()
    for col in ["user_id", "gender_clean", "age_num", "department",
                "n_msgs_user", "has_text", "cluster_id"]:
        assert col in d.columns
    # has_text == user appears in the message spine
    assert int(d["has_text"].sum()) == SD.messages["user_id"].nunique()
    # cluster_id is null without an NLP label map
    assert d["cluster_id"].isna().all()


_SPANISH_TOKENS = ("Mujer", "Hombre", "Otra", "Desconocida", "meses", "años",
                   "útil", "Recomendación", "Redes sociales", "Sí")


def _no_spanish(frame, cols):
    for col in cols:
        vals = {str(v) for v in frame[col].dropna().unique()}
        bad = [v for v in vals if any(t in v for t in _SPANISH_TOKENS)]
        assert not bad, f"{col}: {bad}"


def test_dim_user_display_values_are_english(SD):
    d = export.build_dim_user(SD.responses, SD.messages)
    _no_spanish(d, ["gender_clean", "minors", "away_duration_canon",
                    "city_duration_canon", "city_canon", "nationality_canon"])
    assert set(d["gender_clean"].dropna()) <= {
        "Woman", "Man", "Transgender", "LGBTQ+", "Prefer not to say", "Other", ""}
    # the ordering columns still carry the sort after the labels are translated
    if d["away_duration_order"].notna().any():
        pairs = d.dropna(subset=["away_duration_order"])
        assert pairs.groupby("away_duration_canon")["away_duration_order"].nunique().eq(1).all()


def test_duration_scales_name_their_non_response_bucket(SD):
    d = export.build_dim_user(SD.responses, SD.messages)
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
    assert qa.pii_scan(export.build_dim_user(SD.responses, SD.messages)) == []


def test_fact_message_grain_and_join(SD):
    f = export.build_fact_message(SD.messages)
    assert len(f) == len(SD.messages)
    assert f["message_id"].is_unique
    assert f["message_id"].str.match(r"^[0-9a-f]{16}$").all()  # 16-char hex hash
    assert f["sentiment_label"].isna().all()   # no sentiment passed
    assert f["cluster_id"].isna().all()


def test_fact_message_sentiment_join(SD):
    # synthetic sentiment aligned to the messages index
    sent = pd.DataFrame({"label": ["negative"] * len(SD.messages)}, index=SD.messages.index)
    f = export.build_fact_message(SD.messages, sentiment=sent)
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


def test_agg_weekly_category_long(SD):
    w = export.build_agg_weekly_category(SD.messages)
    assert set(w.columns) == {"week", "category", "n"}


def test_agg_daily_volume(SD):
    d = export.build_agg_daily_volume(SD.messages)
    assert set(d.columns) == {"day", "n"}
    assert d["n"].sum() == SD.messages["ts"].notna().sum()


def test_agg_priority_matrix_no_sentiment(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    fm = export.build_fact_meal(SD.meal)
    pm = export.build_agg_priority_matrix(SD.messages, fm, du)
    assert "category" in pm.columns and "unmet_need" in pm.columns
    assert "unclassified" not in set(pm["category"])   # excluded
    assert (pm["n_axes"] <= 2).all()                    # no sentiment axis


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


def test_dim_cluster_synthetic():
    prof = pd.DataFrame(
        {"n_users": [10, 5], "n_messages": [40, 12],
         "median_age": [30.0, 28.0],
         "top_categories": ["legal (50%)", "employment (40%)"]},
        index=pd.Index([0, 1], name="archetype"))
    names = {0: "Doc-seeker", 1: "Job-seeker"}
    d = export.build_dim_cluster(prof, names)
    assert list(d.columns) == ["cluster_id", "name", "n_users",
                               "n_messages", "median_age", "top_categories"]
    assert d.loc[d["cluster_id"] == 0, "name"].iloc[0] == "Doc-seeker"


def test_nlp_voices_picks_marker_quote():
    from sami import taxonomy
    cid = sorted(taxonomy.ARCHETYPE_NAMES)[0]
    marker = taxonomy.ARCHETYPE_NAMES[cid]["marker"]
    names = {cid: taxonomy.ARCHETYPE_NAMES[cid]["name"]}
    msg = ((marker + " ") * 20)[:150]          # 60-190 chars, contains the marker
    msgs_lab = pd.DataFrame({"archetype": [cid, cid], "user_id": ["u1", "u2"],
                             "seq": [0, 1], "message": [msg, "corto"]})
    v = export.build_nlp_voices(msgs_lab, names)
    assert list(v.columns) == ["cluster_id", "name", "message"]
    assert v.loc[0, "message"] == msg
    assert v.loc[0, "name"] == names[cid]


def test_nlp_voices_dash_fallback_when_no_match():
    from sami import taxonomy
    cid = sorted(taxonomy.ARCHETYPE_NAMES)[0]
    msgs_lab = pd.DataFrame({"archetype": [cid], "user_id": ["u1"],
                             "seq": [0], "message": ["corto"]})   # too short, no marker
    v = export.build_nlp_voices(msgs_lab, {cid: "X"})
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
    du = export.build_dim_user(SD.responses, SD.messages)
    fmsg = export.build_fact_message(SD.messages)
    fmeal = export.build_fact_meal(SD.meal)
    p = export.build_parity_check(SD.reconciliation, du, fmsg, fmeal)
    assert set(p.columns) == {"metric", "exported_value", "reconciliation_value", "match"}
    assert p["match"].all(), p[~p["match"]]


def test_write_all_writes_and_manifests(tmp_path):
    tables = {
        "dim_category": export.build_dim_category(),
        "tiny": pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}),
    }
    manifest = export.write_all(tmp_path, tables)
    assert (tmp_path / "dim_category.csv").exists()
    assert (tmp_path / "tiny.csv").exists()
    assert (tmp_path / "_manifest.csv").exists()
    assert set(manifest["table"]) == {"dim_category", "tiny"}
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
        "dominant_category": ["employment", "employment", "employment"],
    })


def test_message_id_is_stable_when_other_users_are_added():
    """Regression: message_id was messages.reset_index(), a POSITIONAL id.
    The spine is sorted by (user_id, ts), so one new user re-numbered every
    row — silently re-pointing anything keyed on it."""
    base = _spine()
    before = export.build_fact_message(base)
    grown = pd.concat([
        pd.DataFrame({
            "user_id": ["u0"], "ts": pd.to_datetime(["2026-03-01"]),
            "message": ["mensaje nuevo"], "seq": [0], "n_msgs_user": [1],
            "city_canon": ["Bogotá"], "dominant_category": ["services"],
        }), base]).reset_index(drop=True)
    after = export.build_fact_message(grown)

    got = after.set_index("user_id").loc["u2", "message_id"]
    want = before.set_index("user_id").loc["u2", "message_id"]
    assert got == want


def test_message_id_is_unique_per_row():
    f = export.build_fact_message(_spine())
    assert f["message_id"].is_unique


def test_message_id_differs_for_identical_text_from_different_users():
    df = pd.DataFrame({
        "user_id": ["u1", "u2"], "ts": pd.to_datetime(["2026-04-01"] * 2),
        "message": ["gracias", "gracias"], "seq": [0, 0], "n_msgs_user": [1, 1],
        "city_canon": ["Medellín"] * 2, "dominant_category": ["services"] * 2,
    })
    f = export.build_fact_message(df)
    assert f["message_id"].nunique() == 2


def test_message_id_contains_no_pii():
    f = export.build_fact_message(_spine())
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
        "dominant_category": ["employment", "employment"],
    })
    before = export.build_fact_message(base_messages)
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
            "dominant_category": ["employment"],
        }), base_messages
    ]).sort_values(["user_id", "ts"]).reset_index(drop=True)

    # Recompute seq (mimicking load.load_messages behavior)
    backfilled["seq"] = backfilled.groupby("user_id").cumcount()

    after = export.build_fact_message(backfilled)

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
        "dominant_category": ["employment", "unclassified"],
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
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users())
    assert dict(zip(d["user_id"], d["instrument_version"])) == {"u1": "v1", "u2": "v2"}


def test_dim_user_carries_the_new_v2_fields():
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users())
    for col in ("language", "registration_status", "attempts", "is_returning",
                "safety_alert", "escalation_status"):
        assert col in d.columns, f"{col} missing from dim_user"
    assert d.set_index("user_id").loc["u2", "language"] == "en"


def test_every_dim_user_column_has_a_cohort_policy():
    """The guard is only a guard if it cannot fall behind the schema."""
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users())
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
