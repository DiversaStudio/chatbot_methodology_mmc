"""Schema contract: header detection, required columns, MEAL question matching.

These are the checks that stand between a drifted export and silently wrong
numbers, so they are exercised on synthetic frames rather than only on the one
export that happens to be on disk.
"""
import pandas as pd
import pytest

from sami import schema

# The five real MEAL question headers, verbatim from the platform export.
REAL_MEAL_COLS = [
    "Name", "Timestamp",
    "Ha sido un gusto brindarte información. Para mejorar este servicio, "
    "¿nos podrías indicar qué tan útil fue la información entregada?",
    "¿Recomendarías este servicio a otras personas migrantes?",
    "¿Tienes alguna recomendación para mejorar este servicio?",
    "¿Cómo conociste este servicio?",
    "Por favor, escribe el medio por el cual conociste este servicio",
]


def _write_xlsx(tmp_path, rows, name="export.xlsx"):
    path = tmp_path / name
    pd.DataFrame(rows).to_excel(path, index=False, header=False)
    return path


# ---- header detection ---------------------------------------------------------
def test_detects_header_below_banner_rows(tmp_path):
    path = _write_xlsx(tmp_path, [
        ["MMC bot - responses", None, "This spreadsheet was created...", None],
        ["Grupo nuevo", None, "Try it free", None],
        ["Name", "Subitems", "Timestamp", "Consent"],
        ["whatsapp:+57000", None, "2026-01-01", "yes"],
    ])
    assert schema.detect_header_row(path) == 2


def test_detects_header_at_row_zero(tmp_path):
    """A re-export with the banner rows stripped must still load — this is the
    drift the old hardcoded DATA_HEADER_ROW = 2 would have silently mangled."""
    path = _write_xlsx(tmp_path, [
        ["Name", "Timestamp", "City"],
        ["whatsapp:+57000", "2026-01-01", "Bogotá"],
    ])
    assert schema.detect_header_row(path) == 0


def test_missing_header_error_shows_rows_seen(tmp_path):
    path = _write_xlsx(tmp_path, [["a", "b"], ["c", "d"]])
    with pytest.raises(schema.SchemaError) as exc:
        schema.detect_header_row(path)
    msg = str(exc.value)
    assert "Name" in msg and "Timestamp" in msg
    assert "row 0" in msg  # the fix shows what was actually found


# ---- required columns ---------------------------------------------------------
def test_require_columns_names_every_missing_one():
    frame = pd.DataFrame(columns=["Name", "Timestamp", "City"])
    with pytest.raises(schema.SchemaError) as exc:
        schema.require_columns(frame, schema.RESPONSES_REQUIRED, "f.xlsx", "responses")
    msg = str(exc.value)
    for missing in ("Age", "Messages", "Chat_summary"):
        assert missing in msg
    assert "fix:" in msg


def test_require_columns_passes_when_complete():
    frame = pd.DataFrame(columns=list(schema.RESPONSES_REQUIRED))
    schema.require_columns(frame, schema.RESPONSES_REQUIRED, "f.xlsx", "responses")


def test_unknown_columns_quiet_on_known_export():
    """A warning that fires on a good export is a warning nobody reads."""
    frame = pd.DataFrame(columns=list(schema.RESPONSES_REQUIRED)
                         + list(schema.RESPONSES_OPTIONAL)
                         + list(schema.RESPONSES_IGNORED))
    assert schema.report_unknown_columns(frame, "responses") == []


def test_unknown_columns_flags_new_field():
    frame = pd.DataFrame(columns=list(schema.RESPONSES_REQUIRED) + ["Brand_New_Field"])
    assert schema.report_unknown_columns(frame, "responses") == ["Brand_New_Field"]


# ---- MEAL question matching ---------------------------------------------------
def test_meal_maps_real_question_text_without_warnings():
    mapping, warnings = schema.meal_column_map(REAL_MEAL_COLS)
    assert warnings == []
    assert set(mapping.values()) == set(schema.MEAL_QUESTION_MARKERS)
    assert mapping[REAL_MEAL_COLS[3]] == "would_recommend"
    assert mapping[REAL_MEAL_COLS[5]] == "discovery_channel"
    assert mapping[REAL_MEAL_COLS[6]] == "discovery_other"


def test_meal_survives_an_inserted_column():
    """The regression this contract exists for: inserting one column used to
    shift every survey field one position left, silently mislabelling ratings."""
    shifted = REAL_MEAL_COLS[:2] + ["Channel"] + REAL_MEAL_COLS[2:]
    mapping, warnings = schema.meal_column_map(shifted)
    assert warnings == []
    # each canonical name still points at its own question, not its neighbour's
    assert mapping[REAL_MEAL_COLS[2]] == "usefulness_rating"
    assert mapping[REAL_MEAL_COLS[4]] == "recommendation_text"
    assert "Channel" not in mapping


def test_meal_reordered_columns_still_map():
    reordered = [REAL_MEAL_COLS[i] for i in (0, 1, 5, 6, 2, 4, 3)]
    mapping, warnings = schema.meal_column_map(reordered)
    assert warnings == []
    assert mapping[REAL_MEAL_COLS[2]] == "usefulness_rating"
    assert mapping[REAL_MEAL_COLS[3]] == "would_recommend"


def test_meal_positional_fallback_warns_loudly():
    """When question text does not match, falling back is allowed — silently is not."""
    unmatchable = ["Name", "Timestamp", "Q1", "Q2", "Q3", "Q4", "Q5"]
    mapping, warnings = schema.meal_column_map(unmatchable)
    assert len(warnings) == 5
    assert all("VERIFY" in w for w in warnings)
    assert mapping["Q1"] == "usefulness_rating"
    assert mapping["Q5"] == "discovery_other"


def test_meal_missing_column_reported_not_guessed():
    mapping, warnings = schema.meal_column_map(["Name", "Timestamp", "Q1"])
    assert "discovery_other" not in mapping.values()
    assert any("not found" in w and "discovery_other" in w for w in warnings)


def test_meal_accent_and_case_insensitive():
    stripped = list(REAL_MEAL_COLS)
    stripped[2] = "PARA MEJORAR, ¿QUE TAN UTIL FUE LA INFORMACION?"
    mapping, warnings = schema.meal_column_map(stripped)
    assert warnings == []
    assert mapping[stripped[2]] == "usefulness_rating"
