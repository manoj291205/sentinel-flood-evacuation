"""Threadpool FastAPI endpoints for the exploratory two-team network demonstration."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.escrow.session import EscrowSession

WORLDS = {"v4-low-dt2-v1", "v4-medium-dt2-v1", "v4-high-dt2-v1"}


class EscrowRequest(BaseModel):
    seed: int = Field(default=620003, ge=0)
    regime: str = "v4-medium-dt2-v1"
    mode: Literal["escrow", "last_known"] = "escrow"


def install_escrow_routes(app: FastAPI, graph, honesty: str) -> None:
    sessions: OrderedDict[str, EscrowSession] = OrderedDict()
    registry_lock = Lock()

    def get(session_id: str) -> EscrowSession:
        with registry_lock:
            session = sessions.get(session_id)
            if session is None:
                raise HTTPException(404, "escrow session not found")
            sessions.move_to_end(session_id)
            return session

    @app.post("/api/escrow/sessions")
    def create(body: EscrowRequest):
        if body.regime not in WORLDS:
            raise HTTPException(422, "escrow sessions require a v4 dt2 world")
        session = EscrowSession.start(body.seed, body.regime, body.mode, graph=graph)
        with registry_lock:
            sessions[session.session_id] = session
            while len(sessions) > 4:
                sessions.popitem(last=False)
        return session.status(honesty)

    @app.get("/api/escrow/sessions/{session_id}")
    def status(session_id: str):
        session = get(session_id)
        with session.lock:
            return session.status(honesty)

    @app.post("/api/escrow/sessions/{session_id}/step")
    def step(session_id: str):
        session = get(session_id)
        with session.lock:
            session.step()
            return session.status(honesty)

    @app.post("/api/escrow/sessions/{session_id}/cut")
    def cut(session_id: str):
        session = get(session_id)
        with session.lock:
            try:
                session.cut()
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            return session.status(honesty)

    @app.post("/api/escrow/sessions/{session_id}/restore")
    def restore(session_id: str):
        session = get(session_id)
        with session.lock:
            try:
                session.restore()
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            return session.status(honesty)
