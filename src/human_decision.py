"""Offline human-decision and audit helpers for the Sentinel-Agent V3 demo.

The module composes existing simulator, safety, and planner components. It performs no
network calls and does not persist audit records beyond the caller-managed session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Callable

from src.planners import PlannerDecision, RiskGreedyPlanner, build_planner_input
from src.safety import ActionSafetyEvaluation, SafetySnapshot, evaluate_action, evaluate_actions
from src.sim import (
    HIGH,
    LOW,
    MEDIUM,
    DispatchAction,
    EpisodeState,
    ScenarioV3,
    StochasticSimulator,
    WaitAction,
)
from src.sim.configs import UncertaintyConfig, get_uncertainty_config
from src.sim.events import SimulationAction
from src.sim.generator import generate_gate6_scenario
from src.sim.transition import TransitionResult

DEMO_GENERATOR_SEED = 620000
DEMO_SUITE_KIND = "practical"
DEMO_PLANNER_LABEL = "Risk-Greedy"
DEMO_DEFAULT_UNCERTAINTY = MEDIUM.config_id
DEMO_UNCERTAINTY_OPTIONS = (LOW.config_id, MEDIUM.config_id, HIGH.config_id)


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


def build_demo_runtime(
    uncertainty: str | UncertaintyConfig = DEMO_DEFAULT_UNCERTAINTY,
) -> tuple[ScenarioV3, StochasticSimulator]:
    """Create one deterministic, existing Gate 6 practical scenario."""
    scenario = generate_gate6_scenario(DEMO_GENERATOR_SEED, DEMO_SUITE_KIND)
    return scenario, StochasticSimulator(scenario, get_uncertainty_config(uncertainty))


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


def progress_snapshot(state: EpisodeState) -> dict[str, int]:
    """Return the three population ledgers plotted by the session playback UI."""
    return {
        "timestep": state.current_timestep,
        "safe_population": state.people_safely_arrived,
        "remaining_population": state.population_remaining,
        "in_transit_population": state.people_in_transit,
    }


def timeline_entries(
    record: dict[str, object], transition: TransitionResult | None
) -> list[dict[str, object]]:
    """Render actual human and simulator events without inventing demo events."""
    entries = [
        {
            "timestep": record["timestep"],
            "event_type": f"HUMAN_{record['decision']}",
            "event_id": record["audit_id"],
            "zone_id": None,
            "shelter_id": None,
            "route_id": None,
            "people": None,
            "description": (
                f"recommended={record['recommended_action']}; "
                f"executed={record['executed_action']}"
            ),
        }
    ]
    if transition is None:
        return entries
    for event in transition.audit_records:
        entries.append(
            {
                "timestep": event.timestep,
                "event_type": event.event_type.value,
                "event_id": event.event_id,
                "zone_id": event.zone_id,
                "shelter_id": event.shelter_id,
                "route_id": event.route_id,
                "people": event.people,
                "description": (
                    event.message or event.reason_code or event.event_type.value
                ),
            }
        )
    return entries


def session_summary(
    audit_records: list[dict[str, object]], state: EpisodeState
) -> dict[str, int]:
    """Compute the live session summary from audit outcomes and simulator state."""
    executed = [row for row in audit_records if row["executed_action"] != "NONE"]
    return {
        "decisions_made": len(audit_records),
        "accepted_recommendations": sum(row["decision"] == "ACCEPT" for row in audit_records),
        "overrides": sum(row["decision"] == "OVERRIDE" for row in audit_records),
        "rejected_recommendations": sum(row["decision"] == "REJECT" for row in audit_records),
        "population_safely_evacuated": state.people_safely_arrived,
        "population_remaining": state.population_remaining,
        "population_in_transit": state.people_in_transit,
        "unsafe_actions_executed": sum(
            row["mechanical_validity"] != "PASS" or row["safety_result"] != "PASS"
            for row in executed
        ),
    }


def _compact_state(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def apply_human_decision(
    context: DecisionContext,
    simulator: StochasticSimulator,
    *,
    decision: HumanDecision | str,
    evidence: EvidenceReference,
    audit_sequence: int,
    generator_seed: int = DEMO_GENERATOR_SEED,
    selected_action: SimulationAction | None = None,
    human_reason: str = "",
    audit_metadata: dict[str, object] | None = None,
    now: Callable[[], datetime] | None = None,
) -> tuple[dict[str, object], TransitionResult | None]:
    """Validate, optionally execute, and return one session-scoped audit record."""
    choice = HumanDecision(decision)
    note = human_reason
    if audit_sequence < 1:
        raise HumanDecisionError("audit sequence must be positive")
    if simulator.prepared_state_for_debug() != context.state:
        raise HumanDecisionError("decision context is stale; obtain a current recommendation")
    if choice in {HumanDecision.OVERRIDE, HumanDecision.REJECT} and not note.strip():
        raise HumanDecisionError(f"{choice.value} requires a short human reason")
    timestamp = (now or (lambda: datetime.now(timezone.utc)))()
    if timestamp.tzinfo is None:
        raise HumanDecisionError("audit timestamp must include a timezone")
    standard_fields = {
        "audit_id",
        "timestamp",
        "scenario_id",
        "generator_seed",
        "scenario_seed",
        "uncertainty_regime",
        "uncertainty_config_id",
        "timestep",
        "planner",
        "recommended_action",
        "decision",
        "executed_action",
        "mechanical_validity",
        "safety_result",
        "source_zone_state",
        "destination_shelter_state",
        "human_reason",
        "evidence_source",
        "evidence_page",
        "evidence_chunk_id",
    }
    collisions = sorted(standard_fields & set(audit_metadata or {}))
    if collisions:
        raise HumanDecisionError(
            f"audit metadata cannot replace standard field(s): {', '.join(collisions)}"
        )

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

    state_action = executed_action or context.recommendation.action
    if isinstance(state_action, DispatchAction):
        source = context.state.zone(state_action.zone_id)
        destination = context.state.shelter(state_action.shelter_id)
        assert source is not None and destination is not None
        source_state = _compact_state({
            "zone_id": source.zone_id,
            "population_remaining": source.population_remaining,
            "flood_severity_current": source.flood_severity_current,
        })
        destination_state = _compact_state({
            "shelter_id": destination.shelter_id,
            "status_current": destination.status_current.value,
            "capacity_total": destination.capacity_total,
            "occupancy_current": destination.occupancy_current,
            "capacity_reserved": destination.capacity_reserved,
            "capacity_available": destination.capacity_available,
            "flood_severity_current": destination.flood_severity_current,
        })
    else:
        source_state = "NONE"
        destination_state = "NONE"

    transition = None
    if executed_action is not None:
        transition = simulator.step(executed_action)
        if not transition.accepted:
            raise RuntimeError("a deterministically allowed action was rejected by the simulator")

    record: dict[str, object] = {
        "audit_id": f"AUDIT-{audit_sequence:04d}",
        "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
        "scenario_id": context.scenario.scenario_id,
        "generator_seed": generator_seed,
        "scenario_seed": context.scenario.seed,
        "uncertainty_regime": simulator.config.level.value,
        "uncertainty_config_id": simulator.config.config_id,
        "timestep": context.state.current_timestep,
        "planner": (DEMO_PLANNER_LABEL if context.recommendation.planner_name == "risk_greedy"
                    else context.recommendation.planner_name),
        "recommended_action": action_key(context.recommendation.action),
        "decision": choice.value,
        "executed_action": action_key(executed_action) if executed_action else "NONE",
        "mechanical_validity": "PASS" if evaluation.mechanically_valid else "FAIL",
        "safety_result": "PASS" if evaluation.final_allowed else "FAIL",
        "source_zone_state": source_state,
        "destination_shelter_state": destination_state,
        "human_reason": note,
        "evidence_source": evidence.source_id,
        "evidence_page": evidence.page,
        "evidence_chunk_id": evidence.chunk_id,
    }
    if audit_metadata:
        record.update(audit_metadata)
    return record, transition


__all__ = [
    "DEMO_GENERATOR_SEED",
    "DEMO_DEFAULT_UNCERTAINTY",
    "DEMO_PLANNER_LABEL",
    "DEMO_UNCERTAINTY_OPTIONS",
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
    "progress_snapshot",
    "recommended_batch_size",
    "route_for_action",
    "session_summary",
    "timeline_entries",
]
