"""Offline human-decision and audit helpers for the Sentinel-Agent V3 demo.

The module composes existing simulator, safety, and planner components. It performs no
network calls and does not persist audit records beyond the caller-managed session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from src.planners import PlannerDecision, RiskGreedyPlanner, build_planner_input
from src.safety import ActionSafetyEvaluation, SafetySnapshot, evaluate_action, evaluate_actions
from src.sim import (
    MEDIUM,
    DispatchAction,
    EpisodeState,
    ScenarioV3,
    StochasticSimulator,
    WaitAction,
)
from src.sim.events import SimulationAction
from src.sim.generator import generate_gate6_scenario
from src.sim.transition import TransitionResult

DEMO_GENERATOR_SEED = 620000
DEMO_SUITE_KIND = "practical"
DEMO_PLANNER_LABEL = "Risk-Greedy"


class HumanDecision(str, Enum):
    ACCEPT = "ACCEPT"
    OVERRIDE = "OVERRIDE"
    REJECT = "REJECT"


class HumanDecisionError(ValueError):
    """Raised when a proposed human decision violates the demo contract."""


@dataclass(frozen=True)
class EvidenceReference:
    source_id: str
    page: int
    chunk_id: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.chunk_id or self.page < 1:
            raise ValueError("evidence source, positive page, and chunk ID are required")


@dataclass(frozen=True)
class DecisionContext:
    scenario: ScenarioV3
    state: EpisodeState
    snapshot: SafetySnapshot
    recommendation: PlannerDecision
    recommendation_evaluation: ActionSafetyEvaluation


def build_demo_runtime() -> tuple[ScenarioV3, StochasticSimulator]:
    """Create one deterministic, existing Gate 6 practical scenario."""
    scenario = generate_gate6_scenario(DEMO_GENERATOR_SEED, DEMO_SUITE_KIND)
    return scenario, StochasticSimulator(scenario, MEDIUM)


def _evaluation_for(
    snapshot: SafetySnapshot, action: SimulationAction
) -> ActionSafetyEvaluation:
    try:
        index = snapshot.canonical_actions.index(action)
    except ValueError as exc:
        raise HumanDecisionError("action is not in the current canonical action set") from exc
    return snapshot.evaluations[index]


def current_decision_context(
    scenario: ScenarioV3, simulator: StochasticSimulator
) -> DecisionContext:
    """Observe current state and run the unchanged safety mask and Risk-Greedy planner."""
    simulator.observe()
    state = simulator.prepared_state_for_debug()
    snapshot = evaluate_actions(scenario, state)
    planner_input = build_planner_input(scenario, state, snapshot, simulator.config)
    recommendation = RiskGreedyPlanner().choose_action(planner_input)
    evaluation = _evaluation_for(snapshot, recommendation.action)
    if not evaluation.final_allowed:
        raise HumanDecisionError("no executable recommendation remains; reset the demo")
    return DecisionContext(scenario, state, snapshot, recommendation, evaluation)


def action_key(action: SimulationAction) -> str:
    if isinstance(action, WaitAction):
        return "WAIT"
    return f"{action.zone_id}->{action.shelter_id}"


def action_label(action: SimulationAction) -> str:
    if isinstance(action, WaitAction):
        return "WAIT"
    return f"Dispatch {action.zone_id} → {action.shelter_id}"


def recommended_batch_size(context: DecisionContext) -> int:
    action = context.recommendation.action
    if not isinstance(action, DispatchAction):
        return 0
    zone = context.state.zone(action.zone_id)
    shelter = context.state.shelter(action.shelter_id)
    assert zone is not None and shelter is not None
    return min(
        context.scenario.fleet.vehicle_capacity,
        zone.population_remaining,
        shelter.capacity_available,
    )


def allowed_override_actions(context: DecisionContext) -> tuple[SimulationAction, ...]:
    """Expose only currently allowed alternatives and never the original recommendation."""
    return tuple(
        action
        for action in context.snapshot.allowed_actions
        if action != context.recommendation.action
    )


def route_for_action(context: DecisionContext, action: SimulationAction) -> dict | None:
    if not isinstance(action, DispatchAction):
        return None
    return next(
        route
        for route in context.state.to_policy_observation()["routes"]
        if route["source_zone_id"] == action.zone_id
        and route["destination_shelter_id"] == action.shelter_id
    )


def _validated_execution(
    context: DecisionContext, action: SimulationAction
) -> ActionSafetyEvaluation:
    evaluation = evaluate_action(context.scenario, context.state, action)
    if not evaluation.mechanically_valid:
        raise HumanDecisionError("mechanically invalid actions cannot be executed")
    if not evaluation.final_allowed:
        raise HumanDecisionError("unsafe actions cannot be executed")
    return evaluation


def apply_human_decision(
    context: DecisionContext,
    simulator: StochasticSimulator,
    *,
    decision: HumanDecision | str,
    evidence: EvidenceReference,
    audit_sequence: int,
    selected_action: SimulationAction | None = None,
    human_reason: str = "",
    now: Callable[[], datetime] | None = None,
) -> tuple[dict[str, object], TransitionResult | None]:
    """Validate, optionally execute, and return one session-scoped audit record."""
    choice = HumanDecision(decision)
    note = human_reason.strip()
    if audit_sequence < 1:
        raise HumanDecisionError("audit sequence must be positive")
    if simulator.prepared_state_for_debug() != context.state:
        raise HumanDecisionError("decision context is stale; obtain a current recommendation")
    if choice in {HumanDecision.OVERRIDE, HumanDecision.REJECT} and not note:
        raise HumanDecisionError(f"{choice.value} requires a short human reason")
    timestamp = (now or (lambda: datetime.now(timezone.utc)))()
    if timestamp.tzinfo is None:
        raise HumanDecisionError("audit timestamp must include a timezone")

    if choice is HumanDecision.ACCEPT:
        if selected_action is not None:
            raise HumanDecisionError("ACCEPT executes the recommendation, not an alternative")
        executed_action: SimulationAction | None = context.recommendation.action
        evaluation = _validated_execution(context, executed_action)
    elif choice is HumanDecision.OVERRIDE:
        if selected_action is None:
            raise HumanDecisionError("OVERRIDE requires an alternative action")
        if selected_action == context.recommendation.action:
            raise HumanDecisionError("OVERRIDE must select a different action")
        if selected_action not in allowed_override_actions(context):
            raise HumanDecisionError("override action is not in the current allowed action mask")
        executed_action = selected_action
        evaluation = _validated_execution(context, executed_action)
    else:
        executed_action = None
        evaluation = context.recommendation_evaluation

    transition = None
    if executed_action is not None:
        transition = simulator.step(executed_action)
        if not transition.accepted:
            raise RuntimeError("a deterministically allowed action was rejected by the simulator")

    record: dict[str, object] = {
        "audit_id": f"AUDIT-{audit_sequence:04d}",
        "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
        "scenario_id": context.scenario.scenario_id,
        "timestep": context.state.current_timestep,
        "planner": DEMO_PLANNER_LABEL,
        "recommended_action": action_key(context.recommendation.action),
        "decision": choice.value,
        "executed_action": action_key(executed_action) if executed_action else "NONE",
        "mechanical_validity": "PASS" if evaluation.mechanically_valid else "FAIL",
        "safety_result": "PASS" if evaluation.final_allowed else "FAIL",
        "human_reason": note,
        "evidence_source": evidence.source_id,
        "evidence_page": evidence.page,
        "evidence_chunk_id": evidence.chunk_id,
    }
    return record, transition


__all__ = [
    "DEMO_GENERATOR_SEED",
    "DEMO_PLANNER_LABEL",
    "DecisionContext",
    "EvidenceReference",
    "HumanDecision",
    "HumanDecisionError",
    "action_key",
    "action_label",
    "allowed_override_actions",
    "apply_human_decision",
    "build_demo_runtime",
    "current_decision_context",
    "recommended_batch_size",
    "route_for_action",
]
