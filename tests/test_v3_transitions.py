"""Phase 3 tests for deterministic multi-timestep evacuation transitions."""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from src.sim import (
    WAIT,
    ActionRejectionCode,
    AuditEventType,
    DispatchAction,
    DispatchStatus,
    InvariantViolation,
    ScenarioV3,
    ShelterStatus,
    TerminalReason,
    WaitAction,
    assert_episode_invariants,
    initialize_episode,
    transition,
    validate_action,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "scenarios_v3" / "example_v3_scenario.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(EXAMPLE.read_text())


@pytest.fixture
def scenario() -> ScenarioV3:
    return ScenarioV3.from_dict(json.loads(EXAMPLE.read_text()))


def _scenario(raw: dict, *, z1_population: int | None = None) -> ScenarioV3:
    data = copy.deepcopy(raw)
    if z1_population is not None:
        zone = next(zone for zone in data["zones"] if zone["zone_id"] == "Z1")
        zone["population_total"] = z1_population
        zone["population_initial_remaining"] = z1_population
        zone["vulnerable_population"] = min(zone["vulnerable_population"], z1_population)
        zone["medical_priority_population"] = min(
            zone["medical_priority_population"], z1_population
        )
    return ScenarioV3.from_dict(data)


def _state_with_shelter(state, shelter_id: str, **changes):
    return replace(
        state,
        shelters=tuple(
            replace(shelter, **changes) if shelter.shelter_id == shelter_id else shelter
            for shelter in state.shelters
        ),
    )


def _state_with_zone(state, zone_id: str, **changes):
    return replace(
        state,
        zones=tuple(
            replace(zone, **changes) if zone.zone_id == zone_id else zone
            for zone in state.zones
        ),
    )


def test_initial_state_is_separate_from_static_scenario(scenario):
    state = initialize_episode(scenario)
    assert state.scenario_id == scenario.scenario_id
    assert state.current_timestep == 0
    assert state.population_remaining == 850
    assert state.people_in_transit == 0
    assert state.people_safely_arrived == 0
    assert state.dispatch_limit_per_timestep == 1
    assert state.dispatches_used_this_timestep == 0
    assert state.dispatch_events == ()
    assert state.audit_log == ()


def test_initialization_and_transitions_do_not_mutate_scenario(scenario):
    before = scenario.to_dict()
    state = initialize_episode(scenario)
    transition(scenario, state, DispatchAction("Z1", "S1"))
    assert scenario.to_dict() == before


def test_initial_invariants_hold(scenario):
    assert_episode_invariants(scenario, initialize_episode(scenario))


def test_initial_runtime_order_is_canonical(scenario):
    state = initialize_episode(scenario)
    assert [zone.zone_id for zone in state.zones] == ["Z1", "Z2"]
    assert [shelter.shelter_id for shelter in state.shelters] == ["S1", "S2"]


def test_runtime_state_is_frozen(scenario):
    state = initialize_episode(scenario)
    with pytest.raises(FrozenInstanceError):
        state.current_timestep = 9  # type: ignore[misc]


def test_initial_occupants_are_not_counted_as_evacuated(scenario):
    state = initialize_episode(scenario)
    assert sum(item.occupancy_current for item in state.shelters) == 250
    assert state.people_safely_arrived == 0


def test_wait_advances_exactly_one_timestep(scenario):
    state = initialize_episode(scenario)
    result = transition(scenario, state, WAIT)
    assert result.accepted
    assert (result.previous_timestep, result.new_timestep) == (0, 1)
    assert result.state.population_remaining == state.population_remaining
    assert result.state.audit_log[-1].event_type is AuditEventType.WAIT


def test_wait_action_instances_are_semantically_equal(scenario):
    state = initialize_episode(scenario)
    assert transition(scenario, state, WaitAction()).state == transition(
        scenario, state, WAIT
    ).state


def test_dispatch_moves_people_from_zone_to_transit(scenario):
    state = initialize_episode(scenario)
    result = transition(scenario, state, DispatchAction("Z1", "S1"))
    assert result.accepted
    assert result.people_dispatched == 50
    assert result.state.zone("Z1").population_remaining == 450  # type: ignore[union-attr]
    assert result.state.people_in_transit == 50
    assert result.state.people_safely_arrived == 0
    assert result.state.pending_arrivals == result.state.pending_dispatches


def test_dispatch_reserves_capacity_without_occupying_it(scenario):
    state = initialize_episode(scenario)
    before = state.shelter("S1")
    after = transition(scenario, state, DispatchAction("Z1", "S1")).state.shelter("S1")
    assert before is not None and after is not None
    assert after.capacity_reserved == 50
    assert after.occupancy_current == before.occupancy_current
    assert after.capacity_available == before.capacity_available - 50


def test_exact_remaining_capacity_dispatch_works(raw):
    shelter = next(item for item in raw["shelters"] if item["shelter_id"] == "S1")
    shelter["capacity_total"] = shelter["occupancy_initial"] + 50
    scenario = ScenarioV3.from_dict(raw)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.accepted and result.people_dispatched == 50
    assert result.state.shelter("S1").capacity_available == 0  # type: ignore[union-attr]


def test_reservations_prevent_multiple_dispatches_from_overbooking(raw):
    shelter = next(item for item in raw["shelters"] if item["shelter_id"] == "S1")
    shelter["capacity_total"] = shelter["occupancy_initial"] + 75
    scenario = ScenarioV3.from_dict(raw)
    state = initialize_episode(scenario)
    first = transition(scenario, state, DispatchAction("Z1", "S1"))
    second = transition(scenario, first.state, DispatchAction("Z2", "S1"))
    third = transition(scenario, second.state, DispatchAction("Z2", "S1"))
    assert first.people_dispatched == 50
    assert second.people_dispatched == 25
    assert third.rejection_code is ActionRejectionCode.NO_CAPACITY
    assert second.state.shelter("S1").capacity_available == 0  # type: ignore[union-attr]


def test_dispatch_event_has_deterministic_identity_and_fields(scenario):
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    event = result.events_created[0]
    assert event.event_id == "dispatch-000001"
    assert event.source_zone_id == "Z1"
    assert event.destination_shelter_id == "S1"
    assert event.route_id == "R-Z1-S1"
    assert event.departure_timestep == 0
    assert event.arrival_timestep == 2
    assert event.travel_lag_steps == 2
    assert event.status is DispatchStatus.IN_TRANSIT


@pytest.mark.parametrize(
    ("travel_minutes", "expected_lag"),
    [(0.1, 1), (10.0, 1), (10.1, 2), (20.0, 2), (25.0, 3)],
)
def test_travel_lag_uses_ceiling_with_minimum_one(
    raw, travel_minutes, expected_lag
):
    route = next(
        route for route in raw["network"]["routes"] if route["route_id"] == "R-Z1-S1"
    )
    route["travel_time_mean"] = travel_minutes
    scenario = ScenarioV3.from_dict(raw)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.events_created[0].travel_lag_steps == expected_lag


def test_people_remain_in_transit_before_arrival(scenario):
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    state = transition(scenario, state, WAIT).state
    assert state.current_timestep == 2
    assert state.people_in_transit == 50
    assert state.people_safely_arrived == 0


def test_arrival_decreases_transit_and_increases_safe_population(scenario):
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    state = transition(scenario, state, WAIT).state
    state = transition(scenario, state, WAIT).state
    assert state.people_in_transit == 0
    assert state.people_safely_arrived == 50


def test_arrival_is_processed_before_action_at_due_timestep(scenario):
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    event = state.pending_arrivals[0]
    assert event.departure_timestep == 0
    assert event.arrival_timestep == 2
    state = transition(scenario, state, WAIT).state
    assert state.current_timestep == event.arrival_timestep == 2
    result = transition(scenario, state, DispatchAction("Z2", "S1"))
    assert result.previous_timestep == 2
    assert result.new_timestep == 3
    assert result.arrivals_processed[0].event_id == "dispatch-000001"
    assert result.arrivals_processed[0].status is DispatchStatus.ARRIVED
    assert result.audit_records[0].event_type is AuditEventType.ARRIVAL_PROCESSED
    assert result.audit_records[1].event_type is AuditEventType.DISPATCH_CREATED
    assert result.state.people_safely_arrived == 50
    assert result.state.people_in_transit == 50


def test_arrival_converts_reservation_to_occupancy(scenario):
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    state = transition(scenario, state, WAIT).state
    before = state.shelter("S1")
    state = transition(scenario, state, WAIT).state
    after = state.shelter("S1")
    assert before is not None and after is not None
    assert (before.occupancy_current, before.capacity_reserved) == (150, 50)
    assert (after.occupancy_current, after.capacity_reserved) == (200, 0)
    assert before.capacity_available == after.capacity_available


def test_dispatch_batch_is_partial_when_zone_has_fewer_people(raw):
    scenario = _scenario(raw, z1_population=17)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.people_dispatched == 17
    assert result.state.zone("Z1").population_remaining == 0  # type: ignore[union-attr]


def test_dispatch_batch_is_partial_when_shelter_has_less_capacity(raw):
    shelter = next(item for item in raw["shelters"] if item["shelter_id"] == "S1")
    shelter["capacity_total"] = shelter["occupancy_initial"] + 13
    scenario = ScenarioV3.from_dict(raw)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.people_dispatched == 13
    assert result.state.shelter("S1").capacity_available == 0  # type: ignore[union-attr]


def test_closed_shelter_is_mechanically_rejected(scenario):
    state = _state_with_shelter(
        initialize_episode(scenario), "S1", status_current=ShelterStatus.CLOSED
    )
    result = transition(scenario, state, DispatchAction("Z1", "S1"))
    assert not result.accepted
    assert result.rejection_code is ActionRejectionCode.SHELTER_CLOSED


def test_restricted_shelter_is_mechanically_allowed(scenario):
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S2")
    )
    assert result.accepted
    assert result.events_created[0].destination_shelter_id == "S2"


def test_unreachable_route_is_rejected(scenario):
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z2", "S2")
    )
    assert result.rejection_code is ActionRejectionCode.ROUTE_UNREACHABLE


@pytest.mark.parametrize(
    ("action", "code"),
    [
        (DispatchAction("UNKNOWN", "S1"), ActionRejectionCode.UNKNOWN_ZONE),
        (DispatchAction("Z1", "UNKNOWN"), ActionRejectionCode.UNKNOWN_SHELTER),
        (object(), ActionRejectionCode.INVALID_ACTION_TYPE),
    ],
)
def test_invalid_action_is_structurally_rejected(scenario, action, code):
    result = transition(scenario, initialize_episode(scenario), action)
    assert not result.accepted
    assert result.rejection_code is code


def test_missing_route_is_rejected(raw):
    raw["network"]["routes"] = [
        route
        for route in raw["network"]["routes"]
        if route["route_id"] != "R-Z1-S1"
    ]
    scenario = ScenarioV3.from_dict(raw)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.rejection_code is ActionRejectionCode.NO_ROUTE


def test_ambiguous_route_is_rejected(raw):
    duplicate = copy.deepcopy(
        next(
            route
            for route in raw["network"]["routes"]
            if route["route_id"] == "R-Z1-S1"
        )
    )
    duplicate["route_id"] = "R-Z1-S1-ALTERNATE"
    raw["network"]["routes"].append(duplicate)
    scenario = ScenarioV3.from_dict(raw)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.rejection_code is ActionRejectionCode.AMBIGUOUS_ROUTE


def test_no_population_is_rejected_without_empty_event(raw):
    zone = next(item for item in raw["zones"] if item["zone_id"] == "Z1")
    zone["population_total"] = 0
    zone["population_initial_remaining"] = 0
    zone["vulnerable_population"] = 0
    zone["medical_priority_population"] = 0
    scenario = ScenarioV3.from_dict(raw)
    state = initialize_episode(scenario)
    result = transition(scenario, state, DispatchAction("Z1", "S1"))
    assert result.rejection_code is ActionRejectionCode.NO_POPULATION
    assert result.events_created == ()


def test_no_capacity_is_rejected(raw):
    shelter = next(item for item in raw["shelters"] if item["shelter_id"] == "S1")
    shelter["capacity_total"] = shelter["occupancy_initial"]
    scenario = ScenarioV3.from_dict(raw)
    state = initialize_episode(scenario)
    result = transition(scenario, state, DispatchAction("Z1", "S1"))
    assert result.rejection_code is ActionRejectionCode.NO_CAPACITY


def test_wait_creates_no_dispatch_event(scenario):
    result = transition(scenario, initialize_episode(scenario), WAIT)
    assert result.events_created == ()
    assert result.state.dispatch_events == ()


def test_disabled_fleet_rejects_dispatch_but_allows_wait(raw):
    raw["fleet"]["evacuation_enabled"] = False
    raw["fleet"]["dispatches_per_timestep"] = 0
    scenario = ScenarioV3.from_dict(raw)
    state = initialize_episode(scenario)
    rejected = transition(scenario, state, DispatchAction("Z1", "S1"))
    waited = transition(scenario, state, WAIT)
    assert rejected.rejection_code is ActionRejectionCode.EVACUATION_DISABLED
    assert waited.accepted and waited.new_timestep == 1


def test_invalid_current_travel_time_is_rejected(scenario):
    state = initialize_episode(scenario)
    state = replace(
        state,
        routes=tuple(
            replace(route, travel_time_current=None)
            if route.route_id == "R-Z1-S1"
            else route
            for route in state.routes
        ),
    )
    result = transition(scenario, state, DispatchAction("Z1", "S1"))
    assert result.rejection_code is ActionRejectionCode.INVALID_TRAVEL_TIME


def test_validate_action_observes_configured_dispatch_limit(scenario):
    state = replace(initialize_episode(scenario), dispatches_used_this_timestep=1)
    validation = validate_action(scenario, state, DispatchAction("Z1", "S1"))
    assert validation.rejection_code is ActionRejectionCode.NO_DISPATCH_AVAILABILITY


def test_rejected_action_does_not_mutate_or_advance_state(scenario):
    state = initialize_episode(scenario)
    snapshot = state.to_dict()
    result = transition(scenario, state, DispatchAction("Z2", "S2"))
    assert result.state is state
    assert result.state.to_dict() == snapshot
    assert result.new_timestep == result.previous_timestep == 0
    assert result.audit_records[0].event_type is AuditEventType.ACTION_REJECTED
    assert result.state.audit_log == ()


def test_rejection_transactionally_rolls_back_due_arrival(scenario):
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    state = transition(scenario, state, WAIT).state
    assert state.current_timestep == 2
    result = transition(scenario, state, DispatchAction("Z2", "S2"))
    assert result.state is state
    assert result.arrivals_processed == ()
    assert result.state.people_in_transit == 50
    assert result.state.people_safely_arrived == 0


def test_retry_after_rejection_processes_due_arrival(scenario):
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    state = transition(scenario, state, WAIT).state
    rejected = transition(scenario, state, DispatchAction("Z2", "S2"))
    accepted = transition(scenario, rejected.state, WAIT)
    assert accepted.arrivals_processed[0].event_id == "dispatch-000001"
    assert accepted.state.people_safely_arrived == 50


def test_population_is_conserved_across_dispatch_wait_and_arrival(scenario):
    state = initialize_episode(scenario)
    actions = [DispatchAction("Z1", "S1"), WAIT, WAIT, DispatchAction("Z2", "S1")]
    for action in actions:
        state = transition(scenario, state, action).state
        assert (
            state.population_remaining
            + state.people_in_transit
            + state.people_safely_arrived
            == state.initial_evacuation_population
        )
        assert_episode_invariants(scenario, state)


def test_pending_events_and_reservations_match_transit_ledger(scenario):
    state = initialize_episode(scenario)
    state = transition(scenario, state, DispatchAction("Z1", "S1")).state
    state = transition(scenario, state, DispatchAction("Z2", "S1")).state
    assert len(state.pending_dispatches) == 2
    assert sum(event.people for event in state.pending_dispatches) == state.people_in_transit
    assert state.shelter("S1").capacity_reserved == state.people_in_transit  # type: ignore[union-attr]
    assert_episode_invariants(scenario, state)


def test_event_ids_increase_across_timesteps(scenario):
    state = initialize_episode(scenario)
    state = transition(scenario, state, DispatchAction("Z1", "S1")).state
    state = transition(scenario, state, DispatchAction("Z2", "S1")).state
    assert [event.event_id for event in state.dispatch_events] == [
        "dispatch-000001",
        "dispatch-000002",
    ]


def test_completion_waits_for_final_arrival(raw):
    for zone in raw["zones"]:
        count = 50 if zone["zone_id"] == "Z1" else 0
        zone["population_total"] = count
        zone["population_initial_remaining"] = count
        zone["vulnerable_population"] = 0
        zone["medical_priority_population"] = 0
    route = next(
        item for item in raw["network"]["routes"] if item["route_id"] == "R-Z1-S1"
    )
    route["travel_time_mean"] = 10.0
    scenario = ScenarioV3.from_dict(raw)
    dispatched = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    assert dispatched.population_remaining == 0
    assert dispatched.people_in_transit == 50
    assert not dispatched.terminal
    arrived = transition(scenario, dispatched, WAIT).state
    assert arrived.terminal
    assert arrived.terminal_reason is TerminalReason.ALL_EVACUATED


def test_horizon_terminates_after_increment(scenario):
    state = initialize_episode(scenario)
    for _ in range(scenario.time.horizon_steps):
        state = transition(scenario, state, WAIT).state
    assert state.current_timestep == scenario.time.horizon_steps
    assert state.terminal
    assert state.terminal_reason is TerminalReason.HORIZON_REACHED


def test_transition_result_exposes_terminal_fields(raw):
    raw["time"]["horizon_steps"] = 2
    scenario = ScenarioV3.from_dict(raw)
    first = transition(scenario, initialize_episode(scenario), WAIT)
    second = transition(scenario, first.state, WAIT)
    assert second.terminal
    assert second.terminal_reason is TerminalReason.HORIZON_REACHED


def test_horizon_preserves_unserved_and_in_transit_people(raw):
    raw["time"]["horizon_steps"] = 2
    scenario = ScenarioV3.from_dict(raw)
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S2")
    ).state
    state = transition(scenario, state, WAIT).state
    assert state.terminal_reason is TerminalReason.HORIZON_REACHED
    assert state.people_in_transit == 50
    assert state.population_remaining == 800
    assert state.pending_dispatches[0].arrival_timestep == 3


def test_action_after_terminal_is_rejected_without_advancing(raw):
    raw["time"]["horizon_steps"] = 2
    scenario = ScenarioV3.from_dict(raw)
    state = initialize_episode(scenario)
    state = transition(scenario, state, WAIT).state
    state = transition(scenario, state, WAIT).state
    result = transition(scenario, state, WAIT)
    assert result.rejection_code is ActionRejectionCode.EPISODE_TERMINAL
    assert result.state is state
    assert result.new_timestep == 2


def test_same_action_trace_replays_identically(scenario):
    actions = [
        DispatchAction("Z1", "S1"),
        DispatchAction("Z2", "S1"),
        WAIT,
        DispatchAction("Z1", "S2"),
        WAIT,
    ]

    def run():
        state = initialize_episode(scenario)
        results = []
        for action in actions:
            result = transition(scenario, state, action)
            results.append(result.to_dict())
            state = result.state
        return state.to_dict(), results

    assert run() == run()


def test_state_and_transition_are_json_serializable(scenario):
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    encoded = json.dumps(result.to_dict(), sort_keys=True)
    assert '"event_id": "dispatch-000001"' in encoded


def test_route_and_hazard_state_remain_deterministic_no_ops(scenario):
    initial = initialize_episode(scenario)
    later = transition(scenario, initial, WAIT).state
    assert later.routes == initial.routes
    assert [zone.flood_severity_current for zone in later.zones] == [
        zone.flood_severity_current for zone in initial.zones
    ]
    assert [shelter.flood_severity_current for shelter in later.shelters] == [
        shelter.flood_severity_current for shelter in initial.shelters
    ]


def test_travel_standard_deviation_and_closure_probability_are_unused(raw):
    route = next(
        item for item in raw["network"]["routes"] if item["route_id"] == "R-Z1-S1"
    )
    route["travel_time_std"] = 999.0
    route["base_closure_probability"] = 1.0
    scenario = ScenarioV3.from_dict(raw)
    result = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    )
    assert result.accepted
    assert result.events_created[0].travel_lag_steps == 2


def test_open_shelter_is_mechanically_allowed(scenario):
    assert transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).accepted


def test_dispatch_validity_does_not_apply_hazard_threshold(scenario):
    state = _state_with_zone(
        initialize_episode(scenario), "Z1", flood_severity_current=1.0
    )
    state = _state_with_shelter(state, "S1", flood_severity_current=1.0)
    assert transition(scenario, state, DispatchAction("Z1", "S1")).accepted


@pytest.mark.parametrize(
    "tamper",
    [
        lambda state: _state_with_zone(
            state, "Z1", population_remaining=-1
        ),
        lambda state: _state_with_shelter(
            state, "S1", capacity_reserved=1
        ),
        lambda state: replace(state, people_safely_arrived=1),
        lambda state: replace(state, scenario_id="wrong"),
    ],
)
def test_invariant_checker_rejects_corrupt_state(scenario, tamper):
    with pytest.raises(InvariantViolation):
        assert_episode_invariants(scenario, tamper(initialize_episode(scenario)))


def test_audit_log_contains_dispatch_arrival_wait_and_termination(raw):
    for zone in raw["zones"]:
        count = 50 if zone["zone_id"] == "Z1" else 0
        zone["population_total"] = count
        zone["population_initial_remaining"] = count
        zone["vulnerable_population"] = 0
        zone["medical_priority_population"] = 0
    route = next(
        item for item in raw["network"]["routes"] if item["route_id"] == "R-Z1-S1"
    )
    route["travel_time_mean"] = 10.0
    scenario = ScenarioV3.from_dict(raw)
    state = transition(
        scenario, initialize_episode(scenario), DispatchAction("Z1", "S1")
    ).state
    state = transition(scenario, state, WAIT).state
    assert [record.event_type for record in state.audit_log] == [
        AuditEventType.DISPATCH_CREATED,
        AuditEventType.ARRIVAL_PROCESSED,
        AuditEventType.WAIT,
        AuditEventType.EPISODE_TERMINATED,
    ]
    assert all(record.reason_code and record.message for record in state.audit_log)
