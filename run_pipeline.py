# run_pipeline.py
"""Father script: run the whole SAMI pipeline and regenerate the exports/ gold layer.

    python run_pipeline.py                 # full run incl. GPU NLP -> all tables
    python run_pipeline.py --skip-nlp      # fast CPU run, non-NLP tables only

Every table Power BI cannot recompute (UMAP, c-TF-IDF, confusion, funnel,
priority matrix, entity extraction) is written here; simple aggregates are left
for Power BI to derive from dim_user / fact_message / fact_meal.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from sami import load_sami, nlp, clusters, validation, metrics, taxonomy, export  # noqa: E402

RANDOM_STATE = 0


def _nlp_tables(SD):
    """Run the GPU NLP once and build every NLP-dependent table. Returns
    (tables_dict, nlp_meta_dict, sentiment_frame, lab_series)."""
    docs = nlp.user_documents(SD.messages)
    X = nlp.embed_documents(docs["doc"].tolist())

    scan = clusters.k_scan(X, k_range=range(4, 13), random_state=RANDOM_STATE)
    stab_curve = clusters.stability_curve(X, k_range=range(3, 9), n_boot=30,
                                          random_state=RANDOM_STATE)
    K = clusters.choose_k(scan, stability_by_k=stab_curve)
    labels = KMeans(n_clusters=K, n_init=10, random_state=RANDOM_STATE).fit(X).labels_
    lab = pd.Series(labels, index=docs["user_id"].values, name="archetype")

    terms = clusters.ctfidf_terms(docs["doc"].tolist(), labels, top_n=40)
    taxonomy.assert_archetype_mapping(terms)
    names = {c: taxonomy.ARCHETYPE_NAMES[c]["name"] for c in sorted(terms)}
    XY = clusters.project_2d(X, method="umap", random_state=RANDOM_STATE)

    sent = nlp.sentiment_messages(SD.messages)
    prof = clusters.archetype_profiles(lab, SD.responses, SD.messages)
    msgs_lab = SD.messages.merge(lab, left_on="user_id", right_index=True, how="inner")

    analyst = pd.read_csv("validation/tone_labels_analyst.csv", encoding="utf-8")
    report = validation.validation_report(
        analyst["label_analyst"], sent.loc[analyst["message_id"], "label"])
    stab = clusters.stability_ari(X, K, n_boot=50, random_state=RANDOM_STATE)
    dev = nlp.device_report()

    tables = {
        "dim_cluster": export.build_dim_cluster(prof, names),
        "nlp_umap": export.build_nlp_umap(XY, labels, docs["user_id"].values),
        "nlp_cluster_terms": export.build_nlp_cluster_terms(terms),
        "nlp_emergent_themes": export.build_nlp_emergent_themes(SD.messages),
        "nlp_tone_confusion": export.build_nlp_tone_confusion(report),
        "nlp_voices": export.build_nlp_voices(msgs_lab, names),
    }
    nlp_meta = {
        "embed_model": dev["embed_model"], "sentiment_model": dev["sentiment_model"],
        "chosen_k": K, "stability_ari": round(stab["mean_ari"], 3),
        "tone_kappa": round(report["kappa"], 3),
        "tone_gate_passed": report["gate_passed"], "sentiment_quotable": report["gate_passed"],
        "nlp_included": True,
    }
    return tables, nlp_meta, sent, lab


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Regenerate the SAMI exports/ gold layer.")
    ap.add_argument("--out", default="exports")
    ap.add_argument("--skip-nlp", action="store_true")
    ap.add_argument("--responses", default=None)
    ap.add_argument("--meal", default=None)
    args = ap.parse_args(argv)

    SD = load_sami(responses_path=args.responses, meal_path=args.meal)

    sent = lab = None
    nlp_tables, nlp_meta = {}, {"nlp_included": False,
                               "tone_gate_passed": False, "sentiment_quotable": False}
    if not args.skip_nlp:
        nlp_tables, nlp_meta, sent, lab = _nlp_tables(SD)

    neg_by_cat = None
    if sent is not None:
        msgs_pm = SD.messages[SD.messages["dominant_category"] != "unclassified"]
        neg_by_cat = metrics.negative_by_category(msgs_pm, sent)

    dim_user = export.build_dim_user(SD.responses, SD.messages, lab=lab)
    fact_message = export.build_fact_message(SD.messages, sentiment=sent, lab=lab)
    fact_meal = export.build_fact_meal(SD.meal)

    tables = {
        "dim_user": dim_user,
        "fact_message": fact_message,
        "fact_meal": fact_meal,
        "dim_category": export.build_dim_category(),
        "dim_city": export.build_dim_city(),
        "agg_funnel": export.build_agg_funnel(SD.responses, SD.messages, SD.meal),
        "agg_entities_by_kind": export.build_agg_entities_by_kind(SD.messages),
        "agg_weekly_category": export.build_agg_weekly_category(SD.messages),
        "agg_daily_volume": export.build_agg_daily_volume(SD.messages),
        "agg_weekly_rating": export.build_agg_weekly_rating(fact_meal),
        "agg_priority_matrix": export.build_agg_priority_matrix(
            SD.messages, fact_meal, dim_user, neg_by_cat=neg_by_cat),
        "meta_run": export.build_meta_run(SD.run_meta, nlp_meta=nlp_meta),
        "parity_check": export.build_parity_check(
            SD.reconciliation, dim_user, fact_message, fact_meal),
    }
    tables.update(nlp_tables)

    manifest = export.write_all(args.out, tables)
    parity = tables["parity_check"]
    print(manifest.to_string(index=False))
    print("\nparity_check:")
    print(parity.to_string(index=False))
    if not parity["match"].all():
        print("\nPARITY FAILED", file=sys.stderr)
        return 1
    print(f"\nwrote {len(tables)} tables to {args.out}/ · NLP={'no' if args.skip_nlp else 'yes'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
