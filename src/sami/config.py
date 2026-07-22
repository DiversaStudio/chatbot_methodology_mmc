"""Paths, constants, and salt loading for the SAMI pipeline."""
from __future__ import annotations
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _ROOT / "data_&_docs"
RESPONSES_PATH = DATA_DIR / "MMC_bot_responses_1783087815.xlsx"
MEAL_PATH = DATA_DIR / "MMC_MEAL_1783087939.xlsx"
DATA_HEADER_ROW = 2  # 0-indexed; real header is the 3rd row of the export


def _load_dotenv(path: Path = _ROOT / ".env") -> dict[str, str]:
    """Minimal KEY=VALUE parser so we need no python-dotenv dependency."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_DOTENV = _load_dotenv()


def get_salt() -> str:
    """Return SAMI_SALT from env or .env. Raise if absent — never fall back."""
    salt = os.environ.get("SAMI_SALT") or _DOTENV.get("SAMI_SALT")
    if not salt:
        raise RuntimeError(
            "SAMI_SALT is not set. Add it to .env (gitignored) or the environment. "
            "The pseudonymization salt must never live in the repo."
        )
    return salt
