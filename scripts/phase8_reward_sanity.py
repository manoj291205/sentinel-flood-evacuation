"""Frozen-reward arithmetic sanity study; no learned policy is created or evaluated."""

from __future__ import annotations

import json
import math
import random
import statistics
from dataclasses import replace
from pathlib import Path

import numpy as np

from src.env_v3 import (
    BALANCED_REWARD,
    EVACUATION_REWARD,
    EXPOSURE_REWARD,
    REWARD_CONFIGS,
    WAIT_INDEX,
    EvacuationEnvV3,
    FrozenV3RewardProvider,
    combine_reward_components,
)
from src.sim import HIGH, LOW, MEDIUM, ScenarioV3
from src.sim.generator import generate_gate6_scenario

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "eval_v3" / "phase8_reward_sanity.json"
EPISODES = 200

DETERMINISTIC = replace(
    LOW,
    config_id="phase8-sanity-deterministic-v1",
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


def _micro(
    *, severity: float = 0.5, travel: float = 5.0, horizon: int = 4,
    shelter_status: str = "OPEN",
) -> ScenarioV3:
    raw = generate_gate6_scenario(610000, "exact").to_dict()
    raw["scenario_id"] = "phase8-sanity-micro"
    raw["seed"] = 88100
    raw["time"] = {"timestep_minutes": 10.0, "horizon_steps": horizon}
    zone = raw["zones"][0]
    zone.update(
        population_total=20,
        population_initial_remaining=20,
        vulnerable_population=0,
        medical_priority_population=0,
        initial_flood_severity=severity,
        initial_severity_trend="STEADY",
    )
    shelter = raw["shelters"][0]
    shelter.update(
        capacity_total=20,
        occupancy_initial=0,
        status=shelter_status,
        status_reason=None if shelter_status == "OPEN" else "Synthetic sanity status.",
        initial_flood_severity=0.1,
    )
    raw["zones"] = [zone]
    raw["shelters"] = [shelter]
    raw["fleet"] = {
        "evacuation_enabled": True,
        "vehicle_count": 1,
        "vehicle_capacity": 20,
        "dispatches_per_timestep": 1,
    }
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
    return ScenarioV3.from_dict(raw)


def _run(scenario: ScenarioV3, actions: list[int]) -> dict:
    env = EvacuationEnvV3(
        scenario,
        uncertainty_config=DETERMINISTIC,
        reward_provider=FrozenV3RewardProvider(),
    )
    env.reset(seed=8)
    rewards: list[float] = []
    infos: list[dict] = []
    for action in actions:
        _, reward, terminated, truncated, info = env.step(action)
        rewards.append(reward)
        infos.append(info)
        if terminated or truncated:
            break
    return {
        "return": sum(rewards),
        "step_rewards": rewards,
        "components": [info["reward_breakdown"] for info in infos],
        "terminal_reason": infos[-1]["terminal_reason"],
    }


def _micro_cases() -> dict:
    successful = _run(_micro(severity=0.6), [0, WAIT_INDEX])
    doing_nothing = _run(_micro(severity=0.6), [WAIT_INDEX] * 4)
    early = _run(_micro(severity=0.6, horizon=5), [0, WAIT_INDEX])
    late = _run(_micro(severity=0.6, horizon=5), [WAIT_INDEX, 0, WAIT_INDEX])
    short = _run(_micro(travel=5.0, horizon=6), [0] + [WAIT_INDEX] * 5)
    long = _run(_micro(travel=15.0, horizon=6), [0] + [WAIT_INDEX] * 5)
    arrived = _run(_micro(travel=5.0, horizon=2), [0, WAIT_INDEX])
    in_transit = _run(_micro(travel=15.0, horizon=2), [0, WAIT_INDEX])
    wait_no_dispatch = _run(
        _micro(severity=0.0, shelter_status="CLOSED"), [WAIT_INDEX]
    )
    arrival_timing = _run(_micro(), [0, WAIT_INDEX])
    return {
        "successful_short_evacuation": successful,
        "doing_nothing": doing_nothing,
        "early_evacuation": early,
        "late_equivalent_evacuation": late,
        "short_travel": short,
        "long_travel": long,
        "arrived_before_horizon": arrived,
        "in_transit_at_horizon": in_transit,
        "wait_when_no_dispatch_possible": wait_no_dispatch,
        "arrival_timing": arrival_timing,
    }


def _random_trajectory_sanity() -> dict:
    configs = (LOW, MEDIUM, HIGH)
    returns: list[float] = []
    steps: list[float] = []
    nan_count = 0
    infinity_count = 0
    counts = {config.level.value: 0 for config in configs}
    for episode in range(EPISODES):
        uncertainty = configs[episode % len(configs)]
        counts[uncertainty.level.value] += 1
        scenario = generate_gate6_scenario(630000 + episode, "practical")
        env = EvacuationEnvV3(
            scenario,
            uncertainty_config=uncertainty,
            reward_provider=FrozenV3RewardProvider(),
        )
        env.reset(seed=episode)
        policy_rng = random.Random(82000 + episode)
        episode_return = 0.0
        while True:
            allowed = np.flatnonzero(env.action_masks()).tolist()
            action = policy_rng.choice(allowed)
            _, reward, terminated, truncated, _ = env.step(action)
            if math.isnan(reward):
                nan_count += 1
            if math.isinf(reward):
                infinity_count += 1
            steps.append(reward)
            episode_return += reward
            if terminated or truncated:
                break
        returns.append(episode_return)
    return {
        "episodes": EPISODES,
        "uncertainty_counts": counts,
        "step_count": len(steps),
        "minimum_observed_step_reward": min(steps),
        "maximum_observed_step_reward": max(steps),
        "mean_step_reward": statistics.fmean(steps),
        "minimum_episode_return": min(returns),
        "maximum_episode_return": max(returns),
        "mean_episode_return": statistics.fmean(returns),
        "nan_count": nan_count,
        "infinity_count": infinity_count,
    }


def main() -> int:
    micro = _micro_cases()
    monotonic_reference = dict(
        safe_gain=0.2, exposure=0.2, travel_burden=0.2, terminal_unfinished=0.2
    )
    reference = combine_reward_components(BALANCED_REWARD, **monotonic_reference)
    monotonic = {
        "more_safe_increases": combine_reward_components(
            BALANCED_REWARD, **{**monotonic_reference, "safe_gain": 0.3}
        ).total_reward > reference.total_reward,
        "more_exposure_decreases": combine_reward_components(
            BALANCED_REWARD, **{**monotonic_reference, "exposure": 0.3}
        ).total_reward < reference.total_reward,
        "more_travel_decreases": combine_reward_components(
            BALANCED_REWARD, **{**monotonic_reference, "travel_burden": 0.3}
        ).total_reward < reference.total_reward,
        "more_unfinished_decreases": combine_reward_components(
            BALANCED_REWARD, **{**monotonic_reference, "terminal_unfinished": 0.3}
        ).total_reward < reference.total_reward,
    }

    scenario = _micro()
    placeholder = EvacuationEnvV3(scenario, uncertainty_config=DETERMINISTIC)
    real = EvacuationEnvV3(
        scenario,
        uncertainty_config=DETERMINISTIC,
        reward_provider=FrozenV3RewardProvider(),
    )
    placeholder.reset(seed=0)
    real.reset(seed=0)
    training_ready = {
        "placeholder": placeholder.training_ready,
        "frozen_real_provider": real.training_ready,
    }
    real.assert_training_ready()

    random_stats = _random_trajectory_sanity()
    checks = {
        "successful_vs_wait": (
            micro["successful_short_evacuation"]["return"]
            > micro["doing_nothing"]["return"]
        ),
        "early_vs_late": (
            micro["early_evacuation"]["return"]
            > micro["late_equivalent_evacuation"]["return"]
        ),
        "short_vs_long_travel": (
            micro["short_travel"]["return"] > micro["long_travel"]["return"]
        ),
        "arrived_vs_in_transit": (
            micro["arrived_before_horizon"]["return"]
            > micro["in_transit_at_horizon"]["return"]
        ),
        "wait_has_no_fixed_penalty": (
            micro["wait_when_no_dispatch_possible"]["step_rewards"] == [0.0]
        ),
        "arrival_credit_delayed": (
            [
                item["safe_gain"] for item in micro["arrival_timing"]["components"]
            ]
            == [0.0, 1.0]
        ),
    }
    if not all(checks.values()) or not all(monotonic.values()):
        raise AssertionError("a frozen reward semantic sanity check failed")
    if random_stats["nan_count"] or random_stats["infinity_count"]:
        raise AssertionError("non-finite reward observed")
    if training_ready != {"placeholder": False, "frozen_real_provider": True}:
        raise AssertionError("training-readiness safeguard failed")

    artifact = {
        "phase": 8,
        "artifact_kind": "REWARD_ARITHMETIC_SANITY_NOT_POLICY_PERFORMANCE",
        "primary_reward_config_id": BALANCED_REWARD.config_id,
        "reward_configs": [
            REWARD_CONFIGS[key].to_dict() for key in sorted(REWARD_CONFIGS)
        ],
        "micro_case_checks": checks,
        "micro_cases": micro,
        "monotonicity_checks": monotonic,
        "random_trajectory_reward_statistics": random_stats,
        "training_ready_verification": training_ready,
        "ppo_training_performed": False,
        "reward_weights_selected_from_results": False,
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(f"reward configs: {', '.join(sorted(REWARD_CONFIGS))}")
    print(f"micro-case checks: {sum(checks.values())}/{len(checks)} PASS")
    print(
        f"random-valid sanity: {EPISODES} episodes, {random_stats['step_count']} steps, "
        f"step [{random_stats['minimum_observed_step_reward']:.6f}, "
        f"{random_stats['maximum_observed_step_reward']:.6f}], episode "
        f"[{random_stats['minimum_episode_return']:.6f}, "
        f"{random_stats['maximum_episode_return']:.6f}]"
    )
    print(
        f"non-finite: NaN={random_stats['nan_count']}, "
        f"infinity={random_stats['infinity_count']}"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
