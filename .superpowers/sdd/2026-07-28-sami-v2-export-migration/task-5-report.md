# Task 5 Completion Report: Update `qa.py`'s copy of the contract

## Status: COMPLETE ✓

All tests pass. V2 and legacy v1 exports validate correctly.

## Changes Made

1. **Updated imports** in `src/sami/qa.py`:
   - Added `schema` to the imports: `from . import config, schema`

2. **Updated constants** in `src/sami/qa.py`:
   - `_SHEET` changed from a dict of strings to a dict of sets accepting both v1 and v2 sheet names:
     - `"responses"`: `{"users", "mmc bot - responses"}`
     - `"meal"`: `{"survey responses", "mmc-meal"}`
   - `_CRITICAL` remains unchanged (canonical column names post-normalization)

3. **Refactored `validate_schema()`** to share header detection and column normalization:
   - Sheet name comparison now case-insensitive and whitespace-stripped
   - Uses `schema.detect_header_row(path, source=kind)` for header detection
   - Uses `schema.normalize_columns(df, kind)` for column mapping
   - Catches both `ValueError` and `schema.SchemaError` exceptions
   - Maintains same return dict structure: `{"rows", "columns", "ts_parse_rate"}`

4. **Added tests** in `tests/test_qa.py`:
   - `test_validate_schema_accepts_v2_users_export()` — validates `users_v2.xlsx`
   - `test_validate_schema_accepts_v2_survey_export()` — validates `survey_v2.xlsx`

## Verification

### Test Suite Results
```
41 tests passed (test_qa.py, test_load_sami.py, test_schema.py)
No regressions detected.
```

### Real Data Validation
```
v2 responses:      1460 rows ✓
v2 survey:         142 rows ✓
v1 responses:      948 rows ✓ (legacy backwards compatible)
```

## Commit

```
Commit SHA: 1904e29
Message: fix(sami): v2 sheet names and header detection in qa.validate_schema
```

## Notes

- No circular imports detected (`schema.py` → `canon.py`, `qa.py` → `config`/`schema` clean)
- Test fixture row counts adjusted from brief (7/5 actual vs. 6/4 expected in step 1)
- Single-sheet fixture tolerance preserved for backwards compatibility
- Architecture unchanged; no restructuring performed

---

## Fix Round 1: SchemaError Propagation

### Critical Issue Fixed

**Problem:** The except clause caught both `ValueError` and `schema.SchemaError`, swallowing critical diagnostic information. When `detect_header_row` failed to find the header, it raised `SchemaError` with actionable details (file path, expected marker sets, actual rows scanned), but `validate_schema` caught it and fell through to raise a generic "missing critical columns" error. This was misleading for drifting platform exports where the header markers had changed.

**Solution:** Catch only `ValueError` (for short test fixtures), letting `SchemaError` propagate with its full diagnostic payload.

### Changes in Fix Round 1

1. **Updated except clause** in `src/sami/qa.py:66-71`:
   - Changed from: `except (ValueError, schema.SchemaError):`
   - Changed to: `except ValueError:`
   - Restores comment explaining fixture tolerance

2. **Expanded test coverage** in `tests/test_qa.py`:
   - `test_validate_schema_missing_critical_raises` now tests both paths:
     - File with no detectable header → `SchemaError` with path and "header row" in message
     - File with detectable header but missing columns → `ValueError` with column names
   - `test_validate_schema_sheet_name_case_insensitive`: Validates `.strip().lower()` logic
   - `test_validate_schema_single_sheet_escape_hatch`: Validates single-sheet fixture tolerance

### Verification Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
collected 43 items

tests/test_qa.py::test_pii_scan_flags_phone_and_whatsapp PASSED
tests/test_qa.py::test_pii_scan_clean_on_loaded_frames PASSED
tests/test_qa.py::test_pii_scan_catches_phone_in_numeric_heavy_frame PASSED
tests/test_qa.py::test_pii_scan_ignores_file_id_and_float_ratios PASSED
tests/test_qa.py::test_validate_schema_responses_ok PASSED
tests/test_qa.py::test_validate_schema_missing_critical_raises PASSED
tests/test_qa.py::test_reconciliation_table PASSED
tests/test_qa.py::test_validate_schema_accepts_v2_users_export PASSED
tests/test_qa.py::test_validate_schema_accepts_v2_survey_export PASSED
tests/test_qa.py::test_validate_schema_sheet_name_case_insensitive PASSED
tests/test_qa.py::test_validate_schema_single_sheet_escape_hatch PASSED
tests/test_load_sami.py::test_load_sami_returns_populated_bundle PASSED
tests/test_load_sami.py::test_load_sami_is_pii_free PASSED
tests/test_load_sami.py::test_load_sami_is_deterministic PASSED
tests/test_load_sami.py::test_load_sami_frozen PASSED
tests/test_schema.py tests (28 tests) PASSED
========================= 43 passed, 6 warnings in 14.24s ========================
```

### Real Data Validation

```
v2 responses: {'rows': 1460, 'columns': 39, 'ts_parse_rate': 1.0}
v2 survey: {'rows': 142, 'columns': 13, 'ts_parse_rate': 1.0}
v1 responses (legacy must still work): {'rows': 948, 'columns': 29, 'ts_parse_rate': 1.0}
```

All checks passed; no regressions.

### Commit Details (Fix Round 1)

```text
Commit SHA: f805c91
Message: fix(sami): qa.validate_schema must propagate SchemaError, not swallow it
```

