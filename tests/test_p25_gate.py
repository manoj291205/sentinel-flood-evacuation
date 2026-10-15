"""Phase 25 acceptance tests (Lead) — gate, atomic commit, certificate, replay. Do not edit; escalate instead."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.milestone("P25")

CONTRACTS = Path(__file__).resolve().parents[1] / "specs" / "contracts"
OPERATOR = {"decision": "ACCEPT", "actor": "acceptance-test", "reason": ""}


def _contract(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


class FakeFutureSet:
    """Stands in for FutureSet: future k is just k; rollouts decide success from (action, k)."""

    def __init__(self, forecast, graph, world, root, horizon_steps, edge_ids=None, **kwargs):
        self.root = root
        self.edge_ids = None if edge_ids is None else tuple(sorted(set(edge_ids)))
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        if k < 1:
            raise ValueError("k must be >= 1")
        return k

    def edge_set_digest(self):
        if self.edge_ids is None:
            return "ALL"
        return hashlib.sha256("\n".join(self.edge_ids).encode("utf-8")).hexdigest()


def _good(action_key):
    return int(hashlib.sha256(action_key.encode("utf-8")).hexdigest(), 16) % 3 == 0


def fake_rollout(candidate, k, *args, **kwargs):
    from src.certify.rollout import Outcome, RolloutResult

    u = int(hashlib.sha256(f"{candidate.action_key}|{k}".encode("utf-8")).hexdigest()[:8], 16) / 2**32
    ok = u < (0.9999 if _good(candidate.action_key) else 0.5)
    return RolloutResult(
        z=ok, outcome=Outcome.OK if ok else Outcome.STRANDED, arrival_timestep=k % 5 + 1,
        utility=float(candidate.people if ok else -candidate.people),
        path_ok=ok, shelter_ok=True if ok else None, capacity_ok=True if ok else None,
    )


def failing_rollout(candidate, k, *args, **kwargs):
    from src.certify.rollout import Outcome, RolloutResult

    return RolloutResult(z=False, outcome=Outcome.STRANDED, arrival_timestep=None,
                         utility=-float(candidate.people), path_ok=False, shelter_ok=None, capacity_ok=None)


@pytest.fixture(scope="module")
def graph():
    from src.geospatial import load_road_graph

    return load_road_graph()


def _runtime(graph, seed=620000):
    from src.geospatial.v4_runtime import build_v4_runtime

    scenario, simulator, graph, overlay, world = build_v4_runtime(
        "v4-medium-dt2-v1", generator_seed=seed, graph=graph
    )
    simulator.observe()
    return scenario, simulator, overlay, world


def _gate(graph, rollout=fake_rollout, factory=FakeFutureSet, seed=620000):
    from src.actuation.commands import InMemorySink
    from src.certify.gate import CertifiedGate
    from src.certify.ledger import SimLedgerAdapter
    from src.certify.params import get_cert_params

    scenario, simulator, overlay, world = _runtime(graph, seed)
    ledger = SimLedgerAdapter(simulator)
    sink = InMemorySink()
    gate = CertifiedGate(scenario, graph, world, get_cert_params("v4-cert-test-v1"), ledger,
                         sink=sink, futures_factory=factory, rollout=rollout)
    return gate, ledger, sink, scenario, simulator, overlay


def _evaluate(gate, scenario, simulator, overlay):
    from src.safety import evaluate_actions

    state = simulator.prepared_state_for_debug()
    return gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))


def _decide(gate, scenario, simulator, overlay, **kwargs):
    result, inputs = _evaluate(gate, scenario, simulator, overlay)
    decision = gate.commit(result, inputs, operator=OPERATOR, **kwargs)
    if not simulator.state.terminal:
        simulator.observe()
    return result, decision


def test_test_params_registered():
    from src.certify.params import get_cert_params

    p = get_cert_params("v4-cert-test-v1")
    assert (p.k0, p.max_looks, p.eps_dispatch) == (32, 2, 0.30)


def test_canonical_hash_reproduces_every_fixture_hash():
    from src.certify.certificate import certificate_hash, verify_chain

    certs = _contract("certificates_fixture.json")["certificates"]
    for cert in certs:
        assert certificate_hash(cert) == cert["cert_hash"]
    assert verify_chain(certs) is None


def test_dispatch_commit_writes_valid_certificate_then_commands(graph):
    from src.actuation.commands import AdmissionCommand, VehicleCommand, authorize
    from src.certify.certificate import validate_certificate

    gate, ledger, sink, scenario, simulator, overlay = _gate(graph)
    result, decision = _decide(gate, scenario, simulator, overlay)
    assert result.chosen_key != "WAIT"
    cert = decision.certificate
    jsonschema.validate(cert, _contract("certificate.schema.json"))
    validate_certificate(cert)
    assert cert["kind"] == "DISPATCH" and cert["prev_cert_hash"] is None
    assert cert["chosen"]["action_key"] == result.chosen_key
    assert len(cert["edge_set_digest"]) == 64
    assert ledger.certificates() == [cert]
    kinds = {type(c) for c in decision.commands}
    assert kinds == {VehicleCommand, AdmissionCommand}
    assert list(sink.sent) == list(decision.commands)
    assert all(c.cert_id == cert["cert_id"] and c.cert_hash == cert["cert_hash"] for c in decision.commands)
    assert all(authorize(c, ledger) for c in decision.commands)
    assert decision.escalate is False


def test_empty_certified_set_gives_hold_certificate_and_escalation(graph):
    gate, ledger, sink, scenario, simulator, overlay = _gate(graph, rollout=failing_rollout)
    result, decision = _decide(gate, scenario, simulator, overlay)
    assert result.chosen_key == "WAIT"
    assert decision.certificate["kind"] == "HOLD"
    assert decision.escalate is True
    assert decision.commands == () and list(sink.sent) == []


def test_uncertified_selection_is_refused(graph):
    from src.certify.gate import GateError

    gate, ledger, sink, scenario, simulator, overlay = _gate(graph)
    result, inputs = _evaluate(gate, scenario, simulator, overlay)
    blocked = [c.action_key for c in result.candidates if c.action_key not in result.allowed_keys()]
    assert blocked, "fake rollout must leave some candidates uncertified"
    with pytest.raises(GateError):
        gate.commit(result, inputs, operator={"decision": "OVERRIDE", "actor": "t", "reason": "r"},
                    selected_key=blocked[0])
    assert ledger.certificates() == [] and list(sink.sent) == []


@pytest.mark.parametrize("stage", ["after_reserve", "after_certificate"])
def test_crash_injection_commits_nothing(graph, stage):
    from src.certify.ledger import SqliteLedger

    gate, _, _, scenario, simulator, overlay = _gate(graph)
    _, inputs = _evaluate(gate, scenario, simulator, overlay)
    cert = copy.deepcopy(_contract("certificates_fixture.json")["certificates"][0])

    def hook(at):
        if at == stage:
            raise RuntimeError(f"injected crash {at}")

    ledger = SqliteLedger(shelters={"S-02": (100, 10)}, fail_hook=hook)
    with pytest.raises(RuntimeError, match="injected crash"):
        with ledger.transaction() as tx:
            tx.reserve("S-02", 35, cert["cert_id"])
            tx.append_certificate(cert, inputs)
    assert ledger.certificates() == []
    assert ledger.view().reserved["S-02"] == 0


def test_capacity_conflict_rolls_back():
    from src.certify.ledger import LedgerConflict, SqliteLedger

    ledger = SqliteLedger(shelters={"S-01": (50, 40)})
    with pytest.raises(LedgerConflict):
        with ledger.transaction() as tx:
            tx.reserve("S-01", 20, "CERT-000001")
    assert ledger.view().reserved["S-01"] == 0


def test_chain_replay_and_tamper_detection(graph):
    from src.certify.certificate import verify_chain
    from src.certify.replay import replay_certificate

    gate, ledger, _, scenario, simulator, overlay = _gate(graph)
    for _ in range(20):
        if simulator.state.terminal:
            break
        _decide(gate, scenario, simulator, overlay)
    certs = ledger.certificates()
    assert len(certs) >= 3
    assert verify_chain(certs) is None
    for cert in certs:
        report = replay_certificate(cert, ledger.inputs(cert["cert_id"]), graph=graph,
                                    futures_factory=FakeFutureSet, rollout=fake_rollout)
        assert report.result == "MATCH", report.mismatched_fields

    target = next(c for c in certs if c["candidates"])
    inputs = ledger.inputs(target["cert_id"])
    for field in ("timestep", "forecast_hash", "ledger_hash", "root_key", "futures_used", "looks"):
        tampered = copy.deepcopy(target)
        tampered[field] = tampered[field] + 1 if isinstance(tampered[field], int) else "0" * 64
        report = replay_certificate(tampered, inputs, graph=graph,
                                    futures_factory=FakeFutureSet, rollout=fake_rollout)
        assert report.result == "MISMATCH" and field in report.mismatched_fields, field
    tampered = copy.deepcopy(target)
    tampered["candidates"][0]["lower"] = 0.123
    report = replay_certificate(tampered, inputs, graph=graph,
                                futures_factory=FakeFutureSet, rollout=fake_rollout)
    assert "candidates[0].lower" in report.mismatched_fields

    broken = copy.deepcopy(certs)
    broken[1]["timestep"] += 1
    assert verify_chain(broken) == 1


def test_authorize_rejects_bad_commands(graph):
    from src.actuation.commands import VehicleCommand, authorize

    gate, ledger, _, scenario, simulator, overlay = _gate(graph)
    _, decision = _decide(gate, scenario, simulator, overlay)
    vehicle = next(c for c in decision.commands if isinstance(c, VehicleCommand))
    assert authorize(vehicle, ledger)
    assert not authorize(dataclasses.replace(vehicle, cert_id="CERT-999999"), ledger)
    assert not authorize(dataclasses.replace(vehicle, cert_hash="0" * 64), ledger)
    other = "S-00" if vehicle.shelter_id != "S-00" else "S-99"
    assert not authorize(dataclasses.replace(vehicle, shelter_id=other), ledger)


def test_end_to_end_on_real_futures_replays(graph):
    from src.certify.futures import FutureSet
    from src.certify.replay import replay_certificate
    from src.certify.rollout import rollout_joint

    gate, ledger, _, scenario, simulator, overlay = _gate(graph, rollout=rollout_joint, factory=FutureSet)
    _, decision = _decide(gate, scenario, simulator, overlay)
    cert = decision.certificate
    jsonschema.validate(cert, _contract("certificate.schema.json"))
    report = replay_certificate(cert, ledger.inputs(cert["cert_id"]), graph=graph)
    assert report.result == "MATCH", report.mismatched_fields


def test_certified_session_mode_and_legacy_default(graph):
    from src.simulation_session import SimulationSession

    legacy = SimulationSession(620000, graph=graph)
    assert legacy.simulator.config.config_id == "v3-medium-v1"
    certified = SimulationSession(620000, "v4-medium-dt2-v1", graph=graph, certified=True,
                                  params_id="v4-cert-test-v1")
    assert certified.certificates() == []
    assert certified.context() is not None
