# run_pipeline.py
"""Father script: run the whole SAMI pipeline and regenerate the exports/ gold layer.

    python run_pipeline.py                 # full run -> all tables
    python run_pipeline.py --check         # preflight only: can this machine run it?

NLP is not optional: clustering IS the pipeline's categorisation, so a run
without it would write a dashboard with nothing to slice by.

Runs on GPU when one is present and on CPU otherwise — the CPU path is slower
(see preflight.CPU_RUNTIME_HINT) but produces the same tables. Preflight runs
before any work, so a missing file, absent salt or unreachable model download is
reported in seconds instead of twenty minutes in.

Every table Power BI cannot recompute (UMAP, c-TF-IDF, confusion, funnel,
priority matrix, entity extraction) is written here; simple aggregates are left
for Power BI to derive from dim_user / fact_message / fact_meal.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from sami import (load_sami, nlp, clusters, validation, metrics, taxonomy,  # noqa: E402
                  export, preflight, progress, config, schema, datasets, theme,
                  subclusters)

RANDOM_STATE = 0
# Stage count for the [i/n] counter: 4 shared (load, dim/fact, aggregates,
# write) + 6 NLP-only.
_STAGES_BASE, _STAGES_NLP = 4, 6


def _nlp_tables(SD, pr):
    """Run the NLP once and build every NLP-dependent table. Returns
    (tables_dict, nlp_meta_dict, sentiment_frame, lab_series, dim_cluster_frame,
    sub_lab_series, sub_names_dict)."""
    docs = nlp.user_documents(SD.messages)
    with pr.stage(f"embedding {len(docs)} user documents"):
        X = nlp.embed_documents(docs["doc"].tolist())

    with pr.stage("choosing k and clustering"):
        scan = clusters.k_scan(X, k_range=range(4, 13), random_state=RANDOM_STATE)
        stab_curve = clusters.stability_curve(X, k_range=range(3, 13), n_boot=30,
                                              random_state=RANDOM_STATE)
        K = clusters.choose_k(scan, stability_by_k=stab_curve)
        labels = KMeans(n_clusters=K, n_init=10, random_state=RANDOM_STATE).fit(X).labels_
        lab = pd.Series(labels, index=docs["user_id"].values, name="archetype")

    with pr.stage("cluster terms + 2D projection"):
        terms = clusters.ctfidf_terms(docs["doc"].tolist(), labels, top_n=40)
        resolved = taxonomy.resolve_cluster_names(terms)
        XY = clusters.project_2d(X, method="umap", random_state=RANDOM_STATE)

    with pr.stage("sub-clustering inside each cluster"):
        sub_lab, sub_meta = subclusters.subcluster_all(
            X, lab, docs["user_id"].values, random_state=RANDOM_STATE)
        sub_docs = docs.assign(sub=docs["user_id"].map(sub_lab.to_dict()))
        sub_terms_raw = clusters.ctfidf_terms(
            sub_docs["doc"].tolist(), sub_docs["sub"].values, top_n=40)
        sub_terms = subclusters.exclusive_terms(sub_terms_raw)
        resolved_sub = taxonomy.resolve_names(
            sub_terms, taxonomy.SUBCLUSTER_NAMES, kind="subcluster")
        sub_names = {sid: v["name"] for sid, v in resolved_sub.items()}
        sub_names[subclusters.NO_SUBCLUSTER_ID] = subclusters.NO_SUBCLUSTER_NAME

    # On CPU this is by far the longest stage — per-message inference over the
    # full spine, where embedding is only one pass over ~800 user documents.
    with pr.stage(f"sentiment over {len(SD.messages)} messages"):
        sent = nlp.sentiment_messages(SD.messages)

    with pr.stage("archetype profiles + tone validation + stability"):
        prof = clusters.archetype_profiles(lab, SD.responses, SD.messages, terms=terms)
        msgs_lab = SD.messages.merge(lab, left_on="user_id", right_index=True, how="inner")
        analyst = pd.read_csv("validation/tone_labels_analyst.csv", encoding="utf-8")
        # align_gold matches on message_id and raises if any label is unresolvable.
        # The previous `sent.loc[analyst["message_id"]]` was a POSITIONAL lookup
        # that silently compared unrelated messages -- see validation.align_gold.
        report = validation.validation_report(
            analyst["label_analyst"],
            validation.align_gold(analyst["message_id"], SD.messages, sent))
        stab = clusters.stability_ari(X, K, n_boot=50, random_state=RANDOM_STATE)
        dev = nlp.device_report()

    dim_cluster = export.build_dim_cluster(prof, resolved)
    dim_subcluster = export.build_dim_subcluster(
        sub_lab, SD.messages, resolved_sub, sub_terms, dim_cluster, sub_meta)
    tables = {
        "dim_cluster": dim_cluster,
        "dim_subcluster": dim_subcluster,
        "nlp_umap": export.build_nlp_umap(XY, labels, docs["user_id"].values),
        "nlp_cluster_terms": export.build_nlp_cluster_terms(terms),
        "nlp_subcluster_terms": export.build_nlp_subcluster_terms(sub_terms),
        "nlp_emergent_themes": export.build_nlp_emergent_themes(SD.messages),
        "nlp_tone_confusion": export.build_nlp_tone_confusion(report),
        "nlp_voices": export.build_nlp_voices(
            msgs_lab, resolved,
            terms_by_cluster=dict(zip(dim_cluster["cluster_id"],
                                      dim_cluster["top_terms"]))),
    }
    split_aris = [m["stability_ari"] for m in sub_meta.values() if m["is_split"]]
    nlp_meta = {
        "embed_model": dev["embed_model"], "sentiment_model": dev["sentiment_model"],
        "chosen_k": K, "stability_ari": round(stab["mean_ari"], 3),
        "tone_kappa": round(report["kappa"], 3),
        "tone_gate_passed": report["gate_passed"], "sentiment_quotable": report["gate_passed"],
        "nlp_included": True,
        "k_soft_cap": theme.K_SOFT_CAP,
        "n_provisional_names": sum(1 for v in resolved.values() if v["provisional"]),
        # Subcategories. `subcluster_stability_ari` is the mean over SPLIT
        # parents only and is exported precisely because children are less
        # stable than parents -- a poor value here is the signal to revisit the
        # discovered-children decision, not a number to hide.
        "n_subclusters": int((dim_subcluster["subcluster_id"] >= 0).sum()),
        "n_parents_split": sum(1 for m in sub_meta.values() if m["is_split"]),
        "n_provisional_subnames": sum(1 for v in resolved_sub.values()
                                      if v["provisional"]),
        "subcluster_min_users": subclusters.SUBCLUSTER_MIN_USERS,
        "subcluster_stability_ari": (round(float(np.mean(split_aris)), 3)
                                     if split_aris else None),
    }
    return tables, nlp_meta, sent, lab, dim_cluster, sub_lab, sub_names


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Regenerate the SAMI exports/ gold layer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run --check first on a new machine: it verifies data, salt, "
               "packages, device and model cache without doing any work.")
    ap.add_argument("--out", default="exports")
    ap.add_argument("--check", action="store_true",
                    help="run preflight checks and exit")
    ap.add_argument("--responses", default=None,
                    help="path to the responses .xlsx "
                         "(default: newest in datasets/responses/)")
    ap.add_argument("--meal", default=None,
                    help="path to the MEAL .xlsx "
                         "(default: newest in datasets/meal/)")
    args = ap.parse_args(argv)

    ctx = preflight.Context(
        responses_path=Path(args.responses) if args.responses else datasets.resolve("responses"),
        meal_path=Path(args.meal) if args.meal else datasets.resolve("meal"),
        out_dir=Path(args.out),
    )
    results = preflight.run_all(ctx)
    print("preflight:", file=sys.stderr)
    print(preflight.render(results), file=sys.stderr)
    print(preflight.summarize(results), file=sys.stderr)
    blocked = any(r.failed for r in results)
    if args.check:
        return 1 if blocked else 0
    if blocked:
        print("\nRefusing to start — fix the FAIL items above, then re-run. "
              "(`--check` re-runs just these checks.)", file=sys.stderr)
        return 1

    pr = progress.Progress(_STAGES_BASE + _STAGES_NLP)

    with pr.stage("loading responses + MEAL"):
        for role, override in (("responses", args.responses), ("meal", args.meal)):
            chosen = override if override else datasets.describe(role)
            print(f"  {role + ':':<11}{chosen}", file=sys.stderr)
        SD = load_sami(responses_path=args.responses, meal_path=args.meal)

    nlp_tables, nlp_meta, sent, lab, dim_cluster, sub_lab, sub_names = _nlp_tables(SD, pr)

    with pr.stage("building dimension + fact tables"):
        # Every message inherits its author's cluster. This is the join that
        # makes clusters the categorisation axis for message-grain visuals.
        SD.messages["cluster_id"] = (SD.messages["user_id"].map(lab.to_dict())
                                     .fillna(export.NO_CLUSTER_ID).astype(int))
        real_msgs = SD.messages[SD.messages["cluster_id"] != export.NO_CLUSTER_ID]
        neg_by_cluster = metrics.negative_by_cluster(real_msgs, sent)

        dim_user = export.build_dim_user(SD.responses, SD.messages, lab=lab,
                                         sub_lab=sub_lab, sub_names=sub_names)
        fact_message = export.build_fact_message(SD.messages, sentiment=sent, lab=lab,
                                                 sub_lab=sub_lab, sub_names=sub_names)
        fact_meal = export.build_fact_meal(SD.meal)

    with pr.stage("aggregate tables"):
        tables = {
            "dim_user": dim_user,
            "fact_message": fact_message,
            "fact_meal": fact_meal,
            "dim_city": export.build_dim_city(),
            "dim_quadrant": export.build_dim_quadrant(),
            "agg_funnel": export.build_agg_funnel(SD.responses, SD.messages, SD.meal),
            "agg_registration_funnel": export.build_agg_registration_funnel(SD.responses),
            "agg_language": export.build_agg_language(SD.responses),
            "agg_entities_by_kind": export.build_agg_entities_by_kind(SD.messages),
            "agg_weekly_cluster": export.build_agg_weekly_cluster(SD.messages),
            "agg_daily_volume": export.build_agg_daily_volume(SD.messages),
            "agg_weekly_rating": export.build_agg_weekly_rating(fact_meal),
            "agg_priority_matrix": export.build_agg_priority_matrix(
                SD.messages, fact_meal, dim_user, dim_cluster,
                neg_by_cluster=neg_by_cluster),
            "meta_run": export.build_meta_run(SD.run_meta, nlp_meta=nlp_meta),
            "parity_check": export.build_parity_check(
                SD.reconciliation, dim_user, fact_message, fact_meal,
                nlp_tables["dim_subcluster"]),
        }
        tables.update(nlp_tables)

    with pr.stage("PII scan + write"):
        manifest = export.write_all(args.out, tables)

    parity = tables["parity_check"]
    print(manifest.to_string(index=False))
    print("\nparity_check:")
    print(parity.to_string(index=False))
    if not parity["match"].all():
        print("\nPARITY FAILED — the exported tables disagree with the "
              "reconciliation counts. Do not publish this run.", file=sys.stderr)
        return 1
    print(f"\nwrote {len(tables)} tables to {args.out}/ · total {pr.total_elapsed()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except schema.SchemaError as exc:
        # A source export drifted mid-run. Print the contract message (which
        # already carries file + fix) instead of a traceback.
        print(f"\nSchema error:\n{exc}", file=sys.stderr)
        raise SystemExit(1)
