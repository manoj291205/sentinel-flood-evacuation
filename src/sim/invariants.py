"""Fail-fast conservation and identity checks for Phase 3 episode snapshots."""

from __future__ import annotations

from .events import DispatchStatus
from .schemas import ScenarioV3
from .state import EpisodeState, TerminalReason


class InvariantViolation(RuntimeError):
    """Raised when a simulator state is internally inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvariantViolation(message)


def assert_episode_invariants(scenario: ScenarioV3, state: EpisodeState) -> None:
    """Validate all Phase 3 ledgers; return only when the snapshot is coherent."""
    _require(state.scenario_id == scenario.scenario_id, "state scenario_id mismatch")
    _require(state.current_timestep >= 0, "current timestep must be nonnegative")
    _require(state.next_dispatch_sequence >= 1, "next dispatch sequence must be positive")
    expected_dispatch_limit = min(
        scenario.fleet.vehicle_count, scenario.fleet.dispatches_per_timestep
    )
    _require(
        state.dispatch_limit_per_timestep == expected_dispatch_limit,
        "runtime dispatch limit mismatch scenario",
    )
    _require(
        0
        <= state.dispatches_used_this_timestep
        <= state.dispatch_limit_per_timestep,
        "dispatches used must be within the configured limit",
    )

    scenario_zone_ids = {zone.zone_id for zone in scenario.zones}
    state_zone_ids = {zone.zone_id for zone in state.zones}
    _require(len(state_zone_ids) == len(state.zones), "runtime zone IDs must be unique")
    _require(state_zone_ids == scenario_zone_ids, "runtime zone IDs mismatch scenario")

    scenario_shelter_ids = {shelter.shelter_id for shelter in scenario.shelters}
    state_shelter_ids = {shelter.shelter_id for shelter in state.shelters}
    _require(
        len(state_shelter_ids) == len(state.shelters),
        "runtime shelter IDs must be unique",
    )
    _require(
        state_shelter_ids == scenario_shelter_ids,
        "runtime shelter IDs mismatch scenario",
    )

    scenario_route_ids = {route.route_id for route in scenario.network.routes}
    state_route_ids = {route.route_id for route in state.routes}
    _require(len(state_route_ids) == len(state.routes), "runtime route IDs must be unique")
    _require(state_route_ids == scenario_route_ids, "runtime route IDs mismatch scenario")

    initial_remaining = {
        zone.zone_id: zone.population_initial_remaining for zone in scenario.zones
    }
    dispatched_by_zone = {zone_id: 0 for zone_id in state_zone_ids}
    pending_by_shelter = {shelter_id: 0 for shelter_id in state_shelter_ids}
    arrived_by_shelter = {shelter_id: 0 for shelter_id in state_shelter_ids}

    for zone in state.zones:
        _require(zone.population_remaining >= 0, f"negative population in {zone.zone_id}")
        _require(
            0.0 <= zone.flood_severity_current <= 1.0,
            f"invalid current severity in {zone.zone_id}",
        )

    event_ids = [event.event_id for event in state.dispatch_events]
    _require(len(event_ids) == len(set(event_ids)), "dispatch event IDs must be unique")
    _require(
        event_ids
        == [f"dispatch-{sequence:06d}" for sequence in range(1, len(event_ids) + 1)],
        "dispatch event IDs must be sequential and deterministic",
    )
    _require(
        state.next_dispatch_sequence == len(event_ids) + 1,
        "next dispatch sequence does not follow the event ledger",
    )
    for event in state.dispatch_events:
        _require(event.people > 0, f"event {event.event_id} must carry people")
        _require(event.travel_lag_steps >= 1, f"event {event.event_id} has invalid lag")
        _require(
            event.arrival_timestep == event.departure_timestep + event.travel_lag_steps,
            f"event {event.event_id} arrival does not match its lag",
        )
        _require(event.source_zone_id in state_zone_ids, "event has unknown source zone")
        _require(
            event.destination_shelter_id in state_shelter_ids,
            "event has unknown destination shelter",
        )
        _require(event.route_id in state_route_ids, "event has unknown route")
        dispatched_by_zone[event.source_zone_id] += event.people
        if event.status is DispatchStatus.IN_TRANSIT:
            pending_by_shelter[event.destination_shelter_id] += event.people
            _require(
                event.arrival_timestep >= state.current_timestep,
                f"event {event.event_id} is overdue",
            )
        else:
            arrived_by_shelter[event.destination_shelter_id] += event.people

    for zone in state.zones:
        _require(
            zone.population_remaining + dispatched_by_zone[zone.zone_id]
            == initial_remaining[zone.zone_id],
            f"source population ledger mismatch in {zone.zone_id}",
        )

    arrived_people = sum(
        event.people
        for event in state.dispatch_events
        if event.status is DispatchStatus.ARRIVED
    )
    _require(
        state.people_safely_arrived == arrived_people,
        "safe-arrival ledger does not equal arrived dispatch events",
    )
    _require(state.people_safely_arrived >= 0, "safe population must be nonnegative")
    _require(
        state.initial_evacuation_population
        == state.population_remaining
        + state.people_in_transit
        + state.people_safely_arrived,
        "population conservation violated",
    )

    initial_occupancy = {
        shelter.shelter_id: shelter.occupancy_initial for shelter in scenario.shelters
    }
    for shelter in state.shelters:
        _require(shelter.capacity_total >= 0, f"negative capacity in {shelter.shelter_id}")
        _require(shelter.occupancy_current >= 0, f"negative occupancy in {shelter.shelter_id}")
        _require(shelter.capacity_reserved >= 0, f"negative reservation in {shelter.shelter_id}")
        _require(shelter.capacity_available >= 0, f"overbooked shelter {shelter.shelter_id}")
        _require(
            0.0 <= shelter.flood_severity_current <= 1.0,
            f"invalid current severity in {shelter.shelter_id}",
        )
        _require(
            shelter.capacity_reserved == pending_by_shelter[shelter.shelter_id],
            f"reservation ledger mismatch in {shelter.shelter_id}",
        )
        _require(
            shelter.occupancy_current
            == initial_occupancy[shelter.shelter_id]
            + arrived_by_shelter[shelter.shelter_id],
            f"occupancy ledger mismatch in {shelter.shelter_id}",
        )

    if state.terminal:
        _require(state.terminal_reason is not None, "terminal state requires a reason")
        _require(
            isinstance(state.terminal_reason, TerminalReason),
            "terminal reason must be a TerminalReason",
        )
        if state.terminal_reason is TerminalReason.ALL_EVACUATED:
            _require(state.population_remaining == 0, "completion has remaining population")
            _require(state.people_in_transit == 0, "completion has people in transit")
        elif state.terminal_reason is TerminalReason.HORIZON_REACHED:
            _require(
                state.current_timestep >= scenario.time.horizon_steps,
                "horizon termination occurred early",
            )
    else:
        _require(state.terminal_reason is None, "nonterminal state has a terminal reason")
        _require(
            state.current_timestep < scenario.time.horizon_steps,
            "nonterminal state reached the horizon",
        )
