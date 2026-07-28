"""Power BI gold-layer builders + writer.

Pure `build_*(frames) -> DataFrame` functions (no I/O) plus `write_all`, the only
function that touches disk. `run_pipeline.py` is the sole production caller. See
docs/superpowers/specs/2026-07-24-sami-exports-powerbi-design.md.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

import pandas as pd

from . import metrics, taxonomy, qa, canon, theme

# EN display for the official categories (chart text only) — mirrors the notebooks.
CAT_EN = {
    "legal_documentation": "Legal & documentation",
    "humanitarian_assistance": "Humanitarian assistance",
    "protection": "Protection",
    "employment": "Employment",
    "organization_search": "Finding organizations",
    "journey_information": "Journey information",
    "services": "Services",
    "unclassified": "Unclassified",
}
# EN display for the emergent-need probes (mirrors NB3).
PROBE_EN = {
    "transport_logistics": "Transport & movement",
    "entrepreneurship": "Enterprise & livelihood",
    "procedure_troubleshooting": "Stuck in a procedure",
    "human_handoff": "Reach a person",
    "fraud_protection": "Fraud & scams",
    "connectivity": "Connectivity / phone",
}
# Ordinal 1-5 keyed to the observed MEAL usefulness vocabulary (mirrors NB2).
RATING_NUM = {
    "Muy útil": 5, "Útil": 4, "Medianamente útil": 3, "Poco útil": 2, "Nada útil": 1,
}


def _translate(frame: pd.DataFrame, col: str, fn) -> None:
    """Apply an EN display mapping to `col` in place, if the column exists."""
    if col in frame.columns:
        frame[col] = frame[col].map(fn)


def _mapper(table: dict):
    """Value-preserving lookup: NA stays NA, unmapped values pass through."""
    def _f(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return v
        return table.get(v, v)
    return _f


def message_key(user_id, seq, message) -> str:
    """Stable id for one message: sha1(user_id\x00seq\x00text)[:16].

    Replaces a positional index. `load.load_messages` sorts the spine by
    (user_id, ts), so a positional id was re-assigned to a DIFFERENT message
    every time the corpus grew — silently invalidating anything keyed on it,
    including the tone gold labels.

    Keying on (user_id, seq, message_text) is stable under:
    - new users being added (the spine re-sorts; other users' seqs unchanged)
    - new messages appended to existing users (their seq numbers only increase)

    It is NOT stable if a backfilled message lands earlier in an existing user's
    timeline; `seq` is computed from sorted timestamps, so an earlier insertion
    renumbers the entire user's sequence and all their message ids change.

    Uses NUL byte (\\x00) as delimiter to prevent collisions in unusual inputs.
    """
    raw = f"{user_id}\x00{seq}\x00{message}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# Explicit non-response bucket. The canon functions return None for a survey
# answer they cannot place on the scale (blank, or free text off the vocabulary);
# on a Power BI axis that renders as an unlabelled bar, so the gold layer names
# it. Order -1 sits *below* the real scale (0..n-1): ascending sort puts it at
# the top, away from the ordered ramp, and it takes the light end of any
# gradient keyed on the order column — "no information", not "longest".
NO_RESPONSE_EN = "Did not respond"
NO_RESPONSE_ORDER = -1


def _fill_non_response(frame: pd.DataFrame, label_col: str, order_col: str) -> None:
    """Name the null bucket of an ordered survey scale, in place."""
    if label_col in frame.columns:
        frame[label_col] = frame[label_col].fillna(NO_RESPONSE_EN).replace(
            "", NO_RESPONSE_EN)
    if order_col in frame.columns:
        frame[order_col] = frame[order_col].fillna(NO_RESPONSE_ORDER)


def to_english_user(agg: pd.DataFrame) -> pd.DataFrame:
    """Rewrite dim_user's Spanish survey values as their EN dashboard labels.
    Values are replaced in place — the *_order columns carry the sort, and the
    analysis frames keep the Spanish source values untouched."""
    _translate(agg, "gender_clean", canon.gender_display)
    _translate(agg, "minors", canon.yes_no_display)
    _translate(agg, "away_duration_canon", _mapper(canon.AWAY_DURATION_DISPLAY_EN))
    _translate(agg, "city_duration_canon", _mapper(canon.CITY_DURATION_DISPLAY_EN))
    _translate(agg, "city_canon", _mapper(canon.OTHER_BUCKET_EN))
    _translate(agg, "nationality_canon", _mapper(canon.OTHER_BUCKET_EN))
    _fill_non_response(agg, "away_duration_canon", "away_duration_order")
    _fill_non_response(agg, "city_duration_canon", "city_duration_order")
    return agg


def to_english_meal(f: pd.DataFrame) -> pd.DataFrame:
    """Same for fact_meal. Call *after* rating_num, which keys off the Spanish
    usefulness vocabulary."""
    _translate(f, "usefulness_rating", _mapper(canon.USEFULNESS_DISPLAY_EN))
    _translate(f, "would_recommend", canon.yes_no_display)
    _translate(f, "discovery_channel", _mapper(canon.DISCOVERY_DISPLAY_EN))
    return f


# Profile columns collapsed one-row-per-user (first non-null in ts order).
_PROFILE_COLS = [
    "gender_clean", "age_num", "age_flag", "city_canon", "department",
    "nationality_canon", "away_duration_canon", "away_duration_order",
    "city_duration_canon", "city_duration_order", "dominant_category", "n_questions",
]
# Raw survey columns that carry into dim_user under friendlier names.
_RAW_RENAME = {"Minors": "minors", "Age Ranges": "age_range",
               "Destination_Country": "destination_country"}


def build_dim_category() -> pd.DataFrame:
    # CAT_EN is ordered like taxonomy.OFFICIAL_CATEGORIES + ["unclassified"];
    # theme.CAT is the fixed categorical palette (unclassified -> grey #b7b7b7).
    return pd.DataFrame(
        [{"category_key": k, "category_es": k, "category_en": v,
          "color_hex": theme.CAT[i], "display_order": i}
         for i, (k, v) in enumerate(CAT_EN.items())])


def build_dim_city() -> pd.DataFrame:
    """One row per canonical city with coordinates for the dashboard bubble map.
    The 'Otra'/Other bucket is excluded — it has no location."""
    rows = [{"city_canon": city, "department": canon.department_of(city),
             "lat": lat, "lon": lon}
            for city, (lat, lon) in canon.CITY_COORDS.items()]
    return pd.DataFrame(rows, columns=["city_canon", "department", "lat", "lon"])


def build_dim_user(responses: pd.DataFrame, messages: pd.DataFrame,
                   lab: "pd.Series | None" = None) -> pd.DataFrame:
    """One row per user. `lab` (Series indexed by user_id -> archetype) fills
    `cluster_id`; None leaves it null (the --skip-nlp contract)."""
    r = responses.sort_values("ts", kind="stable")
    cols = [c for c in _PROFILE_COLS if c in r.columns]
    agg = r.groupby("user_id")[cols].first()
    for raw, new in _RAW_RENAME.items():
        if raw in r.columns:
            agg[new] = r.groupby("user_id")[raw].first()
    mpu = messages.groupby("user_id").size()
    agg["n_msgs_user"] = agg.index.to_series().map(mpu).fillna(0).astype(int)
    agg["has_text"] = agg["n_msgs_user"] > 0
    # first message timestamp per user (NaT if the user has no text)
    first = messages.groupby("user_id")["ts"].min()
    agg["first_seen"] = agg.index.to_series().map(first)
    # repeat asker — the exact definition behind reconciliation.repeat_askers_pct
    q = responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    agg["is_repeat_asker"] = agg.index.to_series().map(q >= p90).fillna(False).astype(bool)
    # intends to stay: no onward destination stated, or destination folds to Colombia
    def _stay(v):
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
            return True
        return canon.fold(str(v)) == canon.fold("Colombia")
    dest = (agg["destination_country"] if "destination_country" in agg.columns
            else pd.Series(index=agg.index, dtype=object))
    agg["intends_to_stay"] = dest.map(_stay).astype(bool)
    agg["cluster_id"] = (agg.index.to_series().map(lab.to_dict())
                         if lab is not None else pd.NA)
    return to_english_user(agg.reset_index())


_FACT_MSG_COLS = ["message_id", "user_id", "ts", "city_canon",
                  "dominant_category", "seq", "n_msgs_user"]


def build_fact_message(messages: pd.DataFrame, sentiment: "pd.DataFrame | None" = None,
                       lab: "pd.Series | None" = None) -> pd.DataFrame:
    f = messages.copy()
    f["message_id"] = [message_key(u, s, m) for u, s, m
                       in zip(f["user_id"], f["seq"], f["message"])]
    f = f[[c for c in _FACT_MSG_COLS if c in f.columns]].copy()
    f["sentiment_label"] = (sentiment.loc[messages.index, "label"].values
                            if sentiment is not None else pd.NA)
    f["cluster_id"] = (f["user_id"].map(lab.to_dict()) if lab is not None else pd.NA)
    _translate(f, "city_canon", _mapper(canon.OTHER_BUCKET_EN))
    return f


_FACT_MEAL_COLS = ["user_id", "ts", "usefulness_rating", "rating_num",
                   "would_recommend", "recommendation_text", "discovery_channel"]


def build_fact_meal(meal: pd.DataFrame) -> pd.DataFrame:
    f = meal.copy()
    f["rating_num"] = f["usefulness_rating"].map(RATING_NUM)
    return to_english_meal(f[[c for c in _FACT_MEAL_COLS if c in f.columns]].copy())


def build_agg_funnel(responses, messages, meal) -> pd.DataFrame:
    f = metrics.funnel_stages(responses, messages, meal).reset_index(drop=True)
    f.insert(0, "stage_order", range(len(f)))
    return f


def build_agg_entities_by_kind(messages: pd.DataFrame) -> pd.DataFrame:
    by_kind = taxonomy.entity_counts_by_kind(messages["message"])
    rows = [{"kind": kind, "entity": ent, "n": int(n)}
            for kind, s in by_kind.items() for ent, n in s.items()]
    return pd.DataFrame(rows, columns=["kind", "entity", "n"])


def build_agg_weekly_category(messages: pd.DataFrame) -> pd.DataFrame:
    wk = metrics.weekly_category_counts(messages, top_n=4)
    return (wk.reset_index()
            .melt(id_vars="week_start", var_name="category", value_name="n")
            .rename(columns={"week_start": "week"}))


def build_agg_daily_volume(messages: pd.DataFrame) -> pd.DataFrame:
    d = messages.dropna(subset=["ts"]).set_index("ts").resample("D").size()
    return d.reset_index(name="n").rename(columns={"ts": "day"})


def build_agg_weekly_rating(fact_meal: pd.DataFrame) -> pd.DataFrame:
    m = (fact_meal.dropna(subset=["ts", "rating_num"]).set_index("ts")
         .resample("W")["rating_num"].agg(["mean", "count"]))
    return m.reset_index().rename(columns={"ts": "week", "mean": "mean_rating",
                                           "count": "n"})


def build_agg_priority_matrix(messages, fact_meal, dim_user,
                              neg_by_cat: "pd.Series | None" = None) -> pd.DataFrame:
    msgs_pm = messages[messages["dominant_category"] != "unclassified"]
    meal_cat = fact_meal.merge(
        dim_user[["user_id", "dominant_category"]].drop_duplicates("user_id"),
        on="user_id", how="left")
    pm = metrics.priority_matrix_frame(msgs_pm, meal_cat, neg_by_category=neg_by_cat)
    return pm.reset_index().rename(columns={"dominant_category": "category"})


def build_dim_cluster(prof: pd.DataFrame, names: dict) -> pd.DataFrame:
    d = prof.reset_index().rename(columns={"archetype": "cluster_id"})
    d["name"] = d["cluster_id"].map(names)
    cols = ["cluster_id", "name", "n_users", "n_messages", "median_age", "top_categories"]
    return d[[c for c in cols if c in d.columns]]


def build_nlp_umap(XY, labels, user_ids) -> pd.DataFrame:
    return pd.DataFrame({"user_id": list(user_ids), "x": XY[:, 0], "y": XY[:, 1],
                         "cluster_id": list(labels)})


def build_nlp_cluster_terms(terms: dict) -> pd.DataFrame:
    rows = [{"cluster_id": cid, "rank": rank, "term": term, "weight": float(w)}
            for cid, s in terms.items()
            for rank, (term, w) in enumerate(s.items())]
    return pd.DataFrame(rows, columns=["cluster_id", "rank", "term", "weight"])


def build_nlp_emergent_themes(messages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for slug, pat in taxonomy.CANDIDATE_INTENT_PROBES.items():
        hit = messages["message"].str.contains(pat, case=False, regex=True, na=False)
        rows.append({"theme": PROBE_EN.get(slug, slug), "slug": slug,
                     "n_messages": int(hit.sum()),
                     "n_users": int(messages.loc[hit, "user_id"].nunique())})
    return (pd.DataFrame(rows).sort_values("n_users", ascending=False)
            .reset_index(drop=True))


def build_nlp_tone_confusion(report: dict) -> pd.DataFrame:
    cm = report["confusion"]
    long = (cm.reset_index()
            .melt(id_vars=cm.index.name, var_name=cm.columns.name, value_name="n"))
    return long.rename(columns={cm.index.name: "human_label",
                                cm.columns.name: "model_label"})


def build_nlp_voices(msgs_lab: pd.DataFrame, names: dict) -> pd.DataFrame:
    rows = []
    for cid in sorted(msgs_lab["archetype"].unique()):
        marker = taxonomy.ARCHETYPE_NAMES[cid]["marker"]
        g = (msgs_lab[(msgs_lab["archetype"] == cid)
                      & msgs_lab["message"].str.len().between(60, 190)
                      & msgs_lab["message"].str.contains(marker, case=False, na=False)]
             .sort_values(["user_id", "seq"], kind="stable"))
        rows.append({"cluster_id": int(cid), "name": names.get(cid),
                     "message": g["message"].iloc[0] if len(g) else "—"})
    return pd.DataFrame(rows)


def build_meta_run(run_meta: dict, nlp_meta: "dict | None" = None,
                   schema_version: str = "2") -> pd.DataFrame:
    merged = {k: v for k, v in run_meta.items() if k != "checks"}
    merged["schema_version"] = schema_version
    if nlp_meta:
        merged.update(nlp_meta)
    return pd.DataFrame([{"key": k, "value": str(v)} for k, v in merged.items()])


# exported-key -> reconciliation metric label
_PARITY_MAP = {
    "users": "users",
    "messages": "messages",
    "users_with_text": "users_with_text",
    "meal_responses": "meal_responses",
}


def build_parity_check(reconciliation, dim_user, fact_message, fact_meal) -> pd.DataFrame:
    recon = reconciliation.set_index("metric")["value"].to_dict()
    exported = {
        "users": dim_user["user_id"].nunique(),
        "messages": len(fact_message),
        "users_with_text": int(dim_user["has_text"].sum()),
        "meal_responses": len(fact_meal),
    }
    rows = []
    for key, val in exported.items():
        rv = recon.get(_PARITY_MAP[key])
        rows.append({"metric": key, "exported_value": int(val),
                     "reconciliation_value": rv,
                     "match": rv is not None and int(rv) == int(val)})
    # repeat-asker share (float %) — mirrors reconciliation.repeat_askers_pct
    rap_exp = round(100 * float(dim_user["is_repeat_asker"].mean()), 1)
    rap_rec = recon.get("repeat_askers_pct")
    rows.append({"metric": "repeat_askers_pct", "exported_value": rap_exp,
                 "reconciliation_value": rap_rec,
                 "match": rap_rec is not None and float(rap_rec) == rap_exp})
    return pd.DataFrame(rows)


def write_all(out_dir, tables: dict) -> pd.DataFrame:
    """PII-scan every frame, then write each as CSV + a _manifest.csv. Scans run
    before any write, so a violation leaves the directory untouched."""
    out = Path(out_dir)
    for name, frame in tables.items():
        hits = qa.pii_scan(frame)
        if hits:
            raise ValueError(f"PII in table '{name}': {hits[:3]}")
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, frame in tables.items():
        path = out / f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8")
        sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
        manifest.append({"table": name, "rows": len(frame),
                         "columns": ",".join(map(str, frame.columns)), "sha1": sha1})
    man = pd.DataFrame(manifest).sort_values("table").reset_index(drop=True)
    man.to_csv(out / "_manifest.csv", index=False, encoding="utf-8")
    return man
