"""Pure deterministic state transitions for Sentinel-Agent V3 Phase 3.

One call represents one timestep and one action opportunity. Arrivals due at the current
timestep are processed before the chosen action. The Phase 3 exogenous-update position
is an explicit no-op: route and hazard state stay at their initial values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from .events import (
    ActionRejectionCode,
    AuditEventType,
    AuditRecord,
    DispatchAction,
    DispatchEvent,
    DispatchStatus,
    SimulationAction,
    WaitAction,
)
from .invariants import assert_episode_invariants
from .schemas import ScenarioV3, ShelterStatus
from .state import EpisodeState, RouteState, ShelterState, TerminalReason, ZoneState


@dataclass(frozen=True)
class ActionValidation:
    valid: bool
    rejection_code: ActionRejectionCode | None = None
    message: str | None = None
    route_id: str | None = None
    people: int = 0
    travel_lag_steps: int = 0


@dataclass(frozen=True)
class TransitionResult:
    state: EpisodeState
    action: SimulationAction | object
    accepted: bool
    previous_timestep: int
    new_timestep: int
    people_dispatched: int
    arrivals_processed: tuple[DispatchEvent, ...]
    events_created: tuple[DispatchEvent, ...]
    audit_records: tuple[AuditRecord, ...]
    rejection_code: ActionRejectionCode | None = None
    rejection_message: str | None = None

    @property
    def terminal(self) -> bool:
        return self.state.terminal

    @property
    def terminal_reason(self) -> TerminalReason | None:
        return self.state.terminal_reason

    def to_dict(self) -> dict[str, Any]:
        action_dict = (
            self.action.to_dict()
            if isinstance(self.action, (DispatchAction, WaitAction))
            else {"action_type": type(self.action).__name__}
        )
        return {
            "state": self.state.to_dict(),
            "action": action_dict,
            "accepted": self.accepted,
            "previous_timestep": self.previous_timestep,
            "new_timestep": self.new_timestep,
            "people_dispatched": self.people_dispatched,
            "arrivals_processed": [event.to_dict() for event in self.arrivals_processed],
            "events_created": [event.to_dict() for event in self.events_created],
            "audit_records": [record.to_dict() for record in self.audit_records],
            "rejection_code": self.rejection_code.value if self.rejection_code else None,
            "rejection_message": self.rejection_message,
            "terminal": self.terminal,
            "terminal_reason": (
                self.terminal_reason.value if self.terminal_reason else None
            ),
        }


def initialize_episode(scenario: ScenarioV3) -> EpisodeState:
    """Build a fresh runtime snapshot without changing the scenario definition."""
    state = EpisodeState(
        scenario_id=scenario.scenario_id,
        current_timestep=0,
        zones=tuple(
            ZoneState(
                zone_id=zone.zone_id,
                population_remaining=zone.population_initial_remaining,
                flood_severity_current=zone.initial_flood_severity,
            )
            for zone in scenario.canonical_zones
        ),
        shelters=tuple(
            ShelterState(
                shelter_id=shelter.shelter_id,
                capacity_total=shelter.capacity_total,
                occupancy_current=shelter.occupancy_initial,
                capacity_reserved=0,
                status_current=shelter.status,
                flood_severity_current=shelter.initial_flood_severity,
            )
            for shelter in scenario.canonical_shelters
        ),
        routes=tuple(
            RouteState(
                route_id=route.route_id,
                source_zone_id=route.source_zone_id,
                destination_shelter_id=route.destination_shelter_id,
                reachable_current=route.reachable,
                travel_time_current=route.travel_time_mean,
            )
            for route in scenario.canonical_routes
        ),
        dispatch_events=(),
        people_safely_arrived=0,
        initial_evacuation_population=sum(
            zone.population_initial_remaining for zone in scenario.zones
        ),
        dispatch_limit_per_timestep=min(
            scenario.fleet.vehicle_count, scenario.fleet.dispatches_per_timestep
        ),
        dispatches_used_this_timestep=0,
        next_dispatch_sequence=1,
        terminal=False,
        terminal_reason=None,
        audit_log=(),
    )
    assert_episode_invariants(scenario, state)
    return state


def _route_candidates(
    state: EpisodeState, zone_id: str, shelter_id: str
) -> tuple[RouteState, ...]:
    return tuple(
        route
        for route in state.routes
        if route.source_zone_id == zone_id
        and route.destination_shelter_id == shelter_id
    )


def validate_action(
    scenario: ScenarioV3, state: EpisodeState, action: SimulationAction | object
) -> ActionValidation:
    """Check Phase 3 mechanics only; no hazard or RAG safety rule is applied."""
    if state.terminal:
        return ActionValidation(
            False,
            ActionRejectionCode.EPISODE_TERMINAL,
            "episode is already terminal",
        )
    if isinstance(action, WaitAction):
        return ActionValidation(True)
    if not isinstance(action, DispatchAction):
        return ActionValidation(
            False,
            ActionRejectionCode.INVALID_ACTION_TYPE,
            "action must be DispatchAction or WaitAction",
        )

    zone = state.zone(action.zone_id)
    if zone is None:
        return ActionValidation(False, ActionRejectionCode.UNKNOWN_ZONE, "unknown zone")
    shelter = state.shelter(action.shelter_id)
    if shelter is None:
        return ActionValidation(
            False, ActionRejectionCode.UNKNOWN_SHELTER, "unknown shelter"
        )
    routes = _route_candidates(state, action.zone_id, action.shelter_id)
    if not routes:
        return ActionValidation(False, ActionRejectionCode.NO_ROUTE, "no route exists")
    if len(routes) > 1:
        return ActionValidation(
            False,
            ActionRejectionCode.AMBIGUOUS_ROUTE,
            "multiple routes exist for an action that does not select route_id",
        )
    route = routes[0]
    if not route.reachable_current:
        return ActionValidation(
            False, ActionRejectionCode.ROUTE_UNREACHABLE, "route is unreachable"
        )
    if (
        route.travel_time_current is None
        or not math.isfinite(route.travel_time_current)
        or route.travel_time_current <= 0
    ):
        return ActionValidation(
            False,
            ActionRejectionCode.INVALID_TRAVEL_TIME,
            "reachable route must have positive current travel time",
        )
    if zone.population_remaining <= 0:
        return ActionValidation(
            False, ActionRejectionCode.NO_POPULATION, "zone has no remaining population"
        )
    if shelter.status_current is ShelterStatus.CLOSED:
        return ActionValidation(
            False, ActionRejectionCode.SHELTER_CLOSED, "shelter is closed"
        )
    if shelter.capacity_available <= 0:
        return ActionValidation(
            False, ActionRejectionCode.NO_CAPACITY, "shelter has no available capacity"
        )
    if not scenario.fleet.evacuation_enabled:
        return ActionValidation(
            False,
            ActionRejectionCode.EVACUATION_DISABLED,
            "fleet evacuation is disabled",
        )
    if state.dispatches_used_this_timestep >= state.dispatch_limit_per_timestep:
        return ActionValidation(
            False,
            ActionRejectionCode.NO_DISPATCH_AVAILABILITY,
            "no dispatch opportunity remains this timestep",
        )

    people = min(
        scenario.fleet.vehicle_capacity,
        zone.population_remaining,
        shelter.capacity_available,
    )
    if people <= 0:
        return ActionValidation(
            False, ActionRejectionCode.NO_CAPACITY, "dispatch batch would be empty"
        )
    lag = max(
        1,
        math.ceil(route.travel_time_current / scenario.time.timestep_minutes),
    )
    return ActionValidation(
        True,
        route_id=route.route_id,
        people=people,
        travel_lag_steps=lag,
    )


def _process_arrivals(
    state: EpisodeState,
) -> tuple[EpisodeState, tuple[DispatchEvent, ...], tuple[AuditRecord, ...]]:
    due = tuple(
        event
        for event in state.dispatch_events
        if event.status is DispatchStatus.IN_TRANSIT
        and event.arrival_timestep == state.current_timestep
    )
    if not due:
        return state, (), ()

    arrived_due = tuple(replace(event, status=DispatchStatus.ARRIVED) for event in due)
    arrived_by_id = {event.event_id: event for event in arrived_due}
    events = tuple(
        arrived_by_id.get(event.event_id, event)
        for event in state.dispatch_events
    )
    shelters = []
    for shelter in state.shelters:
        arrived = sum(
            event.people
            for event in due
            if event.destination_shelter_id == shelter.shelter_id
        )
        shelters.append(
            replace(
                shelter,
                occupancy_current=shelter.occupancy_current + arrived,
                capacity_reserved=shelter.capacity_reserved - arrived,
            )
        )
    records = tuple(
        AuditRecord(
            event_type=AuditEventType.ARRIVAL_PROCESSED,
            timestep=state.current_timestep,
            event_id=event.event_id,
            zone_id=event.source_zone_id,
            shelter_id=event.destination_shelter_id,
            route_id=event.route_id,
            people=event.people,
            reason_code="SCHEDULED_ARRIVAL_DUE",
            message="reserved evacuees arrived and were recorded as safe",
        )
        for event in due
    )
    return (
        replace(
            state,
            shelters=tuple(shelters),
            dispatch_events=events,
            people_safely_arrived=state.people_safely_arrived
            + sum(event.people for event in due),
            audit_log=state.audit_log + records,
        ),
        arrived_due,
        records,
    )


def _rejected_result(
    state: EpisodeState,
    action: SimulationAction | object,
    validation: ActionValidation,
) -> TransitionResult:
    record = AuditRecord(
        event_type=AuditEventType.ACTION_REJECTED,
        timestep=state.current_timestep,
        zone_id=action.zone_id if isinstance(action, DispatchAction) else None,
        shelter_id=action.shelter_id if isinstance(action, DispatchAction) else None,
        reason_code=(
            validation.rejection_code.value if validation.rejection_code else None
        ),
        message=validation.message,
    )
    return TransitionResult(
        state=state,
        action=action,
        accepted=False,
        previous_timestep=state.current_timestep,
        new_timestep=state.current_timestep,
        people_dispatched=0,
        arrivals_processed=(),
        events_created=(),
        audit_records=(record,),
        rejection_code=validation.rejection_code,
        rejection_message=validation.message,
    )


def _execute_accepted_action(
    scenario: ScenarioV3,
    state: EpisodeState,
    action: SimulationAction,
    validation: ActionValidation,
    *,
    base_travel_time_minutes: float | None = None,
    realized_travel_time_minutes: float | None = None,
    travel_multiplier: float = 1.0,
    expected_travel_time_minutes: float | None = None,
    travel_uncertainty_minutes: float | None = None,
    uncertainty_config_id: str | None = None,
) -> tuple[EpisodeState, int, tuple[DispatchEvent, ...], tuple[AuditRecord, ...]]:
    """Execute an already validated action, optionally with realized stochastic travel."""
    if isinstance(action, WaitAction):
        record = AuditRecord(
            event_type=AuditEventType.WAIT,
            timestep=state.current_timestep,
            uncertainty_config_id=uncertainty_config_id,
            reason_code="WAIT_SELECTED",
            message="no dispatch was requested for this timestep",
        )
        return state, 0, (), (record,)

    zone = state.zone(action.zone_id)
    shelter = state.shelter(action.shelter_id)
    route = state.route(validation.route_id or "")
    assert zone is not None and shelter is not None and route is not None
    current_travel = route.travel_time_current
    if current_travel is None:
        raise ValueError("validated route has no current travel time")
    base_minutes = base_travel_time_minutes or route.base_travel_time_minutes or current_travel
    realized_minutes = realized_travel_time_minutes or current_travel
    lag = max(1, math.ceil(realized_minutes / scenario.time.timestep_minutes))
    people_dispatched = validation.people
    event = DispatchEvent(
        event_id=f"dispatch-{state.next_dispatch_sequence:06d}",
        source_zone_id=action.zone_id,
        destination_shelter_id=action.shelter_id,
        people=people_dispatched,
        departure_timestep=state.current_timestep,
        arrival_timestep=state.current_timestep + lag,
        route_id=route.route_id,
        travel_lag_steps=lag,
        base_travel_time_minutes=base_minutes,
        realized_travel_time_minutes=realized_minutes,
        travel_multiplier=travel_multiplier,
        uncertainty_config_id=uncertainty_config_id,
        status=DispatchStatus.IN_TRANSIT,
    )
    updated = replace(
        state,
        zones=tuple(
            replace(item, population_remaining=item.population_remaining - people_dispatched)
            if item.zone_id == action.zone_id
            else item
            for item in state.zones
        ),
        shelters=tuple(
            replace(item, capacity_reserved=item.capacity_reserved + people_dispatched)
            if item.shelter_id == action.shelter_id
            else item
            for item in state.shelters
        ),
        dispatch_events=state.dispatch_events + (event,),
        dispatches_used_this_timestep=1,
        next_dispatch_sequence=state.next_dispatch_sequence + 1,
    )
    records: list[AuditRecord] = []
    if uncertainty_config_id is not None:
        records.append(
            AuditRecord(
                event_type=AuditEventType.TRAVEL_TIME_REALIZED,
                timestep=state.current_timestep,
                event_id=event.event_id,
                zone_id=event.source_zone_id,
                shelter_id=event.destination_shelter_id,
                route_id=event.route_id,
                uncertainty_config_id=uncertainty_config_id,
                value_before=base_minutes,
                value_after=realized_minutes,
                expected_value=expected_travel_time_minutes,
                uncertainty=travel_uncertainty_minutes,
                reason_code="KEYED_ACTION_CONDITIONAL_TRAVEL",
                message="positive bounded travel time realized for accepted dispatch",
            )
        )
    records.append(
        AuditRecord(
            event_type=AuditEventType.DISPATCH_CREATED,
            timestep=state.current_timestep,
            event_id=event.event_id,
            zone_id=event.source_zone_id,
            shelter_id=event.destination_shelter_id,
            route_id=event.route_id,
            people=event.people,
            uncertainty_config_id=uncertainty_config_id,
            reason_code="DISPATCH_ACCEPTED",
            message="capacity reserved and evacuees entered transit",
        )
    )
    return updated, people_dispatched, (event,), tuple(records)


def _finalize_accepted_transition(
    scenario: ScenarioV3,
    state: EpisodeState,
    action_records: tuple[AuditRecord, ...],
) -> tuple[EpisodeState, tuple[AuditRecord, ...]]:
    """Append action audit, increment time, and apply the frozen terminal rules."""
    state = replace(
        state,
        current_timestep=state.current_timestep + 1,
        audit_log=state.audit_log + action_records,
    )
    terminal_reason = None
    if state.population_remaining == 0 and state.people_in_transit == 0:
        failures = state.people_stranded + state.people_unsafe_arrival + state.people_overflow
        if state.is_v4 and failures:
            terminal_reason = (TerminalReason.MIXED_OUTCOME if state.people_safely_arrived
                               else TerminalReason.ALL_FAILED)
        else:
            terminal_reason = TerminalReason.ALL_EVACUATED
    elif state.current_timestep >= scenario.time.horizon_steps:
        terminal_reason = TerminalReason.HORIZON_REACHED

    termination_records: tuple[AuditRecord, ...] = ()
    if terminal_reason is not None:
        termination_records = (
            AuditRecord(
                event_type=AuditEventType.EPISODE_TERMINATED,
                timestep=state.current_timestep,
                uncertainty_config_id=state.uncertainty_config_id,
                reason_code=terminal_reason.value,
                message={
                    TerminalReason.ALL_EVACUATED: "all evacuees arrived safely",
                    TerminalReason.ALL_FAILED: "all groups resolved without safe arrivals",
                    TerminalReason.MIXED_OUTCOME: "all groups resolved with mixed safe and failed outcomes",
                    TerminalReason.HORIZON_REACHED: "configured timestep horizon reached",
                }[terminal_reason],
            ),
        )
        state = replace(
            state,
            terminal=True,
            terminal_reason=terminal_reason,
            audit_log=state.audit_log + termination_records,
        )
    return state, termination_records


def transition(
    scenario: ScenarioV3, state: EpisodeState, action: SimulationAction | object
) -> TransitionResult:
    """Apply one action transactionally and return a new immutable state snapshot."""
    assert_episode_invariants(scenario, state)
    if state.terminal:
        return _rejected_result(
            state,
            action,
            ActionValidation(
                False,
                ActionRejectionCode.EPISODE_TERMINAL,
                "episode is already terminal",
            ),
        )

    working, arrivals, arrival_records = _process_arrivals(state)
    # This position is reserved for deterministic route/hazard updates. Phase 3 is a
    # deliberate no-op, so the runtime values remain equal to their scenario initials.
    working = replace(working, dispatches_used_this_timestep=0)
    validation = validate_action(scenario, working, action)
    if not validation.valid:
        # Discard arrivals in the working snapshot: rejected calls are all-or-nothing.
        return _rejected_result(state, action, validation)

    working, people_dispatched, created, action_records = _execute_accepted_action(
        scenario, working, action, validation
    )
    working, termination_records = _finalize_accepted_transition(
        scenario, working, action_records
    )

    assert_episode_invariants(scenario, working)
    return TransitionResult(
        state=working,
        action=action,
        accepted=True,
        previous_timestep=state.current_timestep,
        new_timestep=working.current_timestep,
        people_dispatched=people_dispatched,
        arrivals_processed=arrivals,
        events_created=created,
        audit_records=arrival_records + action_records + termination_records,
    )


step = transition
