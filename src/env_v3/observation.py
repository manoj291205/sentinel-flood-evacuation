"""Policy-safe fixed flat observations for the Phase 7 V3 environment."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from src.sim import ScenarioV3

from .action_space import FixedActionMap
from .config import DEFAULT_ENV_CONFIG, EnvV3Config

ZONE_FEATURES = (
    "present",
    "population_remaining_fraction",
    "current_flood_severity",
    "recent_severity_trend_normalized",
    "forecast_mean_next",
    "forecast_uncertainty_normalized",
)
SHELTER_FEATURES = (
    "present",
    "available_capacity_fraction",
    "occupied_capacity_fraction",
    "reserved_capacity_fraction",
    "current_flood_severity",
    "status_open",
    "status_restricted",
    "status_closed",
)
ROUTE_FEATURES = (
    "present",
    "currently_reachable",
    "expected_travel_time_normalized",
    "travel_uncertainty_normalized",
    "estimated_closure_probability",
)
GLOBAL_FEATURES = (
    "timestep_fraction",
    "remaining_population_fraction",
    "in_transit_population_fraction",
    "safely_arrived_population_fraction",
    "vehicle_capacity_fraction",
    "any_dispatch_available",
)


class ObservationValueError(ValueError):
    pass


def observation_dimension(config: EnvV3Config = DEFAULT_ENV_CONFIG) -> int:
    return (
        config.max_zones * len(ZONE_FEATURES)
        + config.max_shelters * len(SHELTER_FEATURES)
        + config.dispatch_slots * len(ROUTE_FEATURES)
        + len(GLOBAL_FEATURES)
    )


OBSERVATION_DIM = observation_dimension()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ObservationValueError(f"{name} must be finite")
    return result


def _unit(value: Any, name: str, *, tolerance: float = 1e-7) -> float:
    result = _finite(value, name)
    if result < -tolerance or result > 1.0 + tolerance:
        raise ObservationValueError(f"{name} must lie in [0, 1], got {result}")
    return min(1.0, max(0.0, result))


def _nonnegative(value: Any, name: str) -> float:
    result = _finite(value, name)
    if result < 0:
        raise ObservationValueError(f"{name} must be nonnegative")
    return result


def _monotonic(value: Any, denominator: float, name: str) -> float:
    number = _nonnegative(value, name)
    if denominator <= 0 or not math.isfinite(denominator):
        raise ObservationValueError(f"{name} normalization denominator must be positive")
    return number / (number + denominator)


def build_observation(
    scenario: ScenarioV3,
    public_observation: dict[str, Any],
    action_mapping: FixedActionMap,
    *,
    any_dispatch_available: bool,
    config: EnvV3Config = DEFAULT_ENV_CONFIG,
) -> np.ndarray:
    """Build from the detached public view; no simulator context is accepted."""
    zone_values = {item["zone_id"]: item for item in public_observation["zones"]}
    shelter_values = {
        item["shelter_id"]: item for item in public_observation["shelters"]
    }
    route_values: dict[tuple[str, str], dict[str, Any]] = {}
    for route in public_observation["routes"]:
        pair = (route["source_zone_id"], route["destination_shelter_id"])
        if pair in route_values:
            raise ObservationValueError(f"multiple public routes for pair {pair}")
        route_values[pair] = route

    initial_by_zone = {
        zone.zone_id: zone.population_total for zone in scenario.canonical_zones
    }
    values: list[float] = []
    for zone_id in action_mapping.zone_slot_to_id:
        if zone_id is None:
            values.extend([0.0] * len(ZONE_FEATURES))
            continue
        zone = zone_values[zone_id]
        initial = initial_by_zone[zone_id]
        remaining = _nonnegative(
            zone["population_remaining"], f"zone {zone_id} population_remaining"
        )
        population_fraction = remaining / initial if initial > 0 else 0.0
        change = _finite(
            zone["observed_severity_change"], f"zone {zone_id} observed change"
        )
        if not -1.0 - 1e-7 <= change <= 1.0 + 1e-7:
            raise ObservationValueError(f"zone {zone_id} observed change outside [-1,1]")
        forecast_mean = zone["forecast_mean_next"]
        forecast_std = zone["forecast_std_next"]
        values.extend(
            (
                1.0,
                _unit(population_fraction, f"zone {zone_id} remaining fraction"),
                _unit(zone["flood_severity_current"], f"zone {zone_id} severity"),
                min(1.0, max(0.0, (change + 1.0) / 2.0)),
                0.0
                if forecast_mean is None
                else _unit(forecast_mean, f"zone {zone_id} forecast mean"),
                0.0
                if forecast_std is None
                else _monotonic(forecast_std, 1.0, f"zone {zone_id} forecast std"),
            )
        )

    for shelter_id in action_mapping.shelter_slot_to_id:
        if shelter_id is None:
            values.extend([0.0] * len(SHELTER_FEATURES))
            continue
        shelter = shelter_values[shelter_id]
        capacity = _nonnegative(
            shelter["capacity_total"], f"shelter {shelter_id} capacity"
        )
        if capacity > 0:
            available = _nonnegative(
                shelter["capacity_available"], f"shelter {shelter_id} available"
            ) / capacity
            occupied = _nonnegative(
                shelter["occupancy_current"], f"shelter {shelter_id} occupancy"
            ) / capacity
            reserved = _nonnegative(
                shelter["capacity_reserved"], f"shelter {shelter_id} reserved"
            ) / capacity
        else:
            available = occupied = reserved = 0.0
        status = shelter["status_current"]
        if status not in {"OPEN", "RESTRICTED", "CLOSED"}:
            raise ObservationValueError(f"unknown shelter status {status!r}")
        values.extend(
            (
                1.0,
                _unit(available, f"shelter {shelter_id} available fraction"),
                _unit(occupied, f"shelter {shelter_id} occupied fraction"),
                _unit(reserved, f"shelter {shelter_id} reserved fraction"),
                _unit(
                    shelter["flood_severity_current"],
                    f"shelter {shelter_id} severity",
                ),
                float(status == "OPEN"),
                float(status == "RESTRICTED"),
                float(status == "CLOSED"),
            )
        )

    horizon_minutes = scenario.time.timestep_minutes * scenario.time.horizon_steps
    for index in range(config.dispatch_slots):
        decoded = action_mapping.decode_action(index)
        if not decoded.present:
            values.extend([0.0] * len(ROUTE_FEATURES))
            continue
        route = route_values.get((decoded.zone_id or "", decoded.shelter_id or ""))
        if route is None:
            values.extend([0.0] * len(ROUTE_FEATURES))
            continue
        reachable = bool(route["reachable_current"])
        if not reachable:
            values.extend((1.0, 0.0, 0.0, 0.0, 0.0))
            continue
        expected = route["expected_travel_time_minutes"]
        uncertainty = route["travel_time_uncertainty_minutes"]
        if expected is None or uncertainty is None:
            raise ObservationValueError("reachable route lacks public travel estimates")
        values.extend(
            (
                1.0,
                1.0,
                _monotonic(expected, horizon_minutes, "expected travel"),
                _monotonic(uncertainty, horizon_minutes, "travel uncertainty"),
                _unit(route["estimated_closure_probability"], "closure probability"),
            )
        )

    initial_population = sum(
        zone.population_initial_remaining for zone in scenario.zones
    )
    if initial_population < 0:
        raise ObservationValueError("initial evacuation population must be nonnegative")
    remaining = _nonnegative(public_observation["population_remaining"], "remaining")
    transit = _nonnegative(public_observation["people_in_transit"], "in transit")
    safe = _nonnegative(public_observation["people_safely_arrived"], "safely arrived")
    timestep = _nonnegative(public_observation["current_timestep"], "timestep")
    vehicle_capacity = _nonnegative(scenario.fleet.vehicle_capacity, "vehicle capacity")
    if initial_population > 0:
        remaining_fraction = remaining / initial_population
        transit_fraction = transit / initial_population
        safe_fraction = safe / initial_population
    else:
        remaining_fraction = transit_fraction = safe_fraction = 0.0
    vehicle_denominator = vehicle_capacity + initial_population
    values.extend(
        (
            _unit(timestep / scenario.time.horizon_steps, "timestep fraction"),
            _unit(remaining_fraction, "remaining fraction"),
            _unit(transit_fraction, "transit fraction"),
            _unit(safe_fraction, "safe fraction"),
            vehicle_capacity / vehicle_denominator if vehicle_denominator > 0 else 0.0,
            float(any_dispatch_available),
        )
    )

    observation = np.asarray(values, dtype=np.float32)
    expected_shape = (observation_dimension(config),)
    if observation.shape != expected_shape:
        raise ObservationValueError(
            f"observation shape {observation.shape} does not match {expected_shape}"
        )
    if not np.all(np.isfinite(observation)):
        raise ObservationValueError("observation contains NaN or infinity")
    if np.any(observation < 0.0) or np.any(observation > 1.0):
        raise ObservationValueError("observation violates frozen [0,1] bounds")
    return observation
