"""Clustering, stability and interpretation for NB3 archetypes.

Clustering is *discovery*, not the headline (doc 02 §6.2): k comes from a scan,
never from fiat, and a solution that fails the stability bar is reported as
"soft structure" rather than dressed up as hard segments.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score

STABILITY_BAR = 0.6  # mean pairwise ARI required to call clusters stable

# Greetings, bot boilerplate and high-frequency function words carry no signal but
# dominate raw frequency. Kept deliberately aggressive: with a distinct-user floor also
# applied, anything left in a rendered term list should be content-bearing.
SAMI_STOPWORDS: set[str] = {
    # greetings / courtesy / bot boilerplate
    "hola", "buenas", "buenos", "dias", "días", "tardes", "noches", "gracias", "gracia",
    "favor", "porfavor", "señor", "senora", "señora", "senor", "saludos", "cordial",
    "sami", "samy", "bot", "chat", "mensaje", "buen", "dia", "muchisima", "muchísima",
    # modal / verbal filler
    "quiero", "necesito", "saber", "ayuda", "ayudar", "puede", "puedo", "pueden",
    "hacer", "hago", "tengo", "tiene", "tienen", "hace", "estoy", "esta", "está",
    "soy", "somos", "seria", "sería", "quisiera", "deseo", "poder", "sacar", "sacando",
    "solicitar", "obtener", "gustaria", "gustaría", "decir", "dar", "ver", "ir",
    # determiners / prepositions / connectives
    "para", "por", "una", "uno", "unos", "unas", "los", "las", "del", "con", "sin",
    "mas", "más", "muy", "este", "esto", "esta", "estos", "esas", "eso", "ese",
    "donde", "dónde", "cuando", "cuándo", "como", "cómo", "cual", "cuál", "cuales",
    "cuáles", "que", "qué", "quien", "quién", "porque", "pero", "también", "tambien",
    "todo", "toda", "todos", "todas", "otro", "otra", "otros", "otras", "mismo",
    "ahora", "aqui", "aquí", "alla", "allá", "desde", "hasta", "sobre", "entre",
    "cada", "algun", "algún", "alguna", "solo", "sólo", "ningun", "ningún", "nada",
    # low-content generic nouns/adjectives seen dominating panels
    "informacion", "información", "info", "verdad", "tipos", "tipo", "manera",
    "momento", "parte", "caso", "cosa", "cosas", "vez", "veces", "bien", "okay",
}


def _kmeans(X: np.ndarray, k: int, random_state: int = 0) -> KMeans:
    return KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(X)


def k_scan(X: np.ndarray, k_range=range(4, 13), random_state: int = 0) -> pd.DataFrame:
    """Silhouette + Davies-Bouldin per k. Annex figure source (doc 02 §6.2)."""
    rows = []
    for k in k_range:
        labels = _kmeans(X, k, random_state).labels_
        rows.append(
            {
                "k": k,
                "silhouette": float(silhouette_score(X, labels)),
                "davies_bouldin": float(davies_bouldin_score(X, labels)),
            }
        )
    return pd.DataFrame(rows).set_index("k")


def silhouette_is_flat(scan: pd.DataFrame, rel_tol: float = 0.05) -> bool:
    """True when the silhouette curve cannot discriminate between candidate k.

    On the SAMI corpus the whole curve sits in 0.028-0.040 — near zero in absolute
    terms and with a spread far smaller than the metric's own sampling noise. When
    this is True, picking k by argmax silhouette is picking noise, and `choose_k`
    must fall back to the stability criterion.
    """
    return bool((scan["silhouette"].max() - scan["silhouette"].min()) < rel_tol)


def choose_k(
    scan: pd.DataFrame,
    stability_by_k: dict[int, dict] | None = None,
    margin: float = 1.0,
) -> int:
    """Pick k from the scan, preferring stability when silhouette cannot discriminate.

    Without `stability_by_k`: best silhouette, ties broken by lower Davies-Bouldin.

    With `stability_by_k` (as returned by `stability_curve`): take the **largest k
    whose bootstrap stability clears STABILITY_BAR by at least `margin` standard
    deviations** — maximal cluster resolution subject to robust stability. This is
    the operative rule for SAMI, where silhouette is flat (see `silhouette_is_flat`)
    but stability falls sharply with k, so k is chosen on the criterion that actually
    varies. Falls back to argmax silhouette if no k clears the bar, in which case the
    caller must report the solution as soft structure.
    """
    if stability_by_k:
        passing = [
            k
            for k, s in sorted(stability_by_k.items())
            if s["mean_ari"] - margin * s["std_ari"] >= STABILITY_BAR
        ]
        if passing:
            return int(max(passing))
    best = scan.sort_values(["silhouette", "davies_bouldin"], ascending=[False, True])
    return int(best.index[0])


def stability_curve(
    X: np.ndarray, k_range=range(3, 9), n_boot: int = 30, random_state: int = 0
) -> dict[int, dict]:
    """`stability_ari` across a range of k — the evidence `choose_k` selects on."""
    return {
        int(k): stability_ari(X, int(k), n_boot=n_boot, random_state=random_state)
        for k in k_range
    }


def stability_ari(
    X: np.ndarray, k: int, n_boot: int = 50, frac: float = 0.8, random_state: int = 0
) -> dict:
    """Mean pairwise ARI across bootstrap resamples of the users.

    Each resample takes `frac` of rows without replacement and refits KMeans.
    Pairs of solutions are compared on the users they share, which is what makes
    the ARI meaningful across differently-sampled fits. `stable` is the doc 02
    §6.2 bar: mean pairwise ARI >= 0.6.
    """
    rng = np.random.default_rng(random_state)
    n = X.shape[0]
    size = max(k + 1, int(round(frac * n)))

    runs: list[tuple[np.ndarray, np.ndarray]] = []
    for b in range(n_boot):
        idx = rng.choice(n, size=size, replace=False)
        labels = _kmeans(X[idx], k, random_state=int(rng.integers(0, 2**31 - 1))).labels_
        runs.append((idx, labels))

    aris: list[float] = []
    for i in range(len(runs)):
        idx_i, lab_i = runs[i]
        map_i = dict(zip(idx_i.tolist(), lab_i.tolist()))
        for j in range(i + 1, len(runs)):
            idx_j, lab_j = runs[j]
            map_j = dict(zip(idx_j.tolist(), lab_j.tolist()))
            shared = np.intersect1d(idx_i, idx_j)
            if shared.size < 2:
                continue
            a = [map_i[s] for s in shared.tolist()]
            b = [map_j[s] for s in shared.tolist()]
            aris.append(float(adjusted_rand_score(a, b)))

    mean_ari = float(np.mean(aris)) if aris else float("nan")
    return {
        "mean_ari": mean_ari,
        "std_ari": float(np.std(aris)) if aris else float("nan"),
        "n_pairs": len(aris),
        "stable": bool(mean_ari >= STABILITY_BAR),
    }


def _tokenize(doc: str) -> list[str]:
    toks = [t for t in "".join(c if c.isalpha() or c.isspace() else " " for c in doc.lower()).split()]
    return [t for t in toks if len(t) > 3 and t not in SAMI_STOPWORDS]


def ctfidf_terms(docs, labels, top_n: int = 10, min_user_df: int = 5) -> dict[int, pd.Series]:
    """Class-based TF-IDF: terms distinctive to a cluster, not merely frequent in it.

    Documents are pooled per cluster into one "class document"; term frequency
    within a class is weighted by log(N_classes / n_classes_containing_term), so
    a word common to every cluster scores ~0 however often it appears.

    `min_user_df` requires a term to appear in at least that many input documents
    before it can be reported. With one document per user this is a distinct-user
    floor, and it does two jobs at once: it drops vocabulary too rare to be a real
    theme, and it is the **PII guard on rendered term lists** — personal names
    reach only one or two users and are removed without needing a name blocklist
    (spaCy NER is far too noisy on this informal Spanish to filter on). Pass
    `min_user_df=1` only when documents are pooled and the count is meaningless.
    """
    docs = list(docs)
    labels = np.asarray(labels)

    user_df = Counter()
    for d in docs:
        user_df.update(set(_tokenize(d)))
    allowed = {t for t, n in user_df.items() if n >= min_user_df}

    class_counts: dict[int, Counter] = {}
    for lab in np.unique(labels):
        c: Counter = Counter()
        for d in (docs[i] for i in np.where(labels == lab)[0]):
            c.update(t for t in _tokenize(d) if t in allowed)
        class_counts[int(lab)] = c

    n_classes = len(class_counts)
    df_term = Counter()
    for c in class_counts.values():
        df_term.update(c.keys())

    out: dict[int, pd.Series] = {}
    for lab, c in class_counts.items():
        total = sum(c.values()) or 1
        scored = {
            t: (n / total) * np.log(n_classes / df_term[t])
            for t, n in c.items()
            if df_term[t] > 0
        }
        s = pd.Series(scored, dtype="float64").sort_values(ascending=False).head(top_n)
        out[lab] = s
    return out


def archetype_profiles(
    labels: pd.Series, responses: pd.DataFrame, messages: pd.DataFrame,
    sentiment: pd.DataFrame | None = None,
    terms: dict[int, pd.Series] | None = None,
    n_terms: int = 6,
) -> pd.DataFrame:
    """Per-cluster profile: size, distinctive terms, demographic skew, tone.

    `labels` must be a Series indexed by `user_id`. Median age excludes records
    flagged `unreliable_sub18` (P9) — those are never read as a real cohort.

    `terms` is the dict `ctfidf_terms` returns. Its top `n_terms` per cluster are
    joined into `top_terms`, which is what tells a reader what a cluster is
    ABOUT — the column that used to hold the platform's category labels. Passing
    None leaves it blank rather than failing, so a caller that only wants the
    size and demographic columns need not compute terms.
    """
    lab = labels.rename("archetype")
    msgs = messages.merge(lab, left_on="user_id", right_index=True, how="inner")
    resp = responses.merge(lab, left_on="user_id", right_index=True, how="inner")

    if sentiment is not None:
        msgs = msgs.join(sentiment[["label"]].rename(columns={"label": "_sent"}))

    rows = []
    for arch, g in msgs.groupby("archetype"):
        r = resp[resp["archetype"] == arch]
        top_terms = ""
        if terms is not None and int(arch) in terms:
            top_terms = ", ".join(terms[int(arch)].head(n_terms).index)
        if "age_flag" in r.columns:
            ages = r.loc[r["age_flag"] != "unreliable_sub18", "age_num"]
        else:
            ages = r["age_num"] if "age_num" in r.columns else pd.Series(dtype=float)
        row = {
            "archetype": int(arch),
            "n_users": int(g["user_id"].nunique()),
            "n_messages": int(len(g)),
            "top_terms": top_terms,
            "median_age": float(ages.median()) if ages.notna().any() else np.nan,
            "top_city": r["city_canon"].mode().iat[0] if r["city_canon"].notna().any() else None,
            "top_nationality": (
                r["nationality_canon"].mode().iat[0]
                if "nationality_canon" in r.columns and r["nationality_canon"].notna().any()
                else None
            ),
        }
        if sentiment is not None:
            row["pct_negative"] = float((g["_sent"] == "negative").mean())
        rows.append(row)
    return pd.DataFrame(rows).set_index("archetype").sort_values("n_users", ascending=False)


def project_2d(X: np.ndarray, method: str = "umap", random_state: int = 0) -> np.ndarray:
    """One 2D view for the archetype map. No 3D, ever (doc 01 §6)."""
    if method == "umap":
        import umap

        reducer = umap.UMAP(n_components=2, random_state=random_state, n_neighbors=15, min_dist=0.1)
        return np.asarray(reducer.fit_transform(X))
    from sklearn.decomposition import PCA

    return np.asarray(PCA(n_components=2, random_state=random_state).fit_transform(X))
