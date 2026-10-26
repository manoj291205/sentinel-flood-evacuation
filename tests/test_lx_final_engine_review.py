"""Independent offline cross-review of execution, masks, and V4 outcome causes."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import socket

    def denied(*args, **kwargs):
        raise AssertionError("final engine review must remain offline")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


class _ReviewFutures:
    def __init__(self, forecast, graph, world, root, horizon_steps, **kwargs):
        self.root = root
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        return k


def _successful_rollout(candidate, k, *args, **kwargs):
    from src.certify.rollout import Outcome, RolloutResult

    return RolloutResult(True, Outcome.OK, 5, float(candidate.people), True, True, True)


def _review_gate(bind_inputs=True):
    from src.certify.gate import CertifiedGate
    from src.certify.ledger import SimLedgerAdapter
    from src.certify.params import get_cert_params
    from src.geospatial.v4_runtime import build_v4_runtime

    scenario, simulator, graph, overlay, world = build_v4_runtime(
        "v4-medium-dt2-v1", generator_seed=620000)
    simulator.observe()
    ledger = SimLedgerAdapter(simulator)
    gate = CertifiedGate(scenario, graph, world, get_cert_params("v4-cert-test-v1"), ledger,
        futures_factory=_ReviewFutures, rollout=_successful_rollout, bind_inputs=bind_inputs)
    return gate, simulator, overlay


def _review_dispatch(gate, simulator, overlay):
    from src.safety import evaluate_actions

    state = simulator.prepared_state_for_debug()
    result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(gate.scenario, state))
    return gate.commit(result, inputs,
        operator={"decision": "ACCEPT", "actor": "offline-review", "reason": ""})


@pytest.mark.parametrize("field", ["ordered_path", "start_minutes", "departure_timestep",
    "horizon_steps", "world_id", "cert_id"])
def test_full_replay_inputs_are_bound_before_authorization_or_replay(field):
    from src.actuation.commands import VehicleCommand, authorize
    from src.certify.certificate import validate_certificate
    from src.certify.replay import replay_certificate

    gate, simulator, overlay = _review_gate()
    decision = _review_dispatch(gate, simulator, overlay)
    cert = decision.certificate
    validate_certificate(cert)
    inputs = gate.ledger.inputs(cert["cert_id"])
    candidate = next(c for c in inputs.candidates if c.action_key == cert["chosen"]["action_key"])
    assert len(candidate.edge_ids) > 1
    command = next(c for c in decision.commands if isinstance(c, VehicleCommand))
    assert authorize(command, gate.ledger)
    if field in {"ordered_path", "start_minutes", "departure_timestep"}:
        attributes = {"edge_ids": tuple(reversed(candidate.edge_ids))} if field == "ordered_path" else {
            field: 1. if field == "start_minutes" else candidate.departure_timestep + 1}
        altered = replace(candidate, **attributes)
        changed = replace(inputs, candidates=tuple(altered if c == candidate else c for c in inputs.candidates))
        command = replace(command, edge_ids=altered.edge_ids)
    else:
        value = inputs.horizon_steps + 1 if field == "horizon_steps" else "changed"
        changed = replace(inputs, **{field: value})
    tampered = SimpleNamespace(certificates=gate.ledger.certificates, inputs=lambda _: changed)
    assert not authorize(command, tampered)

    def forbidden_factory(*args, **kwargs):
        raise AssertionError("mismatched v2 inputs must be rejected before generating futures")

    report = replay_certificate(cert, changed, graph=gate.graph, futures_factory=forbidden_factory)
    assert (report.result, report.mismatched_fields) == ("MISMATCH", ("inputs_digest",))


@pytest.mark.parametrize("bound", [False, True])
def test_new_bound_and_legacy_unbound_certificates_replay_without_changing_simulation(bound):
    from src.actuation.commands import authorize
    from src.certify.certificate import certificate_hash, validate_certificate
    from src.certify.replay import replay_certificate

    gate, simulator, overlay = _review_gate(bind_inputs=bound)
    decision = _review_dispatch(gate, simulator, overlay)
    cert = decision.certificate
    validate_certificate(cert)
    assert cert["cert_version"] == ("sentinel-cert-v2" if bound else "sentinel-cert-v1")
    assert ("inputs_digest" in cert) is bound
    assert certificate_hash(cert) == cert["cert_hash"]
    assert all(authorize(command, gate.ledger) is bound for command in decision.commands)
    report = replay_certificate(cert, gate.ledger.inputs(cert["cert_id"]), graph=gate.graph,
        futures_factory=_ReviewFutures, rollout=_successful_rollout)
    assert report.result == "MATCH", report.mismatched_fields


def test_binding_changes_only_certificate_format_and_hash_not_the_decision_or_state():
    from src.certify.certificate import certificate_hash

    legacy, old_sim, old_overlay = _review_gate(bind_inputs=False)
    bound, new_sim, new_overlay = _review_gate(bind_inputs=True)
    old = _review_dispatch(legacy, old_sim, old_overlay)
    new = _review_dispatch(bound, new_sim, new_overlay)
    normalized = {key: value for key, value in new.certificate.items() if key != "inputs_digest"}
    normalized["cert_version"] = "sentinel-cert-v1"
    normalized["cert_hash"] = certificate_hash(normalized)
    assert normalized == old.certificate
    assert old.action == new.action
    assert old_sim.state == new_sim.state


@pytest.mark.parametrize("change", ["v2_without_digest", "v1_with_digest", "bad_digest"])
def test_certificate_schema_rejects_invalid_version_binding_combinations(change):
    from src.certify.certificate import CertificateError, certificate_hash, validate_certificate

    gate, simulator, overlay = _review_gate()
    cert = copy.deepcopy(_review_dispatch(gate, simulator, overlay).certificate)
    if change == "v2_without_digest":
        del cert["inputs_digest"]
    elif change == "v1_with_digest":
        cert["cert_version"] = "sentinel-cert-v1"
    else:
        cert["inputs_digest"] = "invalid"
    cert["cert_hash"] = certificate_hash(cert)
    with pytest.raises(CertificateError, match="schema"):
        validate_certificate(cert)


def test_frozen_v1_documents_remain_valid_but_cannot_authorize_future_actuation():
    from src.actuation.commands import VehicleCommand, authorize
    from src.certify.certificate import CertificateInputs, validate_certificate, verify_chain

    trace = json.loads((Path(__file__).resolve().parents[1]
        / "data/demo_v4/demo_trace.json").read_text(encoding="utf-8"))
    assert verify_chain(trace["certificates"]) is None
    for cert in trace["certificates"]:
        validate_certificate(cert)
    cert = next(c for c in trace["certificates"] if c["kind"] == "DISPATCH")
    inputs = CertificateInputs.from_dict(copy.deepcopy(trace["inputs"][cert["cert_id"]]))
    candidate = next(c for c in inputs.candidates if c.action_key == cert["chosen"]["action_key"])
    command = VehicleCommand(cert["cert_id"], cert["cert_hash"], cert["chosen"]["group_id"],
        candidate.zone_id, candidate.shelter_id, candidate.people, candidate.edge_ids)
    ledger = SimpleNamespace(certificates=lambda: [cert], inputs=lambda _: inputs)
    assert not authorize(command, ledger)


def test_migration_certificates_inherit_binding_and_replay_exactly():
    from src.actuation.commands import authorize
    from src.certify.certificate import certificate_inputs_digest, validate_certificate, verify_chain
    from src.certify.recertify import GroupHistory
    from src.certify.replay import replay_certificate
    from src.certify.rollout import Outcome, RolloutResult

    gate, simulator, overlay = _review_gate()
    initial = _review_dispatch(gate, simulator, overlay)
    old_shelter = initial.certificate["chosen"]["action_key"].split("->")[1]

    def migration_rollout(candidate, k, *args, **kwargs):
        if candidate.shelter_id == old_shelter:
            return RolloutResult(False, Outcome.STRANDED, None, -float(candidate.people), False, None, None)
        return _successful_rollout(candidate, k, *args, **kwargs)

    gate.rollout = migration_rollout
    simulator.observe()
    plan = next(iter(simulator.transit_plans().values()))
    decision = gate.recertify(simulator.prepared_state_for_debug(), overlay.road_state, plan, GroupHistory())
    assert decision.action == "MIGRATE"
    cert = decision.certificate
    inputs = gate.ledger.inputs(cert["cert_id"])
    validate_certificate(cert)
    assert cert["cert_version"] == "sentinel-cert-v2"
    assert cert["inputs_digest"] == certificate_inputs_digest(inputs)
    assert all(c.start_minutes is not None for c in inputs.candidates)
    assert verify_chain(gate.ledger.certificates()) is None
    assert authorize(gate.sink.sent[-1], gate.ledger)
    report = replay_certificate(cert, inputs, graph=gate.graph,
        futures_factory=_ReviewFutures, rollout=migration_rollout)
    assert report.result == "MATCH", report.mismatched_fields


def _model():
    from src.planners.model import ModelRoute, ModelShelter, ModelState, ModelZone
    from src.sim import DispatchAction, WAIT

    action = DispatchAction("Z", "S")
    return ModelState("review-fixture", 0, 3, 2., 10, 10, 0,
        (ModelZone("Z", 10, .8, 0., .8),),
        (ModelShelter("S", 10, 0, 0, "OPEN", .1, 0., .1),),
        (ModelRoute("R", "Z", "S", True, 1., 1., 0., 0., .1),), (),
        (action, WAIT), .3, 0., 0., 0., 0., 1,
        root_timestep=0, root_allowed_actions=(WAIT,)), action


def test_projected_masks_cannot_bypass_fleet_or_closed_destinations():
    from src.sim import WAIT

    model, action = _model()
    assert model.allowed_actions() == (WAIT,)
    with pytest.raises(ValueError, match="not allowed"):
        model.advance(action)
    assert action in model.advance(WAIT).allowed_actions()
    assert replace(model, dispatch_enabled=False).advance(WAIT).allowed_actions() == (WAIT,)
    closed = replace(model, shelters=(replace(model.shelters[0], status="CLOSED"),),
                     root_allowed_actions=(action, WAIT))
    assert closed.allowed_actions() == (WAIT,)
    risky = replace(model, shelters=(replace(model.shelters[0], severity=.9),),
                    root_allowed_actions=(action, WAIT))
    assert risky.allowed_actions() == (WAIT,)
    assert action in replace(risky, hard_safety_enabled=False).allowed_actions()


@pytest.mark.parametrize("cause,expected,safe,failed", [
    ("closed_edge", "STRANDED", 0, 10),
    ("closed_shelter", "ARRIVAL_UNSAFE", 0, 10),
    ("overflow", "ARRIVAL_OVERFLOW", 3, 7),
    ("clear", "ARRIVED", 10, 0),
])
def test_v4_causal_outcomes_release_reservation_and_conserve_people(cause, expected, safe, failed):
    from src.sim import MEDIUM, initialize_episode
    from src.sim.events import DispatchEvent, DispatchStatus
    from src.sim.generator import generate_gate6_scenario
    from src.sim.schemas import ShelterStatus
    from src.sim.transit import TransitPlan, process_v4_transit
    from src.sim.world import get_world_config
    from src.sim.transition import _finalize_accepted_transition

    scenario = generate_gate6_scenario(610000, "exact")
    state = initialize_episode(scenario)
    zone, shelter, route = state.zones[0], state.shelters[0], state.routes[0]
    shelter = replace(shelter, capacity_total=10, occupancy_current=7 if cause == "overflow" else 0,
        capacity_reserved=10, status_current=ShelterStatus.CLOSED if cause == "closed_shelter"
        else ShelterStatus.OPEN, flood_severity_current=0.)
    event = DispatchEvent("dispatch-000001", zone.zone_id, shelter.shelter_id, 10, 0, 1,
        route.route_id, 1, 2., 2., 1., "v4-review", DispatchStatus.IN_TRANSIT)
    state = replace(state, current_timestep=1, uncertainty_config_id="v4-review",
        zones=(replace(zone, population_remaining=0),), shelters=(shelter,),
        dispatch_events=(event,), initial_evacuation_population=10)
    plan = TransitPlan(event.event_id, zone.zone_id, shelter.shelter_id, 10, 0,
        ("review-edge",), (1.,), 2., timestep_minutes=2.)
    roads = SimpleNamespace(edges=(SimpleNamespace(edge_id="review-edge", open=cause != "closed_edge"),))
    result, changed, records = process_v4_transit(state, (plan,), roads, MEDIUM,
                                               get_world_config("v4-medium-dt2-v1"))
    assert result.dispatch_events[0].status.value == expected
    assert bool(changed) is (cause != "closed_edge")
    assert len(records) == 1
    assert result.people_in_transit == 0
    assert result.shelters[0].capacity_reserved == 0
    assert result.people_safely_arrived == safe
    assert result.people_stranded + result.people_unsafe_arrival + result.people_overflow == failed
    assert result.people_safely_arrived + failed == result.initial_evacuation_population
    ended, _ = _finalize_accepted_transition(scenario, result, ())
    expected_reason = "ALL_EVACUATED" if failed == 0 else "MIXED_OUTCOME" if safe else "ALL_FAILED"
    assert ended.terminal_reason.value == expected_reason
