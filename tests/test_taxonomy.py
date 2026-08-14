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
    first = _terms({0: ["terminal", "albergue"], 1: ["biométrico", "tramite"]})
    swapped = _terms({0: ["biométrico", "tramite"], 1: ["terminal", "albergue"]})

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
    assert "PPT" in ents and "Salud/EPS" in ents


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


def test_cluster_names_entries_all_carry_a_description():
    """Every curated name has prose; spec 3's archetype panel reads this."""
    for entry in taxonomy.CLUSTER_NAMES:
        assert "description" in entry, entry["name"]
        assert isinstance(entry["description"], str)
        assert entry["description"].strip(), entry["name"]


def test_resolve_cluster_names_passes_description_through():
    terms = {0: pd.Series({"terminal": 1.0, "albergue": 0.9})}
    out = taxonomy.resolve_cluster_names(terms)
    assert out[0]["name"] == "Urgent humanitarian needs"
    assert out[0]["description"]           # non-empty
    assert out[0]["provisional"] is False


def test_resolve_cluster_names_auto_named_gets_empty_description():
    """An auto-named cluster has no curated prose, and says so with ''."""
    terms = {0: pd.Series({"zzzznomatch": 1.0})}
    with pytest.warns(UserWarning, match="provisional"):
        out = taxonomy.resolve_cluster_names(terms)
    assert out[0]["provisional"] is True
    assert out[0]["description"] == ""


def test_resolve_names_takes_a_registry():
    reg = [{"marker": "arriendo", "name": "Housing"}]
    terms = {0: pd.Series({"arriendo": 0.9, "subsidio": 0.4}),
             1: pd.Series({"pasaporte": 0.8, "cita": 0.3})}
    with pytest.warns(UserWarning, match="provisional"):
        out = taxonomy.resolve_names(terms, reg)
    assert out[0]["name"] == "Housing"
    assert out[0]["provisional"] is False
    assert out[1]["provisional"] is True
    assert out[1]["marker"] == "pasaporte"


def test_resolve_names_claims_each_entry_once():
    reg = [{"marker": "visa", "name": "Visas"}]
    terms = {0: pd.Series({"visa": 0.9}), 1: pd.Series({"visa": 0.8})}
    with pytest.warns(UserWarning, match="provisional"):
        out = taxonomy.resolve_names(terms, reg)
    assert out[0]["name"] == "Visas"
    assert out[1]["provisional"] is True


def test_resolve_names_warns_naming_the_kind():
    terms = {0: pd.Series({"xyz": 0.5})}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        taxonomy.resolve_names(terms, [], kind="subcluster")
    assert any("SUBCLUSTER_NAMES" in str(x.message) for x in w)


def test_resolve_cluster_names_still_works_unchanged():
    terms = {0: pd.Series({"nacionalidad": 0.9, "registro": 0.2})}
    out = taxonomy.resolve_cluster_names(terms)
    assert out[0]["name"] == "Nationality and family papers"
    assert out[0]["provisional"] is False


def test_subcluster_names_registry_exists_and_is_well_formed():
    assert isinstance(taxonomy.SUBCLUSTER_NAMES, list)
    for entry in taxonomy.SUBCLUSTER_NAMES:
        assert set(entry) >= {"marker", "name"}


def test_resolve_names_passes_description_through_both_branches():
    """description must survive resolve_names, not just resolve_cluster_names."""
    reg = [{"marker": "arriendo", "name": "Housing", "description": "Rent help."}]
    terms = {0: pd.Series({"arriendo": 0.9}), 1: pd.Series({"pasaporte": 0.8})}
    with pytest.warns(UserWarning, match="provisional"):
        out = taxonomy.resolve_names(terms, reg)
    assert out[0]["description"] == "Rent help."
    assert out[1]["description"] == ""
