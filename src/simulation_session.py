"""Session orchestration only: existing V3 simulator, mask, planner and human audit.

No experiments, network clients, models, or disk writes run in this module.
"""
from __future__ import annotations

import csv
from io import StringIO
import json

from src.geospatial import audit_route_metadata, build_geospatial_demo_runtime
from src.human_decision import (
    EvidenceReference, HumanDecisionError,
    apply_human_decision, current_decision_context, progress_snapshot,
    session_summary, timeline_entries,
)
from src.sim import DispatchAction, WaitAction


class SimulationSession:
    """Caller-owned live state; never put an instance in a shared Streamlit cache."""

    def __init__(self, seed=620000, regime="v3-medium-v1", *, graph=None):
        self.reset(seed, regime, graph=graph)

    def reset(self, seed=620000, regime="v3-medium-v1", *, graph=None):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("scenario generator seed must be a non-negative integer")
        self.seed = seed
        self.scenario, self.simulator, self.graph, self.overlay = build_geospatial_demo_runtime(
            regime, graph=graph, generator_seed=seed,
        )
        self.audit = []
        self.timeline = []
        self.population_history = []
        self.hazard_history = []
        self.last_transition = None
        self._event_cursor = 0
        self._observe()

    @property
    def state(self):
        if self.simulator.state.terminal:
            return self.simulator.state
        return self.simulator.prepared_state_for_debug()

    def context(self):
        if self.simulator.state.terminal:
            return None
        return current_decision_context(self.scenario, self.simulator)

    def _capture_events(self, state):
        # Prepared-state events include arrivals and current hazard/graph changes.
        # Consuming the append-only ledger prevents one-step lag and duplicate events.
        for event in state.audit_log[self._event_cursor:]:
            kind = event.event_type.value
            category = (
                "ARRIVAL" if kind == "ARRIVAL_PROCESSED" else
                "DISPATCH" if kind in {"DISPATCH_CREATED", "TRAVEL_TIME_REALIZED"} else
                "HAZARD" if kind == "FLOOD_STATE_UPDATED" else
                "ROUTE" if kind == "ROUTE_CLOSED" else
                "SHELTER" if kind.startswith("SHELTER_") else "SYSTEM"
            )
            self.timeline.append({
                **event.to_dict(), "category": category,
                "description": event.message or event.reason_code or kind,
            })
        self._event_cursor = len(state.audit_log)

    def _capture_population(self, state, phase):
        snapshot = {**progress_snapshot(state), "phase": phase}
        if self.population_history and all(
            self.population_history[-1][key] == value
            for key, value in snapshot.items() if key != "phase"
        ):
            return
        self.population_history.append({**snapshot, "sample": len(self.population_history)})

    def _observe(self):
        if not self.simulator.state.terminal:
            self.simulator.observe()
        state = self.state
        self._capture_events(state)
        self._capture_population(state, "Current observation")
        for zone in state.zones:
            self.hazard_history.append({
                "timestep": state.current_timestep, "zone": zone.zone_id,
                "hazard": zone.flood_severity_current,
            })

    def decide(self, decision, evidence: EvidenceReference, *, selected_action=None, reason=""):
        context = self.context()
        if context is None:
            raise HumanDecisionError("episode is complete; reset to make another decision")
        audited_action = selected_action if decision == "OVERRIDE" else context.recommendation.action
        road_state = self.overlay.road_state
        metadata = audit_route_metadata(self.graph, road_state, audited_action)
        recommended = audit_route_metadata(self.graph, road_state, context.recommendation.action)
        metadata.update({f"recommended_{key}": value for key, value in recommended.items()})
        # A rejection has recommendation provenance but no executed graph path.
        if decision == "REJECT":
            metadata.update(audit_route_metadata(self.graph, road_state, WaitAction()))
        record, transition = apply_human_decision(
            context, self.simulator, decision=decision, evidence=evidence,
            audit_sequence=len(self.audit) + 1, generator_seed=self.seed,
            selected_action=selected_action, human_reason=reason,
            audit_metadata=metadata,
        )
        self.audit.append(record)
        self.timeline.extend({**row, "category": "HUMAN"} for row in timeline_entries(record, None))
        if transition is not None:
            self.last_transition = transition
            self._capture_events(transition.state)
            self._capture_population(transition.state, "After dispatch / before next observation")
            self._observe()
        return record, transition

    def summary(self):
        state = self.state
        return {
            **session_summary(self.audit, state),
            "initial_population": state.initial_evacuation_population,
            "unfinished_population": state.population_remaining + state.people_in_transit,
            "dispatches": len(state.dispatch_events),
            "elapsed_timesteps": state.current_timestep,
            "terminal": state.terminal,
            "terminal_reason": state.terminal_reason.value if state.terminal_reason else None,
        }

    def export_csv(self):
        output = StringIO(newline="")
        if self.audit:
            writer = csv.DictWriter(output, fieldnames=list(self.audit[0]))
            writer.writeheader()
            writer.writerows(self.audit)
        else:
            output.write("audit_id,timestamp,decision,executed_action\r\n")
        return output.getvalue()

    def export_json(self):
        return json.dumps({
            "scenario_id": self.scenario.scenario_id,
            "generator_seed": self.seed, "scenario_seed": self.scenario.seed,
            "uncertainty_regime": self.simulator.config.level.value,
            "uncertainty_config_id": self.simulator.config.config_id,
            "simulator": "StochasticSimulator (V3 Phase 3/4)",
            "scenario_schema_version": self.scenario.schema_version,
            "horizon_steps": self.scenario.time.horizon_steps,
            "timestep_minutes": self.scenario.time.timestep_minutes,
            "graph_version": self.graph.graph_version,
            "graph_fingerprint": self.graph.graph_fingerprint,
            "summary": self.summary(), "audit": self.audit,
            "population_history": self.population_history,
            "hazard_history": self.hazard_history, "timeline": self.timeline,
        }, indent=2)

    def route_rows(self):
        # The adapter is authoritative: a graph path alone does not override an
        # absorbing route-level simulator closure.
        from src.geospatial import path_for_action
        rows = []
        for route in self.state.routes:
            path = path_for_action(self.graph, self.overlay.road_state,
                                   DispatchAction(route.source_zone_id, route.destination_shelter_id))
            rows.append({
                "Source": route.source_zone_id, "Destination": route.destination_shelter_id,
                "Reachable": route.reachable_current,
                "Status": "OPEN" if route.reachable_current else "UNREACHABLE",
                "Distance (m)": path.distance_m if route.reachable_current else None,
                "Travel (min)": route.travel_time_current,
                "Route hazard": route.route_hazard_proxy,
                "Closed at": route.closed_at_timestep,
            })
        return rows
