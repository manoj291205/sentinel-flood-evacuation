"""Lane S unit tests for Phase 25: certified session flow, empty certifier input, ledger ids."""

from __future__ import annotations

import pytest

from src.certify.certificate import verify_chain
from src.certify.ledger import SimLedgerAdapter, SqliteLedger
from src.certify.replay import replay_certificate
from src.human_decision import EvidenceReference
from src.simulation_session import SimulationSession

EVIDENCE = EvidenceReference("doc", 1, "chunk")


@pytest.fixture(scope="module")
def graph():
    from src.geospatial import load_road_graph

    return load_road_graph()


def test_certified_session_decisions_chain_and_replay(graph):
    session = SimulationSession(620000, "v4-medium-dt2-v1", graph=graph, certified=True,
                                params_id="v4-cert-test-v1")
    for _ in range(3):
        if session.context() is None:
            break
        session.decide("ACCEPT", EVIDENCE)
    certs = session.certificates()
    assert len(certs) >= 2
    assert verify_chain(certs) is None
    assert [c["cert_id"] for c in certs] == [f"CERT-{i:06d}" for i in range(1, len(certs) + 1)]
    for cert in certs:
        report = replay_certificate(cert, session.ledger.inputs(cert["cert_id"]), graph=graph)
        assert report.result == "MATCH", report.mismatched_fields


def test_certified_reject_commits_hold_certificate(graph):
    session = SimulationSession(620000, "v4-medium-dt2-v1", graph=graph, certified=True,
                                params_id="v4-cert-test-v1")
    session.decide("REJECT", EVIDENCE, reason="operator hold")
    cert = session.certificates()[0]
    assert cert["kind"] == "HOLD" and cert["operator"]["decision"] == "REJECT"


def test_empty_candidates_do_not_generate_futures():
    from src.certify.certifier import certify
    from src.certify.params import get_cert_params

    class Boom:
        A_MAX = 3
        root = "r"

        def future(self, k):
            raise AssertionError("no futures expected")

    result = certify([], Boom(), None, None, get_cert_params("v4-cert-test-v1"), None)
    assert result.chosen_key == "WAIT" and result.looks == 0 and result.candidates == ()


def test_sqlite_ledger_ids_and_release():
    ledger = SqliteLedger(shelters={"S-01": (50, 0)})
    with ledger.transaction() as tx:
        tx.reserve("S-01", 30, "CERT-000001")
    assert ledger.view().reserved["S-01"] == 30
    with ledger.transaction() as tx:
        tx.release("S-01", 30, "CERT-000001")
    assert ledger.view().reserved["S-01"] == 0
    assert ledger.next_cert_id() == "CERT-000001"
    assert isinstance(SimLedgerAdapter, type)
