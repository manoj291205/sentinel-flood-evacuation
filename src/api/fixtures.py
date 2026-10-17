"""Frozen contract fixtures for Wave A demo, certificates and explanations."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

CONTRACTS = Path(__file__).resolve().parents[2] / "specs/contracts"


def fixture(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


class DemoPlayback:
    def __init__(self, steps: list[dict] | None = None, source: str = "FIXTURE") -> None:
        self.steps = steps if steps is not None else fixture("demo_steps.json")["steps"]
        self.source = source
        self.index = 0
        self.lock = Lock()

    def state(self) -> dict:
        with self.lock:
            return self._state()

    def _state(self) -> dict:
        return {
            "source": self.source,
            "step_index": self.index,
            "step_count": len(self.steps),
            "step": self.steps[self.index],
        }

    def start(self) -> dict:
        with self.lock:
            self.index = 0
            return self._state()

    def step(self, action: str) -> dict:
        with self.lock:
            if action == "next":
                self.index = min(self.index + 1, len(self.steps) - 1)
            elif action == "prev":
                self.index = max(self.index - 1, 0)
            else:
                self.index = 0
            return self._state()
