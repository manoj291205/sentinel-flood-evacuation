"""Highest-current-hazard source followed by nearest safe destination."""

from __future__ import annotations

import time

from src.sim.events import WAIT

from .base import PlannerDecision, PlannerInput, allowed_dispatches, maps, timed


class NearestSafePlanner:
    name = "nearest_safe"
    version = "nearest-safe-v1"

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision:
        started = time.perf_counter_ns()
        dispatches = allowed_dispatches(planner_input)
        if not dispatches:
            action = WAIT
            explanation = "No dispatch is currently allowed."
        else:
            zones, _, routes = maps(planner_input)
            max_hazard = max(zones[item.zone_id]["flood_severity_current"] for item in dispatches)
            source = next(
                item.zone_id
                for item in dispatches
                if zones[item.zone_id]["flood_severity_current"] == max_hazard
            )
            source_actions = [item for item in dispatches if item.zone_id == source]
            action = min(
                source_actions,
                key=lambda item: routes[(item.zone_id, item.shelter_id)][
                    "expected_travel_time_minutes"
                ],
            )
            explanation = "Highest current source hazard, then lowest expected travel."
        return PlannerDecision(
            action=action,
            planner_name=self.name,
            planner_version=self.version,
            decision_latency_ns=timed(started),
            explanation=explanation,
        )
