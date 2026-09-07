"""Phase 9 preregistration, training artifacts, and permutation diagnostics."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import is_masking_supported

from src.env_v3 import BALANCED_REWARD, EvacuationEnvV3, FrozenV3RewardProvider
from src.sim.generator import EXACT_SEEDS, PRACTICAL_SEEDS
from src.training_v3 import (
    FROZEN_TRAINING_CONFIG,
    PRIMARY_TRAINING_SEEDS,
    TRAINING_GENERATOR_VERSION,
    TRAINING_SPEC_VERSION,
    VALIDATION_GENERATOR_SEEDS,
    VALIDATION_GENERATOR_VERSION,
    generate_ppo_scenario,
    permute_scenario_ids,
    representative_seed,
    training_episode_generator_seed,
    validation_manifest,
)
from src.training_v3.envs import make_training_env
from src.training_v3.evaluation import (
    checkpoint_rank,
    deterministic_diagnostic_config,
    load_manifest_scenario,
    run_policy_episode,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "eval_v3" / "training"
MODELS = ROOT / "models" / "v3"


def load_json(path: Path):
    return json.loads(path.read_text())


def test_training_config_is_frozen_versioned_and_exact_budget():
    config = FROZEN_TRAINING_CONFIG
    assert config.spec_version == TRAINING_SPEC_VERSION == "v3-ppo-training-spec-v1"
    assert config.rollout_size == 5_000
    assert config.total_timesteps == 250_000
    assert config.total_timesteps % config.rollout_size == 0
    assert config.validation_interval == config.checkpoint_interval == 10_000
    with pytest.raises(FrozenInstanceError):
        config.gamma = 0.5  # type: ignore[misc]


def test_five_primary_seeds_are_exact():
    assert PRIMARY_TRAINING_SEEDS == (1101, 2202, 3303, 4404, 5505)


def test_primary_reward_is_exact_and_unchanged():
    assert FROZEN_TRAINING_CONFIG.reward_config_id == "v3-reward-balanced-v1"
    assert (
        BALANCED_REWARD.safe_weight,
        BALANCED_REWARD.exposure_weight,
        BALANCED_REWARD.travel_weight,
        BALANCED_REWARD.terminal_weight,
    ) == (0.55, 0.30, 0.05, 0.10)


def test_procedural_environment_is_training_ready_and_maskable():
    env = make_training_env(1101, 0)
    observation, info = env.reset(seed=1101)
    env.assert_training_ready()
    assert is_masking_supported(env)
    assert observation.shape == (384,)
    assert env.action_masks().shape == (55,)
    assert info["reward_spec_version"] == "v3-reward-balanced-v1"


def test_training_generator_and_stream_are_reproducible():
    seed = training_episode_generator_seed(2202, 3, 17)
    assert seed == training_episode_generator_seed(2202, 3, 17)
    left = generate_ppo_scenario(seed)
    right = generate_ppo_scenario(seed)
    assert left == right
    assert left.generator_version == TRAINING_GENERATOR_VERSION


def test_parallel_training_stream_coordinates_do_not_collide():
    seeds = {
        training_episode_generator_seed(seed, rank, episode)
        for seed in PRIMARY_TRAINING_SEEDS
        for rank in range(4)
        for episode in range(100)
    }
    assert len(seeds) == 5 * 4 * 100


def test_validation_manifest_is_frozen_and_reproducible():
    committed = load_json(DATA / "validation_manifest.json")
    assert committed == validation_manifest()
    assert committed["generator_version"] == VALIDATION_GENERATOR_VERSION
    assert committed["number_of_scenarios"] == 150
    assert len({row["scenario_sha256"] for row in committed["entries"]}) == 150


def test_train_validation_and_gate6_seed_domains_are_disjoint():
    reserved = set(PRIMARY_TRAINING_SEEDS) | set(EXACT_SEEDS) | set(PRACTICAL_SEEDS)
    assert set(VALIDATION_GENERATOR_SEEDS).isdisjoint(reserved)
    stream = {
        training_episode_generator_seed(1101, rank, episode)
        for rank in range(4)
        for episode in range(100)
    }
    assert stream.isdisjoint(set(VALIDATION_GENERATOR_SEEDS) | reserved)


def test_validation_sizes_fit_fixed_envelope():
    manifest = load_json(DATA / "validation_manifest.json")
    for row in manifest["entries"]:
        assert row["zones"] in (4, 5, 6)
        assert row["shelters"] in (6, 7, 8, 9)
        assert 10 <= row["horizon_steps"] <= 16


def test_validation_uncertainty_mixture_is_exact():
    manifest = load_json(DATA / "validation_manifest.json")
    assert Counter(row["uncertainty_config_id"] for row in manifest["entries"]) == {
        "v3-low-v1": 50,
        "v3-medium-v1": 50,
        "v3-high-v1": 50,
    }


def test_training_uncertainty_and_size_sampling_is_broad():
    counts = defaultdict(Counter)
    for episode in range(600):
        generated = generate_ppo_scenario(
            training_episode_generator_seed(3303, episode % 4, episode // 4)
        )
        counts["uncertainty"][generated.uncertainty_config_id] += 1
        counts["zones"][len(generated.scenario.zones)] += 1
        counts["shelters"][len(generated.scenario.shelters)] += 1
        counts["horizon"][generated.scenario.time.horizon_steps] += 1
    assert set(counts["uncertainty"]) == {"v3-low-v1", "v3-medium-v1", "v3-high-v1"}
    assert set(counts["zones"]) == {4, 5, 6}
    assert set(counts["shelters"]) == {6, 7, 8, 9}
    assert set(counts["horizon"]) == set(range(10, 17))
    for category in counts.values():
        expected = 600 / len(category)
        assert all(abs(value - expected) < expected * 0.30 for value in category.values())


def test_opaque_slot_assignment_varies_for_same_physical_position():
    observed_zone_slots = set()
    observed_shelter_slots = set()
    for episode in range(300):
        generated = generate_ppo_scenario(
            training_episode_generator_seed(4404, episode % 4, episode // 4)
        )
        zones = list(generated.scenario.canonical_zones)
        shelters = list(generated.scenario.canonical_shelters)
        observed_zone_slots.add(
            next(i for i, item in enumerate(zones) if item.location.node_id == "P9-ZONE-00")
        )
        observed_shelter_slots.add(
            next(
                i
                for i, item in enumerate(shelters)
                if item.location.node_id == "P9-SHELTER-00"
            )
        )
    assert observed_zone_slots == set(range(6))
    assert observed_shelter_slots == set(range(9))


def test_semantic_properties_are_not_fixed_to_slot_zero():
    populations = set()
    capacities = set()
    severities = set()
    for episode in range(100):
        scenario = generate_ppo_scenario(
            training_episode_generator_seed(5505, 0, episode)
        ).scenario
        populations.add(scenario.canonical_zones[0].population_total)
        capacities.add(scenario.canonical_shelters[0].capacity_total)
        severities.add(scenario.canonical_shelters[0].initial_flood_severity)
    assert len(populations) > 40 and len(capacities) > 70 and len(severities) > 90


def test_debug_run_is_finite_nonconstant_and_mask_clean():
    debug = load_json(DATA / "debug_seed1101.json")
    assert debug["result_status"] == "NOT A PRIMARY RESULT"
    assert debug["requested_and_actual_timesteps"] == 20_000
    assert debug["training_invalid_actions"] == 0
    assert debug["training_reward_min"] < debug["training_reward_max"]
    assert all(math.isfinite(row["mean_episode_return"]) for row in debug["validation_history"])


def test_debug_model_saves_loads_and_inference_is_deterministic():
    model = MaskablePPO.load(MODELS / "debug_seed1101.zip", device="cpu")
    entry = load_json(DATA / "validation_manifest.json")["entries"][0]
    scenario = load_manifest_scenario(entry)
    left = run_policy_episode(model, scenario, entry["uncertainty_config_id"], collect_actions=True)
    right = run_policy_episode(model, scenario, entry["uncertainty_config_id"], collect_actions=True)
    assert left == right
    assert left["invalid_actions"] == 0


def test_checkpoint_metric_order_and_ties_are_frozen():
    base = {
        "mean_episode_return": 0.2,
        "mean_exposure": 0.3,
        "mean_safe_population_fraction": 0.6,
    }
    assert checkpoint_rank({**base, "mean_episode_return": 0.21}, 20_000) > checkpoint_rank(base, 10_000)
    assert checkpoint_rank({**base, "mean_exposure": 0.2}, 20_000) > checkpoint_rank(base, 10_000)
    assert checkpoint_rank({**base, "mean_safe_population_fraction": 0.7}, 20_000) > checkpoint_rank(base, 10_000)
    assert checkpoint_rank(base, 10_000) > checkpoint_rank(base, 20_000)


def test_representative_seed_selection_uses_validation_median():
    scores = {1101: 0.1, 2202: 0.4, 3303: 0.3, 4404: 0.2, 5505: 0.5}
    assert representative_seed(scores) == 3303
    summary = load_json(DATA / "training_summary.json")
    assert summary["representative_seed"] == 4404


def test_permutation_remaps_ids_and_routes_but_preserves_physical_features():
    base = generate_ppo_scenario(
        930000,
        generator_version=VALIDATION_GENERATOR_VERSION,
        uncertainty_config_id="v3-low-v1",
    ).scenario
    permuted, mapping = permute_scenario_ids(base, 950000)
    assert mapping["zones"] and mapping["shelters"]
    for original in base.zones:
        variant = next(
            item for item in permuted.zones if item.location.node_id == original.location.node_id
        )
        assert variant.zone_id == mapping["zones"][original.zone_id]
        assert (
            variant.population_total,
            variant.initial_flood_severity,
            variant.initial_severity_trend,
        ) == (
            original.population_total,
            original.initial_flood_severity,
            original.initial_severity_trend,
        )
    for original in base.shelters:
        variant = next(
            item
            for item in permuted.shelters
            if item.location.node_id == original.location.node_id
        )
        assert variant.shelter_id == mapping["shelters"][original.shelter_id]
        assert (
            variant.capacity_total,
            variant.occupancy_initial,
            variant.status,
            variant.initial_flood_severity,
        ) == (
            original.capacity_total,
            original.occupancy_initial,
            original.status,
            original.initial_flood_severity,
        )


def test_permutation_diagnostic_dynamics_are_deterministic():
    config = deterministic_diagnostic_config("v3-high-v1")
    assert config.regional_hazard_sigma == config.local_hazard_sigma == 0.0
    assert config.minimum_travel_multiplier == config.maximum_travel_multiplier == 1.0
    assert config.maximum_closure_probability == 0.0
    assert config.shelter_degradation_probability == 0.0


def test_all_five_primary_artifacts_have_exact_budget_and_no_invalid_actions():
    for seed in PRIMARY_TRAINING_SEEDS:
        result = load_json(DATA / f"seed_{seed}.json")
        assert result["requested_and_actual_timesteps"] == 250_000
        assert len(result["validation_history"]) == 25
        assert result["training_invalid_actions"] == 0
        for kind in ("best", "final"):
            assert (MODELS / f"ppo_seed{seed}_{kind}.zip").is_file()
            metadata = load_json(MODELS / f"ppo_seed{seed}_{kind}.metadata.json")
            assert metadata["training_seed"] == seed
            assert metadata["observation_dimension"] == 384
            assert metadata["action_dimension"] == 55


def test_aggregate_and_permutation_artifacts_are_complete_and_finite():
    summary = load_json(DATA / "training_summary.json")
    diagnostic = load_json(DATA / "permutation_diagnostic.json")
    assert len(summary["seed_results"]) == 5
    assert summary["total_primary_timesteps"] == 1_250_000
    assert summary["training_invalid_actions"] == 0
    assert diagnostic["total_paired_variants"] == 750
    assert set(diagnostic["by_seed"]) == {str(seed) for seed in PRIMARY_TRAINING_SEEDS}
    assert (DATA / "learning_curves.csv").is_file()
    assert (DATA / "learning_curves.svg").is_file()
    for group in summary["across_seed"].values():
        assert all(math.isfinite(value) for value in group.values())


def test_slot_shortcut_alarm_is_reported_not_hidden():
    diagnostic = load_json(DATA / "permutation_diagnostic.json")
    assert diagnostic["alarm"] is True
    assert diagnostic["alarm_label"] == "POTENTIAL_SLOT_SHORTCUT"
    assert diagnostic["aggregate"]["median_absolute_normalized_return_delta"] > 0.05
    assert diagnostic["aggregate"]["mean_absolute_safe_population_delta"] > 0.05
