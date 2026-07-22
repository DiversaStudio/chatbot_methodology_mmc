"""The single entry point: run the whole cleaning pipeline once, return a bundle."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import pandas as pd

from . import config, load, qa


@dataclass(frozen=True)
class SamiData:
    responses: pd.DataFrame
    messages: pd.DataFrame
    meal: pd.DataFrame
    reconciliation: pd.DataFrame
    run_meta: dict


def load_sami(responses_path=None, meal_path=None) -> SamiData:
    responses_path = responses_path or config.RESPONSES_PATH
    meal_path = meal_path or config.MEAL_PATH
    salt = config.get_salt()

    schema_resp = qa.validate_schema(responses_path, kind="responses")
    schema_meal = qa.validate_schema(meal_path, kind="meal")

    responses = load.load_responses(responses_path, salt=salt)
    messages = load.load_messages(responses)
    meal = load.load_meal(meal_path, salt=salt)
    reconciliation = qa.reconciliation_table(responses, messages, meal)
    checks = qa.run_checks(responses, messages, meal)

    failed = [c for c in checks if not c[1] and c[0].startswith(("P1", "P6"))]
    if failed:
        raise RuntimeError(f"critical QA checks failed: {failed}")

    run_meta = {
        "responses_file": responses_path.name,
        "meal_file": meal_path.name,
        "responses_rows": schema_resp["rows"],
        "meal_rows": schema_meal["rows"],
        "ts_min": str(responses["ts"].min()),
        "ts_max": str(responses["ts"].max()),
        "salt_present": True,
        "checks": checks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return SamiData(responses, messages, meal, reconciliation, run_meta)
