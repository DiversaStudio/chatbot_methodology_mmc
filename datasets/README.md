# Datasets

Put the chatbot's data exports here. This is the only folder the pipeline reads
data from.

```text
datasets/
  responses/    <- the chatbot users / responses export
  meal/         <- the MEAL survey export
```

## Adding a new export

1. Save the responses export into `datasets/responses/`.
2. Save the MEAL survey export into `datasets/meal/`.
3. Verify the setup:

   ```powershell
   .venv/Scripts/python.exe run_pipeline.py --check
   ```

   It names the two files it will read and confirms every column it needs is
   present. It does no work, so it takes seconds.

4. Run the pipeline:

   ```powershell
   .venv/Scripts/python.exe run_pipeline.py
   ```

## What the folder guarantees

**The filename does not matter.** The folder declares what a file is, so the
platform can rename its exports freely.

**The newest file is used.** Within each folder the most recently modified
`.xlsx` is read. Older exports may be left in place as an archive; they are
ignored. Every run prints which file it used, so any output can be traced back
to its input:

```text
[1/9] loading responses + MEAL
  responses: datasets/responses/Users_Group_Title_1509.xlsx (modified 2026-09-15, 1 older file ignored)
  meal:      datasets/meal/Survey_1509.xlsx (modified 2026-09-15)
```

**Only `.xlsx` is read.** Other file types are ignored, as are the `~$...xlsx`
lock files Excel creates while a workbook is open. Close the workbook in Excel
before running.

**The data is never committed.** `.gitignore` excludes every spreadsheet in this
folder. The raw exports contain users' WhatsApp phone numbers and must not enter
version control.

## Using a file from somewhere else

To read a one-off file without putting it in the folder:

```powershell
.venv/Scripts/python.exe run_pipeline.py --responses PATH.xlsx --meal PATH.xlsx
```

An explicit path always takes precedence over the folder contents.

## Also required: `SAMI_SALT`

User identifiers are salted hashes, so the pipeline needs the salt that
produced the existing exports. Put it in a `.env` file at the repository root:

```text
SAMI_SALT=<the value provided out-of-band>
```

`.env` is gitignored. The salt is never committed. Using a different salt
produces different `user_id` values, and the new exports will not join against
the previous ones.

## What each export must contain

See [`docs/DATA_SOURCES.md`](../docs/DATA_SOURCES.md) for the required columns
of each file and what happens when one is missing.
