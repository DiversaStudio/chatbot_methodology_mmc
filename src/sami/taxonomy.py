"""Cluster-name registry + dictionary extraction of institutions/procedures.

The platform's own `Chat_summary` categorisation was removed on 2026-08-03: it
is the bot summarising itself, its coverage was degrading as the v2 platform
moved to free prose, and the discovered clusters replaced it as the pipeline's
single categorisation axis. See
docs/superpowers/specs/2026-08-03-cluster-categorization-migration-design.md.
"""
from __future__ import annotations
from collections import Counter
from typing import Iterable
import csv
import io
import re
import warnings
import unicodedata
from pathlib import Path
import pandas as pd

from . import config


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# ---- institutions / procedures dictionary ----
# The dictionary lives in a CSV registry (config.entities_path()), NOT here: the
# shipped src/sami/entities.csv, or a gitignored config/entities.csv when a local
# override is in place. It is edited by people
# who do not write Python, and a change to it must be a reviewable diff rather
# than a code change. `ENTITY_PATTERNS` and `ENTITY_KIND` are DERIVED from that
# file at import so every existing consumer keeps working unchanged.
ENTITY_KINDS = ("institution", "procedure", "ignore")
COUNTED_KINDS = ("institution", "procedure")
_ENTITY_COLUMNS = ("entity", "kind", "pattern", "notes")

_UTF8_FIX = ("Re-save it as 'CSV UTF-8 (comma delimited)'. Excel on Windows "
             "writes ANSI by default, which mangles accented entity names and "
             "silently stops them matching.")


class EntityRegistryError(ValueError):
    """The entity registry is unusable. Always names every problem found."""


def read_entity_rows(path) -> list[dict]:
    """Parse the registry CSV. Raises EntityRegistryError on unreadable input."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise EntityRegistryError(
            f"entity registry not found: {path}\n{_UTF8_FIX}") from None
    except UnicodeDecodeError:
        raise EntityRegistryError(
            f"{path} is not UTF-8. {_UTF8_FIX}") from None
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in _ENTITY_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise EntityRegistryError(
            f"{path} is missing column(s): {', '.join(missing)}. "
            f"Expected header: {','.join(_ENTITY_COLUMNS)}")
    return [{c: (row.get(c) or "").strip() for c in _ENTITY_COLUMNS}
            for row in reader if any((row.get(c) or "").strip()
                                     for c in _ENTITY_COLUMNS)]


def validate_entity_rows(rows: list[dict]) -> None:
    """Raise EntityRegistryError naming EVERY problem, not just the first.

    A person fixing this file should get one list, not a dozen re-runs.
    """
    problems: list[str] = []
    kind_of: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows, start=2):  # +2: header is line 1
        ent, kind, pat = row["entity"], row["kind"], row["pattern"]
        if not ent:
            problems.append(f"line {i}: empty entity name")
        if kind not in ENTITY_KINDS:
            problems.append(
                f"line {i}: kind {kind!r} is not one of {', '.join(ENTITY_KINDS)}")
        if kind in COUNTED_KINDS and not pat:
            problems.append(f"line {i}: a {kind} row needs a pattern")
        if ent and kind in ENTITY_KINDS:
            if ent in kind_of and kind_of[ent] != kind:
                problems.append(
                    f"line {i}: entity {ent!r} carries two kinds "
                    f"({kind_of[ent]!r} and {kind!r})")
            kind_of.setdefault(ent, kind)
        if pat:
            if (ent, pat) in seen:
                problems.append(f"line {i}: duplicate (entity, pattern) for {ent!r}")
            seen.add((ent, pat))
            try:
                re.compile(pat)
            except re.error as exc:
                problems.append(f"line {i}: {pat!r} is not a valid regex ({exc})")
            if pat != pat.lower():
                problems.append(
                    f"line {i}: pattern {pat!r} has uppercase. Patterns match "
                    "accent-folded lowercase text and must be lowercase.")
    if problems:
        raise EntityRegistryError(
            "the entity registry has %d problem(s):\n  - %s"
            % (len(problems), "\n  - ".join(problems)))


def load_entity_registry(path=None) -> list[dict]:
    rows = read_entity_rows(path or config.entities_path())
    validate_entity_rows(rows)
    return rows


def reload_entities(path=None) -> None:
    """Rebuild the derived module globals from the registry file.

    Called once at import. Tests call it with a fixture path and MUST call it
    again with no argument to restore the real registry.
    """
    global ENTITY_REGISTRY, ENTITY_PATTERNS, ENTITY_KIND, IGNORED_TERMS, _COMPILED
    rows = load_entity_registry(path)
    ENTITY_REGISTRY = rows
    ENTITY_PATTERNS = {}
    ENTITY_KIND = {}
    IGNORED_TERMS = set()
    for row in rows:
        if row["kind"] == "ignore":
            if row["entity"]:
                IGNORED_TERMS.add(_fold(row["entity"]))
            if row["pattern"]:
                IGNORED_TERMS.add(_fold(row["pattern"]))
            continue
        ENTITY_PATTERNS.setdefault(row["entity"], []).append(row["pattern"])
        ENTITY_KIND[row["entity"]] = row["kind"]
    _COMPILED = {k: [re.compile(p) for p in pats]
                 for k, pats in ENTITY_PATTERNS.items()}


ENTITY_REGISTRY: list[dict] = []
ENTITY_PATTERNS: dict[str, list[str]] = {}
ENTITY_KIND: dict[str, str] = {}
IGNORED_TERMS: set[str] = set()
_COMPILED: dict[str, list] = {}
reload_entities()


def extract_entities(text: str) -> set[str]:
    t = _fold(text)
    return {name for name, pats in _COMPILED.items() if any(p.search(t) for p in pats)}


def entity_counts(texts: Iterable[str]) -> pd.Series:
    c: Counter = Counter()
    for t in texts:
        if t is None or (isinstance(t, float) and pd.isna(t)):
            continue
        for ent in extract_entities(t):
            c[ent] += 1
    return pd.Series(c, dtype="int64").sort_values(ascending=False)


# ---- institution vs procedure split (NB2 §1 two-panel) ----
def entity_counts_by_kind(texts) -> dict[str, pd.Series]:
    """Split entity_counts into an institution Series and a procedure Series."""
    counts = entity_counts(texts)
    out: dict[str, pd.Series] = {}
    for kind in ("institution", "procedure"):
        names = [k for k, v in ENTITY_KIND.items() if v == kind]
        out[kind] = counts[counts.index.isin(names)].sort_values(ascending=False)
    return out


# ---- coverage gauge + candidate mining (drift detection) ----
# The dictionary is hand-maintained, so it rots as users' vocabulary moves. This
# measures what the dictionary does NOT recognise and hands a human a ranked
# list of what to consider adding. It NEVER edits the registry itself.
#
# Like CANDIDATE_INTENT_PROBES, the output is a FLOOR on what is missing, never
# a rate: recall is unknown, and no percentage derived from it may be quoted.
_CANDIDATE_TOKEN = re.compile(r"[a-z]{4,}")
# ALL words (any length), used only to test real adjacency for bigrams -- a
# short connector like "a"/"de"/"el" must still occupy a slot between two
# longer words so a bigram is never built across a word that was silently
# dropped by the length filter (see entity_candidates).
_ALL_WORDS = re.compile(r"[a-z]+")


def entity_coverage(texts) -> tuple[int, int]:
    """(messages matching >= 1 entity, messages considered). Nulls are skipped."""
    n_hit = n_tot = 0
    for t in texts:
        if t is None or (isinstance(t, float) and pd.isna(t)):
            continue
        n_tot += 1
        if extract_entities(t):
            n_hit += 1
    return n_hit, n_tot


def entity_stopterms() -> set[str]:
    """Folded terms a candidate must never be.

    City and nationality names are the important entries: `medellin` (97 users)
    would otherwise top the candidates table every single run, and it is
    dim_city's job, not the dictionary's.
    """
    from . import canon
    from .clusters import SAMI_STOPWORDS
    from .load import SPANISH_STOPWORDS

    terms = set(IGNORED_TERMS)
    terms |= {_fold(w) for w in SPANISH_STOPWORDS}
    terms |= {_fold(w) for w in SAMI_STOPWORDS}
    terms |= {_fold(v) for v in canon.CITY_CANON.values()}
    terms |= {_fold(k) for k in canon.CITY_CANON}
    terms |= {_fold(v) for v in canon.NATIONALITY_CANON.values()}
    terms |= {_fold(k) for k in canon.NATIONALITY_CANON}
    # Multiword canon values ("santa marta") also block their parts.
    for v in list(terms):
        terms |= set(v.split())
    return terms


def entity_candidates(messages: pd.DataFrame, min_users: int = 15,
                      top_n: int = 40) -> pd.DataFrame:
    """Rank unigrams and bigrams from messages that matched NO entity.

    `messages` needs `message_id`, `user_id`, `message`. Ranked by distinct
    users (not message count — one prolific user must not invent a trend),
    ties broken alphabetically so the export is byte-stable across runs.
    """
    stop = entity_stopterms()
    per_msg: Counter = Counter()
    per_user: dict[str, set] = {}
    example: dict[str, str] = {}

    for mid, uid, text in zip(messages["message_id"], messages["user_id"],
                              messages["message"]):
        if text is None or (isinstance(text, float) and pd.isna(text)):
            continue
        if extract_entities(text):
            continue                      # recognised: nothing to learn here
        folded = _fold(text)
        # Adjacency must be judged against the REAL text, not against the
        # survivors of the length filter -- otherwise a bigram can splice
        # together two words that a short connector ("ir a", "de", "el"...)
        # actually sat between, fabricating a phrase absent from the corpus.
        all_words = _ALL_WORDS.findall(folded)

        def _qualifies(w: str) -> bool:
            return len(w) >= 4 and w not in stop

        grams = [w for w in all_words if _qualifies(w)]
        grams += [f"{a} {b}" for a, b in zip(all_words, all_words[1:])
                  if _qualifies(a) and _qualifies(b)]
        for g in grams:
            per_msg[g] += 1
            per_user.setdefault(g, set()).add(uid)
            example.setdefault(g, mid)

    rows = [{"term": g, "n_gram": 1 + g.count(" "), "n_msgs": n,
             "n_users": len(per_user[g]), "example_message_id": example[g]}
            for g, n in per_msg.items()
            if len(per_user[g]) >= min_users
            # Belt-and-suspenders: the message-level skip above (extract_entities
            # matched -> skip the whole message) already guarantees no candidate
            # here can match a compiled pattern, so this can never exclude
            # anything today. Kept as defence-in-depth in case a future
            # refactor stops skipping whole messages; do not delete as dead code.
            and not any(p.search(g) for pats in _COMPILED.values() for p in pats)]
    out = pd.DataFrame(rows, columns=["term", "n_gram", "n_msgs", "n_users",
                                      "example_message_id"])
    if out.empty:
        return out
    return (out.sort_values(["n_users", "term"], ascending=[False, True])
            .head(top_n).reset_index(drop=True))


# ---- candidate emergent intents (NB3 §3) ----
# Needs the discovered clusters do not separate out. These are the vocabulary the
# NB3 coverage-gap section may assign to a cluster.
CANDIDATE_INTENT_SLUGS: list[str] = [
    "transport_logistics",
    "human_handoff",
    "connectivity",
    "out_of_scope",
    "other_emergent",
]

# Probes for candidate emergent needs. THESE ARE NOT A CLASSIFIER. NB3 drops LLM
# per-message classification (design §0.1), so nothing here is validated: matches are
# a *floor* on how often a need appears (recall is unknown), never a rate. Findings
# sourced from this map are tagged "directional only" and no percentage is quoted.
# They exist to corroborate, in users' own words, the needs the c-TF-IDF cluster terms
# surfaced — and to let a hypothesised need be honestly reported as ABSENT.
CANDIDATE_INTENT_PROBES: dict[str, str] = {
    "transport_logistics": r"\b(?:pasaje|terminal|transporte|bus|viajar|ruta|traslado|trocha)\b",
    "entrepreneurship": r"\b(?:emprendimiento|emprender|negocio propio|capital semilla|microcr[eé]dito)\b",
    "procedure_troubleshooting": r"\b(?:rumv|biom[eé]trico|no me aparece|no carga|verificar|duplicado)\b",
    "human_handoff": r"(?:hablar con (?:un|una|alguien|alguno|persona)|asesor|un humano|una persona real|comunicarme con)",
    "fraud_protection": r"\b(?:estafa|estafaron|fraude|enga[nñ]o|me robaron)\b",
    "connectivity": r"\b(?:recarga|datos m[oó]viles|saldo|internet|wifi)\b",
}

# ---- bot-reply probes (spec 4) ----
# Applied to SAMI'S OWN REPLIES, not to user messages, which is what makes the
# rate they produce a MEASUREMENT rather than an inference: the assistant says
# it has no information, so nothing has to guess what the user felt.
#
# They are still regexes. `COVERAGE_GAP_PROBE` is the one that reaches a KPI
# card, so it is the one with a hand-labelled gold set behind it
# (`validation/gap_gold_labels.csv`) and a precision gate in front of it
# (`validation.GAP_PRECISION_GATE`). Editing this pattern INVALIDATES that
# measurement -- re-run the labelling pass, do not just re-run the pipeline.
COVERAGE_GAP_PROBE = (
    r"no (?:tengo|cuento con|dispongo de|manejo|poseo|encuentro)\s+"
    r"(?:la\s+|con\s+)?(?:informaci[oó]n|datos|registros|detalles)"
    r"|no (?:puedo|podr[ií]a) (?:brindarte|darte|proporcionarte|ofrecerte)\s+"
    r"(?:esa|esta|la|m[aá]s)\s+informaci[oó]n"
    r"|no (?:tengo|dispongo de) (?:acceso|conocimiento)"
    r"|no hay informaci[oó]n disponible"
)

# NOT validated and NOT gated: no gold set covers it, so it is a floor with an
# unmeasured recall, exported with `rate_quotable=False`. It is also NOT a
# failure -- routing someone to a caseworker is usually SAMI working as
# designed. It sits beside the gap rate to stop a reader assuming the gap rate
# is the whole of "SAMI could not help", and its label must say so.
HUMAN_HANDOFF_PROBE = (
    r"asesor|persona del equipo|equipo humano|te conecto"
    r"|comunicarte con|contactar con|l[ií]nea de atenci[oó]n"
)


# Cluster names, keyed by MARKER TERM rather than by cluster id.
#
# Cluster ids are assigned by one clustering run and carry no meaning across
# runs: a data refresh reshuffles them freely. The previous id-keyed dict had to
# be hand-rewritten every time that happened, and `assert_archetype_mapping`
# hard-failed the whole export until someone did. Keying on a term that is
# distinctive to the cluster's content means the name follows the cluster.
#
# `marker` MUST be a term that appears in the cluster's top c-TF-IDF terms. The
# pipeline requests top_n=40 while NB3 renders top_n=12, so a marker ranked
# below 12 resolves in the pipeline and looks unresolved in the notebook --
# choose markers from the top handful.
#
# Names below were read off the k=6 solution on the 1,198-user v2 corpus
# (2026-07-28). A cluster whose marker no longer appears is auto-named and
# flagged provisional rather than blocking the run; review the terms and add or
# amend an entry here when that happens.
#
# `description` is curated prose for the dashboard's archetype panel (spec 3
# §9). It is owned by Diversa, not derived from the data. A cluster that
# auto-names gets "" — the panel renders without prose rather than inventing it.
CLUSTER_NAMES: list[dict[str, str]] = [
    {"marker": "terminal", "name": "Urgent humanitarian needs",
     "description": "Food, shelter, disability and transport support — often at a bus "
              "terminal or border town, often stated as urgent."},
    {"marker": "nacionalidad", "name": "Nationality and family papers",
     "description": "Colombian nationality for a child born here: birth registration, "
              "apostilles, parents' documents."},
    {"marker": "rumv", "name": "Stuck mid-procedure",
     "description": "Already inside the RUMV/PPT pipeline and blocked: biometrics, "
              "appointments, guardianship for minors, collection."},
    {"marker": "visitante", "name": "Permits, visas and travel",
     "description": "Regularising as an adult — PPT, visitor permits, salvoconductos, "
              "cédula de extranjería, extensions and onward travel."},
    {"marker": "regulación", "name": "Settling in",
     "description": "Housing, education, transport and regularisation — building a life "
              "here rather than meeting an emergency."},
    {"marker": "emprendimiento", "name": "Building a livelihood",
     "description": "Work, training and enterprise support — planning ahead, not in crisis."},
]


# Subcategory names, keyed by MARKER TERM exactly as CLUSTER_NAMES is.
#
# Authored 2026-08-06 off the first two real runs of the second pass (identical
# results both times), reading `exports/nlp_subcluster_terms.csv` -- which is
# already the SIBLING-EXCLUSIVE term list, not the raw top terms.
#
# A marker MUST appear in the child's SIBLING-EXCLUSIVE terms
# (`subclusters.exclusive_terms`), not merely its raw top terms: siblings of one
# parent share most of their vocabulary, and a marker on a shared term would be
# claimed by whichever child is visited first. Markers here were also checked to
# be unique across ALL twelve children, because `resolve_names` visits ids in
# ascending order and claims each entry once -- a term two children share would
# be taken by the lower id and the other would auto-name.
#
# Grouped by parent, in `subcluster_id` order. There is no `description` field:
# `build_dim_subcluster` exports no description column, so prose here would be
# dead data. Parent-level prose lives in `CLUSTER_NAMES[*]["description"]`.
SUBCLUSTER_NAMES: list[dict[str, str]] = [
    # -- Building a livelihood --
    {"marker": "emprendimiento", "name": "Starting a business"},
    {"marker": "buscando", "name": "Looking for work and training"},
    # -- Stuck mid-procedure --
    {"marker": "biométrico", "name": "Biometrics and minors' documents"},
    {"marker": "jornada", "name": "Brigades and paperwork steps"},
    # -- Nationality and family papers --
    {"marker": "ciudadanía", "name": "Family nationality options"},
    {"marker": "españa", "name": "Regularising status abroad"},
    {"marker": "apostillado", "name": "Apostilles and birth records"},
    # -- Permits, visas and travel --
    {"marker": "canadá", "name": "Visas and travel abroad"},
    {"marker": "prórroga", "name": "Expiring permits and renewals"},
    # -- Urgent humanitarian needs --
    {"marker": "hospital", "name": "Health access and registration"},
    {"marker": "alimentación", "name": "Food and shelter from organisations"},
    # -- Settling in (did not split; this child is the whole parent) --
    {"marker": "danes", "name": "Services and integration"},
]


def resolve_names(terms: dict[int, "pd.Series"], registry: list[dict],
                  n_auto_terms: int = 3, kind: str = "cluster") -> dict[int, dict]:
    """Name every cluster in `terms` from `registry`, auto-naming the rest.

    `terms` is what `clusters.ctfidf_terms` returns: {id -> Series of term ->
    weight, descending}. Returns {id -> {"name", "marker", "description",
    "provisional"}}.

    Each registry entry is claimed at most once, and ids are visited in
    ascending order, so the result is deterministic when two clusters share a
    marker: the lower id wins it and the other is auto-named.

    `kind` only shapes the warning text, so a reader is told which registry to
    edit -- CLUSTER_NAMES or SUBCLUSTER_NAMES.

    This function NEVER raises. Something it cannot place gets a name built from
    its own top terms, `provisional=True`, and a warning. That is deliberate: an
    unreviewed name is a thing to flag on the dashboard, not a reason to refuse
    to produce the export at all.
    """
    unclaimed = list(registry)
    out: dict[int, dict] = {}
    provisional: list[int] = []

    for cid in sorted(terms):
        top = list(terms[cid].index)
        top_set = set(top)
        entry = next((e for e in unclaimed if e["marker"] in top_set), None)
        if entry is not None:
            unclaimed.remove(entry)
            out[int(cid)] = {"name": entry["name"], "marker": entry["marker"],
                             "description": entry.get("description", ""),
                             "provisional": False}
            continue
        head = top[:n_auto_terms]
        label = "Cluster" if kind == "cluster" else "Subcluster"
        out[int(cid)] = {
            "name": f"{label} {int(cid)} · {', '.join(head)}",
            # The top term stands in for a curated marker so downstream consumers
            # (e.g. export.build_nlp_voices) can still pick a representative quote.
            "marker": head[0] if head else "",
            "description": "",
            "provisional": True,
        }
        provisional.append(int(cid))

    if provisional:
        reg_name = "CLUSTER_NAMES" if kind == "cluster" else "SUBCLUSTER_NAMES"
        warnings.warn(
            f"{len(provisional)} {kind}(s) matched no marker in {reg_name} and "
            f"were given provisional auto-names: {provisional}. They are flagged "
            f"`name_is_provisional` in the export. Read their top terms and add "
            f"an entry to taxonomy.{reg_name} to name them properly.",
            stacklevel=2)
    return out


def resolve_cluster_names(terms: dict[int, "pd.Series"],
                          n_auto_terms: int = 3) -> dict[int, dict]:
    """Name every cluster from CLUSTER_NAMES. See `resolve_names`."""
    return resolve_names(terms, CLUSTER_NAMES, n_auto_terms=n_auto_terms,
                         kind="cluster")

