"""Small in-memory console session for the exploratory outage sequence."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from .outage import OutageEngine
from .shares import TEAMS

NOTE = "Exploratory: not part of the pre-registered evaluation."


@dataclass
class EscrowSession:
    engine: OutageEngine
    session_id: str = field(default_factory=lambda: uuid4().hex)
    lock: Lock = field(default_factory=Lock)

    @classmethod
    def start(cls, seed: int, world_id: str, mode: str, *, graph=None) -> "EscrowSession":
        return cls(OutageEngine(seed, world_id, mode, graph=graph))

    def step(self) -> None:
        if self.engine.network == "OFFLINE":
            self.engine.offline_step()
        else:
            self.engine.online_step()

    def cut(self) -> None:
        self.engine.cut()

    def restore(self) -> None:
        self.engine.restore()

    def status(self, honesty: str) -> dict:
        engine = self.engine
        teams = []
        if engine.network == "OFFLINE":
            teams = [{"team": team, "zones": list(engine.zones[team]),
                      "seats_total": sum(engine.seats[team].values()),
                      "seats_left": sum(engine.adapters[team].left.values())}
                     for team in TEAMS]
        certs = [*engine.base.certificates(),
                 *(item["certificate"] for item in engine.certificates)]
        return {
            "session_id": self.session_id, "network": engine.network,
            "label": "Simulated network outage" if engine.network == "OFFLINE" else None,
            "mode": engine.mode, "timestep": engine.sim.state.current_timestep,
            "teams": teams, "blocked": list(engine.blocked),
            "last_reconciliation": engine.last_reconciliation,
            "certificates": [item["cert_id"] for item in reversed(certs)],
            "note": NOTE, "simulated": True, "honesty": honesty,
        }
