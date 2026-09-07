"""Gymnasium wrapper for the validated sequential stochastic V3 simulator."""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.safety import V3_SAFETY_V1, evaluate_actions
from src.sim import ScenarioV3, StochasticSimulator, TerminalReason

from .action_space import DecodedAction, FixedActionMap
from .config import (
    DEFAULT_ENV_CONFIG,
    EnvV3Config,
)
from .observation import OBSERVATION_DIM, build_observation, observation_dimension
from .rewards import (
    REWARD_CONFIGS,
    ZERO_PLACEHOLDER_REWARD,
    FrozenV3RewardProvider,
    RewardProvider,
    reward_breakdown_to_info,
)
from .scenario_source import (
    FixedScenarioSource,
    ResetContext,
    ScenarioSelection,
    ScenarioSource,
)


class EvacuationEnvV3(gym.Env[np.ndarray, int]):
    """Fixed-space interface with explicit placeholder or frozen reward provider."""

    metadata = {"render_modes": []}
    reward_range = (0.0, 0.0)

    def __init__(
        self,
        scenario: ScenarioV3 | None = None,
        *,
        scenario_source: ScenarioSource | None = None,
        uncertainty_config: str = "v3-medium-v1",
        config: EnvV3Config = DEFAULT_ENV_CONFIG,
        reward_provider: RewardProvider | None = None,
    ) -> None:
        super().__init__()
        if (scenario is None) == (scenario_source is None):
            raise ValueError("provide exactly one of scenario or scenario_source")
        self.config = config
        self.scenario_source = (
            FixedScenarioSource(scenario) if scenario is not None else scenario_source
        )
        assert self.scenario_source is not None
        self.uncertainty_config = uncertainty_config
        self.action_space = spaces.Discrete(config.action_count)
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(observation_dimension(config),),
            dtype=np.float32,
        )
        self._reward_provider = reward_provider or ZERO_PLACEHOLDER_REWARD
        self.reward_range = (
            (
                self._reward_provider.config.episode_return_min,
                self._reward_provider.config.episode_return_max,
            )
            if isinstance(self._reward_provider, FrozenV3RewardProvider)
            else (0.0, 0.0)
        )
        self._episode_index = 0
        self._auto_replication_id = 0
        self._scenario: ScenarioV3 | None = None
        self._simulator: StochasticSimulator | None = None
        self._action_mapping: FixedActionMap | None = None
        self._public_observation: dict[str, Any] | None = None
        self._done = False
        self._invalid_action_attempts = 0

    @property
    def scenario(self) -> ScenarioV3:
        if self._scenario is None:
            raise RuntimeError("environment must be reset before scenario access")
        return self._scenario

    @property
    def action_mapping(self) -> FixedActionMap:
        if self._action_mapping is None:
            raise RuntimeError("environment must be reset before action-map access")
        return self._action_mapping

    @property
    def reward_spec_version(self) -> str:
        return self._reward_provider.version

    @property
    def training_ready(self) -> bool:
        if not isinstance(self._reward_provider, FrozenV3RewardProvider):
            return False
        if self._reward_provider.version not in REWARD_CONFIGS or self._scenario is None:
            return False
        if self.current_state.initial_evacuation_population <= 0:
            return False
        return (
            self.action_space.n == self.config.action_count
            and self.observation_space.shape == (observation_dimension(self.config),)
            and self.observation_space.dtype == np.dtype(np.float32)
            and np.all(self.observation_space.low == 0.0)
            and np.all(self.observation_space.high == 1.0)
            and V3_SAFETY_V1.config_id == "v3-safety-v1"
        )

    def assert_training_ready(self) -> None:
        if not self.training_ready:
            raise RuntimeError(
                "environment is not training-ready: reset a positive-population scenario "
                "with a recognized frozen non-placeholder reward provider"
            )

    @property
    def current_state(self):
        """Current physical state for tests/evaluation; never part of policy output."""
        if self._simulator is None:
            raise RuntimeError("environment must be reset before state access")
        if self._done:
            return self._simulator.state
        return self._simulator.prepared_state_for_debug()

    def _safety_snapshot(self):
        if self._simulator is None:
            raise RuntimeError("environment must be reset before mask access")
        return evaluate_actions(
            self.scenario,
            self._simulator.prepared_state_for_debug(),
            V3_SAFETY_V1,
            enable_hard_safety=self.config.enable_hard_safety,
        )

    def action_masks(self) -> np.ndarray:
        """Direct sb3-contrib-compatible Boolean action mask."""
        if self._done:
            return np.zeros(self.config.action_count, dtype=bool)
        return self.action_mapping.fixed_mask(self._safety_snapshot()).copy()

    def _observation(self) -> np.ndarray:
        if self._public_observation is None:
            raise RuntimeError("environment must be reset before observation access")
        mask = self.action_masks()
        return build_observation(
            self.scenario,
            self._public_observation,
            self.action_mapping,
            any_dispatch_available=bool(mask[: self.config.dispatch_slots].any()),
            config=self.config,
        )

    def _base_info(self, allowed_action_count: int) -> dict[str, Any]:
        state = self.current_state
        return {
            "scenario_id": self.scenario.scenario_id,
            "environment_config_id": self.config.config_id,
            "zone_count": len(self.scenario.zones),
            "shelter_count": len(self.scenario.shelters),
            "zone_slot_to_id": list(self.action_mapping.zone_slot_to_id),
            "shelter_slot_to_id": list(self.action_mapping.shelter_slot_to_id),
            "current_timestep": state.current_timestep,
            "terminal_reason": (
                state.terminal_reason.value if state.terminal_reason else None
            ),
            "safety_config_id": V3_SAFETY_V1.config_id,
            "hard_safety_enabled": self.config.enable_hard_safety,
            "allowed_action_count": allowed_action_count,
            "reward_defined": self._reward_provider.defined,
            "reward_spec_version": self._reward_provider.version,
            "training_ready": self.training_ready,
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        reset_context = ResetContext(gym_seed=seed, episode_index=self._episode_index)
        selection = self.scenario_source.next_scenario(reset_context)
        active_uncertainty = self.uncertainty_config
        if isinstance(selection, ScenarioSelection):
            scenario = selection.scenario
            active_uncertainty = selection.uncertainty_config
        else:
            scenario = selection
        if not isinstance(scenario, ScenarioV3):
            raise TypeError("scenario source must return ScenarioV3")
        replication_id = int(seed) if seed is not None else self._auto_replication_id
        if seed is None:
            self._auto_replication_id += 1
        self._episode_index += 1
        self._scenario = scenario
        self._action_mapping = FixedActionMap(scenario, self.config)
        self._simulator = StochasticSimulator(
            scenario,
            active_uncertainty,
            replication_id=replication_id,
        )
        self._public_observation = self._simulator.observe()
        self._done = False
        self._invalid_action_attempts = 0
        mask = self.action_masks()
        observation = self._observation()
        info = self._base_info(int(mask.sum()))
        return observation, info

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._simulator is None:
            raise RuntimeError("environment must be reset before step")
        if self._done:
            raise RuntimeError("episode is done; call reset() before another step")
        requested: DecodedAction = self.action_mapping.decode_action(action)
        mask_before = self.action_masks()
        invalid = not bool(mask_before[requested.index])
        if invalid:
            executed = self.action_mapping.decode_action(self.config.wait_index)
            self._invalid_action_attempts += 1
        else:
            executed = requested
        semantic = executed.semantic
        if semantic is None:
            raise AssertionError("masked fallback failed to produce WAIT")
        previous_state = self.current_state
        result = self._simulator.step(semantic)
        if not result.accepted:
            raise RuntimeError("environment mask/fallback disagrees with simulator mechanics")

        terminal_reason = result.terminal_reason
        terminated = terminal_reason is TerminalReason.ALL_EVACUATED
        truncated = terminal_reason is TerminalReason.HORIZON_REACHED
        self._done = terminated or truncated
        if self._done:
            self._public_observation = result.state.to_policy_observation()
        else:
            self._public_observation = self._simulator.observe()
        next_mask = self.action_masks()
        observation = self._observation()
        breakdown = self._reward_provider.calculate(
            previous_state,
            result,
            result.state,
            self.scenario,
        )
        reward = float(breakdown.total_reward)
        info = self._base_info(int(next_mask.sum()))
        info.update(
            {
                "semantic_requested_action": requested.to_dict(),
                "semantic_executed_action": executed.to_dict(),
                "invalid_action_attempted": invalid,
                "invalid_action_attempt_count": self._invalid_action_attempts,
                "requested_action": requested.index,
                "executed_action": executed.index,
                "people_dispatched": result.people_dispatched,
                "arrivals_processed": len(result.arrivals_processed),
                "allowed_action_count_before": int(mask_before.sum()),
                "safe_population_fraction": (
                    result.state.people_safely_arrived
                    / result.state.initial_evacuation_population
                    if result.state.initial_evacuation_population > 0
                    else 0.0
                ),
                "evacuation_complete": (
                    result.state.people_safely_arrived
                    == result.state.initial_evacuation_population
                ),
                "audit_events": [
                    {
                        "event_type": record.event_type.value,
                        "timestep": record.timestep,
                        "reason_code": record.reason_code,
                    }
                    for record in result.audit_records
                ],
            }
        )
        info.update(reward_breakdown_to_info(breakdown))
        return observation, reward, terminated, truncated, info

    def render(self) -> None:
        return None


assert OBSERVATION_DIM == 384
