"""Behavioral regressions for state-bound, replay-safe operator decisions."""
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.api.app import create_app

EVIDENCE = {"source_id": "ndma-flood-guidelines-2008", "page": 64,
            "chunk_id": "ndma-flood-guidelines-2008-p64-c0"}


def test_identical_request_replays_original_response(monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as client:
        sid = client.post("/api/sessions", json={"seed": 620000}).json()["session_id"]
        context = client.get(f"/api/sessions/{sid}/context").json()
        binding = context["decision_identity"]
        payload = {"decision": "ACCEPT", "evidence": EVIDENCE,
                   "request_id": str(uuid4()),
                   "expected_state_version": binding["state_version"],
                   "recommendation_id": binding["recommendation_id"]}
        first = client.post(f"/api/sessions/{sid}/decisions", json=payload)
        again = client.post(f"/api/sessions/{sid}/decisions", json=payload)
        assert first.status_code == again.status_code == 200
        assert again.json() == first.json()
        assert len(client.get(f"/api/sessions/{sid}/audit").json()["audit"]) == 1


def test_stale_context_rejected_before_second_transition(monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as client:
        sid = client.post("/api/sessions", json={"seed": 620000}).json()["session_id"]
        binding = client.get(f"/api/sessions/{sid}/context").json()["decision_identity"]
        payload = {"decision": "ACCEPT", "evidence": EVIDENCE,
                   "request_id": str(uuid4()),
                   "expected_state_version": binding["state_version"],
                   "recommendation_id": binding["recommendation_id"]}
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 200
        state = client.get(f"/api/sessions/{sid}/state").json()
        payload["request_id"] = str(uuid4())
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 409
        assert client.get(f"/api/sessions/{sid}/state").json() == state


def test_concurrent_intents_share_only_one_state_transition(monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as client:
        sid = client.post("/api/sessions", json={}).json()["session_id"]
        identity = client.get(f"/api/sessions/{sid}/context").json()["decision_identity"]
        def send(_):
            return client.post(f"/api/sessions/{sid}/decisions", json={
                "decision": "ACCEPT", "evidence": EVIDENCE,
                "request_id": str(uuid4()), "expected_state_version": identity["state_version"],
                "recommendation_id": identity["recommendation_id"],
            }).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(send, range(2))) == [200, 409]
        assert len(client.get(f"/api/sessions/{sid}/audit").json()["audit"]) == 1
        assert client.get(f"/api/sessions/{sid}/state").json()["state_version"] == 1


def test_request_identity_cannot_change_intent_or_session(monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as client:
        sid = client.post("/api/sessions", json={}).json()["session_id"]
        other = client.post("/api/sessions", json={}).json()["session_id"]
        binding = client.get(f"/api/sessions/{sid}/context").json()["decision_identity"]
        payload = {"decision": "REJECT", "reason": "await field report", "evidence": EVIDENCE,
                   "request_id": str(uuid4()), "expected_state_version": binding["state_version"],
                   "recommendation_id": binding["recommendation_id"]}
        assert client.post(f"/api/sessions/{other}/decisions", json=payload).status_code == 409
        assert client.post(f"/api/sessions/{sid}/decisions", json={"decision": "ACCEPT", "evidence": EVIDENCE}).status_code == 422
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 200
        payload["reason"] = "different operator intent"
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 409
        assert client.get(f"/api/sessions/{sid}/state").json()["current_timestep"] == 0


def test_capacity_requires_explicit_close_instead_of_losing_audit():
    from src.api.sessions import SessionRegistry
    from src.geospatial import load_road_graph
    import pytest
    registry = SessionRegistry(load_road_graph(), max_sessions=1)
    first, _ = registry.create(620000, "v3-medium-v1")
    with pytest.raises(RuntimeError, match="capacity"):
        registry.create(620001, "v3-medium-v1")
    assert registry.get(first) is not None
    assert registry.close(first)
    assert registry.get(first) is None
    assert registry.create(620001, "v3-medium-v1")


def test_forged_evidence_is_rejected_without_mutating_state(monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as client:
        sid = client.post("/api/sessions", json={}).json()["session_id"]
        identity = client.get(f"/api/sessions/{sid}/context").json()["decision_identity"]
        state = client.get(f"/api/sessions/{sid}/state").json()
        payload = {"decision": "ACCEPT", "evidence": {**EVIDENCE, "source_id": "invented-ndma"},
                   "request_id": str(uuid4()), "expected_state_version": identity["state_version"],
                   "recommendation_id": identity["recommendation_id"]}
        refused = client.post(f"/api/sessions/{sid}/decisions", json=payload)
        assert refused.status_code == 422
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).json() == refused.json()
        assert client.get(f"/api/sessions/{sid}/state").json() == state
        assert client.get(f"/api/sessions/{sid}/audit").json()["audit"] == []
