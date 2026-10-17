"""Lane S Phase 15' integration: document rules through the gate, mask verdicts, audit and replay."""

from __future__ import annotations

import hashlib

import pytest

from src.actuation.commands import InMemorySink
from src.certify.certificate import validate_certificate
from src.certify.gate import CertifiedGate
from src.certify.ledger import SimLedgerAdapter
from src.certify.params import get_cert_params
from src.certify.replay import replay_certificate
from src.certify.rollout import Outcome, RolloutResult
from src.constraints.claim_support import EvidenceChunk
from src.constraints.ndma_rules import NdmaRule
from src.constraints.tiering import Tier, assign_tier
from src.geospatial import load_road_graph
from src.geospatial.v4_runtime import build_v4_runtime
from src.safety import evaluate_actions
from src.safety.models import RuleProvenance
from src.sim.events import AuditEventType

TEXT = "Evacuees should not be moved over routes that take longer than forty minutes during flooding."


def make_rule():
    digest = hashlib.sha256(TEXT.encode()).hexdigest()
    return NdmaRule("NDMA-T01", "at most forty minutes", "MAX_TRAVEL_MINUTES", {"minutes": 40},
                    {"minutes": 5},
                    {"source_id": "s", "filename": "f.pdf", "page": 1, "chunk_id": "c", "passage_sha256": digest,
                     "span": "longer than forty minutes"}, approved=True)


def chunk(text):
    return EvidenceChunk("c", "s", "f.pdf", 1, text, hashlib.sha256(TEXT.encode()).hexdigest())


class FakeFutureSet:
    def __init__(self, forecast, graph, world, root, horizon_steps, edge_ids=None, **kwargs):
        self.root = root
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        return k


def ok_rollout(c, k, ledger, world, params, graph, extra_terms=()):
    # a fixed 20-minute trip: the 40-minute rule holds, the 5-minute strict fallback fails
    elapsed = 20.0
    policy = all(t(c, SimpleFuture(), 3, elapsed, (), ledger) for t in extra_terms) if extra_terms else None
    if policy is False:
        return RolloutResult(False, Outcome.POLICY, 3, -float(c.people), True, True, True, False)
    return RolloutResult(True, Outcome.OK, 3, float(c.people), True, True, True, policy)


class SimpleFuture:
    start_timestep = 0
    steps = 50


@pytest.fixture(scope="module")
def graph():
    return load_road_graph()


def run_gate(graph, text):
    scenario, sim, graph, overlay, world = build_v4_runtime("v4-medium-dt2-v1", generator_seed=620000, graph=graph)
    tiered = assign_tier(make_rule(), lambda r: chunk(text))
    ledger = SimLedgerAdapter(sim)
    gate = CertifiedGate(scenario, graph, world, get_cert_params("v4-cert-test-v1"), ledger,
                         sink=InMemorySink(), futures_factory=FakeFutureSet, rollout=ok_rollout,
                         world_id="v4-medium-dt2-v1", rules=[tiered])
    sim.observe()
    state = sim.prepared_state_for_debug()
    result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
    return gate, ledger, sim, scenario, state, tiered, result, inputs


def test_t1_rule_certifies_and_replays(graph):
    gate, ledger, sim, scenario, state, tiered, result, inputs = run_gate(graph, TEXT)
    assert tiered.tier is Tier.T1
    assert result.chosen_key != "WAIT"
    assert gate.params.params_id.startswith("v4-cert-test-v1+rules-")
    cert = gate.commit(result, inputs, operator={"decision": "ACCEPT", "actor": "t", "reason": ""}).certificate
    validate_certificate(cert)
    report = replay_certificate(cert, ledger.inputs(cert["cert_id"]), graph=graph,
                                futures_factory=FakeFutureSet, rollout=ok_rollout, rules=[tiered])
    assert report.result == "MATCH", report.mismatched_fields
    assert replay_certificate(cert, ledger.inputs(cert["cert_id"]), graph=graph,
                              futures_factory=FakeFutureSet, rollout=ok_rollout).result == "MISMATCH"
    snap = evaluate_actions(scenario, state, certifier=lambda sc, st, cands: gate.certificate_map(result))
    verdicts = [v for e in snap.evaluations for v in e.rule_verdicts if v.rule_id == "NDMA-T01"]
    assert verdicts and all(v.provenance is RuleProvenance.DOCUMENT_POLICY for v in verdicts)


def test_tampered_chunk_blocks_dispatch_and_is_audited(graph):
    gate, ledger, sim, scenario, state, tiered, result, inputs = run_gate(graph, "tampered text")
    assert tiered.tier is Tier.T0
    assert result.chosen_key == "WAIT"
    assert any(r.event_type is AuditEventType.RULE_STRICT_FALLBACK
               for r in sim.prepared_state_for_debug().audit_log)
    cert = gate.commit(result, inputs, operator={"decision": "ACCEPT", "actor": "t", "reason": ""}).certificate
    validate_certificate(cert)
    assert cert["kind"] == "HOLD"
    for row in cert["candidates"]:
        if row["action_key"] != "WAIT":
            assert "POLICY" in row["outcome_counts"] and sum(row["outcome_counts"].values()) == row["n"]
