"""Phase 7 API/compatibility sanity trace; this script performs no RL training."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from gymnasium.utils.env_checker import check_env
from sb3_contrib.common.maskable.utils import is_masking_supported
from stable_baselines3.common.vec_env import DummyVecEnv

from src.env_v3 import (
    DEFAULT_ENV_CONFIG,
    OBSERVATION_DIM,
    PLACEHOLDER_REWARD_VERSION,
    WAIT_INDEX,
    CallableScenarioSource,
    EvacuationEnvV3,
)
from src.sim import HIGH, ScenarioV3
from src.sim.generator import generate_gate6_scenario

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "eval_v3" / "phase7_env_sanity.json"


def _scenario_with_size(zones: int, shelters: int, seed: int) -> ScenarioV3:
    raw = generate_gate6_scenario(620000, "practical").to_dict()
    raw["scenario_id"] = f"phase7-sanity-{zones}x{shelters}"
    raw["seed"] = seed
    zone_template = copy.deepcopy(raw["zones"][0])
    shelter_template = copy.deepcopy(raw["shelters"][0])
    raw["zones"] = []
    for index in range(1, zones + 1):
        zone = copy.deepcopy(zone_template)
        zone.update(
            zone_id=f"Z{index:02d}",
            population_total=40,
            population_initial_remaining=40,
            vulnerable_population=0,
            medical_priority_population=0,
            initial_flood_severity=0.25,
            initial_severity_trend="RISING",
        )
        zone["location"]["node_id"] = f"SANITY-Z{index:02d}"
        raw["zones"].append(zone)
    raw["shelters"] = []
    for index in range(1, shelters + 1):
        shelter = copy.deepcopy(shelter_template)
        shelter.update(
            shelter_id=f"S{index:02d}",
            capacity_total=max(100, zones * 50),
            occupancy_initial=0,
            status="OPEN",
            status_reason=None,
            initial_flood_severity=0.2,
        )
        shelter["location"]["node_id"] = f"SANITY-S{index:02d}"
        raw["shelters"].append(shelter)
    raw["network"]["routes"] = [
        {
            "route_id": f"R-Z{zone:02d}-S{shelter:02d}",
            "source_zone_id": f"Z{zone:02d}",
            "destination_shelter_id": f"S{shelter:02d}",
            "reachable": True,
            "travel_time_mean": float(6 + zone + shelter),
            "travel_time_std": 2.0,
            "base_closure_probability": 0.05,
        }
        for zone in range(1, zones + 1)
        for shelter in range(1, shelters + 1)
    ]
    return ScenarioV3.from_dict(raw)


def _trace(scenario: ScenarioV3, seed: int, actions: list[int]) -> list[dict]:
    env = EvacuationEnvV3(scenario, uncertainty_config=HIGH.config_id)
    observation, _ = env.reset(seed=seed)
    trace = [
        {
            "observation": observation.tolist(),
            "mask": env.action_masks().tolist(),
            "state": env.current_state.to_dict(),
        }
    ]
    for action in actions:
        observation, reward, terminated, truncated, info = env.step(action)
        trace.append(
            {
                "observation": observation.tolist(),
                "mask": env.action_masks().tolist(),
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "requested": info["semantic_requested_action"],
                "executed": info["semantic_executed_action"],
                "state": env.current_state.to_dict(),
            }
        )
        if terminated or truncated:
            break
    return trace


def main() -> int:
    small = _scenario_with_size(2, 3, 71001)
    medium = _scenario_with_size(4, 5, 71002)
    large = _scenario_with_size(6, 9, 71003)

    checked = EvacuationEnvV3(small)
    check_env(checked, skip_render_check=True)
    mask_supported = is_masking_supported(checked)

    vector = DummyVecEnv(
        [lambda: EvacuationEnvV3(small), lambda: EvacuationEnvV3(medium)]
    )
    stacked = vector.reset()
    vector.step(np.array([WAIT_INDEX, WAIT_INDEX]))
    vector_ok = stacked.shape == (2, OBSERVATION_DIM)
    vector.close()

    actions = [WAIT_INDEX] * 10
    replay_ok = _trace(medium, 81, actions) == _trace(medium, 81, actions)
    variation_ok = _trace(medium, 81, actions) != _trace(medium, 82, actions)

    hidden_other = replace(small, seed=small.seed + 1)
    left, right = EvacuationEnvV3(small), EvacuationEnvV3(hidden_other)
    left_obs, _ = left.reset(seed=5)
    right_obs, _ = right.reset(seed=5)
    leakage_ok = np.array_equal(left_obs, right_obs) and np.array_equal(
        left.action_masks(), right.action_masks()
    )

    high_raw = small.to_dict()
    for shelter in high_raw["shelters"]:
        shelter["initial_flood_severity"] = 0.8
    high_hazard = ScenarioV3.from_dict(high_raw)
    safety_on = EvacuationEnvV3(high_hazard)
    safety_off = EvacuationEnvV3(
        high_hazard, config=replace(DEFAULT_ENV_CONFIG, enable_hard_safety=False)
    )
    safety_on.reset(seed=5)
    safety_off.reset(seed=5)
    first = safety_on.action_mapping.encode_dispatch("Z01", "S01")
    safety_ok = (
        not safety_on.action_masks()[first]
        and safety_off.action_masks()[first]
        and safety_on.action_masks()[WAIT_INDEX]
        and safety_off.action_masks()[WAIT_INDEX]
    )

    supplied = iter((large, small))
    resizing = EvacuationEnvV3(
        scenario_source=CallableScenarioSource(lambda _: next(supplied))
    )
    resizing.reset(seed=1)
    resized_obs, _ = resizing.reset(seed=2)
    padding_ok = resized_obs.shape == (OBSERVATION_DIM,) and all(
        value is None for value in resizing.action_mapping.zone_slot_to_id[2:]
    )

    trace_env = EvacuationEnvV3(small)
    observation, _ = trace_env.reset(seed=17)
    print("reset:")
    print(f"  obs shape={observation.shape}; allowed actions={trace_env.action_masks().sum()}")
    requested = 53  # padded for the 2x3 scenario
    observation, reward, terminated, truncated, info = trace_env.step(requested)
    print("t=0")
    print(
        f"  requested index={requested}; decoded={info['semantic_requested_action']['action_type']}; "
        f"mask=false; executed=WAIT; reward={reward:.1f} [PLACEHOLDER]; "
        f"terminated={terminated}; truncated={truncated}"
    )
    step_number = 1
    while not (terminated or truncated):
        allowed_dispatches = np.flatnonzero(trace_env.action_masks()[:WAIT_INDEX])
        requested = int(allowed_dispatches[0]) if allowed_dispatches.size else WAIT_INDEX
        observation, reward, terminated, truncated, info = trace_env.step(requested)
        print(f"t={step_number}")
        print(
            f"  requested index={requested}; decoded={info['semantic_requested_action']['action_type']}; "
            f"mask=true; executed={info['semantic_executed_action']['action_type']}; "
            f"reward={reward:.1f} [PLACEHOLDER]; terminated={terminated}; truncated={truncated}"
        )
        step_number += 1
    print("final:")
    print(f"  terminal reason={info['terminal_reason']}")

    artifact = {
        "phase": 7,
        "artifact_kind": "ENVIRONMENT_API_SANITY_ONLY_NOT_POLICY_PERFORMANCE",
        "environment_config_id": DEFAULT_ENV_CONFIG.config_id,
        "observation_dimension": OBSERVATION_DIM,
        "action_dimension": 55,
        "wait_index": WAIT_INDEX,
        "scenario_sizes_tested": [
            {"zones": 2, "shelters": 3},
            {"zones": 4, "shelters": 5},
            {"zones": 6, "shelters": 9},
        ],
        "check_env_status": "PASS",
        "vectorization_status": "PASS" if vector_ok else "FAIL",
        "mask_compatibility_status": "PASS" if mask_supported else "FAIL",
        "same_seed_replay_status": "PASS" if replay_ok else "FAIL",
        "different_seed_variation_status": "PASS" if variation_ok else "FAIL",
        "padding_checks": "PASS" if padding_ok else "FAIL",
        "leakage_checks": "PASS" if leakage_ok else "FAIL",
        "safety_on_off_checks": "PASS" if safety_ok else "FAIL",
        "placeholder_reward_warning": (
            f"{PLACEHOLDER_REWARD_VERSION}: zero has no research meaning; training_ready=false"
        ),
        "policy_performance_measured": False,
        "ppo_training_performed": False,
    }
    failed = [key for key, value in artifact.items() if value == "FAIL"]
    if failed:
        raise AssertionError(f"Phase 7 sanity failures: {failed}")
    OUTPUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
