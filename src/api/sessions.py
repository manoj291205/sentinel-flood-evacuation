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

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


class SessionRegistry:
    def __init__(self, graph: RoadGraph, max_sessions: int = 8) -> None:
        self.graph = graph
        self.max_sessions = max_sessions
        self._entries: OrderedDict[str, SessionEntry] = OrderedDict()
        self._lock = Lock()

    def create(self, seed: int, regime: str) -> tuple[str, SessionEntry]:
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
