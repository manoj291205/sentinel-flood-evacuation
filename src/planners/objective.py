"""Frozen Gate-6 physical utility and episode accounting."""

from __future__ import annotations

from dataclasses import dataclass

from src.sim.state import EpisodeState

SAFE_WEIGHT = 0.70
EXPOSURE_WEIGHT = 0.25
TRAVEL_WEIGHT = 0.05
GATE6_UTILITY_MIN = -0.30
GATE6_UTILITY_MAX = 0.70
EPSILON_DEN = 0.01


def state_exposure(state: EpisodeState) -> float:
    zone_exposure = sum(
        zone.population_remaining * zone.flood_severity_current
        for zone in state.zones
    )
    transit_exposure = 0.0
    for event in state.pending_dispatches:
        route = state.route(event.route_id)
        if route is not None and route.route_hazard_proxy is not None:
            transit_exposure += event.people * route.route_hazard_proxy
    return zone_exposure + transit_exposure


@dataclass
class EpisodeLedger:
    exposed_person_timesteps: float = 0.0
    in_transit_person_timesteps: int = 0
    decisions: int = 0

    def observe(self, state: EpisodeState) -> None:
        self.exposed_person_timesteps += state_exposure(state)
        self.in_transit_person_timesteps += state.people_in_transit
        self.decisions += 1

    def utility(self, terminal_state: EpisodeState, horizon_steps: int) -> float:
        population = terminal_state.initial_evacuation_population
        denominator = population * horizon_steps
        if denominator <= 0:
            raise ValueError("Gate 6 utility requires positive population and horizon")
        safe_fraction = terminal_state.people_safely_arrived / population
        exposure = self.exposed_person_timesteps / denominator
        travel = self.in_transit_person_timesteps / denominator
        return (
            SAFE_WEIGHT * safe_fraction
            - EXPOSURE_WEIGHT * exposure
            - TRAVEL_WEIGHT * travel
        )


def exact_headroom(value: float, lower: float, oracle: float) -> float | None:
    denominator = oracle - lower
    if denominator <= EPSILON_DEN:
        return None
    return (value - lower) / denominator
