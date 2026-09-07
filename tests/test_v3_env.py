"""Phase 7 fixed-space Gymnasium environment behavioral tests."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env
from sb3_contrib.common.maskable.utils import get_action_masks, is_masking_supported
from stable_baselines3.common.vec_env import DummyVecEnv

from src.env_v3 import (
    ACTION_COUNT,
    DEFAULT_ENV_CONFIG,
    GLOBAL_FEATURES,
    MAX_SHELTERS,
    MAX_ZONES,
    OBSERVATION_DIM,
    PLACEHOLDER_REWARD_VERSION,
    ROUTE_FEATURES,
    SHELTER_FEATURES,
    WAIT_INDEX,
    ZONE_FEATURES,
    CallableScenarioSource,
    EnvironmentConfigurationError,
    EnvV3Config,
    EvacuationEnvV3,
    FixedActionMap,
)
from src.safety import evaluate_actions
from src.sim import HIGH, WAIT, DispatchAction, ScenarioV3, assert_episode_invariants
from src.sim.generator import generate_gate6_scenario


def scenario_with_size(
    zones: int,
    shelters: int,
    *,
    seed: int = 9001,
    horizon: int = 6,
    population: int = 40,
    shelter_hazard: float = 0.2,
) -> ScenarioV3:
    base = generate_gate6_scenario(620000, "practical").to_dict()
    base["scenario_id"] = f"phase7-{zones}x{shelters}-fixture"
    base["seed"] = seed
    base["time"]["horizon_steps"] = horizon
    base["zones"] = []
    for index in range(1, zones + 1):
        zone = copy.deepcopy(generate_gate6_scenario(610000, "exact").to_dict()["zones"][0])
        zone.update(
            zone_id=f"Z{index:02d}",
            population_total=population,
            population_initial_remaining=population,
            vulnerable_population=0,
            medical_priority_population=0,
            initial_flood_severity=round(0.2 + index * 0.02, 6),
            initial_severity_trend="RISING",
        )
        zone["location"]["node_id"] = f"P7-Z{index:02d}"
        base["zones"].append(zone)
    base["shelters"] = []
    for index in range(1, shelters + 1):
        shelter = copy.deepcopy(
            generate_gate6_scenario(610000, "exact").to_dict()["shelters"][0]
        )
        shelter.update(
            shelter_id=f"S{index:02d}",
            capacity_total=max(80, zones * population),
            occupancy_initial=10,
            status="OPEN",
            status_reason=None,
            initial_flood_severity=shelter_hazard,
        )
        shelter["location"]["node_id"] = f"P7-S{index:02d}"
        base["shelters"].append(shelter)
    base["network"]["routes"] = [
        {
            "route_id": f"R-Z{z:02d}-S{s:02d}",
            "source_zone_id": f"Z{z:02d}",
            "destination_shelter_id": f"S{s:02d}",
            "reachable": True,
            "travel_time_mean": float(5 + z + s),
            "travel_time_std": float((z + s) / 2),
            "base_closure_probability": 0.05,
        }
        for z in range(1, zones + 1)
        for s in range(1, shelters + 1)
    ]
    base["fleet"] = {
        "evacuation_enabled": True,
        "vehicle_count": 3,
        "vehicle_capacity": 20,
        "dispatches_per_timestep": 1,
    }
    return ScenarioV3.from_dict(base)


def run_trace(scenario: ScenarioV3, reset_seed: int, actions: list[int]):
    env = EvacuationEnvV3(scenario, uncertainty_config=HIGH.config_id)
    obs, info = env.reset(seed=reset_seed)
    trace = [(obs.tolist(), env.action_masks().tolist(), info)]
    for action in actions:
        obs, reward, terminated, truncated, info = env.step(action)
        trace.append(
            (
                obs.tolist(),
                env.action_masks().tolist(),
                reward,
                terminated,
                truncated,
                info,
                env.current_state.to_dict(),
            )
        )
        if terminated or truncated:
            break
    return trace


@pytest.mark.parametrize("shape", [(2, 3), (4, 5), (6, 9)])
def test_spaces_are_fixed_bounded_and_finite_across_sizes(shape):
    env = EvacuationEnvV3(scenario_with_size(*shape))
    obs, _ = env.reset(seed=3)
    assert env.action_space.n == ACTION_COUNT == 55
    assert WAIT_INDEX == 54
    assert env.observation_space.shape == (OBSERVATION_DIM,) == (384,)
    assert obs.shape == (384,) and obs.dtype == np.float32
    assert env.observation_space.contains(obs)
    assert np.all(np.isfinite(obs))


@pytest.mark.parametrize("shape", [(7, 3), (3, 10)])
def test_scenario_over_fixed_envelope_fails_loudly(shape):
    env = EvacuationEnvV3(scenario_with_size(*shape))
    with pytest.raises(EnvironmentConfigurationError, match="supports at most"):
        env.reset(seed=1)


def test_mapping_round_trip_key_indices_wait_and_padding():
    mapping = FixedActionMap(scenario_with_size(6, 9))
    assert mapping.decode_action(0).semantic == DispatchAction("Z01", "S01")
    assert mapping.decode_action(8).semantic == DispatchAction("Z01", "S09")
    assert mapping.decode_action(9).semantic == DispatchAction("Z02", "S01")
    assert mapping.decode_action(53).semantic == DispatchAction("Z06", "S09")
    assert mapping.decode_action(54).semantic == WAIT
    for zone_id in mapping.zone_ids:
        for shelter_id in mapping.shelter_ids:
            index = mapping.encode_dispatch(zone_id, shelter_id)
            assert mapping.decode_action(index).semantic == DispatchAction(zone_id, shelter_id)
    small = FixedActionMap(scenario_with_size(2, 3))
    assert small.decode_action(8).action_type == "ABSENT_SLOT"
    assert small.decode_action(53).semantic is None


def test_mapping_is_canonical_and_independent_of_source_order():
    scenario = scenario_with_size(4, 5)
    raw = scenario.to_dict()
    raw["zones"].reverse()
    raw["shelters"].reverse()
    raw["network"]["routes"].reverse()
    shuffled = ScenarioV3.from_dict(raw)
    left, right = FixedActionMap(scenario), FixedActionMap(shuffled)
    assert left.zone_slot_to_id == right.zone_slot_to_id
    assert left.shelter_slot_to_id == right.shelter_slot_to_id
    assert left.encode_dispatch("Z04", "S05") == right.encode_dispatch("Z04", "S05")


def test_padding_presence_and_large_to_small_reset_are_zero():
    large, small = scenario_with_size(6, 9), scenario_with_size(2, 3, seed=9002)
    supplied = iter((large, small))
    env = EvacuationEnvV3(
        scenario_source=CallableScenarioSource(lambda _: next(supplied))
    )
    env.reset(seed=1)
    obs, _ = env.reset(seed=2)
    zone_width, shelter_width, route_width = (
        len(ZONE_FEATURES),
        len(SHELTER_FEATURES),
        len(ROUTE_FEATURES),
    )
    zones_end = MAX_ZONES * zone_width
    shelters_end = zones_end + MAX_SHELTERS * shelter_width
    for slot in range(MAX_ZONES):
        row = obs[slot * zone_width : (slot + 1) * zone_width]
        assert row[0] == float(slot < 2)
        if slot >= 2:
            assert np.count_nonzero(row) == 0
    for slot in range(MAX_SHELTERS):
        start = zones_end + slot * shelter_width
        row = obs[start : start + shelter_width]
        assert row[0] == float(slot < 3)
        if slot >= 3:
            assert np.count_nonzero(row) == 0
    for index in range(MAX_ZONES * MAX_SHELTERS):
        start = shelters_end + index * route_width
        row = obs[start : start + route_width]
        zone_slot, shelter_slot = divmod(index, MAX_SHELTERS)
        present = zone_slot < 2 and shelter_slot < 3
        assert row[0] == float(present)
        if not present:
            assert np.count_nonzero(row) == 0


def test_observation_normalization_and_status_one_hot():
    scenario = scenario_with_size(2, 3)
    env = EvacuationEnvV3(scenario)
    obs, _ = env.reset(seed=0)
    zone_width = len(ZONE_FEATURES)
    first_zone = obs[:zone_width]
    assert first_zone[0] == 1 and first_zone[1] == 1
    assert first_zone[3] == pytest.approx(0.5)
    zone_end = MAX_ZONES * zone_width
    shelter_width = len(SHELTER_FEATURES)
    first_shelter = obs[zone_end : zone_end + shelter_width]
    capacity = scenario.canonical_shelters[0].capacity_total
    assert first_shelter[1] == pytest.approx((capacity - 10) / capacity)
    assert first_shelter[2] == pytest.approx(10 / capacity)
    assert first_shelter[3] == 0
    assert first_shelter[5:8].tolist() == [1.0, 0.0, 0.0]
    globals_ = obs[-len(GLOBAL_FEATURES) :]
    population = sum(z.population_initial_remaining for z in scenario.zones)
    assert globals_[0:4].tolist() == [0.0, 1.0, 0.0, 0.0]
    assert globals_[4] == pytest.approx(20 / (20 + population))
    assert globals_[5] == 1


def test_route_travel_normalization_uses_horizon_transform():
    scenario = scenario_with_size(2, 3, horizon=6)
    env = EvacuationEnvV3(scenario)
    obs, _ = env.reset(seed=0)
    route_start = MAX_ZONES * len(ZONE_FEATURES) + MAX_SHELTERS * len(SHELTER_FEATURES)
    row = obs[route_start : route_start + len(ROUTE_FEATURES)]
    route = env.current_state.routes[0]
    horizon_minutes = scenario.time.timestep_minutes * scenario.time.horizon_steps
    expected = route.expected_travel_time_minutes
    uncertainty = route.travel_time_uncertainty_minutes
    assert row[0:2].tolist() == [1.0, 1.0]
    assert row[2] == pytest.approx(expected / (expected + horizon_minutes))
    assert row[3] == pytest.approx(uncertainty / (uncertainty + horizon_minutes))
    assert row[4] == pytest.approx(route.estimated_closure_probability)


def test_mask_shape_padding_and_phase5_alignment():
    scenario = scenario_with_size(2, 3)
    env = EvacuationEnvV3(scenario)
    env.reset(seed=4)
    mask = env.action_masks()
    assert mask.shape == (55,) and mask.dtype == bool and mask[WAIT_INDEX]
    snapshot = evaluate_actions(scenario, env.current_state)
    for action, allowed in zip(snapshot.canonical_actions, snapshot.allowed_mask):
        index = WAIT_INDEX if action == WAIT else env.action_mapping.encode_dispatch(
            action.zone_id, action.shelter_id
        )
        assert mask[index] == allowed
    for index in range(54):
        if env.action_mapping.decode_action(index).semantic is None:
            assert not mask[index]


def test_missing_and_closed_routes_and_zero_capacity_remain_masked_with_safety_off():
    scenario = scenario_with_size(2, 3)
    raw = scenario.to_dict()
    raw["network"]["routes"] = [
        route
        for route in raw["network"]["routes"]
        if not (route["source_zone_id"] == "Z01" and route["destination_shelter_id"] == "S01")
    ]
    for route in raw["network"]["routes"]:
        if route["source_zone_id"] == "Z01" and route["destination_shelter_id"] == "S02":
            route.update(reachable=False, travel_time_mean=None, travel_time_std=None, base_closure_probability=None)
    raw["shelters"][2]["occupancy_initial"] = raw["shelters"][2]["capacity_total"]
    scenario = ScenarioV3.from_dict(raw)
    config = replace(DEFAULT_ENV_CONFIG, enable_hard_safety=False)
    env = EvacuationEnvV3(scenario, config=config)
    obs, _ = env.reset(seed=0)
    for shelter in ("S01", "S02", "S03"):
        assert not env.action_masks()[env.action_mapping.encode_dispatch("Z01", shelter)]
    assert env.action_masks()[WAIT_INDEX]
    route_start = MAX_ZONES * len(ZONE_FEATURES) + MAX_SHELTERS * len(SHELTER_FEATURES)
    missing_row = obs[route_start : route_start + len(ROUTE_FEATURES)]
    assert np.count_nonzero(missing_row) == 0


def test_zero_population_and_zero_capacity_still_produce_finite_observation():
    scenario = scenario_with_size(1, 1)
    raw = scenario.to_dict()
    raw["zones"][0].update(
        population_total=0,
        population_initial_remaining=0,
        vulnerable_population=0,
        medical_priority_population=0,
    )
    raw["shelters"][0].update(capacity_total=0, occupancy_initial=0)
    scenario = ScenarioV3.from_dict(raw)
    env = EvacuationEnvV3(scenario)
    obs, _ = env.reset(seed=0)
    assert env.observation_space.contains(obs)
    assert np.isfinite(obs).all()
    assert obs[1] == 0.0
    globals_ = obs[-len(GLOBAL_FEATURES) :]
    assert globals_[1:5].tolist() == [0.0, 0.0, 0.0, 1.0]


def test_safety_on_off_changes_only_hard_hazard_exclusion():
    scenario = scenario_with_size(2, 3, shelter_hazard=0.8)
    on = EvacuationEnvV3(scenario)
    off = EvacuationEnvV3(
        scenario, config=replace(DEFAULT_ENV_CONFIG, enable_hard_safety=False)
    )
    on.reset(seed=8)
    off.reset(seed=8)
    index = on.action_mapping.encode_dispatch("Z01", "S01")
    assert not on.action_masks()[index]
    assert off.action_masks()[index]
    assert on.action_masks()[WAIT_INDEX] and off.action_masks()[WAIT_INDEX]


def test_valid_dispatch_wait_and_masked_fallback_semantics():
    scenario = scenario_with_size(2, 3)
    env = EvacuationEnvV3(scenario)
    env.reset(seed=12)
    valid = int(np.flatnonzero(env.action_masks()[:WAIT_INDEX])[0])
    decoded = env.action_mapping.decode_action(valid)
    _, reward, terminated, truncated, info = env.step(valid)
    assert info["semantic_executed_action"]["zone_id"] == decoded.zone_id
    assert info["people_dispatched"] > 0
    assert reward == 0.0 and not terminated and not truncated
    env.reset(seed=12)
    padded = 53
    before = env.current_state.population_remaining
    _, reward, _, _, info = env.step(padded)
    assert info["invalid_action_attempted"]
    assert info["semantic_requested_action"]["action_type"] == "ABSENT_SLOT"
    assert info["semantic_executed_action"]["action_type"] == "WAIT"
    assert info["people_dispatched"] == 0
    assert env.current_state.population_remaining == before
    assert reward == 0.0


def test_out_of_range_noninteger_and_post_terminal_steps_rejected():
    env = EvacuationEnvV3(scenario_with_size(1, 1, horizon=2))
    env.reset(seed=0)
    with pytest.raises(ValueError):
        env.step(55)
    with pytest.raises(ValueError):
        env.step(1.5)  # type: ignore[arg-type]
    env.step(WAIT_INDEX)
    _, _, terminated, truncated, _ = env.step(WAIT_INDEX)
    assert not terminated and truncated
    with pytest.raises(RuntimeError, match="reset"):
        env.step(WAIT_INDEX)
    assert not env.action_masks().any()


def test_terminal_semantics_all_evacuated_vs_horizon():
    complete = scenario_with_size(1, 1, horizon=4, population=20)
    env = EvacuationEnvV3(complete)
    env.reset(seed=0)
    env.step(0)
    _, _, terminated, truncated, info = env.step(WAIT_INDEX)
    assert terminated and not truncated
    assert info["terminal_reason"] == "ALL_EVACUATED"
    horizon = EvacuationEnvV3(scenario_with_size(1, 1, horizon=2, population=100))
    horizon.reset(seed=0)
    horizon.step(WAIT_INDEX)
    _, _, terminated, truncated, info = horizon.step(WAIT_INDEX)
    assert not terminated and truncated
    assert info["terminal_reason"] == "HORIZON_REACHED"


def test_reward_is_explicitly_undefined_zero_placeholder():
    env = EvacuationEnvV3(scenario_with_size(2, 3))
    _, reset_info = env.reset(seed=0)
    _, reward, _, _, info = env.step(WAIT_INDEX)
    assert reward == 0.0
    assert env.reward_spec_version == PLACEHOLDER_REWARD_VERSION
    assert env.training_ready is False
    assert reset_info["reward_defined"] is False
    assert info["reward_defined"] is False
    assert info["reward_spec_version"] == "PHASE7_PLACEHOLDER_ZERO"


def test_same_seed_exact_replay_and_different_seed_stochastic_variation():
    scenario = scenario_with_size(2, 3, horizon=5)
    actions = [WAIT_INDEX] * 5
    assert run_trace(scenario, 41, actions) == run_trace(scenario, 41, actions)
    left = run_trace(scenario, 41, actions)
    right = run_trace(scenario, 42, actions)
    assert left != right


def test_reset_and_step_info_do_not_expose_private_rng_or_future_outcomes():
    env = EvacuationEnvV3(scenario_with_size(2, 3))
    obs, info = env.reset(seed=98765)
    encoded = json.dumps(info, sort_keys=True).lower()
    assert "replication_id" not in encoded and "root_seed" not in encoded
    assert "98765" not in encoded
    assert str(env.scenario.seed) not in encoded
    _, _, _, _, step_info = env.step(0)
    encoded_step = json.dumps(step_info, sort_keys=True).lower()
    for forbidden in (
        "realized_travel_time",
        "travel_multiplier",
        "regional_hazard_state",
        "oracle",
        "future",
    ):
        assert forbidden not in encoded_step
    assert np.isfinite(obs).all()


def test_same_public_state_different_hidden_future_has_identical_observation_and_mask():
    scenario = scenario_with_size(2, 3, seed=111)
    hidden_other = replace(scenario, seed=222)
    left = EvacuationEnvV3(scenario, uncertainty_config=HIGH.config_id)
    right = EvacuationEnvV3(hidden_other, uncertainty_config=HIGH.config_id)
    left_obs, _ = left.reset(seed=7)
    right_obs, _ = right.reset(seed=7)
    assert np.array_equal(left_obs, right_obs)
    assert np.array_equal(left.action_masks(), right.action_masks())


def test_simulator_invariants_hold_after_valid_and_fallback_steps():
    env = EvacuationEnvV3(scenario_with_size(2, 3))
    env.reset(seed=2)
    env.step(0)
    assert_episode_invariants(env.scenario, env.current_state)
    env.step(53)
    assert_episode_invariants(env.scenario, env.current_state)


def test_gymnasium_checker_vectorization_and_mask_detection():
    scenario = scenario_with_size(2, 3)
    checked = EvacuationEnvV3(scenario)
    check_env(checked, skip_render_check=True)
    assert is_masking_supported(checked)
    checked.reset(seed=0)
    assert np.array_equal(get_action_masks(checked), checked.action_masks())
    vector = DummyVecEnv(
        [lambda: EvacuationEnvV3(scenario), lambda: EvacuationEnvV3(scenario)]
    )
    observations = vector.reset()
    assert observations.shape == (2, OBSERVATION_DIM)
    next_observations, rewards, dones, infos = vector.step(
        np.array([WAIT_INDEX, WAIT_INDEX])
    )
    assert next_observations.shape == (2, OBSERVATION_DIM)
    assert rewards.tolist() == [0.0, 0.0]
    assert not dones.any() and len(infos) == 2
    vector.close()
