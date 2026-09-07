"""Pure implementation of the frozen Phase 8A V3 reward specification."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.sim import EpisodeState, ScenarioV3, TerminalReason, TransitionResult

from .config import PLACEHOLDER_REWARD_VERSION

REWARD_MODELING_ASSUMPTION_DISCLAIMER = (
    "SYNTHETIC PROJECT MODELING CHOICES — NOT OFFICIAL DISASTER-MANAGEMENT UTILITY WEIGHTS."
)


@dataclass(frozen=True)
class RewardConfig:
    config_id: str
    version: int
    safe_weight: float
    exposure_weight: float
    travel_weight: float
    terminal_weight: float
    description: str
    episode_return_min: float
    episode_return_max: float
    disclaimer: str = REWARD_MODELING_ASSUMPTION_DISCLAIMER

    def __post_init__(self) -> None:
        if not self.config_id or self.version < 1 or not self.description:
            raise ValueError("reward config identity, version, and description are required")
        weights = (
            self.safe_weight,
            self.exposure_weight,
            self.travel_weight,
            self.terminal_weight,
        )
        if any(not math.isfinite(value) or value < 0 for value in weights):
            raise ValueError("reward weights must be finite and nonnegative")
        if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("reward weights must sum to one")
        if not (
            math.isfinite(self.episode_return_min)
            and math.isfinite(self.episode_return_max)
            and self.episode_return_min < self.episode_return_max
        ):
            raise ValueError("reward return range must be finite and increasing")
        if self.disclaimer != REWARD_MODELING_ASSUMPTION_DISCLAIMER:
            raise ValueError("the reward modeling-assumption disclaimer may not be removed")

    def to_dict(self) -> dict[str, str | int | float]:
        return {
            "config_id": self.config_id,
            "version": self.version,
            "safe_weight": self.safe_weight,
            "exposure_weight": self.exposure_weight,
            "travel_weight": self.travel_weight,
            "terminal_weight": self.terminal_weight,
            "description": self.description,
            "episode_return_min": self.episode_return_min,
            "episode_return_max": self.episode_return_max,
            "disclaimer": self.disclaimer,
        }


BALANCED_REWARD = RewardConfig(
    config_id="v3-reward-balanced-v1",
    version=1,
    safe_weight=0.55,
    exposure_weight=0.30,
    travel_weight=0.05,
    terminal_weight=0.10,
    description="Primary balanced safe-arrival, current-exposure, travel, and horizon reward.",
    episode_return_min=-0.45,
    episode_return_max=0.55,
)
EVACUATION_REWARD = RewardConfig(
    config_id="v3-reward-evacuation-v1",
    version=1,
    safe_weight=0.65,
    exposure_weight=0.20,
    travel_weight=0.05,
    terminal_weight=0.10,
    description="Sensitivity configuration emphasizing completed safe arrivals.",
    episode_return_min=-0.35,
    episode_return_max=0.65,
)
EXPOSURE_REWARD = RewardConfig(
    config_id="v3-reward-exposure-v1",
    version=1,
    safe_weight=0.50,
    exposure_weight=0.40,
    travel_weight=0.05,
    terminal_weight=0.05,
    description="Sensitivity configuration emphasizing rapid exposure reduction.",
    episode_return_min=-0.50,
    episode_return_max=0.50,
)
REWARD_CONFIGS = {
    config.config_id: config
    for config in (BALANCED_REWARD, EVACUATION_REWARD, EXPOSURE_REWARD)
}


def get_reward_config(config: str | RewardConfig) -> RewardConfig:
    if isinstance(config, RewardConfig):
        frozen = REWARD_CONFIGS.get(config.config_id)
        if frozen != config:
            raise ValueError("reward provider requires an exact recognized frozen config")
        return frozen
    try:
        return REWARD_CONFIGS[config]
    except KeyError as exc:
        known = ", ".join(sorted(REWARD_CONFIGS))
        raise ValueError(f"unknown reward config {config!r}; choose {known}") from exc


@dataclass(frozen=True)
class RewardBreakdown:
    reward_config_id: str
    reward_defined: bool
    safe_gain: float
    exposure: float
    travel_burden: float
    terminal_unfinished: float
    weighted_safe: float
    weighted_exposure: float
    weighted_travel: float
    weighted_terminal: float
    total_reward: float

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"reward breakdown {name} must be finite")

    def to_dict(self) -> dict[str, str | bool | float]:
        return {
            "reward_config_id": self.reward_config_id,
            "reward_defined": self.reward_defined,
            "safe_gain": self.safe_gain,
            "exposure": self.exposure,
            "travel_burden": self.travel_burden,
            "terminal_unfinished": self.terminal_unfinished,
            "weighted_safe": self.weighted_safe,
            "weighted_exposure": self.weighted_exposure,
            "weighted_travel": self.weighted_travel,
            "weighted_terminal": self.weighted_terminal,
            "total_reward": self.total_reward,
        }


class RewardProvider:
    version: str
    defined: bool

    def calculate(
        self,
        previous_state: EpisodeState,
        transition_result: TransitionResult,
        current_state: EpisodeState,
        scenario: ScenarioV3,
    ) -> RewardBreakdown:
        raise NotImplementedError


class ZeroPlaceholderReward(RewardProvider):
    version = PLACEHOLDER_REWARD_VERSION
    defined = False

    def calculate(
        self,
        previous_state: EpisodeState,
        transition_result: TransitionResult,
        current_state: EpisodeState,
        scenario: ScenarioV3,
    ) -> RewardBreakdown:
        return RewardBreakdown(
            reward_config_id=self.version,
            reward_defined=False,
            safe_gain=0.0,
            exposure=0.0,
            travel_burden=0.0,
            terminal_unfinished=0.0,
            weighted_safe=0.0,
            weighted_exposure=0.0,
            weighted_travel=0.0,
            weighted_terminal=0.0,
            total_reward=0.0,
        )


ZERO_PLACEHOLDER_REWARD = ZeroPlaceholderReward()


def combine_reward_components(
    config: str | RewardConfig,
    *,
    safe_gain: float,
    exposure: float,
    travel_burden: float,
    terminal_unfinished: float,
) -> RewardBreakdown:
    """Apply frozen weights to already-normalized physical components."""
    selected = get_reward_config(config)
    components = {
        "safe_gain": safe_gain,
        "exposure": exposure,
        "travel_burden": travel_burden,
        "terminal_unfinished": terminal_unfinished,
    }
    for name, value in components.items():
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be finite and in [0,1]")
    weighted_safe = selected.safe_weight * safe_gain
    weighted_exposure = -selected.exposure_weight * exposure
    weighted_travel = -selected.travel_weight * travel_burden
    weighted_terminal = -selected.terminal_weight * terminal_unfinished
    return RewardBreakdown(
        reward_config_id=selected.config_id,
        reward_defined=True,
        safe_gain=safe_gain,
        exposure=exposure,
        travel_burden=travel_burden,
        terminal_unfinished=terminal_unfinished,
        weighted_safe=weighted_safe,
        weighted_exposure=weighted_exposure,
        weighted_travel=weighted_travel,
        weighted_terminal=weighted_terminal,
        total_reward=(
            weighted_safe + weighted_exposure + weighted_travel + weighted_terminal
        ),
    )


class FrozenV3RewardProvider(RewardProvider):
    """Calculate only physical components frozen in V3_REWARD_SPEC.md."""

    defined = True

    def __init__(self, config: str | RewardConfig = BALANCED_REWARD) -> None:
        self.config = get_reward_config(config)
        self.version = self.config.config_id

    def calculate(
        self,
        previous_state: EpisodeState,
        transition_result: TransitionResult,
        current_state: EpisodeState,
        scenario: ScenarioV3,
    ) -> RewardBreakdown:
        if transition_result.state != current_state:
            raise ValueError("transition result and current reward state must match")
        if previous_state.scenario_id != scenario.scenario_id:
            raise ValueError("previous state and scenario must match")
        if current_state.scenario_id != scenario.scenario_id:
            raise ValueError("current state and scenario must match")
        population = current_state.initial_evacuation_population
        if population < 0:
            raise ValueError("initial evacuation population must be nonnegative")
        if population == 0:
            return RewardBreakdown(
                reward_config_id=self.version,
                reward_defined=True,
                safe_gain=0.0,
                exposure=0.0,
                travel_burden=0.0,
                terminal_unfinished=0.0,
                weighted_safe=0.0,
                weighted_exposure=0.0,
                weighted_travel=0.0,
                weighted_terminal=0.0,
                total_reward=0.0,
            )

        horizon = scenario.time.horizon_steps
        horizon_minutes = scenario.time.timestep_minutes * horizon
        arrived = sum(event.people for event in transition_result.arrivals_processed)
        safe_gain = arrived / population
        raw_exposure = sum(
            zone.population_remaining * zone.flood_severity_current
            for zone in current_state.zones
        )
        exposure = raw_exposure / (population * horizon)
        travel_burden = sum(
            (event.people / population)
            * (
                event.realized_travel_time_minutes
                / (event.realized_travel_time_minutes + horizon_minutes)
            )
            for event in transition_result.events_created
        )
        terminal_unfinished = 0.0
        if current_state.terminal_reason is TerminalReason.HORIZON_REACHED:
            terminal_unfinished = (
                current_state.population_remaining + current_state.people_in_transit
            ) / population

        return combine_reward_components(
            self.config,
            safe_gain=safe_gain,
            exposure=exposure,
            travel_burden=travel_burden,
            terminal_unfinished=terminal_unfinished,
        )


def reward_breakdown_to_info(breakdown: RewardBreakdown) -> dict[str, Any]:
    return {
        "reward_defined": breakdown.reward_defined,
        "reward_spec_version": breakdown.reward_config_id,
        "reward_total": breakdown.total_reward,
        "reward_safe_gain": breakdown.safe_gain,
        "reward_exposure": breakdown.exposure,
        "reward_travel": breakdown.travel_burden,
        "reward_terminal": breakdown.terminal_unfinished,
        "reward_weighted_safe": breakdown.weighted_safe,
        "reward_weighted_exposure": breakdown.weighted_exposure,
        "reward_weighted_travel": breakdown.weighted_travel,
        "reward_weighted_terminal": breakdown.weighted_terminal,
        "reward_breakdown": breakdown.to_dict(),
    }
