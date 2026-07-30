"""Every third-party package imported by src/ must be declared, not transitive."""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Import name -> distribution name, for the packages whose names differ.
DIRECTLY_IMPORTED = {
    "pandas": "pandas", "numpy": "numpy", "sklearn": "scikit-learn",
    "scipy": "scipy", "matplotlib": "matplotlib", "geopandas": "geopandas",
    "contextily": "contextily", "wordcloud": "wordcloud",
    "transformers": "transformers",
    "sentence_transformers": "sentence-transformers", "umap": "umap-learn",
}


def _declared() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = {re.split(r"[<>=!~ \[]", d)[0].lower()
             for d in data["project"]["dependencies"]}
    for group in data.get("dependency-groups", {}).values():
        names |= {re.split(r"[<>=!~ \[]", d)[0].lower() for d in group}
    return names


def test_every_directly_imported_package_is_declared():
    missing = sorted(dist for dist in DIRECTLY_IMPORTED.values()
                     if dist.lower() not in _declared())
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
