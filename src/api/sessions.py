"""Bounded, in-memory SimulationSession registry."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from src.geospatial.road_network import RoadGraph
from src.simulation_session import SimulationSession


@dataclass
class SessionEntry:
    session: SimulationSession
    lock: Lock = field(default_factory=Lock)
    sequence: int = 0
    refusals: list[dict] = field(default_factory=list)

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


class SessionRegistry:
    def __init__(self, graph: RoadGraph, max_sessions: int = 8) -> None:
        self.graph = graph
        self.max_sessions = max_sessions
        self._entries: OrderedDict[str, SessionEntry] = OrderedDict()
        self._lock = Lock()

    def create(self, seed: int, regime: str, *, certified: bool = False,
               params_id: str | None = None) -> tuple[str, SessionEntry]:
        if certified:
            if regime not in {"v4-low-dt2-v1", "v4-medium-dt2-v1", "v4-high-dt2-v1"}:
                raise ValueError("certified sessions require a v4 dt2 world")
            if params_id not in (None, "v4-cert-test-v1"):
                raise ValueError("certified sessions require v4-cert-test-v1")
            session = SimulationSession(seed, regime, graph=self.graph, certified=True,
                                        params_id="v4-cert-test-v1", recertify=True)
        else:
            session = SimulationSession(seed, regime, graph=self.graph)
        session_id = uuid4().hex
        entry = SessionEntry(session)
        with self._lock:
            self._entries[session_id] = entry
            while len(self._entries) > self.max_sessions:
                self._entries.popitem(last=False)
        return session_id, entry

    def get(self, session_id: str) -> SessionEntry | None:
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is not None:
                self._entries.move_to_end(session_id)
            return entry
