import warnings

import pandas as pd
import pytest

from sami import taxonomy


def _terms(mapping: dict[int, list[str]]) -> dict[int, pd.Series]:
    """Build the {cluster_id: Series(term -> weight)} shape ctfidf_terms returns."""
    return {cid: pd.Series({t: float(len(ts) - i) for i, t in enumerate(ts)})
            for cid, ts in mapping.items()}


def test_normalize_category_is_gone():
    """The platform's own categorisation is removed from the pipeline entirely."""
    assert not hasattr(taxonomy, "normalize_category")
    assert not hasattr(taxonomy, "OFFICIAL_CATEGORIES")
    assert not hasattr(taxonomy, "ARCHETYPE_NAMES")


def test_resolve_names_matches_by_marker_not_by_id():
    """A cluster keeps its name when the clustering run reshuffles the ids."""
    first = _terms({0: ["terminal", "albergue"], 1: ["rumv", "biometrico"]})
    swapped = _terms({0: ["rumv", "biometrico"], 1: ["terminal", "albergue"]})

    a = taxonomy.resolve_cluster_names(first)
    b = taxonomy.resolve_cluster_names(swapped)

    assert a[0]["name"] == b[1]["name"]
    assert a[1]["name"] == b[0]["name"]
    assert not any(v["provisional"] for v in a.values())


def test_resolve_names_auto_names_unknown_cluster():
    """A cluster matching no marker is named from its terms and flagged."""
    terms = _terms({0: ["terminal"], 7: ["ecuador", "frontera", "tulcan", "ipiales"]})
    with pytest.warns(UserWarning, match="provisional"):
        out = taxonomy.resolve_cluster_names(terms)

    assert out[7]["provisional"] is True
    assert out[7]["name"] == "Cluster 7 · ecuador, frontera, tulcan"
    assert out[7]["marker"] == "ecuador"
    assert out[0]["provisional"] is False


def test_resolve_names_never_raises_on_total_drift():
    """Every marker gone is a warning, not an exception -- the export completes."""
    terms = _terms({0: ["zzz"], 1: ["qqq"]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = taxonomy.resolve_cluster_names(terms)
    assert set(out) == {0, 1}
    assert all(v["provisional"] for v in out.values())


def test_resolve_names_claims_each_registry_entry_once():
    """Two clusters sharing a marker do not both get the same name."""
    terms = _terms({0: ["terminal", "albergue"], 1: ["terminal", "comida"]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = taxonomy.resolve_cluster_names(terms)
    assert out[0]["name"] != out[1]["name"]
    assert out[0]["provisional"] is False   # lowest id claims the marker
    assert out[1]["provisional"] is True


def test_extract_entities():
    ents = taxonomy.extract_entities("Necesito ayuda con mi PPT y la afiliación en salud EPS")
    assert "PPT" in ents and "EPS" in ents


def test_entity_kind_covers_all_patterns():
    from sami import taxonomy
    assert set(taxonomy.ENTITY_KIND) == set(taxonomy.ENTITY_PATTERNS)
    assert set(taxonomy.ENTITY_KIND.values()) <= {"institution", "procedure"}


def test_entity_counts_by_kind_partitions():
    from sami import taxonomy
    texts = ["Necesito mi PPT y afiliación EPS",           # procedures
             "Fui a Migración Colombia y ACNUR"]            # institutions
    out = taxonomy.entity_counts_by_kind(texts)
    assert set(out) == {"institution", "procedure"}
    assert out["procedure"].get("PPT", 0) >= 1
    assert out["institution"].get("ACNUR", 0) >= 1
    # no entity appears in both panels
    assert set(out["institution"].index).isdisjoint(set(out["procedure"].index))


def test_candidate_intent_probes_compile_and_use_known_slugs():
    import re as _re
    from sami import taxonomy as tx
    assert set(tx.CANDIDATE_INTENT_PROBES) <= set(tx.CANDIDATE_INTENT_SLUGS + [
        "entrepreneurship", "procedure_troubleshooting", "fraud_protection"])
    for pat in tx.CANDIDATE_INTENT_PROBES.values():
        _re.compile(pat)
