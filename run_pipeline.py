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
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from sami import (load_sami, nlp, clusters, validation, metrics, taxonomy,  # noqa: E402
                  export, preflight, progress, config, schema, datasets, theme,
                  subclusters, qa, bot_replies, redact)

RANDOM_STATE = 0
# Stage count for the [i/n] counter: 4 shared (load, dim/fact, aggregates,
# write) + 7 NLP-only + 1 optional (bot log).
_STAGES_BASE, _STAGES_NLP = 5, 7

GAP_GOLD_PATH = Path("validation/gap_gold_labels.csv")


def _warn_entity_coverage(coverage: float, n_candidates: int) -> None:
    """Soft drift gate: loud, and never fatal.

    Same posture as `name_is_provisional` — an unmaintained dictionary is a
    thing to flag, not a reason to refuse to produce the export.
    """
    if coverage >= qa.ENTITY_COVERAGE_WARN:
        return
    warnings.warn(
        f"entity coverage is {coverage*100:.1f}%, below the "
        f"{qa.ENTITY_COVERAGE_WARN*100:.0f}% drift floor. The dictionary is "
        f"missing vocabulary users are actually using. Read the top rows of "
        f"nlp_entity_candidates ({n_candidates} candidate term(s) this run) and "
        f"add entries to the entity registry ({config.entities_path()}).",
        stacklevel=2)


def _nlp_tables(SD, pr, k_override: int | None = None):
    """Run the NLP once and build every NLP-dependent table. Returns
    (tables_dict, nlp_meta_dict, sentiment_frame, emotion_frame, lab_series,
    dim_cluster_frame, sub_lab_series, sub_names_dict).

    `k_override` pins the archetype count instead of letting the stability
    curve choose it -- e.g. to hold the cluster count steady across a data
    refresh when the extra resolution a bigger corpus newly supports isn't
    wanted yet. The scan/stability curve are still computed so `nlp_meta`
    keeps reporting the same diagnostics either way.
    """
    docs = nlp.user_documents(SD.messages)
    with pr.stage(f"embedding {len(docs)} user documents"):
        X = nlp.embed_documents(docs["doc"].tolist())

    with pr.stage("choosing k and clustering"):
        scan = clusters.k_scan(X, k_range=range(4, 13), random_state=RANDOM_STATE)
        stab_curve = clusters.stability_curve(X, k_range=range(3, 13), n_boot=30,
                                              random_state=RANDOM_STATE)
        K = k_override if k_override is not None else clusters.choose_k(
            scan, stability_by_k=stab_curve)
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

    with pr.stage(f"emotion over {len(SD.messages)} messages"):
        emo = nlp.emotion_messages(SD.messages)

    with pr.stage("archetype profiles + tone validation + stability"):
        prof = clusters.archetype_profiles(lab, SD.responses, SD.messages, terms=terms)
        msgs_lab = SD.messages.merge(lab, left_on="user_id", right_index=True, how="inner")
        # For the word-cloud tables' per-user regrain (schema v16) -- see
        # export._terms_frame_by_user.
        msgs_sub_lab = SD.messages.merge(sub_lab.rename("sub_lab"),
                                         left_on="user_id", right_index=True, how="inner")
        # The gold set is two independent blind passes, not one: an analyst
        # labelled 178 messages; a reviewer, blind to both the analyst's labels
        # and the model's predictions, independently re-labelled those 178 plus
        # 200 newly drawn messages (n=378). Inter-annotator agreement on the
        # 178 overlap is kappa=0.731 (93.3% raw agreement), so once the reviewer
        # file exists it is trusted as the human record IN FULL -- it carries
        # its own message_id list and does not need the analyst's 178 to
        # resolve ids. See notebooks/03_text_insights_nlp.ipynb §4 for the
        # full account of why (the earlier analyst-only kappa=0.604 turned out
        # to be an optimistic small-sample estimate).
        analyst = pd.read_csv("validation/tone_labels_analyst.csv", encoding="utf-8")
        reviewer_path = Path("validation/tone_labels_reviewer.csv")
        if reviewer_path.exists():
            reviewer = pd.read_csv(reviewer_path, encoding="utf-8")
            gold_ids, human = reviewer["message_id"], reviewer["label_reviewer"]
        else:
            gold_ids, human = analyst["message_id"], analyst["label_analyst"]
        # align_gold matches on message_id and raises if any label is unresolvable.
        # The previous `sent.loc[analyst["message_id"]]` was a POSITIONAL lookup
        # that silently compared unrelated messages -- see validation.align_gold.
        aligned_model = validation.align_gold(gold_ids, SD.messages, sent)
        report = validation.validation_report(human, aligned_model)
        stab = clusters.stability_ari(X, K, n_boot=50, random_state=RANDOM_STATE)
        dev = nlp.device_report()

    dim_cluster = export.build_dim_cluster(prof, resolved)
    dim_subcluster = export.build_dim_subcluster(
        sub_lab, SD.messages, resolved_sub, sub_terms, dim_cluster, sub_meta)
    tables = {
        "dim_cluster": dim_cluster,
        "dim_subcluster": dim_subcluster,
        "nlp_umap": export.build_nlp_umap(XY, labels, docs["user_id"].values),
        "nlp_cluster_terms": export.build_nlp_cluster_terms(terms, msgs_lab=msgs_lab),
        "nlp_subcluster_terms": export.build_nlp_subcluster_terms(
            sub_terms, msgs_sub_lab=msgs_sub_lab),
        "nlp_emergent_themes": export.build_nlp_emergent_themes(SD.messages),
        "nlp_tone_confusion": export.build_nlp_tone_confusion(
            report, message_ids=gold_ids, human=human, model=aligned_model),
        "nlp_voices": export.build_nlp_voices(
            msgs_lab, resolved,
            terms_by_cluster=dict(zip(dim_cluster["cluster_id"],
                                      dim_cluster["top_terms"]))),
    }
    split_aris = [m["stability_ari"] for m in sub_meta.values() if m["is_split"]]
    nlp_meta = {
        "embed_model": dev["embed_model"], "sentiment_model": dev["sentiment_model"],
        "emotion_model": dev["emotion_model"],
        # No gold set yet -- unlike tone_kappa/tone_gate_passed above, this is
        # not withheld pending a kappa gate, just flagged as unvalidated so a
        # reader knows the difference. See nlp.EMOTION_MODEL docstring.
        "emotion_validated": False,
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
    return tables, nlp_meta, sent, emo, lab, dim_cluster, sub_lab, sub_names


def _bot_tables(path, dim_user) -> tuple[dict, dict]:
    """The two spec-4 tables and their meta keys. Degrades, never raises.

    Three levels of degradation, and they are deliberately distinguishable in
    `meta_run` rather than collapsed into one "missing" flag:

    1. **No log file.** Both tables are written EMPTY with their full column
       headers, `bot_log_present=False`. A clone without the out-of-band
       production export still produces a complete, loadable set of tables.
    2. **Log but no gold file.** Counts are exported, the rate is
       `rate_quotable=False`. The KPI exists and is withheld pending labelling.
    3. **Both.** The rate ships if precision clears `GAP_PRECISION_GATE`.

    A malformed log is the one thing that still raises: `bot_replies.load_bot_log`
    throws SchemaError with the fix, and silently degrading a file someone DID
    provide would hide their mistake.
    """
    empty = {"fact_bot_turn": pd.DataFrame(columns=export.FACT_BOT_TURN_COLUMNS),
             "agg_coverage_gap": pd.DataFrame(columns=export.AGG_COVERAGE_GAP_COLUMNS),
             "agg_bot_gap_entities": pd.DataFrame(columns=export.AGG_BOT_GAP_ENTITIES_COLUMNS),
             "fact_bot_turn_entities": pd.DataFrame(
                 columns=export.FACT_BOT_TURN_ENTITIES_COLUMNS)}
    if path is None:
        return empty, {"bot_log_present": False, "gap_gold_present": False,
                       "coverage_gap_quotable": False}

    turns = bot_replies.load_bot_log(path, config.get_salt())

    probe = None
    if GAP_GOLD_PATH.exists():
        gold = pd.read_csv(GAP_GOLD_PATH, encoding="utf-8")
        # DISTINCT-REPLY grain, not turn grain. `gold_candidates` deduplicates by
        # reply_key before sampling, so the sample's population is distinct
        # replies; scaling the miss rate by a turn count would inflate the
        # estimated misses by the duplication factor and understate recall.
        distinct = turns.drop_duplicates("reply_key")
        probe = validation.probe_report(gold, int((~distinct["gap_flag"]).sum()))

    tables = {
        "fact_bot_turn": export.build_fact_bot_turn(turns, dim_user),
        "agg_coverage_gap": export.build_agg_coverage_gap(turns, gap_probe=probe),
        "agg_bot_gap_entities": export.build_agg_bot_gap_entities(turns),
        "fact_bot_turn_entities": export.build_fact_bot_turn_entities(turns),
    }
    meta = {
        "bot_log_present": True,
        "bot_log_turns": len(turns),
        "bot_log_users": int(turns["user_id"].nunique()),
        "gap_gold_present": probe is not None,
        "coverage_gap_quotable": bool(probe["gate_passed"]) if probe else False,
    }
    if probe:
        meta.update({"gap_probe_precision": round(probe["precision"], 3),
                     "gap_probe_recall": round(probe["recall"], 3),
                     "gap_precision_gate": validation.GAP_PRECISION_GATE})
    return tables, meta


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
    ap.add_argument("--bot-log", default=None,
                    help="path to the WhatsApp production log .xlsx, no header "
                         "row (default: newest in datasets/bot_log/). OPTIONAL: "
                         "without it the two coverage-gap tables are empty and "
                         "every other table is unaffected.")
    ap.add_argument("--k", type=int, default=None,
                    help="pin the archetype cluster count instead of letting "
                         "the stability curve choose it (default: auto)")
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

    nlp_tables, nlp_meta, sent, emo, lab, dim_cluster, sub_lab, sub_names = _nlp_tables(
        SD, pr, k_override=args.k)

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
                                                 sub_lab=sub_lab, sub_names=sub_names,
                                                 emotion=emo)
        fact_meal = export.build_fact_meal(SD.meal)
        # NER is loaded once here rather than inside the sampler: the sampler is
        # called per-bucket-loop and spacy.load is expensive.
        _ner = redact.load_ner()
        fact_message_sample = export.build_fact_message_sample(
            SD.messages, fact_message, nlp=_ner)
        fact_conversation_full = export.build_fact_conversation_full(
            SD.messages, fact_message, nlp=_ner)

    with pr.stage("bot replies + coverage gap"):
        bot_log_path = (Path(args.bot_log) if args.bot_log
                        else datasets.resolve("bot_log"))
        print(f"  {'bot_log:':<11}{bot_log_path or 'absent (coverage-gap tables empty)'}",
              file=sys.stderr)
        bot_tables, bot_meta = _bot_tables(bot_log_path, dim_user)

    with pr.stage("aggregate tables"):
        ent_candidates = export.build_nlp_entity_candidates(SD.messages)
        n_ent_hit, n_ent_tot = taxonomy.entity_coverage(SD.messages["message"])
        ent_coverage = (n_ent_hit / n_ent_tot) if n_ent_tot else 0.0

        tables = {
            "dim_user": dim_user,
            "fact_message": fact_message,
            "fact_message_sample": fact_message_sample,
            "fact_conversation_full": fact_conversation_full,
            "fact_meal": fact_meal,
            "dim_city": export.build_dim_city(),
            "dim_quadrant": export.build_dim_quadrant(),
            "agg_funnel": export.build_agg_funnel(SD.responses, SD.messages, SD.meal),
            "agg_registration_funnel": export.build_agg_registration_funnel(SD.responses),
            "agg_language": export.build_agg_language(SD.responses),
            "fact_message_entities": export.build_fact_message_entities(SD.messages),
            "nlp_entity_candidates": ent_candidates,
            "agg_weekly_cluster": export.build_agg_weekly_cluster(SD.messages),
            "agg_daily_volume": export.build_agg_daily_volume(SD.messages),
            "agg_daily_meal": export.build_agg_daily_meal(fact_meal),
            "agg_weekly_rating": export.build_agg_weekly_rating(fact_meal),
            "agg_priority_matrix": export.build_agg_priority_matrix(
                SD.messages, fact_meal, dim_user, dim_cluster,
                neg_by_cluster=neg_by_cluster, sentiment=sent),
            "meta_run": export.build_meta_run(
                SD.run_meta,
                nlp_meta={**nlp_meta,
                          "entity_coverage_pct": round(100 * ent_coverage, 1),
                          "entity_dict_entities": len(taxonomy.ENTITY_PATTERNS),
                          "entity_dict_patterns": sum(
                              len(v) for v in taxonomy.ENTITY_PATTERNS.values()),
                          "entity_candidates_n": len(ent_candidates),
                          **bot_meta}),
            "parity_check": export.build_parity_check(
                SD.reconciliation, dim_user, fact_message, fact_meal,
                nlp_tables["dim_subcluster"],
                entity_coverage_pct=round(100 * ent_coverage, 1)),
        }
        tables.update(nlp_tables)
        tables.update(bot_tables)

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
    _warn_entity_coverage(ent_coverage, len(ent_candidates))
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
