"""Shared fixtures and the real-data skip marker.

Tests that assert exact counts run against the committed synthetic fixtures, so
they stay green on any export. Tests that need the real (gitignored) export are
marked `requires_real_data` and skip cleanly when it is absent -- which is the
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
