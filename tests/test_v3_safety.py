"""Phase 5 tests for deterministic hard safety and semantic action masks."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.safety import (
    DESTINATION_HAZARD_RULE_ID,
    SAFETY_MODELING_ASSUMPTION_DISCLAIMER,
    V3_SAFETY_V1,
    ActionSafetyEvaluation,
    RuleLayer,
    RuleProvenance,
    SafetyConfig,
    SafetySnapshot,
    enumerate_canonical_actions,
    evaluate_action,
    evaluate_actions,
    snapshot_to_json,
)
from src.sim import (
    HIGH,
    WAIT,
    ActionRejectionCode,
    DispatchAction,
    EpisodeRandomStreams,
    ScenarioV3,
    ShelterStatus,
    StochasticSimulator,
    TerminalReason,
    initialize_episode,
    load_v3_scenario,
    transition,
    validate_action,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "scenarios_v3" / "example_v3_scenario.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(EXAMPLE.read_text())


@pytest.fixture
def scenario() -> ScenarioV3:
    return load_v3_scenario(EXAMPLE)


def _with_shelter(state, shelter_id: str, **changes):
    return replace(
        state,
        shelters=tuple(
            replace(item, **changes) if item.shelter_id == shelter_id else item
            for item in state.shelters
        ),
    )


def _with_zone(state, zone_id: str, **changes):
    return replace(
        state,
        zones=tuple(
            replace(item, **changes) if item.zone_id == zone_id else item
            for item in state.zones
        ),
    )


def _with_route(state, route_id: str, **changes):
    return replace(
        state,
        routes=tuple(
            replace(item, **changes) if item.route_id == route_id else item
            for item in state.routes
        ),
    )


def _failure(evaluation: ActionSafetyEvaluation):
    return evaluation.exclusions[0]


def test_open_reachable_route_with_capacity_passes_mechanics(scenario):
    state = initialize_episode(scenario)
    result = evaluate_action(scenario, state, DispatchAction("Z1", "S1"))
    assert result.mechanically_valid
    assert result.final_allowed
    assert validate_action(scenario, state, result.action).valid


@pytest.mark.parametrize(
    ("mutate", "action", "code"),
    [
        (
            lambda state: _with_route(
                state, "R-Z1-S1", reachable_current=False, closed_at_timestep=0
            ),
            DispatchAction("Z1", "S1"),
            ActionRejectionCode.ROUTE_UNREACHABLE,
        ),
        (
            lambda state: state,
            DispatchAction("Z2", "S2"),
            ActionRejectionCode.ROUTE_UNREACHABLE,
        ),
        (
            lambda state: _with_shelter(
                state, "S1", status_current=ShelterStatus.CLOSED
            ),
            DispatchAction("Z1", "S1"),
            ActionRejectionCode.SHELTER_CLOSED,
        ),
        (
            lambda state: _with_shelter(
                state, "S1", capacity_total=150
            ),
            DispatchAction("Z1", "S1"),
            ActionRejectionCode.NO_CAPACITY,
        ),
        (
            lambda state: _with_zone(state, "Z1", population_remaining=0),
            DispatchAction("Z1", "S1"),
            ActionRejectionCode.NO_POPULATION,
        ),
    ],
)
def test_mechanical_exclusions_come_from_simulator(scenario, mutate, action, code):
    state = mutate(initialize_episode(scenario))
    direct = validate_action(scenario, state, action)
    evaluated = evaluate_action(scenario, state, action)
    assert direct.rejection_code is code
    assert not evaluated.mechanically_valid
    assert not evaluated.final_allowed
    assert _failure(evaluated).reason_code == code.value
    assert _failure(evaluated).layer is RuleLayer.MECHANICAL
    assert _failure(evaluated).provenance is RuleProvenance.SIMULATOR_MECHANIC


def test_positive_partial_capacity_remains_mechanically_valid(scenario):
    state = _with_shelter(initialize_episode(scenario), "S1", capacity_total=170)
    validation = validate_action(scenario, state, DispatchAction("Z1", "S1"))
    evaluated = evaluate_action(scenario, state, DispatchAction("Z1", "S1"))
    assert validation.valid and validation.people == 20
    assert evaluated.mechanically_valid and evaluated.final_allowed


@pytest.mark.parametrize(
    ("action", "code"),
    [
        (DispatchAction("UNKNOWN", "S1"), ActionRejectionCode.UNKNOWN_ZONE),
        (DispatchAction("Z1", "UNKNOWN"), ActionRejectionCode.UNKNOWN_SHELTER),
    ],
)
def test_unknown_ids_are_structured_mechanical_failures(scenario, action, code):
    result = evaluate_action(scenario, initialize_episode(scenario), action)
    assert not result.final_allowed
    assert _failure(result).rule_id == f"MECHANICAL_{code.value}"


def test_terminal_state_has_no_executable_action_including_wait(scenario):
    state = replace(
        initialize_episode(scenario),
        current_timestep=scenario.time.horizon_steps,
        terminal=True,
        terminal_reason=TerminalReason.HORIZON_REACHED,
    )
    snapshot = evaluate_actions(scenario, state)
    assert not any(snapshot.allowed_mask)
    assert all(
        evaluation.exclusions[0].reason_code
        == ActionRejectionCode.EPISODE_TERMINAL.value
        for evaluation in snapshot.evaluations
    )


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(-1e-9, True), (0.0, False), (1e-9, False)],
)
def test_destination_hazard_boundary_is_strictly_below(scenario, offset, expected):
    state = _with_shelter(
        initialize_episode(scenario),
        "S1",
        flood_severity_current=V3_SAFETY_V1.max_destination_hazard + offset,
    )
    result = evaluate_action(scenario, state, DispatchAction("Z1", "S1"))
    assert result.mechanically_valid
    assert result.hard_safety_allowed is expected
    assert result.final_allowed is expected
    safety = next(
        item for item in result.rule_verdicts if item.layer is RuleLayer.HARD_SAFETY
    )
    assert safety.rule_id == DESTINATION_HAZARD_RULE_ID


def test_open_high_hazard_can_be_mechanical_but_safety_excluded(scenario):
    state = _with_shelter(
        initialize_episode(scenario),
        "S1",
        status_current=ShelterStatus.OPEN,
        flood_severity_current=0.71,
    )
    result = evaluate_action(scenario, state, DispatchAction("Z1", "S1"))
    assert result.mechanically_valid
    assert not result.hard_safety_allowed
    assert _failure(result).provenance is RuleProvenance.SYNTHETIC_SAFETY_RULE


def test_restricted_below_threshold_remains_allowed(scenario):
    state = _with_shelter(
        initialize_episode(scenario),
        "S1",
        status_current=ShelterStatus.RESTRICTED,
        flood_severity_current=0.69,
    )
    result = evaluate_action(scenario, state, DispatchAction("Z1", "S1"))
    assert result.mechanically_valid and result.final_allowed


def test_safety_config_identity_and_provenance_are_serialized(scenario):
    snapshot = evaluate_actions(scenario, initialize_episode(scenario))
    payload = snapshot.to_dict()
    assert payload["safety_config_id"] == "v3-safety-v1"
    safety = payload["actions"][0]["rule_verdicts"][1]
    assert safety["config_version"] == "v3-safety-v1"
    assert safety["provenance"] == "SYNTHETIC_SAFETY_RULE"
    assert "NDMA" in SAFETY_MODELING_ASSUMPTION_DISCLAIMER


def test_safety_config_rejects_invalid_threshold():
    with pytest.raises(ValueError, match="max_destination_hazard"):
        SafetyConfig("bad-v1", 1, 1.01, "bad")


def test_safety_off_allows_high_hazard_but_preserves_unsafe_label(scenario):
    state = _with_shelter(
        initialize_episode(scenario), "S1", flood_severity_current=0.90
    )
    result = evaluate_action(
        scenario,
        state,
        DispatchAction("Z1", "S1"),
        enable_hard_safety=False,
    )
    assert result.mechanically_valid
    assert not result.hard_safety_allowed
    assert result.final_allowed
    assert result.exclusions == ()
    failed = [item for item in result.rule_verdicts if not item.allowed]
    assert len(failed) == 1 and not failed[0].enforced


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: _with_route(state, "R-Z1-S1", reachable_current=False),
        lambda state: _with_shelter(state, "S1", capacity_total=150),
        lambda state: _with_shelter(
            state, "S1", status_current=ShelterStatus.CLOSED
        ),
    ],
)
def test_safety_off_never_disables_mechanical_validity(scenario, mutate):
    result = evaluate_action(
        scenario,
        mutate(initialize_episode(scenario)),
        DispatchAction("Z1", "S1"),
        enable_hard_safety=False,
    )
    assert not result.mechanically_valid
    assert not result.final_allowed
    assert result.exclusions[0].layer is RuleLayer.MECHANICAL


def test_wait_is_allowed_and_keeps_nonterminal_legal_set_nonempty(scenario):
    state = initialize_episode(scenario)
    state = replace(
        state,
        shelters=tuple(
            replace(item, flood_severity_current=0.70) for item in state.shelters
        ),
    )
    snapshot = evaluate_actions(scenario, state)
    assert snapshot.canonical_actions[-1] == WAIT
    assert snapshot.allowed_mask[-1]
    assert snapshot.allowed_actions == (WAIT,)


def test_crossing_threshold_recomputes_mask(scenario):
    initial = initialize_episode(scenario)
    below = _with_shelter(initial, "S1", flood_severity_current=0.699)
    above = _with_shelter(initial, "S1", flood_severity_current=0.701)
    action = DispatchAction("Z1", "S1")
    assert evaluate_action(scenario, below, action).final_allowed
    assert not evaluate_action(scenario, above, action).final_allowed


def test_route_closure_recomputes_mask(scenario):
    state = initialize_episode(scenario)
    action = DispatchAction("Z1", "S1")
    assert evaluate_action(scenario, state, action).final_allowed
    closed = _with_route(state, "R-Z1-S1", reachable_current=False)
    assert not evaluate_action(scenario, closed, action).final_allowed


def test_reservation_and_arrival_states_are_recomputed(raw):
    shelter = next(item for item in raw["shelters"] if item["shelter_id"] == "S1")
    shelter["capacity_total"] = shelter["occupancy_initial"] + 50
    scenario = ScenarioV3.from_dict(raw)
    action = DispatchAction("Z1", "S1")
    initial = initialize_episode(scenario)
    assert evaluate_action(scenario, initial, action).final_allowed
    reserved = transition(scenario, initial, action).state
    assert not evaluate_action(scenario, reserved, action).final_allowed
    waiting = transition(scenario, reserved, WAIT).state
    arrived = transition(scenario, waiting, WAIT).state
    assert arrived.shelter("S1").capacity_reserved == 0  # type: ignore[union-attr]
    assert not evaluate_action(scenario, arrived, action).final_allowed


def test_canonical_order_is_zone_major_shelter_minor_then_wait(scenario):
    actions = enumerate_canonical_actions(scenario)
    assert [
        item.to_dict() for item in actions
    ] == [
        {"action_type": "DISPATCH", "zone_id": "Z1", "shelter_id": "S1"},
        {"action_type": "DISPATCH", "zone_id": "Z1", "shelter_id": "S2"},
        {"action_type": "DISPATCH", "zone_id": "Z2", "shelter_id": "S1"},
        {"action_type": "DISPATCH", "zone_id": "Z2", "shelter_id": "S2"},
        {"action_type": "WAIT"},
    ]


def test_canonical_order_is_independent_of_json_list_order(raw):
    left = ScenarioV3.from_dict(raw)
    reversed_raw = copy.deepcopy(raw)
    reversed_raw["zones"].reverse()
    reversed_raw["shelters"].reverse()
    reversed_raw["network"]["routes"].reverse()
    right = ScenarioV3.from_dict(reversed_raw)
    assert enumerate_canonical_actions(left) == enumerate_canonical_actions(right)


def test_mask_index_cannot_drift_from_semantic_action(scenario):
    snapshot = evaluate_actions(scenario, initialize_episode(scenario))
    for index, evaluation in enumerate(snapshot.evaluations):
        assert snapshot.canonical_actions[index] == evaluation.action
        assert snapshot.allowed_mask[index] == evaluation.final_allowed
    with pytest.raises(ValueError, match="equal lengths"):
        replace(snapshot, allowed_mask=(True,))


def test_every_false_mask_has_complete_structured_reason(scenario):
    snapshot = evaluate_actions(scenario, initialize_episode(scenario))
    for allowed, evaluation in zip(snapshot.allowed_mask, snapshot.evaluations):
        if allowed:
            continue
        assert evaluation.exclusions
        for reason in evaluation.exclusions:
            assert reason.rule_id
            assert reason.layer
            assert reason.reason_code
            assert reason.reason
            assert reason.config_version


def test_snapshot_is_stably_json_serializable(scenario):
    state = initialize_episode(scenario)
    left = snapshot_to_json(evaluate_actions(scenario, state))
    right = snapshot_to_json(evaluate_actions(scenario, state))
    assert left == right
    assert json.loads(left)["canonical_actions"][-1] == {"action_type": "WAIT"}


def test_safety_evaluation_does_not_mutate_scenario_or_state(scenario):
    state = initialize_episode(scenario)
    before_scenario = scenario.to_dict()
    before_state = state.to_dict()
    evaluate_actions(scenario, state)
    assert scenario.to_dict() == before_scenario
    assert state.to_dict() == before_state


def test_safety_evaluation_does_not_change_stochastic_outcomes(scenario):
    inspected = StochasticSimulator(scenario, HIGH, replication_id=7)
    untouched = StochasticSimulator(scenario, HIGH, replication_id=7)
    actions = [WAIT, DispatchAction("Z1", "S1"), WAIT, WAIT]
    for action in actions:
        assert inspected.observe() == untouched.observe()
        evaluate_actions(scenario, inspected.prepared_state_for_debug())
        left = inspected.step(action)
        right = untouched.step(action)
        assert left.to_dict() == right.to_dict()


def test_safety_evaluation_consumes_no_random_stream(monkeypatch, scenario):
    def fail(*args, **kwargs):
        raise AssertionError("safety evaluation must not query random streams")

    monkeypatch.setattr(EpisodeRandomStreams, "uniform", fail)
    monkeypatch.setattr(EpisodeRandomStreams, "normal", fail)
    evaluate_actions(scenario, initialize_episode(scenario))


def test_hidden_seed_difference_cannot_change_identical_current_result(scenario):
    other_scenario = replace(scenario, seed=scenario.seed + 999)
    left = initialize_episode(scenario)
    right = initialize_episode(other_scenario)
    assert left.to_policy_observation() == right.to_policy_observation()
    assert snapshot_to_json(evaluate_actions(scenario, left)) == snapshot_to_json(
        evaluate_actions(other_scenario, right)
    )


def test_safety_audit_contains_no_future_or_private_rng_data(scenario):
    simulator = StochasticSimulator(scenario, HIGH)
    encoded = snapshot_to_json(
        evaluate_actions(scenario, simulator.prepared_state_for_debug())
    ).lower()
    for forbidden in (
        "root_seed",
        "replication_id",
        "regional_hazard_state",
        "future_draw",
        "closure_draw",
        "realized_travel",
    ):
        assert forbidden not in encoded


def test_safety_snapshot_rejects_action_evaluation_misalignment(scenario):
    snapshot = evaluate_actions(scenario, initialize_episode(scenario))
    with pytest.raises(ValueError, match="ordering"):
        SafetySnapshot(
            scenario_id=snapshot.scenario_id,
            timestep=snapshot.timestep,
            safety_config_id=snapshot.safety_config_id,
            hard_safety_enabled=True,
            canonical_actions=tuple(reversed(snapshot.canonical_actions)),
            allowed_mask=snapshot.allowed_mask,
            evaluations=snapshot.evaluations,
        )


def test_committed_sanity_artifact_records_required_zero_failures():
    payload = json.loads(
        (ROOT / "data" / "eval_v3" / "phase5_safety_sanity.json").read_text()
    )
    assert payload["safety_config"]["config_id"] == V3_SAFETY_V1.config_id
    assert payload["states_examined"] >= 1000
    assert payload["candidate_dispatch_actions"] >= 1000
    assert payload["allowed_dispatches_failing_simulator_validation"] == 0
    assert payload["allowed_actions_violating_enabled_rules"] == 0
    assert payload["excluded_actions_missing_reason"] == 0
    assert payload["nonterminal_states_with_zero_allowed_actions_including_wait"] == 0
