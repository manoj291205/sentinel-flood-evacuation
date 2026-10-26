"""Phase 30 acceptance tests (Lead) — FastAPI service layer. Do not edit; escalate instead."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.milestone("P30")

CONTRACTS = Path(__file__).resolve().parents[1] / "specs" / "contracts"
EVIDENCE = {"source_id": "ndma-flood-guidelines-2008", "page": 64, "chunk_id": "ndma-flood-guidelines-2008-p64-c0"}


def _schema(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.app import create_app

    # Amendment 2026-10-17 (Lead, Wave C): Phase 34A makes RECORDED the default demo source; these Wave A
    # checks run against the contract fixtures, which stay available behind SENTINEL_DEMO_SOURCE=FIXTURE.
    monkeypatch.setenv("SENTINEL_DEMO_SOURCE", "FIXTURE")
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as test_client:
        yield test_client


def _new_session(client):
    response = client.post("/api/sessions", json={"seed": 620000, "regime": "v3-medium-v1"})
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_honesty(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert len(body["graph_fingerprint"]) == 64
    assert body["simulated"] is True
    assert body["honesty"] == "REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED"


def test_session_state_and_context_parity(client):
    from src.human_decision import action_key
    from src.simulation_session import SimulationSession

    session = _new_session(client)
    assert session["timestep"] == 0 and session["seed"] == 620000
    state = client.get(f"/api/sessions/{session['session_id']}/state").json()
    assert state["current_timestep"] == 0
    assert set(state["kpis"]) == {"waiting", "in_transit", "safe", "certificates_issued"}
    context = client.get(f"/api/sessions/{session['session_id']}/context").json()
    direct = SimulationSession(620000, "v3-medium-v1").context()
    assert context["recommendation"]["action_key"] == action_key(direct.recommendation.action)


def test_accept_matches_direct_session(client):
    from src.human_decision import EvidenceReference
    from src.simulation_session import SimulationSession

    session = _new_session(client)
    response = client.post(
        f"/api/sessions/{session['session_id']}/decisions",
        json=_bound_payload(client, session['session_id'], {"decision": "ACCEPT", "reason": "", "evidence": EVIDENCE}),
    )
    assert response.status_code == 200, response.text
    api_record = response.json()["audit_record"]
    twin = SimulationSession(620000, "v3-medium-v1")
    direct_record, _ = twin.decide("ACCEPT", EvidenceReference(**EVIDENCE))
    volatile = {"timestamp", "audit_id", "timestamp_utc"}
    assert api_record["decision_identity"]["session_id"] == session["session_id"]
    assert api_record["evidence_provenance"]["chunk_id"] == EVIDENCE["chunk_id"]
    assert {k: v for k, v in api_record.items() if k not in volatile | {"decision_identity", "evidence_provenance"}} == {
        k: v for k, v in direct_record.items() if k not in volatile
    }
    assert response.json()["state"]["current_timestep"] == 1


def test_reject_requires_reason(client):
    session = _new_session(client)
    response = client.post(
        f"/api/sessions/{session['session_id']}/decisions",
        json=_bound_payload(client, session['session_id'], {"decision": "REJECT", "reason": "", "evidence": EVIDENCE}),
    )
    assert response.status_code == 422


def test_demo_walkthrough_validates(client):
    schema = _schema("demo_step.schema.json")
    start = client.post("/api/demo/start").json()
    assert start["source"] == "FIXTURE" and start["step_index"] == 0 and start["step_count"] == 6
    seen = [start["step"]["step_index"]]
    jsonschema.validate(start["step"], schema)
    for _ in range(7):
        body = client.post("/api/demo/step", json={"action": "next"}).json()
        jsonschema.validate(body["step"], schema)
        seen.append(body["step_index"])
    assert seen == [0, 1, 2, 3, 4, 5, 5, 5]
    assert client.post("/api/demo/step", json={"action": "prev"}).json()["step_index"] == 4
    assert client.post("/api/demo/step", json={"action": "reset"}).json()["step_index"] == 0
    assert client.get("/api/demo/state").json()["step_index"] == 0


def test_certificates_and_replay(client):
    schema = _schema("certificate.schema.json")
    listing = client.get("/api/certificates").json()
    ids = [item["cert_id"] for item in listing["certificates"]]
    assert "CERT-000127" in ids
    cert = client.get("/api/certificates/CERT-000127").json()
    jsonschema.validate(cert, schema)
    assert client.post("/api/certificates/CERT-000127/replay", json={}).json()["result"] == "MATCH"
    tampered = client.post("/api/certificates/CERT-000127/replay", json={"tamper": True}).json()
    assert tampered["result"] == "MISMATCH" and tampered["mismatched_fields"]
    assert client.get("/api/certificates/CERT-999999").status_code == 404


def test_why_endpoint(client):
    body = client.get("/api/decisions/CERT-000127/why").json()
    jsonschema.validate(body, _schema("decision_why.schema.json"))
    assert len(body["reasons"]) == 3


def test_websocket_sequence(client):
    session = _new_session(client)
    with client.websocket_connect(f"/ws/sessions/{session['session_id']}") as ws:
        first = ws.receive_json()
        assert first["seq"] == 1 and first["type"] == "state"
        client.post(
            f"/api/sessions/{session['session_id']}/decisions",
            json=_bound_payload(client, session['session_id'], {"decision": "ACCEPT", "reason": "", "evidence": EVIDENCE}),
        )
        messages = [ws.receive_json() for _ in range(3)]
        seqs = [first["seq"]] + [m["seq"] for m in messages]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
        assert messages[0]["type"] == "decision"


def test_openapi_lists_contract_paths(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    for path in (
        "/api/health", "/api/sessions", "/api/sessions/{session_id}/state", "/api/sessions/{session_id}/context",
        "/api/sessions/{session_id}/decisions", "/api/sessions/{session_id}/audit", "/api/map/geometry",
        "/api/demo/start", "/api/demo/step", "/api/demo/state", "/api/certificates",
        "/api/certificates/{cert_id}", "/api/certificates/{cert_id}/replay", "/api/decisions/{decision_id}/why",
    ):
        assert path in paths, path


# Prospective API v2 amendment: bind each deliberate test action to its displayed state.
# Assertions about simulator behavior and certificate parity remain unchanged.
def _bound_payload(client, session_id, payload):
    from uuid import uuid4
    context = client.get(f"/api/sessions/{session_id}/context").json()["decision_identity"]
    return {**payload, "request_id": str(uuid4()),
            "expected_state_version": context["state_version"],
            "recommendation_id": context["recommendation_id"]}
