"""Phase 8 frozen reward arithmetic, integration, and independence tests."""

from __future__ import annotations

import inspect
import json
import math
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from src.env_v3 import (
    BALANCED_REWARD,
    DEFAULT_ENV_CONFIG,
    EVACUATION_REWARD,
    EXPOSURE_REWARD,
    PLACEHOLDER_REWARD_VERSION,
    REWARD_CONFIGS,
    WAIT_INDEX,
    EnvV3Config,
    EvacuationEnvV3,
    FrozenV3RewardProvider,
    RewardConfig,
    combine_reward_components,
)
from src.sim import LOW, WAIT, ScenarioV3, StochasticSimulator
from src.sim.generator import generate_gate6_scenario


DETERMINISTIC = replace(
    LOW,
    config_id="phase8-test-deterministic-v1",
    regional_hazard_sigma=0.0,
    regional_hazard_persistence=0.0,
    local_hazard_sigma=0.0,
    hazard_drift_scale=0.0,
    travel_noise_fraction=0.0,
    route_hazard_travel_factor=0.0,
    base_closure_multiplier=0.0,
    hazard_to_closure_strength=0.0,
    maximum_closure_probability=0.0,
    restricted_threshold=0.99,
    closed_threshold=1.0,
    shelter_degradation_probability=0.0,
)


def micro_scenario(
    *,
    population: int = 20,
    severity: float = 0.5,
    travel: float = 5.0,
    horizon: int = 4,
    shelter_hazard: float = 0.1,
    shelter_status: str = "OPEN",
    initial_occupancy: int = 0,
) -> ScenarioV3:
    raw = generate_gate6_scenario(610000, "exact").to_dict()
    raw["scenario_id"] = "phase8-micro"
    raw["seed"] = 88001
    raw["time"] = {"timestep_minutes": 10.0, "horizon_steps": horizon}
    zone = raw["zones"][0]
    zone.update(
        population_total=population,
        population_initial_remaining=population,
        vulnerable_population=0,
        medical_priority_population=0,
        initial_flood_severity=severity,
        initial_severity_trend="STEADY",
    )
    shelter = raw["shelters"][0]
    shelter.update(
        capacity_total=max(population, initial_occupancy),
        occupancy_initial=initial_occupancy,
        status=shelter_status,
        status_reason=None if shelter_status == "OPEN" else "Synthetic test status.",
        initial_flood_severity=shelter_hazard,
    )
    raw["zones"] = [zone]
    raw["shelters"] = [shelter]
    raw["network"]["routes"] = [
        {
            "route_id": "R-Z1-S1",
            "source_zone_id": zone["zone_id"],
            "destination_shelter_id": shelter["shelter_id"],
            "reachable": True,
            "travel_time_mean": travel,
            "travel_time_std": 0.0,
            "base_closure_probability": 0.0,
        }
    ]
    raw["fleet"] = {
        "evacuation_enabled": True,
        "vehicle_count": 1,
        "vehicle_capacity": max(1, population),
        "dispatches_per_timestep": 1,
    }
    return ScenarioV3.from_dict(raw)


def rewarded_env(scenario: ScenarioV3, *, safety: bool = True) -> EvacuationEnvV3:
    return EvacuationEnvV3(
        scenario,
        uncertainty_config=DETERMINISTIC,
        config=replace(DEFAULT_ENV_CONFIG, enable_hard_safety=safety),
        reward_provider=FrozenV3RewardProvider(),
    )


def episode_return(scenario: ScenarioV3, actions: list[int]) -> tuple[float, list[dict]]:
    env = rewarded_env(scenario)
    env.reset(seed=7)
    total = 0.0
    infos = []
    for action in actions:
        _, reward, terminated, truncated, info = env.step(action)
        total += reward
        infos.append(info)
        if terminated or truncated:
            break
    return total, infos


def test_primary_and_sensitivity_weights_are_exact_frozen_and_registered():
    assert (
        BALANCED_REWARD.safe_weight,
        BALANCED_REWARD.exposure_weight,
        BALANCED_REWARD.travel_weight,
        BALANCED_REWARD.terminal_weight,
    ) == (0.55, 0.30, 0.05, 0.10)
    assert (
        EVACUATION_REWARD.safe_weight,
        EVACUATION_REWARD.exposure_weight,
        EVACUATION_REWARD.travel_weight,
        EVACUATION_REWARD.terminal_weight,
    ) == (0.65, 0.20, 0.05, 0.10)
    assert (
        EXPOSURE_REWARD.safe_weight,
        EXPOSURE_REWARD.exposure_weight,
        EXPOSURE_REWARD.travel_weight,
        EXPOSURE_REWARD.terminal_weight,
    ) == (0.50, 0.40, 0.05, 0.05)
    assert set(REWARD_CONFIGS) == {
        "v3-reward-balanced-v1",
        "v3-reward-evacuation-v1",
        "v3-reward-exposure-v1",
    }
    with pytest.raises(FrozenInstanceError):
        BALANCED_REWARD.safe_weight = 1.0  # type: ignore[misc]


def test_unrecognized_or_modified_reward_config_is_rejected():
    modified = replace(BALANCED_REWARD, safe_weight=0.50, exposure_weight=0.35)
    with pytest.raises(ValueError, match="exact recognized"):
        FrozenV3RewardProvider(modified)
    with pytest.raises(ValueError, match="unknown reward"):
        FrozenV3RewardProvider("not-frozen")
    with pytest.raises(ValueError, match="sum to one"):
        RewardConfig("bad", 1, 0.5, 0.2, 0.1, 0.1, "bad", -1, 1)


def test_safe_arrival_is_paid_on_arrival_not_dispatch():
    env = rewarded_env(micro_scenario())
    env.reset(seed=1)
    _, dispatch_reward, _, _, dispatch_info = env.step(0)
    assert dispatch_info["reward_safe_gain"] == 0.0
    assert dispatch_reward < 0.0  # only the modest realized-travel burden
    _, arrival_reward, terminated, truncated, arrival_info = env.step(WAIT_INDEX)
    assert arrival_info["reward_safe_gain"] == 1.0
    assert arrival_reward == pytest.approx(0.55)
    assert terminated and not truncated


def test_exposure_uses_post_action_population_and_horizon_normalization():
    scenario = micro_scenario(population=40, severity=0.5, horizon=4)
    env = rewarded_env(scenario)
    env.reset(seed=0)
    _, _, _, _, info = env.step(0)
    assert info["people_dispatched"] == 40
    assert info["reward_exposure"] == 0.0
    no_dispatch = rewarded_env(scenario)
    no_dispatch.reset(seed=0)
    _, _, _, _, wait_info = no_dispatch.step(WAIT_INDEX)
    assert wait_info["reward_exposure"] == pytest.approx((40 * 0.5) / (40 * 4))
    longer = rewarded_env(micro_scenario(population=40, severity=0.5, horizon=8))
    longer.reset(seed=0)
    _, _, _, _, long_info = longer.step(WAIT_INDEX)
    assert long_info["reward_exposure"] == pytest.approx(
        wait_info["reward_exposure"] / 2
    )


def test_travel_transform_and_population_normalization_are_exact():
    scenario = micro_scenario(population=40, travel=20.0, horizon=4)
    env = rewarded_env(scenario)
    env.reset(seed=0)
    _, _, _, _, info = env.step(0)
    expected = (40 / 40) * (20 / (20 + 40))
    assert info["reward_travel"] == pytest.approx(expected)
    assert info["reward_weighted_travel"] == pytest.approx(-0.05 * expected)


def test_terminal_unfinished_applies_only_at_horizon():
    scenario = micro_scenario(population=20, severity=0.0, travel=50.0, horizon=2)
    env = rewarded_env(scenario)
    env.reset(seed=0)
    _, _, _, _, first = env.step(0)
    assert first["reward_terminal"] == 0.0
    _, reward, terminated, truncated, final = env.step(WAIT_INDEX)
    assert not terminated and truncated
    assert final["reward_terminal"] == 1.0
    assert final["reward_weighted_terminal"] == -0.10
    assert reward == pytest.approx(-0.10)


def test_all_evacuated_has_no_terminal_penalty():
    _, infos = episode_return(micro_scenario(), [0, WAIT_INDEX])
    assert infos[-1]["terminal_reason"] == "ALL_EVACUATED"
    assert infos[-1]["reward_terminal"] == 0.0


def test_component_monotonicity_holding_others_fixed():
    base = dict(safe_gain=0.2, exposure=0.2, travel_burden=0.2, terminal_unfinished=0.2)
    reference = combine_reward_components(BALANCED_REWARD, **base).total_reward
    assert combine_reward_components(
        BALANCED_REWARD, **{**base, "safe_gain": 0.3}
    ).total_reward > reference
    for name in ("exposure", "travel_burden", "terminal_unfinished"):
        assert combine_reward_components(
            BALANCED_REWARD, **{**base, name: 0.3}
        ).total_reward < reference


def test_successful_short_evacuation_beats_doing_nothing():
    scenario = micro_scenario(severity=0.6, horizon=4)
    success, _ = episode_return(scenario, [0, WAIT_INDEX])
    waiting, _ = episode_return(scenario, [WAIT_INDEX] * 4)
    assert success > waiting


def test_earlier_completed_evacuation_beats_delayed_equivalent():
    scenario = micro_scenario(severity=0.6, horizon=5)
    early, _ = episode_return(scenario, [0, WAIT_INDEX])
    late, _ = episode_return(scenario, [WAIT_INDEX, 0, WAIT_INDEX])
    assert early > late


def test_shorter_travel_beats_longer_when_both_complete():
    short, _ = episode_return(micro_scenario(travel=5.0, horizon=6), [0] + [WAIT_INDEX] * 5)
    long, _ = episode_return(micro_scenario(travel=15.0, horizon=6), [0] + [WAIT_INDEX] * 5)
    assert short > long


def test_arrived_before_horizon_beats_same_group_still_in_transit():
    arrived, _ = episode_return(micro_scenario(travel=5.0, horizon=2), [0, WAIT_INDEX])
    transit, _ = episode_return(micro_scenario(travel=15.0, horizon=2), [0, WAIT_INDEX])
    assert arrived > transit


def test_wait_has_no_arbitrary_constant_and_initial_occupants_add_no_credit():
    scenario = micro_scenario(
        population=20,
        severity=0.0,
        horizon=3,
        shelter_status="CLOSED",
        initial_occupancy=20,
    )
    env = rewarded_env(scenario)
    env.reset(seed=0)
    _, reward, terminated, truncated, info = env.step(WAIT_INDEX)
    assert reward == 0.0
    assert info["reward_safe_gain"] == 0.0
    assert not terminated and not truncated


def test_masked_fallback_receives_exact_ordinary_wait_reward():
    scenario = micro_scenario(severity=0.5)
    invalid = rewarded_env(scenario)
    ordinary = rewarded_env(scenario)
    invalid.reset(seed=9)
    ordinary.reset(seed=9)
    _, invalid_reward, _, _, invalid_info = invalid.step(53)
    _, wait_reward, _, _, wait_info = ordinary.step(WAIT_INDEX)
    assert invalid_info["invalid_action_attempted"]
    assert invalid_reward == wait_reward
    assert invalid_info["reward_breakdown"] == wait_info["reward_breakdown"]


def test_reward_is_pure_repeatable_and_does_not_mutate_inputs():
    scenario = micro_scenario()
    simulator = StochasticSimulator(scenario, DETERMINISTIC, replication_id=3)
    simulator.observe()
    previous = simulator.prepared_state_for_debug()
    result = simulator.step(WAIT)
    before = (previous.to_dict(), result.to_dict(), result.state.to_dict())
    provider = FrozenV3RewardProvider()
    left = provider.calculate(previous, result, result.state, scenario)
    right = provider.calculate(previous, result, result.state, scenario)
    after = (previous.to_dict(), result.to_dict(), result.state.to_dict())
    assert left == right
    assert before == after


def test_reward_does_not_depend_on_root_seed_or_future_context():
    scenario = micro_scenario()
    simulator = StochasticSimulator(scenario, DETERMINISTIC)
    simulator.observe()
    previous = simulator.prepared_state_for_debug()
    result = simulator.step(WAIT)
    hidden_other = replace(scenario, seed=scenario.seed + 999)
    provider = FrozenV3RewardProvider()
    assert provider.calculate(previous, result, result.state, scenario) == provider.calculate(
        previous, result, result.state, hidden_other
    )


def test_reward_has_no_planner_or_safety_threshold_dependency():
    import src.env_v3.rewards as rewards_module

    source = inspect.getsource(rewards_module)
    assert "src.planners" not in source
    assert "0.70" not in source and "max_destination_hazard" not in source
    for forbidden in ("oracle", "lookahead", "mpc", "forecast_mean_next"):
        assert forbidden not in source.lower()


def test_safety_on_masks_high_hazard_while_off_executes_without_special_penalty():
    scenario = micro_scenario(severity=0.0, shelter_hazard=0.8)
    on = rewarded_env(scenario, safety=True)
    off = rewarded_env(scenario, safety=False)
    on.reset(seed=0)
    off.reset(seed=0)
    assert not on.action_masks()[0] and off.action_masks()[0]
    _, on_reward, _, _, on_info = on.step(0)
    _, off_reward, _, _, off_info = off.step(0)
    assert on_info["semantic_executed_action"]["action_type"] == "WAIT"
    assert off_info["semantic_executed_action"]["action_type"] == "DISPATCH"
    assert on_reward == 0.0
    assert off_reward == pytest.approx(off_info["reward_weighted_travel"])


def test_breakdown_is_json_serializable_and_gym_reward_is_scalar_float():
    env = rewarded_env(micro_scenario())
    env.reset(seed=0)
    _, reward, _, _, info = env.step(0)
    assert isinstance(reward, float)
    assert json.loads(json.dumps(info["reward_breakdown"]))["reward_config_id"] == (
        "v3-reward-balanced-v1"
    )
    assert info["reward_total"] == reward


def test_placeholder_and_real_provider_training_readiness_safeguards():
    scenario = micro_scenario()
    placeholder = EvacuationEnvV3(scenario, uncertainty_config=DETERMINISTIC)
    placeholder.reset(seed=0)
    assert placeholder.reward_spec_version == PLACEHOLDER_REWARD_VERSION
    assert placeholder.training_ready is False
    with pytest.raises(RuntimeError, match="not training-ready"):
        placeholder.assert_training_ready()
    real = rewarded_env(scenario)
    assert real.training_ready is False
    real.reset(seed=0)
    assert real.training_ready is True
    real.assert_training_ready()


def test_zero_population_reward_is_finite_but_not_training_ready():
    scenario = micro_scenario(population=0, severity=1.0)
    env = rewarded_env(scenario)
    env.reset(seed=0)
    _, reward, _, _, info = env.step(WAIT_INDEX)
    assert reward == 0.0 and math.isfinite(reward)
    assert all(
        math.isfinite(value)
        for key, value in info["reward_breakdown"].items()
        if isinstance(value, float)
    )
    assert env.training_ready is False


def test_boundary_components_reject_nan_infinity_and_out_of_range():
    valid = dict(safe_gain=0.0, exposure=0.0, travel_burden=0.0, terminal_unfinished=0.0)
    assert combine_reward_components(BALANCED_REWARD, **valid).total_reward == 0.0
    all_extreme = combine_reward_components(
        BALANCED_REWARD,
        safe_gain=1.0,
        exposure=1.0,
        travel_burden=1.0,
        terminal_unfinished=1.0,
    )
    assert all_extreme.total_reward == pytest.approx(0.10)
    for bad in (float("nan"), float("inf"), -0.1, 1.1):
        with pytest.raises(ValueError):
            combine_reward_components(BALANCED_REWARD, **{**valid, "exposure": bad})


def test_very_long_positive_travel_remains_finite_and_bounded():
    env = rewarded_env(micro_scenario(travel=1e12, horizon=2))
    env.reset(seed=0)
    _, reward, _, _, info = env.step(0)
    assert np.isfinite(reward)
    assert 0.999999 < info["reward_travel"] < 1.0


def test_same_trajectory_has_identical_reward_sequence():
    def run():
        env = rewarded_env(micro_scenario(severity=0.4, horizon=4))
        env.reset(seed=44)
        rewards = []
        for action in (WAIT_INDEX, 0, WAIT_INDEX, WAIT_INDEX):
            _, reward, terminated, truncated, info = env.step(action)
            rewards.append((reward, info["reward_breakdown"]))
            if terminated or truncated:
                break
        return rewards

    assert run() == run()
