"""Resolve a dataset role to the file this run should read.

The recipient's action is "save the new export into datasets/<role>/". Role is
declared by the folder, not by the filename, and the newest file wins -- so a
re-export under any name runs without anyone editing code.

Modification time is used rather than a manifest or a filename convention
because it is a property of the act of saving the file: there is no second step
that can be silently skipped. Older files may be left in place as an archive,
and every run prints which file it used (see `describe`), so the choice is
auditable after the fact.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .schema import SchemaError

_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = _ROOT / "datasets"
ROLES = ("responses", "meal")

_LOCK_PREFIX = "~$"  # Excel writes these while a workbook is open
_SUFFIX = ".xlsx"


class DatasetError(SchemaError):
    """No usable file for a dataset role. The message carries the fix.

    Subclasses SchemaError so run_pipeline.py's existing handler prints the
    message instead of a traceback.
    """


def folder(role: str) -> Path:
    """The drop folder for `role`. Raises DatasetError on an unknown role."""
    if role not in ROLES:
        raise DatasetError(
            f"Unknown dataset role {role!r}.\n"
            f"  fix:  Use one of: {', '.join(ROLES)}.")
    return DATASETS_DIR / role


def candidates(role: str) -> list[Path]:
    """Usable .xlsx files in the role folder, newest modification first.

    Excel lock files (~$*) and every non-.xlsx entry are skipped. Name is the
    tie-break so the result is deterministic when two files share an mtime.
    """
    directory = folder(role)
    if not directory.is_dir():
        return []
    found = [
        p for p in directory.iterdir()
        if p.is_file()
        and p.suffix.lower() == _SUFFIX
        and not p.name.startswith(_LOCK_PREFIX)
    ]
    return sorted(found, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def resolve(role: str) -> Path | None:
    """The file to use for `role`, or None when the folder holds none.

    Returns None rather than raising so preflight can report a clean FAIL and
    so importing this module never depends on the folder's contents.
    """
    found = candidates(role)
    return found[0] if found else None


def require(role: str) -> Path:
    """Like `resolve`, but raises DatasetError with the fix when absent."""
    path = resolve(role)
    if path is None:
        raise DatasetError(missing_message(role))
    return path


def missing_message(role: str) -> str:
    """Why the role is unresolved and exactly what to do about it."""
    directory = folder(role)
    # Display as "datasets/role" for the message
    display_path = f"datasets/{role}"
    return (
        f"No .xlsx found for the {role!r} dataset.\n"
        f"  looked in: {display_path}\n"
        f"  fix:  Save the {role} export into that folder. The filename does "
        f"not matter and the most recently modified .xlsx is used. "
        f"Alternatively pass an explicit path:\n"
        f"        python run_pipeline.py --{role} PATH.xlsx")


def describe(role: str) -> str:
    """One line naming the chosen file, its date, and what was passed over."""
    found = candidates(role)
    if not found:
        return f"no .xlsx in {folder(role)}"
    chosen = found[0]
    stamp = datetime.fromtimestamp(chosen.stat().st_mtime).strftime("%Y-%m-%d")
    line = f"{chosen} (modified {stamp}"
    others = len(found) - 1
    if others:
        line += f", {others} older file{'s' if others > 1 else ''} ignored"
    return line + ")"
