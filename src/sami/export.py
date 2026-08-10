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

from . import metrics, taxonomy, qa, canon, theme, cohort, subclusters, redact

# The categorisation bucket for users with no message text. Clustering needs a
# document, so the ~194 users who registered and never wrote anything cannot be
# labelled. Naming that bucket rather than leaving it null keeps user counts
# reconciling and makes a cluster-sliced KPI's disagreement with the headline
# count an intentional, visible thing. Same reasoning as NO_RESPONSE_EN below.
NO_CLUSTER_ID = -1
NO_CLUSTER_NAME = "No conversation text"

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
    "city_duration_canon", "city_duration_order", "n_questions",
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


def build_dim_city() -> pd.DataFrame:
    """One row per canonical city with coordinates for the dashboard bubble map.
    The 'Otra'/Other bucket is excluded — it has no location."""
    rows = [{"city_canon": city, "department": canon.department_of(city),
             "lat": lat, "lon": lon}
            for city, (lat, lon) in canon.CITY_COORDS.items()]
    return pd.DataFrame(rows, columns=["city_canon", "department", "lat", "lon"])


def build_dim_user(responses: pd.DataFrame, messages: pd.DataFrame,
                   lab: pd.Series, *, sub_lab: pd.Series,
                   sub_names: dict) -> pd.DataFrame:
    """One row per user. `lab` (Series indexed by user_id -> cluster_id) fills
    `cluster_id`; users absent from it — those with no message text to cluster —
    get NO_CLUSTER_ID. `sub_lab` does the same one level down, falling back to
    NO_SUBCLUSTER_ID, and `sub_names` resolves the id to its display name."""
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
                         .fillna(NO_CLUSTER_ID).astype(int))
    agg["subcluster_id"] = (agg.index.to_series().map(sub_lab.to_dict())
                            .fillna(subclusters.NO_SUBCLUSTER_ID).astype(int))
    agg["subcluster_name"] = agg["subcluster_id"].map(sub_names).fillna(
        subclusters.NO_SUBCLUSTER_NAME)
    return to_english_user(agg.reset_index())


_FACT_MSG_COLS = ["message_id", "user_id", "ts", "city_canon",
                  "seq", "n_msgs_user"]


def build_fact_message(messages: pd.DataFrame, sentiment: "pd.DataFrame | None" = None,
                       *, lab: pd.Series, sub_lab: pd.Series,
                       sub_names: dict) -> pd.DataFrame:
    f = messages.copy()
    f["message_id"] = [message_key(u, s, m) for u, s, m
                       in zip(f["user_id"], f["seq"], f["message"])]
    f = f[[c for c in _FACT_MSG_COLS if c in f.columns]].copy()
    f["sentiment_label"] = (sentiment.loc[messages.index, "label"].values
                            if sentiment is not None else pd.NA)
    f["cluster_id"] = f["user_id"].map(lab.to_dict()).fillna(NO_CLUSTER_ID).astype(int)
    f["subcluster_id"] = (f["user_id"].map(sub_lab.to_dict())
                          .fillna(subclusters.NO_SUBCLUSTER_ID).astype(int))
    f["subcluster_name"] = f["subcluster_id"].map(sub_names).fillna(
        subclusters.NO_SUBCLUSTER_NAME)
    _translate(f, "city_canon", _mapper(canon.OTHER_BUCKET_EN))
    return f


SAMPLE_PER_BUCKET = 6
SAMPLE_LEN_MIN, SAMPLE_LEN_MAX = 60, 190
FACT_MESSAGE_SAMPLE_COLUMNS = [
    "message_id", "user_id", "cluster_id", "subcluster_id", "subcluster_name",
    "sentiment_label", "city_canon", "ts", "char_len", "text_redacted",
    "redaction_applied",
]


def build_fact_message_sample(messages: pd.DataFrame, fact_message: pd.DataFrame,
                              *, nlp=None,
                              per_bucket: int = SAMPLE_PER_BUCKET) -> pd.DataFrame:
    """Up to `per_bucket` redacted verbatims per (subcluster x tone) bucket.

    Labels come from `fact_message`, not from a second pass over `messages`.
    Re-deriving cluster/subcluster/tone here would give the two tables their own
    copies of the same join, and they would drift the first time one changed.

    Selection is deterministic (sorted by message_id, no RNG) so a re-run on the
    same input reproduces the file byte-for-byte and the manifest sha1 holds.

    Redaction can DROP a candidate (see `redact.scrub`). A drop is refilled from
    the next candidate in the bucket, so drops cost coverage of the corpus, not
    rows in the output. A bucket with too few survivors is simply short, and an
    empty one contributes nothing — the sampler never pads.
    """
    src = messages.copy()
    src["message_id"] = [message_key(u, s, m) for u, s, m
                         in zip(src["user_id"], src["seq"], src["message"])]
    df = fact_message.merge(src[["message_id", "message"]], on="message_id",
                            how="inner")

    df = df[(df["subcluster_id"] >= 0) & (df["cluster_id"] >= 0)]
    df["char_len"] = df["message"].astype(str).str.len()
    df = df[df["char_len"].between(SAMPLE_LEN_MIN, SAMPLE_LEN_MAX)]
    df = df.sort_values("message_id", kind="mergesort")

    # Built explicitly, not via `bucket.to_dict("records")` -- the record dicts
    # carry extra columns from the merge (message, seq, n_msgs_user) that must
    # never reach the export, and picking each declared field by name is what
    # guarantees every output column gets a real value rather than silently
    # going NaN if a source column were ever renamed or dropped upstream.
    rows = []
    for (_sub, _tone), bucket in df.groupby(["subcluster_id", "sentiment_label"],
                                            sort=True):
        kept = 0
        for rec in bucket.to_dict("records"):
            if kept >= per_bucket:
                break
            clean, changed = redact.scrub(rec["message"], nlp=nlp)
            if clean is None:
                continue          # dropped; refill from the next candidate
            rows.append({
                "message_id": rec["message_id"],
                "user_id": rec["user_id"],
                "cluster_id": rec["cluster_id"],
                "subcluster_id": rec["subcluster_id"],
                "subcluster_name": rec["subcluster_name"],
                "sentiment_label": rec["sentiment_label"],
                "city_canon": rec["city_canon"],
                "ts": rec["ts"],
                "char_len": rec["char_len"],
                "text_redacted": clean,
                "redaction_applied": changed,
            })
            kept += 1

    out = pd.DataFrame(rows, columns=FACT_MESSAGE_SAMPLE_COLUMNS)
    return out.reset_index(drop=True)


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


def build_nlp_entity_candidates(messages: pd.DataFrame) -> pd.DataFrame:
    """Terms the dictionary does not recognise, for a human to triage.

    Carries `example_message_id` and never the message text itself: this table
    is published, and raw user text is not.

    `messages` may come straight from `load_sami` (no `message_id` column
    yet -- it's synthesised here via `message_key`, same as `build_fact_message`,
    so `example_message_id` values line up with `fact_message.message_id`) or
    already carry `message_id` (fixtures, tests).
    """
    if "message_id" not in messages.columns:
        messages = messages.copy()
        messages["message_id"] = [message_key(u, s, m) for u, s, m
                                  in zip(messages["user_id"], messages["seq"],
                                         messages["message"])]
    return taxonomy.entity_candidates(messages)


def build_agg_weekly_cluster(messages: pd.DataFrame) -> pd.DataFrame:
    wk = metrics.weekly_cluster_counts(messages)
    return (wk.reset_index()
            .melt(id_vars="week_start", var_name="cluster_id", value_name="n")
            .rename(columns={"week_start": "week"}))


def build_agg_daily_volume(messages: pd.DataFrame) -> pd.DataFrame:
    d = messages.dropna(subset=["ts"]).set_index("ts").resample("D").size()
    return d.reset_index(name="n").rename(columns={"ts": "day"})


def build_agg_weekly_rating(fact_meal: pd.DataFrame) -> pd.DataFrame:
    m = (fact_meal.dropna(subset=["ts", "rating_num"]).set_index("ts")
         .resample("W")["rating_num"].agg(["mean", "count"]))
    return m.reset_index().rename(columns={"ts": "week", "mean": "mean_rating",
                                           "count": "n"})


def build_agg_priority_matrix(messages, fact_meal, dim_user, dim_cluster,
                              neg_by_cluster: "pd.Series | None" = None) -> pd.DataFrame:
    """Per-cluster priority frame, labelled with each cluster's own terms.

    Only real clusters are plotted: the NO_CLUSTER_ID bucket has no text, so it
    has no unmet-need signal to place on either axis.

    READING THE AXES. x is the share of conversation volume a cluster's users
    generate, NOT how much demand exists for a topic — clusters are assigned per
    user, so every message a user writes counts under their one cluster. The
    `top_terms` column is carried onto the frame so a bubble can be read as the
    needs behind the segment rather than mistaken for a topic.
    """
    real = messages[messages["cluster_id"] != NO_CLUSTER_ID]
    meal_cl = fact_meal.merge(
        dim_user[["user_id", "cluster_id"]].drop_duplicates("user_id"),
        on="user_id", how="left")
    pm = metrics.priority_matrix_frame(real, meal_cl, neg_by_cluster=neg_by_cluster)
    out = pm.reset_index()

    # Resolve the label and colour here, from the dim_cluster this same run
    # built, so an unknown key raises at export instead of plotting as an
    # unlabelled bubble. The dashboard used to recover the label with a DAX
    # LOOKUPVALUE, which returns BLANK for a key it cannot find and therefore
    # failed silently.
    cl = dim_cluster.set_index("cluster_id")
    unknown = sorted(set(out["cluster_id"]) - set(cl.index))
    if unknown:
        raise KeyError(
            f"priority matrix has clusters absent from dim_cluster: {unknown}. "
            "dim_cluster and the labels must come from the same clustering run.")
    out["name"] = out["cluster_id"].map(cl["name"])
    out["top_terms"] = out["cluster_id"].map(cl["top_terms"])
    out["color_hex"] = out["cluster_id"].map(cl["color_hex"])
    return out


def build_dim_cluster(prof: pd.DataFrame, resolved: dict) -> pd.DataFrame:
    """The dashboard's one categorisation dimension.

    `resolved` is `taxonomy.resolve_cluster_names`' output:
    {cluster_id: {"name", "marker", "description", "provisional"}}.

    Colour and sort by SIZE RANK, not cluster_id. Cluster ids are assigned by
    the clustering run and carry no meaning across runs, so binding a colour to
    an id makes the dashboard re-colour itself on every re-cluster. Rank by
    n_users is stable in the way that matters: the biggest cluster keeps the
    primary brand hue. Ties break on cluster_id so the result is deterministic.
    """
    d = prof.reset_index().rename(columns={"archetype": "cluster_id"})
    d["name"] = d["cluster_id"].map(lambda c: resolved[c]["name"])
    d["name_is_provisional"] = d["cluster_id"].map(
        lambda c: bool(resolved[c]["provisional"]))
    d["description"] = d["cluster_id"].map(
        lambda c: resolved[c].get("description", ""))
    d["is_real_cluster"] = True
    if "top_terms" not in d.columns:
        d["top_terms"] = ""

    order = (d.sort_values(["n_users", "cluster_id"], ascending=[False, True],
                           kind="stable")["cluster_id"].tolist())
    rank = {cid: i for i, cid in enumerate(order)}
    d["display_order"] = d["cluster_id"].map(rank)
    palette = theme.cluster_colors(len(order))   # warns past the validated ceiling
    d["color_hex"] = d["display_order"].map(lambda i: palette[i])

    # The no-text bucket, appended last so it sorts to the end of every legend
    # and slicer. is_real_cluster is the flag the dashboard filters on.
    d = pd.concat([d, pd.DataFrame([{
        "cluster_id": NO_CLUSTER_ID, "name": NO_CLUSTER_NAME, "top_terms": "",
        "n_users": pd.NA, "n_messages": pd.NA, "median_age": pd.NA,
        "display_order": len(order), "color_hex": theme.NO_TEXT_COLOR,
        "is_real_cluster": False, "name_is_provisional": False,
        "description": "",
    }])], ignore_index=True)

    cols = ["cluster_id", "name", "description", "top_terms", "n_users",
            "n_messages", "median_age", "display_order", "color_hex",
            "is_real_cluster", "name_is_provisional"]
    return d[[c for c in cols if c in d.columns]]


def build_dim_subcluster(sub_lab, messages, resolved, terms, dim_cluster,
                         meta) -> pd.DataFrame:
    """The subcategory lookup: one row per child, plus the no-text bucket.

    `sub_lab` is `subclusters.subcluster_all`'s Series (user_id ->
    subcluster_id), `resolved` and `terms` are keyed by subcluster_id, `meta` by
    cluster_id.

    The name is carried here AS WELL AS on the fact tables. That duplication is
    deliberate: Power BI's sort-by-column requires the sorted column and its
    sort key in the same table, so a name on `fact_message` cannot be ordered by
    a `display_order` here. Without it every subcategory legend alphabetises.

    Colour and `display_order` position within a parent are keyed by SIZE RANK
    (n_users, descending), never by `subcluster_id` -- the id is composite
    (`cluster_id * 10 + child_index`) and run-scoped, so sorting by it would
    only coincidentally match size rank, and silently stop matching the moment
    a future run's child numbering changes. Ties break on ascending
    `subcluster_id` for a deterministic result, the same tie-break
    `build_dim_cluster` uses on `cluster_id`. `display_order` is the parent's
    order times ten plus that size-rank position, so children sort directly
    beneath their own parent in a flat legend.
    """
    n_users = sub_lab.value_counts()
    msg_sub = messages["user_id"].map(sub_lab.to_dict())
    n_messages = msg_sub.value_counts()

    parent_order = dict(zip(dim_cluster["cluster_id"], dim_cluster["display_order"]))
    parent_color = dict(zip(dim_cluster["cluster_id"], dim_cluster["color_hex"]))

    rows = []
    for cid in sorted(c for c in meta):
        children = sorted(
            (s for s in n_users.index if s >= 0 and s // 10 == cid),
            key=lambda s: (-n_users.get(s, 0), s))
        palette = theme.subcluster_colors(parent_color[cid], len(children))
        for idx, sid in enumerate(children):
            rows.append({
                "subcluster_id": int(sid),
                "cluster_id": int(cid),
                "subcluster_name": resolved[sid]["name"],
                "top_terms": ", ".join(list(terms[sid].index)[:6]) if sid in terms else "",
                "n_users": int(n_users.get(sid, 0)),
                "n_messages": int(n_messages.get(sid, 0)),
                "display_order": int(parent_order[cid]) * 10 + idx,
                "color_hex": palette[idx],
                "is_split": bool(meta[cid]["is_split"]),
                "name_is_provisional": bool(resolved[sid]["provisional"]),
            })

    # The no-text bucket, appended last so it sorts to the end of every legend
    # and slicer, mirroring dim_cluster's -1 row. Its counts are pd.NA, not 0,
    # for the same reason build_dim_cluster's -1 row uses pd.NA (see there):
    # `sub_lab` never actually contains NO_SUBCLUSTER_ID in production -- `lab`
    # (and hence `subcluster_all`'s domain) only covers users who HAVE an
    # embedding, and no-text users never enter the embedding matrix at all. The
    # bucket's real membership is established downstream, by build_dim_user /
    # build_fact_message's fillna onto NO_SUBCLUSTER_ID. Reporting 0 here would
    # be a confident lie about those ~194 users disagreeing with dim_user.
    rows.append({
        "subcluster_id": subclusters.NO_SUBCLUSTER_ID,
        "cluster_id": NO_CLUSTER_ID,
        "subcluster_name": subclusters.NO_SUBCLUSTER_NAME,
        "top_terms": "",
        "n_users": pd.NA,
        "n_messages": pd.NA,
        "display_order": (max(parent_order.values()) + 1) * 10,
        "color_hex": theme.NO_TEXT_COLOR,
        "is_split": False,
        "name_is_provisional": False,
    })
    return pd.DataFrame(rows, columns=[
        "subcluster_id", "cluster_id", "subcluster_name", "top_terms",
        "n_users", "n_messages", "display_order", "color_hex", "is_split",
        "name_is_provisional"])


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


def _terms_frame(terms: dict, key: str) -> pd.DataFrame:
    rows = [{key: cid, "rank": rank, "term": term, "weight": float(w)}
            for cid, s in terms.items()
            for rank, (term, w) in enumerate(s.items())]
    return pd.DataFrame(rows, columns=[key, "rank", "term", "weight"])


def build_nlp_cluster_terms(terms: dict) -> pd.DataFrame:
    return _terms_frame(terms, "cluster_id")


def build_nlp_subcluster_terms(terms: dict) -> pd.DataFrame:
    """Top SIBLING-EXCLUSIVE terms per subcategory.

    A separate table rather than a re-graining of `nlp_cluster_terms`: the
    dashboard's "Main Needs" word cloud is bound to that table at parent grain
    and must keep working.
    """
    return _terms_frame(terms, "subcluster_id")


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


def build_nlp_voices(msgs_lab: pd.DataFrame, resolved: dict,
                     terms_by_cluster: "dict | None" = None) -> pd.DataFrame:
    """One verbatim message per cluster, picked by a term distinctive to it.

    `terms_by_cluster` maps cluster_id -> the comma-joined `top_terms` string
    `dim_cluster` carries. It is the fallback pool, searched in this order:

    1. the cluster's naming marker
    2. its top terms that appear in NO other cluster's top terms
    3. its remaining (shared) top terms

    Passing None restricts the search to the marker alone, which is the
    pre-2026-08-04 behaviour and can leave a cluster with no quotable message.

    Step 2 exists because a shared term makes a bad exemplar. "Settling in" and
    "Urgent humanitarian needs" both list *humanitaria*, *cali* and *ipiales*;
    searching those first handed "Settling in" a quote about returning to
    Venezuela, which is close to the opposite of settling. Preferring a term
    unique to the cluster keeps the quote about what distinguishes it.

    `matched_term` records which term actually found the quote. When it differs
    from `resolved[cid]["marker"]` the quote is a fallback, and a consumer
    showing it as an exemplar should say so.
    """
    terms_by_cluster = terms_by_cluster or {}

    def _terms(cid) -> list:
        return [t for t in str(terms_by_cluster.get(int(cid), "")).split(", ") if t]

    # A term is "shared" when more than one cluster lists it among its top terms.
    shared = {t for t in
              (t for cid in terms_by_cluster for t in _terms(cid))
              if sum(t in _terms(c) for c in terms_by_cluster) > 1}

    rows = []
    for cid in sorted(msgs_lab["archetype"].unique()):
        meta = resolved[int(cid)]
        in_cluster = msgs_lab[(msgs_lab["archetype"] == cid)
                              & msgs_lab["message"].str.len().between(60, 190)]

        # A marker can be genuinely absent from every message in this length
        # band -- "regulación" was, for the Settling in cluster, which left that
        # panel rendering an em-dash on the dashboard while five siblings showed
        # a real voice. Falling through the terms keeps the quote DISTINCTIVE
        # rather than dropping to an arbitrary message, and only gives up when
        # nothing distinctive is quotable.
        rest = [t for t in _terms(cid) if t != meta["marker"]]
        candidates = ([meta["marker"]]
                      + [t for t in rest if t not in shared]
                      + [t for t in rest if t in shared])

        message, matched = "—", None
        for term in candidates:
            g = in_cluster[in_cluster["message"].str.contains(
                term, case=False, na=False, regex=False)].sort_values(
                ["user_id", "seq"], kind="stable")
            if len(g):
                message, matched = g["message"].iloc[0], term
                break

        rows.append({"cluster_id": int(cid), "name": meta["name"],
                     "matched_term": matched, "message": message})
    return pd.DataFrame(rows)


# Version of the DASHBOARD, bumped by hand when the report's visuals or fields
# change. Deliberately not the package version in pyproject.toml: the code and
# the report move on different cadences, and a viewer reading the footer wants
# to know which report they are looking at, not which library built it.
REPORT_VERSION = "2.0.0"


# ---- bot replies / Coverage Gap Rate (spec 4) ----
# Column order for both tables, declared so an empty run and a full run write
# IDENTICAL headers. Power BI binds to columns by name; a table that appears
# with no columns when the source file is absent breaks every visual on it,
# which is a much worse failure than an empty table.
FACT_BOT_TURN_COLUMNS = ["turn_id", "user_id", "ts", "has_survey_record",
                         "gap_flag", "handoff_flag"]
AGG_COVERAGE_GAP_COLUMNS = ["metric", "grain", "numerator", "denominator",
                            "rate_pct", "rate_quotable", "is_floor",
                            "precision", "recall", "recall_lo", "recall_hi",
                            "n_labelled", "window_start", "window_end"]


def build_fact_bot_turn(turns: pd.DataFrame, dim_user: pd.DataFrame) -> pd.DataFrame:
    """One row per bot turn, flags only -- NO message or reply text.

    The text is what makes this data useful and also what makes it dangerous:
    a reply quotes the user's city, family situation and legal status back at
    them. `qa.pii_scan` would pass it (there is no phone number in it), which is
    exactly why the exclusion is structural here rather than left to the scan.
    Nothing downstream needs the text: the KPI is two counts.

    `has_survey_record` is the join flag, not a filter. 128 of the 216 users in
    this log have no survey row, so a visual that silently inner-joins to
    `dim_user` would report the rate over 88 users while labelling it 216.
    """
    known = set(dim_user["user_id"]) if len(dim_user) else set()
    out = turns.copy()
    out["has_survey_record"] = out["user_id"].isin(known)
    out["ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M:%S")
    return out.reindex(columns=FACT_BOT_TURN_COLUMNS).reset_index(drop=True)


def _rate_row(metric, grain, num, den, window, probe=None) -> dict:
    """One `agg_coverage_gap` row. `probe=None` means unvalidated."""
    quotable = bool(probe["gate_passed"]) if probe else False
    rate = round(100 * num / den, 1) if den else None
    return {
        "metric": metric, "grain": grain,
        "numerator": int(num), "denominator": int(den),
        # Suppression, not deletion: the counts stay so a reader can see the
        # measurement exists and was withheld, the same posture the tone gate
        # takes with sentiment percentages.
        "rate_pct": rate if quotable else None,
        "rate_quotable": quotable,
        "is_floor": bool(probe["rate_is_floor"]) if probe else True,
        "precision": round(probe["precision"], 3) if probe else None,
        "recall": round(probe["recall"], 3) if probe else None,
        "recall_lo": round(probe["recall_lo"], 3) if probe else None,
        "recall_hi": round(probe["recall_hi"], 3) if probe else None,
        "n_labelled": (probe["n_matched"] + probe["n_sampled"]) if probe else None,
        "window_start": window[0], "window_end": window[1],
    }


def build_agg_coverage_gap(turns: pd.DataFrame,
                           gap_probe: "dict | None" = None) -> pd.DataFrame:
    """The KPI table: both metrics at both grains, four rows.

    User grain is the headline and turn grain is the supporting line, in that
    order, because "1 in 6 people asked something SAMI could not answer" is the
    unmet-need statement and "6.7% of turns" is not -- the turn rate reads as a
    93% success rate and hides that the failures concentrate in a few people.
    Both are exported so the dashboard never has to recompute either.

    `gap_probe` is `validation.probe_report`'s dict. Without it (no gold file)
    the gap rate is exported UNQUOTABLE, not omitted: a missing validation must
    look like a withheld number, not like a metric nobody thought to build.
    """
    if turns.empty:
        return pd.DataFrame(columns=AGG_COVERAGE_GAP_COLUMNS)

    ts = pd.to_datetime(turns["ts"], utc=True, errors="coerce")
    window = (ts.min().strftime("%Y-%m-%d"), ts.max().strftime("%Y-%m-%d"))
    n_users, n_turns = turns["user_id"].nunique(), len(turns)

    rows = []
    for metric, flag, probe in (("coverage_gap", "gap_flag", gap_probe),
                                ("human_handoff", "handoff_flag", None)):
        hit = turns[turns[flag]]
        rows.append(_rate_row(metric, "users", hit["user_id"].nunique(),
                              n_users, window, probe))
        rows.append(_rate_row(metric, "turns", len(hit), n_turns, window, probe))
    return pd.DataFrame(rows, columns=AGG_COVERAGE_GAP_COLUMNS)


def build_meta_run(run_meta: dict, nlp_meta: "dict | None" = None,
                   schema_version: str = "9") -> pd.DataFrame:
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


def build_parity_check(reconciliation, dim_user, fact_message, fact_meal,
                       dim_subcluster, entity_coverage_pct: float = 100.0) -> pd.DataFrame:
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
    # reconciliation_table writes the string "pending" here when no response
    # has a usable n_questions value — not a number, so it must never reach
    # float(). Guard rather than let a source-data gap crash the last step
    # of the whole export after every other table has already been written.
    rap_rec_is_numeric = isinstance(rap_rec, (int, float)) and not isinstance(rap_rec, bool)
    rows.append({"metric": "repeat_askers_pct", "exported_value": rap_exp,
                 "reconciliation_value": rap_rec,
                 "match": rap_rec_is_numeric and float(rap_rec) == rap_exp})
    # Categorisation coverage. Unlike the rows above this has no reconciliation
    # counterpart — reconciliation is computed before clustering — so it is
    # matched against the threshold instead.
    cov = round(100 * qa.cluster_coverage(dim_user), 1)
    rows.append({"metric": "cluster_coverage_pct", "exported_value": cov,
                 "reconciliation_value": round(100 * qa.CLUSTER_COVERAGE_THRESHOLD, 1),
                 "match": cov >= 100 * qa.CLUSTER_COVERAGE_THRESHOLD})
    # Subcategory floor. Like cluster_coverage_pct this is a THRESHOLD gate, not
    # an equality check: reconciliation_value holds the floor, not an
    # independently recomputed figure. The floor is a disclosure control, so a
    # failure here is a privacy failure, not only a statistical one.
    smallest = qa.min_subcluster_size(dim_subcluster)
    rows.append({"metric": "subcluster_min_users",
                 "exported_value": smallest,
                 "reconciliation_value": subclusters.SUBCLUSTER_MIN_USERS,
                 "match": smallest >= subclusters.SUBCLUSTER_MIN_USERS})
    # Entity-dictionary coverage. A THRESHOLD row against the HARD floor only.
    # The soft drift floor (qa.ENTITY_COVERAGE_WARN) is a warning in
    # run_pipeline, deliberately NOT here: a parity row that is False stops the
    # run publishing at all, which is right for "the registry failed to load"
    # and wrong for "the dictionary is drifting".
    hard = round(100 * qa.ENTITY_COVERAGE_HARD_FLOOR, 1)
    rows.append({"metric": "entity_coverage_pct",
                 "exported_value": round(float(entity_coverage_pct), 1),
                 "reconciliation_value": hard,
                 "match": round(float(entity_coverage_pct), 1) >= hard})
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

    Every table the pipeline builds is written every run, so an orphan CSV in
    `out` means either a failed or interrupted run left partial output behind,
    or the file is left over from an older export whose table set has since
    changed (a renamed or removed table). Power BI and the notebooks load
    every CSV in the folder without complaint, silently joining stale data
    to today's cohort. They are not deleted here so the run can flag them
    instead and let a human decide.
    """
    orphans = sorted(
        p.name for p in out.glob("*.csv")
        if not p.name.startswith("_") and p.stem not in written)
    if orphans:
        warnings.warn(
            f"{len(orphans)} table(s) in {out} were NOT written by this run and "
            f"may be from a failed run or an older export: {', '.join(orphans)}. "
            "They are absent from _manifest.csv. Delete them, or re-run the "
            "pipeline to confirm they are regenerated.",
            stacklevel=2)
