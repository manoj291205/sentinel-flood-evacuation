"""Phase 4 tests for stochastic dynamics, pairing, forecasts, and leakage."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from src.sim.configs import (
    HIGH,
    LOW,
    MEDIUM,
    MODELING_ASSUMPTION_DISCLAIMER,
    UNCERTAINTY_CONFIGS,
    UncertaintyConfig,
    UncertaintyLevel,
    get_uncertainty_config,
)
from src.sim.events import (
    WAIT,
    ActionRejectionCode,
    AuditEventType,
    DispatchAction,
    DispatchStatus,
)
from src.sim.hazard import evolve_flood_state, update_observable_forecasts
from src.sim.invariants import assert_episode_invariants
from src.sim.randomness import EpisodeRandomStreams, RandomStream
from src.sim.routes import (
    modeled_closure_probability,
    realize_dispatch_travel,
)
from src.sim.schemas import (
    ScenarioV3,
    ShelterStatus,
    StochasticModelConfig,
    StochasticParameterStatus,
    Trend,
    load_v3_scenario,
)
from src.sim.stochastic import StochasticSimulator
from src.sim.transition import initialize_episode

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "scenarios_v3" / "example_v3_scenario.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(EXAMPLE.read_text())


@pytest.fixture
def scenario() -> ScenarioV3:
    return load_v3_scenario(EXAMPLE)


def _run(scenario: ScenarioV3, config=MEDIUM, steps: int = 8):
    simulator = StochasticSimulator(scenario, config)
    results = []
    for timestep in range(steps):
        simulator.observe()
        action = DispatchAction("Z1", "S1") if timestep == 0 else WAIT
        result = simulator.step(action)
        results.append(result.to_dict())
        if result.terminal:
            break
    return simulator.state.to_dict(), results


def _forced_closure_config(**changes) -> UncertaintyConfig:
    defaults = {
        "config_id": "test-forced-closure-v1",
        "base_closure_multiplier": 20.0,
        "hazard_to_closure_strength": 0.0,
        "maximum_closure_probability": 1.0,
    }
    defaults.update(changes)
    return replace(MEDIUM, **defaults)


def _forced_shelter_config(*, close: bool) -> UncertaintyConfig:
    return replace(
        MEDIUM,
        config_id=f"test-forced-shelter-{'closed' if close else 'restricted'}-v1",
        restricted_threshold=0.0,
        closed_threshold=0.01 if close else 1.0,
        shelter_degradation_probability=0.0,
        base_closure_multiplier=0.0,
        hazard_to_closure_strength=0.0,
    )


def _hazard_signature(observation: dict) -> tuple:
    return (
        tuple((item["zone_id"], item["flood_severity_current"]) for item in observation["zones"]),
        tuple(
            (item["shelter_id"], item["flood_severity_current"], item["status_current"])
            for item in observation["shelters"]
        ),
        tuple(
            (
                item["route_id"],
                item["reachable_current"],
                item["estimated_closure_probability"],
            )
            for item in observation["routes"]
        ),
    )


def test_phase3_arrival_timing_regression_is_pre_step_two(scenario):
    from src.sim.transition import transition

    state = initialize_episode(scenario)
    state = transition(scenario, state, DispatchAction("Z1", "S1")).state
    event = state.pending_arrivals[0]
    state = transition(scenario, state, WAIT).state
    assert event.arrival_timestep == state.current_timestep == 2
    result = transition(scenario, state, WAIT)
    assert result.previous_timestep == 2
    assert result.audit_records[0].event_type is AuditEventType.ARRIVAL_PROCESSED
    assert result.new_timestep == 3


@pytest.mark.parametrize("config", [LOW, MEDIUM, HIGH])
def test_frozen_configs_validate_and_are_versioned(config):
    assert config.config_id == f"v3-{config.level.value.lower()}-v1"
    assert config.version == 1
    assert config.disclaimer == MODELING_ASSUMPTION_DISCLAIMER
    assert get_uncertainty_config(config.config_id) is config


def test_all_uncertainty_levels_are_present():
    assert {config.level for config in UNCERTAINTY_CONFIGS.values()} == set(
        UncertaintyLevel
    )


@pytest.mark.parametrize("config", [LOW, MEDIUM, HIGH])
def test_config_values_fit_phase2_stochastic_schema(config):
    validated = StochasticModelConfig(
        parameter_status=StochasticParameterStatus.CONFIGURED,
        regional_shock_std=config.regional_hazard_sigma,
        local_noise_std=config.local_hazard_sigma,
        shock_persistence=config.regional_hazard_persistence,
        travel_noise_std=config.travel_noise_fraction,
        closure_hazard_coefficient=config.hazard_to_closure_strength,
        shelter_degradation_probability=config.shelter_degradation_probability,
    )
    assert validated.parameter_status is StochasticParameterStatus.CONFIGURED


@pytest.mark.parametrize("root_seed", [-1, True, 1.5])
def test_invalid_root_seed_rejected(root_seed):
    with pytest.raises(ValueError, match="root_seed"):
        EpisodeRandomStreams(root_seed, MEDIUM.config_id)  # type: ignore[arg-type]


def test_same_keyed_stream_value_is_exactly_reproducible():
    left = EpisodeRandomStreams(123, MEDIUM.config_id, 4)
    right = EpisodeRandomStreams(123, MEDIUM.config_id, 4)
    assert left.normal(RandomStream.LOCAL_HAZARD, 3, "zone", "Z1") == right.normal(
        RandomStream.LOCAL_HAZARD, 3, "zone", "Z1"
    )
    assert left.uniform(RandomStream.ROUTE_CLOSURE, 5, "R1") == right.uniform(
        RandomStream.ROUTE_CLOSURE, 5, "R1"
    )


def test_different_seed_changes_a_rich_stochastic_episode(scenario):
    other = replace(scenario, seed=scenario.seed + 1)
    assert _run(scenario) != _run(other)


def test_same_seed_config_and_actions_replay_exactly(scenario):
    assert _run(scenario) == _run(scenario)


def test_unrelated_travel_queries_do_not_shift_flood_values():
    streams = EpisodeRandomStreams(99, MEDIUM.config_id)
    expected = streams.normal(RandomStream.REGIONAL_HAZARD, 4)
    for index in range(20):
        streams.normal(RandomStream.TRAVEL, 4, "R1", f"dispatch-{index:06d}")
    assert streams.normal(RandomStream.REGIONAL_HAZARD, 4) == expected


def test_stream_namespaces_are_independent():
    streams = EpisodeRandomStreams(99, MEDIUM.config_id)
    key = (2, "same-entity")
    values = {
        streams.normal(stream, *key)
        for stream in (
            RandomStream.REGIONAL_HAZARD,
            RandomStream.LOCAL_HAZARD,
            RandomStream.TRAVEL,
        )
    }
    assert len(values) == 3


def test_t0_observation_preserves_initial_severity(scenario):
    observation = StochasticSimulator(scenario, MEDIUM).observe()
    initial = {zone.zone_id: zone.initial_flood_severity for zone in scenario.zones}
    assert {
        zone["zone_id"]: zone["flood_severity_current"]
        for zone in observation["zones"]
    } == initial


def test_t0_has_no_route_or_shelter_stochastic_transition(scenario):
    observation = StochasticSimulator(
        scenario,
        _forced_closure_config(
            restricted_threshold=0.0,
            closed_threshold=0.01,
        ),
    ).observe()
    initial_routes = {route.route_id: route.reachable for route in scenario.network.routes}
    initial_statuses = {
        shelter.shelter_id: shelter.status.value for shelter in scenario.shelters
    }
    assert {
        route["route_id"]: route["reachable_current"]
        for route in observation["routes"]
    } == initial_routes
    assert {
        shelter["shelter_id"]: shelter["status_current"]
        for shelter in observation["shelters"]
    } == initial_statuses


def test_stochastic_evolution_starts_at_t1(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    initial = _hazard_signature(simulator.observe())
    simulator.step(WAIT)
    updated = _hazard_signature(simulator.observe())
    assert initial != updated
    assert simulator.prepared_state_for_debug().current_timestep == 1


@pytest.mark.parametrize("config", [LOW, MEDIUM, HIGH])
def test_severity_and_forecasts_remain_bounded(scenario, config):
    simulator = StochasticSimulator(scenario, config)
    for _ in range(scenario.time.horizon_steps):
        observation = simulator.observe()
        for entity in observation["zones"] + observation["shelters"]:
            assert 0 <= entity["flood_severity_current"] <= 1
            assert 0 <= entity["forecast_mean_next"] <= 1
            assert entity["forecast_std_next"] >= 0
        result = simulator.step(WAIT)
        if result.terminal:
            break


def test_regional_component_moves_zones_together(raw):
    for zone in raw["zones"]:
        zone["initial_severity_trend"] = Trend.STEADY.value
    scenario = ScenarioV3.from_dict(raw)
    config = replace(
        MEDIUM,
        config_id="test-regional-only-v1",
        local_hazard_sigma=0.0,
        hazard_drift_scale=0.0,
    )
    state = replace(initialize_episode(scenario), current_timestep=1)
    evolved, _, _ = evolve_flood_state(
        scenario,
        state,
        config,
        EpisodeRandomStreams(scenario.seed, config.config_id),
        0.0,
    )
    changes = [zone.observed_severity_change for zone in evolved.zones]
    assert changes[0] == pytest.approx(changes[1])
    assert changes[0] != 0


def test_local_noise_differentiates_zones(raw):
    for zone in raw["zones"]:
        zone["initial_flood_severity"] = 0.5
        zone["initial_severity_trend"] = Trend.STEADY.value
    scenario = ScenarioV3.from_dict(raw)
    config = replace(
        MEDIUM,
        config_id="test-local-only-v1",
        regional_hazard_sigma=0.0,
        regional_hazard_persistence=0.0,
        hazard_drift_scale=0.0,
    )
    state = replace(initialize_episode(scenario), current_timestep=1)
    evolved, _, _ = evolve_flood_state(
        scenario,
        state,
        config,
        EpisodeRandomStreams(scenario.seed, config.config_id),
        0.0,
    )
    assert evolved.zones[0].flood_severity_current != evolved.zones[1].flood_severity_current


def test_forecast_exists_before_first_action(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    observation = simulator.observe()
    assert observation["forecast_for_timestep"] == 1
    assert all(zone["forecast_mean_next"] is not None for zone in observation["zones"])


def test_forecast_is_imperfect_and_not_next_realization(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    forecast = {
        zone["zone_id"]: zone["forecast_mean_next"]
        for zone in simulator.observe()["zones"]
    }
    simulator.step(WAIT)
    realized = {
        zone["zone_id"]: zone["flood_severity_current"]
        for zone in simulator.observe()["zones"]
    }
    assert any(forecast[key] != realized[key] for key in forecast)


def test_forecast_function_has_no_random_stream_input(scenario):
    state = initialize_episode(scenario)
    left = update_observable_forecasts(scenario, state, MEDIUM)
    right = update_observable_forecasts(scenario, state, MEDIUM)
    assert left == right


def test_policy_observation_omits_internal_and_future_randomness(scenario):
    observation = StochasticSimulator(scenario, MEDIUM).observe()
    encoded = json.dumps(observation, sort_keys=True).lower()
    for forbidden in (
        "root_seed",
        "regional_hazard_state",
        "future_draw",
        "closure_draw",
        "realized_travel",
        "shelter_degradation_draw",
    ):
        assert forbidden not in encoded


def test_internal_context_is_separate_from_policy_observation(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    assert "root_seed" in simulator.internal_debug_snapshot()
    assert "root_seed" not in simulator.observe()


def test_policy_observation_is_a_detached_copy(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    observation = simulator.observe()
    observation["zones"][0]["flood_severity_current"] = -999
    assert simulator.observe()["zones"][0]["flood_severity_current"] >= 0


def test_realized_travel_is_positive_and_uses_current_hazard(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    observation = simulator.observe()
    route = next(item for item in observation["routes"] if item["route_id"] == "R-Z1-S1")
    result = simulator.step(DispatchAction("Z1", "S1"))
    event = result.events_created[0]
    assert event.realized_travel_time_minutes > 0
    assert route["route_hazard_proxy"] == 0.68
    assert route["expected_travel_time_minutes"] > event.base_travel_time_minutes


def test_stochastic_lag_uses_ceil_of_realized_travel(scenario):
    result = StochasticSimulator(scenario, MEDIUM).step(DispatchAction("Z1", "S1"))
    event = result.events_created[0]
    expected = max(
        1,
        math.ceil(event.realized_travel_time_minutes / scenario.time.timestep_minutes),
    )
    assert event.travel_lag_steps == expected
    assert event.arrival_timestep == event.departure_timestep + expected


def test_same_dispatch_key_reproduces_travel_realization(scenario):
    left = StochasticSimulator(scenario, MEDIUM).step(DispatchAction("Z1", "S1"))
    right = StochasticSimulator(scenario, MEDIUM).step(DispatchAction("Z1", "S1"))
    assert (
        left.events_created[0].realized_travel_time_minutes
        == right.events_created[0].realized_travel_time_minutes
    )


def test_expected_travel_does_not_reveal_exact_realization(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    expected = next(
        route["expected_travel_time_minutes"]
        for route in simulator.observe()["routes"]
        if route["route_id"] == "R-Z1-S1"
    )
    realized = simulator.step(DispatchAction("Z1", "S1")).events_created[
        0
    ].realized_travel_time_minutes
    assert expected != realized


def test_closure_probability_is_bounded_and_monotonic(scenario):
    route = next(item for item in scenario.network.routes if item.route_id == "R-Z1-S1")
    low_hazard = modeled_closure_probability(route, 0.1, MEDIUM)
    high_hazard = modeled_closure_probability(route, 0.9, MEDIUM)
    assert 0 <= low_hazard <= high_hazard <= 1


def test_route_closure_audit_has_probability_hazard_and_config(scenario):
    config = _forced_closure_config()
    simulator = StochasticSimulator(scenario, config)
    simulator.step(WAIT)
    simulator.observe()
    result = simulator.step(WAIT)
    record = next(
        item for item in result.audit_records if item.event_type is AuditEventType.ROUTE_CLOSED
    )
    assert record.probability == 1.0
    assert record.hazard_proxy is not None
    assert record.uncertainty_config_id == config.config_id


def test_forced_route_closure_blocks_new_dispatch_and_is_absorbing(scenario):
    simulator = StochasticSimulator(scenario, _forced_closure_config())
    simulator.step(WAIT)
    observation = simulator.observe()
    route = next(item for item in observation["routes"] if item["route_id"] == "R-Z1-S1")
    assert not route["reachable_current"]
    rejected = simulator.step(DispatchAction("Z1", "S1"))
    assert rejected.rejection_code is ActionRejectionCode.ROUTE_UNREACHABLE
    committed = simulator.step(WAIT)
    assert committed.accepted
    for _ in range(3):
        simulator.observe()
        simulator.step(WAIT)
        route_state = simulator.state.route("R-Z1-S1")
        assert route_state is not None and not route_state.reachable_current


def test_existing_in_transit_dispatch_survives_later_route_closure(scenario):
    simulator = StochasticSimulator(scenario, _forced_closure_config())
    dispatched = simulator.step(DispatchAction("Z1", "S1"))
    event = dispatched.events_created[0]
    simulator.observe()
    closed_route = simulator.prepared_state_for_debug().route(event.route_id)
    assert closed_route is not None and not closed_route.reachable_current
    while not simulator.state.terminal and simulator.state.people_safely_arrived == 0:
        simulator.step(WAIT)
        if not simulator.state.terminal:
            simulator.observe()
    arrived = next(
        item
        for item in simulator.state.dispatch_events
        if item.event_id == event.event_id
    )
    assert arrived.status is DispatchStatus.ARRIVED
    assert simulator.state.people_safely_arrived == event.people


def test_closure_key_is_policy_independent():
    left = EpisodeRandomStreams(44, MEDIUM.config_id)
    right = EpisodeRandomStreams(44, MEDIUM.config_id)
    for timestep in range(1, 8):
        assert left.uniform(RandomStream.ROUTE_CLOSURE, timestep, "R1") == right.uniform(
            RandomStream.ROUTE_CLOSURE, timestep, "R1"
        )


def test_open_shelter_can_degrade_to_restricted(scenario):
    simulator = StochasticSimulator(scenario, _forced_shelter_config(close=False))
    simulator.step(WAIT)
    observation = simulator.observe()
    shelter = next(item for item in observation["shelters"] if item["shelter_id"] == "S1")
    assert shelter["status_current"] == ShelterStatus.RESTRICTED.value


def test_restricted_shelter_remains_mechanically_usable_at_t0(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    result = simulator.step(DispatchAction("Z1", "S2"))
    assert result.accepted


def test_closed_shelter_blocks_new_dispatch_and_never_reopens(scenario):
    simulator = StochasticSimulator(scenario, _forced_shelter_config(close=True))
    simulator.step(WAIT)
    simulator.observe()
    closed_shelter = simulator.prepared_state_for_debug().shelter("S1")
    assert closed_shelter is not None
    assert closed_shelter.status_current is ShelterStatus.CLOSED
    rejected = simulator.step(DispatchAction("Z1", "S1"))
    assert rejected.rejection_code is ActionRejectionCode.SHELTER_CLOSED
    simulator.step(WAIT)
    for _ in range(2):
        simulator.observe()
        simulator.step(WAIT)
        closed_shelter = simulator.state.shelter("S1")
        assert closed_shelter is not None
        assert closed_shelter.status_current is ShelterStatus.CLOSED


def test_existing_reservation_arrives_after_shelter_closes(scenario):
    simulator = StochasticSimulator(scenario, _forced_shelter_config(close=True))
    dispatched = simulator.step(DispatchAction("Z1", "S1"))
    event = dispatched.events_created[0]
    simulator.observe()
    closed_shelter = simulator.prepared_state_for_debug().shelter("S1")
    assert closed_shelter is not None
    assert closed_shelter.status_current is ShelterStatus.CLOSED
    while not simulator.state.terminal and simulator.state.people_safely_arrived == 0:
        simulator.step(WAIT)
        if not simulator.state.terminal:
            simulator.observe()
    assert simulator.state.people_safely_arrived == event.people
    assert simulator.state.shelter("S1").capacity_reserved == 0  # type: ignore[union-attr]


def test_numeric_shelter_capacity_never_degrades(scenario):
    simulator = StochasticSimulator(scenario, HIGH)
    totals = {item.shelter_id: item.capacity_total for item in simulator.state.shelters}
    for _ in range(6):
        simulator.observe()
        simulator.step(WAIT)
    assert {item.shelter_id: item.capacity_total for item in simulator.state.shelters} == totals


def test_arrivals_precede_stochastic_updates_in_audit(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    event = simulator.step(DispatchAction("Z1", "S1")).events_created[0]
    while simulator.state.current_timestep < event.arrival_timestep:
        simulator.observe()
        simulator.step(WAIT)
    simulator.observe()
    result = simulator.step(WAIT)
    types = [record.event_type for record in result.audit_records]
    assert types[0] is AuditEventType.ARRIVAL_PROCESSED
    assert AuditEventType.FLOOD_STATE_UPDATED in types[1:]


def test_action_validation_uses_current_updated_route_state(scenario):
    simulator = StochasticSimulator(scenario, _forced_closure_config())
    simulator.step(WAIT)
    simulator.observe()
    result = simulator.step(DispatchAction("Z1", "S1"))
    assert result.rejection_code is ActionRejectionCode.ROUTE_UNREACHABLE
    assert result.new_timestep == result.previous_timestep == 1


def test_invalid_stochastic_action_rolls_back_exogenous_state(scenario):
    simulator = StochasticSimulator(scenario, _forced_closure_config())
    simulator.step(WAIT)
    first_observation = simulator.observe()
    result = simulator.step(DispatchAction("Z1", "S1"))
    assert not result.accepted
    assert simulator.state.current_timestep == 1
    assert simulator.observe() == first_observation


def test_stochastic_transitions_preserve_phase3_invariants(scenario):
    simulator = StochasticSimulator(scenario, MEDIUM)
    actions = [DispatchAction("Z1", "S1"), WAIT, WAIT, WAIT, WAIT]
    for action in actions:
        simulator.observe()
        result = simulator.step(action)
        assert result.accepted
        assert_episode_invariants(scenario, simulator.state)


def test_paired_action_sequences_share_exogenous_paths(scenario):
    dispatching = StochasticSimulator(scenario, MEDIUM)
    waiting = StochasticSimulator(scenario, MEDIUM)
    assert _hazard_signature(dispatching.observe()) == _hazard_signature(waiting.observe())
    dispatched = dispatching.step(DispatchAction("Z1", "S1"))
    waited = waiting.step(WAIT)
    assert any(
        record.event_type is AuditEventType.TRAVEL_TIME_REALIZED
        for record in dispatched.audit_records
    )
    assert all(
        record.event_type is not AuditEventType.TRAVEL_TIME_REALIZED
        for record in waited.audit_records
    )
    for _ in range(5):
        left = dispatching.observe()
        right = waiting.observe()
        assert _hazard_signature(left) == _hazard_signature(right)
        dispatching.step(WAIT)
        waiting.step(WAIT)


def test_exogenous_audit_outcomes_align_across_policies(scenario):
    dispatching = StochasticSimulator(scenario, MEDIUM)
    waiting = StochasticSimulator(scenario, MEDIUM)
    dispatching.step(DispatchAction("Z1", "S1"))
    waiting.step(WAIT)
    for _ in range(4):
        dispatching.observe()
        waiting.observe()
        left = dispatching.step(WAIT)
        right = waiting.step(WAIT)
        left_exogenous = [
            record.to_dict()
            for record in left.audit_records
            if record.event_type
            in {
                AuditEventType.FLOOD_STATE_UPDATED,
                AuditEventType.ROUTE_CLOSED,
                AuditEventType.SHELTER_RESTRICTED,
                AuditEventType.SHELTER_CLOSED,
            }
        ]
        right_exogenous = [
            record.to_dict()
            for record in right.audit_records
            if record.event_type
            in {
                AuditEventType.FLOOD_STATE_UPDATED,
                AuditEventType.ROUTE_CLOSED,
                AuditEventType.SHELTER_RESTRICTED,
                AuditEventType.SHELTER_CLOSED,
            }
        ]
        assert left_exogenous == right_exogenous


def test_replication_id_changes_keyed_environment(scenario):
    left = StochasticSimulator(scenario, MEDIUM, replication_id=0)
    right = StochasticSimulator(scenario, MEDIUM, replication_id=1)
    left.step(WAIT)
    right.step(WAIT)
    assert _hazard_signature(left.observe()) != _hazard_signature(right.observe())


def test_config_serialization_contains_units_parameters_and_disclaimer():
    payload = MEDIUM.to_dict()
    assert payload["config_id"] == "v3-medium-v1"
    assert payload["regional_hazard_sigma"] > 0
    assert payload["travel_noise_fraction"] > 0
    assert "NOT EMPIRICALLY CALIBRATED" in payload["disclaimer"]


def test_process_sanity_artifact_is_ordered_and_nondegenerate():
    payload = json.loads(
        (ROOT / "data" / "eval_v3" / "phase4_stochastic_sanity.json").read_text()
    )
    by_id = {item["config_id"]: item for item in payload["configs"]}
    low = by_id[LOW.config_id]
    medium = by_id[MEDIUM.config_id]
    high = by_id[HIGH.config_id]
    assert medium["uncertainty_config"] == MEDIUM.to_dict()
    assert (
        low["mean_absolute_severity_change"]
        < medium["mean_absolute_severity_change"]
        < high["mean_absolute_severity_change"]
    )
    assert (
        low["travel_ratio_standard_deviation"]
        < medium["travel_ratio_standard_deviation"]
        < high["travel_ratio_standard_deviation"]
    )
    assert (
        low["fraction_reachable_routes_ever_closed"]
        < medium["fraction_reachable_routes_ever_closed"]
        < high["fraction_reachable_routes_ever_closed"]
    )
    assert 0 < low["fraction_reachable_routes_ever_closed"] < 1
    assert high["mechanically_actionable_timestep_fraction"] > 0.75
    assert high["shelter_closure_transitions_per_shelter_episode"] < 0.25
