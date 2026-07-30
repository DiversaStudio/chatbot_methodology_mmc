# SAMI v2 Export Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the SAMI pipeline from the retired chatbot platform's exports to the v2 platform's exports, fixing three silent-corruption defects and encoding cohort comparability rules in code so MMC can re-run the pipeline on future exports safely.

**Architecture:** Extend the existing declarative schema contract (`schema.py`) with source→canonical column maps applied immediately after `read_excel`, so every downstream module keeps today's column names untouched. Add one new module, `cohort.py`, following the same shape as its neighbours. All other changes are additive edits to existing modules.

**Tech Stack:** Python 3.12, pandas, openpyxl, pytest, `uv` for environment management.

## Global Constraints

- **Preserve existing architecture. No restructuring.** Extend `schema.py`; `canon.py` keeps sole ownership of value domains; `export.py` keeps its pure `build_*(frames) -> DataFrame` functions with `write_all` as the only disk-touching function; `facade.load_sami` stays the single entry point returning `SamiData`; `run_pipeline.py` keeps the `with pr.stage(...)` progress pattern.
- **Python environment:** always `uv`. Never `pip`, `venv`, or `pyenv` standalone. Run tests as `.venv/Scripts/python.exe -m pytest`.
- **Set `tool.uv.package = false` before any `uv sync`** or it deletes `src/`.
- **Git commits must NOT include a `Co-Authored-By` trailer.**
- **No PII in the repo.** `data_&_docs/` is gitignored. Test fixtures use fabricated phone numbers only. Never commit a real export.
- **Error messages carry the fix.** Every raised `SchemaError` / `CohortError` names the file, the offending column, and what to edit — matching the existing `schema._fmt` contract.
- **Shell:** PowerShell is primary. In the Bash tool use POSIX heredocs, not PowerShell `@'...'@`.
- **Canonical internal column names stay as they are today** (`Name`, `Timestamp`, `Messages`, `Chat_summary`, `City`, `Age`, …). The v2 names are mapped *onto* these, not propagated.
- **Spec:** `docs/superpowers/specs/2026-07-28-sami-v2-export-migration-design.md`
- **Out of scope:** NB3, all NLP re-validation, the `.pbix` rebuild, git-history PII purge.

## File Structure

**Created:**
- `src/sami/cohort.py` — instrument version derivation + comparability policy. One responsibility: deciding whether a variable may be pooled across questionnaire versions.
- `tests/fixtures/make_fixtures.py` — generator script for the synthetic exports (committed so fixtures are reproducible, not magic binaries).
- `tests/fixtures/users_v2.xlsx`, `tests/fixtures/survey_v2.xlsx` — synthetic exports with fabricated phone numbers.
- `tests/test_cohort.py`, `tests/test_fixtures.py`

**Modified:**
- `src/sami/schema.py` — column maps, per-source header markers, MEAL duplicate-column resolution
- `src/sami/load.py` — phone key normalization, drop the `whatsapp:` filter
- `src/sami/qa.py` — sheet names, critical columns, prose tripwire
- `src/sami/canon.py` — new cities, gender noise, accent folding, Colombia, discovery wordings
- `src/sami/export.py` — content-hash `message_id`, new `dim_user` columns, `fact_meal` Q12a fields, two new agg tables, SPLIT dimension
- `src/sami/config.py` — file paths
- `src/sami/facade.py` — critical-check prefix fix
- `run_pipeline.py` — wire the two new tables
- `tests/test_*.py` — count assertions move to fixtures; real-data tests become invariants
- `notebooks/01_input_and_audience.ipynb`, `notebooks/02_demand_behaviour_experience.ipynb`
- `exports/_schema.md`, `README.md`

---

### Task 1: Synthetic test fixtures

Everything downstream is tested against these, so they come first.

**Files:**
- Create: `tests/fixtures/make_fixtures.py`
- Create: `tests/fixtures/users_v2.xlsx`, `tests/fixtures/survey_v2.xlsx`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: nothing
- Produces: `tests/fixtures/users_v2.xlsx` and `tests/fixtures/survey_v2.xlsx`. Both have 2 banner rows then a header at row index 2. Users fixture: 6 data rows — 4 with `Migrated From v1` set (v1 cohort), 2 without (v2 cohort); phone numbers `+571110000001`..`+571110000006` written as *numbers* so pandas parses them as floats, reproducing the real export's `.0` behaviour. Survey fixture: 4 data rows, with the v1 duplicate question columns present and empty and the v2 columns populated.

- [ ] **Step 1: Write the fixture generator**

Create `tests/fixtures/make_fixtures.py`:

```python
"""Generate synthetic v2-format exports for the test suite.

Fabricated phone numbers only — these files are committed, so they must never
carry real data. Re-run with:
    .venv/Scripts/python.exe tests/fixtures/make_fixtures.py
"""
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent

USERS_HEADER = [
    "Address", "Subitems", "Created At", "QA Messages", "Language", "consent",
    "nationality", "city", "time_in_city", "gender", "age", "children",
    "destination", "QA Summary", "Escalation Status", "Safety Alert",
    "Registration Status", "nationality (raw)", "Registration Started",
    "Registration Completed", "Attempts", "Drop-off Question", "Last Message At",
    "Is Returning User", "City_other", "Gender_other", "Away_duration",
    "Destination_Country", "Age Ranges", "Questions per user", "Migrated From v1",
]

# (address, created, messages, lang, consent, nat, city, time_in_city, gender,
#  age, children, dest, summary, escal, safety, regstatus, natraw, regstart,
#  regdone, attempts, dropoff, lastmsg, returning, city_other, gender_other,
#  away, destcountry, agerange, nquestions, migrated)
USERS_ROWS = [
    (571110000001, "2026-04-01T10:00:00.000Z", "¿Cómo saco el PPT?\nGracias",
     "es", "Sí", "Venezuela", "Medellín", "Más de 1 año", "Mujer", 30, "Si",
     "Colombia", "#legal documentation", None, None, "Completed", None,
     "2026-04-01T09:58:00.000Z", "2026-04-01T10:00:00.000Z", 1, None,
     "2026-04-01T10:05:00.000Z", None, None, None, "Entre 1 a 5 años",
     "Colombia", "18-35", 2, "v1:1000001"),
    (571110000002, "2026-04-02T11:00:00.000Z", "Necesito ayuda humanitaria",
     "es", "Sí", "Venezuela", "Cúcuta", "Menos de 1 mes", "Hombre", 45, "No",
     "Colombia", "humanitarian assistance", None, None, "Completed", None,
     "2026-04-02T10:58:00.000Z", "2026-04-02T11:00:00.000Z", 1, None,
     "2026-04-02T11:05:00.000Z", None, None, None, "Menos de 1 mes",
     "Colombia", "36-50", 1, "v1:1000002"),
    (571110000003, "2026-04-03T12:00:00.000Z", "Busco empleo en Bogotá",
     "es", "Sí", "Venezuela", "Otra", "Más de 1 año", "Mujer", 17, "Si",
     "Colombia", "#employment", None, None, "Completed", None,
     "2026-04-03T11:58:00.000Z", "2026-04-03T12:00:00.000Z", 2, None,
     "2026-04-03T12:05:00.000Z", None, "Bogotá", None, "Entre 1 a 5 años",
     "Colombia", "0-17", 1, "v1:1000003"),
    (571110000004, "2026-04-04T13:00:00.000Z", None,
     "es", "Sí", "Ecuador", "Medellín", "Más de 1 año", "Prefiero no responder",
     52, "No", "Otro", None, None, None, "Abandoned", None,
     "2026-04-04T12:58:00.000Z", None, 3, "city", None, None, None, None,
     "Hace más de 5 años", "Estados Unidos", "50 and above", None, "v1:1000004"),
    # --- v2-native cohort: no 'Migrated From v1' ---
    (571110000005, "2026-07-25T14:00:00.000Z", "¿Dónde hay albergue en Ipiales?",
     "es", "Sí", "Colombia", "Ipiales", "Menos de 1 mes", "Mujer", 28, "Sí",
     "Colombia", "[2026-07-25 14:05] El usuario preguntó sobre albergues en "
     "Ipiales, rutas hacia Medellín y asistencia humanitaria.",
     None, None, "Completed", None, "2026-07-25T13:58:00.000Z",
     "2026-07-25T14:00:00.000Z", 1, None, "2026-07-25T14:10:00.000Z", None,
     None, None, None, "Colombia", None, None, None),
    (571110000006, "2026-07-26T15:00:00.000Z", "I need medical help",
     "en", "Sí", "Venezuela", "Bogotá", "Entre 1 y 3 meses", "Trans", 34, "No",
     "Chile", "[2026-07-26 15:05] User asked about medical services in Bogotá.",
     "escalated", "flagged", "Completed", None, "2026-07-26T14:58:00.000Z",
     "2026-07-26T15:00:00.000Z", 1, None, "2026-07-26T15:10:00.000Z", "yes",
     None, None, None, "Chile", None, None, None),
]

# Column 2 and 3 are the EMPTY v1 duplicates; 6 and 8 carry the real v2 data.
SURVEY_HEADER = [
    "Respondent", "Recorded At",
    "Ha sido un gusto brindarte información. Para mejorar este servicio, "
    "¿nos podrías indicar qué tan útil fue la información entregada?",
    "¿Cómo conociste este servicio?\n1) Recomendación de otro migrante",
    "¿Recomendarías este servicio a otras personas migrantes?\n1) Sí",
    "¿Tienes alguna recomendación para mejorar este servicio?",
    "Ha sido un gusto brindarte información. Para mejorar este servicio, "
    "¿nos podrías indicar qué tan útil fue la información entregada?\n"
    "1) ⭐ – Nada útil\n5) ⭐⭐⭐⭐⭐ – Muy útil.1",
    "¿Por qué la información entregada no fue útil?",
    "¿Cómo conociste este servicio?\n1) Otro migrante\n2) Recomendación de ONG",
    "Gracias por tu retroalimentación.",
    "v1 Recomendarias", "v1 Medio Otro", "Migrated From v1",
]

SURVEY_ROWS = [
    # respondent, recorded, v1useful, v1disc, v1rec, v1text, useful, why,
    # discovery, thanks, v1recomendarias, v1medio, migrated
    (571110000001, "2026-04-01T10:30:00.000Z", None, None, None, None,
     "Muy útil", "no", "Redes sociales", None, "Sí", None, "v1:1000001"),
    (571110000002, "2026-04-02T11:30:00.000Z", None, None, None, None,
     "Nada útil", "No me recomendaste nada para Cúcuta", "Otro migrante",
     None, "No", None, "v1:1000002"),
    (571110000003, "2026-04-03T12:30:00.000Z", None, None, None, None,
     "Medianamente útil", "te confundiste de ciudad", "Otro", None,
     "Prefiero no responder", "un amigo", "v1:1000003"),
    (571110000005, "2026-07-25T14:30:00.000Z", None, None, None, None,
     "Útil", "Todo bien gracias", "Recomendación de ONG", None, None, None,
     None),
]


def _write(path: Path, title: str, header: list, rows: list) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.append([title])                       # banner row 0
    ws.append(["Group Title"])               # banner row 1
    ws.append(header)                        # header row 2
    for r in rows:
        ws.append(list(r))
    wb.save(path)


def main() -> None:
    _write(HERE / "users_v2.xlsx", "users", USERS_HEADER, USERS_ROWS)
    _write(HERE / "survey_v2.xlsx", "survey responses", SURVEY_HEADER, SURVEY_ROWS)
    print(f"wrote {HERE / 'users_v2.xlsx'}")
    print(f"wrote {HERE / 'survey_v2.xlsx'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the fixtures**

Run: `.venv/Scripts/python.exe tests/fixtures/make_fixtures.py`
Expected: two "wrote ..." lines, both files exist.

- [ ] **Step 3: Write the fixture-shape test**

Create `tests/test_fixtures.py`:

```python
"""The fixtures are test infrastructure — assert their shape so a broken
regeneration is caught here, not as a confusing failure in another module."""
from pathlib import Path
import pandas as pd

FIX = Path(__file__).resolve().parent / "fixtures"
USERS = FIX / "users_v2.xlsx"
SURVEY = FIX / "survey_v2.xlsx"


def test_fixtures_exist():
    assert USERS.exists() and SURVEY.exists()


def test_users_fixture_shape():
    df = pd.read_excel(USERS, header=2)
    assert len(df) == 6
    assert "Address" in df.columns and "Created At" in df.columns
    assert df["Migrated From v1"].notna().sum() == 4   # v1 cohort
    assert df["Migrated From v1"].isna().sum() == 2    # v2-native cohort


def test_users_fixture_reproduces_float_phone_parsing():
    """The real export stores Address as a number, so pandas yields 5.7e11
    and str() gives a trailing '.0'. The loader must survive that."""
    df = pd.read_excel(USERS, header=2)
    assert str(df["Address"].iloc[0]).endswith(".0")


def test_survey_fixture_has_empty_v1_duplicate_columns():
    """Defect 4: the v1 variants come first and are empty; the v2 variants
    carry the data. The column picker must prefer the populated one."""
    df = pd.read_excel(SURVEY, header=2)
    useful = [c for c in df.columns if "qué tan útil" in str(c)]
    assert len(useful) == 2, "fixture must carry BOTH usefulness columns"
    assert df[useful[0]].notna().sum() == 0, "first (v1) must be empty"
    assert df[useful[1]].notna().sum() == 4, "second (v2) must carry data"


def test_fixtures_contain_no_real_phone_numbers():
    for path in (USERS, SURVEY):
        joined = pd.read_excel(path, header=2).astype(str).to_string()
        assert "whatsapp:" not in joined
        # every fabricated number is in the 5711100000xx block
        assert "573" not in joined
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fixtures.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/ tests/test_fixtures.py
git commit -m "test(sami): synthetic v2-format export fixtures

Fabricated phone numbers only. Reproduces the two shapes that break the
loaders: Address parsed as a float, and the survey's empty v1 duplicate
question columns preceding the populated v2 ones."
```

---

### Task 2: Header detection + responses column map

**Files:**
- Modify: `src/sami/schema.py:28-51` (header detection), add column maps
- Test: `tests/test_schema.py`

**Interfaces:**
- Consumes: `tests/fixtures/users_v2.xlsx` from Task 1
- Produces:
  - `schema.HEADER_MARKERS: dict[str, tuple[tuple[str, ...], ...]]` keyed `"responses"` / `"meal"`
  - `schema.detect_header_row(path, source="responses", max_scan=8) -> int`
  - `schema.RESPONSES_COLUMN_MAP: dict[str, str]` (v2 name → canonical name)
  - `schema.MEAL_COLUMN_MAP: dict[str, str]`
  - `schema.normalize_columns(frame, source) -> pd.DataFrame`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_schema.py`:

```python
from pathlib import Path
import pandas as pd
import pytest
from sami import schema

FIX = Path(__file__).resolve().parent / "fixtures"


def test_detect_header_row_finds_v2_responses_header():
    assert schema.detect_header_row(FIX / "users_v2.xlsx", source="responses") == 2


def test_detect_header_row_finds_v2_meal_header():
    assert schema.detect_header_row(FIX / "survey_v2.xlsx", source="meal") == 2


def test_normalize_columns_maps_v2_names_to_canonical():
    df = pd.read_excel(FIX / "users_v2.xlsx", header=2)
    out = schema.normalize_columns(df, "responses")
    for canonical in ("Name", "Timestamp", "Messages", "Chat_summary",
                      "City", "Age", "Gender", "Nationality", "Minors",
                      "City_duration", "Destination"):
        assert canonical in out.columns, f"{canonical} missing after normalize"
    # v2 names must be gone — downstream code keys off the canonical names
    assert "Address" not in out.columns
    assert "QA Messages" not in out.columns


def test_normalize_columns_preserves_unmapped_v2_columns():
    """New v2-only fields must survive; export.py reads them by their own name."""
    df = pd.read_excel(FIX / "users_v2.xlsx", header=2)
    out = schema.normalize_columns(df, "responses")
    for passthrough in ("Language", "Registration Status", "Attempts",
                        "Migrated From v1", "Safety Alert"):
        assert passthrough in out.columns


def test_normalize_columns_is_idempotent():
    df = pd.read_excel(FIX / "users_v2.xlsx", header=2)
    once = schema.normalize_columns(df, "responses")
    twice = schema.normalize_columns(once, "responses")
    assert list(once.columns) == list(twice.columns)


def test_detect_header_row_error_names_the_file_and_rows(tmp_path):
    bad = tmp_path / "bad.xlsx"
    pd.DataFrame({"a": [1], "b": [2]}).to_excel(bad, index=False)
    with pytest.raises(schema.SchemaError) as e:
        schema.detect_header_row(bad, source="responses")
    assert str(bad) in str(e.value)
    assert "row 0" in str(e.value)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_schema.py -k "v2 or normalize or header_row" -v`
Expected: FAIL — `AttributeError: module 'sami.schema' has no attribute 'normalize_columns'`, and `detect_header_row() got an unexpected keyword argument 'source'`.

- [ ] **Step 3: Replace the header-detection block in `schema.py`**

Replace lines 26–51 (from the `# ---- header row ----` comment through the end of `detect_header_row`) with:

```python
# ---- header row ---------------------------------------------------------------
# The exports carry two banner rows above the real header, so the header is the
# 3rd row today. Detected rather than assumed: a re-export with one more or fewer
# banner rows silently shifts it.
#
# The v2 platform renamed the key columns, so each source accepts several marker
# sets. The legacy sets are kept because they cost nothing and let a v1-shaped
# file still be read (fixtures, archives) — the pipeline targets v2.
HEADER_MARKERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "responses": (("address", "created at"), ("name", "timestamp")),
    "meal": (("respondent", "recorded at"), ("name", "timestamp")),
}
HEADER_SCAN_ROWS = 8


def detect_header_row(path, source: str = "responses",
                      max_scan: int = HEADER_SCAN_ROWS) -> int:
    """0-indexed row holding the real column header.

    Finds the first row containing every marker of any accepted marker set for
    `source`. Raises SchemaError showing the rows actually seen when none match.
    """
    marker_sets = HEADER_MARKERS.get(source, HEADER_MARKERS["responses"])
    probe = pd.read_excel(path, header=None, nrows=max_scan)
    for i in range(len(probe)):
        cells = {fold(v) for v in probe.iloc[i] if not pd.isna(v)}
        if any(all(m in cells for m in markers) for markers in marker_sets):
            return i
    expected = " or ".join("+".join(m) for m in marker_sets)
    seen = "\n".join(
        f"    row {i}: {[str(v)[:24] for v in probe.iloc[i, :5] if not pd.isna(v)]}"
        for i in range(len(probe)))
    raise SchemaError(_fmt(
        f"No header row found in the first {max_scan} rows — expected a row "
        f"containing {expected}.",
        path,
        "Confirm this is a raw platform export (banner rows above the header, "
        "header not yet promoted). If the platform renamed its key columns "
        "again, add the new marker set to HEADER_MARKERS in "
        "src/sami/schema.py. Rows seen:\n" + seen))


# ---- source column maps -------------------------------------------------------
# The v2 platform renamed most fields. Rather than propagate the new names
# through every module, they are mapped back onto the canonical names the
# pipeline has always used. `normalize_columns` is the single place this happens.
RESPONSES_COLUMN_MAP: dict[str, str] = {
    "Address": "Name",
    "Created At": "Timestamp",
    "QA Messages": "Messages",
    "QA Summary": "Chat_summary",
    "consent": "Consent",
    "nationality": "Nationality",
    "nationality (raw)": "Nationality_other",
    "city": "City",
    "time_in_city": "City_duration",
    "gender": "Gender",
    "age": "Age",
    "children": "Minors",
    "destination": "Destination",
    "Survey Sent": "Survey sent",
}
MEAL_COLUMN_MAP: dict[str, str] = {
    "Respondent": "Name",
    "Recorded At": "Timestamp",
}
_COLUMN_MAPS = {"responses": RESPONSES_COLUMN_MAP, "meal": MEAL_COLUMN_MAP}


def normalize_columns(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    """Rename a raw v2 export's columns to the pipeline's canonical names.

    Unmapped columns pass through untouched — new v2 fields are read by their
    own names downstream. Idempotent: a frame already carrying canonical names
    is returned unchanged. A rename that would collide with an existing column
    is skipped, so a hybrid export cannot produce duplicate column labels.
    """
    mapping = _COLUMN_MAPS.get(source, {})
    present = set(frame.columns)
    rename = {src: dst for src, dst in mapping.items()
              if src in present and dst not in present}
    return frame.rename(columns=rename) if rename else frame
```

- [ ] **Step 4: Teach the contract about the new v2 fields**

`report_unknown_columns` warns for any column not listed in
`RESPONSES_REQUIRED | RESPONSES_OPTIONAL | RESPONSES_IGNORED`. The v2 export
adds fourteen, so without this the pipeline warns on every single run — and the
existing comment on `RESPONSES_IGNORED` is explicit that a warning firing every
run is a warning nobody reads.

Add to `RESPONSES_OPTIONAL` (used when present, absence degrades nothing):

```python
    "Language", "Registration Status", "Registration Started",
    "Registration Completed", "Attempts", "Is Returning User",
    "Safety Alert", "Escalation Status", "Migrated From v1",
```

Add to `RESPONSES_IGNORED` (present and deliberately unused):

```python
    "Drop-off Question", "Re-engagement Sent At", "transit", "origin_country",
```

Add this test to `tests/test_schema.py`:

```python
def test_v2_export_produces_no_unknown_column_warnings():
    """A warning that fires on every run is a warning nobody reads."""
    df = pd.read_excel(FIX / "users_v2.xlsx", header=2)
    df = schema.normalize_columns(df, "responses")
    assert schema.report_unknown_columns(df, "responses") == []
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_schema.py -v`
Expected: all pass. Existing `detect_header_row` tests still pass — `source` defaults to `"responses"` and the legacy marker set is still accepted.

- [ ] **Step 6: Commit**

```bash
git add src/sami/schema.py tests/test_schema.py
git commit -m "feat(sami): v2 header markers and source column maps

detect_header_row now takes a source and accepts several marker sets, so
the v2 files (Address/Created At, Respondent/Recorded At) are found.
normalize_columns maps v2 names back onto the canonical names the rest of
the pipeline already uses, keeping the change contained to schema.py."
```

---

### Task 3: MEAL duplicate-column resolution

This is defect 4 — the one that silently ships wrong numbers.

**Files:**
- Modify: `src/sami/schema.py:103-157` (`MEAL_QUESTION_MARKERS`, `meal_column_map`)
- Test: `tests/test_schema.py`

**Interfaces:**
- Consumes: `schema.normalize_columns` from Task 2
- Produces: `schema.meal_column_map(columns, path=None, frame=None) -> tuple[dict[str, str], list[str]]`. `MEAL_QUESTION_MARKERS` becomes `dict[str, tuple[str, ...]]` — each canonical field has one or more accepted fold-normalized fragments.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_schema.py`:

```python
def test_meal_column_map_prefers_the_populated_duplicate():
    """Defect 4: the survey export carries empty v1 duplicates BEFORE the
    populated v2 columns. First-match binding produced all-null ratings."""
    df = pd.read_excel(FIX / "survey_v2.xlsx", header=2)
    mapping, warnings = schema.meal_column_map(df.columns, frame=df)
    useful_src = [k for k, v in mapping.items() if v == "usefulness_rating"]
    assert len(useful_src) == 1
    assert df[useful_src[0]].notna().sum() == 4, "bound to the EMPTY duplicate"


def test_meal_column_map_binds_legacy_recommend_column():
    """Q13 was retired, so the v2-worded column is empty; the surviving v1
    data lives in 'v1 Recomendarias' and must still be reachable."""
    df = pd.read_excel(FIX / "survey_v2.xlsx", header=2)
    mapping, _ = schema.meal_column_map(df.columns, frame=df)
    src = [k for k, v in mapping.items() if v == "would_recommend"]
    assert src == ["v1 Recomendarias"]


def test_meal_column_map_binds_the_new_reason_question():
    df = pd.read_excel(FIX / "survey_v2.xlsx", header=2)
    mapping, _ = schema.meal_column_map(df.columns, frame=df)
    assert "no_usefulness_reason" in mapping.values()


def test_meal_column_map_has_no_positional_fallback():
    """The old position-based fallback mislabelled usefulness data as
    discovery_other. An unmatched field must be ABSENT plus a warning."""
    cols = ["Name", "Timestamp", "something", "unrelated"]
    mapping, warnings = schema.meal_column_map(cols)
    assert mapping == {}
    assert len(warnings) == len(schema.MEAL_QUESTION_MARKERS)
    assert all("not found" in w for w in warnings)


def test_meal_column_map_never_binds_two_fields_to_one_column():
    df = pd.read_excel(FIX / "survey_v2.xlsx", header=2)
    mapping, _ = schema.meal_column_map(df.columns, frame=df)
    assert len(mapping) == len(set(mapping.keys()))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_schema.py -k meal_column_map -v`
Expected: FAIL — `meal_column_map() got an unexpected keyword argument 'frame'`.

- [ ] **Step 3: Replace the MEAL section of `schema.py`**

Replace everything from `# ---- MEAL survey columns ----` to end of file with:

```python
# ---- MEAL survey columns ------------------------------------------------------
# The survey questions are long Spanish sentences, matched by a distinctive
# fold-normalized fragment rather than exact text (which carries punctuation and
# gets reworded) and rather than POSITION.
#
# Each field accepts several fragments because the v2 export carries BOTH
# question vintages. Two rules matter:
#
#   1. The v1 duplicates come FIRST and are EMPTY. Binding to the first match
#      produced all-null ratings with no error, and the old positional fallback
#      then relabelled the real usefulness data as discovery_other. So when a
#      marker matches several columns, the one CARRYING DATA wins.
#   2. There is no positional fallback. A field that cannot be matched is absent
#      from the mapping and raises a warning naming it. Absent-and-loud beats
#      present-and-wrong.
MEAL_QUESTION_MARKERS: dict[str, tuple[str, ...]] = {
    "usefulness_rating":    ("que tan util",),
    "would_recommend":      ("recomendarias este servicio", "v1 recomendarias"),
    "recommendation_text":  ("alguna recomendacion para mejorar",),
    "discovery_channel":    ("como conociste",),
    "discovery_other":      ("escribe el medio", "v1 medio otro"),
    "no_usefulness_reason": ("por que la informacion entregada no fue util",),
}


def meal_column_map(columns, path=None, frame=None) -> tuple[dict[str, str], list[str]]:
    """Map MEAL survey columns to their canonical names.

    Returns `({source_column: canonical_name}, warnings)`.

    When `frame` is supplied and a marker matches several columns, the populated
    one is chosen; ties break on the LAST occurrence, which is the newer vintage
    in every export seen. Without a frame the last match wins, which is still
    right for the v2 layout.
    """
    cols = [str(c) for c in columns]
    folded = [fold(c) for c in cols]
    mapping: dict[str, str] = {}
    warnings: list[str] = []
    taken: set[int] = set()

    def _populated(i: int) -> bool:
        if frame is None:
            return False
        try:
            return bool(frame[frame.columns[i]].notna().sum())
        except Exception:
            return False

    for canonical, markers in MEAL_QUESTION_MARKERS.items():
        hits = [i for i, f in enumerate(folded)
                if i not in taken and any(m in f for m in markers)]
        if not hits:
            warnings.append(
                f"MEAL column '{canonical}' not found by question text "
                f"(looked for {' | '.join(markers)}); it will be absent from "
                "fact_meal. If the platform reworded the question, add the new "
                "fragment to MEAL_QUESTION_MARKERS in src/sami/schema.py.")
            continue
        with_data = [i for i in hits if _populated(i)]
        chosen = (with_data or hits)[-1]
        taken.add(chosen)
        mapping[cols[chosen]] = canonical
        if len(hits) > 1 and not with_data and frame is not None:
            warnings.append(
                f"MEAL column '{canonical}' matched {len(hits)} columns and "
                f"none carry data; bound to {cols[chosen][:70]!r}. The question "
                "may have been retired.")
    return mapping, warnings
```

- [ ] **Step 4: Update the one caller in `load.py`**

In `load.load_meal`, change:

```python
    rename, notes = schema.meal_column_map(df.columns, path)
```

to:

```python
    rename, notes = schema.meal_column_map(df.columns, path, frame=df)
```

And extend the `keep` list on the following lines to carry the new field:

```python
    keep = ["user_id", "ts", "usefulness_rating", "would_recommend",
            "recommendation_text", "discovery_channel", "discovery_other",
            "no_usefulness_reason"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_schema.py tests/test_load_meal.py -v`
Expected: the new tests pass. Pre-existing `test_load_meal.py` tests that assert against the real old export may fail — that is expected and is fixed in Task 12. Note which fail; do not "fix" them here.

- [ ] **Step 6: Commit**

```bash
git add src/sami/schema.py src/sami/load.py tests/test_schema.py
git commit -m "fix(sami): bind MEAL columns to the populated duplicate

The v2 survey export carries both question vintages, v1 first and empty.
First-match binding silently produced all-null ratings, and the positional
fallback then relabelled real usefulness data as discovery_other. Markers
now accept several fragments, the populated column wins, and the
positional fallback is removed — an unmatched field is absent and loud."
```

---

### Task 4: Phone key normalization + drop the whatsapp filter

**Files:**
- Modify: `src/sami/load.py:16-17` (`digits`), `src/sami/load.py:72-99` (`_read_whatsapp`)
- Test: `tests/test_load_responses.py`

**Interfaces:**
- Consumes: `schema.normalize_columns`, `schema.detect_header_row(path, source)` from Task 2
- Produces: `load.digits(s) -> str` strips a trailing `.0`; `load._read_export(path, source)` replaces `_read_whatsapp` (no channel filter, normalizes columns). `load.pseudonymize` is unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_load_responses.py`:

```python
def test_digits_strips_float_suffix():
    """v2 Address parses as a float, so str() yields '573154047912.0'.
    Without stripping, every user_id changes and breaks joins to prior runs."""
    assert load.digits("573154047912.0") == "573154047912"
    assert load.digits(573154047912.0) == "573154047912"


def test_digits_unchanged_for_legacy_prefixed_names():
    assert load.digits("whatsapp:+573154047912") == "573154047912"


def test_user_id_identical_across_export_formats():
    """The migration must not re-pseudonymize: the same person in the v1 and
    v2 exports must hash to the same user_id."""
    salt = "test_salt"
    assert (load.pseudonymize("whatsapp:+573154047912", salt)
            == load.pseudonymize(573154047912.0, salt))


def test_load_responses_reads_the_v2_fixture():
    from pathlib import Path
    fix = Path(__file__).resolve().parent / "fixtures" / "users_v2.xlsx"
    df = load.load_responses(fix, salt="test_salt")
    assert len(df) == 6
    assert "user_id" in df.columns
    assert "Name" not in df.columns          # dropped after pseudonymization
    assert "Address" not in df.columns       # renamed by normalize_columns
    assert df["ts"].notna().all()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_load_responses.py -k "digits or identical or v2_fixture" -v`
Expected: FAIL — `digits` returns `5731540479120`, and `load_responses` raises `SchemaError` about missing WhatsApp rows.

- [ ] **Step 3: Update `digits` in `load.py`**

Replace lines 16–17:

```python
def digits(s) -> str:
    return re.sub(r"\D", "", str(s))
```

with:

```python
_FLOAT_TAIL = re.compile(r"\.0+$")


def digits(s) -> str:
    """Digits of an identifier, stable across export formats.

    The v1 export stored the id as text ("whatsapp:+573154047912"); the v2
    export stores it as a NUMBER, so pandas hands us 573154047912.0 and a naive
    digit strip yields a 13-char key. Dropping the float tail first keeps
    user_id byte-identical across the migration — every downstream join, and
    every comparison against a previous run, depends on that.
    """
    return re.sub(r"\D", "", _FLOAT_TAIL.sub("", str(s).strip()))
```

- [ ] **Step 4: Replace `_read_whatsapp` with `_read_export`**

Replace the whole `_read_whatsapp` function (lines 72–99) with:

```python
def _read_export(path, source: str = "responses") -> pd.DataFrame:
    """Read a platform export and normalize its columns to canonical names.

    The header row is detected, not assumed (schema.detect_header_row), and a
    missing file raises with the fix rather than a bare FileNotFoundError.

    There is no channel filter. The v1 export prefixed every id with
    "whatsapp:"; the v2 export stores a bare number, so filtering on that prefix
    dropped every row. The v2 platform is WhatsApp-only, and `Language` /
    `Registration Status` identify the channel if that ever changes.
    """
    path = Path(path)
    if not path.exists():
        raise schema.SchemaError(
            f"{source.capitalize()} export not found.\n"
            f"  file: {path}\n"
            "  fix:  The raw exports are not in the repo (data_&_docs/ is "
            "gitignored — they carry phone numbers). Obtain them out-of-band, "
            "put them in data_&_docs/, or pass an explicit path:\n"
            "        python run_pipeline.py --responses PATH --meal PATH\n"
            "        Run `python run_pipeline.py --check` to verify your setup.")
    df = pd.read_excel(path, header=schema.detect_header_row(path, source=source))
    df = schema.normalize_columns(df, source)
    schema.require_columns(df, schema.BASE_REQUIRED, path, source)
    df = df[df["Name"].notna()].copy()
    if df.empty:
        raise schema.SchemaError(
            f"{source.capitalize()} export has no rows with an identifier.\n"
            f"  file: {path}\n"
            "  fix:  Every row needs a value in the id column (v2: 'Address' "
            "for responses, 'Respondent' for the survey). Check you downloaded "
            "a complete export.")
    df.reset_index(drop=True, inplace=True)
    return df
```

- [ ] **Step 5: Update the two call sites**

In `load_responses`, change `df = _read_whatsapp(path, source="responses")` to `df = _read_export(path, source="responses")`.
In `load_meal`, change `df = _read_whatsapp(path, source="meal")` to `df = _read_export(path, source="meal")`.

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_load_responses.py tests/test_load_meal.py -v`
Expected: the new tests pass. Real-data count assertions still fail — Task 12 fixes those.

- [ ] **Step 7: Commit**

```bash
git add src/sami/load.py tests/test_load_responses.py
git commit -m "fix(sami): stable phone key and channel-filter removal

v2 stores the id as a number, so str() gave a trailing '.0' and every
user_id would have changed. digits() now strips it, keeping user_id
byte-identical across the migration. The whatsapp: prefix filter dropped
every v2 row and is replaced by a non-null id check."
```

---

### Task 5: Update `qa.py`'s copy of the contract

`qa.validate_schema` runs in `facade.load_sami` **before** the loaders, so this fails first.

**Files:**
- Modify: `src/sami/qa.py:14-18` (`_CRITICAL`, `_SHEET`), `src/sami/qa.py:51-71` (`validate_schema`)
- Test: `tests/test_qa.py`

**Interfaces:**
- Consumes: `schema.detect_header_row`, `schema.normalize_columns` from Task 2
- Produces: `qa.validate_schema(path, kind)` unchanged signature, returning the same `{"rows", "columns", "ts_parse_rate"}` dict.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_qa.py`:

```python
from pathlib import Path
from sami import qa

FIX = Path(__file__).resolve().parent / "fixtures"


def test_validate_schema_accepts_v2_users_export():
    out = qa.validate_schema(FIX / "users_v2.xlsx", kind="responses")
    assert out["rows"] == 6
    assert out["ts_parse_rate"] == 1.0


def test_validate_schema_accepts_v2_survey_export():
    out = qa.validate_schema(FIX / "survey_v2.xlsx", kind="meal")
    assert out["rows"] == 4
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_qa.py -k v2 -v`
Expected: FAIL — `ValueError: expected sheet 'mmc bot - responses', got ['users']`.

- [ ] **Step 3: Update the constants and reader in `qa.py`**

Replace lines 14–18:

```python
_CRITICAL = {
    "responses": ["Name", "Timestamp", "City", "Age", "Messages", "Chat_summary"],
    "meal": ["Name", "Timestamp"],
}
_SHEET = {"responses": "mmc bot - responses", "meal": "mmc-meal"}
```

with:

```python
# Checked AFTER schema.normalize_columns, so these are the canonical names.
_CRITICAL = {
    "responses": ["Name", "Timestamp", "City", "Age", "Messages", "Chat_summary"],
    "meal": ["Name", "Timestamp"],
}
# Accepted sheet names per source. v2 renamed them ('users', 'survey responses');
# the v1 names are kept so archived exports still validate.
_SHEET = {
    "responses": {"users", "mmc bot - responses"},
    "meal": {"survey responses", "mmc-meal"},
}
```

Then in `validate_schema`, replace the body's first block:

```python
def validate_schema(path, kind: str) -> dict:
    xl = pd.ExcelFile(path)
    if _SHEET[kind] not in xl.sheet_names:
        # tolerate single-sheet test fixtures; only enforce for real exports
        if len(xl.sheet_names) != 1:
            raise ValueError(f"expected sheet {_SHEET[kind]!r}, got {xl.sheet_names}")
    try:
        df = pd.read_excel(path, header=config.DATA_HEADER_ROW)
    except ValueError:
        df = pd.DataFrame()
```

with:

```python
def validate_schema(path, kind: str) -> dict:
    xl = pd.ExcelFile(path)
    names = {str(s).strip().lower() for s in xl.sheet_names}
    if not (names & _SHEET[kind]):
        # tolerate single-sheet test fixtures; only enforce for real exports
        if len(xl.sheet_names) != 1:
            raise ValueError(
                f"expected one of {sorted(_SHEET[kind])} for {kind}, "
                f"got {xl.sheet_names}")
    try:
        # header detected, not assumed — matches the loaders
        df = pd.read_excel(path, header=schema.detect_header_row(path, source=kind))
        df = schema.normalize_columns(df, kind)
    except (ValueError, schema.SchemaError):
        df = pd.DataFrame()
```

Add `schema` to the imports at the top of `qa.py`:

```python
from . import config, schema
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_qa.py -v`
Expected: the two new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/sami/qa.py tests/test_qa.py
git commit -m "fix(sami): v2 sheet names and header detection in qa.validate_schema

qa held a second copy of the export contract with the v1 sheet names, and
it runs inside facade.load_sami BEFORE the loaders — so it failed first.
It now shares schema.detect_header_row and schema.normalize_columns."
```

---

### Task 6: `cohort.py` — instrument version and comparability policy

**Files:**
- Create: `src/sami/cohort.py`
- Test: `tests/test_cohort.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `cohort.Policy` — str enum: `POOLABLE`, `SPLIT`, `V1_ONLY`, `V2_ONLY`
  - `cohort.CohortError(Exception)`
  - `cohort.V1_MARKER_COLUMN = "Migrated From v1"`
  - `cohort.POLICY: dict[str, Policy]`
  - `cohort.instrument_version(frame) -> pd.Series` of `"v1"`/`"v2"`
  - `cohort.policy_for(column) -> Policy` (raises `CohortError`)
  - `cohort.requires_split(column) -> bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cohort.py`:

```python
import pandas as pd
import pytest
from sami import cohort


def test_instrument_version_splits_on_migration_marker():
    df = pd.DataFrame({cohort.V1_MARKER_COLUMN: ["v1:100", None, "v1:102", None]})
    assert list(cohort.instrument_version(df)) == ["v1", "v2", "v1", "v2"]


def test_instrument_version_all_v2_when_marker_column_absent():
    """A future export with no migrated rows must not crash."""
    df = pd.DataFrame({"user_id": ["a", "b"]})
    assert list(cohort.instrument_version(df)) == ["v2", "v2"]


def test_nationality_requires_split():
    """v1 survey Q3 terminated Colombian respondents, so a pooled nationality
    total measures the old exit rule, not the user base."""
    assert cohort.policy_for("nationality_canon") is cohort.Policy.SPLIT
    assert cohort.requires_split("nationality_canon") is True


def test_retired_questions_are_v1_only():
    for col in ("away_duration_canon", "would_recommend", "recommendation_text"):
        assert cohort.policy_for(col) is cohort.Policy.V1_ONLY


def test_new_question_is_v2_only():
    assert cohort.policy_for("no_usefulness_reason") is cohort.Policy.V2_ONLY


def test_ordinary_variables_are_poolable():
    for col in ("city_canon", "age_num", "gender_clean", "usefulness_rating"):
        assert cohort.policy_for(col) is cohort.Policy.POOLABLE


def test_unclassified_column_raises_with_the_fix():
    with pytest.raises(cohort.CohortError) as e:
        cohort.policy_for("some_new_field")
    msg = str(e.value)
    assert "some_new_field" in msg
    assert "src/sami/cohort.py" in msg


def test_requires_split_is_false_for_poolable():
    assert cohort.requires_split("city_canon") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cohort.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sami.cohort'`.

- [ ] **Step 3: Create `src/sami/cohort.py`**

```python
"""Questionnaire-version cohorts and which variables may be pooled across them.

The chatbot's registration survey was rewritten between v1 and v2. Three kinds
of change make a naive total wrong, and none of them announce themselves:

- **v1 excluded people.** Q3 terminated the survey for anyone answering
  "Colombia", so v1 rows contain no Colombians *by construction* — 0 of 1,355.
  A pooled nationality share measures that exit rule, not the user base.
- **Questions were retired.** Q9 (away_duration), Q10 (prev_country),
  Q13 (would_recommend) and Q14 (recommendation_text) are gone in v2. Their
  totals freeze while every other total grows, which reads as collapse.
- **A question was added.** Q12a exists only for v2 respondents.

Every export MMC downloads keeps carrying the v1 rows, so none of this ages
out. The policy below is therefore a permanent part of the contract, not a
migration artifact. See
docs/superpowers/specs/2026-07-28-sami-v2-export-migration-design.md.
"""
from __future__ import annotations

from enum import Enum

import pandas as pd


class Policy(str, Enum):
    """How a variable may be aggregated across questionnaire versions."""

    POOLABLE = "poolable"    # same question and options in both — total is valid
    SPLIT = "split"          # must be reported per instrument_version
    V1_ONLY = "v1_only"      # question retired in v2; series is frozen
    V2_ONLY = "v2_only"      # question added in v2; no v1 history


class CohortError(Exception):
    """A variable has no comparability policy. Message carries the fix."""


# The column the platform writes on rows carried over from the v1 bot.
V1_MARKER_COLUMN = "Migrated From v1"

POLICY: dict[str, Policy] = {
    # --- not comparable across versions ---
    "nationality_canon": Policy.SPLIT,
    "nationality_clean": Policy.SPLIT,
    # --- retired in v2 ---
    "away_duration_canon": Policy.V1_ONLY,
    "away_duration_order": Policy.V1_ONLY,
    "would_recommend": Policy.V1_ONLY,
    "recommendation_text": Policy.V1_ONLY,
    # --- added in v2 ---
    "no_usefulness_reason": Policy.V2_ONLY,
    "reason_is_valid": Policy.V2_ONLY,
    "language": Policy.V2_ONLY,
    "registration_status": Policy.V2_ONLY,
    "attempts": Policy.V2_ONLY,
    "is_returning": Policy.V2_ONLY,
    "safety_alert": Policy.V2_ONLY,
    "escalation_status": Policy.V2_ONLY,
    # --- identical question and options in both versions ---
    "user_id": Policy.POOLABLE,
    "ts": Policy.POOLABLE,
    "instrument_version": Policy.POOLABLE,
    "gender_clean": Policy.POOLABLE,
    "age_num": Policy.POOLABLE,
    "age_flag": Policy.POOLABLE,
    "age_range": Policy.POOLABLE,
    "minors": Policy.POOLABLE,
    "destination_country": Policy.POOLABLE,
    "intends_to_stay": Policy.POOLABLE,
    # City's option list widened 3 -> 8, but canon.clean_city already merges
    # City with the City_other free text and recovers most of the v1 "Otra"
    # bucket, so the canonical distribution is comparable.
    "city_canon": Policy.POOLABLE,
    "city_clean": Policy.POOLABLE,
    "department": Policy.POOLABLE,
    "city_duration_canon": Policy.POOLABLE,
    "city_duration_order": Policy.POOLABLE,
    "dominant_category": Policy.POOLABLE,
    "n_questions": Policy.POOLABLE,
    "n_msgs_user": Policy.POOLABLE,
    "has_text": Policy.POOLABLE,
    "first_seen": Policy.POOLABLE,
    "is_repeat_asker": Policy.POOLABLE,
    "cluster_id": Policy.POOLABLE,
    "usefulness_rating": Policy.POOLABLE,
    "rating_num": Policy.POOLABLE,
    "discovery_channel": Policy.POOLABLE,
    "discovery_other": Policy.POOLABLE,
}


def instrument_version(frame: pd.DataFrame) -> pd.Series:
    """`"v1"` where the migration marker is present, else `"v2"`.

    An export with no marker column at all yields all-`"v2"` — the correct
    reading once the v1 rows have aged out of the platform.
    """
    if V1_MARKER_COLUMN not in frame.columns:
        return pd.Series(["v2"] * len(frame), index=frame.index, dtype="object")
    marker = frame[V1_MARKER_COLUMN]
    return pd.Series(
        ["v1" if present else "v2" for present in marker.notna()],
        index=frame.index, dtype="object")


def policy_for(column: str) -> Policy:
    """The comparability policy for `column`, or raise naming the fix."""
    try:
        return POLICY[column]
    except KeyError:
        raise CohortError(
            f"'{column}' has no cohort policy, so it cannot be aggregated.\n"
            "  why:  the v1 and v2 registration surveys differ — some variables "
            "cannot be pooled across them (v1 excluded Colombian respondents; "
            "several questions were retired or added).\n"
            "  fix:  classify it in POLICY in src/sami/cohort.py as one of "
            "POOLABLE / SPLIT / V1_ONLY / V2_ONLY. See "
            "docs/superpowers/specs/2026-07-28-sami-v2-export-migration-design.md"
        ) from None


def requires_split(column: str) -> bool:
    """True when `column` must be reported per instrument version."""
    return policy_for(column) is Policy.SPLIT
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cohort.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sami/cohort.py tests/test_cohort.py
git commit -m "feat(sami): cohort comparability policy

v1 and v2 ran different registration surveys: v1 terminated Colombian
respondents, four questions were retired and one added. Every future
export keeps carrying the v1 rows, so the distinction is permanent.
POLICY classifies each variable and policy_for raises on anything
unclassified, so a new field cannot be silently pooled."
```

---

### Task 7: `canon.py` value-domain updates

**Scope note — verified against the running code, not assumed.** Most of the
value-domain work this migration seemed to need is already done:

- **Cities:** 11 of the 12 relevant cities already canonicalize *and* already
  have map coordinates. `CITY_CANON` was built from the v1 `City_other` free
  text, which already contained Bogotá, Cali, Soacha, Barranquilla and the
  rest. **Only `Pasto` is missing** — it was never typed in v1 free text and is
  new as a dropdown option.
- **Gender:** `gender_display` is a closed-set lookup, so junk (`bhdhb`, `jj`)
  already renders as `Other` and `Trans` already renders as `Transgender`. No
  noise rule is needed; the closed set already contains the blast radius.
- **`Sí`/`Si`:** `yes_no_display` already folds accents — both give `Yes`.
- **Colombia:** `nationality_canon("Colombia")` already returns `Colombia`.

That leaves two genuine gaps.

**Files:**
- Modify: `src/sami/canon.py` — `CITY_CANON`, `CITY_COORDS`, `DISCOVERY_DISPLAY_EN`
- Test: `tests/test_canon.py`

**Interfaces:**
- Consumes: nothing
- Produces: no signature changes — two widened lookup tables.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_canon.py`:

```python
from sami import canon


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_canon.py -k "pasto or v2_dropdown or discovery_wordings" -v`
Expected: FAIL — `clean_city("Pasto", None)` canonicalizes to `'Otra'`, and `KeyError: 'Otro migrante'`.

- [ ] **Step 3: Add Pasto**

In `CITY_CANON`, add alongside the existing entries:

```python
    "pasto": "Pasto",
```

In `CITY_COORDS`, add:

```python
    "Pasto": (1.2136, -77.2811),
```

- [ ] **Step 4: Add the v2 discovery wordings**

In `DISCOVERY_DISPLAY_EN`, add two entries pointing at the *existing* English
labels (do not invent new strings — these must match the v1 values exactly or
the two vintages will still render as separate slices):

```python
    # v2 reworded these two options; both vintages map to one label so a
    # pooled chart does not split the same answer in two.
    "Otro migrante": "Referral from another migrant",
    "Recomendación de ONG": "Referral from an NGO",
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_canon.py -v`
Expected: all pass, including the pre-existing ones.

- [ ] **Step 6: Commit**

```bash
git add src/sami/canon.py tests/test_canon.py
git commit -m "feat(sami): Pasto and the v2 discovery wordings

The v2 survey added Pasto as a city option; it never appeared in the v1
free text CITY_CANON was built from, so it fell into 'Otra' and had no map
coordinates. v2 also reworded two discovery options, which passed through
untranslated and split one answer across two slices.

Verified as the only canon gaps: the other 11 cities, the closed-set
gender display, accent folding for Sí/Si and Colombia as a nationality all
already work."
```

---

### Task 8: Prose-summary tripwire

**Files:**
- Modify: `src/sami/qa.py` (add `summary_prose_share`, extend `run_checks`), `src/sami/facade.py:33` (critical prefix fix)
- Test: `tests/test_qa.py`

**Interfaces:**
- Consumes: nothing
- Produces: `qa.SUMMARY_PROSE_THRESHOLD = 0.05`; `qa.summary_prose_share(responses) -> float`; `run_checks` gains a `("P9_summary_format", bool, str)` entry. `facade` raises on prefixes `("P1_", "P6_", "P9_")`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_qa.py`:

```python
import pandas as pd
from sami import qa


def test_summary_prose_share_detects_the_v2_format():
    df = pd.DataFrame({"Chat_summary": [
        "#legal documentation",
        "humanitarian assistance",
        "[2026-07-24 14:15] El usuario preguntó sobre X, Y y Z.",
        None,
    ]})
    # 1 prose of 3 non-null
    assert abs(qa.summary_prose_share(df) - 1 / 3) < 1e-9


def test_summary_prose_share_is_zero_without_the_column():
    assert qa.summary_prose_share(pd.DataFrame({"a": [1]})) == 0.0


def test_summary_format_check_passes_below_threshold():
    df = pd.DataFrame({"Chat_summary": ["#employment"] * 99
                       + ["[2026-07-24 10:00] prosa"]})
    name, ok, _ = [c for c in _checks_for(df) if c[0] == "P9_summary_format"][0]
    assert ok is True


def test_summary_format_check_fails_above_threshold():
    df = pd.DataFrame({"Chat_summary": ["#employment"] * 5
                       + ["[2026-07-24 10:00] prosa"] * 5})
    name, ok, detail = [c for c in _checks_for(df) if c[0] == "P9_summary_format"][0]
    assert ok is False
    assert "50" in detail or "0.5" in detail


def _checks_for(responses):
    """run_checks needs three frames; build the minimal messages/meal shapes."""
    responses = responses.assign(
        user_id=[f"u{i}" for i in range(len(responses))],
        dominant_category="employment",
        n_questions=1)
    messages = pd.DataFrame({"user_id": responses["user_id"],
                             "n_msgs_user": 1, "message": "x"})
    meal = pd.DataFrame({"user_id": responses["user_id"]})
    return qa.run_checks(responses, messages, meal)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_qa.py -k "prose or summary_format" -v`
Expected: FAIL — `module 'sami.qa' has no attribute 'summary_prose_share'`.

- [ ] **Step 3: Add the tripwire to `qa.py`**

Add near the top of `qa.py`, after `_PII_PATTERNS`:

```python
# The v2 platform emits a timestamped prose summary instead of the short
# taxonomy label v1 emitted ("[2026-07-24 14:15] El usuario preguntó sobre...").
# taxonomy.normalize_category is an exact-match lookup, so prose becomes
# 'unclassified'. At 1.4% of rows that is honest noise; left unattended it grows
# until dominant_category means nothing, with the charts still rendering. This
# check fails the run at the point the field stops being usable.
_SUMMARY_PROSE = re.compile(r"^\s*\[\d{4}-\d{2}-\d{2}")
SUMMARY_PROSE_THRESHOLD = 0.05


def summary_prose_share(responses: pd.DataFrame,
                        col: str = "Chat_summary") -> float:
    """Share of non-null summaries in the v2 prose format. 0.0 if absent."""
    if col not in responses.columns:
        return 0.0
    values = responses[col].dropna()
    if values.empty:
        return 0.0
    hits = values.astype(str).str.match(_SUMMARY_PROSE)
    return float(hits.mean())
```

Then add to `run_checks`, before the `return`:

```python
    prose = summary_prose_share(responses)
    checks.append((
        "P9_summary_format",
        bool(prose <= SUMMARY_PROSE_THRESHOLD),
        f"{prose:.1%} of summaries are v2 prose (limit "
        f"{SUMMARY_PROSE_THRESHOLD:.0%}) — above this, dominant_category is no "
        f"longer meaningful. See the spec's 'Summary field changed format'."))
```

- [ ] **Step 4: Make `facade` treat P9 as critical**

In `src/sami/facade.py` line 33, change:

```python
    failed = [c for c in checks if not c[1] and c[0].startswith(("P1", "P6"))]
```

to:

```python
    # Underscore-anchored: bare "P1" would also match "P9"/"P11" style names.
    failed = [c for c in checks if not c[1] and c[0].startswith(("P1_", "P6_", "P9_"))]
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_qa.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/sami/qa.py src/sami/facade.py tests/test_qa.py
git commit -m "feat(sami): fail the run when the summary field ages out

v2 emits prose where v1 emitted a taxonomy label, and prose falls through
normalize_category to 'unclassified'. At 1.4% that is honest noise; the
check fails the run past 5%, before dominant_category quietly becomes
meaningless. Also anchors facade's critical-prefix match on underscores."
```

---

### Task 9: Content-hash `message_id`

**Files:**
- Modify: `src/sami/export.py:161-173` (`build_fact_message`)
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: nothing
- Produces: `export.message_key(user_id, seq, message) -> str` — 16-char sha1 hex. `build_fact_message` uses it for `message_id` instead of the positional index. Signature unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_export.py`:

```python
import pandas as pd
from sami import export


def _spine():
    return pd.DataFrame({
        "user_id": ["u1", "u1", "u2"],
        "ts": pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"]),
        "message": ["hola que tal", "necesito ayuda", "busco empleo"],
        "seq": [0, 1, 0],
        "n_msgs_user": [2, 2, 1],
        "city_canon": ["Medellín", "Medellín", "Cúcuta"],
        "dominant_category": ["employment", "employment", "employment"],
    })


def test_message_id_is_stable_when_other_users_are_added():
    """Regression: message_id was messages.reset_index(), a POSITIONAL id.
    The spine is sorted by (user_id, ts), so one new user re-numbered every
    row — silently re-pointing anything keyed on it."""
    base = _spine()
    before = export.build_fact_message(base)
    grown = pd.concat([
        pd.DataFrame({
            "user_id": ["u0"], "ts": pd.to_datetime(["2026-03-01"]),
            "message": ["mensaje nuevo"], "seq": [0], "n_msgs_user": [1],
            "city_canon": ["Bogotá"], "dominant_category": ["services"],
        }), base]).reset_index(drop=True)
    after = export.build_fact_message(grown)

    got = after.set_index("user_id").loc["u2", "message_id"]
    want = before.set_index("user_id").loc["u2", "message_id"]
    assert got == want


def test_message_id_is_unique_per_row():
    f = export.build_fact_message(_spine())
    assert f["message_id"].is_unique


def test_message_id_differs_for_identical_text_from_different_users():
    df = pd.DataFrame({
        "user_id": ["u1", "u2"], "ts": pd.to_datetime(["2026-04-01"] * 2),
        "message": ["gracias", "gracias"], "seq": [0, 0], "n_msgs_user": [1, 1],
        "city_canon": ["Medellín"] * 2, "dominant_category": ["services"] * 2,
    })
    f = export.build_fact_message(df)
    assert f["message_id"].nunique() == 2


def test_message_id_contains_no_pii():
    f = export.build_fact_message(_spine())
    assert f["message_id"].str.match(r"^[0-9a-f]{16}$").all()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -k message_id -v`
Expected: FAIL on `test_message_id_is_stable_when_other_users_are_added` — ids are `0,1,2` before and `1,2,3` after.

- [ ] **Step 3: Add `message_key` and use it**

In `export.py`, add after the `_mapper` helper:

```python
def message_key(user_id, seq, message) -> str:
    """Stable id for one message: sha1(user_id|seq|text)[:16].

    Replaces a positional index. `load.load_messages` sorts the spine by
    (user_id, ts), so a positional id was re-assigned to a DIFFERENT message
    every time the corpus grew — silently invalidating anything keyed on it,
    including the tone gold labels. Keying on the user plus their own message
    sequence is stable under new users and new messages, because a user's own
    history only ever appends.
    """
    raw = f"{user_id}|{seq}|{message}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
```

Then replace the first two lines of `build_fact_message`:

```python
    f = messages.reset_index().rename(columns={"index": "message_id"})
    f = f[[c for c in _FACT_MSG_COLS if c in f.columns]].copy()
```

with:

```python
    f = messages.copy()
    f["message_id"] = [message_key(u, s, m) for u, s, m
                       in zip(f["user_id"], f["seq"], f["message"])]
    f = f[[c for c in _FACT_MSG_COLS if c in f.columns]].copy()
```

Note `hashlib` is already imported at the top of `export.py`.

The `sentiment` lookup below still uses `messages.index`, which is unchanged — leave it.

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: the four new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "fix(sami): stable content-hash message_id

message_id was messages.reset_index() — a positional id over a spine
sorted by (user_id, ts), so adding messages renumbered every row and
silently re-pointed anything keyed on it. Now sha1(user_id|seq|text),
which is stable because a user's own history only appends.

This orphans validation/tone_gold_labels.csv by design: those ids are
already invalid against the new corpus, and a stable key is a
precondition for re-keying them. The NLP spec owns that."
```

---

### Task 10: `dim_user` gains cohort and v2 fields

**Files:**
- Modify: `src/sami/export.py:99-107` (`_PROFILE_COLS`, `_RAW_RENAME`), `src/sami/export.py:128-158` (`build_dim_user`)
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `cohort.instrument_version` from Task 6
- Produces: `dim_user` gains `instrument_version`, `language`, `registration_status`, `attempts`, `is_returning`, `safety_alert`, `escalation_status`. `build_dim_user` signature unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_export.py`:

```python
from sami import cohort


def _responses_two_cohorts():
    return pd.DataFrame({
        "user_id": ["u1", "u2"],
        "ts": pd.to_datetime(["2026-04-01", "2026-07-25"]),
        "gender_clean": ["Mujer", "Hombre"],
        "age_num": [30.0, 28.0],
        "city_canon": ["Medellín", "Ipiales"],
        "dominant_category": ["employment", "unclassified"],
        "n_questions": [2, 1],
        "Migrated From v1": ["v1:100", None],
        "Language": ["es", "en"],
        "Registration Status": ["Completed", "Completed"],
        "Attempts": [1, 2],
        "Is Returning User": [None, "yes"],
        "Safety Alert": [None, "flagged"],
        "Escalation Status": [None, "escalated"],
        "Destination_Country": ["Colombia", "Chile"],
    })


def _messages_two_users():
    return pd.DataFrame({
        "user_id": ["u1", "u2"], "ts": pd.to_datetime(["2026-04-01", "2026-07-25"]),
        "message": ["hola", "help"], "seq": [0, 0], "n_msgs_user": [1, 1],
    })


def test_dim_user_carries_instrument_version():
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users())
    assert dict(zip(d["user_id"], d["instrument_version"])) == {"u1": "v1", "u2": "v2"}


def test_dim_user_carries_the_new_v2_fields():
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users())
    for col in ("language", "registration_status", "attempts", "is_returning",
                "safety_alert", "escalation_status"):
        assert col in d.columns, f"{col} missing from dim_user"
    assert d.set_index("user_id").loc["u2", "language"] == "en"


def test_every_dim_user_column_has_a_cohort_policy():
    """The guard is only a guard if it cannot fall behind the schema."""
    d = export.build_dim_user(_responses_two_cohorts(), _messages_two_users())
    for col in d.columns:
        cohort.policy_for(col)   # raises CohortError if unclassified
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -k dim_user -v`
Expected: FAIL — `KeyError: 'instrument_version'`.

- [ ] **Step 3: Extend `_RAW_RENAME` and `build_dim_user`**

In `export.py`, add `cohort` to the imports:

```python
from . import metrics, taxonomy, qa, canon, theme, cohort
```

Extend `_RAW_RENAME`:

```python
_RAW_RENAME = {"Minors": "minors", "Age Ranges": "age_range",
               "Destination_Country": "destination_country",
               "Language": "language",
               "Registration Status": "registration_status",
               "Attempts": "attempts",
               "Is Returning User": "is_returning",
               "Safety Alert": "safety_alert",
               "Escalation Status": "escalation_status"}
```

In `build_dim_user`, immediately after `r = responses.sort_values("ts", kind="stable")`, add:

```python
    # Derived before the groupby so 'first' picks the version of the user's
    # earliest record — a user who appears in both cohorts is counted as v1,
    # which is when they actually answered the registration survey.
    r = r.assign(instrument_version=cohort.instrument_version(r).values)
```

Then add `"instrument_version"` to `_PROFILE_COLS` (first entry, so it sorts to the front of the profile block).

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: all pass. If `test_every_dim_user_column_has_a_cohort_policy` fails, add the named column to `POLICY` in `cohort.py` — that is the test doing its job.

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): dim_user carries instrument_version and v2 fields

instrument_version makes the v1/v2 split sliceable in Power BI, and a test
asserts every dim_user column is classified in cohort.POLICY so the guard
cannot fall behind the schema."
```

---

### Task 11: `fact_meal` — the Q12a validity flag

**Files:**
- Modify: `src/sami/export.py:176-183` (`_FACT_MEAL_COLS`, `build_fact_meal`)
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: nothing
- Produces: `export.REASON_VALID_RATINGS: frozenset[str]`; `fact_meal` gains `no_usefulness_reason` and `reason_is_valid` (bool).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_export.py`:

```python
def _meal_frame():
    return pd.DataFrame({
        "user_id": ["u1", "u2", "u3", "u4"],
        "ts": pd.to_datetime(["2026-07-01"] * 4),
        "usefulness_rating": ["Muy útil", "Nada útil", "Medianamente útil", "Útil"],
        "no_usefulness_reason": ["no", "te confundiste de ciudad",
                                 "faltó info", "Todo bien gracias"],
    })


def test_reason_is_valid_only_for_dissatisfied_ratings():
    """The v2 skip logic misfired: 'why wasn't it useful' was asked of 118
    people, 75 of whom rated it Útil/Muy útil and answered with negations.
    Only the dissatisfied answers are analytically usable."""
    f = export.build_fact_meal(_meal_frame())
    valid = dict(zip(f["user_id"], f["reason_is_valid"]))
    assert valid == {"u1": False, "u2": True, "u3": True, "u4": False}


def test_reason_is_valid_is_false_when_no_reason_given():
    df = _meal_frame().assign(no_usefulness_reason=[None] * 4)
    f = export.build_fact_meal(df)
    assert not f["reason_is_valid"].any()


def test_fact_meal_survives_a_missing_reason_column():
    """A v1-only archive export has no Q12a at all."""
    df = _meal_frame().drop(columns=["no_usefulness_reason"])
    f = export.build_fact_meal(df)
    assert "reason_is_valid" in f.columns
    assert not f["reason_is_valid"].any()


def test_every_fact_meal_column_has_a_cohort_policy():
    f = export.build_fact_meal(_meal_frame())
    for col in f.columns:
        cohort.policy_for(col)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -k "reason or fact_meal" -v`
Expected: FAIL — `KeyError: 'reason_is_valid'`.

- [ ] **Step 3: Implement in `export.py`**

Replace `_FACT_MEAL_COLS` and `build_fact_meal`:

```python
# Ratings for which the v2 "¿Por qué la información entregada no fue útil?"
# question was SUPPOSED to fire. Its skip logic misfired in production: it was
# asked of 118 respondents, 75 of whom had rated the service Útil or Muy útil
# and answered with negations ("no", "Todo bien gracias"). Counting all 118 as
# reasons-for-failure is 64% noise, so the validity is carried in the data
# rather than in a note nobody reads.
REASON_VALID_RATINGS = frozenset({"Nada útil", "Poco útil", "Medianamente útil"})

_FACT_MEAL_COLS = ["user_id", "ts", "usefulness_rating", "rating_num",
                   "would_recommend", "recommendation_text", "discovery_channel",
                   "no_usefulness_reason", "reason_is_valid"]


def build_fact_meal(meal: pd.DataFrame) -> pd.DataFrame:
    f = meal.copy()
    f["rating_num"] = f["usefulness_rating"].map(RATING_NUM)
    # Computed BEFORE to_english_meal, which rewrites the Spanish vocabulary.
    if "no_usefulness_reason" not in f.columns:
        f["no_usefulness_reason"] = pd.NA
    f["reason_is_valid"] = (f["usefulness_rating"].isin(REASON_VALID_RATINGS)
                            & f["no_usefulness_reason"].notna())
    return to_english_meal(f[[c for c in _FACT_MEAL_COLS if c in f.columns]].copy())
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/sami/export.py tests/test_export.py
git commit -m "feat(sami): flag which Q12a reasons are analytically valid

The v2 'why wasn't it useful' question fired for satisfied respondents
too — 75 of 118 answers came from people who rated it Útil or Muy útil.
reason_is_valid encodes the intended skip logic in the data so a Power BI
user cannot count 118 reasons for failure when only 43 are real."
```

---

### Task 12: New aggregate tables + pipeline wiring

**Files:**
- Modify: `src/sami/export.py` (add two builders), `run_pipeline.py:142-160`
- Modify: `src/sami/config.py:8-9`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `cohort.instrument_version` from Task 6
- Produces: `export.build_agg_registration_funnel(responses) -> DataFrame` with columns `stage_order, stage, n, pct_of_started`; `export.build_agg_language(responses) -> DataFrame` with `language, instrument_version, n_users`. Both registered in `run_pipeline.main`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_export.py`:

```python
def _responses_registration():
    return pd.DataFrame({
        "user_id": ["u1", "u2", "u3", "u4"],
        "ts": pd.to_datetime(["2026-07-25"] * 4),
        "Registration Status": ["Completed", "Completed", "Abandoned",
                                "In Progress"],
        "Registration Started": ["2026-07-25T09:00:00Z"] * 4,
        "Registration Completed": ["2026-07-25T09:05:00Z",
                                   "2026-07-25T09:06:00Z", None, None],
        "Attempts": [1, 2, 3, 1],
        "Language": ["es", "es", "en", "es"],
        "Migrated From v1": [None, None, None, "v1:1"],
    })


def test_agg_registration_funnel_stages_and_counts():
    f = export.build_agg_registration_funnel(_responses_registration())
    counts = dict(zip(f["stage"], f["n"]))
    assert counts["registration started"] == 4
    assert counts["registration completed"] == 2
    assert counts["abandoned"] == 1
    assert counts["in progress"] == 1


def test_agg_registration_funnel_is_ordered():
    f = export.build_agg_registration_funnel(_responses_registration())
    assert list(f["stage_order"]) == sorted(f["stage_order"])


def test_agg_registration_funnel_pct_is_relative_to_started():
    f = export.build_agg_registration_funnel(_responses_registration())
    row = f[f["stage"] == "registration completed"].iloc[0]
    assert abs(row["pct_of_started"] - 50.0) < 1e-9


def test_agg_language_splits_by_instrument_version():
    f = export.build_agg_language(_responses_registration())
    got = {(r.language, r.instrument_version): r.n_users
           for r in f.itertuples()}
    assert got[("es", "v2")] == 2
    assert got[("en", "v2")] == 1
    assert got[("es", "v1")] == 1


def test_agg_registration_funnel_empty_without_the_columns():
    """A v1-only archive export has no registration fields."""
    df = pd.DataFrame({"user_id": ["u1"], "ts": pd.to_datetime(["2026-04-01"])})
    f = export.build_agg_registration_funnel(df)
    assert list(f.columns) == ["stage_order", "stage", "n", "pct_of_started"]
    assert len(f) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -k "registration or agg_language" -v`
Expected: FAIL — `module 'sami.export' has no attribute 'build_agg_registration_funnel'`.

- [ ] **Step 3: Add the builders to `export.py`**

Add after `build_agg_funnel`:

```python
# Registration is the stage BEFORE `agg_funnel`'s "arrived": the v1 platform
# exposed nothing about people who started the survey and never finished, so
# this is new ground rather than a re-cut of the existing funnel.
_REG_STAGES = ("registration started", "registration completed",
               "abandoned", "in progress")


def build_agg_registration_funnel(responses: pd.DataFrame) -> pd.DataFrame:
    """Ordered pre-conversation funnel from the v2 registration fields.

    Empty (with the right columns) when the export predates those fields, so a
    v1-only archive still writes a well-formed table.
    """
    cols = ["stage_order", "stage", "n", "pct_of_started"]
    if "Registration Status" not in responses.columns:
        return pd.DataFrame(columns=cols)
    status = responses["Registration Status"].astype("string").str.strip().str.lower()
    started = len(responses)
    counts = {
        "registration started": started,
        "registration completed": int((status == "completed").sum()),
        "abandoned": int((status == "abandoned").sum()),
        "in progress": int((status == "in progress").sum()),
    }
    rows = [{"stage_order": i, "stage": stage, "n": counts[stage],
             "pct_of_started": (round(100 * counts[stage] / started, 1)
                                if started else 0.0)}
            for i, stage in enumerate(_REG_STAGES)]
    return pd.DataFrame(rows, columns=cols)


def build_agg_language(responses: pd.DataFrame) -> pd.DataFrame:
    """Users per interface language, split by instrument version.

    Split because the language selector is v2-only: a pooled count would read
    as 99% Spanish when the question simply did not exist for v1 users.
    """
    cols = ["language", "instrument_version", "n_users"]
    if "Language" not in responses.columns:
        return pd.DataFrame(columns=cols)
    r = responses.assign(
        instrument_version=cohort.instrument_version(responses).values)
    g = (r.dropna(subset=["Language"])
         .groupby(["Language", "instrument_version"])["user_id"]
         .nunique().reset_index())
    g.columns = cols
    return g.sort_values(["instrument_version", "n_users"],
                         ascending=[True, False]).reset_index(drop=True)
```

- [ ] **Step 4: Point `config.py` at the v2 files**

Replace `src/sami/config.py` lines 8–9:

```python
RESPONSES_PATH = DATA_DIR / "Users_Group_Title_2807.xlsx"
MEAL_PATH = DATA_DIR / "Survey_Responses_Group_Title_2807.xlsx"
```

- [ ] **Step 5: Register the tables in `run_pipeline.py`**

In `main`, inside the `with pr.stage("aggregate tables"):` block, add to the `tables` dict alongside the existing entries:

```python
            "agg_registration_funnel": export.build_agg_registration_funnel(SD.responses),
            "agg_language": export.build_agg_language(SD.responses),
```

- [ ] **Step 6: Bump the schema version**

In `export.build_meta_run`, change the default `schema_version: str = "2"` to `"3"`.

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export.py -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/sami/export.py src/sami/config.py run_pipeline.py tests/test_export.py
git commit -m "feat(sami): registration funnel and language tables, v2 paths

The v2 export exposes who started registration and never finished, which
the v1 platform never showed. agg_language is split by instrument version
because the selector is v2-only and a pooled count would read as 99%
Spanish. Schema version 2 -> 3."
```

---

### Task 13: Real-data tests become invariants

**Files:**
- Modify: `tests/test_load_responses.py`, `tests/test_load_meal.py`, `tests/test_load_sami.py`, `tests/test_message_spine.py`, `tests/test_metrics.py`, `tests/test_stats.py` — any test asserting an exact count against `config.RESPONSES_PATH` / `config.MEAL_PATH`
- Test: the same files

**Interfaces:**
- Consumes: fixtures from Task 1
- Produces: a `requires_real_data` skip marker available to all test modules via `tests/conftest.py`.

- [ ] **Step 1: Find every hard-coded count**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v 2>&1 | grep -E "FAILED|assert"`

Also run: `grep -rnE "== *(946|917|2991|3207|69|78|800|200)\b" tests/`

Record the list. Every one of these is a test that would go red for MMC on a fresh export.

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared fixtures and the real-data skip marker.

Tests that assert exact counts run against the committed synthetic fixtures, so
they stay green on any export. Tests that need the real (gitignored) export are
marked `requires_real_data` and skip cleanly when it is absent — which is the
normal state for anyone who is not the author.
"""
from pathlib import Path

import pytest

from sami import config

FIXTURES = Path(__file__).resolve().parent / "fixtures"
USERS_FIXTURE = FIXTURES / "users_v2.xlsx"
SURVEY_FIXTURE = FIXTURES / "survey_v2.xlsx"

requires_real_data = pytest.mark.skipif(
    not (Path(config.RESPONSES_PATH).exists() and Path(config.MEAL_PATH).exists()),
    reason="real export not present (data_&_docs/ is gitignored)")


@pytest.fixture
def users_fixture() -> Path:
    return USERS_FIXTURE


@pytest.fixture
def survey_fixture() -> Path:
    return SURVEY_FIXTURE
```

- [ ] **Step 3: Convert each exact-count test**

For every test found in Step 1, apply one of two transformations.

**If it asserts a count** — repoint it at the fixture. For example, replace:

```python
def test_load_responses_counts():
    df = load.load_responses()
    assert len(df) == 946
```

with:

```python
def test_load_responses_counts(users_fixture):
    df = load.load_responses(users_fixture, salt="test_salt")
    assert len(df) == 6
```

**If it asserts a property that must hold for any export** — keep it on real data and mark it. For example:

```python
from conftest import requires_real_data


@requires_real_data
def test_real_export_reconciles():
    """Invariant: holds for the December export too, not just today's."""
    from sami import facade
    SD = facade.load_sami()
    recon = SD.reconciliation.set_index("metric")["value"].to_dict()
    assert recon["users"] == SD.responses["user_id"].nunique()
    assert recon["messages"] == len(SD.messages)
    assert recon["users_with_text"] <= recon["users"]


@requires_real_data
def test_real_export_has_no_pii():
    from sami import facade, qa
    SD = facade.load_sami()
    assert qa.pii_scan(SD.responses) == []
    assert qa.pii_scan(SD.messages) == []
    assert qa.pii_scan(SD.meal) == []
```

- [ ] **Step 4: Add the user_id-stability invariant**

This is the concrete proof that the phone-key fix works. Add to `tests/test_load_responses.py`:

```python
@requires_real_data
def test_user_ids_match_the_pre_migration_exports():
    """The migration must not re-pseudonymize. Every user_id in the previous
    dim_user export must still be present after the v2 switch."""
    import pandas as pd
    from pathlib import Path
    from sami import facade

    previous = Path("exports/dim_user.csv")
    if not previous.exists():
        import pytest
        pytest.skip("no previous export to compare against")
    old_ids = set(pd.read_csv(previous)["user_id"])
    new_ids = set(facade.load_sami().responses["user_id"])
    missing = old_ids - new_ids
    assert not missing, f"{len(missing)} user_ids changed in the migration"
```

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all pass. Real-data tests either pass or skip; none fail.

- [ ] **Step 6: Verify the suite is green WITHOUT the real data**

Run: `SAMI_SALT=x .venv/Scripts/python.exe -m pytest tests/ -v -p no:cacheprovider` with `data_&_docs/` temporarily renamed, or simply confirm the `requires_real_data` tests report as skipped rather than failed.
Expected: zero failures, some skips. This is what MMC will see.

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "test(sami): fixtures for counts, invariants for real data

Exact-count assertions ran against the real export, so they would go red
for MMC the first time they refreshed data — teaching them to ignore test
failures. Counts now run on the synthetic fixtures; real-data tests assert
properties that hold for any export and skip when it is absent."
```

---

### Task 14: Full pipeline run on the real v2 export

The first end-to-end verification. No new code unless something breaks.

**Files:**
- Modify: whatever the run reveals
- Modify: `exports/_schema.md`

**Interfaces:**
- Consumes: everything above
- Produces: a regenerated `exports/` directory at schema version 3.

- [ ] **Step 1: Run preflight**

Run: `.venv/Scripts/python.exe run_pipeline.py --check`
Expected: all checks pass. If a check still names an old filename or column, fix it in `preflight.py` and note it in the commit.

- [ ] **Step 2: Run the pipeline without NLP**

Run: `.venv/Scripts/python.exe run_pipeline.py --skip-nlp --out exports/`
Expected: every stage completes; the PII scan passes; a manifest is written.

If `P9_summary_format` fails, the prose share has exceeded 5% — check the actual share with:
`.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'src'); from sami import facade, qa; print(qa.summary_prose_share(facade.load_sami().responses))"`
At the time of writing it is 1.6% (19 of 1,154). A higher number means the platform has moved on and the spec's assumption needs revisiting — do not simply raise the threshold.

- [ ] **Step 3: Check the reconciliation numbers**

Run: `.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'src'); from sami import facade; print(facade.load_sami().reconciliation.to_string())"`

Expected, from the measurements in the spec:
- `users` = 1392
- `records` = 1460
- `meal_responses` = 115
- `users_with_text` ≈ 1275

If `users` is 1393 or the count is off by one, check whether the blank `Address` row is being kept — `_read_export` drops null ids.

- [ ] **Step 4: Verify parity and user-id stability**

Run: `.venv/Scripts/python.exe -c "import pandas as pd; print(pd.read_csv('exports/parity_check.csv').to_string())"`
Expected: `match` is True on every row.

Run: `.venv/Scripts/python.exe -m pytest tests/test_load_responses.py::test_user_ids_match_the_pre_migration_exports -v`
Expected: PASS — this is the proof that the phone-key fix preserved every user_id.

- [ ] **Step 5: Regenerate the schema documentation**

Update `exports/_schema.md` to describe the new and changed tables: `dim_user`'s seven new columns, `fact_meal`'s two, the new `agg_registration_funnel` and `agg_language`, the `message_id` change from positional to content hash, and `schema_version` 3.

- [ ] **Step 6: Commit**

```bash
git add exports/ docs/
git commit -m "data(sami): regenerate exports from the v2 platform export

1,392 users / 1,460 records / 115 MEAL responses, schema version 3.
Every user_id from the previous export is preserved."
```

---

### Task 15: NB1 — input and audience

Notebooks are too large for `Read`/`NotebookEdit`; edit them with a JSON script that locates cells by id, then verify by executing.

**Files:**
- Modify: `notebooks/01_input_and_audience.ipynb`

**Interfaces:**
- Consumes: the regenerated `exports/` and the updated `src/sami` modules
- Produces: an executed notebook whose reconciliation tables match Task 14's numbers

- [ ] **Step 1: Inventory the cells to change**

```bash
.venv/Scripts/python.exe - <<'EOF'
import json
nb = json.load(open("notebooks/01_input_and_audience.ipynb", encoding="utf-8"))
for c in nb["cells"]:
    src = "".join(c["source"])
    hits = [f for f in ("Away_duration", "away_duration", "Nationality",
                        "nationality_canon", "Minors", "minors", "946", "917",
                        "2991", "69 ") if f in src]
    if hits:
        print(c["id"], c["cell_type"], hits)
EOF
```

Record the cell ids — the edits below reference them.

- [ ] **Step 2: Update the two reconciliation tables**

Both the top and bottom reconciliation cells must show Task 14's measured values. They read from `SD.reconciliation`, so if any number is hard-coded in surrounding markdown, update it to: 1,392 users · 1,460 records · 115 MEAL responses.

- [ ] **Step 3: Split the nationality figure by cohort**

Replace the nationality plotting cell's data preparation with:

```python
# v1's registration survey TERMINATED anyone answering "Colombia" (Q3), so a
# pooled nationality share would measure that exit rule rather than the user
# base. cohort.POLICY marks this variable SPLIT; the figure honours it.
from sami import cohort

nat = dim_user.groupby(["instrument_version", "nationality_canon"])["user_id"] \
              .nunique().reset_index(name="n_users")
```

Then draw one panel per `instrument_version` (side by side, sharing a y axis), and add this markdown immediately above the figure:

```markdown
**Read these panels separately.** The v1 registration survey ended the
conversation for anyone who answered "Colombia" (question Q3), so Colombian
respondents are absent from the v1 panel *by design* — not because none used
the service. v2 removed that exit. Pooling the two panels would report the old
survey's exit rule as a finding about who the service reaches.
```

- [ ] **Step 4: Mark `away_duration` as retired**

Above the away-duration figure, add:

```markdown
**This series is frozen.** The question *"¿Hace cuánto saliste de tu país de
nacionalidad?"* (Q9) was removed when the survey was rewritten, so this chart
covers the v1 cohort only and will not grow. It is shown because it is the only
evidence on time-since-departure that exists, not because it is current.
```

And filter its data to `dim_user[dim_user["instrument_version"] == "v1"]`.

- [ ] **Step 5: Add the registration-funnel section**

Add a new `## 5 · Registration funnel` section reading `exports/agg_registration_funnel.csv`, drawn as a horizontal bar chart in the existing palette (`theme.BLUE_SEQ`), with this note:

```markdown
The v1 platform showed nothing about people who began the registration survey
and never finished, so this is new ground. **Caveat:** the v2 cohort is 105
users over five days. Treat the shape as indicative and redraw it once the
sample grows.
```

- [ ] **Step 6: Add the language section**

Add `## 6 · Interface language` reading `exports/agg_language.csv`, showing only the v2 rows, with:

```markdown
The language selector is v2-only, so v1 users are excluded rather than counted
as Spanish. Of the v2 cohort, 4 users chose English. French is offered in the
interface but has not been selected by anyone yet.
```

- [ ] **Step 7: Execute and verify**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/01_input_and_audience.ipynb`
Expected: completes with no exception.

Then extract and view the figures to confirm they render:

```bash
.venv/Scripts/python.exe - <<'EOF'
import json, base64, pathlib
nb = json.load(open("notebooks/01_input_and_audience.ipynb", encoding="utf-8"))
out = pathlib.Path(".superpowers/sdd/2026-07-28-sami-v2-export-migration/nb1-figs"); out.mkdir(parents=True, exist_ok=True)
n = 0
for c in nb["cells"]:
    for o in c.get("outputs", []):
        png = o.get("data", {}).get("image/png")
        if png:
            (out / f"fig{n:02d}.png").write_bytes(base64.b64decode(png)); n += 1
print(f"{n} figures ->", out)
EOF
```

Read several of the PNGs to confirm the nationality panels are side by side and the new sections rendered.

- [ ] **Step 8: Commit**

```bash
git add notebooks/01_input_and_audience.ipynb
git commit -m "notebook(sami): NB1 on v2 data

Nationality is split by instrument version because v1 terminated Colombian
respondents; away_duration is marked frozen because the question was
retired. Adds registration-funnel and language sections from the new v2
fields, with the small-sample caveat stated."
```

---

### Task 16: NB2 — demand, behaviour and experience

**Files:**
- Modify: `notebooks/02_demand_behaviour_experience.ipynb`

**Interfaces:**
- Consumes: regenerated `exports/`, `fact_meal.reason_is_valid`
- Produces: an executed notebook

- [ ] **Step 1: Inventory the cells to change**

```bash
.venv/Scripts/python.exe - <<'EOF'
import json
nb = json.load(open("notebooks/02_demand_behaviour_experience.ipynb", encoding="utf-8"))
for c in nb["cells"]:
    src = "".join(c["source"])
    hits = [f for f in ("would_recommend", "recommendation_text", "69",
                        "nationality_canon", "city_duration", "min_meal_n") if f in src]
    if hits:
        print(c["id"], c["cell_type"], hits)
EOF
```

- [ ] **Step 2: Update the §5 header and MEAL counts**

The section title says "MEAL join ≈ 69 users". Change to 115, and update any hard-coded n in the surrounding narrative.

- [ ] **Step 3: Convert `would_recommend` to a v1-only panel**

Filter its data to `fact_meal` rows whose users are `instrument_version == "v1"`, and add above it:

```markdown
**Frozen series.** *"¿Recomendarías este servicio a otras personas migrantes?"*
(Q13) was removed in the survey rewrite. These 110 responses are the complete
and final record; the count will not grow, so it must not be read as a trend.
```

- [ ] **Step 4: Add the "why wasn't it useful" section**

Add after the satisfaction pulse:

```python
# The v2 skip logic misfired — the question was put to satisfied respondents
# too, who answered with negations. reason_is_valid carries the intended
# condition, so only genuine dissatisfaction reasons are read here.
reasons = fact_meal[fact_meal["reason_is_valid"]]
```

with this markdown above it:

```markdown
### Why the information missed

v2 added *"¿Por qué la información entregada no fue útil?"*, shown when someone
rates the service poorly. In practice it fired for everyone, so 75 of the 118
answers come from satisfied users replying "no" to a question that did not
apply. Only the **43** responses from people who actually rated the service
Nada / Poco / Medianamente útil are read below. This is a small sample and is
reported as themes, not percentages.
```

- [ ] **Step 5: Re-check the priority-matrix fallback**

The `min_meal_n=20` guard was tuned when MEAL had 69 responses across 8 categories; it now has 115. Print which categories still fall back:

```python
pm = pd.read_csv("exports/agg_priority_matrix.csv")
print(pm[["category", "meal_n", "rating_is_fallback"]].to_string(index=False))
```

State the result in the narrative. Do not change the threshold — just report honestly which categories are carrying a fallback rating.

- [ ] **Step 6: State the unclassified-category exclusion**

`build_agg_priority_matrix` drops `unclassified` messages, and v2 users' summaries are prose and therefore unclassified. Add to the §6 narrative:

```markdown
**Coverage note.** The matrix excludes messages whose category is
`unclassified`, which includes every v2-cohort user — the new platform emits a
prose summary the taxonomy cannot map. That is 1.6% of summaries today. The
pipeline fails the run if it passes 5%, at which point this figure would need
rebuilding on a different category source.
```

- [ ] **Step 7: Execute and verify**

Run: `.venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace notebooks/02_demand_behaviour_experience.ipynb`
Expected: completes with no exception. Extract the PNGs as in Task 15 Step 7 and read a few.

- [ ] **Step 8: Commit**

```bash
git add notebooks/02_demand_behaviour_experience.ipynb
git commit -m "notebook(sami): NB2 on v2 data

MEAL n 69 -> 115. would_recommend becomes a frozen v1-only panel since
Q13 was retired. Adds the 'why wasn't it useful' themes over the 43 valid
responses, and states both the priority matrix's fallback categories and
its exclusion of the v2 cohort's unclassified summaries."
```

---

### Task 17: Documentation

**Files:**
- Modify: `README.md`, `docs/powerbi_guide.md`

- [ ] **Step 1: Update `README.md`**

Update the data-files section to name `Users_Group_Title_2807.xlsx` and `Survey_Responses_Group_Title_2807.xlsx`, and add a short subsection:

```markdown
### Questionnaire versions

The registration survey was rewritten in July 2026. Every export carries both
cohorts, distinguished by `instrument_version` in `dim_user`.

Some variables cannot be pooled across them — most importantly **nationality**,
because the v1 survey ended the conversation for Colombian respondents. Four
questions were retired (time since leaving, previous country, would-recommend,
improvement suggestions) and one was added (why the information was not useful).

`src/sami/cohort.py` holds the policy. If you add a field to `dim_user` or
`fact_meal`, classify it there or the pipeline will refuse to aggregate it.
```

- [ ] **Step 2: Update `docs/powerbi_guide.md`**

Document the new tables (`agg_registration_funnel`, `agg_language`) and the new columns, and add a warning that `no_usefulness_reason` must always be filtered on `reason_is_valid`, and that any nationality visual must be sliced by `instrument_version`.

- [ ] **Step 3: Run the full suite one final time**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all pass or skip; zero failures.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/powerbi_guide.md
git commit -m "docs(sami): v2 export and questionnaire-version guidance

Names the current export files and explains which variables cannot be
pooled across questionnaire versions, for whoever refreshes the data next."
```

---

## Verification checklist

Run at the end. Every item must pass before the branch is considered done.

- [ ] `.venv/Scripts/python.exe -m pytest tests/ -v` — zero failures
- [ ] `.venv/Scripts/python.exe run_pipeline.py --check` — all preflight checks pass
- [ ] `.venv/Scripts/python.exe run_pipeline.py --skip-nlp` — completes, PII scan clean
- [ ] `exports/parity_check.csv` — `match` True on every row
- [ ] `test_user_ids_match_the_pre_migration_exports` passes — no user was re-pseudonymized
- [ ] Reconciliation shows 1,392 users / 1,460 records / 115 MEAL responses
- [ ] NB1 and NB2 execute end to end via nbconvert
- [ ] `git grep -n "MMC_bot_responses\|MMC_MEAL"` returns only spec/plan documents
- [ ] NB3 is untouched and still on the old contract — expected; the NLP spec owns it
