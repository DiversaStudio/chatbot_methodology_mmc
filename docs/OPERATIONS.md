# Operations

This is the runbook for installing the project, refreshing it with a new data
export, and diagnosing it when something fails. What each source file must
contain is covered separately in [`DATA_SOURCES.md`](DATA_SOURCES.md); this
document assumes that contract and does not repeat it.

## Install

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and
dependency management.

```powershell
uv sync
```

This creates `.venv` with every dependency declared in `pyproject.toml` and
installs the CPU build of `torch` (`cpu` is a default dependency group). The
CPU build works on any machine — Windows, Linux, Intel and Apple Silicon Macs.

On a machine with an NVIDIA GPU, opt into the CUDA build instead:

```powershell
uv sync --no-group cpu --group gpu
```

`cpu` and `gpu` are declared as mutually exclusive dependency groups. Re-run
whichever command you need to switch between them — a plain `uv sync` always
lands the CPU group again, replacing a GPU install. See
[Troubleshooting](#troubleshooting) for the failure this causes if missed.

### Alternative: plain pip + venv (no uv)

If `uv` is not available, install with the standard-library `venv` and `pip`.
This requires Python 3.11+ already installed.

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate

# 2. Upgrade pip
python -m pip install --upgrade pip

# 3. Install PyTorch. CPU build — works on any machine:
pip install "torch>=2.10"
#    ...or, on a machine with an NVIDIA GPU (faster NLP):
#    pip install "torch>=2.10" --index-url https://download.pytorch.org/whl/cu128

# 4. Install everything else (mirrors pyproject.toml)
pip install -r requirements.txt
```

`requirements.txt` is kept in sync with `pyproject.toml`. `torch` is installed
as a separate step so the CPU or GPU wheel is chosen deliberately — installing
it before `requirements.txt` means `pip` keeps the wheel already present.

## The first run downloads models

A full run (not `--skip-nlp`) uses two Hugging Face models: a sentence
embedding model and a sentiment model, roughly 4 GB together. The first run
downloads them once into the user's Hugging Face cache directory
(`~/.cache/huggingface/hub`, or `$HF_HOME/hub` if `HF_HOME` is set). Every
run after that reads the local cache and needs no network access for the
models.

## Refresh runbook

End-to-end sequence for refreshing the exports with a new data export:

1. **Save the new export files.** Drop the responses workbook into
   `datasets/responses/` and the MEAL workbook into `datasets/meal/`. The
   filename does not matter — the newest `.xlsx` in each folder is used. See
   [`datasets/README.md`](../datasets/README.md) and
   [`DATA_SOURCES.md`](DATA_SOURCES.md) for what each file must contain.

2. **Verify the machine and the files:**

   ```powershell
   .venv\Scripts\python.exe run_pipeline.py --check
   ```

   Success looks like ten `OK` (or `OK`/`WARN`, never `FAIL`) lines ending in
   `preflight passed`, and exit code `0`. It does no work and downloads
   nothing, so it costs seconds. See [The ten preflight
   checks](#the-ten-preflight-checks) below for what each line means and what
   to do if it fails.

3. **Run the pipeline:**

   ```powershell
   .venv\Scripts\python.exe run_pipeline.py
   ```

   Success looks like numbered, timed stage lines (`[1/9] loading responses +
   MEAL`, …), a manifest table, a `parity_check` table, a line reporting how
   many tables were written and the total elapsed time, and exit code `0`.

4. **Inspect `parity_check`.** The run prints it and also writes
   `exports/parity_check.csv`. Every row's `match` column must be `True`. If
   any row is `False`, the run printed `PARITY FAILED` to stderr and exited
   non-zero — see [The parity gate](#the-parity-gate).

5. **Refresh Power BI.** Open the `.pbix` report and use *Refresh* (it is
   bound to the CSVs in `exports/`, not to the raw workbooks). Confirm the
   report opens and its visuals populate, then commit the updated `exports/`
   CSVs and, if the report changed meaningfully, the `.pbix` file — see [The
   `.pbix` is a tracked binary](#the-pbix-is-a-tracked-binary).

## The three run modes

```powershell
.venv\Scripts\python.exe run_pipeline.py             # full run
.venv\Scripts\python.exe run_pipeline.py --skip-nlp   # non-NLP tables only
.venv\Scripts\python.exe run_pipeline.py --check      # preflight only, no work
```

| Mode | What it does | Measured duration |
| --- | --- | --- |
| `run_pipeline.py` | Full pipeline: load, embed, cluster, sentiment, dimension/fact/aggregate tables, PII scan, write. Writes the full set of tables in `exports/`. | ~174 seconds (this run, RTX 3050 Ti, model cache warm). Previously measured at 2m11s on the same GPU and 5m22s on CPU only (also model cache warm); the CPU figure has not been re-measured on this branch. |
| `--skip-nlp` | Everything except embedding, clustering, and sentiment. No model download, no NLP-dependent tables (`dim_cluster`, `nlp_*`). | ~7 seconds (this run). |
| `--check` | Runs the ten preflight checks and exits. `responses`/`meal` each read only the first 5 rows of the export to confirm the header and columns; nothing is written. | Seconds. |

The run prints numbered, timed stages (e.g. `[5/9] sentiment over N
messages …`, where N is the current message count in `fact_message`), so a
slow stage is visibly working rather than hung.

Across two runs on the same machine with the same inputs, the only export
that differs is `meta_run.csv` (its `generated_at` timestamp) — every other
table, including `nlp_umap.csv`, is byte-identical because the clustering and
projection are seeded.

## The ten preflight checks

`run_pipeline.py` runs these checks, in this order, before doing any work —
on every invocation, including `--check`. A `FAIL` stops the run; a `WARN`
lets it continue.

| Check | What it verifies | Fix when it fails |
| --- | --- | --- |
| `python` | Python is 3.11 or newer. | Install Python 3.11+ and recreate the environment: `uv sync` |
| `packages` | The required packages are importable (`pandas`, `numpy`, `sklearn`, `openpyxl` always; `torch`, `transformers`, `sentence_transformers`, `umap` unless `--skip-nlp`). | `uv sync` (add `--no-group cpu --group gpu` on an NVIDIA machine) |
| `salt` | `SAMI_SALT` resolves (environment or `.env`). | The pseudonymization salt is never committed. Obtain it out-of-band and put `SAMI_SALT=...` in a `.env` file at the repo root (gitignored), or set it in the environment. A different salt yields different `user_id` hashes, so exports will not match the committed ones. |
| `responses` | `datasets/responses/` has a readable `.xlsx` with every required column present after header detection and column mapping. | If no file: save the responses export into `datasets/responses/`, or pass `--responses PATH`. If a column is missing: the error names the file and the missing column(s) — see `DATA_SOURCES.md`. |
| `meal` | Same as `responses`, for `datasets/meal/`. | Save the MEAL export into `datasets/meal/`, or pass `--meal PATH`. |
| `tone labels` | `validation/tone_labels_analyst.csv` exists (skipped, and reported `OK`, under `--skip-nlp`). See [`DATA_SOURCES.md`](DATA_SOURCES.md) for what this file is, its columns, and why it is committed rather than dropped into `datasets/`. | A full run reads this file to build the `nlp_tone_confusion` table. Restore the file, or run with `--skip-nlp`. |
| `device` | Whether CUDA is usable (skipped, and reported `OK`, under `--skip-nlp`). | CPU-only is a `WARN`, not a `FAIL` — the run proceeds, only slower. On an NVIDIA machine, install the CUDA build: `uv sync --no-group cpu --group gpu` |
| `models` | The two Hugging Face models are cached, or the network can reach `huggingface.co` to download them (skipped, and reported `OK`, under `--skip-nlp`). | Connect to the network for the first run, or copy a populated cache to the Hugging Face cache directory, or run with `--skip-nlp`. |
| `disk` | Enough free disk space for the model cache (or a smaller minimum under `--skip-nlp`). | Free up space (the model cache is the bulk of it). |
| `output` | The output directory exists and is writable. | `mkdir -p <dir>`, or pass `--out` to another path. Or check permissions. |

Verbatim output captured on this branch, on this machine (GPU present, data
and salt in place):

```
preflight:
  OK    python       3.12.10
  OK    packages     8 required packages present
  OK    salt         SAMI_SALT resolved
  OK    responses    Users_Group_Title_2807.xlsx (header row 2)
  OK    meal         Survey_Responses_Group_Title_2807.xlsx (header row 2)
  OK    tone labels  validation\tone_labels_analyst.csv
  OK    device       CUDA — NVIDIA GeForce RTX 3050 Ti Laptop GPU
  OK    models       both models cached in C:\Users\sedig\.cache\huggingface\hub
  OK    disk         62.8 GB free
  OK    output       exports writable
preflight passed — 10 checks, 0 warning(s)
```

Exit code `0`. On a CPU-only machine, `device` returns `WARN` (with the
CPU/GPU runtime hint quoted above as the fix text) rather than `FAIL`, and
`--check` still exits `0` — a missing GPU never blocks a run.

## The parity gate

`exports/parity_check.csv` reconciles the row counts and key metrics in the
exported tables against `qa.reconciliation`, an independent count computed
straight from the loaded data. `run_pipeline.py` prints this table at the end
of every run and exits non-zero the moment any row's `match` column is
`False`. A run that fails parity must not be published — do not commit its
`exports/` output or refresh the Power BI report from it. Re-run the pipeline
after resolving the underlying data or code issue.

## CPU and GPU

The pipeline runs on GPU when one is present and falls back to CPU otherwise;
both produce the same set of tables in `exports/`. Comparing a full run on
each device against the same input data: **every table except `meta_run` and
`nlp_umap` is byte-identical.** The two that differ:

- `meta_run.csv` — differs only in its `generated_at` timestamp.
- `nlp_umap.csv` — every `user_id` and `cluster_id` matches between devices;
  only the 2D `x`/`y` projection coordinates differ. No count or percentage
  anywhere in the exports depends on those coordinates.

## `SAMI_SALT`

`SAMI_SALT` is required and never committed to the repository. Obtain it
out-of-band and put it in a `.env` file at the repository root:

```text
SAMI_SALT=<the value provided out-of-band>
```

`.env` is gitignored. `user_id` is a salted hash computed from this value —
using a different salt produces different `user_id` values for the same
underlying users, so a run's exports will be internally consistent but will
not join against exports produced with a different salt.

## The `.pbix` is a tracked binary

The Power BI report file is committed to the repository as a binary. Unlike
the CSVs in `exports/`, git cannot diff or compress successive versions of it
against each other — each saved version adds its full file size to the
repository history. Commit it on meaningful revisions of the report (a new
visual, a restructured page), not after every save while iterating.

## Running the notebooks

Run the notebooks with the project's environment, e.g. from VS Code (select
the `.venv` kernel) or from the command line:

```powershell
uv run jupyter lab
```

If the environment was set up with plain pip + venv instead of `uv` (see
[Alternative: plain pip + venv](#alternative-plain-pip--venv-no-uv) above),
activate it first and launch Jupyter directly:

```powershell
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
jupyter lab
```

Run the notebooks in order (01 → 02 → 03). They import shared loaders and
analysis logic from [`src/sami/`](../src/sami/), so use the project's `.venv`
(via `uv sync`, above) rather than a bare Python environment. Each notebook's
setup cell locates `src/` by walking up from the working directory, so it
works whether the kernel starts in `notebooks/` (JupyterLab) or at the repo
root (VS Code).

The notebooks read the same `datasets/responses/` and `datasets/meal/`
exports as the pipeline, populated per [`datasets/README.md`](../datasets/README.md),
and need `SAMI_SALT` set — see [`SAMI_SALT`](#sami_salt) above.
`run_pipeline.py --check` is the quickest way to confirm both before opening
Jupyter.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `SAMI_SALT is not set` (or the `salt` preflight check fails) | No salt in the environment or `.env`. | Put `SAMI_SALT=<value>` in a `.env` file at the repo root, obtained out-of-band, or set it in the environment. |
| `No .xlsx found for the 'responses'/'meal' dataset` | The corresponding `datasets/<role>/` folder is empty. | Save the export into `datasets/responses/` or `datasets/meal/`. The filename does not matter; the newest `.xlsx` is used. Or pass `--responses PATH` / `--meal PATH`. |
| Preflight or a run reports the export file as missing or unreadable, but the folder looks populated in Explorer | An Excel lock file (`~$...xlsx`) is present because the workbook is currently open in Excel. Lock files are skipped by `datasets.candidates`, so an open workbook is treated as absent. | Close the workbook in Excel, then re-run. |
| `SchemaError` naming a missing required column | The export is missing a column the pipeline requires (see `DATA_SOURCES.md`). | The error message names the file, the missing column(s), and every column the file actually has. Map the platform's renamed field back to the expected name, or extend `RESPONSES_REQUIRED` / `MEAL_REQUIRED` in `src/sami/schema.py`. |
| `qa.validate_schema` raises `expected one of {...} for <role>, got [...]` | The check inspects the workbook's **sheet name** before it looks at columns. A workbook with more than one sheet, none of which matches the accepted names for that role, fails here — before header detection or column checks ever run, so it is a different error from a missing column. | Confirm the export was saved from the correct source (responses vs. MEAL) and that its sheet was not renamed. Single-sheet workbooks are tolerated regardless of sheet name. |
| `PARITY FAILED` printed at the end of a run; exit code 1 | `exports/parity_check.csv` has at least one row where `match` is `False` — the exported tables disagree with the independent reconciliation count. | Do not publish this run's `exports/` output. Investigate the mismatched metric before re-running. |
| Tests fail after `uv sync`, or the GPU stops being used, even though it worked before | A bare `uv sync` applies `default-groups = ["cpu", "dev"]` in `pyproject.toml`, which reinstalls the CPU build of `torch` over a previously installed GPU build. | Re-sync with the GPU group: `uv sync --no-group cpu --group gpu`. Do this after any change to the lockfile or dependencies on a GPU machine. |
| A freshly installed CPU `torch` wheel is blocked from running (import fails, or a hang with no clear error) on Windows | Windows Smart App Control blocks the newly downloaded, unsigned wheel's native components. Observed on this machine after the `uv sync` CPU/GPU mixup above: the CPU wheel install triggered this and five tests failed. | Re-sync with the correct group as above. If the block persists, confirm `python-preference = "only-system"` is set in `pyproject.toml`'s `[tool.uv]` section (it is, by default in this repo) so `uv` uses the signed system Python rather than an unsigned uv-managed build. |
| Jupyter kernel fails to launch with `spawn UNKNOWN` | Windows Smart App Control blocks `uv`'s own unsigned managed Python builds. | `pyproject.toml` sets `python-preference = "only-system"` and `python-downloads = "never"` under `[tool.uv]` so `uv` always uses the signed system Python instead of downloading its own. If this is missing or was reverted, restore it and re-run `uv sync`. |
| `uv sync` deletes `src/` | `tool.uv.package` is unset (defaults to installing the project as a package, which treats `src/` as a package source root during sync) or was reverted to `true`. | Confirm `pyproject.toml` has `[tool.uv]` `package = false` before running `uv sync` — this repo is a notebook/analysis project, not an installable library. |

## Related documents

- [`DATA_SOURCES.md`](DATA_SOURCES.md) — what the responses and MEAL exports
  must contain, and how the pipeline reads them.
- [`datasets/README.md`](../datasets/README.md) — the `datasets/` folder
  mechanism (role-by-folder, newest-file-wins).
- [`exports/_schema.md`](../exports/_schema.md) — the export table reference
  (grain, columns, which notebook plot each table feeds).
