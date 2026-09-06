"""Immutable runtime snapshots shared by deterministic and stochastic simulators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .events import AuditRecord, DispatchEvent, DispatchStatus
from .schemas import ShelterStatus


class TerminalReason(str, Enum):
    ALL_EVACUATED = "ALL_EVACUATED"
    HORIZON_REACHED = "HORIZON_REACHED"


@dataclass(frozen=True)
class ZoneState:
    zone_id: str
    population_remaining: int
    flood_severity_current: float
    flood_severity_previous: float | None = None
    observed_severity_change: float = 0.0
    forecast_mean_next: float | None = None
    forecast_std_next: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "population_remaining": self.population_remaining,
            "flood_severity_current": self.flood_severity_current,
            "flood_severity_previous": self.flood_severity_previous,
            "observed_severity_change": self.observed_severity_change,
            "forecast_mean_next": self.forecast_mean_next,
            "forecast_std_next": self.forecast_std_next,
        }


@dataclass(frozen=True)
class ShelterState:
    shelter_id: str
    capacity_total: int
    occupancy_current: int
    capacity_reserved: int
    status_current: ShelterStatus
    flood_severity_current: float
    flood_severity_previous: float | None = None
    observed_severity_change: float = 0.0
    forecast_mean_next: float | None = None
    forecast_std_next: float | None = None

    @property
    def capacity_available(self) -> int:
        """Unoccupied and unreserved capacity available to a new dispatch."""
        return self.capacity_total - self.occupancy_current - self.capacity_reserved

    def to_dict(self) -> dict[str, Any]:
        return {
            "shelter_id": self.shelter_id,
            "capacity_total": self.capacity_total,
            "occupancy_current": self.occupancy_current,
            "capacity_reserved": self.capacity_reserved,
            "capacity_available": self.capacity_available,
            "status_current": self.status_current.value,
            "flood_severity_current": self.flood_severity_current,
            "flood_severity_previous": self.flood_severity_previous,
            "observed_severity_change": self.observed_severity_change,
            "forecast_mean_next": self.forecast_mean_next,
            "forecast_std_next": self.forecast_std_next,
        }


@dataclass(frozen=True)
class RouteState:
    route_id: str
    source_zone_id: str
    destination_shelter_id: str
    reachable_current: bool
    travel_time_current: float | None
    base_travel_time_minutes: float | None = None
    expected_travel_time_minutes: float | None = None
    travel_time_uncertainty_minutes: float | None = None
    estimated_closure_probability: float = 0.0
    route_hazard_proxy: float | None = None
    closed_at_timestep: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "source_zone_id": self.source_zone_id,
            "destination_shelter_id": self.destination_shelter_id,
            "reachable_current": self.reachable_current,
            "travel_time_current": self.travel_time_current,
            "base_travel_time_minutes": self.base_travel_time_minutes,
            "expected_travel_time_minutes": self.expected_travel_time_minutes,
            "travel_time_uncertainty_minutes": self.travel_time_uncertainty_minutes,
            "estimated_closure_probability": self.estimated_closure_probability,
            "route_hazard_proxy": self.route_hazard_proxy,
            "closed_at_timestep": self.closed_at_timestep,
        }


@dataclass(frozen=True)
class EpisodeState:
    scenario_id: str
    current_timestep: int
    zones: tuple[ZoneState, ...]
    shelters: tuple[ShelterState, ...]
    routes: tuple[RouteState, ...]
    dispatch_events: tuple[DispatchEvent, ...]
    people_safely_arrived: int
    initial_evacuation_population: int
    dispatch_limit_per_timestep: int
    dispatches_used_this_timestep: int
    next_dispatch_sequence: int
    terminal: bool
    terminal_reason: TerminalReason | None
    audit_log: tuple[AuditRecord, ...]
    uncertainty_config_id: str | None = None
    forecast_for_timestep: int | None = None

    @property
    def pending_dispatches(self) -> tuple[DispatchEvent, ...]:
        return tuple(
            event
            for event in self.dispatch_events
            if event.status is DispatchStatus.IN_TRANSIT
        )

    @property
    def pending_arrivals(self) -> tuple[DispatchEvent, ...]:
        """Alias emphasizing that active dispatches form the arrival queue."""
        return self.pending_dispatches

    @property
    def people_in_transit(self) -> int:
        return sum(event.people for event in self.pending_dispatches)

    @property
    def population_remaining(self) -> int:
        return sum(zone.population_remaining for zone in self.zones)

    def zone(self, zone_id: str) -> ZoneState | None:
        return next((zone for zone in self.zones if zone.zone_id == zone_id), None)

    def shelter(self, shelter_id: str) -> ShelterState | None:
        return next(
            (shelter for shelter in self.shelters if shelter.shelter_id == shelter_id),
            None,
        )

    def route(self, route_id: str) -> RouteState | None:
        return next((route for route in self.routes if route.route_id == route_id), None)

    def to_policy_observation(self) -> dict[str, Any]:
        """Observable current/past state and forecasts, never future outcome draws."""
        return {
            "scenario_id": self.scenario_id,
            "current_timestep": self.current_timestep,
            "uncertainty_config_id": self.uncertainty_config_id,
            "forecast_for_timestep": self.forecast_for_timestep,
            "zones": [zone.to_dict() for zone in self.zones],
            "shelters": [shelter.to_dict() for shelter in self.shelters],
            "routes": [route.to_dict() for route in self.routes],
            "population_remaining": self.population_remaining,
            "people_in_transit": self.people_in_transit,
            "people_safely_arrived": self.people_safely_arrived,
            "dispatch_limit_per_timestep": self.dispatch_limit_per_timestep,
            "terminal": self.terminal,
            "terminal_reason": self.terminal_reason.value if self.terminal_reason else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "current_timestep": self.current_timestep,
            "uncertainty_config_id": self.uncertainty_config_id,
            "forecast_for_timestep": self.forecast_for_timestep,
            "zones": [zone.to_dict() for zone in self.zones],
            "shelters": [shelter.to_dict() for shelter in self.shelters],
            "routes": [route.to_dict() for route in self.routes],
            "dispatch_events": [event.to_dict() for event in self.dispatch_events],
            "pending_event_ids": [event.event_id for event in self.pending_dispatches],
            "population_remaining": self.population_remaining,
            "people_in_transit": self.people_in_transit,
            "people_safely_arrived": self.people_safely_arrived,
            "initial_evacuation_population": self.initial_evacuation_population,
            "dispatch_limit_per_timestep": self.dispatch_limit_per_timestep,
            "dispatches_used_this_timestep": self.dispatches_used_this_timestep,
            "next_dispatch_sequence": self.next_dispatch_sequence,
            "terminal": self.terminal,
            "terminal_reason": self.terminal_reason.value if self.terminal_reason else None,
            "audit_log": [record.to_dict() for record in self.audit_log],
        }
