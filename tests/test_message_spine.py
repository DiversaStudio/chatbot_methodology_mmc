import pandas as pd
from sami import load

SALT = "test_salt"


def test_spine_count_and_invariant():
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    assert len(msgs) == 2991  # measured; see report for 2993->2991 explanation
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
    assert msgs["user_id"].nunique() == 800  # measured; matches design doc's ~800
