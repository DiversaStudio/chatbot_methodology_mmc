# SAMI Pipeline Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared `src/sami/` package (load, canon, taxonomy, theme, qa) with a single `load_sami() -> SamiData` facade so all three notebooks and the future headless pipeline compute from one deterministic, PII-safe, reconciling code path.

**Architecture:** Approach B — five faithful modules matching `requirements/02_notebook_requirements.md` §1, plus one facade that runs pseudonymize → clean → canon → message-spine → categorize → dedup → age-flag → reconcile exactly once and returns a frozen `SamiData` bundle. Notebooks/pipeline consume; modules compute. TDD throughout.

**Tech Stack:** Python ≥3.11, pandas ≥2.2, openpyxl (Excel), hashlib (sha256 pseudonymization), pytest ≥9.1. No new runtime dependencies (a tiny inline `.env` parser avoids adding `python-dotenv`).

## Global Constraints

- Package layout: `src/sami/` importable as `sami` via pytest `pythonpath = ["src"]`. **Do not** set `[tool.uv] package = true` — it stays `false` (uv sync wipes `src/` otherwise).
- Data files (canonical July export): `data_&_docs/MMC_bot_responses_1783087815.xlsx` (sheet `mmc bot - responses`, `header=2`), `data_&_docs/MMC_MEAL_1783087939.xlsx` (sheet `mmc-meal`, `header=2`). `data_&_docs/` is gitignored (PII) — never commit it.
- PII gate (P1): `user_id = sha256(SAMI_SALT + digits(Name))[:12]`; raw `Name`/phone dropped before any frame is returned; zero `whatsapp:` or 7+-digit runs in any `SamiData` frame. `SAMI_SALT` from gitignored `.env`; missing salt → raise, never silent fallback.
- 7 official categories (canonical, lowercase snake): `legal_documentation`, `humanitarian_assistance`, `protection`, `employment`, `organization_search`, `journey_information`, `services`, plus `unclassified`.
- Determinism: no randomness; fixed sort order; two `load_sami()` calls produce frame-equal outputs.
- Measured reconciliation targets from the July export (pin in tests; doc reference values in parentheses): records **946**, users **917** (doc ~918), messages **2993** (doc 2993), users-with-text **829** (doc ~800; differs because courtesy-filtering strictness varies — assert the value the code actually produces), MEAL rows **78** / unique users **69**, Age<18 flagged **36**.
- No `Co-Authored-By` trailer in commits.

---

### Task 1: Package scaffold, pytest wiring, config + salt

**Files:**
- Create: `src/sami/__init__.py`
- Create: `src/sami/config.py`
- Create: `tests/test_config.py`
- Modify: `pyproject.toml` (add `[tool.pytest.ini_options]`)
- Modify: `.gitignore` (add `.env`)
- Create: `.env` (gitignored, generated salt)

**Interfaces:**
- Produces: `sami.config.RESPONSES_PATH: Path`, `sami.config.MEAL_PATH: Path`, `sami.config.DATA_HEADER_ROW = 2`, `sami.config.get_salt() -> str` (raises `RuntimeError` if `SAMI_SALT` unset/empty).

- [ ] **Step 1: Add pytest config to `pyproject.toml`**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Add `.env` to `.gitignore`**

Add under the `# Python` section of `.gitignore`:

```
# Secrets (pseudonymization salt)
.env
```

- [ ] **Step 3: Generate the salt into `.env`**

Run (Bash tool):

```bash
cd "c:/Users/sedig/Desktop/DIVERSA/chatbot_methodology_mmc" && python -c "import secrets; print('SAMI_SALT=' + secrets.token_hex(16))" > .env && cat .env
```

Expected: `.env` contains one line `SAMI_SALT=<32 hex chars>`. Verify it is gitignored: `git status --porcelain .env` prints nothing.

- [ ] **Step 4: Write the failing test**

`tests/test_config.py`:

```python
import importlib
import pytest
from sami import config


def test_paths_point_to_july_export():
    assert config.RESPONSES_PATH.name == "MMC_bot_responses_1783087815.xlsx"
    assert config.MEAL_PATH.name == "MMC_MEAL_1783087939.xlsx"
    assert config.DATA_HEADER_ROW == 2


def test_get_salt_reads_env(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", "deadbeef")
    assert config.get_salt() == "deadbeef"


def test_get_salt_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SAMI_SALT", raising=False)
    monkeypatch.setattr(config, "_DOTENV", {}, raising=False)
    with pytest.raises(RuntimeError, match="SAMI_SALT"):
        config.get_salt()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'sami'`).

- [ ] **Step 6: Write `src/sami/__init__.py`**

```python
"""SAMI shared analysis package: one compute path for notebooks and pipeline."""
```

(The `load_sami`/`SamiData` re-exports are added in Task 8.)

- [ ] **Step 7: Write `src/sami/config.py`**

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore src/sami/__init__.py src/sami/config.py tests/test_config.py
git commit -m "feat(sami): package scaffold, pytest wiring, salt config"
```

---

### Task 2: `canon.py` — folding + city/nationality/duration canonicalization

**Files:**
- Create: `src/sami/canon.py`
- Create: `tests/test_canon.py`

**Interfaces:**
- Produces: `fold(s) -> str` (accent/case-insensitive key); `city_canon(name) -> str` (canonical city or `"Otra"`); `clean_city(raw_city, city_other) -> str` (`_other` fallback); `CITY_CANON: dict`, `NON_CITY: set`; `is_non_city(name) -> tuple[bool, str]` (excluded flag + reason).

- [ ] **Step 1: Write the failing test**

`tests/test_canon.py`:

```python
from sami import canon


def test_fold_strips_accents_and_case():
    assert canon.fold("Medellín") == "medellin"
    assert canon.fold("  BOGOTÁ ") == "bogota"


def test_city_canon_known_variants():
    assert canon.city_canon("medellin antioquia") == "Medellín"
    assert canon.city_canon("Bogota DC") == "Bogotá"
    assert canon.city_canon("cucuta") == "Cúcuta"


def test_city_canon_non_city_returns_otra():
    assert canon.city_canon("Colombia") == "Otra"
    assert canon.city_canon("Antioquia") == "Otra"
    assert canon.city_canon("12345") == "Otra"
    assert canon.city_canon(None) == "Otra"


def test_is_non_city_reports_reason():
    excluded, reason = canon.is_non_city("Colombia")
    assert excluded and "country/region" in reason
    excluded, reason = canon.is_non_city("Medellín")
    assert not excluded


def test_clean_city_uses_other_when_otra():
    assert canon.clean_city("Otra", "Envigado") == "Envigado"
    assert canon.clean_city("Medellín", None) == "Medellín"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_canon.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'sami.canon'`).

- [ ] **Step 3: Write `src/sami/canon.py`**

```python
"""Canonical dictionaries and mapping for city / nationality / duration."""
from __future__ import annotations
import unicodedata
import pandas as pd

# 10 MMC priority cities + common variants -> canonical display name
CITY_CANON: dict[str, str] = {
    "medellin": "Medellín", "medellin antioquia": "Medellín", "belen": "Medellín",
    "bogota": "Bogotá", "bogota dc": "Bogotá",
    "cucuta": "Cúcuta",
    "barranquilla": "Barranquilla",
    "santa marta": "Santa Marta",
    "cali": "Cali",
    "cartagena": "Cartagena",
    "bucaramanga": "Bucaramanga",
    "ipiales": "Ipiales",
    "riohacha": "Riohacha", "maicao": "Maicao",
    "soacha": "Soacha", "soacha cundinamarca": "Soacha",
    "necocli": "Necoclí",
}
# tokens that are regions/countries, not a priority city
NON_CITY: set[str] = {"colombia", "cundinamarca", "antioquia", "otra", "nan", ""}


def fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def is_non_city(name) -> tuple[bool, str]:
    """Return (excluded, reason). Reason is '' when it is a mappable city."""
    if name is None:
        return True, "missing"
    key = fold(name)
    if key == "" or key == "nan":
        return True, "missing"
    if key.isdigit():
        return True, "numeric token"
    if key in NON_CITY:
        return True, "country/region, not a city"
    return False, ""


def city_canon(name) -> str:
    excluded, _ = is_non_city(name)
    if excluded:
        return "Otra"
    key = fold(name)
    if key in CITY_CANON:
        return CITY_CANON[key]
    for k, v in CITY_CANON.items():  # startswith match for "<city> <tail>"
        if key.startswith(k):
            return v
    return "Otra"


def clean_city(raw_city, city_other) -> str:
    raw = ("" if raw_city is None else str(raw_city)).strip()
    other = "" if city_other is None or pd.isna(city_other) else str(city_other).strip()
    if raw == "Otra" and other:
        return other.title()
    return raw
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_canon.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sami/canon.py tests/test_canon.py
git commit -m "feat(sami): canon.py city/nationality folding + mapping"
```

---

### Task 3: `taxonomy.py` — category normalizer + institution/entity patterns

**Files:**
- Create: `src/sami/taxonomy.py`
- Create: `tests/test_taxonomy.py`

**Interfaces:**
- Produces: `OFFICIAL_CATEGORIES: list[str]` (the 7); `normalize_category(raw) -> str` (one of the 7 or `"unclassified"`); `ENTITY_PATTERNS: dict[str, list[str]]`; `extract_entities(text) -> set[str]`; `entity_counts(texts) -> pd.Series`.

- [ ] **Step 1: Write the failing test**

`tests/test_taxonomy.py`:

```python
from sami import taxonomy


def test_official_categories_are_seven():
    assert len(taxonomy.OFFICIAL_CATEGORIES) == 7
    assert "legal_documentation" in taxonomy.OFFICIAL_CATEGORIES


def test_normalize_category_variants():
    for raw in ["legal documentation", "#legal_documentation",
                "#legaldocumentation", "#legal documentation", "LEGAL DOCUMENTATION"]:
        assert taxonomy.normalize_category(raw) == "legal_documentation"
    assert taxonomy.normalize_category("#humanitarian_assistance") == "humanitarian_assistance"
    assert taxonomy.normalize_category("Protection") == "protection"


def test_normalize_category_prompt_leftover_is_unclassified():
    junk = ("Use exactly one of these hashtags in the column for each entry, "
            "based on the main topic of the migrants question:  #humanitarian_assistance")
    assert taxonomy.normalize_category(junk) == "unclassified"


def test_normalize_category_multilabel_is_unclassified():
    assert taxonomy.normalize_category("legal documentation, employment") == "unclassified"


def test_normalize_category_blank_is_unclassified():
    assert taxonomy.normalize_category("") == "unclassified"
    assert taxonomy.normalize_category(None) == "unclassified"


def test_extract_entities():
    ents = taxonomy.extract_entities("Necesito ayuda con mi PPT y la afiliación en salud EPS")
    assert "PPT" in ents and "EPS" in ents
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_taxonomy.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'sami.taxonomy'`).

- [ ] **Step 3: Write `src/sami/taxonomy.py`**

```python
"""Official MMC category taxonomy + dictionary extraction of institutions/procedures."""
from __future__ import annotations
from collections import Counter
from typing import Iterable
import re
import unicodedata
import pandas as pd

OFFICIAL_CATEGORIES: list[str] = [
    "legal_documentation",
    "humanitarian_assistance",
    "protection",
    "employment",
    "organization_search",
    "journey_information",
    "services",
]

# folded, separator-free aliases -> canonical category
_CATEGORY_ALIASES: dict[str, str] = {
    "legaldocumentation": "legal_documentation",
    "humanitarianassistance": "humanitarian_assistance",
    "protection": "protection",
    "employment": "employment",
    "organizationsearch": "organization_search",
    "journeyinformation": "journey_information",
    "services": "services",
}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def normalize_category(raw) -> str:
    """Map a raw Chat_summary value to one official category or 'unclassified'.

    Handles '#' hashtags, '_'/space separators, case; multi-label (comma) and
    the leftover prompt instruction row both resolve to 'unclassified'.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "unclassified"
    text = str(raw).strip()
    if text == "" or "," in text:  # blank or multi-label
        return "unclassified"
    if len(text) > 60:  # the prompt-leftover instruction row is long
        return "unclassified"
    key = _fold(text).lstrip("#").strip()
    key = re.sub(r"[\s_]+", "", key)  # drop spaces and underscores
    return _CATEGORY_ALIASES.get(key, "unclassified")


# ---- institutions / procedures dictionary ----
ENTITY_PATTERNS: dict[str, list[str]] = {
    "PPT": [r"\bppt\b", r"permiso por proteccion temporal"],
    "PEP": [r"\bpep\b", r"permiso especial de permanencia"],
    "Visa": [r"\bvisa\b", r"\bvisas\b"],
    "Cédula de extranjería": [r"cedula de extranjeria"],
    "Pasaporte": [r"\bpasaporte\b"],
    "EPS": [r"\beps\b", r"afiliacion en salud", r"seguro de salud"],
    "SISBÉN": [r"\bsisben\b"],
    "Migración Colombia": [r"migracion colombia", r"\bmigracion\b"],
    "ACNUR": [r"\bacnur\b", r"\bunhcr\b"],
    "Cancillería": [r"cancilleria"],
    "Registraduría": [r"registraduria"],
    "SENA": [r"\bsena\b"],
    "ICBF": [r"\bicbf\b"],
    "Refugio/Asilo": [r"\brefugio\b", r"\basilo\b", r"solicitante de refugio"],
    "Trabajo/Empleo": [r"\bempleo\b", r"\btrabajo\b", r"permiso de trabajo"],
    "Educación": [r"\beducacion\b", r"\bcolegio\b", r"\bestudios?\b", r"convalidacion"],
    "Vivienda/Arriendo": [r"\barriendo\b", r"\bvivienda\b", r"subsidio de arriendo"],
    "Ayuda humanitaria": [r"ayuda humanitaria", r"asistencia humanitaria"],
}
_COMPILED = {k: [re.compile(p) for p in pats] for k, pats in ENTITY_PATTERNS.items()}


def extract_entities(text: str) -> set[str]:
    t = _fold(text)
    return {name for name, pats in _COMPILED.items() if any(p.search(t) for p in pats)}


def entity_counts(texts: Iterable[str]) -> pd.Series:
    c: Counter = Counter()
    for t in texts:
        if t is None or (isinstance(t, float) and pd.isna(t)):
            continue
        for ent in extract_entities(t):
            c[ent] += 1
    return pd.Series(c, dtype="int64").sort_values(ascending=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_taxonomy.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sami/taxonomy.py tests/test_taxonomy.py
git commit -m "feat(sami): taxonomy.py category normalizer + entity dictionary"
```

---

### Task 4: `load.py` part 1 — pseudonymize + text helpers + responses loader

**Files:**
- Create: `src/sami/load.py`
- Create: `tests/test_load_responses.py`

**Interfaces:**
- Consumes: `sami.config`, `sami.canon`, `sami.taxonomy`.
- Produces: `pseudonymize(name, salt) -> str` (12-hex); `digits(s) -> str`; `split_messages(blob) -> list[str]`; `is_courtesy(text) -> bool`; `SPANISH_STOPWORDS: list[str]`; `load_responses(path=None, salt=None) -> pd.DataFrame` with columns incl. `user_id, ts, city_clean, city_canon, age_num, age_flag, n_questions, dominant_category` and **no** `Name`/phone column.

- [ ] **Step 1: Write the failing test**

`tests/test_load_responses.py`:

```python
import re
import pandas as pd
from sami import load, config

SALT = "test_salt"


def test_pseudonymize_is_stable_and_salted():
    a = load.pseudonymize("whatsapp:+573001188778", SALT)
    assert re.fullmatch(r"[0-9a-f]{12}", a)
    assert a == load.pseudonymize("whatsapp:+573001188778", SALT)  # stable
    assert a != load.pseudonymize("whatsapp:+573001188778", "other_salt")  # salted


def test_load_responses_has_no_raw_identifiers():
    df = load.load_responses(salt=SALT)
    assert "Name" not in df.columns
    assert not any(c.lower() in {"phone", "digits"} for c in df.columns)
    joined = " ".join(df.astype(str).fillna("").values.ravel())
    assert "whatsapp:" not in joined
    assert not re.search(r"\d{7,}", joined)


def test_load_responses_counts():
    df = load.load_responses(salt=SALT)
    assert len(df) == 946                      # records (whatsapp rows)
    assert df["user_id"].nunique() == 917      # users; doc reference ~918
    assert (df["age_num"] < 18).sum() == 36    # P9 sub-18 count


def test_age_flag_marks_sub18():
    df = load.load_responses(salt=SALT)
    sub = df[df["age_num"] < 18]
    assert (sub["age_flag"] == "unreliable_sub18").all()
    assert (df[df["age_num"] >= 18]["age_flag"] == "ok").all()


def test_dominant_category_in_official_set():
    df = load.load_responses(salt=SALT)
    from sami.taxonomy import OFFICIAL_CATEGORIES
    allowed = set(OFFICIAL_CATEGORIES) | {"unclassified"}
    assert set(df["dominant_category"]).issubset(allowed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_load_responses.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'sami.load'`).

- [ ] **Step 3: Write `src/sami/load.py` (part 1)**

```python
"""Loaders + cleaning + pseudonymization: the single source of truth for SAMI data."""
from __future__ import annotations
import hashlib
import re
import unicodedata
import pandas as pd

from . import config, canon, taxonomy

_NOISE = {"undefined", "?", ""}


def digits(s) -> str:
    return re.sub(r"\D", "", str(s))


def pseudonymize(name, salt: str) -> str:
    """sha256(salt + digits(name))[:12]. Deterministic, salted, non-reversible."""
    return hashlib.sha256((salt + digits(name)).encode("utf-8")).hexdigest()[:12]


# ---- text helpers (ported from mmc_text.py) ----
def split_messages(blob) -> list[str]:
    if not isinstance(blob, str):
        return []
    parts = [p.strip() for p in blob.split("\n")]
    return [p for p in parts if not _is_noise(p)]


def _is_noise(t: str) -> bool:
    t = t.strip()
    return len(t) < 3 or t.isdigit() or t.lower() in _NOISE


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


_BASE_STOP = (
    "a al algo algunas algunos ante antes como con contra cual cuando de del "
    "desde donde dos el ella ellas ellos en entre era es esa ese eso esta este "
    "esto ha hasta hay la las le les lo los mas me mi mis mucho muy nada ni no "
    "nos o os para pero poco por porque que quien se sin sobre soy su sus te "
    "tener tengo ti tu tus un una uno unos y ya yo".split()
)
_COURTESY_TOKENS = (
    "hola buenas buenos dias tardes noches gracias muchas mil bendiga bendiciones "
    "amen dios saludos hi hello ok okay bien vale adios chao hasta luego favor "
    "porfavor porfa disculpa disculpe perdon le".split()
)
SPANISH_STOPWORDS = sorted(set(_BASE_STOP) | set(_COURTESY_TOKENS))


def is_courtesy(text: str) -> bool:
    words = re.findall(r"[a-zñ]+", _fold(text))
    if not words:
        return True
    return all(w in _COURTESY_TOKENS for w in words)


# ---- responses loader ----
def _read_whatsapp(path) -> pd.DataFrame:
    df = pd.read_excel(path, header=config.DATA_HEADER_ROW)
    df = df[df["Name"].astype(str).str.startswith("whatsapp")].copy()
    df.reset_index(drop=True, inplace=True)
    return df


def load_responses(path=None, salt=None) -> pd.DataFrame:
    path = path or config.RESPONSES_PATH
    salt = salt if salt is not None else config.get_salt()
    df = _read_whatsapp(path)
    df["user_id"] = df["Name"].map(lambda n: pseudonymize(n, salt))
    df = df.drop(columns=[c for c in ["Name"] if c in df.columns])
    df["city_clean"] = [canon.clean_city(c, o) for c, o in zip(df["City"], df.get("City_other", pd.Series([None] * len(df))))]
    df["city_canon"] = df["city_clean"].map(canon.city_canon)
    df["age_num"] = pd.to_numeric(df["Age"], errors="coerce")
    df["age_flag"] = df["age_num"].map(lambda a: "unreliable_sub18" if pd.notna(a) and a < 18 else "ok")
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    df["n_questions"] = pd.to_numeric(df.get("Questions per user"), errors="coerce")
    df["dominant_category"] = df["Chat_summary"].map(taxonomy.normalize_category)
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_load_responses.py -v`
Expected: 5 passed. If `test_load_responses_counts` shows different numbers, update the asserted constants to the produced values **and** note the delta in the commit message (the export is the source of truth).

- [ ] **Step 5: Commit**

```bash
git add src/sami/load.py tests/test_load_responses.py
git commit -m "feat(sami): load.py pseudonymize + responses loader with age flag + category"
```

---

### Task 5: `load.py` part 2 — message spine (P6)

**Files:**
- Modify: `src/sami/load.py` (add `load_messages`)
- Create: `tests/test_message_spine.py`

**Interfaces:**
- Produces: `load_messages(responses_df) -> pd.DataFrame` with columns `user_id, ts, message, seq, n_msgs_user` and carried `city_canon, dominant_category`.

- [ ] **Step 1: Write the failing test**

`tests/test_message_spine.py`:

```python
import pandas as pd
from sami import load

SALT = "test_salt"


def test_spine_count_and_invariant():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    assert len(msgs) == 2993  # doc target
    # P6: sum of per-user message counts == number of message rows
    per_user = msgs.groupby("user_id")["n_msgs_user"].first().sum()
    assert per_user == len(msgs)


def test_spine_no_noise_rows():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    assert (msgs["message"].str.strip().str.len() >= 3).all()
    assert not msgs["message"].str.fullmatch(r"\d+").any()


def test_spine_seq_is_zero_based_per_user():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    first = msgs.sort_values(["user_id", "seq"]).groupby("user_id")["seq"].first()
    assert (first == 0).all()


def test_users_with_text():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    assert msgs["user_id"].nunique() == 829  # measured; doc reference ~800
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_message_spine.py -v`
Expected: FAIL (`AttributeError: module 'sami.load' has no attribute 'load_messages'`).

- [ ] **Step 3: Add `load_messages` to `src/sami/load.py`**

Append:

```python
def load_messages(responses_df: pd.DataFrame) -> pd.DataFrame:
    """Explode per-user `Messages` blob into one row per message (the spine)."""
    carry = [c for c in ["user_id", "ts", "city_canon", "dominant_category",
                         "Gender", "Age Ranges", "Nationality", "age_num"]
             if c in responses_df.columns]
    rows = []
    for _, r in responses_df.iterrows():
        parts = split_messages(r.get("Messages"))
        for i, p in enumerate(parts):
            row = {c: r[c] for c in carry}
            row["seq"] = i
            row["n_msgs_user"] = len(parts)
            row["message"] = p
            rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_message_spine.py -v`
Expected: 4 passed. If a count differs, update the constant to the produced value and note it in the commit.

- [ ] **Step 5: Commit**

```bash
git add src/sami/load.py tests/test_message_spine.py
git commit -m "feat(sami): message spine loader (P6) with per-user invariant"
```

---

### Task 6: `load.py` part 3 — MEAL loader + dedup (P8)

**Files:**
- Modify: `src/sami/load.py` (add `load_meal`)
- Create: `tests/test_load_meal.py`

**Interfaces:**
- Produces: `load_meal(path=None, salt=None) -> pd.DataFrame` with columns `user_id, ts, usefulness_rating, would_recommend, recommendation_text, discovery_channel, discovery_other`, one row per `user_id` (most recent kept), no `Name`.

- [ ] **Step 1: Write the failing test**

`tests/test_load_meal.py`:

```python
import re
import pandas as pd
from sami import load

SALT = "test_salt"


def test_meal_columns_renamed():
    df = load.load_meal(salt=SALT)
    for col in ["user_id", "usefulness_rating", "would_recommend",
                "recommendation_text", "discovery_channel", "discovery_other"]:
        assert col in df.columns
    assert "Name" not in df.columns


def test_meal_dedup_one_row_per_user():
    df = load.load_meal(salt=SALT)
    assert df["user_id"].is_unique
    assert len(df) == 69  # unique MEAL users; 78 raw rows


def test_meal_keeps_most_recent():
    df = load.load_meal(salt=SALT)
    # after dedup, no user should appear twice
    assert df.groupby("user_id").size().max() == 1


def test_meal_no_raw_identifiers():
    df = load.load_meal(salt=SALT)
    joined = " ".join(df.astype(str).fillna("").values.ravel())
    assert "whatsapp:" not in joined and not re.search(r"\d{7,}", joined)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_load_meal.py -v`
Expected: FAIL (`AttributeError: ... 'load_meal'`).

- [ ] **Step 3: Add `load_meal` to `src/sami/load.py`**

Append:

```python
def load_meal(path=None, salt=None) -> pd.DataFrame:
    path = path or config.MEAL_PATH
    salt = salt if salt is not None else config.get_salt()
    df = _read_whatsapp(path)
    df["user_id"] = df["Name"].map(lambda n: pseudonymize(n, salt))
    df["ts"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    cols = list(df.columns)
    rename = {                    # positional: the 5 survey question columns
        cols[2]: "usefulness_rating",
        cols[3]: "would_recommend",
        cols[4]: "recommendation_text",
        cols[5]: "discovery_channel",
        cols[6]: "discovery_other",
    }
    df = df.rename(columns=rename)
    keep = ["user_id", "ts", "usefulness_rating", "would_recommend",
            "recommendation_text", "discovery_channel", "discovery_other"]
    df = df[[c for c in keep if c in df.columns]].copy()
    # P8: keep most recent response per user
    df = df.sort_values("ts").drop_duplicates("user_id", keep="last").reset_index(drop=True)
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_load_meal.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sami/load.py tests/test_load_meal.py
git commit -m "feat(sami): MEAL loader with per-user dedup (P8)"
```

---

### Task 7: `qa.py` — schema validation, PII scan, reconciliation, P-checks

**Files:**
- Create: `src/sami/qa.py`
- Create: `tests/test_qa.py`

**Interfaces:**
- Consumes: `sami.taxonomy`.
- Produces: `pii_scan(obj) -> list[dict]` (violations; empty = clean; accepts a DataFrame or a file Path); `validate_schema(path, kind) -> dict` (`kind` in {"responses","meal"}; raises on missing critical column); `reconciliation_table(responses, messages, meal) -> pd.DataFrame` with columns `metric, value` and `pending` for NB3-derived rows; `run_checks(responses, messages, meal) -> list[tuple[str, bool, str]]`.

- [ ] **Step 1: Write the failing test**

`tests/test_qa.py`:

```python
import pandas as pd
import pytest
from sami import qa, load

SALT = "test_salt"


def test_pii_scan_flags_phone_and_whatsapp():
    bad = pd.DataFrame({"x": ["whatsapp:+573001188778", "hola"]})
    violations = qa.pii_scan(bad)
    assert len(violations) >= 1


def test_pii_scan_clean_on_loaded_frames():
    resp = load.load_responses(salt=SALT)
    assert qa.pii_scan(resp) == []


def test_validate_schema_responses_ok():
    info = qa.validate_schema(load.config.RESPONSES_PATH, kind="responses")
    assert info["rows"] > 0
    assert info["ts_parse_rate"] == 1.0


def test_validate_schema_missing_critical_raises(tmp_path):
    p = tmp_path / "bad.xlsx"
    pd.DataFrame({"Foo": [1]}).to_excel(p, index=False)
    with pytest.raises(ValueError, match="critical"):
        qa.validate_schema(p, kind="responses")


def test_reconciliation_table():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    meal = load.load_meal(salt=SALT)
    table = qa.reconciliation_table(resp, msgs, meal)
    d = dict(zip(table["metric"], table["value"]))
    assert d["users"] == 917
    assert d["records"] == 946
    assert d["messages"] == 2993
    assert d["meal_responses"] == 69
    assert d["negative_tone_pct"] == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_qa.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'sami.qa'`).

- [ ] **Step 3: Write `src/sami/qa.py`**

```python
"""Validation, PII scanning, and the reconciliation table (doc 01 §7)."""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

from . import config, taxonomy

_PII_PATTERNS = [re.compile(r"whatsapp:", re.I), re.compile(r"\d{7,}")]

_CRITICAL = {
    "responses": ["Name", "Timestamp", "City", "Age", "Messages", "Chat_summary"],
    "meal": ["Name", "Timestamp"],
}
_SHEET = {"responses": "mmc bot - responses", "meal": "mmc-meal"}


def pii_scan(obj) -> list[dict]:
    """Return violation records for whatsapp:/7+-digit runs. Empty list = clean."""
    if isinstance(obj, (str, Path)):
        df = pd.read_excel(obj, header=config.DATA_HEADER_ROW, dtype=str)
    else:
        df = obj
    violations = []
    for col in df.columns:
        for val in df[col].astype(str).fillna(""):
            if any(p.search(val) for p in _PII_PATTERNS):
                violations.append({"column": str(col), "value_prefix": val[:12]})
                break  # one hit per column is enough to flag
    return violations


def validate_schema(path, kind: str) -> dict:
    xl = pd.ExcelFile(path)
    if _SHEET[kind] not in xl.sheet_names:
        # tolerate single-sheet test fixtures; only enforce for real exports
        if len(xl.sheet_names) != 1:
            raise ValueError(f"expected sheet {_SHEET[kind]!r}, got {xl.sheet_names}")
    df = pd.read_excel(path, header=config.DATA_HEADER_ROW)
    missing = [c for c in _CRITICAL[kind] if c not in df.columns]
    if missing:
        raise ValueError(f"missing critical columns for {kind}: {missing}")
    ts = df["Timestamp"] if "Timestamp" in df.columns else pd.Series(dtype=object)
    non_null = ts.notna().sum()
    parsed = pd.to_datetime(ts, errors="coerce", utc=True).notna().sum()
    rate = 1.0 if non_null == 0 else parsed / non_null
    return {"rows": len(df), "columns": len(df.columns), "ts_parse_rate": float(rate)}


def reconciliation_table(responses: pd.DataFrame, messages: pd.DataFrame,
                         meal: pd.DataFrame) -> pd.DataFrame:
    n_users = responses["user_id"].nunique()
    n_msgs = len(messages)
    legal = (messages["dominant_category"] == "legal_documentation").mean() if "dominant_category" in messages else float("nan")
    # repeat-asker proxy: users at/above p90 question volume
    q = responses.groupby("user_id")["n_questions"].max()
    p90 = q.quantile(0.90)
    repeat_pct = round(100 * (q >= p90).mean(), 1) if q.notna().any() else "pending"
    rows = [
        ("users", n_users),
        ("records", len(responses)),
        ("messages", n_msgs),
        ("users_with_text", messages["user_id"].nunique()),
        ("meal_responses", len(meal)),
        ("meal_response_rate_pct", round(100 * len(meal) / n_users, 1)),
        ("legal_documentation_pct", round(100 * legal, 1)),
        ("repeat_askers_pct", repeat_pct),
        ("negative_tone_pct", "pending"),  # from NB3 sentiment
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def run_checks(responses, messages, meal) -> list[tuple[str, bool, str]]:
    checks = []
    checks.append(("P1_pii_responses", pii_scan(responses) == [], "no whatsapp/phone in responses"))
    checks.append(("P1_pii_messages", pii_scan(messages) == [], "no whatsapp/phone in messages"))
    per_user = messages.groupby("user_id")["n_msgs_user"].first().sum()
    checks.append(("P6_spine_invariant", per_user == len(messages), f"{per_user} == {len(messages)}"))
    checks.append(("P8_meal_unique", meal["user_id"].is_unique, "one MEAL row per user"))
    unclass = (responses["dominant_category"] == "unclassified").mean()
    checks.append(("P7_unclassified_share", unclass < 0.10, f"{unclass:.1%} unclassified"))
    return checks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_qa.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sami/qa.py tests/test_qa.py
git commit -m "feat(sami): qa.py schema validation, PII scan, reconciliation, checks"
```

---

### Task 8: `SamiData` facade — `load_sami()`

**Files:**
- Modify: `src/sami/__init__.py`
- Create: `src/sami/facade.py`
- Create: `tests/test_load_sami.py`

**Interfaces:**
- Consumes: `sami.load`, `sami.qa`, `sami.config`.
- Produces: `SamiData` (frozen dataclass: `responses, messages, meal, reconciliation, run_meta`); `load_sami(responses_path=None, meal_path=None) -> SamiData`. Both re-exported from `sami`.

- [ ] **Step 1: Write the failing test**

`tests/test_load_sami.py`:

```python
import pandas as pd
from sami import load_sami, SamiData
from sami import qa

SALT = "test_salt"  # facade reads config.get_salt(); ensure .env or env has SAMI_SALT


def test_load_sami_returns_populated_bundle(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    assert isinstance(d, SamiData)
    assert len(d.responses) == 946
    assert d.responses["user_id"].nunique() == 917
    assert len(d.messages) == 2993
    assert d.meal["user_id"].is_unique
    assert not d.reconciliation.empty
    assert d.run_meta["salt_present"] is True


def test_load_sami_is_pii_free(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    assert qa.pii_scan(d.responses) == []
    assert qa.pii_scan(d.messages) == []
    assert qa.pii_scan(d.meal) == []


def test_load_sami_is_deterministic(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    a = load_sami()
    b = load_sami()
    pd.testing.assert_frame_equal(a.responses, b.responses)
    pd.testing.assert_frame_equal(a.messages, b.messages)


def test_load_sami_frozen(monkeypatch):
    monkeypatch.setenv("SAMI_SALT", SALT)
    d = load_sami()
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.responses = None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_load_sami.py -v`
Expected: FAIL (`ImportError: cannot import name 'load_sami' from 'sami'`).

- [ ] **Step 3: Write `src/sami/facade.py`**

```python
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
```

- [ ] **Step 4: Wire re-exports in `src/sami/__init__.py`**

Replace the file contents with:

```python
"""SAMI shared analysis package: one compute path for notebooks and pipeline."""
from .facade import SamiData, load_sami

__all__ = ["SamiData", "load_sami"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_load_sami.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/sami/__init__.py src/sami/facade.py tests/test_load_sami.py
git commit -m "feat(sami): load_sami() facade returning frozen SamiData bundle"
```

---

### Task 9: `theme.py` — palette + templates port

**Files:**
- Create: `src/sami/theme.py`
- Create: `tests/test_theme.py`

**Interfaces:**
- Produces: whatever `src/palette.py` currently exports, re-homed under `sami.theme` (palette constants, any `apply_theme`/template setters, EN display maps).

- [ ] **Step 1: Read the current palette to port it faithfully**

Run: `cat src/palette.py` (Read tool). Port its public names verbatim into `src/sami/theme.py` — do not redesign the palette here (that is a notebook-spec concern). Keep the same constant names so notebooks can switch `import palette` → `from sami import theme as palette` with no other change.

- [ ] **Step 2: Write the failing test**

`tests/test_theme.py` (adjust asserted names to the actual palette exports found in Step 1):

```python
from sami import theme


def test_theme_exposes_palette():
    # palette.py defines brand color constants; at least one categorical list exists
    public = [n for n in dir(theme) if not n.startswith("_")]
    assert public, "theme should expose palette constants"
    # spot-check: a hex color is present somewhere in the module's public values
    values = [getattr(theme, n) for n in public]
    flat = []
    for v in values:
        flat.extend(v if isinstance(v, (list, tuple)) else [v])
    assert any(isinstance(x, str) and x.startswith("#") for x in flat)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_theme.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'sami.theme'`).

- [ ] **Step 4: Create `src/sami/theme.py`**

Paste the ported contents of `src/palette.py` (from Step 1), keeping every public name identical. Add a module docstring: `"""Brand palette, plotly/mpl templates and EN display maps (ported from palette.py)."""`.

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_theme.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/sami/theme.py tests/test_theme.py
git commit -m "feat(sami): theme.py palette/templates ported from palette.py"
```

---

### Task 10: Remove old modules + old tests; full-suite green

**Files:**
- Delete: `src/mmc_data.py`, `src/mmc_entities.py`, `src/mmc_text.py`, `src/palette.py`
- Delete: `tests/test_mmc_data.py`, `tests/test_mmc_entities.py`, `tests/test_mmc_text.py`, `tests/test_city_canon.py`, `tests/test_courtesy.py`, `tests/test_load_messages.py`, `tests/test_emotion.py`

**Interfaces:**
- Consumes: nothing new. Produces: a clean `src/sami/`-only package.

- [ ] **Step 1: Confirm nothing in `src/` imports the old modules**

Run (Grep tool): search `import mmc_|from mmc_|import palette|from palette` under `src/sami/`.
Expected: zero matches. (Notebooks still import them — that is expected and out of scope; they break until their own specs.)

- [ ] **Step 2: Check `mmc_text.py` for NLP helpers to preserve**

Run: Read `src/mmc_text.py`. The emotion pipeline (`load_emotion_pipeline`) and reformulation-similarity functions (`max_consecutive_similarity`, `count_reformulations`) belong to NB3, not the foundation. Copy these three functions into a new file `docs/superpowers/deferred/nb3_text_helpers.py` (create the dir) with a header comment `# Deferred from mmc_text.py for the NB3 spec — do not import yet.` so they are not lost when the module is deleted.

- [ ] **Step 3: Delete the old modules and old tests**

```bash
cd "c:/Users/sedig/Desktop/DIVERSA/chatbot_methodology_mmc"
git rm src/mmc_data.py src/mmc_entities.py src/mmc_text.py src/palette.py
git rm tests/test_mmc_data.py tests/test_mmc_entities.py tests/test_mmc_text.py tests/test_city_canon.py tests/test_courtesy.py tests/test_load_messages.py tests/test_emotion.py
```

- [ ] **Step 4: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass (test_config, test_canon, test_taxonomy, test_load_responses, test_message_spine, test_load_meal, test_qa, test_load_sami, test_theme). No collection errors from deleted modules.

- [ ] **Step 5: Manual smoke check of the facade**

Run:

```bash
cd "c:/Users/sedig/Desktop/DIVERSA/chatbot_methodology_mmc" && ./.venv/Scripts/python.exe -c "from sami import load_sami; d = load_sami(); print(d.reconciliation.to_string(index=False)); print('PII-free:', all(len(__import__('sami').qa.pii_scan(f))==0 for f in [d.responses,d.messages,d.meal]))"
```

Expected: reconciliation table prints (users 917, records 946, messages 2993, negative_tone_pct pending); `PII-free: True`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(sami): remove old mmc_* modules and tests; foundation complete"
```

---

## Self-Review

**Spec coverage:**
- §3 module layout → Tasks 1,2,3,4,7,9 (config/canon/taxonomy/load/qa/theme). ✓
- §3.1 facade / SamiData → Task 8. ✓
- §3.2 processing order → Task 8 `load_sami` sequence. ✓
- §4 pseudonymization + PII gate (P1) → Task 1 (salt), Task 4 (`pseudonymize`, drop Name), Task 7 (`pii_scan`). ✓
- §5 schema validation + reconciliation + P-checks → Task 7. ✓
- §6 exhaustive tests P1/P3/P4/P5/P6/P7/P8/P9 → Tasks 2–8 test files. ✓
- §7 deliverables (delete old modules, `.env`, gitignore) → Tasks 1,10. ✓
- §9 acceptance criteria → Task 8 + Task 10 smoke. ✓

**Placeholder scan:** No TBD/TODO. `theme.py` (Task 9) intentionally ports live `palette.py` contents read at Step 1 rather than hard-coding an unknown palette — the test asserts structure, not specific values. Reconciliation constants are measured (946/917/2993/69/36), not placeholders, with an explicit "update to produced value if the export differs" instruction.

**Type consistency:** `user_id` (12-hex str), `SamiData` field names (`responses/messages/meal/reconciliation/run_meta`), `reconciliation` columns (`metric/value`), and `run_checks` tuple shape `(name, bool, detail)` are used identically across Tasks 4–10. `load_responses(salt=)`, `load_messages(responses_df)`, `load_meal(salt=)` signatures match their call sites in Task 8.

**P3 coercion note:** covered implicitly by `age_num`/`n_questions`/`ts` coercion tests in Task 4 and `ts_parse_rate == 1.0` in Task 7; no separate task needed.
