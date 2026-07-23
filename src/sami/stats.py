"""Association tests (chi-square / Fisher) + effect size + bootstrap CI."""
from __future__ import annotations
from typing import Callable
import numpy as np
import pandas as pd
from scipy import stats as _sps


def cramers_v(confusion: pd.DataFrame) -> float:
    """Bias-corrected Cramér's V for a contingency table. 0 = independent, 1 = perfect."""
    arr = np.asarray(confusion, dtype=float)
    n = arr.sum()
    if n == 0:
        return float("nan")
    chi2 = _sps.chi2_contingency(arr, correction=False)[0]
    phi2 = chi2 / n
    r, k = arr.shape
    phi2corr = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rcorr = r - (r - 1) ** 2 / (n - 1)
    kcorr = k - (k - 1) ** 2 / (n - 1)
    denom = min(kcorr - 1, rcorr - 1)
    if denom <= 0:
        return 0.0
    return float(np.sqrt(phi2corr / denom))


def assoc_test(a: pd.Series, b: pd.Series) -> dict:
    """Contingency-table association test with effect size.

    Drops rows where either value is NaN, builds the crosstab, runs chi-square
    (Fisher's exact for a 2x2 with an expected cell < 5), and reports Cramér's V.
    `meaningful` is True only when V >= 0.1 AND the min expected cell >= 5 — so a
    strong association on a thin 2x2 (min_expected < 5) is conservatively reported
    as not meaningful even when Fisher's p is tiny. Note `stat` is always the
    uncorrected chi-square even when `test == "fisher"`; the reported `p` for a
    Fisher case comes from `fisher_exact`, not from `stat`.
    """
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    conf = pd.crosstab(df["a"], df["b"])
    n = int(conf.to_numpy().sum())
    chi2, p, dof, expected = _sps.chi2_contingency(conf, correction=False)
    min_expected = float(expected.min())
    test = "chi2"
    if conf.shape == (2, 2) and min_expected < 5:
        _, p = _sps.fisher_exact(conf.to_numpy())
        test = "fisher"
    v = cramers_v(conf)
    return {
        "stat": float(chi2), "p": float(p), "dof": int(dof), "test": test,
        "cramers_v": v, "min_expected": min_expected, "n": n,
        "meaningful": bool(v >= 0.1 and min_expected >= 5),
    }


def bootstrap_ci(values, statistic: Callable = np.mean, n_boot: int = 1000,
                 ci: float = 0.95, random_state: int = 0) -> tuple[float, float, float]:
    """Deterministic percentile bootstrap CI. Returns (lo, hi, point_estimate)."""
    vals = np.asarray(pd.Series(values).dropna(), dtype=float)
    point = float(statistic(vals))
    if len(vals) == 0:
        return (float("nan"), float("nan"), point)
    rng = np.random.default_rng(random_state)
    boots = np.array([
        statistic(rng.choice(vals, size=len(vals), replace=True))
        for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    lo, hi = np.quantile(boots, [alpha, 1 - alpha])
    return (float(lo), float(hi), point)
