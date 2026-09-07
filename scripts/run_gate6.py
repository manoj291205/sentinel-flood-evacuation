"""Run the frozen Gate 6 exact-headroom and practical-size diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

from src.planners import (
    EPSILON_DEN,
    EpisodeLedger,
    LookaheadK2Planner,
    LookaheadK3Planner,
    NearestSafePlanner,
    OracleTimeout,
    RandomValidPlanner,
    RiskGreedyPlanner,
    SampledMPCPlanner,
    build_planner_input,
    exact_headroom,
    solve_clairvoyant,
)
from src.safety import V3_SAFETY_V1, evaluate_actions
from src.sim.configs import get_uncertainty_config
from src.sim.events import DispatchAction
from src.sim.generator import (
    EXACT_SEEDS,
    GENERATOR_VERSION,
    PRACTICAL_SEEDS,
    dump_suite,
    generate_gate6_scenario,
    suite_manifest,
    uncertainty_for_seed,
)
from src.sim.stochastic import StochasticSimulator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "eval_v3"
EXACT_PATH = OUTPUT_DIR / "gate6_exact_results.json"
PRACTICAL_PATH = OUTPUT_DIR / "gate6_practical_results.json"
SUMMARY_PATH = OUTPUT_DIR / "gate6_summary.json"
EXACT_SUITE_PATH = OUTPUT_DIR / "gate6_exact_suite.json"
PRACTICAL_SUITE_PATH = OUTPUT_DIR / "gate6_practical_suite.json"
SPEC_VERSION = "v3-planner-spec-v1"
RANDOM_POLICY_SEEDS = (73001, 73002, 73003, 73004, 73005)
PRACTICAL_NAMES = (
    "random_valid",
    "nearest_safe",
    "risk_greedy",
    "lookahead_k2",
    "lookahead_k3",
    "sampled_mpc",
)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires data")
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _stable_policy_seed(master: int, scenario_id: str) -> int:
    payload = f"gate6-policy-v1|{master}|{scenario_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _planner(name: str, scenario_id: str, policy_seed: int = 73001):
    if name == "random_valid":
        return RandomValidPlanner(_stable_policy_seed(policy_seed, scenario_id))
    if name == "nearest_safe":
        return NearestSafePlanner()
    if name == "risk_greedy":
        return RiskGreedyPlanner()
    if name == "lookahead_k2":
        return LookaheadK2Planner()
    if name == "lookahead_k3":
        return LookaheadK3Planner()
    if name == "sampled_mpc":
        return SampledMPCPlanner()
    raise ValueError(name)


def _mask_counts(snapshot) -> dict[str, int]:
    counts = {
        "candidate_dispatches": 0,
        "mechanically_invalid": 0,
        "hard_safety_excluded": 0,
        "allowed_dispatches": 0,
    }
    for item in snapshot.evaluations:
        if not isinstance(item.action, DispatchAction):
            continue
        counts["candidate_dispatches"] += 1
        if not item.mechanically_valid:
            counts["mechanically_invalid"] += 1
        elif not item.hard_safety_allowed:
            counts["hard_safety_excluded"] += 1
        elif item.final_allowed:
            counts["allowed_dispatches"] += 1
    return counts


def _sum_counts(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: left.get(key, 0) + right.get(key, 0) for key in set(left) | set(right)}


def run_episode(scenario, config, planner_name: str, policy_seed: int = 73001) -> dict:
    simulator = StochasticSimulator(scenario, config, replication_id=0)
    planner = _planner(planner_name, scenario.scenario_id, policy_seed)
    ledger = EpisodeLedger()
    latencies: list[int] = []
    actions = []
    nodes = 0
    transitions = 0
    masks: dict[str, int] = {}
    while not simulator.state.terminal:
        simulator.observe()
        state = simulator.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state, V3_SAFETY_V1)
        masks = _sum_counts(masks, _mask_counts(snapshot))
        planner_input = build_planner_input(scenario, state, snapshot, config)
        ledger.observe(state)
        decision = planner.choose_action(planner_input)
        index = snapshot.canonical_actions.index(decision.action)
        if not snapshot.allowed_mask[index]:
            raise AssertionError(f"{planner_name} selected an excluded action")
        result = simulator.step(decision.action)
        if not result.accepted:
            raise AssertionError(f"{planner_name} action failed simulator validation")
        latencies.append(decision.decision_latency_ns)
        actions.append(decision.action.to_dict())
        nodes += decision.nodes_evaluated
        transitions += decision.model_transitions
    population = simulator.state.initial_evacuation_population
    horizon = scenario.time.horizon_steps
    return {
        "utility": ledger.utility(simulator.state, horizon),
        "safe_population_fraction": simulator.state.people_safely_arrived / population,
        "evacuation_complete": simulator.state.people_safely_arrived == population,
        "exposed_person_timesteps": ledger.exposed_person_timesteps,
        "in_transit_person_minutes": (
            ledger.in_transit_person_timesteps * scenario.time.timestep_minutes
        ),
        "unsafe_dispatches": 0,
        "route_failures": 0,
        "decision_latency_ns": latencies,
        "nodes_evaluated": nodes,
        "model_transitions": transitions,
        "mask_diagnostics": masks,
        "actions": actions,
    }


def run_sequence(scenario, config, actions) -> dict:
    simulator = StochasticSimulator(scenario, config, replication_id=0)
    ledger = EpisodeLedger()
    for action in actions:
        simulator.observe()
        state = simulator.prepared_state_for_debug()
        ledger.observe(state)
        result = simulator.step(action)
        if not result.accepted:
            raise AssertionError("oracle replay action was not accepted")
    population = simulator.state.initial_evacuation_population
    return {
        "utility": ledger.utility(simulator.state, scenario.time.horizon_steps),
        "safe_population_fraction": simulator.state.people_safely_arrived / population,
        "evacuation_complete": simulator.state.people_safely_arrived == population,
        "exposed_person_timesteps": ledger.exposed_person_timesteps,
        "in_transit_person_minutes": ledger.in_transit_person_timesteps
        * scenario.time.timestep_minutes,
    }


def _mean_runs(runs: list[dict]) -> dict:
    numeric = (
        "utility",
        "safe_population_fraction",
        "exposed_person_timesteps",
        "in_transit_person_minutes",
    )
    result = {key: statistics.fmean(run[key] for run in runs) for key in numeric}
    result["evacuation_completion_fraction"] = statistics.fmean(
        float(run["evacuation_complete"]) for run in runs
    )
    result["decision_latency_ns"] = [
        value for run in runs for value in run["decision_latency_ns"]
    ]
    result["nodes_evaluated"] = sum(run["nodes_evaluated"] for run in runs)
    result["model_transitions"] = sum(run["model_transitions"] for run in runs)
    result["mask_diagnostics"] = {}
    for run in runs:
        result["mask_diagnostics"] = _sum_counts(
            result["mask_diagnostics"], run["mask_diagnostics"]
        )
    return result


def metadata() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:  # pragma: no cover
        commit = "UNKNOWN"
    return {
        "git_commit": commit,
        "planner_spec_version": SPEC_VERSION,
        "planner_spec_commit": commit,
        "generator_version": GENERATOR_VERSION,
        "safety_config": V3_SAFETY_V1.to_dict(),
        "uncertainty_config_versions": ["v3-low-v1", "v3-medium-v1", "v3-high-v1"],
        "replication_id": 0,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "timing_clock": "time.perf_counter_ns",
        "latency_excludes": "input/safety construction, simulator transition, logging, imports",
        "reference_machine": "MacBookAir10,1 Apple M1 8-core 8GB arm64",
        "artifact_note": "Synthetic Gate 6 diagnostic; not final held-out evaluation.",
    }


def warm_up() -> None:
    scenario = generate_gate6_scenario(EXACT_SEEDS[0], "exact")
    config = get_uncertainty_config("v3-low-v1")
    simulator = StochasticSimulator(scenario, config)
    state = simulator.prepared_state_for_debug()
    value = build_planner_input(scenario, state, evaluate_actions(scenario, state), config)
    for name in PRACTICAL_NAMES:
        planner = _planner(name, scenario.scenario_id)
        for _ in range(20):
            planner.choose_action(value)


def run_exact(seeds=EXACT_SEEDS) -> dict:
    units = []
    for number, seed in enumerate(seeds, 1):
        scenario = generate_gate6_scenario(seed, "exact")
        config_id = uncertainty_for_seed(seed, "exact")
        config = get_uncertainty_config(config_id)
        random_runs = [
            run_episode(scenario, config, "random_valid", policy_seed)
            for policy_seed in RANDOM_POLICY_SEEDS
        ]
        lower = _mean_runs(random_runs)
        planners = {"random_valid": lower}
        for name in PRACTICAL_NAMES[1:]:
            planners[name] = run_episode(scenario, config, name)
        try:
            oracle = solve_clairvoyant(StochasticSimulator(scenario, config))
            oracle_metrics = run_sequence(scenario, config, oracle.actions)
            if abs(oracle.utility - oracle_metrics["utility"]) > 1e-9:
                raise AssertionError("oracle search/replay utility mismatch")
            timed_out = False
        except OracleTimeout:
            oracle = None
            oracle_metrics = None
            timed_out = True
        denominator = None if timed_out else oracle.utility - lower["utility"]
        for name, values in planners.items():
            values["nsu_exact"] = (
                None
                if timed_out
                else exact_headroom(values["utility"], lower["utility"], oracle.utility)
            )
            if not timed_out and values["utility"] > oracle.utility + 1e-9:
                raise AssertionError(f"{name} exceeded exact oracle on {scenario.scenario_id}")
        units.append(
            {
                "generator_seed": seed,
                "scenario_id": scenario.scenario_id,
                "environment_root_seed": scenario.seed,
                "uncertainty_config_id": config_id,
                "replication_id": 0,
                "lower_reference_policy_seeds": list(RANDOM_POLICY_SEEDS),
                "lower_reference_utility": lower["utility"],
                "oracle": oracle.to_dict() if oracle else {"timed_out": True},
                "oracle_metrics": oracle_metrics,
                "normalization_denominator": denominator,
                "normalization_valid": denominator is not None and denominator > EPSILON_DEN,
                "planners": planners,
            }
        )
        if number % 10 == 0:
            print(f"exact {number}/{len(seeds)}", flush=True)
    return {"metadata": metadata(), "suite": suite_manifest("exact"), "units": units}


def run_practical(seeds=PRACTICAL_SEEDS) -> dict:
    units = []
    for number, seed in enumerate(seeds, 1):
        scenario = generate_gate6_scenario(seed, "practical")
        config_id = uncertainty_for_seed(seed, "practical")
        config = get_uncertainty_config(config_id)
        planners = {
            name: run_episode(scenario, config, name) for name in PRACTICAL_NAMES
        }
        units.append(
            {
                "generator_seed": seed,
                "scenario_id": scenario.scenario_id,
                "environment_root_seed": scenario.seed,
                "uncertainty_config_id": config_id,
                "replication_id": 0,
                "planners": planners,
            }
        )
        if number % 10 == 0:
            print(f"practical {number}/{len(seeds)}", flush=True)
    return {"metadata": metadata(), "suite": suite_manifest("practical"), "units": units}


def _latency_summary(values: list[int]) -> dict:
    milliseconds = [value / 1_000_000 for value in values]
    return {
        "n": len(milliseconds),
        "mean_ms": statistics.fmean(milliseconds),
        "median_ms": _quantile(milliseconds, 0.50),
        "p90_ms": _quantile(milliseconds, 0.90),
        "p95_ms": _quantile(milliseconds, 0.95),
        "maximum_ms": max(milliseconds),
    }


def _planner_summary(units: list[dict], name: str, exact: bool) -> dict:
    rows = [unit["planners"][name] for unit in units]
    result = {
        "mean_utility": statistics.fmean(row["utility"] for row in rows),
        "mean_safe_population_fraction": statistics.fmean(
            row["safe_population_fraction"] for row in rows
        ),
        "mean_exposed_person_timesteps": statistics.fmean(
            row["exposed_person_timesteps"] for row in rows
        ),
        "mean_in_transit_person_minutes": statistics.fmean(
            row["in_transit_person_minutes"] for row in rows
        ),
        "latency": _latency_summary(
            [value for row in rows for value in row["decision_latency_ns"]]
        ),
        "nodes_evaluated": sum(row["nodes_evaluated"] for row in rows),
        "model_transitions": sum(row["model_transitions"] for row in rows),
        "mask_diagnostics": {},
    }
    for row in rows:
        result["mask_diagnostics"] = _sum_counts(
            result["mask_diagnostics"], row["mask_diagnostics"]
        )
    if exact:
        values = [row["nsu_exact"] for row in rows if row["nsu_exact"] is not None]
        result["valid_nsu_units"] = len(values)
        result["median_nsu_exact"] = _quantile(values, 0.50) if values else None
        result["p10_nsu_exact"] = _quantile(values, 0.10) if values else None
        result["mean_nsu_exact"] = statistics.fmean(values) if values else None
    return result


def summarize(exact: dict, practical: dict) -> dict:
    exact_units = exact["units"]
    invalid = sum(not unit["normalization_valid"] for unit in exact_units)
    timeouts = sum(bool(unit["oracle"].get("timed_out")) for unit in exact_units)
    exact_summary = {
        name: _planner_summary(exact_units, name, True) for name in PRACTICAL_NAMES
    }
    practical_summary = {
        name: _planner_summary(practical["units"], name, False)
        for name in PRACTICAL_NAMES
    }
    by_regime = {}
    for config_id in ("v3-low-v1", "v3-medium-v1", "v3-high-v1"):
        regime_units = [
            unit for unit in exact_units if unit["uncertainty_config_id"] == config_id
        ]
        by_regime[config_id] = {
            name: _planner_summary(regime_units, name, True) for name in PRACTICAL_NAMES
        }
    gate_failure = invalid / len(exact_units) > 0.05 or timeouts / len(exact_units) > 0.05
    qualifying = []
    for name in PRACTICAL_NAMES[1:]:
        values = exact_summary[name]
        if (
            values["median_nsu_exact"] is not None
            and values["median_nsu_exact"] >= 0.99
            and values["p10_nsu_exact"] >= 0.97
            and values["latency"]["p95_ms"] <= 100.0
        ):
            qualifying.append(name)
    verdict = "INCONCLUSIVE_GATE" if gate_failure else "STOP_RL" if qualifying else "PROCEED_TO_RL"
    return {
        "metadata": metadata(),
        "gate_thresholds": {
            "median_nsu_exact_minimum": 0.99,
            "p10_nsu_exact_minimum": 0.97,
            "p95_latency_ms_maximum": 100.0,
            "epsilon_den": EPSILON_DEN,
        },
        "exact_units": len(exact_units),
        "invalid_normalization_units": invalid,
        "oracle_timeouts": timeouts,
        "exact_planners": exact_summary,
        "by_uncertainty": by_regime,
        "practical_planners": practical_summary,
        "qualifying_planners": qualifying,
        "gate_verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="development smoke limit")
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    warm_up()
    exact_seeds = EXACT_SEEDS[: args.limit] if args.limit else EXACT_SEEDS
    practical_seeds = PRACTICAL_SEEDS[: args.limit] if args.limit else PRACTICAL_SEEDS
    exact = run_exact(exact_seeds)
    practical = run_practical(practical_seeds)
    if args.limit:
        print(json.dumps({"exact_units": len(exact["units"]), "practical_units": len(practical["units"])}, indent=2))
        return 0
    dump_suite(EXACT_SUITE_PATH, "exact")
    dump_suite(PRACTICAL_SUITE_PATH, "practical")
    summary = summarize(exact, practical)
    EXACT_PATH.write_text(json.dumps(exact, indent=2) + "\n")
    PRACTICAL_PATH.write_text(json.dumps(practical, indent=2) + "\n")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
