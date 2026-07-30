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
    assert canon.gender_display("lgtbQ+") == "LGBTQ+"
    assert canon.gender_display("Gay") == "LGBTQ+"
    # trans and non-binary self-descriptions join the same umbrella: the cells
    # were 4 and 2 people, small enough to be re-identifying on their own
    assert canon.gender_display("transgenero") == "LGBTQ+"
    assert canon.gender_display("Soy una mujer trans") == "LGBTQ+"
    assert canon.gender_display("no binario") == "LGBTQ+"
    # merged 2026-07-30: "Other" was 3 people, below the cell size the review had
    # already judged too small to name on its own
    joint = canon.GENDER_OTHER_OR_UNSTATED
    assert canon.gender_display("Prefiero no responder") == joint
    assert canon.gender_display("Otro") == joint
    # empty stays empty; unknown free text never leaks to a chart
    assert canon.gender_display("") == ""
    assert canon.gender_display(None) == ""
    assert canon.gender_display("cualquier otra cosa") == joint


def test_gender_joint_bucket_does_not_claim_a_refusal():
    """The merged label must not report a stated answer as a declined one."""
    label = canon.GENDER_OTHER_OR_UNSTATED
    assert label == "Other or prefer not to say"
    assert label != "Prefer not to say"          # would misreport 3 stated answers
    assert label != "Other"                      # would misreport 19 refusals


def test_gender_display_legend_is_four_labels():
    """The dashboard legend is closed at four labels plus the empty non-answer."""
    measured = ["Mujer", "Hombre", "transgenero", "no binario", "lgtbQ+", "Gay",
                "lesbiana", "bisexual", "Prefiero no responder", "Otro", "bhdhb", ""]
    assert {canon.gender_display(v) for v in measured} == {
        "Woman", "Man", "LGBTQ+", canon.GENDER_OTHER_OR_UNSTATED, ""}


def test_minors_prefer_not_to_say_is_untouched_by_the_gender_merge():
    """`minors` is a different question with its own vocabulary -- merging the
    gender buckets must not reach into it."""
    assert canon.yes_no_display("Prefiero no responder") == "Prefer not to say"


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


def test_v2_discovery_options_are_complete_and_consistent():
    """The v2 survey reworded three of five discovery options; an unmapped option
    passes through untranslated and splits one answer across two slices in a
    pooled chart. This test ensures the complete v2 dropdown set is mapped and
    that each v2 option resolves to the same English string as its v1 counterpart.
    """
    d = canon.DISCOVERY_DISPLAY_EN
    # All v2 dropdown options are keys in DISCOVERY_DISPLAY_EN
    v2_options = ("Otro migrante", "Recomendación de ONG", "Redes sociales",
                  "Punto de atención", "Otro")
    for option in v2_options:
        assert option in d, f"v2 option {option!r} is not mapped"
    # The three reworded pairs map to identical English strings
    assert d["Otro migrante"] == d["Recomendación de otro migrante"]
    assert d["Recomendación de ONG"] == d["Recomendación de una ONG"]
    assert d["Punto de atención"] == d["Cartelera en un punto de atención"]
