"""Phase 4 stochastic simulator orchestration with policy-safe observation views."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .configs import UncertaintyConfig, get_uncertainty_config
from .events import (
    AuditEventType,
    AuditRecord,
    DispatchAction,
    DispatchEvent,
    DispatchStatus,
    SimulationAction,
)
from .hazard import evolve_flood_state, update_observable_forecasts
from .invariants import assert_episode_invariants
from .randomness import EpisodeRandomStreams, RandomStream
from .routes import realize_dispatch_travel, update_route_state
from .schemas import ScenarioV3, ShelterStatus
from .state import EpisodeState
from .transit import (
    TransitPlan,
    apply_walk_ins,
    build_transit_plan,
    group_position,
    process_v4_transit,
    reroute_plan,
)
from .world import V4WorldConfig, get_world_config, scaled_uncertainty
from .transition import (
    TransitionResult,
    _execute_accepted_action,
    _finalize_accepted_transition,
    _process_arrivals,
    _rejected_result,
    initialize_episode,
    validate_action,
)


@dataclass(frozen=True)
class _StochasticContext:
    """Simulator-harness state; deliberately absent from policy/state serialization."""

    streams: EpisodeRandomStreams
    config: UncertaintyConfig
    regional_hazard_state: float = 0.0
    world: V4WorldConfig | None = None
    plans: tuple[TransitPlan, ...] = ()


def _next_status(status: ShelterStatus) -> ShelterStatus:
    if status is ShelterStatus.OPEN:
        return ShelterStatus.RESTRICTED
    return ShelterStatus.CLOSED


def degrade_shelter_status(
    previous: ShelterStatus,
    severity: float,
    config: UncertaintyConfig,
    streams: Any,
    timestep: int,
    shelter_id: str,
) -> tuple[ShelterStatus, str | None, float]:
    """Pure shelter-status step: (new status, trigger code, degradation probability)."""
    if previous is ShelterStatus.CLOSED:
        return previous, None, 0.0
    updated = previous
    trigger_code: str | None = None
    probability = min(1.0, config.shelter_degradation_probability * severity)
    if severity >= config.closed_threshold:
        updated = ShelterStatus.CLOSED
        trigger_code = "SYNTHETIC_CLOSED_SEVERITY_THRESHOLD"
    elif severity >= config.restricted_threshold and previous is ShelterStatus.OPEN:
        updated = ShelterStatus.RESTRICTED
        trigger_code = "SYNTHETIC_RESTRICTED_SEVERITY_THRESHOLD"
    if (
        trigger_code is None
        and streams.uniform(RandomStream.SHELTER_DEGRADATION, timestep, shelter_id)
        < probability
        and updated is not ShelterStatus.CLOSED
    ):
        updated = _next_status(updated)
        trigger_code = "KEYED_SYNTHETIC_SHELTER_DEGRADATION"
    return updated, trigger_code, probability


def _degrade_shelters(
    state: EpisodeState,
    context: _StochasticContext,
) -> tuple[EpisodeState, tuple[AuditRecord, ...]]:
    config = context.config
    timestep = state.current_timestep
    shelters = []
    records: list[AuditRecord] = []
    for shelter in state.shelters:
        previous = shelter.status_current
        severity = shelter.flood_severity_current
        updated, trigger_code, degradation_probability = degrade_shelter_status(
            previous, severity, config, context.streams, timestep, shelter.shelter_id
        )
        shelters.append(replace(shelter, status_current=updated))
        if updated is not previous:
            event_type = (
                AuditEventType.SHELTER_CLOSED
                if updated is ShelterStatus.CLOSED
                else AuditEventType.SHELTER_RESTRICTED
            )
            records.append(
                AuditRecord(
                    event_type=event_type,
                    timestep=timestep,
                    shelter_id=shelter.shelter_id,
                    uncertainty_config_id=config.config_id,
                    value_before=severity,
                    value_after=severity,
                    probability=degradation_probability,
                    reason_code=trigger_code,
                    message=f"shelter status degraded from {previous.value} to {updated.value}",
                )
            )
    return replace(state, shelters=tuple(shelters)), tuple(records)


def _prepare_timestep(
    scenario: ScenarioV3,
    committed_state: EpisodeState,
    context: _StochasticContext,
    intervention: Callable[
        [ScenarioV3, EpisodeState], tuple[EpisodeState, tuple[AuditRecord, ...]]
    ]
    | None = None,
) -> tuple[
    EpisodeState,
    _StochasticContext,
    tuple[DispatchEvent, ...],
    tuple[AuditRecord, ...],
]:
    """Realize current exogenous state before a policy observes and selects an action."""
    if context.world is not None:
        return _prepare_v4_timestep(scenario, committed_state, context, intervention)
    state, arrivals, arrival_records = _process_arrivals(committed_state)
    exogenous_records: tuple[AuditRecord, ...] = ()
    next_context = context
    if state.current_timestep > 0:
        state, regional, flood_records = evolve_flood_state(
            scenario,
            state,
            context.config,
            context.streams,
            context.regional_hazard_state,
        )
        next_context = replace(context, regional_hazard_state=regional)
        exogenous_records += flood_records

    state, route_records = update_route_state(
        scenario,
        state,
        context.config,
        context.streams,
        realize_closures=state.current_timestep > 0,
    )
    exogenous_records += route_records
    if state.current_timestep > 0:
        state, shelter_records = _degrade_shelters(state, next_context)
        exogenous_records += shelter_records

    if intervention is not None:
        state, intervention_records = intervention(scenario, state)
        exogenous_records += intervention_records

    state = update_observable_forecasts(scenario, state, context.config)
    state = replace(
        state,
        uncertainty_config_id=context.config.config_id,
        dispatches_used_this_timestep=0,
        audit_log=state.audit_log + exogenous_records,
    )
    return state, next_context, arrivals, arrival_records + exogenous_records


def _prepare_v4_timestep(
    scenario: ScenarioV3,
    committed_state: EpisodeState,
    context: _StochasticContext,
    intervention: Callable[
        [ScenarioV3, EpisodeState], tuple[EpisodeState, tuple[AuditRecord, ...]]
    ]
    | None,
):
    """v4 order: hazards, shelters, edge closures, then transit (stranding sees this step's roads)."""
    world = context.world
    assert world is not None
    state = committed_state
    exogenous_records: tuple[AuditRecord, ...] = ()
    next_context = context
    if state.current_timestep > 0:
        state, regional, flood_records = evolve_flood_state(
            scenario, state, context.config, context.streams, context.regional_hazard_state
        )
        next_context = replace(context, regional_hazard_state=regional)
        exogenous_records += flood_records
    # Edge closures are authoritative in v4: never realize route-level closures.
    state, route_records = update_route_state(
        scenario, state, context.config, context.streams, realize_closures=False
    )
    exogenous_records += route_records
    if state.current_timestep > 0:
        state, shelter_records = _degrade_shelters(state, next_context)
        exogenous_records += shelter_records
    if intervention is not None:
        state, intervention_records = intervention(scenario, state)
        exogenous_records += intervention_records
    state = replace(state, audit_log=state.audit_log + exogenous_records)
    road_state = getattr(intervention, "road_state", None)
    arrivals: tuple[DispatchEvent, ...] = ()
    transit_records: tuple[AuditRecord, ...] = ()
    if world.enable_transit_failures:
        state, arrivals, transit_records = process_v4_transit(
            state, next_context.plans, road_state, context.config, world
        )
    walk_records: tuple[AuditRecord, ...] = ()
    if state.current_timestep > 0:
        state, walk_records = apply_walk_ins(state, context.streams, world)
    state = update_observable_forecasts(scenario, state, context.config)
    state = replace(
        state,
        uncertainty_config_id=context.config.config_id,
        dispatches_used_this_timestep=0,
    )
    return (
        state,
        next_context,
        arrivals,
        exogenous_records + transit_records + walk_records,
    )


class StochasticSimulator:
    """Two-stage observe/step harness that prevents policy access to future draws.

    ``observe()`` prepares arrivals and current exogenous state, then returns a detached
    policy-facing dictionary. ``step(action)`` executes against exactly that prepared
    state. The keyed context is retained only by this harness and is never included in
    the observation or serialized ``TransitionResult``.
    """

    def __init__(
        self,
        scenario: ScenarioV3,
        config: str | UncertaintyConfig,
        *,
        replication_id: int = 0,
        intervention: Callable[
            [ScenarioV3, EpisodeState], tuple[EpisodeState, tuple[AuditRecord, ...]]
        ]
        | None = None,
        world: V4WorldConfig | str | None = None,
    ) -> None:
        self._scenario = scenario
        selected = get_uncertainty_config(config)
        selected_world = get_world_config(world) if world is not None else None
        self._context = _StochasticContext(
            streams=EpisodeRandomStreams(
                root_seed=scenario.seed,
                config_id=selected.config_id,
                replication_id=replication_id,
            ),
            config=selected,
            world=selected_world,
        )
        self._intervention = intervention
        base = replace(
            initialize_episode(scenario),
            uncertainty_config_id=selected.config_id,
        )
        prepared, next_context, arrivals, records = _prepare_timestep(
            scenario, base, self._context, self._intervention
        )
        self.state = prepared
        self._context = next_context
        self._prepared = (prepared, next_context, arrivals, records)
        assert_episode_invariants(self._scenario, self.state)

    @property
    def config(self) -> UncertaintyConfig:
        return self._context.config

    @property
    def replication_id(self) -> int:
        return self._context.streams.replication_id

    def _ensure_prepared(self):
        if self._prepared is None:
            self._prepared = _prepare_timestep(
                self._scenario, self.state, self._context, self._intervention
            )
        return self._prepared

    def observe(self) -> dict[str, Any]:
        """Return current realized state plus t+1 forecasts, never future draws."""
        prepared, _, _, _ = self._ensure_prepared()
        return prepared.to_policy_observation()

    def prepared_state_for_debug(self) -> EpisodeState:
        """Current decision state for simulator diagnostics, not a policy API."""
        prepared, _, _, _ = self._ensure_prepared()
        return prepared

    def transit_plans(self) -> Mapping[str, TransitPlan]:
        """Read-only view of v4 transit plans by event id (``{}`` for v3 worlds)."""
        return MappingProxyType({p.event_id: p for p in self._context.plans})

    def _append_audit(self, record: AuditRecord, state: EpisodeState | None = None) -> None:
        prepared, ctx, arrivals, records = self._ensure_prepared()
        base = prepared if state is None else state
        base = replace(base, audit_log=base.audit_log + (record,))
        assert_episode_invariants(self._scenario, base)
        self._prepared = (base, ctx, arrivals, records + (record,))
        self.state = base if self.state is prepared else self.state

    def record_no_alternative(self, event_id: str) -> None:
        """Audit a certified failure with no certified alternative (v4 re-certification)."""
        prepared, _, _, _ = self._ensure_prepared()
        event = next(e for e in prepared.dispatch_events if e.event_id == event_id)
        self._append_audit(AuditRecord(
            event_type=AuditEventType.MIGRATION_NO_CERTIFIED_ALTERNATIVE,
            timestep=prepared.current_timestep, event_id=event_id, zone_id=event.source_zone_id,
            shelter_id=event.destination_shelter_id, people=event.people,
            reason_code="NO_CERTIFIED_ALTERNATIVE",
            message="remaining trip is certified infeasible and no alternative is certified; group kept",
        ))

    def migrate(self, event_id: str, new_shelter_id: str, new_edge_ids: tuple[str, ...]) -> None:
        """Re-route an in-transit group (v4 only; called by the certified gate inside its transaction)."""
        prepared, ctx, arrivals, records = self._ensure_prepared()
        if ctx.world is None:
            raise ValueError("migration exists only in v4 worlds")
        overlay = self._intervention
        t = prepared.current_timestep
        dt = ctx.world.timestep_minutes
        event = next((e for e in prepared.dispatch_events
                      if e.event_id == event_id and e.status is DispatchStatus.IN_TRANSIT), None)
        plan = next((p for p in ctx.plans if p.event_id == event_id), None)
        if event is None or plan is None:
            raise ValueError(f"{event_id} is not an in-transit group")
        new_shelter = prepared.shelter(new_shelter_id)
        if new_shelter is None or new_shelter_id == event.destination_shelter_id:
            raise ValueError("migration needs a different, known shelter")
        if new_shelter.status_current is ShelterStatus.CLOSED:
            raise ValueError("cannot migrate to a closed shelter")
        if new_shelter.capacity_available < event.people:
            raise ValueError("cannot migrate: the new shelter lacks seats")
        route = next((r for r in prepared.routes if r.source_zone_id == event.source_zone_id
                      and r.destination_shelter_id == new_shelter_id), None)
        if route is None:
            raise ValueError("no route record for the migration target")
        position = group_position(plan, overlay.graph, t * dt)
        new_plan = reroute_plan(plan, position, new_shelter_id, tuple(new_edge_ids),
                                overlay.road_state, overlay.graph, ctx.world, ctx.config,
                                ctx.streams, t)
        arrival = new_plan.arrival_timestep
        lag = arrival - event.departure_timestep
        realized = max(new_plan.arrival_minutes - event.departure_timestep * dt, (lag - 1) * dt + 1e-6)
        updated = replace(
            event, destination_shelter_id=new_shelter_id, arrival_timestep=arrival,
            travel_lag_steps=lag, realized_travel_time_minutes=realized, route_id=route.route_id,
        )
        shelters = tuple(
            replace(s, capacity_reserved=s.capacity_reserved - event.people)
            if s.shelter_id == event.destination_shelter_id
            else replace(s, capacity_reserved=s.capacity_reserved + event.people)
            if s.shelter_id == new_shelter_id else s
            for s in prepared.shelters
        )
        record = AuditRecord(
            event_type=AuditEventType.GROUP_MIGRATED, timestep=t, event_id=event_id,
            zone_id=event.source_zone_id, shelter_id=new_shelter_id, people=event.people,
            reason_code="CERTIFIED_MIGRATION",
            message=f"re-routed from {event.destination_shelter_id} to {new_shelter_id}",
        )
        working = replace(
            prepared,
            dispatch_events=tuple(updated if e.event_id == event_id else e for e in prepared.dispatch_events),
            shelters=shelters, audit_log=prepared.audit_log + (record,),
        )
        assert_episode_invariants(self._scenario, working)
        new_ctx = replace(ctx, plans=tuple(new_plan if p.event_id == event_id else p for p in ctx.plans))
        self._prepared = (working, new_ctx, arrivals, records + (record,))
        if self.state is prepared:
            self.state = working

    def internal_debug_snapshot(self) -> dict[str, Any]:
        """Current latent metadata only; it contains no pre-generated future schedule."""
        _, current_context, _, _ = self._ensure_prepared()
        return {
            "root_seed": current_context.streams.root_seed,
            "replication_id": current_context.streams.replication_id,
            "config_id": current_context.config.config_id,
            "regional_hazard_state": current_context.regional_hazard_state,
        }

    def _plan_v4_dispatch(self, prepared, action, validation, context):
        from src.geospatial.road_network import shortest_valid_path

        overlay = self._intervention
        graph, road_state = overlay.graph, overlay.road_state
        path = shortest_valid_path(
            graph,
            road_state,
            graph.zone_node_map[action.zone_id],
            graph.shelter_node_map[action.shelter_id],
        )
        if not path.reachable:  # validate_action saw the same road state; defensive only
            raise ValueError("validated v4 dispatch has no open path")
        return build_transit_plan(
            graph=graph,
            road_state=road_state,
            path_edge_ids=path.edge_ids,
            event_id=f"dispatch-{prepared.next_dispatch_sequence:06d}",
            zone_id=action.zone_id,
            shelter_id=action.shelter_id,
            people=validation.people,
            departure_timestep=prepared.current_timestep,
            world=context.world,
            config=context.config,
            streams=context.streams,
        )

    def step(self, action: SimulationAction | object) -> TransitionResult:
        """Execute one action against the state last returned by ``observe()``."""
        if self.state.terminal:
            validation = validate_action(self._scenario, self.state, action)
            return _rejected_result(self.state, action, validation)

        prepared, next_context, arrivals, pre_action_records = self._ensure_prepared()
        validation = validate_action(self._scenario, prepared, action)
        if not validation.valid:
            return _rejected_result(self.state, action, validation)

        travel_kwargs: dict[str, Any] = {}
        if isinstance(action, DispatchAction):
            if next_context.world is not None:
                realization = self._plan_v4_dispatch(prepared, action, validation, next_context)
                next_context = replace(
                    next_context, plans=next_context.plans + (realization.plan,)
                )
                travel_kwargs = dict(
                    base_travel_time_minutes=realization.base_minutes,
                    realized_travel_time_minutes=realization.realized_minutes,
                    travel_multiplier=realization.multiplier,
                    expected_travel_time_minutes=realization.base_minutes,
                    travel_uncertainty_minutes=0.0,
                )
            else:
                route_state = prepared.route(validation.route_id or "")
                route_definition = next(
                    route
                    for route in self._scenario.network.routes
                    if route.route_id == validation.route_id
                )
                assert route_state is not None
                travel = realize_dispatch_travel(
                    route_definition,
                    route_state,
                    next_context.config,
                    next_context.streams,
                    departure_timestep=prepared.current_timestep,
                    event_id=f"dispatch-{prepared.next_dispatch_sequence:06d}",
                )
                travel_kwargs = dict(
                    base_travel_time_minutes=travel.base_minutes,
                    realized_travel_time_minutes=travel.realized_minutes,
                    travel_multiplier=travel.multiplier,
                    expected_travel_time_minutes=travel.expected_minutes,
                    travel_uncertainty_minutes=travel.uncertainty_minutes,
                )

        working, people, created, action_records = _execute_accepted_action(
            self._scenario,
            prepared,
            action,
            validation,
            **travel_kwargs,
            uncertainty_config_id=next_context.config.config_id,
        )
        working, termination_records = _finalize_accepted_transition(
            self._scenario, working, action_records
        )
        assert_episode_invariants(self._scenario, working)
        result = TransitionResult(
            state=working,
            action=action,
            accepted=True,
            previous_timestep=prepared.current_timestep,
            new_timestep=working.current_timestep,
            people_dispatched=people,
            arrivals_processed=arrivals,
            events_created=created,
            audit_records=pre_action_records + action_records + termination_records,
        )
        self.state = working
        self._context = next_context
        self._prepared = None
        return result
