"""Local FastAPI facade over live V3 sessions and frozen Wave A fixtures."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from src.api.dto import DecisionRequest, DemoStepRequest, ReplayRequest, SessionRequest
from src.api.fixtures import DemoPlayback
from src.api.sessions import SessionEntry, SessionRegistry
from src.geospatial import load_road_graph
from src.human_decision import (
    EvidenceReference, HumanDecisionError, action_key, action_label,
    allowed_override_actions,
)
from src.presentation.artifacts import load_contract_fixture
from src.presentation.evidence import evidence_items
from src.presentation.map_geometry import project_graph

HONESTY = "REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED"
VERSION = "v4-api-wave-a"


def _public(payload: dict, source: str = "LIVE") -> dict:
    return {**payload, "simulated": True, "honesty": HONESTY, "source": source}


def _session_dto(session_id: str, entry: SessionEntry) -> dict:
    session = entry.session
    return _public({
        "session_id": session_id,
        "scenario_id": session.scenario.scenario_id,
        "seed": session.seed,
        "regime": session.simulator.config.config_id,
        "timestep": session.state.current_timestep,
        "horizon_steps": session.scenario.time.horizon_steps,
        "timestep_minutes": session.scenario.time.timestep_minutes,
        "graph_version": session.graph.graph_version,
        "graph_fingerprint": session.graph.graph_fingerprint,
    })


def _state_dto(entry: SessionEntry) -> dict:
    session = entry.session
    state = session.state
    return _public({
        **state.to_policy_observation(),
        "summary": session.summary(),
        "route_rows": session.route_rows(),
        "kpis": {
            "waiting": state.population_remaining,
            "in_transit": state.people_in_transit,
            "safe": state.people_safely_arrived,
            "certificates_issued": 0,
        },
    })


def _context_dto(entry: SessionEntry) -> dict:
    context = entry.session.context()
    if context is None:
        raise HTTPException(409, "episode is complete")
    action = context.recommendation.action
    return _public({
        "recommendation": {
            "action_key": action_key(action),
            "label": action_label(action),
            "planner_id": context.recommendation.planner_name,
        },
        "snapshot": context.snapshot.to_dict(),
        "allowed_override_actions": [
            {"action_key": action_key(item), "label": action_label(item), "action": item.to_dict()}
            for item in allowed_override_actions(context)
        ],
    })


def create_app() -> FastAPI:
    graph = load_road_graph()
    registry = SessionRegistry(graph)
    demo = DemoPlayback()
    certificates = load_contract_fixture("certificates_fixture.json")["certificates"]
    cert_by_id = {item["cert_id"]: item for item in certificates}
    explanations = load_contract_fixture("decision_why_fixture.json")["items"]
    why_by_id = {item["decision_id"]: item for item in explanations}
    system_fixture = load_contract_fixture("system_status_fixture.json")
    subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
    app = FastAPI(title="Sentinel local API", version=VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def response_provenance(request, call_next):
        response = await call_next(request)
        response.headers["X-Sentinel-Simulated"] = "true"
        response.headers["X-Sentinel-Honesty"] = HONESTY.replace(" · ", " | ")
        if "X-Sentinel-Source" not in response.headers:
            response.headers["X-Sentinel-Source"] = "LIVE"
        return response

    def entry_or_404(session_id: str) -> SessionEntry:
        entry = registry.get(session_id)
        if entry is None:
            raise HTTPException(404, "session not found")
        return entry

    @app.get("/api/health")
    def health():
        return _public({"status": "ok", "version": VERSION, "graph_fingerprint": graph.graph_fingerprint})

    @app.post("/api/sessions")
    def create_session(body: SessionRequest):
        try:
            session_id, entry = registry.create(body.seed, body.regime)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return _session_dto(session_id, entry)

    @app.get("/api/sessions/{session_id}/state")
    def session_state(session_id: str):
        entry = entry_or_404(session_id)
        with entry.lock:
            return _state_dto(entry)

    @app.get("/api/sessions/{session_id}/context")
    def session_context(session_id: str):
        entry = entry_or_404(session_id)
        with entry.lock:
            return _context_dto(entry)

    @app.post("/api/sessions/{session_id}/decisions")
    async def decide(session_id: str, body: DecisionRequest):
        entry = entry_or_404(session_id)
        with entry.lock:
            session = entry.session
            old_timeline_length = len(session.timeline)
            try:
                selected_action = None
                if body.selected_action is not None:
                    context = session.context()
                    if context is None:
                        raise HumanDecisionError("episode is complete")
                    selected_action = next(
                        (action for action in context.snapshot.canonical_actions
                         if action_key(action) == body.selected_action), None
                    )
                    if selected_action is None:
                        raise HumanDecisionError("selected action is unknown")
                record, _ = session.decide(
                    body.decision,
                    EvidenceReference(**body.evidence.model_dump()),
                    selected_action=selected_action,
                    reason=body.reason,
                )
            except (HumanDecisionError, ValueError) as exc:
                raise HTTPException(422, str(exc)) from exc
            state = _state_dto(entry)
            new_events = session.timeline[old_timeline_length:]
            messages = [
                {"seq": entry.next_sequence(), "type": "decision", "payload": record},
                *(
                    {"seq": entry.next_sequence(), "type": "event", "payload": event}
                    for event in new_events
                ),
                {"seq": entry.next_sequence(), "type": "state", "payload": state},
            ]
        for subscriber in tuple(subscribers[session_id]):
            for message in messages:
                subscriber.put_nowait(message)
        return _public({"audit_record": record, "state": state})

    @app.get("/api/sessions/{session_id}/audit")
    def audit(session_id: str):
        entry = entry_or_404(session_id)
        with entry.lock:
            return _public({"audit": list(entry.session.audit)})

    @app.get("/api/sessions/{session_id}/audit.csv")
    def audit_csv(session_id: str):
        entry = entry_or_404(session_id)
        with entry.lock:
            return PlainTextResponse(entry.session.export_csv(), media_type="text/csv")

    @app.get("/api/sessions/{session_id}/audit.json")
    def audit_json(session_id: str):
        entry = entry_or_404(session_id)
        with entry.lock:
            return _public(json.loads(entry.session.export_json()))

    @app.get("/api/sessions/{session_id}/timeline")
    def timeline(session_id: str):
        entry = entry_or_404(session_id)
        with entry.lock:
            return _public({"timeline": list(entry.session.timeline)})

    @app.get("/api/map/geometry")
    def map_geometry():
        return _public(project_graph(graph))

    @app.post("/api/demo/start")
    def demo_start(response: Response):
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return _public(demo.start(), "FIXTURE")

    @app.post("/api/demo/step")
    def demo_step(body: DemoStepRequest, response: Response):
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return _public(demo.step(body.action), "FIXTURE")

    @app.get("/api/demo/state")
    def demo_state(response: Response):
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return _public(demo.state(), "FIXTURE")

    @app.get("/api/certificates")
    def certificate_list(response: Response):
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return _public({"certificates": certificates}, "FIXTURE")

    @app.get("/api/evidence")
    def evidence():
        return _public({"items": evidence_items()}, "ARTIFACT")

    @app.get("/api/system/status")
    def system_status(response: Response):
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return system_fixture

    @app.get("/api/system/acks")
    def system_acks(response: Response):
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return _public({"items": []}, "FIXTURE")

    @app.get("/api/certificates/{cert_id}")
    def certificate(cert_id: str, response: Response):
        if cert_id not in cert_by_id:
            raise HTTPException(404, "certificate not found")
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return cert_by_id[cert_id]

    @app.post("/api/certificates/{cert_id}/replay")
    def replay(cert_id: str, body: ReplayRequest, response: Response):
        if cert_id not in cert_by_id:
            raise HTTPException(404, "certificate not found")
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return _public({
            "result": "MISMATCH" if body.tamper else "MATCH",
            "mismatched_fields": ["forecast_hash"] if body.tamper else [],
        }, "FIXTURE")

    @app.get("/api/decisions/{decision_id}/why")
    def why(decision_id: str, response: Response):
        if decision_id not in why_by_id:
            raise HTTPException(404, "decision explanation not found")
        response.headers["X-Sentinel-Source"] = "FIXTURE"
        return why_by_id[decision_id]

    @app.websocket("/ws/sessions/{session_id}")
    async def websocket_session(websocket: WebSocket, session_id: str):
        entry = registry.get(session_id)
        if entry is None:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue()
        subscribers[session_id].add(queue)
        try:
            with entry.lock:
                first = {"seq": entry.next_sequence(), "type": "state", "payload": _state_dto(entry)}
            await websocket.send_json(first)
            while True:
                receive_task = asyncio.create_task(websocket.receive())
                queue_task = asyncio.create_task(queue.get())
                done, pending = await asyncio.wait(
                    {receive_task, queue_task}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                if receive_task in done and receive_task.result()["type"] == "websocket.disconnect":
                    break
                if queue_task in done:
                    await websocket.send_json(queue_task.result())
        except WebSocketDisconnect:
            pass
        finally:
            subscribers[session_id].discard(queue)

    return app
