"""Synthetic route-risk estimates, absorbing closures, and realized travel."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .configs import UncertaintyConfig
from .events import AuditEventType, AuditRecord
from .randomness import EpisodeRandomStreams, RandomStream
from .schemas import RouteDefinition, ScenarioV3
from .state import EpisodeState, RouteState


def route_hazard_proxy(state: EpisodeState, route: RouteState) -> float:
    """Pre-geospatial proxy: maximum source-zone/destination-shelter severity."""
    zone = state.zone(route.source_zone_id)
    shelter = state.shelter(route.destination_shelter_id)
    if zone is None or shelter is None:
        raise ValueError(f"route {route.route_id} references missing runtime entities")
    return max(zone.flood_severity_current, shelter.flood_severity_current)


def modeled_closure_probability(
    route: RouteDefinition,
    hazard_proxy: float,
    config: UncertaintyConfig,
) -> float:
    if not route.reachable or route.base_closure_probability is None:
        return 0.0
    probability = (
        route.base_closure_probability * config.base_closure_multiplier
        + config.hazard_to_closure_strength * hazard_proxy
    )
    return min(config.maximum_closure_probability, max(0.0, probability))


def route_noise_fraction(
    route: RouteDefinition, config: UncertaintyConfig
) -> float:
    """Configured regime variation plus one quarter of the route's static CV."""
    if route.travel_time_mean is None or route.travel_time_std is None:
        return 0.0
    return config.travel_noise_fraction + 0.25 * (
        route.travel_time_std / route.travel_time_mean
    )


def update_route_state(
    scenario: ScenarioV3,
    state: EpisodeState,
    config: UncertaintyConfig,
    streams: EpisodeRandomStreams,
    *,
    realize_closures: bool,
) -> tuple[EpisodeState, tuple[AuditRecord, ...]]:
    definitions = {route.route_id: route for route in scenario.network.routes}
    routes: list[RouteState] = []
    records: list[AuditRecord] = []
    for route in state.routes:
        definition = definitions[route.route_id]
        if not definition.reachable:
            routes.append(
                replace(
                    route,
                    reachable_current=False,
                    base_travel_time_minutes=None,
                    expected_travel_time_minutes=None,
                    travel_time_uncertainty_minutes=None,
                    estimated_closure_probability=0.0,
                    route_hazard_proxy=None,
                )
            )
            continue

        assert definition.travel_time_mean is not None
        hazard = route_hazard_proxy(state, route)
        expected = definition.travel_time_mean * (
            1.0 + config.route_hazard_travel_factor * hazard
        )
        uncertainty = expected * route_noise_fraction(definition, config)
        probability = modeled_closure_probability(definition, hazard, config)
        close_now = False
        if route.reachable_current and realize_closures:
            close_now = (
                streams.uniform(
                    RandomStream.ROUTE_CLOSURE,
                    state.current_timestep,
                    route.route_id,
                )
                < probability
            )
        reachable = route.reachable_current and not close_now
        closed_at = (
            state.current_timestep
            if close_now
            else route.closed_at_timestep
        )
        routes.append(
            replace(
                route,
                reachable_current=reachable,
                travel_time_current=expected,
                base_travel_time_minutes=definition.travel_time_mean,
                expected_travel_time_minutes=expected,
                travel_time_uncertainty_minutes=uncertainty,
                estimated_closure_probability=probability,
                route_hazard_proxy=hazard,
                closed_at_timestep=closed_at,
            )
        )
        if close_now:
            records.append(
                AuditRecord(
                    event_type=AuditEventType.ROUTE_CLOSED,
                    timestep=state.current_timestep,
                    route_id=route.route_id,
                    uncertainty_config_id=config.config_id,
                    probability=probability,
                    hazard_proxy=hazard,
                    reason_code="ABSORBING_SYNTHETIC_ROUTE_CLOSURE",
                    message="route became unavailable for new dispatches",
                )
            )
    return replace(state, routes=tuple(routes)), tuple(records)


@dataclass(frozen=True)
class TravelRealization:
    base_minutes: float
    expected_minutes: float
    realized_minutes: float
    multiplier: float
    uncertainty_minutes: float


def realize_dispatch_travel(
    route_definition: RouteDefinition,
    route_state: RouteState,
    config: UncertaintyConfig,
    streams: EpisodeRandomStreams,
    *,
    departure_timestep: int,
    event_id: str,
) -> TravelRealization:
    if (
        route_definition.travel_time_mean is None
        or route_state.expected_travel_time_minutes is None
        or route_state.travel_time_uncertainty_minutes is None
    ):
        raise ValueError("travel can only be realized for a configured reachable route")
    sigma = route_noise_fraction(route_definition, config)
    raw_multiplier = 1.0 + sigma * streams.normal(
        RandomStream.TRAVEL,
        departure_timestep,
        route_state.route_id,
        event_id,
    )
    multiplier = min(
        config.maximum_travel_multiplier,
        max(config.minimum_travel_multiplier, raw_multiplier),
    )
    realized = route_state.expected_travel_time_minutes * multiplier
    if not math.isfinite(realized) or realized <= 0:
        raise ValueError("realized travel must be finite and positive")
    return TravelRealization(
        base_minutes=route_definition.travel_time_mean,
        expected_minutes=route_state.expected_travel_time_minutes,
        realized_minutes=realized,
        multiplier=multiplier,
        uncertainty_minutes=route_state.travel_time_uncertainty_minutes,
    )
