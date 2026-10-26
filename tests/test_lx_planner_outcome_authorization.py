"""Prospective planner, V4 outcome and command-boundary regressions; no providers."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_providers(monkeypatch):
    import socket

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    def blocked(*args, **kwargs):
        raise AssertionError("provider/network access forbidden in these regressions")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


def planner_case(mode):
    from src.planners import build_planner_input
    from src.safety import evaluate_actions
    from src.sim import MEDIUM, StochasticSimulator, WAIT
    from src.sim.generator import generate_gate6_scenario

    scenario = generate_gate6_scenario(610000, "exact")
    if mode == "disabled":
        scenario = replace(scenario, fleet=replace(
            scenario.fleet, evacuation_enabled=False, dispatches_per_timestep=0))
    if mode == "empty":
        scenario = replace(scenario, zones=tuple(replace(z, population_total=0,
            population_initial_remaining=0, vulnerable_population=0, medical_priority_population=0)
            for z in scenario.zones))
    simulator = StochasticSimulator(scenario, MEDIUM)
    simulator.observe()
    state = simulator.prepared_state_for_debug()
    if mode == "exhausted":
        state = replace(state, dispatches_used_this_timestep=state.dispatch_limit_per_timestep)
    if mode == "safety_disabled":
        state = replace(state, shelters=tuple(replace(s, flood_severity_current=.8,
                                                     forecast_mean_next=.8)
                                             for s in state.shelters))

    def deny_all(scenario, state, actions):
        return {f"{a.zone_id}->{a.shelter_id}": SimpleNamespace(
            verdict=SimpleNamespace(value="INFEASIBLE"), lower=0., upper=.5, n=32)
            for a in actions}

    snapshot = evaluate_actions(scenario, state,
        enable_hard_safety=mode != "safety_disabled",
        certifier=deny_all if mode == "certified" else None)
    if mode == "partial":
        only = next(a for a in reversed(snapshot.allowed_actions) if a != WAIT)

        def allow_one(scenario, state, actions):
            return {f"{a.zone_id}->{a.shelter_id}": SimpleNamespace(
                verdict=SimpleNamespace(value="FEASIBLE" if a == only else "INFEASIBLE"),
                lower=.99 if a == only else 0., upper=1., n=32) for a in actions}

        snapshot = evaluate_actions(scenario, state, certifier=allow_one)
    return build_planner_input(scenario, state, snapshot, MEDIUM)


@pytest.mark.parametrize("name", ["LookaheadK2Planner", "LookaheadK3Planner", "SampledMPCPlanner"])
@pytest.mark.parametrize("mode", ["disabled", "exhausted", "certified", "partial", "normal", "safety_disabled", "empty"])
def test_root_recommendations_obey_authoritative_mask(name, mode):
    import src.planners as planners

    value = planner_case(mode)
    planner = getattr(planners, name)()
    decision = planner.choose_action(value)
    assert decision.action in value.safety_snapshot.allowed_actions
    assert decision.planner_version.endswith("-v2")
    assert {c.action for c in decision.candidate_scores} == set(value.safety_snapshot.allowed_actions)


@pytest.mark.parametrize("mode", ["disabled", "exhausted", "safety_disabled"])
def test_projected_state_resets_slots_but_preserves_fleet_and_safety(mode):
    from src.planners.model import ModelState
    from src.sim import WAIT

    root = ModelState.from_input(planner_case(mode))
    child = root.advance(WAIT)
    dispatches = [a for a in child.allowed_actions() if a != WAIT]
    assert bool(dispatches) is (mode != "disabled")
    if mode == "safety_disabled":
        assert all(s.severity >= .7 for s in child.shelters)
    if mode == "disabled":
        invalid = next(a for a in root.actions if a != WAIT)
        with pytest.raises(ValueError, match="allowed"):
            child.advance(invalid)


@pytest.mark.parametrize("name", ["LookaheadK2Planner", "LookaheadK3Planner", "SampledMPCPlanner"])
def test_current_threshold_can_further_restrict_a_supplied_mask(name):
    import src.planners as planners
    from src.sim import WAIT

    value = replace(planner_case("normal"), max_destination_hazard=0.)
    decision = getattr(planners, name)().choose_action(value)
    assert decision.action == WAIT
    assert {c.action for c in decision.candidate_scores} == {WAIT}


def outcome_state(safe, stranded, unsafe, overflow, remaining=0):
    from src.sim import ScenarioV3, initialize_episode
    from src.sim.events import DispatchEvent, DispatchStatus

    raw = json.loads((ROOT / "data/scenarios_v3/example_v3_scenario.json").read_text(encoding="utf-8"))
    raw["zones"], raw["shelters"] = raw["zones"][:1], raw["shelters"][:1]
    zone, shelter = raw["zones"][0], raw["shelters"][0]
    population = safe + stranded + unsafe + overflow + remaining
    zone["population_total"] = zone["population_initial_remaining"] = population
    for key in ("vulnerable_population", "medical_priority_population"):
        zone[key] = min(zone[key], population)
    raw["network"]["routes"] = [r for r in raw["network"]["routes"]
        if r["source_zone_id"] == zone["zone_id"] and r["destination_shelter_id"] == shelter["shelter_id"]]
    scenario = ScenarioV3.from_dict(raw)
    state = initialize_episode(scenario)
    events = []
    for count, status in ((safe, DispatchStatus.ARRIVED), (stranded, DispatchStatus.STRANDED),
                          (unsafe, DispatchStatus.ARRIVAL_UNSAFE), (overflow, DispatchStatus.ARRIVAL_OVERFLOW)):
        if count:
            events.append(DispatchEvent(f"dispatch-{len(events)+1:06d}", zone["zone_id"],
                shelter["shelter_id"], count, 0, 1, state.routes[0].route_id, 1,
                10., 10., 1., "v4-probe", status))
    state = replace(state, current_timestep=1, uncertainty_config_id="v4-probe", forecast_for_timestep=2,
        zones=(replace(state.zones[0], population_remaining=remaining),),
        shelters=(replace(state.shelters[0], occupancy_current=state.shelters[0].occupancy_current+safe),),
        dispatch_events=tuple(events), next_dispatch_sequence=len(events)+1,
        people_safely_arrived=safe, people_stranded=stranded,
        people_unsafe_arrival=unsafe, people_overflow=overflow)
    return scenario, state


@pytest.mark.parametrize("counts,reason", [
    ((20, 0, 0, 0), "ALL_EVACUATED"), ((0, 20, 0, 0), "ALL_FAILED"),
    ((0, 0, 20, 0), "ALL_FAILED"), ((0, 0, 0, 20), "ALL_FAILED"),
    ((10, 10, 0, 0), "MIXED_OUTCOME"), ((10, 0, 5, 5), "MIXED_OUTCOME"),
])
def test_v4_terminal_outcomes_do_not_claim_failed_people_arrived(counts, reason):
    from src.sim import assert_episode_invariants
    from src.sim.transition import _finalize_accepted_transition

    scenario, state = outcome_state(*counts)
    assert_episode_invariants(scenario, state)
    ended, records = _finalize_accepted_transition(scenario, state, ())
    assert_episode_invariants(scenario, ended)
    assert ended.terminal_reason.value == reason
    if reason != "ALL_EVACUATED":
        assert "all evacuees arrived safely" not in records[-1].message


def test_v4_unfinished_horizon_is_distinct_from_resolved_outcomes():
    from src.sim import assert_episode_invariants
    from src.sim.transition import _finalize_accepted_transition

    scenario, state = outcome_state(10, 5, 0, 0, remaining=5)
    state = replace(state, current_timestep=scenario.time.horizon_steps-1)
    ended, _ = _finalize_accepted_transition(scenario, state, ())
    assert_episode_invariants(scenario, ended)
    assert ended.terminal_reason.value == "HORIZON_REACHED"


def test_v4_audit_exposes_causes_before_transit_effects():
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.planners import RiskGreedyPlanner, build_planner_input
    from src.safety import evaluate_actions
    from src.sim import WAIT

    scenario, sim, _, _, _ = build_v4_runtime("v4-medium-dt2-v1", generator_seed=620000)
    observed = False
    for n in range(8):
        sim.observe()
        state = sim.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state)
        action = (RiskGreedyPlanner().choose_action(build_planner_input(
            scenario, state, snapshot, sim.config)).action if n == 0 else WAIT)
        result = sim.step(action)
        types = [r.event_type.value for r in result.audit_records]
        effects = [i for i, kind in enumerate(types) if kind in {
            "GROUP_STRANDED", "ARRIVAL_PROCESSED", "ARRIVAL_UNSAFE", "ARRIVAL_OVERFLOW"}]
        if effects and "FLOOD_STATE_UPDATED" in types:
            observed = True
            assert types.index("FLOOD_STATE_UPDATED") < min(effects)
            same_step = [r.event_type.value for r in result.state.audit_log if r.timestep == n]
            assert same_step.index("FLOOD_STATE_UPDATED") < same_step.index(types[min(effects)])
            break
    assert observed


@pytest.fixture
def recorded_ledger():
    from src.certify.certificate import CertificateInputs

    trace = json.loads((ROOT / "data/demo_v4/demo_trace.json").read_text(encoding="utf-8"))
    return SimpleNamespace(certificates=lambda: copy.deepcopy(trace["certificates"]),
        inputs=lambda cert_id: CertificateInputs.from_dict(copy.deepcopy(trace["inputs"][cert_id])))


def command_for(ledger, kind):
    from src.actuation.commands import VehicleCommand, AdmissionCommand, RerouteCommand

    cert = next(c for c in ledger.certificates() if c["kind"] == ("MIGRATION" if kind == "reroute" else "DISPATCH"))
    candidate = next(c for c in ledger.inputs(cert["cert_id"]).candidates if c.action_key == cert["chosen"]["action_key"])
    chosen = cert["chosen"]
    common = (cert["cert_id"], cert["cert_hash"])
    if kind == "vehicle":
        return VehicleCommand(*common, chosen["group_id"], candidate.zone_id,
                              candidate.shelter_id, chosen["people"], candidate.edge_ids)
    if kind == "admission":
        return AdmissionCommand(*common, candidate.shelter_id, chosen["people"], chosen["group_id"])
    return RerouteCommand(*common, chosen["group_id"], candidate.shelter_id, candidate.edge_ids)


@pytest.mark.parametrize("kind,field", [("vehicle", "edge_ids"), ("vehicle", "group_id"),
    ("admission", "group_id"), ("reroute", "edge_ids"), ("reroute", "group_id")])
def test_authorizer_rejects_group_or_ordered_path_tampering(recorded_ledger, kind, field):
    from src.actuation.commands import authorize

    command = command_for(recorded_ledger, kind)
    assert authorize(command, recorded_ledger)
    changed = ("forged-edge",) if field == "edge_ids" else "forged-group"
    assert not authorize(replace(command, **{field: changed}), recorded_ledger)


@pytest.mark.parametrize("kind", ["vehicle", "admission", "reroute"])
def test_authorizer_fails_closed_without_authenticated_inputs(recorded_ledger, kind):
    from src.actuation.commands import authorize

    command = command_for(recorded_ledger, kind)
    missing = SimpleNamespace(certificates=recorded_ledger.certificates)
    assert not authorize(command, missing)


def test_authorizer_rejects_wrong_forecast_or_ordered_route(recorded_ledger):
    from src.actuation.commands import authorize

    command = command_for(recorded_ledger, "vehicle")
    inputs = recorded_ledger.inputs(command.cert_id)
    poisoned = replace(inputs, forecast=replace(inputs.forecast, timestep=inputs.forecast.timestep+1))
    ledger = SimpleNamespace(certificates=recorded_ledger.certificates, inputs=lambda _: poisoned)
    assert not authorize(command, ledger)
    assert not authorize(replace(command, edge_ids=tuple(reversed(command.edge_ids))), recorded_ledger)


def test_authorizer_rejects_a_chosen_candidate_without_feasible_evidence(recorded_ledger):
    from src.actuation.commands import authorize
    from src.certify.certificate import certificate_hash

    command = command_for(recorded_ledger, "vehicle")
    certs = recorded_ledger.certificates()
    cert = next(c for c in certs if c["cert_id"] == command.cert_id)
    row = next(c for c in cert["candidates"] if c["action_key"] == cert["chosen"]["action_key"])
    row["verdict"] = "INFEASIBLE"
    cert["cert_hash"] = certificate_hash(cert)
    ledger = SimpleNamespace(certificates=lambda: certs, inputs=recorded_ledger.inputs)
    assert not authorize(replace(command, cert_hash=cert["cert_hash"]), ledger)


def test_future_accounting_counts_execution_and_keeps_frozen_mode():
    from scripts.run_phase10 import run_index_policy_episode
    from src.sim import MEDIUM
    from src.sim.generator import generate_gate6_scenario

    class InvalidPolicy:
        def predict(self, observation, **kwargs):
            return 0, None

    scenario = generate_gate6_scenario(610000, "exact")
    scenario = replace(scenario, scenario_id="prospective-accounting-fixture",
        time=replace(scenario.time, horizon_steps=2), fleet=replace(scenario.fleet,
        evacuation_enabled=False, dispatches_per_timestep=0))
    legacy = run_index_policy_episode(scenario, MEDIUM, model=InvalidPolicy())
    assert legacy["dispatches"] == legacy["unsafe_dispatches"] == 2
    future = run_index_policy_episode(scenario, MEDIUM, model=InvalidPolicy(),
                                     action_accounting_version="executed-actions-v2")
    assert future["action_accounting_version"] == "executed-actions-v2"
    assert future["requested_dispatches"] == future["blocked_dispatches"] == 2
    assert future["executed_dispatches"] == future["dispatches"] == future["unsafe_dispatches"] == 0
    assert all(a["action_type"] == "WAIT" for a in future["actions"])
    assert all(a["action_type"] == "DISPATCH" for a in future["requested_actions"])


def test_future_accounting_keeps_real_successful_dispatches():
    from scripts.run_phase10 import run_index_policy_episode
    from src.sim import MEDIUM
    from src.sim.generator import generate_gate6_scenario

    class AllowedPolicy:
        def predict(self, observation, *, action_masks, **kwargs):
            return next(i for i, allowed in enumerate(action_masks) if allowed), None

    result = run_index_policy_episode(generate_gate6_scenario(610000, "exact"), MEDIUM,
        model=AllowedPolicy(), action_accounting_version="executed-actions-v2")
    assert result["executed_dispatches"] == result["requested_dispatches"] == result["dispatches"] > 0
    assert result["blocked_dispatches"] == result["unsafe_dispatches"] == 0
    assert any(a["action_type"] == "DISPATCH" for a in result["actions"])


def test_unknown_accounting_version_is_rejected():
    from scripts.run_phase10 import run_index_policy_episode

    with pytest.raises(ValueError, match="accounting version"):
        run_index_policy_episode(None, None, action_accounting_version="unknown")
