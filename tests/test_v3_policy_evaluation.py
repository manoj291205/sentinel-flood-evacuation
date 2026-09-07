"""Behavioral audit of the frozen Phase 10 evaluation implementation."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest
from sb3_contrib import MaskablePPO

from src.env_v3 import EvacuationEnvV3, FrozenV3RewardProvider
from src.evaluation_v3.config import (
    FROZEN_PHASE10_CONFIG,
    HELDOUT_SEEDS,
    PERMUTATION_BASE_SEEDS,
    PERMUTATION_SEEDS,
    PPO_TRAINING_SEEDS,
    RANDOM_POLICY_SEEDS,
    STRESS_SEEDS,
)
from src.evaluation_v3.generator import (
    generate_evaluation_scenario,
    permute_heldout_scenario,
)
from src.evaluation_v3.metrics import (
    BootstrapInterval,
    cvar_10,
    decide_rl_usefulness,
    normalised_safe_utility,
    paired_cluster_bootstrap,
    relative_exposure_reduction,
    two_level_ppo_bootstrap,
)
from src.evaluation_v3.observation_matched import ObservationMatchedGreedy
from src.planners import build_planner_input
from src.planners.model import ModelState, terminal_action_estimates, terminal_estimate
from src.safety import evaluate_actions
from src.sim import WAIT, EpisodeRandomStreams, RandomStream, StochasticSimulator, get_uncertainty_config
from src.training_v3.config import GATE6_GENERATOR_SEED_RANGES, VALIDATION_GENERATOR_SEEDS
from src.training_v3.evaluation import deterministic_diagnostic_config


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "eval_v3" / "phase10" / "heldout_manifest.json"
RAW_RESULTS = ROOT / "data" / "eval_v3" / "phase10" / "heldout_raw_results.json"


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="module")
def first_generated(manifest):
    entry = manifest["entries"][0]
    return generate_evaluation_scenario(
        entry["generator_seed"],
        suite="heldout",
        uncertainty_config_id=entry["uncertainty_config_id"],
    )


@pytest.fixture(scope="module")
def raw_results():
    return json.loads(RAW_RESULTS.read_text())["rows"]


def test_phase10_counts_and_seeds_are_frozen():
    assert len(HELDOUT_SEEDS) == 600
    assert len(PERMUTATION_BASE_SEEDS) == 100
    assert len(PERMUTATION_SEEDS) == 500
    assert len(STRESS_SEEDS) == 250
    assert FROZEN_PHASE10_CONFIG.bootstrap_resamples == 10_000
    assert FROZEN_PHASE10_CONFIG.replication_id == 0


def test_evaluation_seed_sets_are_pairwise_disjoint():
    sets = [set(HELDOUT_SEEDS), set(PERMUTATION_BASE_SEEDS), set(PERMUTATION_SEEDS), set(STRESS_SEEDS)]
    for index, left in enumerate(sets):
        for right in sets[index + 1 :]:
            assert left.isdisjoint(right)


def test_test_seeds_are_disjoint_from_validation_and_gate6():
    forbidden = set(VALIDATION_GENERATOR_SEEDS)
    for low, high in GATE6_GENERATOR_SEED_RANGES:
        forbidden.update(range(low, high + 1))
    assert set(HELDOUT_SEEDS).isdisjoint(forbidden)
    assert set(PERMUTATION_BASE_SEEDS).isdisjoint(forbidden)
    assert set(STRESS_SEEDS).isdisjoint(forbidden)


def test_manifest_is_balanced_complete_and_structurally_bounded(manifest):
    assert manifest["number_of_scenarios"] == 600
    assert manifest["uncertainty_counts"] == {"LOW": 200, "MEDIUM": 200, "HIGH": 200}
    assert len({entry["scenario_id"] for entry in manifest["entries"]}) == 600
    assert all(4 <= entry["zones"] <= 6 for entry in manifest["entries"])
    assert all(6 <= entry["shelters"] <= 9 for entry in manifest["entries"])
    assert all(10 <= entry["horizon_steps"] <= 16 for entry in manifest["entries"])


def test_generated_scenario_is_schema_valid_and_matches_manifest(first_generated, manifest):
    scenario = first_generated.scenario
    assert scenario.scenario_id == manifest["entries"][0]["scenario_id"]
    assert scenario.schema_version == "3.0"
    assert len(scenario.zones) >= 4


def test_all_policy_results_align_on_the_same_scenario_worlds(manifest, raw_results):
    manifest_ids = {entry["scenario_id"] for entry in manifest["entries"]}
    for policy in (
        "random_valid",
        "nearest_safe",
        "risk_greedy",
        "lookahead_k2",
        "lookahead_k3",
        "sampled_mpc",
        "observation_matched_greedy",
    ):
        assert {row["scenario_id"] for row in raw_results if row["policy"] == policy} == manifest_ids
    for seed in PPO_TRAINING_SEEDS:
        assert {
            row["scenario_id"]
            for row in raw_results
            if row["policy"] == "ppo" and row["training_seed"] == seed
        } == manifest_ids
    for entry in manifest["entries"]:
        worlds = {
            (row["scenario_seed"], row["replication_id"], row["uncertainty_config_id"])
            for row in raw_results
            if row["scenario_id"] == entry["scenario_id"]
        }
        assert worlds == {
            (
                entry["scenario_root_seed"],
                entry["replication_id"],
                entry["uncertainty_config_id"],
            )
        }


def test_recorded_physical_metrics_and_mechanical_integrity(raw_results):
    for row in raw_results:
        assert row["safe_population_fraction"] == pytest.approx(
            row["safe_population"] / row["initial_population"]
        )
        assert 0.0 <= row["completion"] <= 1.0
        assert row["exposed_person_timesteps"] >= 0.0
        assert row["capacity_violations"] == 0
        assert row["closed_route_dispatches"] == 0
        assert row["unsafe_dispatches"] == 0
        if row["policy"] == "ppo":
            assert row["invalid_masked_actions"] == 0
    latency = json.loads((ROOT / "data" / "eval_v3" / "phase10" / "latency_results.json").read_text())
    assert all(value["n"] >= 1_000 for value in latency["policies"].values())


def test_result_artifacts_record_normalisation_bootstrap_and_frozen_outcome():
    output = ROOT / "data" / "eval_v3" / "phase10"
    for path in output.glob("*.json"):
        payload = json.loads(path.read_text())
        assert payload.get("normalisation", payload.get("metadata", {}).get("normalisation")) == "practical"
    bootstrap = json.loads((output / "pairwise_bootstrap.json").read_text())
    for interval in bootstrap["combined"]["effects"].values():
        assert interval["valid_draws"] == 10_000
        assert interval["invalid_draws"] == 0
        assert interval["lower"] <= interval["estimate"] <= interval["upper"]
    summary = json.loads((output / "heldout_summary.json").read_text())
    assert summary["formal_result"] == "NO"


@pytest.mark.parametrize("seed", PPO_TRAINING_SEEDS)
def test_all_five_best_checkpoints_load(seed):
    model = MaskablePPO.load(ROOT / "models" / "v3" / f"ppo_seed{seed}_best.zip", device="cpu")
    assert model.observation_space.shape == (384,)
    assert model.action_space.n == 55


def test_deterministic_masked_inference(first_generated):
    model = MaskablePPO.load(ROOT / "models" / "v3" / "ppo_seed4404_best.zip", device="cpu")
    env = EvacuationEnvV3(
        first_generated.scenario,
        uncertainty_config=first_generated.uncertainty_config_id,
        reward_provider=FrozenV3RewardProvider(),
    )
    observation, _ = env.reset(seed=0)
    mask = env.action_masks()
    first, _ = model.predict(observation, action_masks=mask, deterministic=True)
    second, _ = model.predict(observation, action_masks=mask, deterministic=True)
    assert int(first) == int(second)
    assert mask[int(first)]


def test_policy_rng_cannot_shift_keyed_environment_draws():
    left = EpisodeRandomStreams(123, "v3-medium-v1", 0)
    right = EpisodeRandomStreams(123, "v3-medium-v1", 0)
    _ = np.random.default_rng(RANDOM_POLICY_SEEDS[0]).random(10_000)
    assert left.uniform(RandomStream.ROUTE_CLOSURE, 3, "R1") == right.uniform(RandomStream.ROUTE_CLOSURE, 3, "R1")


def test_nsu_is_phase1_ratio_of_means_and_unclipped():
    assert normalised_safe_utility([3.0, 5.0], [0.0, 2.0], [2.0, 4.0]) == 1.5
    assert normalised_safe_utility([-1.0, 0.0], [0.0, 2.0], [2.0, 4.0]) == -0.75


def test_nsu_near_zero_denominator_is_na():
    assert normalised_safe_utility([1.0], [0.0], [0.01]) is None


def test_cvar_uses_fractional_exact_ten_percent_mass():
    assert cvar_10([1.0, 2.0, 3.0, 4.0, 5.0]) == 1.0
    assert cvar_10(list(range(1, 16))) == pytest.approx((1.0 + 0.5 * 2.0) / 1.5)


def test_relative_exposure_direction_and_zero_behavior():
    assert relative_exposure_reduction(90.0, 100.0) == pytest.approx(0.10)
    assert relative_exposure_reduction(100.0, 0.0) is None


def test_paired_bootstrap_is_deterministic_and_clusters_rows():
    rows = [("a", 1.0), ("b", 3.0), ("c", 8.0)]
    statistic = lambda sample: sum(item[1] for item in sample) / len(sample)
    first = paired_cluster_bootstrap(rows, statistic, seed=12, resamples=200)
    second = paired_cluster_bootstrap(rows, statistic, seed=12, resamples=200)
    assert first == second
    assert first.valid_draws == 200


def test_two_level_bootstrap_does_not_count_seed_rows_as_scenarios():
    values = {1101: [1.0, 2.0], 2202: [3.0, 4.0]}
    result = two_level_ppo_bootstrap(values, [0.0, 0.0], lambda p, b: float(np.mean(p) - np.mean(b)), resamples=100)
    assert result.estimate == 2.5
    assert result.valid_draws == 100


def test_observation_matched_api_cannot_accept_hidden_state(first_generated):
    signature = inspect.signature(ObservationMatchedGreedy.choose_action)
    assert list(signature.parameters) == ["self", "observation", "action_mask", "action_mapping"]
    source = inspect.getsource(ObservationMatchedGreedy)
    assert "pending_dispatch" not in source
    assert "EpisodeState" not in source
    assert "simulator" not in source


def test_observation_matched_action_is_masked(first_generated):
    env = EvacuationEnvV3(
        first_generated.scenario,
        uncertainty_config=first_generated.uncertainty_config_id,
        reward_provider=FrozenV3RewardProvider(),
    )
    observation, _ = env.reset(seed=0)
    mask = env.action_masks()
    decision = ObservationMatchedGreedy().choose_action(observation, mask, env.action_mapping)
    assert mask[decision.action_index]


def test_terminal_batch_optimization_matches_explicit_transitions(first_generated):
    """The Phase 10 runtime optimization must not change frozen planner scores."""
    config = get_uncertainty_config(first_generated.uncertainty_config_id)
    simulator = StochasticSimulator(first_generated.scenario, config)
    simulator.observe()
    episode_state = simulator.prepared_state_for_debug()
    planner_input = build_planner_input(
        first_generated.scenario,
        episode_state,
        evaluate_actions(first_generated.scenario, episode_state),
        config,
    )
    state = ModelState.from_input(planner_input)
    actions = state.allowed_actions()
    batched = terminal_action_estimates(state, actions, 17.25, 31.5)
    explicit = tuple(
        terminal_estimate(state.advance(action), 17.25, 31.5)
        for action in actions
    )
    assert batched == pytest.approx(explicit, abs=1e-12)


def test_permutation_preserves_physical_entity_features(first_generated):
    original = first_generated.scenario
    variant, mapping = permute_heldout_scenario(original, PERMUTATION_SEEDS[0])
    original_zones = {item.location.node_id: (item.population_total, item.initial_flood_severity) for item in original.zones}
    variant_zones = {item.location.node_id: (item.population_total, item.initial_flood_severity) for item in variant.zones}
    assert original_zones == variant_zones
    assert mapping["zones"]


def test_permutation_remaps_actions_and_preserves_paired_dynamics(first_generated):
    original = first_generated.scenario
    variant, mapping = permute_heldout_scenario(original, PERMUTATION_SEEDS[0])
    original_route = original.network.routes[0]
    remapped_route = variant.network.routes[0]
    assert remapped_route.source_zone_id == mapping["zones"][original_route.source_zone_id]
    assert remapped_route.destination_shelter_id == mapping["shelters"][original_route.destination_shelter_id]
    assert remapped_route.travel_time_mean == original_route.travel_time_mean

    config = deterministic_diagnostic_config(first_generated.uncertainty_config_id)
    left = StochasticSimulator(original, config)
    right = StochasticSimulator(variant, config)
    left_physical_ids = {item.zone_id: item.location.node_id for item in original.zones}
    right_physical_ids = {item.zone_id: item.location.node_id for item in variant.zones}
    for _ in range(original.time.horizon_steps):
        left_result = left.step(WAIT)
        right_result = right.step(WAIT)
        assert {
            left_physical_ids[item.zone_id]: (
                item.population_remaining,
                item.flood_severity_current,
            )
            for item in left_result.state.zones
        } == {
            right_physical_ids[item.zone_id]: (
                item.population_remaining,
                item.flood_severity_current,
            )
            for item in right_result.state.zones
        }
        assert left_result.state.people_safely_arrived == right_result.state.people_safely_arrived
        if left_result.terminal:
            assert right_result.terminal
            break


def test_phase9_alarm_thresholds_are_not_relaxed():
    assert FROZEN_PHASE10_CONFIG.material_nsu == 0.02
    assert FROZEN_PHASE10_CONFIG.material_exposure_reduction == 0.05
    manifest = json.loads((ROOT / "data" / "eval_v3" / "phase10" / "permutation_manifest.json").read_text())
    assert manifest["alarm"]["median_absolute_normalised_return_difference"] == 0.05
    assert manifest["alarm"]["mean_absolute_safe_population_difference"] == 0.05


def test_outcome_function_uses_only_yes_no_mixed():
    assert decide_rl_usefulness(combined_gate=True, stratum_gates=[], tail_gate=False, stress_gates=[], supported_safety_regression=False) == "YES"
    assert decide_rl_usefulness(combined_gate=False, stratum_gates=[True], tail_gate=False, stress_gates=[], supported_safety_regression=False) == "MIXED"
    assert decide_rl_usefulness(combined_gate=False, stratum_gates=[], tail_gate=False, stress_gates=[], supported_safety_regression=False) == "NO"
    assert decide_rl_usefulness(combined_gate=True, stratum_gates=[], tail_gate=False, stress_gates=[], supported_safety_regression=True) == "NO"


def test_threshold_logic_is_independent_of_model_performance():
    assert FROZEN_PHASE10_CONFIG.material_nsu == 0.02
    assert FROZEN_PHASE10_CONFIG.material_tail_nsu == 0.02
    assert FROZEN_PHASE10_CONFIG.material_exposure_reduction == 0.05


def test_phase10_source_has_no_learning_call():
    source = (ROOT / "scripts" / "run_phase10.py").read_text()
    package = "\n".join(path.read_text() for path in (ROOT / "src" / "evaluation_v3").glob("*.py"))
    forbidden = "." + "learn("
    assert forbidden not in source
    assert forbidden not in package
