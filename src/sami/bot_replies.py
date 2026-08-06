"""SAMI's own replies: the only source that can MEASURE an unmet need.

Every other unmet-need signal in this pipeline is inferred from what the user
said — tone, cluster vocabulary, emergent-theme probes. This one is different:
the assistant states, in its own words, that it has no information. There is no
model between the data and the number, so no kappa gate applies.

That is also the trap. "No model" is not "no error": the flags come from a
REGEX, and a regex has precision and recall like anything else. It is only
quotable because `validation.probe_report` measures both against a hand-labelled
gold set. Ship the rate without that and it is the tone problem again, minus the
gate that would have caught it.

Scope is deliberately narrow. This module never merges with the message spine:
its window (2026-07-23 -> 08-04) overlaps the survey corpus (which ends 07-28),
so a merge would need a dedup rule for the 88 users in both, and re-clustering
over the enlarged corpus would shuffle every cluster id, archetype name and
subcategory name in the export. The KPI is worth none of that. The two data
sets meet only through `user_id`, which lines up for free because
`load.pseudonymize` hashes the phone's digits and both sources carry the phone.
"""
from __future__ import annotations

import hashlib
import re

import pandas as pd

from . import load, schema, taxonomy

# The raw log has NO HEADER ROW: four unnamed columns, positional. Read with
# header=None and name them here, once.
COLUMNS = ["ts", "wa_id", "user_message", "bot_reply"]

#: Columns of `load_bot_log`'s result that carry raw text. They exist for the
#: gold-labelling pass and for `validation`; `export.build_fact_bot_turn` drops
#: them, because a bot reply quotes the user's city and situation back at them
#: and has no business in a published table that exists to produce one rate.
TEXT_COLUMNS = ["user_message", "bot_reply"]


def reply_key(reply: str) -> str:
    """Stable identity for a bot reply: sha1 of its normalised text.

    Keyed on CONTENT, never on row position. The tone gold set was once keyed
    positionally and produced a kappa computed from unrelated message pairs
    (see `validation.align_gold`); the same mistake here would produce a
    precision computed from unrelated replies. A re-export in a different row
    order must not move a single label.

    Two turns with byte-identical replies share a key on purpose. The gold
    label answers "does this text state SAMI lacked the information", which is
    a property of the text alone — so identical text must carry an identical
    label, and the labeller should only have to read it once.
    """
    norm = re.sub(r"\s+", " ", str(reply)).strip().lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _turn_id(user_id: str, ts, key: str) -> str:
    return hashlib.sha1(f"{user_id}|{ts}|{key}".encode("utf-8")).hexdigest()[:16]


def flag(replies) -> pd.DataFrame:
    """Apply both probes to a series of bot replies -> (gap_flag, handoff_flag).

    Split out from `load_bot_log` so the probes can be re-run over a gold file,
    a fixture, or a candidate regex without touching Excel.
    """
    s = pd.Series(replies).astype(str)
    return pd.DataFrame({
        "gap_flag": s.str.contains(taxonomy.COVERAGE_GAP_PROBE, case=False,
                                   regex=True, na=False),
        "handoff_flag": s.str.contains(taxonomy.HUMAN_HANDOFF_PROBE, case=False,
                                       regex=True, na=False),
    }, index=s.index)


def load_bot_log(path, salt: str) -> pd.DataFrame:
    """Read the raw WhatsApp production log into flagged turns.

    Returns one row per turn: turn_id, user_id, ts, reply_key, the two text
    columns, and the two flags. `user_id` is the same salted digest
    `load_responses` produces, so it joins `dim_user` directly for the users
    who also have a survey record.
    """
    raw = pd.read_excel(path, header=None, dtype=str)
    if raw.shape[1] != len(COLUMNS):
        raise schema.SchemaError(
            f"The bot log must have exactly {len(COLUMNS)} columns and no header "
            f"row; this file has {raw.shape[1]}.\n"
            f"  file: {path}\n"
            f"  expected, in order: {', '.join(COLUMNS)}\n"
            "  fix:  Export the WhatsApp production log again without a header "
            "row, or pass the correct file with --bot-log PATH.xlsx.")
    df = raw.set_axis(COLUMNS, axis=1)

    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    if df["ts"].isna().all():
        raise schema.SchemaError(
            "No parsable timestamp in the bot log's first column.\n"
            f"  file: {path}\n"
            "  fix:  Column 1 must be an ISO timestamp (2026-08-04T17:51:43.624Z). "
            "Check the export was not written with the columns reordered.")
    df = df[df["ts"].notna()].copy()

    df["user_id"] = df["wa_id"].map(lambda v: load.pseudonymize(v, salt))
    df["reply_key"] = df["bot_reply"].map(reply_key)
    df["turn_id"] = [_turn_id(u, t, k) for u, t, k
                     in zip(df["user_id"], df["ts"], df["reply_key"])]
    df = df.join(flag(df["bot_reply"]))

    df = df.drop(columns=["wa_id"]).sort_values("ts").reset_index(drop=True)
    return df[["turn_id", "user_id", "ts", "reply_key",
               "user_message", "bot_reply", "gap_flag", "handoff_flag"]]


def gold_candidates(turns: pd.DataFrame, n_unmatched: int = 200,
                    random_state: int = 0) -> pd.DataFrame:
    """The set a human must label: every gap-flagged reply, plus a random sample
    of the rest.

    Two strata, for two different measurements, and they are NOT interchangeable:

    - **matched: a census.** Every flagged reply is labelled, so precision is
      exact and carries no sampling error at all. There are few enough to read.
    - **unmatched: a random sample.** Labelling all of them is what nobody will
      do, so recall is ESTIMATED from a sample and reported with an interval.
      `validation.probe_report` needs `n_unmatched_total` to scale the miss rate
      back up, which is why `stratum` is recorded per row rather than inferred.

    Deduplicated by `reply_key`: identical text gets one row and one label.
    """
    uniq = turns.drop_duplicates("reply_key")
    matched = uniq[uniq["gap_flag"]]
    unmatched = uniq[~uniq["gap_flag"]]
    take = min(n_unmatched, len(unmatched))
    sample = unmatched.sample(n=take, random_state=random_state)

    out = pd.concat([
        matched.assign(stratum="matched"),
        sample.assign(stratum="unmatched"),
    ])
    out = out[["reply_key", "stratum", "bot_reply"]].copy()
    out["human_label"] = ""  # the human fills this: gap / not_gap
    return out.sort_values(["stratum", "reply_key"]).reset_index(drop=True)
