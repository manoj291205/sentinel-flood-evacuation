"""API request and top-level response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    seed: int = Field(default=620000, ge=0)
    regime: str = "v3-medium-v1"


class EvidenceDTO(BaseModel):
    source_id: str
    page: int = Field(gt=0)
    chunk_id: str


class DecisionRequest(BaseModel):
    decision: Literal["ACCEPT", "OVERRIDE", "REJECT"]
    selected_action: str | None = None
    reason: str = ""
    evidence: EvidenceDTO


class DemoStepRequest(BaseModel):
    action: Literal["next", "prev", "reset"]


class ReplayRequest(BaseModel):
    tamper: bool = False
