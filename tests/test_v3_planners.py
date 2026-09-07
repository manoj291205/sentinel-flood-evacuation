"""Phase 6 planner, generator, oracle, pairing, and leakage tests."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.planners import (
    EPSILON_DEN,
    MPC_HORIZON,
    MPC_SAMPLES,
    ORACLE_LABEL,
    RISK_GREEDY_WEIGHTS,
    EpisodeLedger,
    LookaheadK2Planner,
    LookaheadK3Planner,
    NearestSafePlanner,
    RandomValidPlanner,
    RiskGreedyPlanner,
    SampledMPCPlanner,
    build_planner_input,
    exact_headroom,
    score_dispatch,
    solve_clairvoyant,
)
from src.safety import V3_SAFETY_V1, evaluate_actions, snapshot_to_json
from src.sim import HIGH, LOW, MEDIUM, WAIT, DispatchAction, ScenarioV3, StochasticSimulator
from src.sim.generator import (
    EXACT_SEEDS,
    GENERATOR_VERSION,
    PRACTICAL_SEEDS,
    generate_gate6_scenario,
    suite_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def _prepared(seed=610000, config=MEDIUM):
    scenario = generate_gate6_scenario(seed, "exact")
    simulator = StochasticSimulator(scenario, config)
    simulator.observe()
    state = simulator.prepared_state_for_debug()
    snapshot = evaluate_actions(scenario, state)
    return scenario, simulator, build_planner_input(scenario, state, snapshot, config)


def _planners():
    return (
        NearestSafePlanner(),
        RiskGreedyPlanner(),
        LookaheadK2Planner(),
        LookaheadK3Planner(),
        SampledMPCPlanner(),
    )


def test_practical_input_matches_policy_view_and_omits_private_state():
    scenario, simulator, planner_input = _prepared()
    assert planner_input.observation == simulator.observe()
    encoded = json.dumps(planner_input.to_dict()).lower()
    for forbidden in ("root_seed", "replication_id", "regional_hazard_state"):
        assert forbidden not in encoded
    assert str(scenario.seed) not in encoded


@pytest.mark.parametrize("planner", _planners())
def test_every_practical_planner_selects_allowed_action(planner):
    _, _, planner_input = _prepared()
    decision = planner.choose_action(planner_input)
    index = planner_input.safety_snapshot.canonical_actions.index(decision.action)
    assert planner_input.safety_snapshot.allowed_mask[index]


@pytest.mark.parametrize("planner", _planners())
def test_deterministic_planners_wait_when_dispatches_are_all_excluded(planner):
    scenario, simulator, _ = _prepared()
    state = simulator.prepared_state_for_debug()
    state = replace(
        state,
        shelters=tuple(replace(item, flood_severity_current=0.70) for item in state.shelters),
    )
    snapshot = evaluate_actions(scenario, state)
    value = build_planner_input(scenario, state, snapshot, MEDIUM)
    assert planner.choose_action(value).action == WAIT


@pytest.mark.parametrize("planner", _planners())
def test_planner_selection_does_not_mutate_input(planner):
    _, _, planner_input = _prepared()
    before = copy.deepcopy(planner_input.to_dict())
    planner.choose_action(planner_input)
    assert planner_input.to_dict() == before


def test_random_valid_is_reproducible_with_fixed_policy_seed():
    _, _, planner_input = _prepared()
    left = RandomValidPlanner(99)
    right = RandomValidPlanner(99)
    assert [left.choose_action(planner_input).action for _ in range(20)] == [
        right.choose_action(planner_input).action for _ in range(20)
    ]


def test_random_valid_does_not_shift_environment_outcomes():
    scenario, left, planner_input = _prepared()
    right = StochasticSimulator(scenario, MEDIUM)
    RandomValidPlanner(7).choose_action(planner_input)
    assert left.step(WAIT).to_dict() == right.step(WAIT).to_dict()


def test_nearest_uses_highest_hazard_source_then_expected_travel():
    _, _, planner_input = _prepared()
    decision = NearestSafePlanner().choose_action(planner_input)
    allowed = [
        action
        for action, ok in zip(
            planner_input.safety_snapshot.canonical_actions,
            planner_input.safety_snapshot.allowed_mask,
        )
        if ok and isinstance(action, DispatchAction)
    ]
    zones = {item["zone_id"]: item for item in planner_input.observation["zones"]}
    routes = {
        (item["source_zone_id"], item["destination_shelter_id"]): item
        for item in planner_input.observation["routes"]
    }
    max_hazard = max(zones[item.zone_id]["flood_severity_current"] for item in allowed)
    assert zones[decision.action.zone_id]["flood_severity_current"] == max_hazard
    same_source = [item for item in allowed if item.zone_id == decision.action.zone_id]
    assert routes[(decision.action.zone_id, decision.action.shelter_id)][
        "expected_travel_time_minutes"
    ] == min(routes[(item.zone_id, item.shelter_id)]["expected_travel_time_minutes"] for item in same_source)


def test_nearest_tie_breaks_by_canonical_order():
    scenario, simulator, _ = _prepared()
    state = simulator.prepared_state_for_debug()
    state = replace(
        state,
        zones=tuple(replace(item, flood_severity_current=0.5) for item in state.zones),
        shelters=tuple(replace(item, flood_severity_current=0.2) for item in state.shelters),
        routes=tuple(
            replace(item, reachable_current=True, travel_time_current=10.0, expected_travel_time_minutes=10.0)
            for item in state.routes
        ),
    )
    value = build_planner_input(scenario, state, evaluate_actions(scenario, state), MEDIUM)
    assert NearestSafePlanner().choose_action(value).action == DispatchAction("Z1", "S1")


def test_risk_weights_are_frozen_and_sum_to_one():
    assert RISK_GREEDY_WEIGHTS == {
        "source_urgency": 0.30,
        "destination_safety": 0.20,
        "capacity_usefulness": 0.25,
        "travel": 0.10,
        "closure_safety": 0.10,
        "travel_certainty": 0.05,
    }
    assert sum(RISK_GREEDY_WEIGHTS.values()) == pytest.approx(1.0)


def test_risk_score_components_are_bounded_and_total_is_weighted():
    _, _, planner_input = _prepared()
    action = next(
        action
        for action, allowed in zip(
            planner_input.safety_snapshot.canonical_actions,
            planner_input.safety_snapshot.allowed_mask,
        )
        if allowed and isinstance(action, DispatchAction)
    )
    score = score_dispatch(planner_input, action)
    components = dict(score.components)
    assert all(0 <= value <= 1 for value in components.values())
    assert score.total == pytest.approx(
        sum(RISK_GREEDY_WEIGHTS[name] * value for name, value in components.items())
    )


def test_higher_current_route_risk_reduces_greedy_score():
    _, _, planner_input = _prepared()
    action = next(
        item for item in planner_input.safety_snapshot.canonical_actions
        if isinstance(item, DispatchAction) and planner_input.safety_snapshot.allowed_mask[
            planner_input.safety_snapshot.canonical_actions.index(item)
        ]
    )
    low = score_dispatch(planner_input, action).total
    changed = copy.deepcopy(planner_input)
    for route in changed.observation["routes"]:
        if (route["source_zone_id"], route["destination_shelter_id"]) == (action.zone_id, action.shelter_id):
            route["estimated_closure_probability"] = 1.0
    assert score_dispatch(changed, action).total < low


def test_lookahead_depths_really_expand_additional_levels():
    _, _, planner_input = _prepared()
    k2 = LookaheadK2Planner().choose_action(planner_input)
    k3 = LookaheadK3Planner().choose_action(planner_input)
    assert k2.model_transitions > 0
    assert k3.model_transitions > k2.model_transitions
    assert k3.nodes_evaluated > k2.nodes_evaluated


def test_mpc_configuration_is_frozen():
    assert (MPC_SAMPLES, MPC_HORIZON) == (16, 3)


def test_mpc_is_repeatable_with_fixed_seed_and_scores():
    _, _, planner_input = _prepared()
    left = SampledMPCPlanner(76001).choose_action(planner_input)
    right = SampledMPCPlanner(76001).choose_action(planner_input)
    assert left.action == right.action
    assert left.candidate_scores == right.candidate_scores


@pytest.mark.parametrize(
    "planner_factory",
    [RiskGreedyPlanner, LookaheadK2Planner, LookaheadK3Planner, SampledMPCPlanner],
)
def test_practical_decision_ignores_different_hidden_environment_future(planner_factory):
    scenario, _, left_input = _prepared()
    other = replace(scenario, seed=scenario.seed + 1_000_000)
    other_sim = StochasticSimulator(other, MEDIUM)
    other_state = other_sim.prepared_state_for_debug()
    right_input = build_planner_input(
        other, other_state, evaluate_actions(other, other_state), MEDIUM
    )
    assert left_input.to_dict() == right_input.to_dict()
    left = planner_factory().choose_action(left_input)
    right = planner_factory().choose_action(right_input)
    assert left.action == right.action
    assert left.candidate_scores == right.candidate_scores


def test_gate6_utility_and_exact_normalization_boundaries():
    assert EPSILON_DEN == 0.01
    assert exact_headroom(0.4, 0.0, 0.5) == pytest.approx(0.8)
    assert exact_headroom(0.0, 0.0, 0.01) is None
    assert exact_headroom(-0.1, 0.0, 0.5) == pytest.approx(-0.2)


def test_generator_is_reproducible_schema_valid_and_synthetic():
    left = generate_gate6_scenario(610001, "exact")
    right = generate_gate6_scenario(610001, "exact")
    assert left.to_dict() == right.to_dict()
    assert left.provenance.scenario_origin.classification.value == "SIMULATED"
    assert left.provenance.geography_origin.classification.value == "FICTIONAL"
    assert left.network.network_id.startswith(GENERATOR_VERSION)


@pytest.mark.parametrize("kind", ["exact", "practical"])
def test_suite_manifest_has_frozen_size_and_balanced_strata(kind):
    manifest = suite_manifest(kind)
    assert manifest["number_of_scenarios"] == 120
    assert manifest["uncertainty_counts"] == {"LOW": 40, "MEDIUM": 40, "HIGH": 40}
    expected = EXACT_SEEDS if kind == "exact" else PRACTICAL_SEEDS
    assert tuple(manifest["generator_seeds"]) == expected


def test_oracle_is_explicitly_clairvoyant_and_recovers_a_valid_exact_plan():
    scenario = generate_gate6_scenario(610003, "exact")
    simulator = StochasticSimulator(scenario, MEDIUM)
    result = solve_clairvoyant(simulator)
    assert result.label == ORACLE_LABEL
    assert len(result.actions) == scenario.time.horizon_steps
    assert result.states_expanded > 0 and result.branches_evaluated > 0
    replay = StochasticSimulator(scenario, MEDIUM)
    ledger = EpisodeLedger()
    for action in result.actions:
        replay.observe()
        state = replay.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state)
        index = snapshot.canonical_actions.index(action)
        assert snapshot.allowed_mask[index]
        ledger.observe(state)
        assert replay.step(action).accepted
    assert ledger.utility(replay.state, scenario.time.horizon_steps) == pytest.approx(result.utility)


def test_oracle_is_not_below_tested_practical_planners():
    scenario = generate_gate6_scenario(610004, "exact")
    oracle = solve_clairvoyant(StochasticSimulator(scenario, HIGH))
    for planner in (NearestSafePlanner(), RiskGreedyPlanner(), LookaheadK2Planner()):
        simulator = StochasticSimulator(scenario, HIGH)
        ledger = EpisodeLedger()
        while not simulator.state.terminal:
            simulator.observe()
            state = simulator.prepared_state_for_debug()
            snapshot = evaluate_actions(scenario, state)
            value = build_planner_input(scenario, state, snapshot, HIGH)
            ledger.observe(state)
            simulator.step(planner.choose_action(value).action)
        assert oracle.utility + 1e-9 >= ledger.utility(simulator.state, scenario.time.horizon_steps)


def test_oracle_recovers_manually_solvable_short_route():
    data = generate_gate6_scenario(610005, "exact").to_dict()
    data["time"]["horizon_steps"] = 2
    data["zones"] = [data["zones"][0]]
    data["zones"][0].update(
        population_total=20,
        population_initial_remaining=20,
        vulnerable_population=0,
        medical_priority_population=0,
        initial_flood_severity=0.5,
        initial_severity_trend="STEADY",
    )
    for shelter in data["shelters"]:
        shelter.update(
            capacity_total=40,
            occupancy_initial=0,
            status="OPEN",
            status_reason=None,
            initial_flood_severity=0.1,
        )
    data["network"]["routes"] = [
        {
            "route_id": f"R-Z1-{shelter_id}",
            "source_zone_id": "Z1",
            "destination_shelter_id": shelter_id,
            "reachable": True,
            "travel_time_mean": travel,
            "travel_time_std": 0.0,
            "base_closure_probability": 0.0,
        }
        for shelter_id, travel in (("S1", 5.0), ("S2", 25.0))
    ]
    scenario = ScenarioV3.from_dict(data)
    config = replace(
        LOW,
        config_id="test-gate6-deterministic-v1",
        regional_hazard_sigma=0.0,
        regional_hazard_persistence=0.0,
        local_hazard_sigma=0.0,
        hazard_drift_scale=0.0,
        travel_noise_fraction=0.0,
        route_hazard_travel_factor=0.0,
        base_closure_multiplier=0.0,
        hazard_to_closure_strength=0.0,
        restricted_threshold=0.99,
        closed_threshold=1.0,
        shelter_degradation_probability=0.0,
    )
    result = solve_clairvoyant(StochasticSimulator(scenario, config))
    assert result.actions[0] == DispatchAction("Z1", "S1")
    assert result.utility > 0


def test_different_planner_actions_preserve_paired_exogenous_world():
    scenario = generate_gate6_scenario(610006, "exact")
    left = StochasticSimulator(scenario, MEDIUM)
    right = StochasticSimulator(scenario, MEDIUM)
    left_input = build_planner_input(
        scenario,
        left.prepared_state_for_debug(),
        evaluate_actions(scenario, left.prepared_state_for_debug()),
        MEDIUM,
    )
    right_input = build_planner_input(
        scenario,
        right.prepared_state_for_debug(),
        evaluate_actions(scenario, right.prepared_state_for_debug()),
        MEDIUM,
    )
    left.step(NearestSafePlanner().choose_action(left_input).action)
    right.step(RandomValidPlanner(123).choose_action(right_input).action)
    left_observation = left.observe()
    right_observation = right.observe()

    def exogenous(observation):
        return (
            [(item["zone_id"], item["flood_severity_current"]) for item in observation["zones"]],
            [(item["shelter_id"], item["flood_severity_current"], item["status_current"]) for item in observation["shelters"]],
            [(item["route_id"], item["reachable_current"]) for item in observation["routes"]],
        )

    assert exogenous(left_observation) == exogenous(right_observation)


def test_committed_gate6_summary_matches_frozen_gate():
    payload = json.loads((ROOT / "data" / "eval_v3" / "gate6_summary.json").read_text())
    assert payload["exact_units"] == 120
    assert payload["invalid_normalization_units"] == 0
    assert payload["oracle_timeouts"] == 0
    assert payload["gate_thresholds"] == {
        "median_nsu_exact_minimum": 0.99,
        "p10_nsu_exact_minimum": 0.97,
        "p95_latency_ms_maximum": 100.0,
        "epsilon_den": 0.01,
    }
    assert payload["qualifying_planners"] == []
    assert payload["gate_verdict"] == "PROCEED_TO_RL"
    assert payload["exact_planners"]["lookahead_k3"]["median_nsu_exact"] >= 0.99
    assert payload["exact_planners"]["lookahead_k3"]["p10_nsu_exact"] < 0.97
