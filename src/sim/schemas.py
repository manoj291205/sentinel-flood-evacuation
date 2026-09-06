"""Immutable, validated, JSON-serializable Sentinel-Agent V3 scenario schema.

This module defines configuration and *initial* values only. It intentionally does not
model current population, current severity, reservations, closures, pending arrivals, or
any transition behavior. Those values belong to mutable episode state in later phases.

The schema uses standard-library frozen dataclasses to keep the contract lightweight and
to avoid adding a validation dependency. Validation is explicit and error messages name
the failing field.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, TypeVar

SCHEMA_VERSION = "3.0"


class ScenarioValidationError(ValueError):
    """Raised when V3 scenario data violates the static contract."""


class ProvenanceClass(str, Enum):
    REAL = "REAL"
    SIMULATED = "SIMULATED"
    FICTIONAL = "FICTIONAL"
    MODEL_GENERATED = "MODEL_GENERATED"
    MEASURED = "MEASURED"


class LocationKind(str, Enum):
    ABSTRACT_NODE = "ABSTRACT_NODE"
    GRAPH_NODE = "GRAPH_NODE"
    COORDINATES = "COORDINATES"


class Trend(str, Enum):
    RISING = "RISING"
    STEADY = "STEADY"
    FALLING = "FALLING"
    UNKNOWN = "UNKNOWN"


class ShelterStatus(str, Enum):
    """Initial intake status; Phase 5 will define the hard-rule treatment."""

    OPEN = "OPEN"
    RESTRICTED = "RESTRICTED"
    CLOSED = "CLOSED"


class NetworkMode(str, Enum):
    ABSTRACT_ROUTES = "ABSTRACT_ROUTES"
    GRAPH = "GRAPH"


class StochasticParameterStatus(str, Enum):
    DEFERRED_TO_PHASE_4 = "DEFERRED_TO_PHASE_4"
    CONFIGURED = "CONFIGURED"


E = TypeVar("E", bound=Enum)


def _error(path: str, message: str) -> None:
    raise ScenarioValidationError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _error(path, f"must be an object, got {type(value).__name__}")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _error(path, f"must be an array, got {type(value).__name__}")
    return value


def _keys(
    value: Mapping[str, Any], required: set[str], optional: set[str], path: str
) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing:
        _error(path, f"missing required field(s): {', '.join(missing)}")
    if unknown:
        _error(path, f"unknown field(s): {', '.join(unknown)}")


def _text(value: Any, path: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        _error(path, "must be a non-empty string")
    return value.strip()


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _error(path, "must be an integer")
    if value < minimum:
        _error(path, f"must be >= {minimum}")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _error(path, "must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        _error(path, "must be a finite number")
    return result


def _range(value: Any, path: str, low: float, high: float) -> float:
    result = _number(value, path)
    if not low <= result <= high:
        _error(path, f"must be in [{low}, {high}]")
    return result


def _optional_number(value: Any, path: str, *, minimum: float | None = None) -> float | None:
    if value is None:
        return None
    result = _number(value, path)
    if minimum is not None and result < minimum:
        _error(path, f"must be >= {minimum}")
    return result


def _optional_probability(value: Any, path: str) -> float | None:
    if value is None:
        return None
    return _range(value, path, 0.0, 1.0)


def _enum(enum_type: type[E], value: Any, path: str) -> E:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        allowed = ", ".join(item.value for item in enum_type)
        _error(path, f"must be one of: {allowed}")


def _string_tuple(value: Any, path: str) -> tuple[str, ...]:
    result = []
    for index, item in enumerate(_list(value, path)):
        result.append(_text(item, f"{path}[{index}]") or "")
    return tuple(result)


@dataclass(frozen=True)
class ProvenanceComponent:
    classification: ProvenanceClass
    description: str
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.classification, ProvenanceClass):
            _error("provenance.classification", "must be a ProvenanceClass")
        _text(self.description, "provenance.description")
        for index, ref in enumerate(self.source_refs):
            _text(ref, f"provenance.source_refs[{index}]")

    @classmethod
    def from_dict(cls, raw: Any, path: str) -> "ProvenanceComponent":
        data = _mapping(raw, path)
        _keys(data, {"classification", "description"}, {"source_refs"}, path)
        return cls(
            classification=_enum(
                ProvenanceClass, data["classification"], f"{path}.classification"
            ),
            description=_text(data["description"], f"{path}.description") or "",
            source_refs=_string_tuple(data.get("source_refs", []), f"{path}.source_refs"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "description": self.description,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class Provenance:
    """Component-level origins so mixed real/simulated scenarios stay explicit."""

    scenario_origin: ProvenanceComponent
    geography_origin: ProvenanceComponent
    population_origin: ProvenanceComponent
    shelter_origin: ProvenanceComponent
    hazard_origin: ProvenanceComponent
    travel_origin: ProvenanceComponent
    network_origin: ProvenanceComponent
    notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: Any, path: str = "provenance") -> "Provenance":
        data = _mapping(raw, path)
        names = {
            "scenario_origin",
            "geography_origin",
            "population_origin",
            "shelter_origin",
            "hazard_origin",
            "travel_origin",
            "network_origin",
        }
        _keys(data, names, {"notes"}, path)
        values = {
            name: ProvenanceComponent.from_dict(data[name], f"{path}.{name}")
            for name in names
        }
        return cls(
            **values,
            notes=_string_tuple(data.get("notes", []), f"{path}.notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_origin": self.scenario_origin.to_dict(),
            "geography_origin": self.geography_origin.to_dict(),
            "population_origin": self.population_origin.to_dict(),
            "shelter_origin": self.shelter_origin.to_dict(),
            "hazard_origin": self.hazard_origin.to_dict(),
            "travel_origin": self.travel_origin.to_dict(),
            "network_origin": self.network_origin.to_dict(),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class LocationRef:
    """One location representation, usable before or after graph integration."""

    kind: LocationKind
    node_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LocationKind):
            _error("location.kind", "must be a LocationKind")
        if self.kind in {LocationKind.ABSTRACT_NODE, LocationKind.GRAPH_NODE}:
            _text(self.node_id, "location.node_id")
            if self.latitude is not None or self.longitude is not None:
                _error("location", "node locations may not also contain coordinates")
        else:
            if self.node_id is not None:
                _error("location.node_id", "must be null for coordinate locations")
            if self.latitude is None or self.longitude is None:
                _error("location", "coordinate locations require latitude and longitude")
            _range(self.latitude, "location.latitude", -90.0, 90.0)
            _range(self.longitude, "location.longitude", -180.0, 180.0)

    @classmethod
    def from_dict(cls, raw: Any, path: str) -> "LocationRef":
        data = _mapping(raw, path)
        _keys(data, {"kind"}, {"node_id", "latitude", "longitude"}, path)
        return cls(
            kind=_enum(LocationKind, data["kind"], f"{path}.kind"),
            node_id=_text(data.get("node_id"), f"{path}.node_id", optional=True),
            latitude=_optional_number(data.get("latitude"), f"{path}.latitude"),
            longitude=_optional_number(data.get("longitude"), f"{path}.longitude"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "node_id": self.node_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass(frozen=True)
class TimeConfig:
    """Configured timestep and horizon; defaults are modeling conveniences, not facts."""

    timestep_minutes: float = 10.0
    horizon_steps: int = 12

    def __post_init__(self) -> None:
        if _number(self.timestep_minutes, "time.timestep_minutes") <= 0:
            _error("time.timestep_minutes", "must be > 0")
        if _integer(self.horizon_steps, "time.horizon_steps") <= 1:
            _error("time.horizon_steps", "must be > 1")

    @property
    def total_horizon_minutes(self) -> float:
        return float(self.timestep_minutes) * self.horizon_steps

    @classmethod
    def from_dict(cls, raw: Any, path: str = "time") -> "TimeConfig":
        data = _mapping(raw, path)
        _keys(data, {"timestep_minutes", "horizon_steps"}, set(), path)
        return cls(
            timestep_minutes=_number(data["timestep_minutes"], f"{path}.timestep_minutes"),
            horizon_steps=_integer(data["horizon_steps"], f"{path}.horizon_steps"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestep_minutes": self.timestep_minutes,
            "horizon_steps": self.horizon_steps,
        }


@dataclass(frozen=True)
class OperationalPriorityFeature:
    name: str
    value: float
    description: str

    def __post_init__(self) -> None:
        _text(self.name, "priority_feature.name")
        _number(self.value, "priority_feature.value")
        _text(self.description, "priority_feature.description")

    @classmethod
    def from_dict(cls, raw: Any, path: str) -> "OperationalPriorityFeature":
        data = _mapping(raw, path)
        _keys(data, {"name", "value", "description"}, set(), path)
        return cls(
            name=_text(data["name"], f"{path}.name") or "",
            value=_number(data["value"], f"{path}.value"),
            description=_text(data["description"], f"{path}.description") or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "description": self.description}


@dataclass(frozen=True)
class ZoneDefinition:
    """Immutable initial zone inputs.

    Vulnerability and medical-priority counts are overlapping operational groups. Each
    is independently bounded by total population; their sum may exceed it.
    """

    zone_id: str
    location: LocationRef
    population_total: int
    population_initial_remaining: int
    vulnerable_population: int
    medical_priority_population: int
    initial_flood_severity: float
    initial_severity_trend: Trend
    priority_features: tuple[OperationalPriorityFeature, ...] = ()

    def __post_init__(self) -> None:
        _text(self.zone_id, "zone.zone_id")
        total = _integer(self.population_total, "zone.population_total")
        remaining = _integer(
            self.population_initial_remaining, "zone.population_initial_remaining"
        )
        if remaining > total:
            _error("zone.population_initial_remaining", "may not exceed population_total")
        for name, value in (
            ("vulnerable_population", self.vulnerable_population),
            ("medical_priority_population", self.medical_priority_population),
        ):
            if _integer(value, f"zone.{name}") > total:
                _error(f"zone.{name}", "may not exceed population_total")
        _range(self.initial_flood_severity, "zone.initial_flood_severity", 0.0, 1.0)
        if not isinstance(self.initial_severity_trend, Trend):
            _error("zone.initial_severity_trend", "must be a Trend")

    @classmethod
    def from_dict(cls, raw: Any, path: str) -> "ZoneDefinition":
        data = _mapping(raw, path)
        required = {
            "zone_id",
            "location",
            "population_total",
            "population_initial_remaining",
            "vulnerable_population",
            "medical_priority_population",
            "initial_flood_severity",
            "initial_severity_trend",
        }
        _keys(data, required, {"priority_features"}, path)
        features = tuple(
            OperationalPriorityFeature.from_dict(item, f"{path}.priority_features[{i}]")
            for i, item in enumerate(_list(data.get("priority_features", []), f"{path}.priority_features"))
        )
        return cls(
            zone_id=_text(data["zone_id"], f"{path}.zone_id") or "",
            location=LocationRef.from_dict(data["location"], f"{path}.location"),
            population_total=_integer(data["population_total"], f"{path}.population_total"),
            population_initial_remaining=_integer(
                data["population_initial_remaining"],
                f"{path}.population_initial_remaining",
            ),
            vulnerable_population=_integer(
                data["vulnerable_population"], f"{path}.vulnerable_population"
            ),
            medical_priority_population=_integer(
                data["medical_priority_population"],
                f"{path}.medical_priority_population",
            ),
            initial_flood_severity=_range(
                data["initial_flood_severity"],
                f"{path}.initial_flood_severity",
                0.0,
                1.0,
            ),
            initial_severity_trend=_enum(
                Trend, data["initial_severity_trend"], f"{path}.initial_severity_trend"
            ),
            priority_features=features,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "location": self.location.to_dict(),
            "population_total": self.population_total,
            "population_initial_remaining": self.population_initial_remaining,
            "vulnerable_population": self.vulnerable_population,
            "medical_priority_population": self.medical_priority_population,
            "initial_flood_severity": self.initial_flood_severity,
            "initial_severity_trend": self.initial_severity_trend.value,
            "priority_features": [feature.to_dict() for feature in self.priority_features],
        }


@dataclass(frozen=True)
class ShelterDefinition:
    """Immutable initial shelter inputs; available capacity is always derived."""

    shelter_id: str
    location: LocationRef
    capacity_total: int
    occupancy_initial: int
    status: ShelterStatus
    status_reason: str | None
    initial_flood_severity: float
    accessibility_score: float

    def __post_init__(self) -> None:
        _text(self.shelter_id, "shelter.shelter_id")
        capacity = _integer(self.capacity_total, "shelter.capacity_total")
        occupancy = _integer(self.occupancy_initial, "shelter.occupancy_initial")
        if occupancy > capacity:
            _error("shelter.occupancy_initial", "may not exceed capacity_total")
        if not isinstance(self.status, ShelterStatus):
            _error("shelter.status", "must be a ShelterStatus")
        if self.status_reason is not None:
            _text(self.status_reason, "shelter.status_reason")
        _range(self.initial_flood_severity, "shelter.initial_flood_severity", 0.0, 1.0)
        _range(self.accessibility_score, "shelter.accessibility_score", 0.0, 1.0)

    @property
    def capacity_initial_available(self) -> int:
        return self.capacity_total - self.occupancy_initial

    @classmethod
    def from_dict(cls, raw: Any, path: str) -> "ShelterDefinition":
        data = _mapping(raw, path)
        required = {
            "shelter_id",
            "location",
            "capacity_total",
            "occupancy_initial",
            "status",
            "initial_flood_severity",
            "accessibility_score",
        }
        _keys(data, required, {"status_reason"}, path)
        return cls(
            shelter_id=_text(data["shelter_id"], f"{path}.shelter_id") or "",
            location=LocationRef.from_dict(data["location"], f"{path}.location"),
            capacity_total=_integer(data["capacity_total"], f"{path}.capacity_total"),
            occupancy_initial=_integer(data["occupancy_initial"], f"{path}.occupancy_initial"),
            status=_enum(ShelterStatus, data["status"], f"{path}.status"),
            status_reason=_text(
                data.get("status_reason"), f"{path}.status_reason", optional=True
            ),
            initial_flood_severity=_range(
                data["initial_flood_severity"],
                f"{path}.initial_flood_severity",
                0.0,
                1.0,
            ),
            accessibility_score=_range(
                data["accessibility_score"], f"{path}.accessibility_score", 0.0, 1.0
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "shelter_id": self.shelter_id,
            "location": self.location.to_dict(),
            "capacity_total": self.capacity_total,
            "occupancy_initial": self.occupancy_initial,
            "status": self.status.value,
            "status_reason": self.status_reason,
            "initial_flood_severity": self.initial_flood_severity,
            "accessibility_score": self.accessibility_score,
        }


@dataclass(frozen=True)
class FleetConfig:
    """Aggregate fleet limits only; this contract does not model individual vehicles."""

    evacuation_enabled: bool
    vehicle_count: int
    vehicle_capacity: int
    dispatches_per_timestep: int

    def __post_init__(self) -> None:
        if not isinstance(self.evacuation_enabled, bool):
            _error("fleet.evacuation_enabled", "must be a boolean")
        count = _integer(self.vehicle_count, "fleet.vehicle_count")
        capacity = _integer(self.vehicle_capacity, "fleet.vehicle_capacity")
        dispatches = _integer(self.dispatches_per_timestep, "fleet.dispatches_per_timestep")
        if self.evacuation_enabled:
            if count == 0:
                _error("fleet.vehicle_count", "must be > 0 when evacuation is enabled")
            if capacity == 0:
                _error("fleet.vehicle_capacity", "must be > 0 when evacuation is enabled")
            if dispatches == 0:
                _error(
                    "fleet.dispatches_per_timestep",
                    "must be >= 1 when evacuation is enabled",
                )
        elif dispatches != 0:
            _error(
                "fleet.dispatches_per_timestep",
                "must be 0 when evacuation is disabled",
            )
        if count == 0 and capacity != 0:
            _error("fleet.vehicle_capacity", "must be 0 when vehicle_count is 0")

    @classmethod
    def from_dict(cls, raw: Any, path: str = "fleet") -> "FleetConfig":
        data = _mapping(raw, path)
        required = {
            "evacuation_enabled",
            "vehicle_count",
            "vehicle_capacity",
            "dispatches_per_timestep",
        }
        _keys(data, required, set(), path)
        return cls(
            evacuation_enabled=data["evacuation_enabled"],
            vehicle_count=_integer(data["vehicle_count"], f"{path}.vehicle_count"),
            vehicle_capacity=_integer(data["vehicle_capacity"], f"{path}.vehicle_capacity"),
            dispatches_per_timestep=_integer(
                data["dispatches_per_timestep"], f"{path}.dispatches_per_timestep"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evacuation_enabled": self.evacuation_enabled,
            "vehicle_count": self.vehicle_count,
            "vehicle_capacity": self.vehicle_capacity,
            "dispatches_per_timestep": self.dispatches_per_timestep,
        }


@dataclass(frozen=True)
class RouteDefinition:
    """Static zone-to-shelter relation.

    Travel mean and standard deviation are minutes. Unreachable routes carry null
    travel/closure metrics rather than numeric sentinels.
    """

    route_id: str
    source_zone_id: str
    destination_shelter_id: str
    reachable: bool
    travel_time_mean: float | None
    travel_time_std: float | None
    base_closure_probability: float | None

    def __post_init__(self) -> None:
        _text(self.route_id, "route.route_id")
        _text(self.source_zone_id, "route.source_zone_id")
        _text(self.destination_shelter_id, "route.destination_shelter_id")
        if not isinstance(self.reachable, bool):
            _error("route.reachable", "must be a boolean")
        if self.reachable:
            if self.travel_time_mean is None or _number(
                self.travel_time_mean, "route.travel_time_mean"
            ) <= 0:
                _error("route.travel_time_mean", "must be > 0 for a reachable route")
            if self.travel_time_std is None or _number(
                self.travel_time_std, "route.travel_time_std"
            ) < 0:
                _error("route.travel_time_std", "must be >= 0 for a reachable route")
            if self.base_closure_probability is None:
                _error(
                    "route.base_closure_probability",
                    "is required for a reachable route",
                )
            _range(
                self.base_closure_probability,
                "route.base_closure_probability",
                0.0,
                1.0,
            )
        elif any(
            value is not None
            for value in (
                self.travel_time_mean,
                self.travel_time_std,
                self.base_closure_probability,
            )
        ):
            _error(
                "route",
                "unreachable routes must use null travel and closure metrics",
            )

    @classmethod
    def from_dict(cls, raw: Any, path: str) -> "RouteDefinition":
        data = _mapping(raw, path)
        required = {
            "route_id",
            "source_zone_id",
            "destination_shelter_id",
            "reachable",
            "travel_time_mean",
            "travel_time_std",
            "base_closure_probability",
        }
        _keys(data, required, set(), path)
        reachable = data["reachable"]
        if not isinstance(reachable, bool):
            _error(f"{path}.reachable", "must be a boolean")
        return cls(
            route_id=_text(data["route_id"], f"{path}.route_id") or "",
            source_zone_id=_text(data["source_zone_id"], f"{path}.source_zone_id") or "",
            destination_shelter_id=_text(
                data["destination_shelter_id"], f"{path}.destination_shelter_id"
            ) or "",
            reachable=reachable,
            travel_time_mean=_optional_number(
                data["travel_time_mean"], f"{path}.travel_time_mean"
            ),
            travel_time_std=_optional_number(
                data["travel_time_std"], f"{path}.travel_time_std"
            ),
            base_closure_probability=_optional_probability(
                data["base_closure_probability"], f"{path}.base_closure_probability"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "source_zone_id": self.source_zone_id,
            "destination_shelter_id": self.destination_shelter_id,
            "reachable": self.reachable,
            "travel_time_mean": self.travel_time_mean,
            "travel_time_std": self.travel_time_std,
            "base_closure_probability": self.base_closure_probability,
        }


@dataclass(frozen=True)
class NetworkConfig:
    network_id: str
    mode: NetworkMode
    routes: tuple[RouteDefinition, ...]

    def __post_init__(self) -> None:
        _text(self.network_id, "network.network_id")
        if not isinstance(self.mode, NetworkMode):
            _error("network.mode", "must be a NetworkMode")

    @classmethod
    def from_dict(cls, raw: Any, path: str = "network") -> "NetworkConfig":
        data = _mapping(raw, path)
        _keys(data, {"network_id", "mode", "routes"}, set(), path)
        routes = tuple(
            RouteDefinition.from_dict(item, f"{path}.routes[{index}]")
            for index, item in enumerate(_list(data["routes"], f"{path}.routes"))
        )
        return cls(
            network_id=_text(data["network_id"], f"{path}.network_id") or "",
            mode=_enum(NetworkMode, data["mode"], f"{path}.mode"),
            routes=routes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "network_id": self.network_id,
            "mode": self.mode.value,
            "routes": [route.to_dict() for route in self.routes],
        }


@dataclass(frozen=True)
class HazardConfig:
    """Normalized severity-scale metadata, separate from dynamic hazard state."""

    severity_min: float
    severity_max: float
    scale_description: str
    thresholds_are_modeling_assumptions: bool

    def __post_init__(self) -> None:
        low = _range(self.severity_min, "hazard.severity_min", 0.0, 1.0)
        high = _range(self.severity_max, "hazard.severity_max", 0.0, 1.0)
        if low != 0.0 or high != 1.0:
            _error("hazard", "V3 severity must use the normalized [0, 1] bounds")
        _text(self.scale_description, "hazard.scale_description")
        if not isinstance(self.thresholds_are_modeling_assumptions, bool):
            _error("hazard.thresholds_are_modeling_assumptions", "must be a boolean")

    @classmethod
    def from_dict(cls, raw: Any, path: str = "hazard") -> "HazardConfig":
        data = _mapping(raw, path)
        required = {
            "severity_min",
            "severity_max",
            "scale_description",
            "thresholds_are_modeling_assumptions",
        }
        _keys(data, required, set(), path)
        return cls(
            severity_min=_range(data["severity_min"], f"{path}.severity_min", 0.0, 1.0),
            severity_max=_range(data["severity_max"], f"{path}.severity_max", 0.0, 1.0),
            scale_description=_text(data["scale_description"], f"{path}.scale_description") or "",
            thresholds_are_modeling_assumptions=data["thresholds_are_modeling_assumptions"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity_min": self.severity_min,
            "severity_max": self.severity_max,
            "scale_description": self.scale_description,
            "thresholds_are_modeling_assumptions": self.thresholds_are_modeling_assumptions,
        }


@dataclass(frozen=True)
class StochasticModelConfig:
    """Future Phase 4 parameter interface; loading performs no random draw."""

    parameter_status: StochasticParameterStatus = StochasticParameterStatus.DEFERRED_TO_PHASE_4
    regional_shock_std: float | None = None
    local_noise_std: float | None = None
    shock_persistence: float | None = None
    travel_noise_std: float | None = None
    closure_hazard_coefficient: float | None = None
    shelter_degradation_probability: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.parameter_status, StochasticParameterStatus):
            _error("stochastic_model.parameter_status", "must be a StochasticParameterStatus")
        for name in (
            "regional_shock_std",
            "local_noise_std",
            "travel_noise_std",
            "closure_hazard_coefficient",
        ):
            value = getattr(self, name)
            if value is not None and (_number(value, f"stochastic_model.{name}") < 0):
                _error(f"stochastic_model.{name}", "must be >= 0")
        if self.shock_persistence is not None:
            _range(self.shock_persistence, "stochastic_model.shock_persistence", -1.0, 1.0)
        if self.shelter_degradation_probability is not None:
            _range(
                self.shelter_degradation_probability,
                "stochastic_model.shelter_degradation_probability",
                0.0,
                1.0,
            )
        if self.parameter_status is StochasticParameterStatus.DEFERRED_TO_PHASE_4 and any(
            getattr(self, name) is not None
            for name in (
                "regional_shock_std",
                "local_noise_std",
                "shock_persistence",
                "travel_noise_std",
                "closure_hazard_coefficient",
                "shelter_degradation_probability",
            )
        ):
            _error(
                "stochastic_model",
                "deferred Phase 4 parameters must remain null",
            )

    @classmethod
    def from_dict(cls, raw: Any, path: str = "stochastic_model") -> "StochasticModelConfig":
        data = _mapping(raw, path)
        fields = {
            "parameter_status",
            "regional_shock_std",
            "local_noise_std",
            "shock_persistence",
            "travel_noise_std",
            "closure_hazard_coefficient",
            "shelter_degradation_probability",
        }
        _keys(data, {"parameter_status"}, fields - {"parameter_status"}, path)
        return cls(
            parameter_status=_enum(
                StochasticParameterStatus,
                data["parameter_status"],
                f"{path}.parameter_status",
            ),
            regional_shock_std=_optional_number(
                data.get("regional_shock_std"), f"{path}.regional_shock_std", minimum=0.0
            ),
            local_noise_std=_optional_number(
                data.get("local_noise_std"), f"{path}.local_noise_std", minimum=0.0
            ),
            shock_persistence=_optional_number(
                data.get("shock_persistence"), f"{path}.shock_persistence"
            ),
            travel_noise_std=_optional_number(
                data.get("travel_noise_std"), f"{path}.travel_noise_std", minimum=0.0
            ),
            closure_hazard_coefficient=_optional_number(
                data.get("closure_hazard_coefficient"),
                f"{path}.closure_hazard_coefficient",
                minimum=0.0,
            ),
            shelter_degradation_probability=_optional_probability(
                data.get("shelter_degradation_probability"),
                f"{path}.shelter_degradation_probability",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter_status": self.parameter_status.value,
            "regional_shock_std": self.regional_shock_std,
            "local_noise_std": self.local_noise_std,
            "shock_persistence": self.shock_persistence,
            "travel_noise_std": self.travel_noise_std,
            "closure_hazard_coefficient": self.closure_hazard_coefficient,
            "shelter_degradation_probability": self.shelter_degradation_probability,
        }


@dataclass(frozen=True)
class PolicyContext:
    """Optional evidence/cache version references; contains no policy judgment."""

    constraint_cache_version: str | None = None
    policy_schema_version: str | None = None
    document_corpus_fingerprint: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "constraint_cache_version",
            "policy_schema_version",
            "document_corpus_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                _text(value, f"policy_context.{name}")

    @classmethod
    def from_dict(cls, raw: Any, path: str = "policy_context") -> "PolicyContext":
        data = _mapping(raw, path)
        fields = {
            "constraint_cache_version",
            "policy_schema_version",
            "document_corpus_fingerprint",
        }
        _keys(data, set(), fields, path)
        return cls(
            constraint_cache_version=_text(
                data.get("constraint_cache_version"),
                f"{path}.constraint_cache_version",
                optional=True,
            ),
            policy_schema_version=_text(
                data.get("policy_schema_version"),
                f"{path}.policy_schema_version",
                optional=True,
            ),
            document_corpus_fingerprint=_text(
                data.get("document_corpus_fingerprint"),
                f"{path}.document_corpus_fingerprint",
                optional=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_cache_version": self.constraint_cache_version,
            "policy_schema_version": self.policy_schema_version,
            "document_corpus_fingerprint": self.document_corpus_fingerprint,
        }


@dataclass(frozen=True)
class ScenarioV3:
    """Immutable V3 scenario definition.

    ``seed`` is the non-negative root from which Phase 4 may derive independent streams;
    schema loading itself never consumes it or generates hidden values.
    """

    schema_version: str
    scenario_id: str
    seed: int
    provenance: Provenance
    time: TimeConfig
    zones: tuple[ZoneDefinition, ...]
    shelters: tuple[ShelterDefinition, ...]
    fleet: FleetConfig
    network: NetworkConfig
    hazard: HazardConfig
    stochastic_model: StochasticModelConfig
    policy_context: PolicyContext

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            _error(
                "schema_version",
                f"unsupported version {self.schema_version!r}; expected {SCHEMA_VERSION!r}",
            )
        _text(self.scenario_id, "scenario_id")
        _integer(self.seed, "seed")
        if not self.zones:
            _error("zones", "must contain at least one zone")
        if not self.shelters:
            _error("shelters", "must contain at least one shelter")

        zone_ids = [zone.zone_id for zone in self.zones]
        shelter_ids = [shelter.shelter_id for shelter in self.shelters]
        route_ids = [route.route_id for route in self.network.routes]
        self._require_unique(zone_ids, "zones.zone_id")
        self._require_unique(shelter_ids, "shelters.shelter_id")
        self._require_unique(route_ids, "network.routes.route_id")

        known_zones = set(zone_ids)
        known_shelters = set(shelter_ids)
        for index, route in enumerate(self.network.routes):
            if route.source_zone_id not in known_zones:
                _error(
                    f"network.routes[{index}].source_zone_id",
                    f"unknown zone {route.source_zone_id!r}",
                )
            if route.destination_shelter_id not in known_shelters:
                _error(
                    f"network.routes[{index}].destination_shelter_id",
                    f"unknown shelter {route.destination_shelter_id!r}",
                )

    @staticmethod
    def _require_unique(values: list[str], path: str) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            _error(path, f"must be unique; duplicate(s): {', '.join(sorted(duplicates))}")

    @property
    def canonical_zones(self) -> tuple[ZoneDefinition, ...]:
        return tuple(sorted(self.zones, key=lambda zone: zone.zone_id))

    @property
    def canonical_shelters(self) -> tuple[ShelterDefinition, ...]:
        return tuple(sorted(self.shelters, key=lambda shelter: shelter.shelter_id))

    @property
    def canonical_routes(self) -> tuple[RouteDefinition, ...]:
        return tuple(
            sorted(
                self.network.routes,
                key=lambda route: (
                    route.source_zone_id,
                    route.destination_shelter_id,
                    route.route_id,
                ),
            )
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "ScenarioV3":
        data = _mapping(raw, "scenario")
        if "schema_version" in data and data["schema_version"] != SCHEMA_VERSION:
            _error(
                "schema_version",
                f"unsupported version {data['schema_version']!r}; expected {SCHEMA_VERSION!r}",
            )
        required = {
            "schema_version",
            "scenario_id",
            "seed",
            "provenance",
            "time",
            "zones",
            "shelters",
            "fleet",
            "network",
            "hazard",
            "stochastic_model",
            "policy_context",
        }
        _keys(data, required, set(), "scenario")

        version = data["schema_version"]
        zones = tuple(
            ZoneDefinition.from_dict(item, f"zones[{index}]")
            for index, item in enumerate(_list(data["zones"], "zones"))
        )
        shelters = tuple(
            ShelterDefinition.from_dict(item, f"shelters[{index}]")
            for index, item in enumerate(_list(data["shelters"], "shelters"))
        )
        return cls(
            schema_version=version,
            scenario_id=_text(data["scenario_id"], "scenario_id") or "",
            seed=_integer(data["seed"], "seed"),
            provenance=Provenance.from_dict(data["provenance"]),
            time=TimeConfig.from_dict(data["time"]),
            zones=zones,
            shelters=shelters,
            fleet=FleetConfig.from_dict(data["fleet"]),
            network=NetworkConfig.from_dict(data["network"]),
            hazard=HazardConfig.from_dict(data["hazard"]),
            stochastic_model=StochasticModelConfig.from_dict(data["stochastic_model"]),
            policy_context=PolicyContext.from_dict(data["policy_context"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a new JSON-compatible object without mutating source ordering."""
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "provenance": self.provenance.to_dict(),
            "time": self.time.to_dict(),
            "zones": [zone.to_dict() for zone in self.zones],
            "shelters": [shelter.to_dict() for shelter in self.shelters],
            "fleet": self.fleet.to_dict(),
            "network": self.network.to_dict(),
            "hazard": self.hazard.to_dict(),
            "stochastic_model": self.stochastic_model.to_dict(),
            "policy_context": self.policy_context.to_dict(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"


def load_v3_scenario(path: str | Path) -> ScenarioV3:
    """Load and validate V3 JSON. V1 JSON fails explicitly on schema version."""
    source = Path(path)
    try:
        raw = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioValidationError(f"{source}: could not load scenario: {exc}") from exc
    return ScenarioV3.from_dict(raw)


def dump_v3_scenario(scenario: ScenarioV3, path: str | Path) -> None:
    """Serialize an already validated immutable definition to JSON."""
    if not isinstance(scenario, ScenarioV3):
        _error("scenario", "must be a ScenarioV3 instance")
    Path(path).write_text(scenario.to_json())
