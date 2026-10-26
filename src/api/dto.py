"""API request and top-level response models."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    seed: int = Field(default=620000, ge=0)
    regime: str = "v3-medium-v1"
    certified: bool = False
    params_id: str | None = None


class EvidenceDTO(BaseModel):
    source_id: str
    page: int = Field(gt=0)
    chunk_id: str


class DecisionRequest(BaseModel):
    request_id: UUID
    expected_state_version: int = Field(ge=0)
    recommendation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["ACCEPT", "OVERRIDE", "REJECT"]
    selected_action: str | None = None
    reason: str = ""
    evidence: EvidenceDTO


class DemoStepRequest(BaseModel):
    action: Literal["next", "prev", "reset"]


class ReplayRequest(BaseModel):
    tamper: bool = False
