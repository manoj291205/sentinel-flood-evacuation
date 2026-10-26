"""Independent final review of live provenance and post-commit failure recovery."""
import importlib
import threading
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from src.api.app import create_app


EVIDENCE = {"source_id": "ndma-flood-guidelines-2008", "page": 64,
            "chunk_id": "ndma-flood-guidelines-2008-p64-c0"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app(), raise_server_exceptions=False) as result:
        yield result


def begin(client, certified=False):
    response = client.post("/api/sessions", json={
        "seed": 620003, "certified": certified,
        "regime": "v4-medium-dt2-v1" if certified else "v3-medium-v1",
        **({"params_id": "v4-cert-test-v1"} if certified else {}),
    })
    assert response.status_code == 200
    sid = response.json()["session_id"]
    context = client.get(f"/api/sessions/{sid}/context").json()
    identity = context["decision_identity"]
    payload = {"request_id": str(uuid4()), "expected_state_version": identity["state_version"],
               "recommendation_id": identity["recommendation_id"], "decision": "ACCEPT",
               "evidence": EVIDENCE}
    return sid, context, payload


def test_certified_audit_names_the_planner_that_made_its_recommendation(client):
    sid, context, payload = begin(client, certified=True)
    response = client.post(f"/api/sessions/{sid}/decisions", json=payload)
    assert response.status_code == 200
    assert context["recommendation"]["planner_id"] == "certified_v4"
    assert response.json()["audit_record"]["planner"] == "certified_v4"
    exported = client.get(f"/api/sessions/{sid}/audit.json").json()
    assert exported["audit"][0]["planner"] == "certified_v4"
    assert exported["provenance"]["planner"] == context["recommendation"]["planner_id"]


def test_api_refuses_an_untrusted_sink_subclass_before_mutation(monkeypatch, client):
    from src.actuation.commands import InMemorySink
    from src.simulation_session import SimulationSession
    original = SimulationSession.__init__
    class UntrustedSink(InMemorySink):
        pass
    def configured(session, *args, **kwargs):
        original(session, *args, **kwargs)
        if session.certified:
            session.gate.sink = UntrustedSink()
    monkeypatch.setattr(SimulationSession, "__init__", configured)
    sid, _, payload = begin(client, certified=True)
    assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 503
    assert client.get(f"/api/sessions/{sid}/state").json()["state_version"] == 0
    assert client.get(f"/api/sessions/{sid}/audit").json()["audit"] == []


def test_websocket_snapshot_and_subscription_have_one_ordered_commit_cut(monkeypatch, client):
    module = importlib.import_module("src.api.app")
    original = module.asyncio.to_thread
    entered, release = threading.Event(), threading.Event()
    async def delayed(function, *args, **kwargs):
        if function.__name__ == "initial_snapshot":
            entered.set()
            assert await original(release.wait, 10)
        return await original(function, *args, **kwargs)
    sid, _, payload = begin(client)
    monkeypatch.setattr(module.asyncio, "to_thread", delayed)
    with client.websocket_connect(f"/ws/sessions/{sid}") as websocket:
        assert entered.wait(5)
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 200
        release.set()
        first = websocket.receive_json()
        assert first["type"] == "state" and first["payload"]["state_version"] == 1
        identity = client.get(f"/api/sessions/{sid}/context").json()["decision_identity"]
        next_payload = {**payload, "request_id": str(uuid4()),
                        "expected_state_version": identity["state_version"],
                        "recommendation_id": identity["recommendation_id"]}
        assert client.post(f"/api/sessions/{sid}/decisions", json=next_payload).status_code == 200
        assert websocket.receive_json()["seq"] > first["seq"]


@pytest.mark.parametrize("failure", [ValueError, RuntimeError])
@pytest.mark.parametrize("stage", ["response", "observation"])
@pytest.mark.parametrize("certified", [False, True])
def test_retry_recovers_one_decision_after_postcommit_failure(
        monkeypatch, client, failure, stage, certified):
    """An observation/rendering failure must not make a committed action unrecoverable."""
    sid, _, payload = begin(client, certified=certified)
    module = importlib.import_module("src.api.app")
    failed = False

    if stage == "response":
        original = module._state_dto

        def interrupted_projection(entry):
            nonlocal failed
            if entry.session.audit and not failed:
                failed = True
                raise failure("one-time response projection failure after commit")
            return original(entry)

        monkeypatch.setattr(module, "_state_dto", interrupted_projection)
    else:
        from src.simulation_session import SimulationSession
        original = SimulationSession._observe

        def interrupted_observation(session):
            nonlocal failed
            if session.audit and not failed:
                failed = True
                raise failure("one-time post-commit observation failure")
            return original(session)

        monkeypatch.setattr(SimulationSession, "_observe", interrupted_observation)
    first = client.post(f"/api/sessions/{sid}/decisions", json=payload)
    assert failed
    assert first.status_code == 503
    assert client.get(f"/api/sessions/{sid}/state").json()["state_version"] == 0
    assert client.get(f"/api/sessions/{sid}/audit").json()["audit"] == []
    assert client.get(f"/api/sessions/{sid}/certificates").json()["certificates"] == []
    retry = client.post(f"/api/sessions/{sid}/decisions", json=payload)
    assert retry.status_code == 200, retry.text
    assert retry.json()["state"]["state_version"] == 1
    assert len(client.get(f"/api/sessions/{sid}/audit").json()["audit"]) == 1
    assert client.post(f"/api/sessions/{sid}/decisions", json=payload).json() == retry.json()
