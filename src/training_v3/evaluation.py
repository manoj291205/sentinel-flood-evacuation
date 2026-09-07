"""Frozen validation, checkpoint ranking, and slot-permutation diagnostics."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import replace
from typing import Any, Iterable

import numpy as np
from sb3_contrib.common.maskable.utils import get_action_masks

from src.env_v3 import EvacuationEnvV3, FrozenV3RewardProvider
from src.sim import UncertaintyConfig, get_uncertainty_config

from .config import FROZEN_TRAINING_CONFIG, VALIDATION_GENERATOR_VERSION
from .generator import generate_ppo_scenario, permute_scenario_ids


def _scenario_hash(scenario) -> str:
    encoded = json.dumps(
        scenario.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_manifest_scenario(entry: dict[str, Any]):
    generated = generate_ppo_scenario(
        int(entry["generator_seed"]),
        generator_version=VALIDATION_GENERATOR_VERSION,
        uncertainty_config_id=str(entry["uncertainty_config_id"]),
    )
    if generated.scenario.scenario_id != entry["scenario_id"]:
        raise RuntimeError("validation manifest scenario identity mismatch")
    if _scenario_hash(generated.scenario) != entry["scenario_sha256"]:
        raise RuntimeError("validation scenario differs from frozen manifest")
    return generated.scenario


def deterministic_diagnostic_config(config_id: str) -> UncertaintyConfig:
    base = get_uncertainty_config(config_id)
    return replace(
        base,
        config_id=f"{base.config_id}-permutation-deterministic-v1",
        description=(
            "Phase 9 paired-ID diagnostic transform with deterministic dynamics; "
            "not a training or primary validation configuration."
        ),
        regional_hazard_sigma=0.0,
        regional_hazard_persistence=0.0,
        local_hazard_sigma=0.0,
        travel_noise_fraction=0.0,
        minimum_travel_multiplier=1.0,
        maximum_travel_multiplier=1.0,
        base_closure_multiplier=0.0,
        hazard_to_closure_strength=0.0,
        maximum_closure_probability=0.0,
        shelter_degradation_probability=0.0,
    )


def run_policy_episode(
    model,
    scenario,
    uncertainty_config: str | UncertaintyConfig,
    *,
    collect_actions: bool = False,
) -> dict[str, Any]:
    env = EvacuationEnvV3(
        scenario,
        uncertainty_config=uncertainty_config,
        reward_provider=FrozenV3RewardProvider(),
    )
    observation, _ = env.reset(seed=0)
    env.assert_training_ready()
    episode_return = 0.0
    exposure = 0.0
    travel = 0.0
    invalid_actions = 0
    allowed_counts: list[int] = []
    wait_only = 0
    actions: list[dict[str, Any]] = []
    zone_slots = [0] * FROZEN_TRAINING_CONFIG.max_zones
    shelter_slots = [0] * FROZEN_TRAINING_CONFIG.max_shelters
    terminated = truncated = False
    while not (terminated or truncated):
        masks = get_action_masks(env)
        allowed = int(np.asarray(masks, dtype=bool).sum())
        allowed_counts.append(allowed)
        wait_only += int(allowed == 1 and bool(masks[FROZEN_TRAINING_CONFIG.wait_action]))
        action, _ = model.predict(
            observation,
            action_masks=masks,
            deterministic=FROZEN_TRAINING_CONFIG.deterministic_validation,
        )
        action_index = int(np.asarray(action).item())
        selected_outside_mask = not bool(masks[action_index])
        decoded = env.action_mapping.decode_action(action_index)
        if decoded.action_type == "DISPATCH":
            assert decoded.zone_slot is not None and decoded.shelter_slot is not None
            zone_slots[decoded.zone_slot] += 1
            shelter_slots[decoded.shelter_slot] += 1
        if collect_actions:
            payload = decoded.to_dict()
            if decoded.zone_id is not None and decoded.shelter_id is not None:
                zone = next(item for item in scenario.zones if item.zone_id == decoded.zone_id)
                shelter = next(
                    item for item in scenario.shelters if item.shelter_id == decoded.shelter_id
                )
                payload["physical_zone"] = zone.location.node_id
                payload["physical_shelter"] = shelter.location.node_id
            actions.append(payload)
        observation, reward, terminated, truncated, info = env.step(action_index)
        episode_return += float(reward)
        exposure += float(info["reward_exposure"])
        travel += float(info["reward_travel"])
        invalid_actions += int(selected_outside_mask or info["invalid_action_attempted"])
    state = env.current_state
    population = state.initial_evacuation_population
    result = {
        "scenario_id": scenario.scenario_id,
        "episode_return": episode_return,
        "safe_population_fraction": state.people_safely_arrived / population,
        "exposure": exposure,
        "travel": travel,
        "completion": float(state.people_safely_arrived == population),
        "invalid_actions": invalid_actions,
        "mean_allowed_actions": statistics.fmean(allowed_counts),
        "minimum_allowed_actions": min(allowed_counts),
        "wait_only_timesteps": wait_only,
        "zone_slot_selections": zone_slots,
        "shelter_slot_selections": shelter_slots,
    }
    if collect_actions:
        result["actions"] = actions
    return result


def summarize_episodes(episodes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(episodes)
    if not rows:
        raise ValueError("at least one episode is required")
    numeric = (
        "episode_return",
        "safe_population_fraction",
        "exposure",
        "travel",
        "completion",
        "mean_allowed_actions",
        "wait_only_timesteps",
    )
    summary = {f"mean_{name}": statistics.fmean(row[name] for row in rows) for name in numeric}
    summary.update(
        {
            "scenario_count": len(rows),
            "median_episode_return": statistics.median(
                row["episode_return"] for row in rows
            ),
            "minimum_allowed_actions": min(row["minimum_allowed_actions"] for row in rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "zone_slot_selections": [
                sum(row["zone_slot_selections"][slot] for row in rows)
                for slot in range(FROZEN_TRAINING_CONFIG.max_zones)
            ],
            "shelter_slot_selections": [
                sum(row["shelter_slot_selections"][slot] for row in rows)
                for slot in range(FROZEN_TRAINING_CONFIG.max_shelters)
            ],
        }
    )
    for value in summary.values():
        if isinstance(value, float) and not math.isfinite(value):
            raise RuntimeError("non-finite validation summary")
    return summary


def evaluate_validation(model, manifest: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    episodes = [
        run_policy_episode(
            model,
            load_manifest_scenario(entry),
            str(entry["uncertainty_config_id"]),
        )
        for entry in manifest["entries"]
    ]
    summary = summarize_episodes(episodes)
    if summary["invalid_actions"] != FROZEN_TRAINING_CONFIG.invalid_validation_action_threshold:
        raise RuntimeError("MaskablePPO selected an action outside the validation mask")
    return summary, episodes


def checkpoint_rank(summary: dict[str, Any], timestep: int) -> tuple[float, float, float, int]:
    """Larger tuple is better: return, lower exposure, safety, earlier checkpoint."""
    return (
        float(summary["mean_episode_return"]),
        -float(summary["mean_exposure"]),
        float(summary["mean_safe_population_fraction"]),
        -int(timestep),
    )


def _semantic(action: dict[str, Any]) -> tuple[str, str | None, str | None]:
    return (
        str(action["action_type"]),
        action.get("physical_zone"),
        action.get("physical_shelter"),
    )


def run_permutation_diagnostic(
    model,
    validation_manifest_payload: dict[str, Any],
    permutation_manifest_payload: dict[str, Any],
) -> dict[str, Any]:
    pairs = []
    zone_slots = [0] * FROZEN_TRAINING_CONFIG.max_zones
    shelter_slots = [0] * FROZEN_TRAINING_CONFIG.max_shelters
    for base_index in permutation_manifest_payload["base_validation_indices"]:
        entry = validation_manifest_payload["entries"][base_index]
        base = load_manifest_scenario(entry)
        config = deterministic_diagnostic_config(entry["uncertainty_config_id"])
        original = run_policy_episode(model, base, config, collect_actions=True)
        for permutation_seed in permutation_manifest_payload["permutation_seeds"][str(base_index)]:
            variant, mapping = permute_scenario_ids(base, permutation_seed)
            permuted = run_policy_episode(model, variant, config, collect_actions=True)
            compared = min(len(original["actions"]), len(permuted["actions"]))
            equivalent = sum(
                _semantic(original["actions"][index]) == _semantic(permuted["actions"][index])
                for index in range(compared)
            )
            denominator = max(len(original["actions"]), len(permuted["actions"]), 1)
            zone_slots = [
                left + right
                for left, right in zip(zone_slots, permuted["zone_slot_selections"])
            ]
            shelter_slots = [
                left + right
                for left, right in zip(shelter_slots, permuted["shelter_slot_selections"])
            ]
            pairs.append(
                {
                    "base_index": base_index,
                    "permutation_seed": permutation_seed,
                    "mapping": mapping,
                    "action_equivalence_rate": equivalent / denominator,
                    "return_delta": permuted["episode_return"] - original["episode_return"],
                    "absolute_normalized_return_delta": abs(
                        permuted["episode_return"] - original["episode_return"]
                    ),
                    "safe_population_delta": (
                        permuted["safe_population_fraction"]
                        - original["safe_population_fraction"]
                    ),
                    "absolute_safe_population_delta": abs(
                        permuted["safe_population_fraction"]
                        - original["safe_population_fraction"]
                    ),
                    "exposure_delta": permuted["exposure"] - original["exposure"],
                }
            )
    median_return = statistics.median(
        row["absolute_normalized_return_delta"] for row in pairs
    )
    mean_safe = statistics.fmean(row["absolute_safe_population_delta"] for row in pairs)
    return {
        "base_scenarios": len(permutation_manifest_payload["base_validation_indices"]),
        "permutations_per_base": permutation_manifest_payload["permutations_per_base"],
        "paired_variants": len(pairs),
        "mean_action_equivalence_rate": statistics.fmean(
            row["action_equivalence_rate"] for row in pairs
        ),
        "mean_return_delta": statistics.fmean(row["return_delta"] for row in pairs),
        "median_absolute_normalized_return_delta": median_return,
        "mean_absolute_safe_population_delta": mean_safe,
        "mean_exposure_delta": statistics.fmean(row["exposure_delta"] for row in pairs),
        "zone_slot_selections": zone_slots,
        "shelter_slot_selections": shelter_slots,
        "alarm": bool(
            median_return > FROZEN_TRAINING_CONFIG.normalized_return_alarm
            or mean_safe > FROZEN_TRAINING_CONFIG.safe_population_alarm
        ),
        "alarm_label": "POTENTIAL_SLOT_SHORTCUT",
        "conditioned_slot_bias_note": (
            "Raw slot counts are reported; systematic conditioned bias requires human "
            "review because reachable/allowed sets vary by timestep."
        ),
        "pairs": pairs,
    }
