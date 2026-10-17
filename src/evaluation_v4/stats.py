"""Statistics for the pre-registered Phase 27 analysis (V4_EVALUATION_PREREG.md)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy.stats import binom


def paired_bootstrap_ci(values: Sequence[float], *, resamples: int, seed: int) -> tuple[float, float]:
    """2.5 / 97.5 percentiles of the means of ``resamples`` resamples (numpy default_rng(seed))."""
    data = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(data), size=(resamples, len(data)))
    means = data[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p = min(1, 2 * Binom.cdf(min(b, c), b + c, 0.5)); 1.0 when b + c = 0."""
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, 2.0 * binom.cdf(min(b, c), n, 0.5)))


def stratified_bootstrap_ci(groups: dict[str, Sequence[float]], *, resamples: int, seed: int) -> tuple[float, float]:
    """Percentile CI of the pooled mean when each stratum (regime) is resampled within itself."""
    arrays = [np.asarray(groups[k], dtype=float) for k in sorted(groups)]
    rng = np.random.default_rng(seed)
    total = sum(len(a) for a in arrays)
    sums = np.zeros(resamples)
    for a in arrays:
        idx = rng.integers(0, len(a), size=(resamples, len(a)))
        sums += a[idx].sum(axis=1)
    lo, hi = np.percentile(sums / total, [2.5, 97.5])
    return float(lo), float(hi)


def clopper_pearson_upper(successes: int, n: int, alpha: float = 0.05) -> float:
    """One-sided upper bound at level ``alpha``."""
    from scipy.stats import beta

    return 1.0 if successes >= n else float(beta.ppf(1 - alpha, successes + 1, n - successes))
