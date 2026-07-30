import pandas as pd
from sami import load
from conftest import requires_real_data

SALT = "test_salt"


def test_spine_count_and_invariant(users_fixture):
    # Exact count against the committed synthetic fixture (6 messages survive
    # across the 6 valid users). See the requires_real_data invariant below for
    # the check that must hold on the real, gitignored export instead.
    resp = load.load_responses(users_fixture, salt=SALT)
    msgs = load.load_messages(resp)
    assert len(msgs) == 6
    # P6: sum of per-user message counts == number of message rows
    per_user = msgs.groupby("user_id")["n_msgs_user"].first().sum()
    assert per_user == len(msgs)


def test_spine_no_noise_rows(users_fixture):
    resp = load.load_responses(users_fixture, salt=SALT)
    msgs = load.load_messages(resp)
    assert (msgs["message"].str.strip().str.len() >= 3).all()
    assert not msgs["message"].str.fullmatch(r"\d+").any()


def test_spine_seq_is_zero_based_per_user(users_fixture):
    resp = load.load_responses(users_fixture, salt=SALT)
    msgs = load.load_messages(resp)
    first = msgs.sort_values(["user_id", "seq"]).groupby("user_id")["seq"].first()
    assert (first == 0).all()


def test_users_with_text(users_fixture):
    # 5 of the fixture's 6 users have a Messages blob (one row is null).
    resp = load.load_responses(users_fixture, salt=SALT)
    msgs = load.load_messages(resp)
    assert msgs["user_id"].nunique() == 5


@requires_real_data
def test_spine_invariants_hold_on_real_export():
    """The P6 spine invariant and the noise/seq properties, re-checked on the
    real (gitignored) export -- which will have a different row count every
    time MMC refreshes the download, so no count is asserted here."""
    resp = load.load_responses(salt=SALT)
    msgs = load.load_messages(resp)
    per_user = msgs.groupby("user_id")["n_msgs_user"].first().sum()
    assert per_user == len(msgs)
    assert msgs["user_id"].nunique() <= resp["user_id"].nunique()
    assert (msgs["message"].str.strip().str.len() >= 3).all()
    assert not msgs["message"].str.fullmatch(r"\d+").any()
