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


def test_gender_display_closed_set():
    # the measured free-text variants all fold into the dashboard legend
    assert canon.gender_display("Mujer") == "Woman"
    assert canon.gender_display("Hombre") == "Man"
    assert canon.gender_display("transgenero") == "Transgender"
    assert canon.gender_display("Soy una mujer trans") == "Transgender"
    assert canon.gender_display("lgtbQ+") == "LGBTQ+"
    assert canon.gender_display("Gay") == "LGBTQ+"
    assert canon.gender_display("Prefiero no responder") == "Prefer not to say"
    # empty stays empty; unknown free text never leaks to a chart
    assert canon.gender_display("") == ""
    assert canon.gender_display(None) == ""
    assert canon.gender_display("cualquier otra cosa") == "Other"


def test_survey_vocabularies_are_english():
    assert canon.yes_no_display("Si") == "Yes"
    assert canon.yes_no_display("Sí") == "Yes"
    assert canon.yes_no_display("No") == "No"
    assert canon.yes_no_display("Prefiero no responder") == "Prefer not to say"
    assert canon.yes_no_display(None) == ""
    # every ordered duration bucket has an EN label
    assert set(canon.AWAY_DURATION_DISPLAY_EN) == set(canon.AWAY_DURATION_ORDER)
    assert set(canon.CITY_DURATION_DISPLAY_EN) == set(canon.CITY_DURATION_ORDER)
    assert canon.OTHER_BUCKET_EN[canon.city_canon("Otra")] == "Other"


def test_city_duration_canon_and_order():
    from sami import canon
    labels = canon.CITY_DURATION_ORDER
    assert len(labels) >= 3
    # canon is idempotent on its own canonical labels
    for i, lab in enumerate(labels):
        assert canon.city_duration_canon(lab) == lab
        assert canon.city_duration_order(lab) == i
    # accent/case-insensitive
    assert canon.city_duration_canon(labels[0].upper()) == labels[0]
    # unknown -> None
    assert canon.city_duration_canon("xyz no such bucket") is None
    assert canon.city_duration_order("xyz no such bucket") is None


# --- Pasto and v2 discovery wordings ------------------------------------------
def test_pasto_canonicalizes():
    """The one v2 dropdown city absent from CITY_CANON — it never appeared in
    the v1 City_other free text the table was built from."""
    assert canon.city_canon(canon.clean_city("Pasto", None)) == "Pasto"


def test_pasto_has_map_coordinates():
    """Without coordinates a city silently vanishes from dim_city and the maps."""
    assert "Pasto" in canon.CITY_COORDS


def test_all_v2_dropdown_cities_are_mappable():
    """Every option the v2 survey offers must reach the dashboard map."""
    for city in ("Bogotá", "Cali", "Cúcuta", "Ipiales", "Medellín",
                 "Necoclí", "Pasto"):
        assert canon.city_canon(canon.clean_city(city, None)) == city
        assert city in canon.CITY_COORDS, f"{city} has no coordinates"


def test_both_discovery_wordings_share_a_label():
    """v2 reworded the options. Unmapped values pass through untranslated, so
    'Otro migrante' would sit beside 'Referral from another migrant' as a
    separate slice of the same thing."""
    d = canon.DISCOVERY_DISPLAY_EN
    assert d["Otro migrante"] == d["Recomendación de otro migrante"]
    assert d["Recomendación de ONG"] == d["Recomendación de una ONG"]
