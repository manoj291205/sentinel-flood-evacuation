"""Observable-only common interface for practical Gate 6 planners."""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any, Protocol

from src.safety import SafetySnapshot, get_safety_config
from src.sim.configs import UncertaintyConfig
from src.sim.events import DispatchAction, SimulationAction
from src.sim.schemas import ScenarioV3
from src.sim.state import EpisodeState


@dataclass(frozen=True)
class CandidateScore:
    action: SimulationAction
    total: float
    components: tuple[tuple[str, float], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "total": self.total,
            "components": dict(self.components),
        }


@dataclass(frozen=True)
class PlannerInput:
    """Detached public input; notably contains no scenario seed or simulator."""

    scenario_id: str
    current_timestep: int
    timestep_minutes: float
    horizon_steps: int
    vehicle_capacity: int
    observation: dict[str, Any]
    safety_snapshot: SafetySnapshot
    uncertainty_config: UncertaintyConfig
    max_destination_hazard: float = 0.70  # not serialised: legacy to_dict() is unchanged

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "current_timestep": self.current_timestep,
            "timestep_minutes": self.timestep_minutes,
            "horizon_steps": self.horizon_steps,
            "vehicle_capacity": self.vehicle_capacity,
            "observation": copy.deepcopy(self.observation),
            "safety_snapshot": self.safety_snapshot.to_dict(),
            "uncertainty_config": self.uncertainty_config.to_dict(),
        }


@dataclass(frozen=True)
class PlannerDecision:
    action: SimulationAction
    planner_name: str
    planner_version: str
    decision_latency_ns: int
    candidate_scores: tuple[CandidateScore, ...] = ()
    nodes_evaluated: int = 0
    model_transitions: int = 0
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "planner_name": self.planner_name,
            "planner_version": self.planner_version,
            "decision_latency_ns": self.decision_latency_ns,
            "candidate_scores": [item.to_dict() for item in self.candidate_scores],
            "nodes_evaluated": self.nodes_evaluated,
            "model_transitions": self.model_transitions,
            "explanation": self.explanation,
        }


class PracticalPlanner(Protocol):
    name: str
    version: str

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision: ...


def build_planner_input(
    scenario: ScenarioV3,
    state: EpisodeState,
    safety_snapshot: SafetySnapshot,
    uncertainty_config: UncertaintyConfig,
) -> PlannerInput:
    """Build the future-policy-equivalent public view without private seed/context."""
    return PlannerInput(
        scenario_id=scenario.scenario_id,
        current_timestep=state.current_timestep,
        timestep_minutes=scenario.time.timestep_minutes,
        horizon_steps=scenario.time.horizon_steps,
        vehicle_capacity=scenario.fleet.vehicle_capacity,
        observation=copy.deepcopy(state.to_policy_observation()),
        safety_snapshot=safety_snapshot,
        uncertainty_config=uncertainty_config,
        max_destination_hazard=get_safety_config(
            safety_snapshot.safety_config_id
        ).max_destination_hazard,
    )


def allowed_dispatches(planner_input: PlannerInput) -> tuple[DispatchAction, ...]:
    return tuple(
        action
        for action, allowed in zip(
            planner_input.safety_snapshot.canonical_actions,
            planner_input.safety_snapshot.allowed_mask,
        )
        if allowed and isinstance(action, DispatchAction)
    )


def allowed_actions(planner_input: PlannerInput) -> tuple[SimulationAction, ...]:
    return tuple(
        action
        for action, allowed in zip(
            planner_input.safety_snapshot.canonical_actions,
            planner_input.safety_snapshot.allowed_mask,
        )
        if allowed
    )


def maps(planner_input: PlannerInput):
    observation = planner_input.observation
    return (
        {item["zone_id"]: item for item in observation["zones"]},
        {item["shelter_id"]: item for item in observation["shelters"]},
        {
            (item["source_zone_id"], item["destination_shelter_id"]): item
            for item in observation["routes"]
        },
    )


def timed(start_ns: int) -> int:
    return time.perf_counter_ns() - start_ns
