"""Scenario-provider boundary without defining the future training distribution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from src.sim import ScenarioV3


@dataclass(frozen=True)
class ResetContext:
    gym_seed: int | None
    episode_index: int


class ScenarioSource(Protocol):
    def next_scenario(self, reset_context: ResetContext) -> ScenarioV3: ...


@dataclass(frozen=True)
class FixedScenarioSource:
    scenario: ScenarioV3

    def next_scenario(self, reset_context: ResetContext) -> ScenarioV3:
        return self.scenario


@dataclass(frozen=True)
class CallableScenarioSource:
    provider: Callable[[ResetContext], ScenarioV3]

    def next_scenario(self, reset_context: ResetContext) -> ScenarioV3:
        scenario = self.provider(reset_context)
        if not isinstance(scenario, ScenarioV3):
            raise TypeError("scenario provider must return ScenarioV3")
        return scenario
