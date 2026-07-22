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
    # user_id is the intended pseudonymized hex hash: a 12-char hex string can
    # incidentally contain a run of 7+ digit characters by chance (hex digits
    # are 0-9a-f), which is not a PII leak. Exclude it from the raw-digit scan.
    scan_cols = [c for c in df.columns if c != "user_id"]
    joined = " ".join(df[scan_cols].astype(str).fillna("").values.ravel())
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


def test_split_messages_drops_redacted_only_lines():
    # split_messages runs on the Messages column *after* _redact_pii_runs has already
    # replaced 7+-digit runs with the literal token "[redacted]" (load_responses
    # redacts before returning; split_messages is applied downstream). A line that
    # was purely a digit run (e.g. a phone number) becomes just "[redacted]" — that
    # must still be treated as noise (as the original all-digit line was), not
    # survive as a phantom message.
    msgs = load.split_messages("hola\n[redacted]\ngracias amigo")
    assert "[redacted]" not in msgs
    assert msgs == ["hola", "gracias amigo"]


def test_split_messages_keeps_lines_with_embedded_pii_redacted():
    # A line with PII embedded alongside real content should survive, redacted,
    # not be dropped entirely.
    msgs = load.split_messages("necesito ayuda mi numero [redacted] por favor")
    assert len(msgs) == 1
    assert "[redacted]" in msgs[0]
    assert not re.search(r"\d{7,}", msgs[0])


def test_message_spine_has_no_phantom_redacted_messages():
    # End-to-end: the full pipeline (load_responses -> split_messages on the
    # already-redacted Messages column) must not manufacture phantom "[redacted]"
    # messages out of lines that were originally pure digit runs.
    #
    # Measured count is 2991, not the design doc's 2993 (see docs/superpowers/plans/
    # 2026-07-22-sami-pipeline-foundation.md). The 2993 baseline was measured on raw,
    # unredacted text, where two standalone "+<12 digits>" phone-number lines
    # (e.g. "+573208471248") were counted as real messages only because a leading
    # "+" defeated the original `t.isdigit()` noise check -- not because they held
    # any conversational content. After PII redaction (required for the hard PII
    # gate) those lines become "+[redacted]", which the redaction-invariant noise
    # check correctly drops as noise. That's 2 fewer messages than the stale
    # baseline: 2993 - 2 = 2991. The export/actual behavior is the source of truth
    # per project convention; this constant reflects the produced value, not the
    # doc reference.
    df = load.load_responses(salt=SALT)
    spine = [m for blob in df["Messages"] for m in load.split_messages(blob)]
    assert not any(m.strip() == "[redacted]" for m in spine)
    assert len(spine) == 2991
