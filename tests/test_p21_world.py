"""Phase 21 acceptance tests (Lead) — v4 world. Do not edit; escalate instead."""

from __future__ import annotations

import math
import statistics
from dataclasses import replace

import pytest

pytestmark = pytest.mark.milestone("P21")


@pytest.fixture(scope="module")
def graph():
    from src.geospatial.road_network import load_road_graph

    return load_road_graph()


def test_world_registry_defaults():
    from src.sim.world import V4_WORLDS, get_world_config

    assert set(V4_WORLDS) >= {"v4-low-dt2-v1", "v4-medium-dt2-v1", "v4-high-dt2-v1"}
    world = get_world_config("v4-medium-dt2-v1")
    assert world.base_uncertainty_id == "v3-medium-v1"
    assert world.timestep_minutes == 2.0
    assert world.horizon_steps == 45
    assert world.closure_model == "EDGE"
    with pytest.raises(ValueError):
        get_world_config("v4-unknown")


def test_scaled_uncertainty_rules_and_legacy_untouched():
    from src.sim.configs import MEDIUM, UNCERTAINTY_CONFIGS
    from src.sim.world import get_world_config, scaled_uncertainty

    legacy_before = {key: cfg.to_dict() for key, cfg in UNCERTAINTY_CONFIGS.items() if key.startswith("v3-")}
    world = get_world_config("v4-medium-dt2-v1")
    scaled = scaled_uncertainty(world)
    f = world.timestep_minutes / 10.0
    assert scaled.config_id == "v4-medium-dt2-v1-unc"
    assert scaled.regional_hazard_sigma == pytest.approx(MEDIUM.regional_hazard_sigma * math.sqrt(f))
    assert scaled.local_hazard_sigma == pytest.approx(MEDIUM.local_hazard_sigma * math.sqrt(f))
    assert scaled.regional_hazard_persistence == pytest.approx(MEDIUM.regional_hazard_persistence ** f)
    assert scaled.hazard_drift_scale == pytest.approx(MEDIUM.hazard_drift_scale * f)
    assert scaled.maximum_closure_probability == pytest.approx(
        1 - (1 - MEDIUM.maximum_closure_probability) ** f
    )
    assert scaled.shelter_degradation_probability == pytest.approx(
        1 - (1 - MEDIUM.shelter_degradation_probability) ** f
    )
    assert scaled.restricted_threshold == MEDIUM.restricted_threshold
    assert scaled.closed_threshold == MEDIUM.closed_threshold
    assert scaled.config_id in UNCERTAINTY_CONFIGS
    assert {key: cfg.to_dict() for key, cfg in UNCERTAINTY_CONFIGS.items() if key.startswith("v3-")} == legacy_before
    assert MEDIUM.to_dict()["regional_hazard_sigma"] == 0.018


def test_transit_enums_exist():
    from src.sim.events import AuditEventType, DispatchStatus
    from src.sim.randomness import RandomStream
    from src.sim.transit import TransitOutcome

    assert {o.value for o in TransitOutcome} == {"ARRIVED", "STRANDED", "ARRIVAL_UNSAFE", "ARRIVAL_OVERFLOW"}
    for name in ("STRANDED", "ARRIVAL_UNSAFE", "ARRIVAL_OVERFLOW"):
        assert hasattr(DispatchStatus, name)
    for name in ("GROUP_STRANDED", "ARRIVAL_UNSAFE", "ARRIVAL_OVERFLOW", "WALK_IN"):
        assert hasattr(AuditEventType, name)
    assert RandomStream("walk_in") is RandomStream.WALK_IN


def test_v4_runtime_trips_span_several_steps(graph):
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.safety import evaluate_actions
    from src.sim import DispatchAction

    scenario, simulator, _, _, world = build_v4_runtime("v4-medium-dt2-v1", graph=graph)
    assert scenario.time.timestep_minutes == world.timestep_minutes == 2.0
    simulator.observe()
    state = simulator.prepared_state_for_debug()
    snapshot = evaluate_actions(scenario, state)
    dispatches = [a for a in snapshot.allowed_actions if isinstance(a, DispatchAction)]
    assert dispatches, "seed 620000 must offer at least one dispatch at t=0"
    lags = []
    for action in dispatches:
        _, fresh, _, _, _ = build_v4_runtime("v4-medium-dt2-v1", graph=graph)
        fresh.observe()
        result = fresh.step(action)
        assert result.accepted
        event = result.events_created[0]
        lags.append(event.arrival_timestep - event.departure_timestep)
    assert statistics.median(lags) >= 3


def test_derive_road_state_streams_and_replication(graph):
    from src.geospatial.road_network import derive_road_state
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.sim.randomness import EpisodeRandomStreams

    scenario, simulator, _, _, world = build_v4_runtime("v4-medium-dt2-v1", graph=graph)
    state = simulator.prepared_state_for_debug()
    cfg = simulator.config
    legacy, _ = derive_road_state(graph, state, cfg, scenario_seed=scenario.seed)
    explicit, _ = derive_road_state(
        graph, state, cfg, scenario_seed=scenario.seed,
        streams=EpisodeRandomStreams(scenario.seed, cfg.config_id, 0),
    )
    assert legacy == explicit
    other, _ = derive_road_state(
        graph, state, cfg, scenario_seed=scenario.seed,
        streams=EpisodeRandomStreams(scenario.seed, cfg.config_id, 1),
    )
    assert [e.hazard_severity for e in other.edges] != [e.hazard_severity for e in legacy.edges]


def test_planner_reads_safety_threshold():
    from src.geospatial import build_geospatial_demo_runtime
    from src.planners import build_planner_input
    from src.planners.model import ModelState
    from src.safety import evaluate_actions
    from src.sim import WAIT

    scenario, simulator, _, _ = build_geospatial_demo_runtime("v3-medium-v1")
    simulator.observe()
    state = simulator.prepared_state_for_debug()
    planner_input = build_planner_input(scenario, state, evaluate_actions(scenario, state), simulator.config)
    assert planner_input.max_destination_hazard == 0.70
    assert "max_destination_hazard" not in planner_input.to_dict()  # legacy serialisation unchanged
    strict = replace(planner_input, max_destination_hazard=0.0)
    assert ModelState.from_input(strict).allowed_actions() == (WAIT,)
    assert len(ModelState.from_input(planner_input).allowed_actions()) > 1


def test_v4_episode_conserves_population(graph):
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.planners import RiskGreedyPlanner, build_planner_input
    from src.safety import evaluate_actions

    scenario, simulator, _, _, _ = build_v4_runtime("v4-high-dt2-v1", graph=graph)
    planner = RiskGreedyPlanner()
    for _ in range(400):
        if simulator.state.terminal:
            break
        simulator.observe()
        state = simulator.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state)
        decision = planner.choose_action(build_planner_input(scenario, state, snapshot, simulator.config))
        assert simulator.step(decision.action).accepted
    final = simulator.state
    assert final.terminal
    accounted = (
        final.population_remaining + final.people_in_transit + final.people_safely_arrived
        + final.people_stranded + final.people_unsafe_arrival + final.people_overflow
    )
    assert accounted == final.initial_evacuation_population
    for shelter in final.shelters:
        assert shelter.occupancy_current <= shelter.capacity_total
