"""Phase 4 stochastic simulator orchestration with policy-safe observation views."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .configs import UncertaintyConfig, get_uncertainty_config
from .events import (
    AuditEventType,
    AuditRecord,
    DispatchAction,
    DispatchEvent,
    SimulationAction,
)
from .hazard import evolve_flood_state, update_observable_forecasts
from .invariants import assert_episode_invariants
from .randomness import EpisodeRandomStreams, RandomStream
from .routes import realize_dispatch_travel, update_route_state
from .schemas import ScenarioV3, ShelterStatus
from .state import EpisodeState
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


def _next_status(status: ShelterStatus) -> ShelterStatus:
    if status is ShelterStatus.OPEN:
        return ShelterStatus.RESTRICTED
    return ShelterStatus.CLOSED


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
        updated = previous
        severity = shelter.flood_severity_current
        trigger_code: str | None = None
        if previous is not ShelterStatus.CLOSED:
            degradation_probability = min(
                1.0, config.shelter_degradation_probability * severity
            )
            if severity >= config.closed_threshold:
                updated = ShelterStatus.CLOSED
                trigger_code = "SYNTHETIC_CLOSED_SEVERITY_THRESHOLD"
            elif severity >= config.restricted_threshold and previous is ShelterStatus.OPEN:
                updated = ShelterStatus.RESTRICTED
                trigger_code = "SYNTHETIC_RESTRICTED_SEVERITY_THRESHOLD"
            if (
                trigger_code is None
                and context.streams.uniform(
                    RandomStream.SHELTER_DEGRADATION,
                    timestep,
                    shelter.shelter_id,
                )
                < degradation_probability
                and updated is not ShelterStatus.CLOSED
            ):
                updated = _next_status(updated)
                trigger_code = "KEYED_SYNTHETIC_SHELTER_DEGRADATION"
        else:
            degradation_probability = 0.0

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
) -> tuple[
    EpisodeState,
    _StochasticContext,
    tuple[DispatchEvent, ...],
    tuple[AuditRecord, ...],
]:
    """Realize current exogenous state before a policy observes and selects an action."""
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

    state = update_observable_forecasts(scenario, state, context.config)
    state = replace(
        state,
        uncertainty_config_id=context.config.config_id,
        dispatches_used_this_timestep=0,
        audit_log=state.audit_log + exogenous_records,
    )
    return state, next_context, arrivals, arrival_records + exogenous_records


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
    ) -> None:
        self._scenario = scenario
        selected = get_uncertainty_config(config)
        self._context = _StochasticContext(
            streams=EpisodeRandomStreams(
                root_seed=scenario.seed,
                config_id=selected.config_id,
                replication_id=replication_id,
            ),
            config=selected,
        )
        base = replace(
            initialize_episode(scenario),
            uncertainty_config_id=selected.config_id,
        )
        prepared, next_context, arrivals, records = _prepare_timestep(
            scenario, base, self._context
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
                self._scenario, self.state, self._context
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

    def internal_debug_snapshot(self) -> dict[str, Any]:
        """Current latent metadata only; it contains no pre-generated future schedule."""
        _, current_context, _, _ = self._ensure_prepared()
        return {
            "root_seed": current_context.streams.root_seed,
            "replication_id": current_context.streams.replication_id,
            "config_id": current_context.config.config_id,
            "regional_hazard_state": current_context.regional_hazard_state,
        }

    def step(self, action: SimulationAction | object) -> TransitionResult:
        """Execute one action against the state last returned by ``observe()``."""
        if self.state.terminal:
            validation = validate_action(self._scenario, self.state, action)
            return _rejected_result(self.state, action, validation)

        prepared, next_context, arrivals, pre_action_records = self._ensure_prepared()
        validation = validate_action(self._scenario, prepared, action)
        if not validation.valid:
            return _rejected_result(self.state, action, validation)

        travel = None
        if isinstance(action, DispatchAction):
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

        working, people, created, action_records = _execute_accepted_action(
            self._scenario,
            prepared,
            action,
            validation,
            base_travel_time_minutes=travel.base_minutes if travel else None,
            realized_travel_time_minutes=travel.realized_minutes if travel else None,
            travel_multiplier=travel.multiplier if travel else 1.0,
            expected_travel_time_minutes=travel.expected_minutes if travel else None,
            travel_uncertainty_minutes=travel.uncertainty_minutes if travel else None,
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
