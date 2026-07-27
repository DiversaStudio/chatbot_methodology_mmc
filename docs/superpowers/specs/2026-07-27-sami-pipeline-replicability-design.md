# SAMI pipeline replicability — design

**Date:** 2026-07-27
**Status:** approved
**Scope:** `run_pipeline.py`, `src/sami/`, `pyproject.toml`, `README.md`

## Problem

The pipeline runs on the author's machine and nowhere else. Four defects make a
clean-machine run fail outright, not merely run slowly:

1. **Wrong data files.** `config.py` targets `MMC_bot_responses_1783087815.xlsx`
   / `MMC_MEAL_1783087939.xlsx`. `data_&_docs/` is gitignored, and the only two
   tracked files are the older, smaller `Base de datos … Sami_060526.xlsx` pair.
   A recipient gets `FileNotFoundError`.
2. **Unshippable salt.** `config.get_salt()` raises without `SAMI_SALT`, by
   design. A different salt yields different `user_id`s, so exports cannot match.
3. **GPU-only install.** `torch` is pinned to the cu128 index. `nlp._device()`
   falls back to CPU correctly, but `uv sync` itself pulls a ~3 GB CUDA wheel,
   and on Apple Silicon / ARM Linux no cu128 wheel exists, so install breaks
   before any code runs.
4. **Stale docs.** README references notebook filenames that no longer exist.

Two further hazards block the refresh use case:

5. **Positional MEAL columns.** `load.load_meal` picks the five survey columns by
   position (`cols[2]`…`cols[6]`). A new export with one inserted column silently
   mislabels every rating — wrong numbers, no error.
6. **Hardcoded header row.** `DATA_HEADER_ROW = 2` is a constant, not a detection.

And there is a live PII exposure: `data_&_docs/Base de datos respuestas
Sami_060526.xlsx` is committed to git with raw WhatsApp phone numbers in `Name`.

## Decisions

| Question | Decision |
|---|---|
| What must a recipient do? | Rebuild `exports/` identically, run the three notebooks, **and** refresh against a newer export |
| How does data reach them? | **Out-of-band.** Repo stays code-only; raw xlsx + `SAMI_SALT` travel through a secure channel. No silver layer, no synthetic fixture. |
| torch install | **CPU by default, GPU opt-in.** `uv sync` → plain PyPI CPU wheel; `uv sync --extra gpu` → cu128. |
| Guardrails | Preflight doctor check · actionable errors everywhere · progress and timings. **No** synthetic fixture / `--self-test`. |
| Notebooks | Fix docs and any CPU-unsafe code; **do not** execute-verify. |

## Design

### 1 · Install

`torch` becomes a plain CPU dependency; the cu128 build moves behind a `gpu`
extra. Default `uv sync` then works on Windows, Linux, and both Mac
architectures at ~200 MB. `python-preference = "only-system"` stays — that is
the Smart App Control workaround and is unrelated to device choice.

*Risk:* uv's per-extra index + `conflicts` pattern is unverified under
`tool.uv.package = false`. If extras do not resolve on a virtual project, fall
back to `[dependency-groups] gpu` + `uv sync --group gpu`. Same UX.

### 2 · `src/sami/preflight.py`

Independent named checks, each returning `(name, ok, detail, fix)` — never a
bare traceback. Runs at the start of every pipeline run, **before** any model
download; `run_pipeline.py --check` runs only the checks and exits.

Python version · required packages importable · `SAMI_SALT` resolvable · both
data files exist at the configured or CLI path · required columns present ·
`validation/tone_labels_analyst.csv` present · torch device, warning on CPU with
expected runtime · HF model cache present or network reachable, with download
size · free disk · output dir writable.

Hard failures exit non-zero. Warnings (CPU device, cold model cache) print and
continue.

### 3 · `src/sami/schema.py`

One declared contract per source. Responses columns are matched by exact name;
MEAL's five survey columns are matched by fold-normalized substring of the
Spanish question text (`"qué tan útil"`, `"recomendarías este servicio"`,
`"alguna recomendación para mejorar"`, `"cómo conociste"`, `"escribe el medio"`),
falling back to positional **only** with a warning naming each guess.

Header row is detected — scan the first rows for the one containing `Name` and
`Timestamp` — and on failure the error shows the rows actually found.

### 4 · `src/sami/progress.py`

A `stage()` context manager printing `[4/9] embedding 800 documents … 4m12s` to
stderr. No new dependency. Device banner up front, total at the end. Measured
CPU runtime goes in the README so nobody kills a run they believe has hung.

### 5 · Docs

README: corrected notebook filenames; a **Reproducing `exports/`** section
(out-of-band data + salt, CPU vs GPU install, measured runtimes, `--check`); a
**Refreshing with a new export** section documenting the schema contract and
what happens when it drifts.

### 6 · Repo hygiene

`git rm --cached` both stale, phone-number-bearing xlsx. They remain on disk and
are already gitignored. Purging them from git *history* requires `git
filter-repo` and a force-push that rewrites every clone — **flagged, not done.**

## Testing

Unit coverage for every preflight check (synthetic pass and fail), header-row
detection including the failure message, and name-based MEAL mapping including
the positional-fallback warning. No test downloads a model.

## Out of scope

Synthetic fixture / `--self-test`; executing the notebooks; CI; git history
rewrite.
