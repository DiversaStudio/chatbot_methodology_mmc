from sami import taxonomy


def test_official_categories_are_seven():
    assert len(taxonomy.OFFICIAL_CATEGORIES) == 7
    assert "legal_documentation" in taxonomy.OFFICIAL_CATEGORIES


def test_normalize_category_variants():
    for raw in ["legal documentation", "#legal_documentation",
                "#legaldocumentation", "#legal documentation", "LEGAL DOCUMENTATION"]:
        assert taxonomy.normalize_category(raw) == "legal_documentation"
    assert taxonomy.normalize_category("#humanitarian_assistance") == "humanitarian_assistance"
    assert taxonomy.normalize_category("Protection") == "protection"


def test_normalize_category_prompt_leftover_is_unclassified():
    junk = ("Use exactly one of these hashtags in the column for each entry, "
            "based on the main topic of the migrants question:  #humanitarian_assistance")
    assert taxonomy.normalize_category(junk) == "unclassified"


def test_normalize_category_multilabel_is_unclassified():
    assert taxonomy.normalize_category("legal documentation, employment") == "unclassified"


def test_normalize_category_blank_is_unclassified():
    assert taxonomy.normalize_category("") == "unclassified"
    assert taxonomy.normalize_category(None) == "unclassified"


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
