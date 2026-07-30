# run_pipeline.py
"""Father script: run the whole SAMI pipeline and regenerate the exports/ gold layer.

    python run_pipeline.py                 # full run incl. NLP -> all tables
    python run_pipeline.py --skip-nlp      # fast run, non-NLP tables only
    python run_pipeline.py --check         # preflight only: can this machine run it?

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

import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from sami import (load_sami, nlp, clusters, validation, metrics, taxonomy,  # noqa: E402
                  export, preflight, progress, config, schema, datasets)

RANDOM_STATE = 0
# Stage count for the [i/n] counter: 4 shared (load, dim/fact, aggregates,
# write) + 5 NLP-only.
_STAGES_BASE, _STAGES_NLP = 4, 5


def _nlp_tables(SD, pr):
    """Run the NLP once and build every NLP-dependent table. Returns
    (tables_dict, nlp_meta_dict, sentiment_frame, lab_series)."""
    docs = nlp.user_documents(SD.messages)
    with pr.stage(f"embedding {len(docs)} user documents"):
        X = nlp.embed_documents(docs["doc"].tolist())

    with pr.stage("choosing k and clustering"):
        scan = clusters.k_scan(X, k_range=range(4, 13), random_state=RANDOM_STATE)
        stab_curve = clusters.stability_curve(X, k_range=range(3, 9), n_boot=30,
                                              random_state=RANDOM_STATE)
        K = clusters.choose_k(scan, stability_by_k=stab_curve)
        labels = KMeans(n_clusters=K, n_init=10, random_state=RANDOM_STATE).fit(X).labels_
        lab = pd.Series(labels, index=docs["user_id"].values, name="archetype")

    with pr.stage("cluster terms + 2D projection"):
        terms = clusters.ctfidf_terms(docs["doc"].tolist(), labels, top_n=40)
        taxonomy.assert_archetype_mapping(terms)
        names = {c: taxonomy.ARCHETYPE_NAMES[c]["name"] for c in sorted(terms)}
        XY = clusters.project_2d(X, method="umap", random_state=RANDOM_STATE)

    # On CPU this is by far the longest stage — per-message inference over the
    # full spine, where embedding is only one pass over ~800 user documents.
    with pr.stage(f"sentiment over {len(SD.messages)} messages"):
        sent = nlp.sentiment_messages(SD.messages)

    with pr.stage("archetype profiles + tone validation + stability"):
        prof = clusters.archetype_profiles(lab, SD.responses, SD.messages)
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
    ap = argparse.ArgumentParser(
        description="Regenerate the SAMI exports/ gold layer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run --check first on a new machine: it verifies data, salt, "
               "packages, device and model cache without doing any work.")
    ap.add_argument("--out", default="exports")
    ap.add_argument("--skip-nlp", action="store_true",
                    help="skip the NLP stages (no model download, much faster)")
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
        skip_nlp=args.skip_nlp,
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

    pr = progress.Progress(_STAGES_BASE + (0 if args.skip_nlp else _STAGES_NLP))

    with pr.stage("loading responses + MEAL"):
        for role, override in (("responses", args.responses), ("meal", args.meal)):
            chosen = override if override else datasets.describe(role)
            print(f"  {role + ':':<11}{chosen}", file=sys.stderr)
        SD = load_sami(responses_path=args.responses, meal_path=args.meal)

    sent = lab = None
    nlp_tables, nlp_meta = {}, {"nlp_included": False,
                               "tone_gate_passed": False, "sentiment_quotable": False}
    if not args.skip_nlp:
        nlp_tables, nlp_meta, sent, lab = _nlp_tables(SD, pr)

    with pr.stage("building dimension + fact tables"):
        neg_by_cat = None
        if sent is not None:
            msgs_pm = SD.messages[SD.messages["dominant_category"] != "unclassified"]
            neg_by_cat = metrics.negative_by_category(msgs_pm, sent)

        dim_user = export.build_dim_user(SD.responses, SD.messages, lab=lab)
        fact_message = export.build_fact_message(SD.messages, sentiment=sent, lab=lab)
        fact_meal = export.build_fact_meal(SD.meal)

    with pr.stage("aggregate tables"):
        tables = {
            "dim_user": dim_user,
            "fact_message": fact_message,
            "fact_meal": fact_meal,
            "dim_category": export.build_dim_category(),
            "dim_city": export.build_dim_city(),
            "agg_funnel": export.build_agg_funnel(SD.responses, SD.messages, SD.meal),
            "agg_registration_funnel": export.build_agg_registration_funnel(SD.responses),
            "agg_language": export.build_agg_language(SD.responses),
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
    print(f"\nwrote {len(tables)} tables to {args.out}/ · "
          f"NLP={'no' if args.skip_nlp else 'yes'} · total {pr.total_elapsed()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except schema.SchemaError as exc:
        # A source export drifted mid-run. Print the contract message (which
        # already carries file + fix) instead of a traceback.
        print(f"\nSchema error:\n{exc}", file=sys.stderr)
        raise SystemExit(1)
