"""Operational exports preserve original intent and can replay certificates offline."""
import csv
import json
from io import StringIO

import pytest

from src.human_decision import EvidenceReference
from src.simulation_session import SimulationSession

EVIDENCE = EvidenceReference("ndma-flood-guidelines-2008", 64, "ndma-flood-guidelines-2008-p64-c0")


@pytest.mark.parametrize("reason", ["=1+1", "+SUM(A1)", "-1+1", "@SUM(A1)", " \t=1+1", "\ufeff=1+1", "\u2003=1+1", "\u2003\x00\t=1+1", "ordinary reason"])
def test_csv_formula_escaping_preserves_json_reason(reason):
    session = SimulationSession()
    session.decide("REJECT", EVIDENCE, reason=reason)
    raw = json.loads(session.export_json())["audit"][0]
    row = next(csv.DictReader(StringIO(session.export_csv())))
    key = next(k for k in raw if raw[k] == reason)
    assert raw[key] == reason
    assert row[key] == (reason if reason == "ordinary reason" else "'" + reason)


def test_export_contains_configuration_and_replay_identity():
    session = SimulationSession()
    data = json.loads(session.export_json())
    assert data["export_schema"] == "sentinel-session-v2"
    assert len(data["provenance"]["source_commit"]) == 40
    assert len(data["provenance"]["configuration_sha256"]) == 64
    assert data["scenario"]["scenario_id"] == session.scenario.scenario_id
    assert data["graph_fingerprint"] == session.graph.graph_fingerprint
    assert data["certificate_inputs"] == {}


def test_serialized_certificate_inputs_replay_independently():
    from src.certify.certificate import CertificateInputs, verify_chain
    from src.certify.replay import replay_certificate
    session = SimulationSession(620003, "v4-medium-dt2-v1", certified=True,
                                params_id="v4-cert-test-v1", recertify=True)
    for _ in range(2):
        session.decide("ACCEPT", EVIDENCE)
    exported = json.loads(session.export_json())
    assert verify_chain(exported["certificates"]) is None
    for cert in exported["certificates"]:
        saved = CertificateInputs.from_dict(exported["certificate_inputs"][cert["cert_id"]])
        assert replay_certificate(cert, saved, graph=session.graph,
                                  rules=session.runtime_rules.rules).result == "MATCH"
    assert exported["provenance"]["active_rules"]["enforced_count"] == 0
