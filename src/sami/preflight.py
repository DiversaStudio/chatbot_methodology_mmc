"""Preflight checks: fail before the work, not twenty minutes into it.

Every check is independent, named, and returns a `Result` carrying *what* is
wrong and *how to fix it* — never a bare traceback. `run_all` is called at the
start of every pipeline run (before any model download) and standalone by
`run_pipeline.py --check`.

Adding a check: write a `check_*(ctx) -> Result` function and list it in CHECKS.
Checks must not mutate anything and must not raise — an unexpected exception
inside one is reported as that check failing, so a broken check can never take
down the run it was meant to protect.
"""
from __future__ import annotations

import importlib.util  # not implied by `import importlib`; find_spec needs it
import os
import shutil
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import config, datasets, schema

OK, WARN, FAIL = "ok", "warn", "fail"

# Rough disk needed for the Hugging Face model cache (e5-large ~2.2 GB +
# xlm-roberta sentiment ~1.1 GB) plus room for the exports.
MODEL_CACHE_GB = 4.0
# Measured end-to-end on this project's data (917 users / 800 documents /
# 2991 messages), model cache warm. Quoted in the CPU warning so a slow run
# reads as expected rather than as a hang.
CPU_RUNTIME_HINT = "a full run took 5m22s on CPU vs 2m11s on an RTX 3050 Ti"

_REQUIRED_PACKAGES = ("pandas", "numpy", "sklearn", "openpyxl")
_NLP_PACKAGES = ("torch", "transformers", "sentence_transformers", "umap")


@dataclass
class Result:
    name: str
    status: str
    detail: str
    fix: str = ""

    @property
    def failed(self) -> bool:
        return self.status == FAIL


@dataclass
class Context:
    """What the run is about to do. Paths are the effective ones (CLI, or
    resolved from datasets/). None means nothing was dropped into the folder."""
    responses_path: Path | None = field(
        default_factory=lambda: datasets.resolve("responses"))
    meal_path: Path | None = field(
        default_factory=lambda: datasets.resolve("meal"))
    out_dir: Path = field(default_factory=lambda: Path("exports"))


# ---- individual checks --------------------------------------------------------
def check_python(ctx: Context) -> Result:
    v = sys.version_info
    if v >= (3, 11):
        return Result("python", OK, f"{v.major}.{v.minor}.{v.micro}")
    return Result("python", FAIL, f"{v.major}.{v.minor} is too old (need >= 3.11)",
                  "Install Python 3.11+ and recreate the environment: uv sync")


def check_packages(ctx: Context) -> Result:
    needed = list(_REQUIRED_PACKAGES) + list(_NLP_PACKAGES)
    missing = [m for m in needed if importlib.util.find_spec(m) is None]
    if not missing:
        return Result("packages", OK, f"{len(needed)} required packages present")
    return Result("packages", FAIL, f"missing: {', '.join(missing)}",
                  "uv sync   (add --no-group cpu --group gpu on an NVIDIA machine)")


def check_salt(ctx: Context) -> Result:
    try:
        config.get_salt()
    except RuntimeError as exc:
        return Result("salt", FAIL, str(exc).split(".")[0],
                      "The pseudonymization salt is never committed. Obtain it "
                      "out-of-band and put SAMI_SALT=... in a .env file at the "
                      "repo root (gitignored), or set it in the environment.\n"
                      "        Note: a DIFFERENT salt yields different user_id "
                      "hashes, so exports will not match the committed ones.")
    return Result("salt", OK, "SAMI_SALT resolved")


def _check_export(path: Path | None, source: str, required) -> Result:
    if path is None:
        # missing_message() is "<why>\n  looked in: <dir>\n  fix:  <text>\n
        # <continuation>". `detail` below already states the directory, so
        # drop the "looked in:" line too, and strip the embedded "fix:" label
        # since `render()` adds its own.
        fix_lines = datasets.missing_message(source).splitlines()[2:]
        fix_lines[0] = fix_lines[0].split("fix:", 1)[1].strip()
        return Result(source, FAIL, f"no .xlsx in {datasets.folder(source)}",
                      "\n        ".join(fix_lines))
    if not path.exists():
        return Result(source, FAIL, f"not found: {path}",
                      "Save the export into datasets/%s/ (the filename does "
                      "not matter; the newest .xlsx is used), or pass an "
                      "explicit path:\n"
                      "        python run_pipeline.py --%s PATH" % (source, source))
    try:
        import pandas as pd
        # Header detection and column normalization must match what the loaders
        # do (load._read_export), or preflight reports a healthy export as
        # broken: the v2 platform renamed the key columns, so `required` is
        # stated in canonical names that only exist after normalize_columns.
        header = schema.detect_header_row(path, source=source)
        frame = pd.read_excel(path, header=header, nrows=5)
        frame = schema.normalize_columns(frame, source)
        schema.require_columns(frame, required, path, source)
    except schema.SchemaError as exc:
        return Result(source, FAIL, str(exc).splitlines()[0],
                      "\n        ".join(str(exc).splitlines()[1:]))
    except Exception as exc:  # unreadable file, wrong format, permissions
        return Result(source, FAIL, f"could not read {path}: {exc}",
                      "Confirm the file is a readable .xlsx platform export.")
    return Result(source, OK, f"{path.name} (header row {header})")


def check_responses(ctx: Context) -> Result:
    return _check_export(ctx.responses_path, "responses", schema.RESPONSES_REQUIRED)


def check_meal(ctx: Context) -> Result:
    return _check_export(ctx.meal_path, "meal", schema.MEAL_REQUIRED)


def check_tone_labels(ctx: Context) -> Result:
    path = Path("validation/tone_labels_analyst.csv")
    if path.exists():
        return Result("tone labels", OK, str(path))
    return Result("tone labels", FAIL, f"not found: {path}",
                  "A full run reads this file to build the nlp_tone_confusion "
                  "table. Restore the file.")


def check_entities(ctx: Context) -> Result:
    """The institutions/procedures registry parses and validates.

    Cheap and early: a mangled registry otherwise surfaces as a chart that
    quietly counts nothing, twenty minutes into a run.
    """
    from . import taxonomy
    path = config.entities_path()
    try:
        rows = taxonomy.load_entity_registry()
    except taxonomy.EntityRegistryError as exc:
        first, *rest = str(exc).splitlines()
        return Result("entities", FAIL, first,
                      "\n        ".join(x.strip() for x in rest) or
                      f"Fix {path} and re-run --check.")
    counted = [r for r in rows if r["kind"] in taxonomy.COUNTED_KINDS]
    n_entities = len({r["entity"] for r in counted})
    return Result("entities", OK,
                  f"{n_entities} entities, {len(counted)} patterns "
                  f"({path.name})")


def check_device(ctx: Context) -> Result:
    try:
        import torch

        from . import nlp
    except Exception as exc:
        return Result("device", FAIL, f"torch not importable: {exc}", "uv sync")
    if nlp.cuda_usable():
        return Result("device", OK, f"CUDA — {nlp.gpu_name()}")
    return Result("device", WARN, f"CPU only (torch {torch.__version__})",
                  f"The run will work but is slower — {CPU_RUNTIME_HINT}. "
                  "On an NVIDIA machine, install the CUDA build:\n"
                  "        uv sync --no-group cpu --group gpu")


def _hf_cache_dir() -> Path:
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _network_ok(host: str = "huggingface.co", port: int = 443, timeout: float = 4.0) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def check_models(ctx: Context) -> Result:
    """Models must be either already cached or downloadable — this is the check
    that saves someone from a 20-minute run that dies at the download step."""
    from . import nlp
    cache = _hf_cache_dir()
    wanted = {
        nlp.EMBED_MODEL: "models--" + nlp.EMBED_MODEL.replace("/", "--"),
        nlp.SENTIMENT_MODEL: "models--" + nlp.SENTIMENT_MODEL.replace("/", "--"),
        nlp.EMOTION_MODEL: "models--" + nlp.EMOTION_MODEL.replace("/", "--"),
    }
    absent = [name for name, d in wanted.items() if not (cache / d).exists()]
    if not absent:
        return Result("models", OK, f"all {len(wanted)} models cached in {cache}")
    if _network_ok():
        return Result("models", WARN,
                      f"{len(absent)} model(s) not cached — will download "
                      f"(~{MODEL_CACHE_GB:.0f} GB): {', '.join(absent)}",
                      "First run only; they are cached afterwards.")
    return Result("models", FAIL,
                  f"not cached and huggingface.co unreachable: {', '.join(absent)}",
                  "Connect to the network for the first run, or copy a populated "
                  f"cache to {cache}.")


def check_disk(ctx: Context) -> Result:
    need = MODEL_CACHE_GB
    try:
        free_gb = shutil.disk_usage(Path.cwd()).free / 1e9
    except OSError as exc:
        return Result("disk", WARN, f"could not determine free space: {exc}")
    if free_gb >= need:
        return Result("disk", OK, f"{free_gb:.1f} GB free")
    return Result("disk", FAIL, f"{free_gb:.1f} GB free, need ~{need:.0f} GB",
                  "Free up space (the model cache is the bulk of it).")


def check_output_dir(ctx: Context) -> Result:
    out = Path(ctx.out_dir)
    probe_parent = out if out.exists() else out.parent
    if not probe_parent.exists():
        return Result("output", FAIL, f"{probe_parent} does not exist",
                      f"mkdir -p {probe_parent}, or pass --out to another path.")
    if not os.access(probe_parent, os.W_OK):
        return Result("output", FAIL, f"{probe_parent} is not writable",
                      "Check permissions, or pass --out to a writable path.")
    return Result("output", OK, f"{out} writable")


CHECKS = (
    check_python, check_packages, check_salt, check_responses, check_meal,
    check_tone_labels, check_entities, check_device, check_models, check_disk,
    check_output_dir,
)


# ---- driver -------------------------------------------------------------------
def run_all(ctx: Context | None = None) -> list[Result]:
    ctx = ctx or Context()
    results = []
    for fn in CHECKS:
        try:
            results.append(fn(ctx))
        except Exception as exc:  # a broken check must not kill the run
            results.append(Result(fn.__name__, FAIL, f"check itself errored: {exc!r}",
                                  "This is a bug in preflight, not in your setup."))
    return results


_MARK = {OK: "OK  ", WARN: "WARN", FAIL: "FAIL"}


def render(results: list[Result]) -> str:
    width = max(len(r.name) for r in results)
    lines = []
    for r in results:
        lines.append(f"  {_MARK[r.status]}  {r.name:<{width}}  {r.detail}")
        if r.fix and r.status != OK:
            lines.append(f"        fix: {r.fix}")
    return "\n".join(lines)


def summarize(results: list[Result]) -> str:
    n_fail = sum(r.status == FAIL for r in results)
    n_warn = sum(r.status == WARN for r in results)
    if n_fail:
        return f"preflight FAILED — {n_fail} blocking problem(s), {n_warn} warning(s)"
    return f"preflight passed — {len(results)} checks, {n_warn} warning(s)"
