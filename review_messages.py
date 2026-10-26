# review_messages.py
"""Rebuild the message grain with text + sentiment, for human review.

    python review_messages.py                  # -> exports/message_sentiment_review.ods
    python review_messages.py --label neutral  # only the neutral messages
    python review_messages.py --csv            # machine-readable instead of a workbook

Why this exists. `fact_message` carries the labels but is deliberately text-free,
and the message-grain `fact_message_full` that once shipped the whole corpus was
retired in schema v12 — full text now lives only at conversation grain
(`fact_conversation_full`). Reading individual messages against their labels
therefore means rebuilding the spine and re-joining it by `message_id`, which is
what this does.

**The one trap.** `fact_message_sample.csv` also has text and labels and looks
like the natural file to read, but it caps `SAMPLE_PER_BUCKET = 6` rows per
(subcluster x tone) bucket, so it is deliberately tone-balanced: it reads ~50%
neutral against a true rate of ~77%. Use this script, not that file, to judge the
distribution.

**Conversations.** `conversation` is the response record's creation time to the
second: messages sharing it belong to one conversation. Second precision is
load-bearing, not decoration — see `prepare`.

Privacy. Text goes through the SAME gate the shipped tables use — `redact.scrub`
with the real Spanish NER model, plus the self-identification and known-first-name
drop rules. A message the gate refuses is DROPPED, never written: the output
carries user messages, so the default path is gitignored and every other
destination is checked against .gitignore before a byte is written.
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))
from sami import load, redact, schema  # noqa: E402
from sami.export import EMOTION_DISPLAY_ORDER, message_key  # noqa: E402

DEFAULT_OUT = Path("exports/review/message_sentiment_review.ods")
LABELS = ("negative", "neutral", "positive")
#: Share of spine messages that must join to `fact_message` before the output is
#: trusted. Below this the two inputs describe different corpora and a silent
#: partial join would report a distribution no table was built from.
JOIN_FLOOR = 0.99


def labelled_messages() -> tuple[pd.DataFrame, int]:
    """The message spine joined to the labels already committed in exports/.

    No model inference happens here: the sentiment labels are read from
    `fact_message.csv`, so this reproduces the shipped run exactly rather than
    scoring the corpus a second time and risking a different answer.
    """
    src = (Path("exports") / "fact_message.csv")
    if not src.exists():
        raise schema.SchemaError(
            f"{src} not found — it carries the sentiment labels this joins to.\n"
            "  fix:  Run `python run_pipeline.py` first, or point --out at an "
            "exports/ directory that has been generated.")

    messages = load.load_messages(load.load_responses())
    messages["message_id"] = [message_key(u, s, m) for u, s, m
                              in zip(messages["user_id"], messages["seq"],
                                     messages["message"])]
    labels = pd.read_csv(src)[["message_id", "sentiment_label",
                               "emotion_display", "subcluster_name"]]
    joined = messages.merge(labels, on="message_id", how="inner")

    if not len(messages):
        raise schema.SchemaError(
            "The responses export produced no messages.\n"
            "  fix:  Check datasets/responses/ holds the platform export.")
    matched = len(joined) / len(messages)
    if matched < JOIN_FLOOR:
        # Almost always: datasets/ was refreshed but exports/ was not, so the
        # message_ids were hashed from a different corpus.
        raise schema.SchemaError(
            f"Only {matched:.1%} of the message spine joined to {src}.\n"
            f"  spine: {len(messages)} messages, joined: {len(joined)}\n"
            "  fix:  exports/ and datasets/ disagree. Re-run `python "
            "run_pipeline.py` so the labels and the spine come from the same "
            "export, then re-run this script.")
    return joined, len(messages)


def apply_privacy_gate(joined: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Scrub every message; return the survivors and how many were dropped.

    Mirrors `export.build_fact_message_sample`: a row the gate refuses is
    discarded rather than emitted with its raw text.
    """
    try:
        nlp = redact.load_ner()
    except Exception as exc:  # missing spaCy model is the common cause
        raise schema.SchemaError(
            f"Could not load the Spanish NER model required for redaction: {exc}\n"
            "  fix:  `uv sync` installs es-core-news-sm. Without it the person-"
            "name layer of the privacy gate cannot run, and shipping user text "
            "unredacted is not an option.")

    scrubbed = [redact.scrub(t, nlp=nlp) for t in joined["message"]]
    out = joined.copy()
    out["text_redacted"] = [r[0] for r in scrubbed]
    out["redaction_applied"] = [r[1] for r in scrubbed]
    dropped = int(out["text_redacted"].isna().sum())
    return out[out["text_redacted"].notna()].copy(), dropped


#: Columns the review output carries, in order. `is_courtesy` and the sort key
#: are measured on the working frame and deliberately left out of the output.
REVIEW_COLUMNS = ["sentiment_label", "emotion_display", "char_len",
                  "text_redacted", "subcluster_name", "city_canon", "ts",
                  "conversation", "conv_msg_n", "conv_size",
                  "redaction_applied", "message_id", "user_id"]


def prepare(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Filter to one label, add the review measures, order the rows.

    `conversation` is the record's creation time to the SECOND, and for one user
    the messages sharing it are one conversation. Second precision is
    load-bearing, not decoration: at minute precision this corpus yields only
    1329 distinct values for 1417 conversations (1022 conversations share a
    minute) and a bare date yields 124, so a coarser label would silently merge
    unrelated conversations into one. The upstream `ts` column keeps its
    minute-resolution display form; the grouping uses the full timestamp.

    `conv_msg_n` / `conv_size` are counted over the rows present in this output,
    i.e. after the privacy gate, so a conversation shows the messages the
    reviewer can actually see rather than ones dropped from the file.
    """
    df = df.copy()
    created = pd.to_datetime(df["ts"])
    df["conversation"] = created.dt.floor("s").dt.strftime("%Y-%m-%d %H:%M:%S")
    # Counted before the --label filter so a conversation's size is its real size,
    # not just the size of the slice being reviewed.
    grouped = df.groupby(["user_id", "conversation"], sort=False)
    df["conv_size"] = grouped["message_id"].transform("size")
    df["conv_msg_n"] = grouped.cumcount() + 1
    df["char_len"] = df["text_redacted"].astype(str).str.len()
    df["is_courtesy"] = df["text_redacted"].map(load.is_courtesy)
    df["ts"] = created.dt.strftime("%Y-%m-%d %H:%M")
    if label != "all":
        df = df[df["sentiment_label"] == label].copy()
    df["_o"] = df["sentiment_label"].map({l: i for i, l in enumerate(LABELS)}).fillna(9)
    # Same label grouping as before, but now a conversation's messages sit
    # together inside their label instead of being scattered by timestamp.
    return df.sort_values(["_o", "conversation", "conv_msg_n"], kind="mergesort")


def summary(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Counts, and the reading-quality measures that explain them.

    `pct_courtesy` is the one that matters: a high share means the label is
    reading politeness ("Gracias", "Buenas") rather than sentiment.

    Both distributions are ordered, not sorted by count. Sentiment runs
    negative/neutral/positive, and emotion follows
    `export.EMOTION_DISPLAY_ORDER` -- the dashboard's own least- to
    most-alarming reading order -- so the two always read the same way and a
    value's row is stable between runs.
    """
    dist = df["sentiment_label"].value_counts().reindex(LABELS).fillna(0).astype(int)
    emo = (df["emotion_display"].value_counts()
           .reindex(list(EMOTION_DISPLAY_ORDER)).fillna(0).astype(int))
    stats = df.groupby("sentiment_label").agg(
        n=("message_id", "size"),
        median_chars=("char_len", "median"),
        pct_under_20=("char_len", lambda s: round(100 * (s < 20).mean(), 1)),
        pct_courtesy=("is_courtesy", lambda s: round(100 * s.mean(), 1)),
    ).reindex([l for l in LABELS if l in set(df["sentiment_label"])])
    return dist, emo, stats


def guard_destination(path: Path) -> None:
    """Warn if the destination would be committed.

    The output is user text. `exports/review/` is gitignored precisely so it
    cannot be committed; any other path inside the repo has to
    earn that itself, and a warning is cheaper than a history rewrite.
    """
    try:
        inside = path.resolve().is_relative_to(_ROOT)
    except AttributeError:  # Python < 3.9
        inside = str(path.resolve()).startswith(str(_ROOT))
    if not inside:
        return
    try:
        ignored = subprocess.run(["git", "check-ignore", "-q", str(path)],
                                 cwd=_ROOT, capture_output=True).returncode == 0
    except OSError:
        return  # no git available; nothing useful to say
    if not ignored:
        print(f"WARNING: {path} is inside the repo and NOT gitignored.\n"
              "         It contains user message text — add it to .gitignore "
              "before committing anything.", file=sys.stderr)


def write_workbook(path: Path, df: pd.DataFrame, dist: pd.Series,
                   emo: pd.Series, stats: pd.DataFrame, n_spine: int,
                   n_joined: int, dropped: int, masked: int) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    hdr_fill = PatternFill("solid", fgColor="1F3864")
    hdr_font = Font(bold=True, color="FFFFFF")

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Sentiment review"
    ws["A1"].font = Font(bold=True, size=14)

    row = 3
    total = len(df) or 1
    ws.cell(row, 1, "Distribution by sentiment").font = Font(bold=True, size=12)
    row += 1
    for c, h in enumerate(["sentiment", "messages", "share %"], start=1):
        cell = ws.cell(row, c, h); cell.font = hdr_font; cell.fill = hdr_fill
    row += 1
    for name, n in dist.items():
        ws.cell(row, 1, name)
        ws.cell(row, 2, int(n))
        ws.cell(row, 3, round(100 * n / total, 1)).number_format = "0.0"
        row += 1
    ws.cell(row, 1, "TOTAL").font = Font(bold=True)
    ws.cell(row, 2, len(df)).font = Font(bold=True)
    row += 2

    ws.cell(row, 1, "Distribution by emotion").font = Font(bold=True, size=12)
    row += 1
    for c, h in enumerate(["emotion", "messages", "share %"], start=1):
        cell = ws.cell(row, c, h); cell.font = hdr_font; cell.fill = hdr_fill
    row += 1
    for name, n in emo.items():
        ws.cell(row, 1, name)
        ws.cell(row, 2, int(n))
        ws.cell(row, 3, round(100 * n / total, 1)).number_format = "0.0"
        row += 1
    ws.cell(row, 1, "TOTAL").font = Font(bold=True)
    ws.cell(row, 2, len(df)).font = Font(bold=True)
    row += 2

    ws.cell(row, 1, "Reading quality by sentiment").font = Font(bold=True, size=12)
    row += 1
    for c, h in enumerate(["sentiment", "messages", "median chars",
                           "% under 20 chars", "% pure courtesy"], start=1):
        cell = ws.cell(row, c, h); cell.font = hdr_font; cell.fill = hdr_fill
    row += 1
    for name, r in stats.iterrows():
        ws.cell(row, 1, name)
        ws.cell(row, 2, int(r["n"]))
        ws.cell(row, 3, int(r["median_chars"]))
        ws.cell(row, 4, float(r["pct_under_20"])).number_format = "0.0"
        ws.cell(row, 5, float(r["pct_courtesy"])).number_format = "0.0"
        row += 1
    row += 1

    ws.cell(row, 1, "Provenance and privacy").font = Font(bold=True, size=12)
    row += 1
    for text in [
        f"messages in spine: {n_spine}",
        f"joined to fact_message.csv: {n_joined} ({100 * n_joined / n_spine:.1f}%)",
        f"dropped as unredactable by redact.scrub: {dropped}",
        f"kept with names masked: {masked}",
        "conversation = record creation time to the second; a shared value is",
        "  one conversation (conv_msg_n / conv_size count the rows in this file)",
        "labels are read from exports/fact_message.csv, not re-scored here",
        "text is scrubbed with the same gate as fact_message_sample.csv",
    ]:
        ws.cell(row, 1, text)
        row += 1

    ws.column_dimensions["A"].width = 62
    for col, w in zip("BCDE", (12, 14, 20, 18)):
        ws.column_dimensions[col].width = w

    ms = wb.create_sheet("Messages")
    cols = list(df.columns)
    ms.append(cols)
    for c in range(1, len(cols) + 1):
        cell = ms.cell(1, c); cell.font = hdr_font; cell.fill = hdr_fill
        cell.alignment = Alignment(vertical="center")
    ms.freeze_panes = "A2"
    ms.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(df) + 1}"
    for r in df.itertuples(index=False):
        ms.append(list(r))
    widths = {"sentiment_label": 14, "emotion_display": 13, "char_len": 9,
              "text_redacted": 110, "subcluster_name": 30, "city_canon": 14,
              "ts": 17, "conversation": 21, "conv_msg_n": 11, "conv_size": 11,
              "redaction_applied": 17, "message_id": 18, "user_id": 14}
    for i, name in enumerate(cols, start=1):
        ms.column_dimensions[get_column_letter(i)].width = widths.get(name, 16)
    text_col = cols.index("text_redacted") + 1
    for r in range(2, len(df) + 2):
        ms.cell(r, text_col).alignment = Alignment(wrap_text=True, vertical="top")
        ms.row_dimensions[r].height = 42
    wb.save(path)


def warn_if_open(path: Path) -> None:
    """Warn when a spreadsheet app has the file open (it leaves a lock file).

    Saving underneath an open workbook lets the app clobber this run when it
    next saves, which looks like the regeneration silently failing.
    """
    lock = path.parent / f".~lock.{path.name}#"
    if lock.exists():
        print(f"WARNING: {path.name} appears to be open ({lock.name} exists).\n"
              "         Close it first, or the app may overwrite this run when "
              "it next saves.", file=sys.stderr)


def write_ods(xlsx_path: Path, ods_path: Path) -> bool:
    """Convert the workbook we build into .ods, and report whether it worked.

    openpyxl writes .xlsx only, and pandas' ODS writer emits no formatting at
    all (no header fill, freeze pane, autofilter or wrapped text), so the .ods
    is produced by converting the formatted .xlsx -- the same route the file
    took when it was first saved as .ods by hand.

    Returns False when LibreOffice is not installed, so the caller can fall back
    to the .xlsx instead of failing outright.
    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return False
    subprocess.run([soffice, "--headless", "--norestore", "--convert-to", "ods",
                    "--outdir", str(ods_path.parent), str(xlsx_path)],
                   check=True, capture_output=True)
    return ods_path.exists()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Rebuild the message grain with text + sentiment for review.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Text is redacted with the pipeline's own gate; messages it "
               "refuses are dropped. The output contains user messages — keep "
               "it out of version control.")
    ap.add_argument("--out", default=None,
                    help=f"output path (default: {DEFAULT_OUT})")
    ap.add_argument("--label", choices=("all",) + LABELS, default="all",
                    help="keep only one sentiment (default: all)")
    ap.add_argument("--csv", action="store_true",
                    help="write machine-readable CSV instead of a workbook")
    args = ap.parse_args(argv)

    out = Path(args.out) if args.out else DEFAULT_OUT
    if args.csv and out.suffix.lower() != ".csv":
        out = out.with_suffix(".csv")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        joined, n_spine = labelled_messages()
        scrubbed, dropped = apply_privacy_gate(joined)
    masked = int(scrubbed["redaction_applied"].sum())
    work = prepare(scrubbed, args.label)
    df = work[REVIEW_COLUMNS]
    dist, emo, stats = summary(work)

    guard_destination(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.csv:
        df.to_csv(out, index=False)
    elif out.suffix.lower() == ".ods":
        warn_if_open(out)
        # Build the formatted .xlsx under the .ods's own stem, then convert.
        xlsx = out.with_suffix(".xlsx")
        guard_destination(xlsx)
        write_workbook(xlsx, df, dist, emo, stats, n_spine, len(joined),
                       dropped, masked)
        try:
            converted = write_ods(xlsx, out)
        except subprocess.CalledProcessError as exc:
            converted = False
            print(f"WARNING: LibreOffice failed to convert to .ods: {exc}",
                  file=sys.stderr)
        if converted:
            xlsx.unlink(missing_ok=True)
        else:
            out = xlsx
            print("NOTE: LibreOffice not available, so the formatted .xlsx was "
                  f"written instead ({xlsx}).\n      Install libreoffice for "
                  ".ods output, or open it and Save As .ods.", file=sys.stderr)
    else:
        warn_if_open(out)
        write_workbook(out, df, dist, emo, stats, n_spine, len(joined),
                       dropped, masked)

    print(f"spine {n_spine} -> joined {len(joined)} -> after privacy gate "
          f"{len(joined) - dropped} -> written {len(df)}")
    # Per-conversation, not per-row: a row-weighted median is pulled up by the
    # few very long conversations and describes no actual conversation.
    conv_sizes = df.groupby(["user_id", "conversation"]).size()
    print(f"conversations: {len(conv_sizes)} "
          f"(median {int(conv_sizes.median())} messages each, max {int(conv_sizes.max())})")
    print("\nby sentiment:")
    print(stats.to_string())
    print("\nby emotion:")
    print(emo.to_string())
    print(f"\nwrote {out}")
    if not args.csv:
        print("  sheet 'Messages' is filterable; 'Summary' carries both "
              "distributions and the privacy accounting.")
    print("  NOTE: contains user message text — do not commit it.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except schema.SchemaError as exc:
        print(f"\nSchema error:\n{exc}", file=sys.stderr)
        raise SystemExit(1)
