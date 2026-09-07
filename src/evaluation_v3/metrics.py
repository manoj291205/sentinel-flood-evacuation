"""Phase 1 metric, bootstrap, and decision-gate implementations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import numpy as np

from .config import FROZEN_PHASE10_CONFIG


def linear_quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0,1]")
    return float(np.quantile(np.asarray(values, dtype=float), probability, method="linear"))


def cvar_10(values: Sequence[float]) -> float:
    """Mean of exactly the lowest 10% empirical mass, fractionally weighted."""
    if not values:
        raise ValueError("CVaR requires at least one value")
    ordered = sorted(float(value) for value in values)
    mass = 0.1 * len(ordered)
    whole = int(math.floor(mass))
    fraction = mass - whole
    total = sum(ordered[:whole])
    if fraction:
        total += fraction * ordered[whole]
    return total / mass


def normalised_safe_utility(
    policy_returns: Sequence[float],
    lower_returns: Sequence[float],
    upper_returns: Sequence[float],
    *,
    epsilon_den: float = FROZEN_PHASE10_CONFIG.epsilon_den,
) -> float | None:
    if not (len(policy_returns) == len(lower_returns) == len(upper_returns)):
        raise ValueError("paired NSU inputs must have the same length")
    if not policy_returns:
        raise ValueError("NSU requires at least one evaluation unit")
    denominator = float(np.mean(upper_returns) - np.mean(lower_returns))
    if denominator <= epsilon_den:
        return None
    return float((np.mean(policy_returns) - np.mean(lower_returns)) / denominator)


def relative_exposure_reduction(policy: float, baseline: float) -> float | None:
    if baseline <= 0:
        return None
    return (baseline - policy) / baseline


def tail_nsu(
    policy_returns: Sequence[float],
    lower_returns: Sequence[float],
    baseline_returns: Sequence[float],
    *,
    epsilon_den: float = FROZEN_PHASE10_CONFIG.epsilon_den,
) -> float | None:
    denominator = cvar_10(baseline_returns) - cvar_10(lower_returns)
    if denominator <= epsilon_den:
        return None
    return (cvar_10(policy_returns) - cvar_10(lower_returns)) / denominator


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float | None
    lower: float | None
    upper: float | None
    valid_draws: int
    invalid_draws: int

    @property
    def invalid_fraction(self) -> float:
        total = self.valid_draws + self.invalid_draws
        return self.invalid_draws / total if total else 1.0

    def to_dict(self) -> dict[str, float | int | None]:
        return {
            "estimate": self.estimate,
            "lower": self.lower,
            "upper": self.upper,
            "valid_draws": self.valid_draws,
            "invalid_draws": self.invalid_draws,
            "invalid_fraction": self.invalid_fraction,
        }


def paired_cluster_bootstrap(
    rows: Sequence[object],
    statistic: Callable[[Sequence[object]], float | None],
    *,
    seed: int = FROZEN_PHASE10_CONFIG.bootstrap_seed,
    resamples: int = FROZEN_PHASE10_CONFIG.bootstrap_resamples,
) -> BootstrapInterval:
    """Resample the supplied scenario-cluster rows as indivisible paired units."""
    if not rows:
        raise ValueError("bootstrap requires scenario clusters")
    estimate = statistic(rows)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    invalid = 0
    for _ in range(resamples):
        indices = rng.integers(0, len(rows), size=len(rows))
        value = statistic([rows[int(index)] for index in indices])
        if value is None or not math.isfinite(value):
            invalid += 1
        else:
            values.append(float(value))
    if invalid / resamples > FROZEN_PHASE10_CONFIG.maximum_invalid_bootstrap_fraction:
        return BootstrapInterval(estimate, None, None, len(values), invalid)
    return BootstrapInterval(
        estimate,
        linear_quantile(values, 0.025),
        linear_quantile(values, 0.975),
        len(values),
        invalid,
    )


def two_level_ppo_bootstrap(
    seed_scenario_values: dict[int, Sequence[float]],
    baseline_values: Sequence[float],
    statistic: Callable[[Sequence[float], Sequence[float]], float | None],
    *,
    seed: int = FROZEN_PHASE10_CONFIG.bootstrap_seed,
    resamples: int = FROZEN_PHASE10_CONFIG.bootstrap_resamples,
) -> BootstrapInterval:
    """Resample training seeds, then paired scenario clusters (Phase 1 §7)."""
    training_seeds = sorted(seed_scenario_values)
    if not training_seeds or not baseline_values:
        raise ValueError("two-level bootstrap requires seeds and scenarios")
    scenario_count = len(baseline_values)
    if any(len(values) != scenario_count for values in seed_scenario_values.values()):
        raise ValueError("every training seed must cover every paired scenario")
    matrix = np.asarray([seed_scenario_values[item] for item in training_seeds], dtype=float)
    baseline = np.asarray(baseline_values, dtype=float)
    estimate = statistic(matrix.mean(axis=0), baseline)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    invalid = 0
    for _ in range(resamples):
        sampled_seed_rows = rng.integers(0, len(training_seeds), size=len(training_seeds))
        sampled_scenarios = rng.integers(0, scenario_count, size=scenario_count)
        policy = matrix[sampled_seed_rows][:, sampled_scenarios].mean(axis=0)
        value = statistic(policy, baseline[sampled_scenarios])
        if value is None or not math.isfinite(value):
            invalid += 1
        else:
            values.append(float(value))
    if invalid / resamples > FROZEN_PHASE10_CONFIG.maximum_invalid_bootstrap_fraction:
        return BootstrapInterval(estimate, None, None, len(values), invalid)
    return BootstrapInterval(
        estimate,
        linear_quantile(values, 0.025),
        linear_quantile(values, 0.975),
        len(values),
        invalid,
    )


def _supported(effect: float | None, interval: BootstrapInterval, threshold: float) -> bool:
    return bool(
        effect is not None
        and effect >= threshold
        and interval.lower is not None
        and interval.lower > 0.0
    )


def gate_passes(
    *,
    nsu_difference: float | None,
    nsu_interval: BootstrapInterval,
    exposure_reduction: float | None,
    exposure_interval: BootstrapInterval,
    tail_nsu_difference: float | None,
    tail_interval: BootstrapInterval,
    ppo_unsafe_rate: float,
    baseline_unsafe_rate: float,
    unsafe_interval: BootstrapInterval,
) -> tuple[bool, tuple[str, ...]]:
    benefits = []
    if _supported(nsu_difference, nsu_interval, FROZEN_PHASE10_CONFIG.material_nsu):
        benefits.append("NSU_PRACTICAL")
    if _supported(
        exposure_reduction,
        exposure_interval,
        FROZEN_PHASE10_CONFIG.material_exposure_reduction,
    ):
        benefits.append("EXPOSURE")
    if _supported(
        tail_nsu_difference,
        tail_interval,
        FROZEN_PHASE10_CONFIG.material_tail_nsu,
    ):
        benefits.append("TAIL_NSU")
    safety_ok = ppo_unsafe_rate <= baseline_unsafe_rate
    if ppo_unsafe_rate or baseline_unsafe_rate:
        safety_ok = safety_ok and unsafe_interval.upper is not None and unsafe_interval.upper <= 0
    return bool(benefits and safety_ok), tuple(benefits)


def decide_rl_usefulness(
    *,
    combined_gate: bool,
    stratum_gates: Iterable[bool],
    tail_gate: bool,
    stress_gates: Iterable[bool],
    supported_safety_regression: bool,
) -> str:
    """Return exactly the Phase 1 §10 YES/NO/MIXED vocabulary."""
    if supported_safety_regression:
        return "NO"
    if combined_gate:
        return "YES"
    if tail_gate or any(stratum_gates) or any(stress_gates):
        return "MIXED"
    return "NO"
