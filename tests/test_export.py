import numpy as np
import pandas as pd
import pytest
from sami import load_sami, export


@pytest.fixture(scope="module")
def SD():
    return load_sami()


def test_dim_category_schema():
    d = export.build_dim_category()
    assert list(d.columns) == ["category_key", "category_es", "category_en"]
    assert "legal_documentation" in set(d["category_key"])
    assert d["category_key"].is_unique


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


def test_dim_user_no_pii(SD):
    from sami import qa
    assert qa.pii_scan(export.build_dim_user(SD.responses, SD.messages)) == []


def test_fact_message_grain_and_join(SD):
    f = export.build_fact_message(SD.messages)
    assert len(f) == len(SD.messages)
    assert f["message_id"].is_unique
    assert list(f["message_id"]) == list(SD.messages.index)
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


def test_agg_city(SD):
    du = export.build_dim_user(SD.responses, SD.messages)
    c = export.build_agg_city(du)
    assert list(c.columns) == ["city_canon", "department", "n_users"]
    assert c["n_users"].sum() == len(du)


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
