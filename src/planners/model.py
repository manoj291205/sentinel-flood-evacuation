"""Observable expected transition model used only by practical planners."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import cached_property

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
    max_destination_hazard: float = 0.70
    hard_safety_enabled: bool = True
    dispatch_enabled: bool = True
    root_timestep: int | None = None
    root_allowed_actions: tuple[SimulationAction, ...] | None = None

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
            max_destination_hazard=value.max_destination_hazard,
            hard_safety_enabled=value.safety_snapshot.hard_safety_enabled,
            dispatch_enabled=observation.get("dispatch_limit_per_timestep", 0) > 0,
            root_timestep=value.current_timestep,
            root_allowed_actions=value.safety_snapshot.allowed_actions,
        )

    @cached_property
    def _zones_by_id(self) -> dict[str, ModelZone]:
        return {item.zone_id: item for item in self.zones}

    @cached_property
    def _shelters_by_id(self) -> dict[str, ModelShelter]:
        return {item.shelter_id: item for item in self.shelters}

    @cached_property
    def _routes_by_pair(self) -> dict[tuple[str, str], ModelRoute]:
        return {(item.zone_id, item.shelter_id): item for item in self.routes}

    @cached_property
    def _routes_by_id(self) -> dict[str, ModelRoute]:
        return {item.route_id: item for item in self.routes}

    def zone(self, zone_id: str) -> ModelZone | None:
        return self._zones_by_id.get(zone_id)

    def shelter(self, shelter_id: str) -> ModelShelter | None:
        return self._shelters_by_id.get(shelter_id)

    def route(self, action: DispatchAction) -> ModelRoute | None:
        return self._routes_by_pair.get((action.zone_id, action.shelter_id))

    def allowed_actions(self) -> tuple[SimulationAction, ...]:
        if self.timestep >= self.horizon:
            return ()
        root_allowed = self.root_allowed_actions if self.timestep == self.root_timestep else None
        allowed: list[SimulationAction] = []
        for action in self.actions:
            # A mask can exclude extra constraints; it cannot grant modeled infeasibility.
            if root_allowed is not None and action not in root_allowed:
                continue
            if action == WAIT:
                allowed.append(action)
                continue
            assert isinstance(action, DispatchAction)
            zone = self.zone(action.zone_id)
            shelter = self.shelter(action.shelter_id)
            route = self.route(action)
            if (
                self.dispatch_enabled
                and zone is not None
                and zone.population > 0
                and shelter is not None
                and shelter.status != "CLOSED"
                and shelter.available > 0
                and (not self.hard_safety_enabled or shelter.severity < self.max_destination_hazard)
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
            route = self._routes_by_id[pending.route_id]
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
        if action not in self.allowed_actions():
            raise ValueError("modeled action is not allowed in the current projected state")
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


def _finish_waiting(
    state: ModelState,
    *,
    timestep: int,
    zone_population: list[int],
    zone_severity: list[float],
    zone_forecast: list[float | None],
    shelter_severity: list[float],
    shelter_forecast: list[float | None],
    route_hazard: dict[str, float | None],
    pending: list[ModelPending],
    safe: int,
    exposure_sum: float,
    transit_sum: float,
) -> float:
    """Allocation-free equivalent of advancing WAIT to the horizon."""
    if state.initial_population == 0:
        return 0.0
    zone_index = {item.zone_id: index for index, item in enumerate(state.zones)}
    shelter_index = {item.shelter_id: index for index, item in enumerate(state.shelters)}
    route_entities = tuple(
        (item.route_id, item.zone_id, item.shelter_id, item.base_travel)
        for item in state.routes
    )
    exposure = exposure_sum
    transit = transit_sum
    while timestep < state.horizon:
        exposure += sum(
            population * severity
            for population, severity in zip(zone_population, zone_severity)
        )
        for event in pending:
            exposure += event.people * float(route_hazard[event.route_id] or 0.0)
        transit += sum(event.people for event in pending)
        new_timestep = timestep + 1
        if new_timestep >= state.horizon:
            timestep = new_timestep
            break

        due = [event for event in pending if event.arrival_timestep == new_timestep]
        pending = [event for event in pending if event.arrival_timestep != new_timestep]
        safe += sum(event.people for event in due)
        previous_zone_severity = zone_severity
        zone_severity = [
            _clip(forecast if forecast is not None else severity)
            for severity, forecast in zip(zone_severity, zone_forecast)
        ]
        zone_forecast = [
            _clip(updated + (updated - previous))
            for updated, previous in zip(zone_severity, previous_zone_severity)
        ]
        previous_shelter_severity = shelter_severity
        shelter_severity = [
            _clip(forecast if forecast is not None else severity)
            for severity, forecast in zip(shelter_severity, shelter_forecast)
        ]
        shelter_forecast = [
            _clip(updated + (updated - previous))
            for updated, previous in zip(shelter_severity, previous_shelter_severity)
        ]
        for route_id, zone_id, shelter_id, base_travel in route_entities:
            if base_travel is not None:
                route_hazard[route_id] = max(
                    zone_severity[zone_index[zone_id]],
                    shelter_severity[shelter_index[shelter_id]],
                )
        timestep = new_timestep

    denominator = state.initial_population * state.horizon
    return (
        SAFE_WEIGHT * (safe / state.initial_population)
        - EXPOSURE_WEIGHT * (exposure / denominator)
        - TRAVEL_WEIGHT * (transit / denominator)
    )


def terminal_estimate(
    state: ModelState,
    exposure_sum: float,
    transit_sum: float,
) -> float:
    """Propagate WAIT to the horizon and score the frozen Gate-6 utility."""
    return _finish_waiting(
        state,
        timestep=state.timestep,
        zone_population=[item.population for item in state.zones],
        zone_severity=[item.severity for item in state.zones],
        zone_forecast=[item.forecast for item in state.zones],
        shelter_severity=[item.severity for item in state.shelters],
        shelter_forecast=[item.forecast for item in state.shelters],
        route_hazard={item.route_id: item.hazard_proxy for item in state.routes},
        pending=list(state.pending),
        safe=state.safe,
        exposure_sum=exposure_sum,
        transit_sum=transit_sum,
    )


def terminal_estimate_after_action(
    state: ModelState,
    action: SimulationAction,
    exposure_sum: float,
    transit_sum: float,
) -> float:
    """Apply one action and finish with WAIT without allocating a child state."""
    zone_population = [item.population for item in state.zones]
    zone_severity = [item.severity for item in state.zones]
    zone_forecast = [item.forecast for item in state.zones]
    shelter_severity = [item.severity for item in state.shelters]
    shelter_forecast = [item.forecast for item in state.shelters]
    route_hazard = {item.route_id: item.hazard_proxy for item in state.routes}
    pending = list(state.pending)
    safe = state.safe
    if isinstance(action, DispatchAction):
        zone = state.zone(action.zone_id)
        shelter = state.shelter(action.shelter_id)
        route = state.route(action)
        if zone is None or shelter is None or route is None or route.expected_travel is None:
            raise ValueError("modeled dispatch is invalid")
        people = min(state.vehicle_capacity, zone.population, shelter.available)
        zone_slot = next(index for index, item in enumerate(state.zones) if item.zone_id == action.zone_id)
        zone_population[zone_slot] -= people
        lag = max(1, math.ceil(route.expected_travel / state.timestep_minutes))
        pending.append(
            ModelPending(
                "terminal-fast-path",
                action.zone_id,
                action.shelter_id,
                route.route_id,
                people,
                state.timestep + lag,
            )
        )

    timestep = state.timestep + 1
    if timestep < state.horizon:
        due = [event for event in pending if event.arrival_timestep == timestep]
        pending = [event for event in pending if event.arrival_timestep != timestep]
        safe += sum(event.people for event in due)
        previous_zone_severity = zone_severity
        zone_severity = [
            _clip(forecast if forecast is not None else severity)
            for severity, forecast in zip(zone_severity, zone_forecast)
        ]
        zone_forecast = [
            _clip(updated + (updated - previous))
            for updated, previous in zip(zone_severity, previous_zone_severity)
        ]
        previous_shelter_severity = shelter_severity
        shelter_severity = [
            _clip(forecast if forecast is not None else severity)
            for severity, forecast in zip(shelter_severity, shelter_forecast)
        ]
        shelter_forecast = [
            _clip(updated + (updated - previous))
            for updated, previous in zip(shelter_severity, previous_shelter_severity)
        ]
        zones = {item.zone_id: index for index, item in enumerate(state.zones)}
        shelters = {item.shelter_id: index for index, item in enumerate(state.shelters)}
        for route in state.routes:
            if route.base_travel is not None:
                route_hazard[route.route_id] = max(
                    zone_severity[zones[route.zone_id]],
                    shelter_severity[shelters[route.shelter_id]],
                )
    return _finish_waiting(
        state,
        timestep=timestep,
        zone_population=zone_population,
        zone_severity=zone_severity,
        zone_forecast=zone_forecast,
        shelter_severity=shelter_severity,
        shelter_forecast=shelter_forecast,
        route_hazard=route_hazard,
        pending=pending,
        safe=safe,
        exposure_sum=exposure_sum,
        transit_sum=transit_sum,
    )


def terminal_action_estimates(
    state: ModelState,
    actions: tuple[SimulationAction, ...],
    exposure_sum: float,
    transit_sum: float,
) -> tuple[float, ...]:
    """Vector-equivalent terminal scores for every final-depth action.

    With only WAIT after this action, hazard evolution is action-independent. Compute
    that common path once and add the exact population/transit deltas per dispatch.
    """
    base = terminal_estimate_after_action(state, WAIT, exposure_sum, transit_sum)
    if state.timestep + 1 >= state.horizon:
        return tuple(base for _ in actions)

    zone_severity = [item.severity for item in state.zones]
    zone_forecast = [item.forecast for item in state.zones]
    shelter_severity = [item.severity for item in state.shelters]
    shelter_forecast = [item.forecast for item in state.shelters]
    zone_index = {item.zone_id: index for index, item in enumerate(state.zones)}
    shelter_index = {item.shelter_id: index for index, item in enumerate(state.shelters)}
    zone_paths = {item.zone_id: [] for item in state.zones}
    route_paths = {item.route_id: [] for item in state.routes}
    for _timestep in range(state.timestep + 1, state.horizon):
        previous = zone_severity
        zone_severity = [
            _clip(forecast if forecast is not None else severity)
            for severity, forecast in zip(zone_severity, zone_forecast)
        ]
        zone_forecast = [
            _clip(updated + (updated - old))
            for updated, old in zip(zone_severity, previous)
        ]
        previous_shelter = shelter_severity
        shelter_severity = [
            _clip(forecast if forecast is not None else severity)
            for severity, forecast in zip(shelter_severity, shelter_forecast)
        ]
        shelter_forecast = [
            _clip(updated + (updated - old))
            for updated, old in zip(shelter_severity, previous_shelter)
        ]
        for item in state.zones:
            zone_paths[item.zone_id].append(zone_severity[zone_index[item.zone_id]])
        for route in state.routes:
            if route.base_travel is None:
                hazard = float(route.hazard_proxy or 0.0)
            else:
                hazard = max(
                    zone_severity[zone_index[route.zone_id]],
                    shelter_severity[shelter_index[route.shelter_id]],
                )
            route_paths[route.route_id].append(hazard)

    denominator = state.initial_population * state.horizon
    results = []
    for action in actions:
        if action == WAIT:
            results.append(base)
            continue
        assert isinstance(action, DispatchAction)
        zone = state.zone(action.zone_id)
        shelter = state.shelter(action.shelter_id)
        route = state.route(action)
        assert zone is not None and shelter is not None and route is not None
        assert route.expected_travel is not None
        people = min(state.vehicle_capacity, zone.population, shelter.available)
        lag = max(1, math.ceil(route.expected_travel / state.timestep_minutes))
        arrival = state.timestep + lag
        pending_steps = max(
            0,
            min(state.horizon, arrival) - (state.timestep + 1),
        )
        exposure_delta = -people * sum(zone_paths[action.zone_id])
        exposure_delta += people * sum(route_paths[route.route_id][:pending_steps])
        transit_delta = people * pending_steps
        safe_delta = people if arrival < state.horizon else 0
        results.append(
            base
            + SAFE_WEIGHT * (safe_delta / state.initial_population)
            - EXPOSURE_WEIGHT * (exposure_delta / denominator)
            - TRAVEL_WEIGHT * (transit_delta / denominator)
        )
    return tuple(results)
