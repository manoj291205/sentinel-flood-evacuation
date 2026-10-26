"""Lane X checks for the live API paths outside the P34C scripted acceptance run."""

from fastapi.testclient import TestClient

from src.api.app import create_app


def test_uncertified_refusal_is_pushed_without_advancing(monkeypatch):
    monkeypatch.setenv("SENTINEL_DEMO_SOURCE", "FIXTURE")
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as client:
        created = client.post("/api/sessions", json={
            "seed": 620003, "regime": "v4-medium-dt2-v1", "certified": True,
        })
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        context = client.get(f"/api/sessions/{session_id}/context").json()
        blocked = next(item for item in context["certified"]["alternatives"] if not item["certified"])
        with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
            assert ws.receive_json()["type"] == "state"
            refused = client.post(f"/api/sessions/{session_id}/decisions", json=_bound_payload(client, session_id, {
                "decision": "OVERRIDE", "selected_action": blocked["action_key"],
                "reason": "field request", "evidence": {
                    "source_id": "ndma-flood-guidelines-2008", "page": 64,
                    "chunk_id": "ndma-flood-guidelines-2008-p64-c0",
                },
            }))
            pushed = ws.receive_json()
        assert refused.status_code == 422
        assert pushed["type"] == "refusal"
        assert pushed["payload"]["flag"] == "UNCERTIFIED_OVERRIDE_REFUSED"
        assert pushed["payload"]["action_key"] == blocked["action_key"]
        assert client.get(f"/api/sessions/{session_id}/state").json()["current_timestep"] == 0
        assert client.get(f"/api/sessions/{session_id}/certificates").json()["certificates"] == []


# Prospective API v2 amendment: bind each deliberate test action to its displayed state.
# Assertions about simulator behavior and certificate parity remain unchanged.
def _bound_payload(client, session_id, payload):
    from uuid import uuid4
    context = client.get(f"/api/sessions/{session_id}/context").json()["decision_identity"]
    return {**payload, "request_id": str(uuid4()),
            "expected_state_version": context["state_version"],
            "recommendation_id": context["recommendation_id"]}
