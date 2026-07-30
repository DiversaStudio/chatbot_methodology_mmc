"""Power BI gold-layer builders + writer.

Pure `build_*(frames) -> DataFrame` functions (no I/O) plus `write_all`, the only
function that touches disk. `run_pipeline.py` is the sole production caller. See
docs/superpowers/specs/2026-07-24-sami-exports-powerbi-design.md.
"""
from __future__ import annotations
import hashlib
import warnings
from pathlib import Path

import pandas as pd

from . import metrics, taxonomy, qa, canon, theme, cohort

# EN display for the official categories (chart text only) — mirrors the notebooks.
CAT_EN = {
    "legal_documentation": "Legal & documentation",
    "humanitarian_assistance": "Humanitarian assistance",
    "protection": "Protection",
    "employment": "Employment",
    "organization_search": "Finding organizations",
    "journey_information": "Journey information",
    "services": "Services",
    # The platform's own categorisation is presented as a SUGGESTION, not
    # ground truth (checkpoint 2026-07-28). This bucket holds every record the
    # taxonomy cannot place: users with no summary at all, and the v2
    # timestamped-prose summaries that carry no category label.
    "unclassified": "Suggestion",
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
    "instrument_version", "gender_clean", "age_num", "age_flag", "city_canon", "department",
    "nationality_canon", "away_duration_canon", "away_duration_order",
    "city_duration_canon", "city_duration_order", "dominant_category", "n_questions",
]
# Raw survey columns that carry into dim_user under friendlier names.
_RAW_RENAME = {"Minors": "minors", "Age Ranges": "age_range",
               "Destination_Country": "destination_country",
               "Language": "language",
               "Registration Status": "registration_status",
               "Attempts": "attempts",
               "Is Returning User": "is_returning",
               "Safety Alert": "safety_alert",
               "Escalation Status": "escalation_status"}


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
    # Derived before the groupby so 'first' picks the version of the user's
    # earliest record — a user who appears in both cohorts is counted as v1,
    # which is when they actually answered the registration survey.
    r = r.assign(instrument_version=cohort.instrument_version(r).values)
    cols = [c for c in _PROFILE_COLS if c in r.columns]
    agg = r.groupby("user_id")[cols].first()
    for raw, new in _RAW_RENAME.items():
        if raw in r.columns:
            agg[new] = r.groupby("user_id")[raw].first()
    # KPI2 feeds off this column. A user with several response records has
    # several sessions; the longest is taken, so the value is one real observed
    # session rather than a sum across days. Null wherever load could not trust
    # `Last Message At` — Power BI's MEDIAN ignores those rows.
    if "session_minutes" in r.columns:
        agg["session_minutes"] = r.groupby("user_id")["session_minutes"].max()
    mpu = messages.groupby("user_id").size()
    agg["n_msgs_user"] = agg.index.to_series().map(mpu).fillna(0).astype(int)
    agg["has_text"] = agg["n_msgs_user"] > 0
    # first message timestamp per user (NaT if the user has no text)
    first = messages.groupby("user_id")["ts"].min()
    agg["first_seen"] = agg.index.to_series().map(first)
    # Registration timestamp: the user's earliest response record. Distinct from
    # `first_seen`, which is their first MESSAGE and is therefore null for the
    # users who registered and never wrote anything. A "new users" count built on
    # first_seen silently drops those people and disagrees with a plain user count
    # for a reason invisible on the dashboard; this column is never null, because
    # every row in dim_user comes from at least one response record.
    agg["registered_at"] = r.groupby("user_id")["ts"].min()
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


# Ratings for which the v2 "¿Por qué la información entregada no fue útil?"
# question was SUPPOSED to fire. Its skip logic misfired in production: it was
# asked of 118 respondents, 75 of whom had rated the service Útil or Muy útil
# and answered with negations ("no", "Todo bien gracias"). Counting all 118 as
# reasons-for-failure is 64% noise, so the validity is carried in the data
# rather than in a note nobody reads.
# CRITICAL: Keep these values in SPANISH. The flag is computed BEFORE to_english_meal
# translates the vocabulary. Translating them would silently make reason_is_valid all-False.
REASON_VALID_RATINGS = frozenset({"Nada útil", "Poco útil", "Medianamente útil"})

_FACT_MEAL_COLS = ["user_id", "ts", "usefulness_rating", "rating_num",
                   "would_recommend", "recommendation_text", "discovery_channel",
                   "no_usefulness_reason", "reason_is_valid"]


def build_fact_meal(meal: pd.DataFrame) -> pd.DataFrame:
    f = meal.copy()
    f["rating_num"] = f["usefulness_rating"].map(RATING_NUM)
    # Computed BEFORE to_english_meal, which rewrites the Spanish vocabulary.
    if "no_usefulness_reason" not in f.columns:
        f["no_usefulness_reason"] = pd.NA
    f["reason_is_valid"] = (f["usefulness_rating"].isin(REASON_VALID_RATINGS)
                            & f["no_usefulness_reason"].notna())
    return to_english_meal(f[[c for c in _FACT_MEAL_COLS if c in f.columns]].copy())


# CRITICAL: Aggregate builder section. These builders are outside the cohort.POLICY
# guard's reach (which only covers dim_user and fact_meal columns). Builders here
# must handle cohort splitting themselves — never pool v1 and v2 data. The next
# person adding an agg_* builder: the guard will not catch you. Read the cohort
# comments in this file and in build_dim_user before pooling any data.

def build_agg_funnel(responses, messages, meal) -> pd.DataFrame:
    f = metrics.funnel_stages(responses, messages, meal).reset_index(drop=True)
    f.insert(0, "stage_order", range(len(f)))
    return f


# Registration is the stage BEFORE `agg_funnel`'s "arrived": the v1 platform
# exposed nothing about people who started the survey and never finished, so
# this is new ground rather than a re-cut of the existing funnel.
_REG_STAGES = ("registration started", "registration completed",
               "abandoned", "in progress", "other")


def build_agg_registration_funnel(responses: pd.DataFrame) -> pd.DataFrame:
    """Ordered pre-conversation funnel from the v2 registration fields, split by cohort.

    Empty (with the right columns) when the export predates those fields, so a
    v1-only archive still writes a well-formed table. The "other" bucket holds
    rows with unrecognized status values (new states, typos, nulls), ensuring
    stages always sum to started by construction.

    CRITICAL: Split by instrument_version. v1 rows are complete by construction
    (migrated from a platform that never tracked partial registration), so their
    100% completion rate dilutes v2's real drop-off signal when pooled. A pooled
    rate is meaningless and must never be shown. Keep v1 rows to document that
    the legacy data carries no drop-off information; do not filter them out.

    NOTE: This builder stays RECORD-level (each record is a distinct registration
    attempt). Cohort is assigned per-user (user's earliest record's cohort).
    """
    cols = ["instrument_version", "stage_order", "stage", "n", "pct_of_started"]
    if "Registration Status" not in responses.columns:
        return pd.DataFrame(columns=cols)

    # Assign each user ONE instrument_version (earliest record's cohort)
    r = responses.sort_values("ts", kind="stable")
    r = r.assign(instrument_version=cohort.instrument_version(r).values)
    user_cohort = r.groupby("user_id")["instrument_version"].first()
    r = r.merge(user_cohort.rename("user_instrument_version"), left_on="user_id", right_index=True)

    status = r["Registration Status"].astype("string").str.strip().str.lower()
    rows = []

    # Build rows for each cohort separately
    for cohort_val in ["v1", "v2"]:
        cohort_mask = r["user_instrument_version"] == cohort_val
        cohort_r = r[cohort_mask]
        cohort_status = status[cohort_mask]

        # Count rows where Registration Started is non-null as the true denominator
        if "Registration Started" in r.columns:
            started = int(cohort_r["Registration Started"].notna().sum())
        else:
            started = len(cohort_r)

        if started == 0:
            continue  # Skip cohorts with no records

        counts = {
            "registration started": started,
            "registration completed": int((cohort_status == "completed").sum()),
            "abandoned": int((cohort_status == "abandoned").sum()),
            "in progress": int((cohort_status == "in progress").sum()),
        }
        # Count unrecognized statuses in "other"
        recognized = {"completed", "abandoned", "in progress"}
        counts["other"] = int((~cohort_status.isin(recognized)).sum())

        for i, stage in enumerate(_REG_STAGES):
            rows.append({
                "instrument_version": cohort_val,
                "stage_order": i,
                "stage": stage,
                "n": counts[stage],
                "pct_of_started": (round(100 * counts[stage] / started, 1)
                                   if started else 0.0)
            })

    return pd.DataFrame(rows, columns=cols)


def build_agg_language(responses: pd.DataFrame) -> pd.DataFrame:
    """Distinct users per interface language, split by instrument version.

    Split because the language selector is v2-only: a pooled count would read
    as 99% Spanish when the question simply did not exist for v1 users.

    SEMANTICS: instrument_version is a per-user attribute (which registration
    survey the user answered); language is per-record (the same person can use
    multiple languages). Each user is assigned to ONE cohort (their earliest
    record's instrument_version). A user who used multiple languages appears in
    multiple rows. Therefore, n_users does NOT sum to the total user count — a
    multilingual user is counted under each language they used. This is correct
    and intentional.

    Per-cohort user counts still reconcile with dim_user on per-cohort basis
    (e.g., v1 users = count of distinct users with v1 instrument_version across
    all languages they used).
    """
    cols = ["language", "instrument_version", "n_users"]
    if "Language" not in responses.columns:
        return pd.DataFrame(columns=cols)
    # Assign each user one instrument_version (their earliest record's cohort).
    r = responses.sort_values("ts", kind="stable")
    r = r.assign(instrument_version=cohort.instrument_version(r).values)
    user_cohort = r.groupby("user_id")["instrument_version"].first()
    # Join per-user cohort onto the full record-level frame.
    r = r.merge(user_cohort.rename("user_instrument_version"), left_on="user_id", right_index=True)
    # Group by (Language, user_instrument_version) at the RECORD level,
    # counting distinct users. A multilingual user appears in multiple rows.
    g = (r.dropna(subset=["Language"])
         .groupby(["Language", "user_instrument_version"])["user_id"]
         .nunique().reset_index())
    g.columns = cols
    return g.sort_values(["instrument_version", "n_users"],
                         ascending=[True, False]).reset_index(drop=True)


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
    out = pm.reset_index().rename(columns={"dominant_category": "category"})

    # Carry the canonical EN label and colour, from the same CAT_EN source
    # dim_category is built from. The dashboard used to recover the label with a
    # DAX LOOKUPVALUE against dim_category -- but the two tables have no
    # relationship, and LOOKUPVALUE returns BLANK for a key it cannot find, so a
    # category the taxonomy gained would plot as an unlabelled bubble rather than
    # failing. Resolving it here means an unknown key raises at export instead.
    cat = build_dim_category().set_index("category_key")
    unknown = sorted(set(out["category"]) - set(cat.index))
    if unknown:
        raise KeyError(
            f"priority matrix has categories absent from CAT_EN: {unknown}. "
            "Add them to export.CAT_EN so the dashboard can label them.")
    out["category_en"] = out["category"].map(cat["category_en"])
    out["color_hex"] = out["category"].map(cat["color_hex"])
    return out


def build_dim_cluster(prof: pd.DataFrame, names: dict) -> pd.DataFrame:
    d = prof.reset_index().rename(columns={"archetype": "cluster_id"})
    d["name"] = d["cluster_id"].map(names)

    # Colour and sort by SIZE RANK, not cluster_id. Cluster ids are assigned by
    # the clustering run and carry no meaning across runs, so binding a colour
    # to an id makes the dashboard re-colour itself on every re-cluster. Rank by
    # n_users is stable in the way that matters: the biggest archetype keeps the
    # primary brand hue. Ties break on cluster_id so the result is deterministic.
    order = (d.sort_values(["n_users", "cluster_id"], ascending=[False, True],
                           kind="stable")["cluster_id"].tolist())
    rank = {cid: i for i, cid in enumerate(order)}
    d["display_order"] = d["cluster_id"].map(rank)
    palette = (theme.ARCHETYPE if len(order) <= len(theme.ARCHETYPE)
               else theme.bar_colors(len(order)))   # k > 6 falls back to full CAT
    d["color_hex"] = d["display_order"].map(lambda i: palette[i])

    cols = ["cluster_id", "name", "n_users", "n_messages", "median_age",
            "top_categories", "display_order", "color_hex"]
    return d[[c for c in cols if c in d.columns]]


# The four cells of the priority matrix, as a table so Power BI can draw a real
# legend bound to data instead of four hand-placed shapes with hand-typed hexes.
# Static by construction: the quadrants are a fixed reading of the two axes, not
# something the data decides. `axis_x` / `axis_y` name the side of each median
# line the cell sits on, so the legend can be regenerated if the axes ever swap.
_QUADRANTS = [
    ("high_volume_high_need", "Big and badly served", "Act here",
     "high", "high", theme.QUADRANT["high_volume_high_need"]),
    ("low_volume_high_need", "Small but badly served", "Watch",
     "low", "high", theme.QUADRANT["low_volume_high_need"]),
    ("high_volume_low_need", "Big and well served", "Protect",
     "high", "low", theme.QUADRANT["high_volume_low_need"]),
    ("low_volume_low_need", "Small and well served", "Steady state",
     "low", "low", theme.QUADRANT["low_volume_low_need"]),
]


def build_dim_quadrant() -> pd.DataFrame:
    return pd.DataFrame(
        [{"quadrant_key": key, "label": label, "action": action,
          "axis_x": ax, "axis_y": ay, "color_hex": hexv, "display_order": i}
         for i, (key, label, action, ax, ay, hexv) in enumerate(_QUADRANTS)])


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


# Version of the DASHBOARD, bumped by hand when the report's visuals or fields
# change. Deliberately not the package version in pyproject.toml: the code and
# the report move on different cadences, and a viewer reading the footer wants
# to know which report they are looking at, not which library built it.
REPORT_VERSION = "1.1.0"


def build_meta_run(run_meta: dict, nlp_meta: "dict | None" = None,
                   schema_version: str = "4") -> pd.DataFrame:
    merged = {k: v for k, v in run_meta.items() if k != "checks"}
    merged["schema_version"] = schema_version
    merged["report_version"] = REPORT_VERSION
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
    _warn_stale_tables(out, set(tables))
    return man


def _warn_stale_tables(out: Path, written: set) -> None:
    """Name CSVs in `out` that this run did not write.

    A `--skip-nlp` run does not delete the NLP tables it skips, so the previous
    run's `dim_cluster` / `nlp_*` files stay on disk. Power BI and the notebooks
    load them without complaint, silently joining an older — and possibly
    smaller — cohort to today's users. They are not deleted here because a
    deliberate skip-NLP workflow still wants them; the run says so instead.
    """
    orphans = sorted(
        p.name for p in out.glob("*.csv")
        if not p.name.startswith("_") and p.stem not in written)
    if orphans:
        warnings.warn(
            f"{len(orphans)} table(s) in {out} were NOT written by this run and "
            f"may be from an older export: {', '.join(orphans)}. They are absent "
            "from _manifest.csv. Re-run without --skip-nlp for a coherent "
            "folder, or delete them.",
            stacklevel=2)
