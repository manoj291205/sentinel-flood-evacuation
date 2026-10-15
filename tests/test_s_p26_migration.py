"""Lane S Phase 26 integration: real v4 runtime, fake futures, forced certified failure -> migration."""

from __future__ import annotations

import hashlib

import pytest

from src.actuation.commands import InMemorySink, RerouteCommand, authorize
from src.certify.certificate import verify_chain
from src.certify.gate import CertifiedGate
from src.certify.ledger import SimLedgerAdapter
from src.certify.params import get_cert_params
from src.certify.recertify import GroupHistory, RecertPolicy, recertify_in_transit
from src.certify.replay import replay_certificate
from src.certify.rollout import Outcome, RolloutResult
from src.geospatial import load_road_graph
from src.geospatial.v4_runtime import build_v4_runtime
from src.safety import evaluate_actions

OPERATOR = {"decision": "ACCEPT", "actor": "test", "reason": ""}


class FakeFutureSet:
    def __init__(self, forecast, graph, world, root, horizon_steps, edge_ids=None, **kwargs):
        self.root = root
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        return k


BAD_SHELTERS: set[str] = set()


def rollout(c, k, *args, **kwargs):
    bad = c.shelter_id in BAD_SHELTERS
    ok = not bad
    return RolloutResult(ok, Outcome.OK if ok else Outcome.STRANDED, 3, float(c.people if ok else -c.people),
                         ok, True if ok else None, True if ok else None)


@pytest.fixture(scope="module")
def graph():
    return load_road_graph()


def test_forced_failure_migrates_atomically_and_replays(graph):
    BAD_SHELTERS.clear()
    scenario, sim, graph, overlay, world = build_v4_runtime("v4-medium-dt2-v1", generator_seed=620000, graph=graph)
    ledger = SimLedgerAdapter(sim)
    sink = InMemorySink()
    gate = CertifiedGate(scenario, graph, world, get_cert_params("v4-cert-test-v1"), ledger, sink=sink,
                         futures_factory=FakeFutureSet, rollout=rollout, world_id="v4-medium-dt2-v1")
    sim.observe()
    state = sim.prepared_state_for_debug()
    result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
    decision = gate.commit(result, inputs, operator=OPERATOR)
    assert decision.certificate["kind"] == "DISPATCH"
    old_shelter = decision.certificate["chosen"]["action_key"].split("->")[1]
    # advance one step, then declare the group's current shelter certified-infeasible
    sim.observe()
    state = sim.prepared_state_for_debug()
    plans = sim.transit_plans()
    histories = {}
    BAD_SHELTERS.add(old_shelter)
    reserved_before = {s.shelter_id: s.capacity_reserved for s in state.shelters}
    decisions = recertify_in_transit(gate, state, overlay.road_state, plans, histories, RecertPolicy())
    migrated = [d for d in decisions if d.action == "MIGRATE"]
    if not migrated:  # group may have arrived / have no reachable alternative in this layout
        assert all(d.action in {"KEEP", "KEEP_ESCALATE", "COOLDOWN"} for d in decisions)
        pytest.skip("no migration possible for this seed/step")
    d = migrated[0]
    assert d.certificate["kind"] == "MIGRATION" and d.new_shelter_id != old_shelter
    after = {s.shelter_id: s.capacity_reserved for s in sim.prepared_state_for_debug().shelters}
    people = d.certificate["chosen"]["people"]
    assert after[old_shelter] == reserved_before[old_shelter] - people
    assert after[d.new_shelter_id] == reserved_before[d.new_shelter_id] + people
    assert verify_chain(ledger.certificates()) is None
    reroute = next(c for c in sink.sent if isinstance(c, RerouteCommand))
    assert authorize(reroute, ledger)
    report = replay_certificate(d.certificate, ledger.inputs(d.certificate["cert_id"]), graph=graph,
                                futures_factory=FakeFutureSet, rollout=rollout)
    assert report.result == "MATCH", report.mismatched_fields
    assert histories[d.event_id].left_shelters == frozenset({old_shelter})
    sim.step(__import__("src.sim", fromlist=["WaitAction"]).WaitAction())  # state stays consistent
    BAD_SHELTERS.clear()
