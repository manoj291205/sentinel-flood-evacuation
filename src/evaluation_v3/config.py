"""Immutable pre-results configuration for the Phase 10 evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PHASE10_SPEC_VERSION = "v3-phase10-eval-spec-v1"
HELDOUT_GENERATOR_VERSION = "v3-heldout-generator-v1"
STRESS_GENERATOR_VERSION = "v3-stress-generator-v1"
PERMUTATION_VERSION = "v3-heldout-slot-permutation-v1"
HELDOUT_SEEDS = tuple(range(1_000_000, 1_000_600))
PERMUTATION_BASE_SEEDS = tuple(range(1_020_000, 1_020_100))
PERMUTATION_SEEDS = tuple(range(1_030_000, 1_030_500))
STRESS_SEEDS = tuple(range(1_040_000, 1_040_250))
RANDOM_POLICY_SEEDS = (73_001, 73_002, 73_003, 73_004, 73_005)
PPO_TRAINING_SEEDS = (1_101, 2_202, 3_303, 4_404, 5_505)
UNCERTAINTY_IDS = ("v3-low-v1", "v3-medium-v1", "v3-high-v1")
STRESS_TYPES = (
    "sudden_flood_surge",
    "route_closure_cascade",
    "shelter_failure",
    "demand_shift",
    "longer_travel_lags",
)
PRACTICAL_POLICIES = (
    "random_valid",
    "nearest_safe",
    "risk_greedy",
    "lookahead_k2",
    "lookahead_k3",
    "sampled_mpc",
)


@dataclass(frozen=True)
class Phase10Config:
    spec_version: str = PHASE10_SPEC_VERSION
    heldout_generator_version: str = HELDOUT_GENERATOR_VERSION
    stress_generator_version: str = STRESS_GENERATOR_VERSION
    permutation_version: str = PERMUTATION_VERSION
    heldout_scenarios: int = 600
    scenarios_per_uncertainty: int = 200
    replication_id: int = 0
    stress_scenarios: int = 250
    stress_per_type: int = 50
    permutation_bases: int = 100
    permutations_per_base: int = 5
    bootstrap_seed: int = 10_010_007
    bootstrap_resamples: int = 10_000
    epsilon_den: float = 0.01
    maximum_invalid_bootstrap_fraction: float = 0.05
    material_nsu: float = 0.02
    material_exposure_reduction: float = 0.05
    material_tail_nsu: float = 0.02
    latency_budget_ms: float = 100.0
    latency_minimum_decisions: int = 1_000
    representative_ppo_seed: int = 4_404
    principal_comparator: str = "risk_greedy"
    observation_matched_policy: str = "observation_matched_greedy"
    hard_safety: bool = True
    deterministic_ppo: bool = True

    def __post_init__(self) -> None:
        if self.spec_version != PHASE10_SPEC_VERSION:
            raise ValueError("Phase 10 specification version is immutable")
        if self.heldout_scenarios != len(HELDOUT_SEEDS):
            raise ValueError("held-out seed count does not match the frozen suite")
        if self.stress_scenarios != len(STRESS_SEEDS):
            raise ValueError("stress seed count does not match the frozen suite")
        if self.permutation_bases != len(PERMUTATION_BASE_SEEDS):
            raise ValueError("permutation base count does not match the frozen suite")
        if self.bootstrap_resamples < 10_000:
            raise ValueError("Phase 1 requires at least 10,000 bootstrap draws")
        if self.principal_comparator != "risk_greedy":
            raise ValueError("the pre-test Gate 6 principal comparator is frozen")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.update(
            {
                "heldout_seeds": list(HELDOUT_SEEDS),
                "permutation_base_seeds": list(PERMUTATION_BASE_SEEDS),
                "permutation_seeds": list(PERMUTATION_SEEDS),
                "stress_seeds": list(STRESS_SEEDS),
                "random_policy_seeds": list(RANDOM_POLICY_SEEDS),
                "ppo_training_seeds": list(PPO_TRAINING_SEEDS),
                "uncertainty_ids": list(UNCERTAINTY_IDS),
                "stress_types": list(STRESS_TYPES),
                "practical_policies": list(PRACTICAL_POLICIES),
            }
        )
        return value


FROZEN_PHASE10_CONFIG = Phase10Config()
