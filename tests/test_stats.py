import numpy as np
import pandas as pd
import pytest
from sami import stats


def test_cramers_v_perfect_association_is_one():
    # block-diagonal table -> perfect association -> V == 1.0
    conf = pd.DataFrame([[10, 0], [0, 10]])
    assert stats.cramers_v(conf) == pytest.approx(1.0, abs=1e-6)


def test_cramers_v_no_association_is_zero():
    conf = pd.DataFrame([[10, 10], [10, 10]])
    assert stats.cramers_v(conf) == pytest.approx(0.0, abs=1e-6)


def test_assoc_test_uses_fisher_on_thin_2x2():
    # a 2x2 with an expected cell < 5 must switch to Fisher's exact
    a = pd.Series(["x"] * 12 + ["y"] * 3)
    b = pd.Series((["p"] * 10 + ["q"] * 2) + (["p"] * 1 + ["q"] * 2))
    res = stats.assoc_test(a, b)
    assert res["test"] == "fisher"
    assert res["min_expected"] < 5
    assert "p" in res and 0.0 <= res["p"] <= 1.0


def test_assoc_test_uses_chi2_when_cells_are_fat():
    a = pd.Series((["x"] * 60 + ["y"] * 60))
    b = pd.Series((["p"] * 30 + ["q"] * 30) * 2)
    res = stats.assoc_test(a, b)
    assert res["test"] == "chi2"
    assert res["min_expected"] >= 5
    assert res["n"] == 120


def test_assoc_test_meaningful_flag():
    # strong association, fat cells -> meaningful True
    a = pd.Series(["x"] * 50 + ["y"] * 50)
    b = pd.Series(["p"] * 50 + ["q"] * 50)
    res = stats.assoc_test(a, b)
    assert res["meaningful"] is True
    # independent, fat cells -> V ~ 0 -> meaningful False
    a2 = pd.Series((["x"] * 50 + ["y"] * 50))
    b2 = pd.Series((["p", "q"] * 50))
    assert stats.assoc_test(a2, b2)["meaningful"] is False


def test_bootstrap_ci_is_deterministic():
    vals = np.arange(1, 101, dtype=float)
    a = stats.bootstrap_ci(vals, random_state=0)
    b = stats.bootstrap_ci(vals, random_state=0)
    assert a == b
    lo, hi, point = a
    assert lo < point < hi
    assert point == pytest.approx(vals.mean(), abs=1e-9)
