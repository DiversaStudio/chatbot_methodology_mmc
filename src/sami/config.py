"""Paths, constants, and salt loading for the SAMI pipeline."""
from __future__ import annotations
import os
from pathlib import Path

from . import datasets

_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = datasets.DATASETS_DIR

# 0-indexed; the real header is the 3rd row of the export. Kept for qa.py's
# fixture-tolerant reader. The loaders do NOT rely on it -- they call
# schema.detect_header_row(), so a re-export with a different number of banner
# rows still loads.
DATA_HEADER_ROW = 2


def responses_path() -> Path | None:
    """The responses export to use, or None if datasets/responses/ is empty.

    A function, not a constant: resolution depends on folder contents, which
    can change between import and use, and an empty folder must not raise at
    import time.
    """
    return datasets.resolve("responses")


def meal_path() -> Path | None:
    """The MEAL export to use, or None if datasets/meal/ is empty."""
    return datasets.resolve("meal")


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
