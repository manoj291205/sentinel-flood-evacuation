"""Independent behavioral review of retry, concurrency and explicit session closure."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import asyncio
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
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with TestClient(create_app(), raise_server_exceptions=False) as result:
        yield result


def session(client, certified=False):
    response = client.post("/api/sessions", json={"seed": 620003,
        "regime": "v4-medium-dt2-v1" if certified else "v3-medium-v1",
        "certified": certified, **({"params_id": "v4-cert-test-v1"} if certified else {})})
    assert response.status_code == 200
    return response.json()["session_id"]


def intent(client, sid, decision="ACCEPT", **changes):
    response = client.get(f"/api/sessions/{sid}/context")
    assert response.status_code == 200
    identity = response.json()["decision_identity"]
    return {"request_id": str(uuid4()), "expected_state_version": identity["state_version"],
            "recommendation_id": identity["recommendation_id"], "decision": decision,
            "evidence": EVIDENCE, **changes}


def test_concurrent_identical_retries_return_one_receipt(client):
    sid = session(client)
    payload = intent(client, sid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(f"/api/sessions/{sid}/decisions", json=payload), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert len(client.get(f"/api/sessions/{sid}/audit").json()["audit"]) == 1


def test_stale_override_never_records_a_refusal_or_advances(client):
    sid = session(client)
    context = client.get(f"/api/sessions/{sid}/context").json()
    alternative = context["allowed_override_actions"][0]["action_key"]
    binding = context["decision_identity"]
    accept = {"request_id": str(uuid4()), "expected_state_version": binding["state_version"],
              "recommendation_id": binding["recommendation_id"], "decision": "ACCEPT", "evidence": EVIDENCE}
    assert client.post(f"/api/sessions/{sid}/decisions", json=accept).status_code == 200
    before = client.get(f"/api/sessions/{sid}/audit.json").json()
    stale = {**accept, "request_id": str(uuid4()), "decision": "OVERRIDE",
             "selected_action": alternative, "reason": "stale alternative"}
    assert client.post(f"/api/sessions/{sid}/decisions", json=stale).status_code == 409
    after = client.get(f"/api/sessions/{sid}/audit.json").json()
    assert after["audit"] == before["audit"]
    assert after["refusals"] == before["refusals"]
    assert after["state_version"] == before["state_version"]


def test_cached_receipt_survives_terminal_state(client):
    sid = session(client)
    last_payload = last_response = None
    for _ in range(50):
        if client.get(f"/api/sessions/{sid}/state").json()["terminal"]:
            break
        last_payload = intent(client, sid)
        last_response = client.post(f"/api/sessions/{sid}/decisions", json=last_payload)
        assert last_response.status_code == 200
    assert client.get(f"/api/sessions/{sid}/state").json()["terminal"]
    again = client.post(f"/api/sessions/{sid}/decisions", json=last_payload)
    assert again.status_code == 200
    assert again.json() == last_response.json()


def test_request_uuid_is_scoped_to_its_bound_session(client):
    first, second = session(client), session(client)
    request_id = str(uuid4())
    for sid in (first, second):
        payload = intent(client, sid, "REJECT", reason="check independently", request_id=request_id)
        assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 200
        assert len(client.get(f"/api/sessions/{sid}/audit").json()["audit"]) == 1


@pytest.mark.parametrize("change", [{"request_id": "not-a-uuid"}, {"request_id": ""},
                                    {"expected_state_version": -1}, {"recommendation_id": "bad"}])
def test_malformed_bindings_are_rejected_without_mutation(client, change):
    sid = session(client)
    before = client.get(f"/api/sessions/{sid}/state").json()
    payload = intent(client, sid, **change)
    assert client.post(f"/api/sessions/{sid}/decisions", json=payload).status_code == 422
    assert client.get(f"/api/sessions/{sid}/state").json() == before


@pytest.mark.parametrize("certified", [False, True])
def test_reject_keeps_version_specific_advance_and_hold_semantics(client, certified):
    sid = session(client, certified)
    before = client.get(f"/api/sessions/{sid}/state").json()
    response = client.post(f"/api/sessions/{sid}/decisions", json=intent(
        client, sid, "REJECT", reason="operator pause"))
    assert response.status_code == 200
    after = response.json()["state"]
    assert after["current_timestep"] == before["current_timestep"] + int(certified)
    assert after["state_version"] == before["state_version"] + 1
    if certified:
        assert response.json()["certificates"][-1]["kind"] == "HOLD"
    assert response.json()["audit_record"]["executed_action"] == "NONE"


def test_closed_subscriber_loop_cannot_destroy_committed_receipt(monkeypatch, client):
    module = importlib.import_module("src.api.app")

    class ClosedLoop:
        def is_closed(self):
            return False  # closing can race the check

        def call_soon_threadsafe(self, *args):
            raise RuntimeError("subscriber loop closed during delivery")

    class AsyncProxy:
        def get_running_loop(self):
            return ClosedLoop()

        def __getattr__(self, name):
            return getattr(asyncio, name)

    monkeypatch.setattr(module, "asyncio", AsyncProxy())
    sid = session(client)
    with client.websocket_connect(f"/ws/sessions/{sid}") as websocket:
        assert websocket.receive_json()["type"] == "state"
        payload = intent(client, sid)
        first = client.post(f"/api/sessions/{sid}/decisions", json=payload)
        assert first.status_code == 200
        again = client.post(f"/api/sessions/{sid}/decisions", json=payload)
        assert again.status_code == 200
        assert again.json() == first.json()
        assert len(client.get(f"/api/sessions/{sid}/audit").json()["audit"]) == 1


def test_slow_subscriber_is_bounded_and_told_to_resynchronize(monkeypatch, client):
    module = importlib.import_module("src.api.app")
    original = module.asyncio
    queues = []
    release = threading.Event()

    class SlowQueue(asyncio.Queue):
        async def get(self):
            await asyncio.to_thread(release.wait)
            return await super().get()

    class AsyncProxy:
        def Queue(self, *args, **kwargs):
            queue = SlowQueue(*args, **kwargs)
            for _ in range(queue.maxsize or 256):
                queue.put_nowait({"type": "test_backlog"})
            queues.append(queue)
            return queue

        def __getattr__(self, name):
            return getattr(original, name)

    monkeypatch.setattr(module, "asyncio", AsyncProxy())
    sid = session(client)
    with client.websocket_connect(f"/ws/sessions/{sid}") as websocket:
        try:
            websocket.receive_json()
            assert len(queues) == 1 and queues[0].maxsize > 0
            response = client.post(f"/api/sessions/{sid}/decisions", json=intent(client, sid))
            assert response.status_code == 200
            assert queues[0].qsize() <= queues[0].maxsize
            release.set()
            closed = websocket.receive()
            assert closed["type"] == "websocket.close" and closed["code"] == 1013
        finally:
            release.set()


def test_explicit_close_disconnects_subscribers(client):
    sid = session(client)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with client.websocket_connect(f"/ws/sessions/{sid}") as websocket:
            websocket.receive_json()
            pending = pool.submit(websocket.receive)
            assert client.delete(f"/api/sessions/{sid}").status_code == 200
            try:
                message = pending.result(timeout=2)
            except TimeoutError:
                websocket.close()
                pytest.fail("explicit session close left its subscriber waiting")
            assert message["type"] == "websocket.close" or message.get("text", "").find("session_closed") >= 0
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def test_context_fetched_before_close_cannot_prepare_a_closed_session(monkeypatch, client):
    from src.api.sessions import SessionRegistry

    sid = session(client)
    original = SessionRegistry.get
    fetched, release = threading.Event(), threading.Event()

    def delayed_get(registry, requested):
        entry = original(registry, requested)
        if requested == sid:
            fetched.set()
            assert release.wait(timeout=8)
        return entry

    monkeypatch.setattr(SessionRegistry, "get", delayed_get)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.get, f"/api/sessions/{sid}/context")
        try:
            assert fetched.wait(timeout=8)
            assert client.delete(f"/api/sessions/{sid}").status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=8).status_code == 410
