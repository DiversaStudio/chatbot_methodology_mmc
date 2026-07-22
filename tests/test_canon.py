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


# --- nationality --------------------------------------------------------------
def test_nationality_canon_known_and_fallback():
    assert canon.nationality_canon("Venezuela") == "Venezuela"
    assert canon.nationality_canon("venezolana") == "Venezuela"
    assert canon.nationality_canon("United States") == "United States"
    assert canon.nationality_canon("Estados Unidos") == "United States"
    # unknown value is title-cased through, never dropped silently
    assert canon.nationality_canon("Brasil") == "Brasil"
    assert canon.nationality_canon(None) == "Desconocida"


def test_clean_nationality_uses_other_fallback():
    assert canon.clean_nationality("Otra", "Brasil") == "Brasil"
    assert canon.clean_nationality("Venezuela", None) == "Venezuela"


# --- department of city -------------------------------------------------------
def test_department_of_priority_cities():
    assert canon.department_of("Medellín") == "Antioquia"
    assert canon.department_of("Cúcuta") == "Norte de Santander"
    assert canon.department_of("Bogotá") == "Bogotá"          # fold-matches NE "Bogota"
    assert canon.department_of("Riohacha") == canon.department_of("Maicao") == "La Guajira"
    assert canon.department_of("Otra") is None
    assert canon.department_of("nowhere") is None


# --- away duration (ordered) --------------------------------------------------
def test_away_duration_canon_and_order():
    assert canon.away_duration_canon("Hace más de 5 años") == "Hace más de 5 años"
    # accent/case-insensitive via fold
    assert canon.away_duration_canon("HACE MAS DE 5 ANOS") == "Hace más de 5 años"
    assert canon.away_duration_canon("garbage") is None
    order = [canon.away_duration_order(v) for v in canon.AWAY_DURATION_ORDER]
    assert order == [0, 1, 2, 3, 4]
    assert canon.away_duration_order("garbage") is None


# --- gender -------------------------------------------------------------------
def test_gender_display_and_consolidation():
    assert canon.GENDER_DISPLAY["Mujer"] == "Woman"
    assert canon.clean_gender("Otro", "No binario") == "No binario"
    assert canon.clean_gender("Mujer", None) == "Mujer"
