from sami import canon


def test_fold_strips_accents_and_case():
    assert canon.fold("Medellín") == "medellin"
    assert canon.fold("  BOGOTÁ ") == "bogota"


def test_city_canon_known_variants():
    assert canon.city_canon("medellin antioquia") == "Medellín"
    assert canon.city_canon("Bogota DC") == "Bogotá"
    assert canon.city_canon("cucuta") == "Cúcuta"


def test_city_canon_non_city_returns_otra():
    assert canon.city_canon("Colombia") == "Otra"
    assert canon.city_canon("Antioquia") == "Otra"
    assert canon.city_canon("12345") == "Otra"
    assert canon.city_canon(None) == "Otra"


def test_is_non_city_reports_reason():
    excluded, reason = canon.is_non_city("Colombia")
    assert excluded and "country/region" in reason
    excluded, reason = canon.is_non_city("Medellín")
    assert not excluded


def test_clean_city_uses_other_when_otra():
    assert canon.clean_city("Otra", "Envigado") == "Envigado"
    assert canon.clean_city("Medellín", None) == "Medellín"


def test_city_canon_does_not_over_match_prefixes():
    # distinct municipalities that happen to share a prefix with a canon key
    assert canon.city_canon("Belen de Umbria") == "Otra"
    assert canon.city_canon("Belen, Narino") == "Otra"
    assert canon.city_canon("Calima") == "Otra"
    # intended matches must still hold
    assert canon.city_canon("belen") == "Medellín"
    assert canon.city_canon("cali") == "Cali"
    assert canon.city_canon("medellin antioquia") == "Medellín"
