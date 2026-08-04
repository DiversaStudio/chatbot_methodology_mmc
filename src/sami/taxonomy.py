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
import re
import warnings
import unicodedata
import pandas as pd


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# ---- institutions / procedures dictionary ----
ENTITY_PATTERNS: dict[str, list[str]] = {
    "PPT": [r"\bppt\b", r"permiso por proteccion temporal"],
    "PEP": [r"\bpep\b", r"permiso especial de permanencia"],
    "Visa": [r"\bvisa\b", r"\bvisas\b"],
    "Cédula de extranjería": [r"cedula de extranjeria"],
    "Pasaporte": [r"\bpasaporte\b"],
    "EPS": [r"\beps\b", r"afiliacion en salud", r"seguro de salud"],
    "SISBÉN": [r"\bsisben\b"],
    "Migración Colombia": [r"migracion colombia", r"\bmigracion\b"],
    "ACNUR": [r"\bacnur\b", r"\bunhcr\b"],
    "Cancillería": [r"cancilleria"],
    "Registraduría": [r"registraduria"],
    "SENA": [r"\bsena\b"],
    "ICBF": [r"\bicbf\b"],
    "Refugio/Asilo": [r"\brefugio\b", r"\basilo\b", r"solicitante de refugio"],
    "Trabajo/Empleo": [r"\bempleo\b", r"\btrabajo\b", r"permiso de trabajo"],
    "Educación": [r"\beducacion\b", r"\bcolegio\b", r"\bestudios?\b", r"convalidacion"],
    "Vivienda/Arriendo": [r"\barriendo\b", r"\bvivienda\b", r"subsidio de arriendo"],
    "Ayuda humanitaria": [r"ayuda humanitaria", r"asistencia humanitaria"],
}
_COMPILED = {k: [re.compile(p) for p in pats] for k, pats in ENTITY_PATTERNS.items()}


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
ENTITY_KIND: dict[str, str] = {
    "PPT": "procedure", "PEP": "procedure", "Visa": "procedure",
    "Cédula de extranjería": "procedure", "Pasaporte": "procedure",
    "EPS": "procedure", "SISBÉN": "procedure",
    "Refugio/Asilo": "procedure", "Trabajo/Empleo": "procedure",
    "Vivienda/Arriendo": "procedure", "Ayuda humanitaria": "procedure",
    "Educación": "procedure",
    "Migración Colombia": "institution", "ACNUR": "institution",
    "Cancillería": "institution", "Registraduría": "institution",
    "SENA": "institution", "ICBF": "institution",
}


def entity_counts_by_kind(texts) -> dict[str, pd.Series]:
    """Split entity_counts into an institution Series and a procedure Series."""
    counts = entity_counts(texts)
    out: dict[str, pd.Series] = {}
    for kind in ("institution", "procedure"):
        names = [k for k, v in ENTITY_KIND.items() if v == kind]
        out[kind] = counts[counts.index.isin(names)].sort_values(ascending=False)
    return out


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
CLUSTER_NAMES: list[dict[str, str]] = [
    {"marker": "terminal", "name": "Urgent humanitarian needs",
     "blurb": "Food, shelter, disability and transport support — often at a bus "
              "terminal or border town, often stated as urgent."},
    {"marker": "nacionalidad", "name": "Nationality and family papers",
     "blurb": "Colombian nationality for a child born here: birth registration, "
              "apostilles, parents' documents."},
    {"marker": "rumv", "name": "Stuck mid-procedure",
     "blurb": "Already inside the RUMV/PPT pipeline and blocked: biometrics, "
              "appointments, guardianship for minors, collection."},
    {"marker": "visitante", "name": "Permits, visas and travel",
     "blurb": "Regularising as an adult — PPT, visitor permits, salvoconductos, "
              "cédula de extranjería, extensions and onward travel."},
    {"marker": "regulación", "name": "Settling in",
     "blurb": "Housing, education, transport and regularisation — building a life "
              "here rather than meeting an emergency."},
    {"marker": "emprendimiento", "name": "Building a livelihood",
     "blurb": "Work, training and enterprise support — planning ahead, not in crisis."},
]


def resolve_cluster_names(terms: dict[int, "pd.Series"],
                          n_auto_terms: int = 3) -> dict[int, dict]:
    """Name every cluster in `terms`, auto-naming the ones no marker matches.

    `terms` is what `clusters.ctfidf_terms` returns: {cluster_id -> Series of
    term -> weight, descending}. Returns {cluster_id -> {"name", "marker",
    "provisional"}}.

    Each registry entry is claimed at most once, and clusters are visited in
    ascending id order, so the result is deterministic when two clusters happen
    to share a marker: the lower id wins it and the other is auto-named.

    This function NEVER raises. A cluster it cannot place gets a name built from
    its own top terms, `provisional=True`, and a warning. That is deliberate: an
    unreviewed cluster name is a thing to flag on the dashboard, not a reason to
    refuse to produce the export at all.
    """
    unclaimed = list(CLUSTER_NAMES)
    out: dict[int, dict] = {}
    provisional: list[int] = []

    for cid in sorted(terms):
        top = list(terms[cid].index)
        top_set = set(top)
        entry = next((e for e in unclaimed if e["marker"] in top_set), None)
        if entry is not None:
            unclaimed.remove(entry)
            out[int(cid)] = {"name": entry["name"], "marker": entry["marker"],
                             "provisional": False}
            continue
        head = top[:n_auto_terms]
        out[int(cid)] = {
            "name": f"Cluster {int(cid)} · {', '.join(head)}",
            # The top term stands in for a curated marker so downstream consumers
            # (e.g. export.build_nlp_voices) can still pick a representative quote.
            "marker": head[0] if head else "",
            "provisional": True,
        }
        provisional.append(int(cid))

    if provisional:
        warnings.warn(
            f"{len(provisional)} cluster(s) matched no marker in CLUSTER_NAMES and "
            f"were given provisional auto-names: {provisional}. They are flagged "
            "`name_is_provisional` in dim_cluster. Read their top terms and add an "
            "entry to taxonomy.CLUSTER_NAMES to name them properly.",
            stacklevel=2)
    return out

