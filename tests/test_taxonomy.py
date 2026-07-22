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
