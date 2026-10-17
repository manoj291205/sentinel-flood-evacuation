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

    def __init__(self, seed=620000, regime="v3-medium-v1", *, graph=None,
                 certified=False, params_id="v4-cert-v1", recertify=False):
        if recertify and not certified:
            raise ValueError("recertify requires a certified session")
        self.certified = certified
        self.params_id = params_id
        self.recertify = recertify
        self.reset(seed, regime, graph=graph)

    def reset(self, seed=620000, regime="v3-medium-v1", *, graph=None):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("scenario generator seed must be a non-negative integer")
        self.seed = seed
        self._gate_cache = None
        self.recert_log = []
        self._recert_histories = {}
        self._rechecked_timestep = None
        if self.certified:
            from src.actuation.commands import InMemorySink
            from src.certify.gate import CertifiedGate
            from src.certify.ledger import SimLedgerAdapter
            from src.certify.params import get_cert_params
            from src.geospatial.v4_runtime import build_v4_runtime

            (self.scenario, self.simulator, self.graph, self.overlay,
             self.world) = build_v4_runtime(regime, generator_seed=seed, graph=graph)
            self.ledger = SimLedgerAdapter(self.simulator)
            self.sink = InMemorySink()
            self.gate = CertifiedGate(
                self.scenario, self.graph, self.world, get_cert_params(self.params_id),
                self.ledger, sink=self.sink, world_id=regime,
            )
        else:
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

    def certificates(self):
        return self.ledger.certificates() if self.certified else []

    def _pending(self):
        """The current step's gate evaluation: (state, result, inputs), cached per timestep."""
        from src.safety import evaluate_actions

        self.simulator.observe()
        state = self.simulator.prepared_state_for_debug()
        cached = self._gate_cache
        if cached is None or cached[0] != state.current_timestep:
            base = evaluate_actions(self.scenario, state)
            result, inputs = self.gate.evaluate(state, self.overlay.road_state, base)
            self._gate_cache = cached = (state.current_timestep, result, inputs)
        return state, cached[1], cached[2]

    def certification(self):
        """Pending (CertificationResult, CertificateInputs), or None if uncertified or terminal. Never commits."""
        if not self.certified or self.simulator.state.terminal:
            return None
        self._ensure_rechecked()
        _, result, inputs = self._pending()
        return result, inputs

    def _certified_context(self):
        from src.human_decision import DecisionContext, _evaluation_for
        from src.planners import CertifiedPlanner, build_planner_input
        from src.safety import evaluate_actions

        state, result, inputs = self._pending()
        snapshot = evaluate_actions(
            self.scenario, state, certifier=lambda sc, st, cands: self.gate.certificate_map(result)
        )
        planner_input = build_planner_input(self.scenario, state, snapshot, self.simulator.config)
        recommendation = CertifiedPlanner(lambda _: result).choose_action(planner_input)
        evaluation = _evaluation_for(snapshot, recommendation.action)
        return DecisionContext(self.scenario, state, snapshot, recommendation, evaluation)

    def context(self):
        if self.simulator.state.terminal:
            return None
        if self.certified:
            self._ensure_rechecked()
            return self._certified_context()
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
                "MIGRATION" if kind == "GROUP_MIGRATED" else
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

    def _ensure_rechecked(self):
        """Phase 26 re-check of groups on the road: lazily, once per timestep, before the gate evaluates.

        Phase 27 order (observe -> recertify -> evaluate -> commit); see spec Amendment 2026-10-17.
        """
        if not (self.recertify and self.certified) or self.simulator.state.terminal:
            return
        from src.certify.recertify import RecertPolicy, recertify_in_transit

        self.simulator.observe()
        state = self.simulator.prepared_state_for_debug()
        if state.current_timestep == self._rechecked_timestep:
            return
        decisions = recertify_in_transit(
            self.gate, state, self.overlay.road_state, self.simulator.transit_plans(),
            self._recert_histories, RecertPolicy(),
        )
        self._gate_cache = None  # the ledger may have changed; the gate evaluates afterwards
        self._rechecked_timestep = state.current_timestep
        for d in decisions:
            verdict = getattr(d.keep_verdict, "value", d.keep_verdict)
            self.recert_log.append({
                "timestep": state.current_timestep, "group_id": d.event_id, "action": d.action,
                "verdict": verdict, "lower": d.keep_lower, "upper": d.keep_upper,
                "new_shelter_id": d.new_shelter_id,
                "cert_id": (d.certificate or {}).get("cert_id"),
            })
        self._capture_events(self.state)

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
        executor = self.simulator
        if self.certified:
            executor = _GateExecutor(self, decision, reason)
        record, transition = apply_human_decision(
            context, executor, decision=decision, evidence=evidence,
            audit_sequence=len(self.audit) + 1, generator_seed=self.seed,
            selected_action=selected_action, human_reason=reason,
            audit_metadata=metadata,
        )
        if self.certified and decision == "REJECT":
            transition = executor.hold()  # a rejection is committed as a HOLD certificate
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


class _GateExecutor:
    """Stands in for the simulator in ``apply_human_decision``: every step goes through the gate."""

    def __init__(self, session, decision, reason):
        self._session, self._reason = session, reason
        self._decision = decision if isinstance(decision, str) else decision.value

    @property
    def config(self):
        return self._session.simulator.config

    def prepared_state_for_debug(self):
        return self._session.simulator.prepared_state_for_debug()

    def _commit(self, key):
        session = self._session
        _, result, inputs = session._gate_cache
        operator = {"decision": self._decision, "actor": "session-operator", "reason": self._reason}
        session.gate.commit(result, inputs, operator=operator, selected_key=key)
        session._gate_cache = None
        return session.ledger.last_transition

    def step(self, action):
        from src.human_decision import action_key

        return self._commit(action_key(action))

    def hold(self):
        return self._commit("WAIT")
