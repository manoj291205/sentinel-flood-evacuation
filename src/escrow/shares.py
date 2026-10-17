"""Deterministic division of currently free shelter seats between field teams."""

from __future__ import annotations

from math import ceil, floor
from typing import Mapping

from src.certify.forecast import forecast_from_state

TEAMS = ("TEAM-A", "TEAM-B")


def team_zones(scenario) -> dict[str, tuple[str, ...]]:
    zones = sorted(zone.zone_id for zone in scenario.zones)
    middle = ceil(len(zones) / 2)
    return {TEAMS[0]: tuple(zones[:middle]), TEAMS[1]: tuple(zones[middle:])}


def forecast_weights(scenario, state, road_state) -> dict[str, float]:
    severity = dict(forecast_from_state(state, road_state, scenario).zone_severity)
    population = {zone.zone_id: zone.population_remaining for zone in state.zones}
    return {
        team: sum(population[zone] * (1 + severity[zone]) for zone in zones)
        for team, zones in team_zones(scenario).items()
    }


def split_shares(free: Mapping[str, int], weights: Mapping[str, float]) -> dict[str, dict[str, int]]:
    values = {team: max(0.0, float(weights.get(team, 0.0))) for team in TEAMS}
    if not sum(values.values()):
        values = {team: 1.0 for team in TEAMS}
    total = sum(values.values())
    return {
        team: {shelter: floor(max(0, seats) * values[team] / total)
               for shelter, seats in free.items()}
        for team in TEAMS
    }
