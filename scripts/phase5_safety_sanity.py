"""Run the Phase 5 deterministic safety sanity exercise (not a policy benchmark)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

from src.safety import (
    RuleLayer,
    V3_SAFETY_V1,
    evaluate_actions,
    format_evaluation,
)
from src.sim import (
    HIGH,
    LOW,
    MEDIUM,
    WAIT,
    DispatchAction,
    StochasticSimulator,
    validate_action,
)
from src.sim.schemas import load_v3_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "data" / "scenarios_v3" / "example_v3_scenario.json"
OUTPUT_PATH = ROOT / "data" / "eval_v3" / "phase5_safety_sanity.json"
SEEDS_PER_CONFIG = tuple(range(52000, 52030))
CONFIGS = (LOW, MEDIUM, HIGH)


def run_sanity() -> dict:
    template = load_v3_scenario(SCENARIO_PATH)
    states_examined = 0
    candidate_dispatches = 0
    total_candidate_actions = 0
    mechanically_invalid = 0
    hard_safety_exclusions = 0
    finally_allowed = 0
    allowed_mechanical_violations = 0
    allowed_rule_violations = 0
    excluded_missing_reason = 0
    zero_legal_nonterminal = 0
    exclusions: Counter[str] = Counter()

    for config_index, config in enumerate(CONFIGS):
        for seed in SEEDS_PER_CONFIG:
            scenario = replace(template, seed=seed + config_index * 1000)
            simulator = StochasticSimulator(scenario, config)
            while not simulator.state.terminal:
                simulator.observe()
                state = simulator.prepared_state_for_debug()
                snapshot = evaluate_actions(scenario, state, V3_SAFETY_V1)
                states_examined += 1
                total_candidate_actions += len(snapshot.evaluations)

                if not snapshot.allowed_actions:
                    zero_legal_nonterminal += 1

                allowed_dispatches: list[DispatchAction] = []
                for evaluation in snapshot.evaluations:
                    if isinstance(evaluation.action, DispatchAction):
                        candidate_dispatches += 1
                    if not evaluation.mechanically_valid:
                        mechanically_invalid += 1
                    elif (
                        isinstance(evaluation.action, DispatchAction)
                        and not evaluation.hard_safety_allowed
                    ):
                        hard_safety_exclusions += 1
                    if evaluation.final_allowed:
                        finally_allowed += 1
                        if isinstance(evaluation.action, DispatchAction):
                            allowed_dispatches.append(evaluation.action)
                            allowed_mechanical_violations += int(
                                not validate_action(
                                    scenario, state, evaluation.action
                                ).valid
                            )
                            safety_failures = [
                                verdict
                                for verdict in evaluation.rule_verdicts
                                if verdict.layer is RuleLayer.HARD_SAFETY
                                and not verdict.allowed
                            ]
                            allowed_rule_violations += int(bool(safety_failures))
                    else:
                        excluded_missing_reason += int(not evaluation.exclusions)
                        exclusions.update(
                            verdict.rule_id for verdict in evaluation.exclusions
                        )

                # Fixed cyclic exploration only: periodically WAIT, otherwise rotate
                # through currently allowed dispatches. This is not a planner/benchmark.
                if state.current_timestep % 4 == 3 or not allowed_dispatches:
                    action = WAIT
                else:
                    index = (seed + state.current_timestep) % len(allowed_dispatches)
                    action = allowed_dispatches[index]
                result = simulator.step(action)
                if not result.accepted:
                    raise AssertionError("the safety mask allowed a simulator rejection")

    if states_examined < 1000:
        raise AssertionError("Phase 5 sanity must examine at least 1000 decision states")
    if (
        allowed_mechanical_violations
        or allowed_rule_violations
        or excluded_missing_reason
        or zero_legal_nonterminal
    ):
        raise AssertionError("Phase 5 safety sanity invariants failed")

    return {
        "artifact_type": "PHASE_5_SAFETY_SANITY_NOT_POLICY_EVALUATION",
        "generated_date": "2026-09-07",
        "scenario": str(SCENARIO_PATH.relative_to(ROOT)),
        "safety_config": V3_SAFETY_V1.to_dict(),
        "uncertainty_config_ids": [config.config_id for config in CONFIGS],
        "seed_generation": (
            "30 deterministic seeds per uncertainty config; base range 52000-52029 "
            "with disjoint +1000 config offsets"
        ),
        "exploration": (
            "fixed cyclic selection across currently allowed semantic dispatches, "
            "with WAIT every fourth timestep; not a planner or policy benchmark"
        ),
        "states_examined": states_examined,
        "total_candidate_actions_including_wait": total_candidate_actions,
        "candidate_dispatch_actions": candidate_dispatches,
        "mechanically_invalid_count": mechanically_invalid,
        "hard_safety_exclusion_count": hard_safety_exclusions,
        "finally_allowed_action_count_including_wait": finally_allowed,
        "exclusion_counts_by_rule": dict(sorted(exclusions.items())),
        "allowed_dispatches_failing_simulator_validation": (
            allowed_mechanical_violations
        ),
        "allowed_actions_violating_enabled_rules": allowed_rule_violations,
        "excluded_actions_missing_reason": excluded_missing_reason,
        "nonterminal_states_with_zero_allowed_actions_including_wait": (
            zero_legal_nonterminal
        ),
    }


def human_readable_example() -> str:
    """Build and render one fixture state containing all three decision cases."""
    scenario = load_v3_scenario(SCENARIO_PATH)
    simulator = StochasticSimulator(scenario, MEDIUM)
    state = simulator.prepared_state_for_debug()
    state = replace(
        state,
        shelters=tuple(
            replace(
                shelter,
                flood_severity_current=(
                    V3_SAFETY_V1.max_destination_hazard + 0.05
                    if shelter.shelter_id == "S1"
                    else V3_SAFETY_V1.max_destination_hazard - 0.10
                ),
            )
            for shelter in state.shelters
        ),
    )
    snapshot = evaluate_actions(scenario, state)
    by_key = {evaluation.action_key: evaluation for evaluation in snapshot.evaluations}
    cases = (
        ("A. mechanically invalid", by_key["Z2->S2"]),
        ("B. mechanically valid but safety-excluded", by_key["Z2->S1"]),
        ("C. mechanically valid and safety-allowed", by_key["Z1->S2"]),
    )
    return "\n\n".join(
        f"{heading}\n{format_evaluation(evaluation)}"
        for heading, evaluation in cases
    )


def main() -> None:
    payload = run_sanity()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print("\nHUMAN-READABLE THREE-CASE EXAMPLE\n")
    print(human_readable_example())


if __name__ == "__main__":
    main()
