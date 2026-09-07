"""Frozen observable risk-greedy planner with inspectable components."""

from __future__ import annotations

import time

from src.sim.events import WAIT, DispatchAction

from .base import CandidateScore, PlannerDecision, PlannerInput, allowed_dispatches, maps, timed

RISK_GREEDY_WEIGHTS = {
    "source_urgency": 0.30,
    "destination_safety": 0.20,
    "capacity_usefulness": 0.25,
    "travel": 0.10,
    "closure_safety": 0.10,
    "travel_certainty": 0.05,
}


def score_dispatch(planner_input: PlannerInput, action: DispatchAction) -> CandidateScore:
    zones, shelters, routes = maps(planner_input)
    zone = zones[action.zone_id]
    shelter = shelters[action.shelter_id]
    route = routes[(action.zone_id, action.shelter_id)]
    expected = float(route["expected_travel_time_minutes"])
    uncertainty = float(route["travel_time_uncertainty_minutes"] or 0.0)
    useful = min(
        planner_input.vehicle_capacity,
        int(zone["population_remaining"]),
        int(shelter["capacity_available"]),
    )
    components = {
        "source_urgency": float(zone["flood_severity_current"]),
        "destination_safety": 1.0 - float(shelter["flood_severity_current"]),
        "capacity_usefulness": useful / planner_input.vehicle_capacity,
        "travel": 1.0
        - min(expected / (planner_input.horizon_steps * planner_input.timestep_minutes), 1.0),
        "closure_safety": 1.0 - float(route["estimated_closure_probability"]),
        "travel_certainty": 1.0 - min(uncertainty / expected, 1.0),
    }
    total = sum(RISK_GREEDY_WEIGHTS[name] * value for name, value in components.items())
    return CandidateScore(action, total, tuple(components.items()))


class RiskGreedyPlanner:
    name = "risk_greedy"
    version = "risk-greedy-v1"

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision:
        started = time.perf_counter_ns()
        scores = tuple(score_dispatch(planner_input, action) for action in allowed_dispatches(planner_input))
        if scores:
            best = max(score.total for score in scores)
            action = next(score.action for score in scores if score.total == best)
            explanation = "Maximum frozen observable risk-greedy score."
        else:
            action = WAIT
            explanation = "No dispatch is currently allowed."
        return PlannerDecision(
            action=action,
            planner_name=self.name,
            planner_version=self.version,
            decision_latency_ns=timed(started),
            candidate_scores=scores,
            explanation=explanation,
        )
