import re
import pytest

from sami import taxonomy

HEADER = "entity,kind,pattern,notes\n"


def _write(tmp_path, body, encoding="utf-8"):
    p = tmp_path / "entities.csv"
    p.write_text(HEADER + body, encoding=encoding)
    return p


def test_loads_rows_with_accented_display_names(tmp_path):
    p = _write(tmp_path, "Cédula,procedure,\\bcedula\\b,keeps its accent\n")
    rows = taxonomy.load_entity_registry(p)
    assert rows == [{"entity": "Cédula", "kind": "procedure",
                     "pattern": r"\bcedula\b", "notes": "keeps its accent"}]


def test_tolerates_utf8_bom(tmp_path):
    p = _write(tmp_path, "SENA,institution,\\bsena\\b,\n", encoding="utf-8-sig")
    assert taxonomy.load_entity_registry(p)[0]["entity"] == "SENA"


def test_rejects_ansi_encoded_file_with_actionable_message(tmp_path):
    p = tmp_path / "entities.csv"
    p.write_bytes((HEADER + "Cédula,procedure,\\bcedula\\b,\n").encode("cp1252"))
    with pytest.raises(taxonomy.EntityRegistryError, match="CSV UTF-8"):
        taxonomy.load_entity_registry(p)


def test_rejects_unknown_kind(tmp_path):
    p = _write(tmp_path, "Foo,organisation,\\bfoo\\b,\n")
    with pytest.raises(taxonomy.EntityRegistryError, match="organisation"):
        taxonomy.load_entity_registry(p)


def test_rejects_duplicate_entity_pattern_pair(tmp_path):
    p = _write(tmp_path, "Foo,procedure,\\bfoo\\b,\nFoo,procedure,\\bfoo\\b,\n")
    with pytest.raises(taxonomy.EntityRegistryError, match="duplicate"):
        taxonomy.load_entity_registry(p)


def test_rejects_one_entity_carrying_two_kinds(tmp_path):
    p = _write(tmp_path, "Foo,procedure,\\bfoo\\b,\nFoo,institution,\\bbar\\b,\n")
    with pytest.raises(taxonomy.EntityRegistryError, match="two kinds"):
        taxonomy.load_entity_registry(p)


def test_rejects_uncompilable_regex(tmp_path):
    p = _write(tmp_path, "Foo,procedure,\\bfoo(\\b,\n")
    with pytest.raises(taxonomy.EntityRegistryError, match="not a valid regex"):
        taxonomy.load_entity_registry(p)


def test_rejects_empty_entity_name(tmp_path):
    p = _write(tmp_path, ",procedure,\\bfoo\\b,\n")
    with pytest.raises(taxonomy.EntityRegistryError, match="empty entity"):
        taxonomy.load_entity_registry(p)


def test_rejects_counted_row_with_no_pattern(tmp_path):
    p = _write(tmp_path, "Foo,procedure,,\n")
    with pytest.raises(taxonomy.EntityRegistryError, match="needs a pattern"):
        taxonomy.load_entity_registry(p)


def test_ignore_rows_need_no_pattern_and_are_not_counted(tmp_path):
    p = _write(tmp_path, "Visa,procedure,\\bvisa\\b,\ntramite,ignore,,generic word\n")
    taxonomy.reload_entities(p)
    try:
        assert set(taxonomy.ENTITY_PATTERNS) == {"Visa"}
        assert taxonomy.ENTITY_KIND == {"Visa": "procedure"}
        assert "tramite" in taxonomy.IGNORED_TERMS
    finally:
        taxonomy.reload_entities()


def test_reports_every_problem_at_once(tmp_path):
    p = _write(tmp_path, "Foo,organisation,\\bfoo\\b,\n,procedure,\\bbar\\b,\n")
    with pytest.raises(taxonomy.EntityRegistryError) as exc:
        taxonomy.load_entity_registry(p)
    assert "organisation" in str(exc.value) and "empty entity" in str(exc.value)


def test_reload_restores_the_real_registry(tmp_path):
    p = _write(tmp_path, "Visa,procedure,\\bvisa\\b,\n")
    taxonomy.reload_entities(p)
    taxonomy.reload_entities()
    assert len(taxonomy.ENTITY_PATTERNS) > 1
    assert set(taxonomy.ENTITY_KIND.values()) <= set(taxonomy.COUNTED_KINDS)


def test_default_registry_ships_with_the_code(tmp_path, monkeypatch):
    """A clean clone must run: the tracked default is always present."""
    from sami import config
    assert config.ENTITIES_DEFAULT.exists()
    monkeypatch.setattr(config, "ENTITIES_OVERRIDE", tmp_path / "absent.csv")
    assert config.entities_path() == config.ENTITIES_DEFAULT


def test_local_override_wins_when_present(tmp_path, monkeypatch):
    from sami import config
    override = _write(tmp_path, "Visa,procedure,\\bvisa\\b,\n")
    monkeypatch.setattr(config, "ENTITIES_OVERRIDE", override)
    assert config.entities_path() == override
    taxonomy.reload_entities()
    try:
        assert set(taxonomy.ENTITY_PATTERNS) == {"Visa"}
    finally:
        monkeypatch.undo()
        taxonomy.reload_entities()


def test_registry_file_is_the_one_config_points_at():
    from sami import config
    assert config.entities_path().exists()
    assert taxonomy.load_entity_registry() == taxonomy.ENTITY_REGISTRY


def test_every_registry_pattern_is_lowercase_and_compiles():
    """Patterns match accent-folded lowercase text; an uppercase one is dead."""
    import re
    for row in taxonomy.ENTITY_REGISTRY:
        if not row["pattern"]:
            continue
        assert row["pattern"] == row["pattern"].lower(), row
        re.compile(row["pattern"])


def test_both_counted_kinds_are_populated():
    kinds = set(taxonomy.ENTITY_KIND.values())
    assert kinds == set(taxonomy.COUNTED_KINDS)


NEW_ENTITIES = {
    "Salvoconducto", "Regularización", "Emprendimiento", "Ayuda económica",
    "Nacionalidad/Naturalización", "Registro civil/Apostilla",
}

# One real phrasing per addition, taken from the corpus mining of 2026-08-06.
MUST_MATCH = [
    ("Salvoconducto", "necesito renovar mi salvoconducto"),
    ("Salvoconducto", "como saco el salvo conducto"),
    ("Regularización", "quiero regularizar mi situacion"),
    ("Regularización", "estoy en situacion irregular"),
    ("Emprendimiento", "ayuda para mi emprendimiento"),
    ("Ayuda económica", "necesito una ayuda economica"),
    ("Nacionalidad/Naturalización", "como obtengo la nacionalidad colombiana"),
    ("Registro civil/Apostilla", "necesito el registro civil de mi hija"),
    ("Registro civil/Apostilla", "donde apostillo el acta"),
    ("Cédula", "perdi mi cedula"),
    ("Salud/EPS", "necesito acceder a salud"),
    ("Trabajo/Empleo", "quiero trabajar aqui"),
]

MUST_NOT_MATCH = ["necesito hacer un tramite", "cuales son los requisitos",
                  "no entiendo el proceso", "tengo mis documentos",
                  "me faltan papeles", "somos migrantes"]


def test_new_entities_are_present_and_are_procedures():
    assert NEW_ENTITIES <= set(taxonomy.ENTITY_PATTERNS)
    for e in NEW_ENTITIES:
        assert taxonomy.ENTITY_KIND[e] == "procedure", e


def test_renamed_entities_replaced_the_old_names():
    assert "Cédula" in taxonomy.ENTITY_PATTERNS
    assert "Salud/EPS" in taxonomy.ENTITY_PATTERNS
    assert "Cédula de extranjería" not in taxonomy.ENTITY_PATTERNS
    assert "EPS" not in taxonomy.ENTITY_PATTERNS


def test_every_addition_matches_a_real_phrasing():
    for entity, text in MUST_MATCH:
        assert entity in taxonomy.extract_entities(text), f"{entity} missed {text!r}"


def test_rejected_terms_match_nothing():
    for text in MUST_NOT_MATCH:
        assert taxonomy.extract_entities(text) == set(), text


def test_rejected_terms_are_recorded_as_ignore_rows():
    """A rejection is durable data, so the candidates table stops resurfacing it."""
    for term in ("tramite", "requisitos", "proceso", "documentos", "papeles",
                 "permiso", "migrantes"):
        assert term in taxonomy.IGNORED_TERMS, term


import pandas as pd


def _msgs(rows):
    return pd.DataFrame(rows, columns=["message_id", "user_id", "message"])


def test_entity_coverage_counts_matched_over_total():
    n_hit, n_tot = taxonomy.entity_coverage(
        ["necesito mi ppt", "hola buenas tardes", None, "quiero un pasaporte"])
    assert (n_hit, n_tot) == (2, 3)   # None is not a message


def test_candidates_rank_by_distinct_users_not_message_count():
    rows = [(f"m{i}", "u1", "quiero informacion sobre albergue") for i in range(20)]
    rows += [(f"n{i}", f"u{i}", "necesito una beca") for i in range(20)]
    out = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    assert out.iloc[0]["term"] == "beca"           # 20 users beats 20 messages/1 user
    assert "albergue" not in set(out["term"])       # 1 user, under the floor


def test_candidates_exclude_cities_nationalities_and_ignored_terms():
    rows = [(f"m{i}", f"u{i}", "en medellin necesito un tramite venezuela")
            for i in range(20)]
    out = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    terms = set(out["term"])
    assert "medellin" not in terms      # dim_city's job
    assert "venezuela" not in terms     # nationality canon
    assert "tramite" not in terms       # an ignore row


def test_candidates_exclude_terms_the_dictionary_already_matches():
    # Two separate messages, not one: entity_candidates skips a message
    # entirely once extract_entities(text) finds anything in it (message-level
    # filter), so a term the dictionary already matches must not even share a
    # message with the term under test, or the whole message -- "beca"
    # included -- would be dropped before either term is counted.
    rows = [(f"m{i}", f"u{i}", "quiero saber del salvoconducto") for i in range(20)]
    rows += [(f"n{i}", f"u{i}", "quiero saber de una beca") for i in range(20)]
    out = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    assert "salvoconducto" not in set(out["term"])
    assert "beca" in set(out["term"])


def test_candidates_only_mine_messages_that_matched_nothing():
    rows = [(f"m{i}", f"u{i}", "necesito mi ppt y una beca") for i in range(20)]
    out = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    assert out.empty      # every message matched PPT, so nothing is mined


def test_candidates_carry_an_example_message_id():
    rows = [(f"m{i}", f"u{i}", "necesito una beca") for i in range(20)]
    out = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    row = out[out["term"] == "beca"].iloc[0]
    assert row["example_message_id"] == "m0"
    assert row["n_users"] == 20 and row["n_msgs"] == 20 and row["n_gram"] == 1


def test_candidate_bigrams_drop_when_either_token_is_a_stopterm():
    rows = [(f"m{i}", f"u{i}", "beca universitaria para el tramite") for i in range(20)]
    out = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    terms = set(out["term"])
    assert "beca universitaria" in terms
    assert not any("tramite" in t for t in terms)


def test_candidates_are_deterministic_under_row_shuffling():
    rows = [(f"m{i}", f"u{i}", "beca universitaria") for i in range(20)]
    rows += [(f"n{i}", f"u{i}", "auxilio funerario") for i in range(20)]
    a = taxonomy.entity_candidates(_msgs(rows), min_users=15)
    b = taxonomy.entity_candidates(_msgs(list(reversed(rows))), min_users=15)
    assert list(a["term"]) == list(b["term"])


def test_candidates_respect_top_n():
    out = taxonomy.entity_candidates(
        _msgs([(f"m{i}", f"u{i}", "beca auxilio subsidio2 albergue2 comedor2")
               for i in range(20)]), min_users=15, top_n=2)
    assert len(out) == 2


def test_coverage_thresholds_are_ordered():
    from sami import qa
    assert 0 < qa.ENTITY_COVERAGE_HARD_FLOOR < qa.ENTITY_COVERAGE_WARN < 1
    assert qa.ENTITY_COVERAGE_WARN == 0.35
    assert qa.ENTITY_COVERAGE_HARD_FLOOR == 0.20
