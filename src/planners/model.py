"""Observable expected transition model used only by practical planners."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from src.sim.events import WAIT, DispatchAction, SimulationAction

from .base import PlannerInput
from .objective import EXPOSURE_WEIGHT, SAFE_WEIGHT, TRAVEL_WEIGHT


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


@dataclass(frozen=True)
class ModelZone:
    zone_id: str
    population: int
    severity: float
    change: float
    forecast: float | None


@dataclass(frozen=True)
class ModelShelter:
    shelter_id: str
    capacity_total: int
    occupancy: int
    reserved: int
    status: str
    severity: float
    change: float
    forecast: float | None

    @property
    def available(self) -> int:
        return self.capacity_total - self.occupancy - self.reserved


@dataclass(frozen=True)
class ModelRoute:
    route_id: str
    zone_id: str
    shelter_id: str
    reachable: bool
    base_travel: float | None
    expected_travel: float | None
    uncertainty: float | None
    closure_probability: float
    hazard_proxy: float | None


@dataclass(frozen=True)
class ModelPending:
    event_id: str
    zone_id: str
    shelter_id: str
    route_id: str
    people: int
    arrival_timestep: int


@dataclass(frozen=True)
class ModelState:
    scenario_id: str
    timestep: int
    horizon: int
    timestep_minutes: float
    vehicle_capacity: int
    initial_population: int
    safe: int
    zones: tuple[ModelZone, ...]
    shelters: tuple[ModelShelter, ...]
    routes: tuple[ModelRoute, ...]
    pending: tuple[ModelPending, ...]
    actions: tuple[SimulationAction, ...]
    route_hazard_factor: float
    base_closure_multiplier: float
    hazard_to_closure_strength: float
    maximum_closure_probability: float
    travel_noise_fraction: float
    next_event: int

    @classmethod
    def from_input(cls, value: PlannerInput) -> "ModelState":
        observation = value.observation
        zones = tuple(
            ModelZone(
                item["zone_id"],
                item["population_remaining"],
                item["flood_severity_current"],
                item["observed_severity_change"],
                item["forecast_mean_next"],
            )
            for item in observation["zones"]
        )
        shelters = tuple(
            ModelShelter(
                item["shelter_id"],
                item["capacity_total"],
                item["occupancy_current"],
                item["capacity_reserved"],
                item["status_current"],
                item["flood_severity_current"],
                item["observed_severity_change"],
                item["forecast_mean_next"],
            )
            for item in observation["shelters"]
        )
        routes = tuple(
            ModelRoute(
                item["route_id"],
                item["source_zone_id"],
                item["destination_shelter_id"],
                item["reachable_current"],
                item["base_travel_time_minutes"],
                item["expected_travel_time_minutes"],
                item["travel_time_uncertainty_minutes"],
                item["estimated_closure_probability"],
                item["route_hazard_proxy"],
            )
            for item in observation["routes"]
        )
        pending = tuple(
            ModelPending(
                item["event_id"],
                item["source_zone_id"],
                item["destination_shelter_id"],
                item["route_id"],
                item["people"],
                item["arrival_timestep"],
            )
            for item in observation.get("pending_dispatches", [])
        )
        initial = (
            sum(item.population for item in zones)
            + sum(item.people for item in pending)
            + observation["people_safely_arrived"]
        )
        config = value.uncertainty_config
        return cls(
            scenario_id=value.scenario_id,
            timestep=value.current_timestep,
            horizon=value.horizon_steps,
            timestep_minutes=value.timestep_minutes,
            vehicle_capacity=value.vehicle_capacity,
            initial_population=initial,
            safe=observation["people_safely_arrived"],
            zones=zones,
            shelters=shelters,
            routes=routes,
            pending=pending,
            actions=value.safety_snapshot.canonical_actions,
            route_hazard_factor=config.route_hazard_travel_factor,
            base_closure_multiplier=config.base_closure_multiplier,
            hazard_to_closure_strength=config.hazard_to_closure_strength,
            maximum_closure_probability=config.maximum_closure_probability,
            travel_noise_fraction=config.travel_noise_fraction,
            next_event=len(pending) + observation["people_safely_arrived"] + 1,
        )

    def zone(self, zone_id: str) -> ModelZone | None:
        return next((item for item in self.zones if item.zone_id == zone_id), None)

    def shelter(self, shelter_id: str) -> ModelShelter | None:
        return next((item for item in self.shelters if item.shelter_id == shelter_id), None)

    def route(self, action: DispatchAction) -> ModelRoute | None:
        return next(
            (
                item
                for item in self.routes
                if item.zone_id == action.zone_id and item.shelter_id == action.shelter_id
            ),
            None,
        )

    def allowed_actions(self) -> tuple[SimulationAction, ...]:
        if self.timestep >= self.horizon:
            return ()
        allowed: list[SimulationAction] = []
        for action in self.actions:
            if action == WAIT:
                allowed.append(action)
                continue
            assert isinstance(action, DispatchAction)
            zone = self.zone(action.zone_id)
            shelter = self.shelter(action.shelter_id)
            route = self.route(action)
            if (
                zone is not None
                and zone.population > 0
                and shelter is not None
                and shelter.status != "CLOSED"
                and shelter.available > 0
                and shelter.severity < 0.70
                and route is not None
                and route.reachable
                and route.expected_travel is not None
                and route.expected_travel > 0
            ):
                allowed.append(action)
        return tuple(allowed)

    def exposure(self) -> float:
        result = sum(item.population * item.severity for item in self.zones)
        for pending in self.pending:
            route = next(item for item in self.routes if item.route_id == pending.route_id)
            result += pending.people * float(route.hazard_proxy or 0.0)
        return result

    @property
    def transit(self) -> int:
        return sum(item.people for item in self.pending)

    def advance(
        self,
        action: SimulationAction,
        *,
        travel_multiplier: float = 1.0,
        closed_route_ids: frozenset[str] = frozenset(),
        zone_shocks: dict[str, float] | None = None,
        shelter_shocks: dict[str, float] | None = None,
        shelter_status_updates: dict[str, str] | None = None,
    ) -> "ModelState":
        zones = self.zones
        shelters = self.shelters
        pending = self.pending
        next_event = self.next_event
        if isinstance(action, DispatchAction):
            zone = self.zone(action.zone_id)
            shelter = self.shelter(action.shelter_id)
            route = self.route(action)
            if zone is None or shelter is None or route is None or route.expected_travel is None:
                raise ValueError("modeled dispatch is invalid")
            people = min(self.vehicle_capacity, zone.population, shelter.available)
            realized = max(0.01, route.expected_travel * travel_multiplier)
            lag = max(1, math.ceil(realized / self.timestep_minutes))
            zones = tuple(
                replace(item, population=item.population - people)
                if item.zone_id == action.zone_id
                else item
                for item in zones
            )
            shelters = tuple(
                replace(item, reserved=item.reserved + people)
                if item.shelter_id == action.shelter_id
                else item
                for item in shelters
            )
            pending += (
                ModelPending(
                    f"model-{next_event:06d}",
                    action.zone_id,
                    action.shelter_id,
                    route.route_id,
                    people,
                    self.timestep + lag,
                ),
            )
            next_event += 1

        new_timestep = self.timestep + 1
        if new_timestep >= self.horizon:
            return replace(
                self,
                timestep=new_timestep,
                zones=zones,
                shelters=shelters,
                pending=pending,
                next_event=next_event,
            )

        due = tuple(item for item in pending if item.arrival_timestep == new_timestep)
        pending = tuple(item for item in pending if item.arrival_timestep != new_timestep)
        safe = self.safe + sum(item.people for item in due)
        shelters = tuple(
            replace(
                item,
                occupancy=item.occupancy
                + sum(d.people for d in due if d.shelter_id == item.shelter_id),
                reserved=item.reserved
                - sum(d.people for d in due if d.shelter_id == item.shelter_id),
            )
            for item in shelters
        )

        zone_shocks = zone_shocks or {}
        shelter_shocks = shelter_shocks or {}
        shelter_status_updates = shelter_status_updates or {}
        zones = tuple(
            replace(
                item,
                severity=_clip(
                    (item.forecast if item.forecast is not None else item.severity)
                    + zone_shocks.get(item.zone_id, 0.0)
                ),
                change=(item.forecast if item.forecast is not None else item.severity)
                - item.severity,
                forecast=_clip(
                    (item.forecast if item.forecast is not None else item.severity)
                    + ((item.forecast if item.forecast is not None else item.severity) - item.severity)
                ),
            )
            for item in zones
        )
        shelters = tuple(
            replace(
                item,
                severity=_clip(
                    (item.forecast if item.forecast is not None else item.severity)
                    + shelter_shocks.get(item.shelter_id, 0.0)
                ),
                change=(item.forecast if item.forecast is not None else item.severity)
                - item.severity,
                forecast=_clip(
                    (item.forecast if item.forecast is not None else item.severity)
                    + ((item.forecast if item.forecast is not None else item.severity) - item.severity)
                ),
                status=shelter_status_updates.get(item.shelter_id, item.status),
            )
            for item in shelters
        )
        zone_map = {item.zone_id: item for item in zones}
        shelter_map = {item.shelter_id: item for item in shelters}
        routes = []
        for route in self.routes:
            reachable = route.reachable and route.route_id not in closed_route_ids
            if route.base_travel is None:
                routes.append(replace(route, reachable=False))
                continue
            hazard = max(
                zone_map[route.zone_id].severity,
                shelter_map[route.shelter_id].severity,
            )
            expected = route.base_travel * (1 + self.route_hazard_factor * hazard)
            probability = min(
                self.maximum_closure_probability,
                max(
                    0.0,
                    route.closure_probability
                    + self.hazard_to_closure_strength * (hazard - float(route.hazard_proxy or 0.0)),
                ),
            )
            routes.append(
                replace(
                    route,
                    reachable=reachable,
                    expected_travel=expected,
                    closure_probability=probability,
                    hazard_proxy=hazard,
                )
            )
        return replace(
            self,
            timestep=new_timestep,
            safe=safe,
            zones=zones,
            shelters=shelters,
            routes=tuple(routes),
            pending=pending,
            next_event=next_event,
        )


def terminal_estimate(
    state: ModelState,
    exposure_sum: float,
    transit_sum: float,
) -> float:
    """Propagate WAIT to the horizon and score the frozen Gate-6 utility."""
    current = state
    exposure = exposure_sum
    transit = transit_sum
    while current.timestep < current.horizon:
        exposure += current.exposure()
        transit += current.transit
        current = current.advance(WAIT)
    denominator = current.initial_population * current.horizon
    return (
        SAFE_WEIGHT * (current.safe / current.initial_population)
        - EXPOSURE_WEIGHT * (exposure / denominator)
        - TRAVEL_WEIGHT * (transit / denominator)
    )
