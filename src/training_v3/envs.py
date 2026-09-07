"""Training-only scenario streams and vector environments for Phase 9."""

from __future__ import annotations

from dataclasses import dataclass

from stable_baselines3.common.vec_env import DummyVecEnv

from src.env_v3 import EvacuationEnvV3, FrozenV3RewardProvider, ResetContext, ScenarioSelection

from .config import FROZEN_TRAINING_CONFIG
from .generator import generate_ppo_scenario, training_episode_generator_seed


@dataclass(frozen=True)
class ProceduralTrainingScenarioSource:
    training_seed: int
    environment_rank: int

    def next_scenario(self, reset_context: ResetContext) -> ScenarioSelection:
        generator_seed = training_episode_generator_seed(
            self.training_seed,
            self.environment_rank,
            reset_context.episode_index,
        )
        generated = generate_ppo_scenario(generator_seed)
        return ScenarioSelection(
            scenario=generated.scenario,
            uncertainty_config=generated.uncertainty_config_id,
        )


def make_training_env(training_seed: int, environment_rank: int) -> EvacuationEnvV3:
    env = EvacuationEnvV3(
        scenario_source=ProceduralTrainingScenarioSource(training_seed, environment_rank),
        reward_provider=FrozenV3RewardProvider(),
    )
    return env


def make_training_vec_env(training_seed: int) -> DummyVecEnv:
    config = FROZEN_TRAINING_CONFIG
    return DummyVecEnv(
        [
            (lambda rank=rank: make_training_env(training_seed, rank))
            for rank in range(config.n_envs)
        ]
    )
