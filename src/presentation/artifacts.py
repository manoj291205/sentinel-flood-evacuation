"""Presentation-facing loaders for frozen contract material."""

from __future__ import annotations

import json
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[2] / "specs/contracts"


def load_contract_fixture(name: str) -> dict:
    allowed = {"demo_steps.json", "certificates_fixture.json", "decision_why_fixture.json"}
    if name not in allowed:
        raise ValueError("unknown contract fixture")
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))
