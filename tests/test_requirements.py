"""Every third-party package imported by src/ must be declared, not transitive.

`_imported_third_party_names()` AST-walks every module under `src/` and
collects top-level `import X` / `from X import ...` names, so this guards
future imports the way the docstring always claimed — a hand-maintained list
would only prove the imports known when it was last edited were declared.
"""
import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Import name -> distribution name, for the handful whose PyPI name differs
# from the name used in `import ...`.
_IMPORT_TO_DIST = {
    "sklearn": "scikit-learn",
    "umap": "umap-learn",
    "sentence_transformers": "sentence-transformers",
}

# Imported but deliberately not required in DIRECTLY_IMPORTED's sense:
# `torch` lives in the `cpu`/`gpu` dependency groups (mutually exclusive,
# chosen by CPU-vs-GPU install), which `_declared()` does read — so it
# WOULD pass if checked. It is excluded anyway because no single group is
# "the" declaration of it; asserting it here would just duplicate what
# `docs/OPERATIONS.md`'s install instructions already cover.
_EXEMPT = {"torch"}

# First-party: the package's own name, importable as `sami` once installed.
_FIRST_PARTY = {"sami"}


def _imported_third_party_names() -> set[str]:
    stdlib = sys.stdlib_module_names
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:  # level > 0 is a relative import
                    found.add(node.module.split(".")[0])
    return found - stdlib - _FIRST_PARTY - _EXEMPT


def _declared() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = {re.split(r"[<>=!~ \[]", d)[0].lower()
             for d in data["project"]["dependencies"]}
    for group in data.get("dependency-groups", {}).values():
        names |= {re.split(r"[<>=!~ \[]", d)[0].lower() for d in group}
    return names


def test_every_directly_imported_package_is_declared():
    imported = _imported_third_party_names()
    declared = _declared()
    missing = sorted(
        name for name in imported
        if _IMPORT_TO_DIST.get(name, name).lower() not in declared
    )
    assert not missing, f"imported but not declared in pyproject.toml: {missing}"


def test_requirements_txt_mirrors_pyproject_runtime_deps():
    """requirements.txt is the pip path; it must not drift from pyproject."""
    txt = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    listed = {re.split(r"[<>=!~ @\[]", line)[0].strip().lower()
              for line in txt.splitlines()
              if line.strip() and not line.startswith("#")}
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {re.split(r"[<>=!~ \[]", d)[0].strip().lower()
                for d in data["project"]["dependencies"]}
    # torch is deliberately absent from requirements.txt (CPU/GPU choice).
    assert declared - listed == set(), f"in pyproject but not requirements.txt: {declared - listed}"
