"""Phase P34R acceptance tests (Lead) — SimulationSession for live certified sessions. Do not edit; escalate instead.

Spec: specs/V4_RELEASE_SPEC.md section 2a. With recertify=True a certified session re-checks groups already on the road
once per step (Phase 26) before the next suggestion, exactly like the Phase 27 episode loop; certification() exposes the
pending result. World v4-medium-dt2-v1, seed 620003, params v4-cert-test-v1 (Lead pilot: a MIGRATION at step 4).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.milestone("P34R")

SEED, WORLD, PARAMS, STEPS = 620003, "v4-medium-dt2-v1", "v4-cert-test-v1", 6
EVIDENCE = {"source_id": "ndma-flood-guidelines-2008", "page": 64, "chunk_id": "ndma-flood-guidelines-2008-p64-c0"}
OPERATOR = {"decision": "ACCEPT", "actor": "session-operator", "reason": ""}


@pytest.fixture(scope="module")
def graph():
    from src.geospatial import load_road_graph

    return load_road_graph()


def _verdict(decision):
    verdict = getattr(decision, "keep_verdict", None)
    return verdict.value if verdict is not None else None


@pytest.fixture(scope="module")
def reference(graph):
    """The Phase 27 order: observe -> recertify_in_transit -> evaluate -> commit (ACCEPT)."""
    from src.certify.gate import CertifiedGate
    from src.certify.ledger import SimLedgerAdapter
    from src.certify.params import get_cert_params
    from src.certify.recertify import RecertPolicy, recertify_in_transit
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.safety import evaluate_actions

    scenario, sim, g, overlay, world = build_v4_runtime(WORLD, generator_seed=SEED, graph=graph)
    ledger = SimLedgerAdapter(sim)
    gate = CertifiedGate(scenario, g, world, get_cert_params(PARAMS), ledger, world_id=WORLD)
    histories, rows = {}, []
    for _ in range(STEPS):
        sim.observe()
        state = sim.prepared_state_for_debug()
        for d in recertify_in_transit(gate, state, overlay.road_state, sim.transit_plans(), histories, RecertPolicy()):
            rows.append({"timestep": state.current_timestep, "group_id": d.event_id, "action": d.action,
                         "verdict": _verdict(d), "cert_id": (d.certificate or {}).get("cert_id")})
        state = sim.prepared_state_for_debug()
        result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
        gate.commit(result, inputs, operator=OPERATOR)
    return ledger.certificates(), rows


@pytest.fixture(scope="module")
def session(graph):
    from src.human_decision import EvidenceReference
    from src.simulation_session import SimulationSession

    s = SimulationSession(SEED, WORLD, graph=graph, certified=True, params_id=PARAMS, recertify=True)
    for _ in range(STEPS):
        s.decide("ACCEPT", EvidenceReference(**EVIDENCE))
    return s


def test_recertify_needs_a_certified_session(graph):
    from src.simulation_session import SimulationSession

    with pytest.raises(ValueError):
        SimulationSession(SEED, "v3-medium-v1", graph=graph, recertify=True)


def test_session_commits_exactly_the_reference_certificates(session, reference):
    certs, _ = reference
    assert session.certificates() == certs
    kinds = [c["kind"] for c in certs]
    assert "MIGRATION" in kinds and "HOLD" in kinds and "DISPATCH" in kinds  # Lead pilot of this config


def test_recheck_log_matches_the_reference(session, reference):
    _, rows = reference
    got = [{k: row[k] for k in ("timestep", "group_id", "action", "verdict", "cert_id")} for row in session.recert_log]
    assert got == rows
    for row in session.recert_log:
        assert set(row) >= {"timestep", "group_id", "action", "verdict", "lower", "upper", "new_shelter_id", "cert_id"}
        assert (row["cert_id"] is not None) == (row["action"] == "MIGRATE")
    assert any(entry.get("category") == "MIGRATION" for entry in session.timeline)


def test_default_certified_session_does_not_recheck(graph):
    from src.human_decision import EvidenceReference
    from src.simulation_session import SimulationSession

    s = SimulationSession(SEED, WORLD, graph=graph, certified=True, params_id=PARAMS)
    for _ in range(3):
        s.decide("ACCEPT", EvidenceReference(**EVIDENCE))
    assert getattr(s, "recert_log", []) == []
    assert all(c["kind"] != "MIGRATION" for c in s.certificates())


def test_certification_accessor_exposes_the_pending_result(graph):
    from src.human_decision import action_key
    from src.simulation_session import SimulationSession

    assert SimulationSession(SEED, "v3-medium-v1", graph=graph).certification() is None
    s = SimulationSession(SEED, WORLD, graph=graph, certified=True, params_id=PARAMS, recertify=True)
    first = s.certification()
    assert first is not None
    result, _inputs = first
    assert s.certification()[0] is result  # repeated calls do not re-certify
    assert result.chosen_key == action_key(s.context().recommendation.action)
    assert s.certification()[0] is result  # context() reused the same evaluation
    assert s.certificates() == []  # reading it commits nothing
