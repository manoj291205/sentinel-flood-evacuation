"""Immutable, pre-registered configuration for Sentinel-Agent V3 Phase 9."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


TRAINING_SPEC_VERSION = "v3-ppo-training-spec-v1"
TRAINING_GENERATOR_VERSION = "v3-ppo-train-generator-v1"
VALIDATION_GENERATOR_VERSION = "v3-ppo-validation-v1"
PERMUTATION_DIAGNOSTIC_VERSION = "v3-slot-permutation-diagnostic-v1"
PRIMARY_TRAINING_SEEDS = (1101, 2202, 3303, 4404, 5505)
VALIDATION_GENERATOR_SEEDS = tuple(range(930_000, 930_150))
GATE6_GENERATOR_SEED_RANGES = ((610_000, 610_119), (620_000, 620_119))


@dataclass(frozen=True)
class TrainingConfig:
    """The complete primary-run contract; changes require a new version."""

    spec_version: str = TRAINING_SPEC_VERSION
    algorithm: str = "sb3_contrib.MaskablePPO"
    policy: str = "MlpPolicy"
    net_arch: tuple[int, ...] = (256, 256)
    activation: str = "ReLU"
    max_zones: int = 6
    max_shelters: int = 9
    observation_dim: int = 384
    action_dim: int = 55
    wait_action: int = 54
    reward_config_id: str = "v3-reward-balanced-v1"
    safety_config_id: str = "v3-safety-v1"
    learning_rate: float = 3e-4
    n_steps: int = 1_250
    batch_size: int = 250
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    n_envs: int = 4
    total_timesteps: int = 250_000
    debug_timesteps: int = 20_000
    checkpoint_interval: int = 10_000
    validation_interval: int = 10_000
    validation_scenarios: int = 150
    device: str = "cpu"
    deterministic_validation: bool = True
    performance_early_stopping: bool = False
    invalid_validation_action_threshold: int = 0
    normalized_return_alarm: float = 0.05
    safe_population_alarm: float = 0.05

    def __post_init__(self) -> None:
        if self.spec_version != TRAINING_SPEC_VERSION:
            raise ValueError("Phase 9 configuration version may not be changed in place")
        if self.n_steps * self.n_envs % self.batch_size:
            raise ValueError("rollout size must be divisible by batch size")
        if self.total_timesteps % (self.n_steps * self.n_envs):
            raise ValueError("total timesteps must contain complete rollouts")
        if self.validation_interval % (self.n_steps * self.n_envs):
            raise ValueError("validation interval must align with complete rollouts")
        if self.checkpoint_interval != self.validation_interval:
            raise ValueError("checkpoint and validation cadence are frozen together")
        if len(PRIMARY_TRAINING_SEEDS) != 5:
            raise ValueError("exactly five primary training seeds are required")

    @property
    def rollout_size(self) -> int:
        return self.n_steps * self.n_envs

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["net_arch"] = list(self.net_arch)
        value["training_seeds"] = list(PRIMARY_TRAINING_SEEDS)
        value["training_generator_version"] = TRAINING_GENERATOR_VERSION
        value["validation_generator_version"] = VALIDATION_GENERATOR_VERSION
        value["permutation_diagnostic_version"] = PERMUTATION_DIAGNOSTIC_VERSION
        return value


FROZEN_TRAINING_CONFIG = TrainingConfig()


def representative_seed(scores: dict[int, float]) -> int:
    """Choose the seed closest to the five-seed validation median, then lower seed."""
    if set(scores) != set(PRIMARY_TRAINING_SEEDS):
        raise ValueError("representative selection requires all five primary seeds")
    ordered_values = sorted(scores.values())
    median = ordered_values[len(ordered_values) // 2]
    return min(scores, key=lambda seed: (abs(scores[seed] - median), seed))
