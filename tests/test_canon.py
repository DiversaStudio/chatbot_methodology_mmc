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
    # An unlisted but plausible country still passes through untouched.
    assert canon.nationality_canon("Uruguay") == "Uruguay"
    assert canon.nationality_canon(None) == "Desconocida"


def test_nationality_canon_folds_accent_and_language_variants():
    """The 2026-08-03 export carried these as separate rows. They are one country."""
    assert canon.nationality_canon("Haiti") == "Haiti"
    assert canon.nationality_canon("Haití") == "Haiti"
    assert canon.nationality_canon("Panamá") == "Panama"
    assert canon.nationality_canon("Noruega") == "Norway"
    assert canon.nationality_canon("República Dominicana") == "Dominican Republic"
    assert canon.nationality_canon("Brasil") == "Brazil"
    # Ordering sentinel: the map lookup must run before the plausibility guard.
    # "el salvador" is in NATIONALITY_CANON; a reordering regression would only
    # surface in production since the guard no longer rejects it either way.
    assert canon.nationality_canon("El Salvador") == "El Salvador"


def test_nationality_canon_rejects_non_country_input():
    """Real values from the 2026-08-03 export that must not reach a slicer."""
    for junk in ("1", "3", "4", "  ", "-", "Soy Colombovenezolana"):
        assert canon.nationality_canon(junk) == "Desconocida", junk


def test_nationality_canon_folds_multiword_free_text_to_one_country():
    """2026-08-20 export carried 'México mexicana' as its own literal bucket
    -- the folded two-word key isn't in NATIONALITY_CANON's single-word
    'mexico'/'mexicana' entries, so it fell through untranslated."""
    assert canon.nationality_canon("México mexicana") == "Mexico"
    assert canon.nationality_canon("Mexico Mexicana") == "Mexico"


def test_nationality_canon_masculine_demonym_forms():
    """Every nationality had both grammatical-gender demonyms mapped (e.g.
    venezolana/venezolano) except Mexico, Panama, Chile, Brazil, and Haiti,
    which only had the feminine form -- the masculine fell through untranslated
    and sat as its own bucket (e.g. "Mexicano") next to "Mexico"."""
    assert canon.nationality_canon("mexicano") == "Mexico"
    assert canon.nationality_canon("panameno") == "Panama"
    assert canon.nationality_canon("chileno") == "Chile"
    assert canon.nationality_canon("brasileno") == "Brazil"
    assert canon.nationality_canon("haitiano") == "Haiti"


def test_nationality_canon_bare_otro_folds_to_unknown():
    """2026-08-20 export carried 6 rows of literal 'Otro' (the free-text
    option picked with nothing typed into it -- clean_nationality only
    substitutes *_other when there IS elaboration). Without an explicit
    mapping this passes is_plausible_nationality and title-cases to its own
    'Otro' bucket, duplicating Desconocida instead of joining it -- see the
    'Otra' (city) / 'Desconocida' (nationality) catch-all convention."""
    assert canon.nationality_canon("Otro") == "Desconocida"
    assert canon.nationality_canon("Otra") == "Desconocida"


def test_is_plausible_nationality():
    assert canon.is_plausible_nationality("uruguay")
    assert canon.is_plausible_nationality("costa rica")
    assert canon.is_plausible_nationality("republica dominicana")
    assert not canon.is_plausible_nationality("1")
    assert not canon.is_plausible_nationality("")
    assert not canon.is_plausible_nationality("soy colombovenezolana")


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


def test_discovery_channel_display_defaults_unknown_to_other():
    """Free text typed into the 'Otro' option's own field (instead of the
    literal 'Otro'), and any other value outside the closed dropdown set,
    still means 'other' -- it must not draw its own bar."""
    assert canon.discovery_channel_display(
        "Por un afiche que esta pegado a la pared") == "Other"
    assert canon.discovery_channel_display("Por int�grate") == "Other"
    assert canon.discovery_channel_display("Recomendación de otro migrante") == \
        "Another migrant"
    assert canon.discovery_channel_display("Social media") == "Social media"
    assert canon.discovery_channel_display(None) is None
    import pandas as pd
    assert pd.isna(canon.discovery_channel_display(float("nan")))


def test_language_display_covers_es_en_fr_and_defaults_to_not_specified():
    """fr has zero usage in the current export (the selector is v2-only and
    no v2 user has picked it yet), but the option exists, so it must display
    correctly the moment it appears rather than needing a code change."""
    assert canon.language_display("es") == "Spanish"
    assert canon.language_display("en") == "English"
    assert canon.language_display("fr") == "French"
    assert canon.language_display("ES") == "Spanish"  # case-insensitive
    assert canon.language_display("pt") == "Not specified"  # unrecognized code
    assert canon.language_display(None) == "Not specified"
    import pandas as pd
    assert canon.language_display(float("nan")) == "Not specified"


def test_age_range_bucket_matches_mmc_brackets_at_every_boundary():
    """0-17, 18-24, 25-34, 35-44, 45-54, 55+ -- check both edges of every
    bracket so an off-by-one in the bin list is caught, not just the middle
    of each band."""
    cases = {
        0: "0-17", 17: "0-17",
        18: "18-24", 24: "18-24",
        25: "25-34", 34: "25-34",
        35: "35-44", 44: "35-44",
        45: "45-54", 54: "45-54",
        55: "55+", 87: "55+",
    }
    for age, expected in cases.items():
        assert canon.age_range_bucket(age) == expected, age
    assert canon.age_range_bucket(None) == "Not specified"
    assert canon.age_range_bucket(float("nan")) == "Not specified"


def test_age_range_order_of_sorts_youngest_to_oldest_then_not_specified():
    labels = ["0-17", "18-24", "25-34", "35-44", "45-54", "55+", "Not specified"]
    orders = [canon.age_range_order_of(l) for l in labels]
    assert orders == sorted(orders)
