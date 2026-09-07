"""Semantic actions and auditable Phase 3/4 evacuation/environment events."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias


class DispatchStatus(str, Enum):
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"


class AuditEventType(str, Enum):
    DISPATCH_CREATED = "DISPATCH_CREATED"
    ARRIVAL_PROCESSED = "ARRIVAL_PROCESSED"
    WAIT = "WAIT"
    ACTION_REJECTED = "ACTION_REJECTED"
    EPISODE_TERMINATED = "EPISODE_TERMINATED"
    FLOOD_STATE_UPDATED = "FLOOD_STATE_UPDATED"
    ROUTE_CLOSED = "ROUTE_CLOSED"
    SHELTER_RESTRICTED = "SHELTER_RESTRICTED"
    SHELTER_CLOSED = "SHELTER_CLOSED"
    TRAVEL_TIME_REALIZED = "TRAVEL_TIME_REALIZED"


class ActionRejectionCode(str, Enum):
    EPISODE_TERMINAL = "EPISODE_TERMINAL"
    INVALID_ACTION_TYPE = "INVALID_ACTION_TYPE"
    UNKNOWN_ZONE = "UNKNOWN_ZONE"
    UNKNOWN_SHELTER = "UNKNOWN_SHELTER"
    NO_ROUTE = "NO_ROUTE"
    AMBIGUOUS_ROUTE = "AMBIGUOUS_ROUTE"
    ROUTE_UNREACHABLE = "ROUTE_UNREACHABLE"
    INVALID_TRAVEL_TIME = "INVALID_TRAVEL_TIME"
    NO_POPULATION = "NO_POPULATION"
    SHELTER_CLOSED = "SHELTER_CLOSED"
    NO_CAPACITY = "NO_CAPACITY"
    EVACUATION_DISABLED = "EVACUATION_DISABLED"
    NO_DISPATCH_AVAILABILITY = "NO_DISPATCH_AVAILABILITY"


@dataclass(frozen=True)
class DispatchAction:
    zone_id: str
    shelter_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "action_type": "DISPATCH",
            "zone_id": self.zone_id,
            "shelter_id": self.shelter_id,
        }


@dataclass(frozen=True)
class WaitAction:
    def to_dict(self) -> dict[str, str]:
        return {"action_type": "WAIT"}


SimulationAction: TypeAlias = DispatchAction | WaitAction
WAIT = WaitAction()


@dataclass(frozen=True)
class DispatchEvent:
    event_id: str
    source_zone_id: str
    destination_shelter_id: str
    people: int
    departure_timestep: int
    arrival_timestep: int
    route_id: str
    travel_lag_steps: int
    base_travel_time_minutes: float
    realized_travel_time_minutes: float
    travel_multiplier: float
    uncertainty_config_id: str | None
    status: DispatchStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_zone_id": self.source_zone_id,
            "destination_shelter_id": self.destination_shelter_id,
            "people": self.people,
            "departure_timestep": self.departure_timestep,
            "arrival_timestep": self.arrival_timestep,
            "route_id": self.route_id,
            "travel_lag_steps": self.travel_lag_steps,
            "base_travel_time_minutes": self.base_travel_time_minutes,
            "realized_travel_time_minutes": self.realized_travel_time_minutes,
            "travel_multiplier": self.travel_multiplier,
            "uncertainty_config_id": self.uncertainty_config_id,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class AuditRecord:
    event_type: AuditEventType
    timestep: int
    event_id: str | None = None
    zone_id: str | None = None
    shelter_id: str | None = None
    route_id: str | None = None
    people: int | None = None
    reason_code: str | None = None
    message: str | None = None
    entity_kind: str | None = None
    uncertainty_config_id: str | None = None
    value_before: float | None = None
    value_after: float | None = None
    probability: float | None = None
    hazard_proxy: float | None = None
    expected_value: float | None = None
    uncertainty: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestep": self.timestep,
            "event_id": self.event_id,
            "zone_id": self.zone_id,
            "shelter_id": self.shelter_id,
            "route_id": self.route_id,
            "people": self.people,
            "reason_code": self.reason_code,
            "message": self.message,
            "entity_kind": self.entity_kind,
            "uncertainty_config_id": self.uncertainty_config_id,
            "value_before": self.value_before,
            "value_after": self.value_after,
            "probability": self.probability,
            "hazard_proxy": self.hazard_proxy,
            "expected_value": self.expected_value,
            "uncertainty": self.uncertainty,
        }
