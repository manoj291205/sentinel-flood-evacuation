"""Run the post-10A frozen Sentinel-Agent V3 held-out evaluation.

This module has no training import and contains no optimizer/learning call. Expensive
policy passes are independently resumable; ``all`` executes missing passes in order.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import multiprocessing as mp
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from sb3_contrib import MaskablePPO

from src.env_v3 import EvacuationEnvV3, FrozenV3RewardProvider
from src.evaluation_v3.config import (
    FROZEN_PHASE10_CONFIG,
    HELDOUT_GENERATOR_VERSION,
    PPO_TRAINING_SEEDS,
    PRACTICAL_POLICIES,
    RANDOM_POLICY_SEEDS,
    STRESS_TYPES,
    UNCERTAINTY_IDS,
)
from src.evaluation_v3.generator import (
    generate_evaluation_scenario,
    heldout_manifest,
    permutation_manifest,
    permute_heldout_scenario,
    stress_manifest,
)
from src.evaluation_v3.metrics import (
    BootstrapInterval,
    cvar_10,
    decide_rl_usefulness,
    gate_passes,
    linear_quantile,
    normalised_safe_utility,
    relative_exposure_reduction,
    tail_nsu,
)
from src.evaluation_v3.observation_matched import ObservationMatchedGreedy
from src.evaluation_v3.stress import apply_stress_intervention
from src.planners import (
    EpisodeLedger,
    LookaheadK2Planner,
    LookaheadK3Planner,
    NearestSafePlanner,
    RandomValidPlanner,
    RiskGreedyPlanner,
    SampledMPCPlanner,
    build_planner_input,
)
from src.safety import V3_SAFETY_V1, evaluate_actions
from src.sim import DispatchAction, DispatchStatus, StochasticSimulator, get_uncertainty_config


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "eval_v3" / "phase10"
FIGURES = ROOT / "artifacts" / "figures" / "phase10"
STAGE10A_COMMIT = "c92173dc0001e60cd7db69d89fab8f391d202905"
HELDOUT_MANIFEST = OUTPUT / "heldout_manifest.json"
PERMUTATION_MANIFEST = OUTPUT / "permutation_manifest.json"
STRESS_MANIFEST = OUTPUT / "stress_manifest.json"
NUMERIC_METRICS = (
    "episode_return",
    "safe_population_fraction",
    "exposed_person_timesteps",
    "mean_time_to_safety",
    "mean_travel_person_minutes",
    "completion",
    "unsafe_dispatch_rate_zero_filled",
    "capacity_violation_rate",
    "route_failure_rate",
)


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read(path: Path) -> Any:
    return json.loads(path.read_text())


def metadata() -> dict[str, Any]:
    source_paths = [
        ROOT / "V3_PHASE10_EVAL_SPEC.md",
        ROOT / "scripts" / "run_phase10.py",
        ROOT / "src" / "planners" / "lookahead.py",
        ROOT / "src" / "planners" / "model.py",
        ROOT / "src" / "planners" / "mpc.py",
        ROOT / "src" / "sim" / "stochastic.py",
        ROOT / "src" / "env_v3" / "evacuation_env.py",
        *sorted((ROOT / "src" / "evaluation_v3").glob("*.py")),
    ]
    source_hash = hashlib.sha256()
    for path in source_paths:
        source_hash.update(str(path.relative_to(ROOT)).encode())
        source_hash.update(path.read_bytes())
    return {
        "phase10_spec_version": FROZEN_PHASE10_CONFIG.spec_version,
        "stage10a_commit": STAGE10A_COMMIT,
        "evaluation_parent_commit": STAGE10A_COMMIT,
        "evaluation_source_sha256": source_hash.hexdigest(),
        "evaluation_source_note": "Evaluation code is recorded in the Phase 10B result commit; hash covers the pre-commit source tree.",
        "normalisation": "practical",
        "reward": "v3-reward-balanced-v1",
        "safety": "v3-safety-v1",
        "hard_safety": True,
        "replication_id": 0,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "timing_clock": "time.perf_counter_ns",
        "artifact_note": "Synthetic V3 evaluation; not real emergency-response evidence.",
    }


def generate_manifests() -> None:
    if any(path.exists() for path in (HELDOUT_MANIFEST, PERMUTATION_MANIFEST, STRESS_MANIFEST)):
        raise RuntimeError("refusing to overwrite an existing frozen Phase 10 manifest")
    _write(HELDOUT_MANIFEST, heldout_manifest())
    _write(PERMUTATION_MANIFEST, permutation_manifest())
    _write(STRESS_MANIFEST, stress_manifest())


def _scenario_from_entry(entry: dict[str, Any]):
    generated = generate_evaluation_scenario(
        int(entry["generator_seed"]),
        suite=str(entry["suite"]),
        uncertainty_config_id=str(entry["uncertainty_config_id"]),
        stress_type=entry.get("stress_type"),
    )
    encoded = json.dumps(generated.scenario.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    if generated.scenario.scenario_id != entry["scenario_id"]:
        raise RuntimeError("manifest scenario identity mismatch")
    if hashlib.sha256(encoded).hexdigest() != entry["scenario_sha256"]:
        raise RuntimeError("regenerated scenario differs from frozen manifest")
    return generated.scenario


def _stable_random_seed(master: int, scenario_id: str) -> int:
    payload = f"phase10-random-policy-v1|{master}|{scenario_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _planner(name: str, scenario_id: str, policy_seed: int = RANDOM_POLICY_SEEDS[0]):
    if name == "random_valid":
        return RandomValidPlanner(_stable_random_seed(policy_seed, scenario_id))
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


def _intervention(stress_type: str | None):
    if stress_type is None:
        return None
    return functools.partial(apply_stress_intervention, stress_type=stress_type)


def _final_metrics(
    scenario,
    state,
    ledger: EpisodeLedger,
    episode_return: float,
    *,
    decisions: int,
    dispatches: int,
    unsafe_dispatches: int,
    capacity_violations: int,
    route_failures: int,
    invalid_masked_actions: int,
    closed_route_dispatches: int,
    latencies_ns: list[int],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    population = state.initial_evacuation_population
    horizon_minutes = scenario.time.horizon_steps * scenario.time.timestep_minutes
    safe_time_total = 0.0
    travel_total = 0.0
    for event in state.dispatch_events:
        if event.status is DispatchStatus.ARRIVED:
            safe_time_total += event.people * min(
                event.arrival_timestep * scenario.time.timestep_minutes, horizon_minutes
            )
            travel_total += event.people * event.realized_travel_time_minutes
        else:
            elapsed = max(
                0.0,
                horizon_minutes - event.departure_timestep * scenario.time.timestep_minutes,
            )
            travel_total += event.people * min(event.realized_travel_time_minutes, elapsed)
    unfinished = population - state.people_safely_arrived
    safe_time_total += unfinished * horizon_minutes
    return {
        "episode_return": episode_return,
        "safe_population_fraction": state.people_safely_arrived / population,
        "safe_population": state.people_safely_arrived,
        "initial_population": population,
        "exposed_person_timesteps": ledger.exposed_person_timesteps,
        "exposed_person_minutes": ledger.exposed_person_timesteps * scenario.time.timestep_minutes,
        "mean_time_to_safety": safe_time_total / population,
        "mean_travel_person_minutes": travel_total / population,
        "completion": float(state.people_safely_arrived == population),
        "decisions": decisions,
        "dispatches": dispatches,
        "unsafe_dispatches": unsafe_dispatches,
        "unsafe_dispatch_rate": unsafe_dispatches / dispatches if dispatches else None,
        "unsafe_dispatch_rate_zero_filled": unsafe_dispatches / dispatches if dispatches else 0.0,
        "capacity_violations": capacity_violations,
        "capacity_violation_rate": capacity_violations / dispatches if dispatches else 0.0,
        "route_failures": route_failures,
        "route_failure_rate": route_failures / dispatches if dispatches else 0.0,
        "closed_route_dispatches": closed_route_dispatches,
        "invalid_masked_actions": invalid_masked_actions,
        "decision_latency_ns": latencies_ns,
        "actions": actions,
    }


def run_planner_episode(
    scenario,
    uncertainty_config_id: str,
    planner_name: str,
    *,
    policy_seed: int = RANDOM_POLICY_SEEDS[0],
    stress_type: str | None = None,
) -> dict[str, Any]:
    config = get_uncertainty_config(uncertainty_config_id)
    simulator = StochasticSimulator(
        scenario, config, replication_id=0, intervention=_intervention(stress_type)
    )
    planner = _planner(planner_name, scenario.scenario_id, policy_seed)
    reward_provider = FrozenV3RewardProvider()
    ledger = EpisodeLedger()
    episode_return = 0.0
    dispatches = unsafe = capacity = failures = invalid = closed = decisions = 0
    latencies: list[int] = []
    actions: list[dict[str, Any]] = []
    while not simulator.state.terminal:
        simulator.observe()
        state = simulator.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state, V3_SAFETY_V1)
        planner_input = build_planner_input(scenario, state, snapshot, config)
        ledger.observe(state)
        decision = planner.choose_action(planner_input)
        index = snapshot.canonical_actions.index(decision.action)
        permitted = bool(snapshot.allowed_mask[index])
        invalid += int(not permitted)
        if isinstance(decision.action, DispatchAction):
            dispatches += 1
            unsafe += int(not permitted)
            route = next(
                item for item in state.routes
                if item.source_zone_id == decision.action.zone_id
                and item.destination_shelter_id == decision.action.shelter_id
            )
            closed += int(not route.reachable_current)
        if not permitted:
            raise AssertionError(f"{planner_name} selected an excluded action")
        previous = state
        result = simulator.step(decision.action)
        if not result.accepted:
            raise AssertionError(f"{planner_name} action failed simulator validation")
        episode_return += reward_provider.calculate(previous, result, result.state, scenario).total_reward
        capacity += int(any(item.capacity_available < 0 for item in result.state.shelters))
        latencies.append(decision.decision_latency_ns)
        action = decision.action.to_dict()
        if isinstance(decision.action, DispatchAction):
            action["physical_zone"] = next(item.location.node_id for item in scenario.zones if item.zone_id == decision.action.zone_id)
            action["physical_shelter"] = next(item.location.node_id for item in scenario.shelters if item.shelter_id == decision.action.shelter_id)
        actions.append(action)
        decisions += 1
    return _final_metrics(
        scenario,
        simulator.state,
        ledger,
        episode_return,
        decisions=decisions,
        dispatches=dispatches,
        unsafe_dispatches=unsafe,
        capacity_violations=capacity,
        route_failures=failures,
        invalid_masked_actions=invalid,
        closed_route_dispatches=closed,
        latencies_ns=latencies,
        actions=actions,
    )


def run_index_policy_episode(
    scenario,
    uncertainty_config_id: str,
    *,
    model=None,
    observation_matched: ObservationMatchedGreedy | None = None,
    stress_type: str | None = None,
) -> dict[str, Any]:
    if (model is None) == (observation_matched is None):
        raise ValueError("provide exactly one index policy")
    env = EvacuationEnvV3(
        scenario,
        uncertainty_config=uncertainty_config_id,
        reward_provider=FrozenV3RewardProvider(),
        simulator_intervention=_intervention(stress_type),
    )
    observation, _ = env.reset(seed=0)
    env.assert_training_ready()
    ledger = EpisodeLedger()
    episode_return = 0.0
    dispatches = unsafe = capacity = failures = invalid = closed = decisions = 0
    latencies: list[int] = []
    actions: list[dict[str, Any]] = []
    terminated = truncated = False
    while not (terminated or truncated):
        state = env.current_state
        snapshot = evaluate_actions(scenario, state, V3_SAFETY_V1)
        mask = env.action_masks()
        ledger.observe(state)
        if model is not None:
            started = time.perf_counter_ns()
            selected, _ = model.predict(observation, action_masks=mask, deterministic=True)
            latency = time.perf_counter_ns() - started
            action_index = int(np.asarray(selected).item())
        else:
            assert observation_matched is not None
            decision = observation_matched.choose_action(observation, mask, env.action_mapping)
            action_index = decision.action_index
            latency = decision.decision_latency_ns
        requested = env.action_mapping.decode_action(action_index)
        permitted = bool(mask[action_index])
        invalid += int(not permitted)
        if isinstance(requested.semantic, DispatchAction):
            dispatches += 1
            unsafe += int(not permitted)
            route = next(
                item for item in state.routes
                if item.source_zone_id == requested.zone_id
                and item.destination_shelter_id == requested.shelter_id
            )
            closed += int(not route.reachable_current)
        observation, reward, terminated, truncated, info = env.step(action_index)
        episode_return += float(reward)
        capacity += int(any(item.capacity_available < 0 for item in env.current_state.shelters))
        latencies.append(latency)
        action = requested.to_dict()
        if requested.zone_id is not None and requested.shelter_id is not None:
            action["physical_zone"] = next(item.location.node_id for item in scenario.zones if item.zone_id == requested.zone_id)
            action["physical_shelter"] = next(item.location.node_id for item in scenario.shelters if item.shelter_id == requested.shelter_id)
        actions.append(action)
        decisions += 1
    return _final_metrics(
        scenario,
        env.current_state,
        ledger,
        episode_return,
        decisions=decisions,
        dispatches=dispatches,
        unsafe_dispatches=unsafe,
        capacity_violations=capacity,
        route_failures=failures,
        invalid_masked_actions=invalid,
        closed_route_dispatches=closed,
        latencies_ns=latencies,
        actions=actions,
    )


def _average_random_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        metric: statistics.fmean(float(row[metric]) for row in runs)
        for metric in NUMERIC_METRICS
    }
    for metric in (
        "safe_population",
        "initial_population",
        "decisions",
        "dispatches",
        "unsafe_dispatches",
        "capacity_violations",
        "route_failures",
        "closed_route_dispatches",
        "invalid_masked_actions",
        "exposed_person_minutes",
    ):
        result[metric] = statistics.fmean(float(row[metric]) for row in runs)
    result["unsafe_dispatch_rate"] = result["unsafe_dispatch_rate_zero_filled"]
    result["decision_latency_ns"] = [value for row in runs for value in row["decision_latency_ns"]]
    result["actions"] = []
    result["random_seed_returns"] = {
        str(seed): run["episode_return"] for seed, run in zip(RANDOM_POLICY_SEEDS, runs)
    }
    return result


def _result_row(
    entry: dict[str, Any],
    policy: str,
    values: dict[str, Any],
    *,
    training_seed: int | None = None,
) -> dict[str, Any]:
    return {
        "scenario_id": entry["scenario_id"],
        "scenario_seed": entry["scenario_root_seed"],
        "generator_seed": entry["generator_seed"],
        "replication_id": entry["replication_id"],
        "uncertainty_config_id": entry["uncertainty_config_id"],
        "stress_type": entry.get("stress_type"),
        "policy": policy,
        "training_seed": training_seed,
        **values,
    }


def _planner_task(task: tuple[dict[str, Any], str]) -> dict[str, Any]:
    entry, policy = task
    scenario = _scenario_from_entry(entry)
    if policy == "random_valid":
        runs = [
            run_planner_episode(
                scenario,
                entry["uncertainty_config_id"],
                policy,
                policy_seed=seed,
                stress_type=entry.get("stress_type"),
            )
            for seed in RANDOM_POLICY_SEEDS
        ]
        values = _average_random_runs(runs)
    elif policy == "observation_matched_greedy":
        values = run_index_policy_episode(
            scenario,
            entry["uncertainty_config_id"],
            observation_matched=ObservationMatchedGreedy(),
            stress_type=entry.get("stress_type"),
        )
    else:
        values = run_planner_episode(
            scenario,
            entry["uncertainty_config_id"],
            policy,
            stress_type=entry.get("stress_type"),
        )
    return _result_row(entry, policy, values)


def evaluate_planner_policy(suite: str, policy: str, workers: int) -> Path:
    manifest_path = HELDOUT_MANIFEST if suite == "heldout" else STRESS_MANIFEST
    entries = _read(manifest_path)["entries"]
    suffix = "normal" if suite == "heldout" else "stress"
    path = OUTPUT / f"_{suffix}_{policy}.json"
    if path.exists():
        print(f"reuse {path.name}", flush=True)
        return path
    partial = path.with_suffix(".partial.json")
    rows: list[dict[str, Any]] = _read(partial)["rows"] if partial.exists() else []
    completed = {row["scenario_id"] for row in rows}
    tasks = [(entry, policy) for entry in entries if entry["scenario_id"] not in completed]
    order = {entry["scenario_id"]: entry["index"] for entry in entries}
    context = mp.get_context("spawn")
    with context.Pool(processes=workers) as pool:
        for number, row in enumerate(
            pool.imap_unordered(_planner_task, tasks), len(rows) + 1
        ):
            rows.append(row)
            if number % 10 == 0:
                _write(partial, {"policy": policy, "rows": rows})
                print(f"{suffix} {policy}: {number}/{len(entries)}", flush=True)
    rows.sort(key=lambda row: order[row["scenario_id"]])
    _write(path, {"metadata": metadata(), "policy": policy, "rows": rows})
    partial.unlink(missing_ok=True)
    return path


def evaluate_ppo_policy(suite: str, training_seed: int) -> Path:
    manifest_path = HELDOUT_MANIFEST if suite == "heldout" else STRESS_MANIFEST
    entries = _read(manifest_path)["entries"]
    suffix = "normal" if suite == "heldout" else "stress"
    path = OUTPUT / f"_{suffix}_ppo_{training_seed}.json"
    if path.exists():
        print(f"reuse {path.name}", flush=True)
        return path
    model_path = ROOT / "models" / "v3" / f"ppo_seed{training_seed}_best.zip"
    model = MaskablePPO.load(model_path, device="cpu")
    rows = []
    for number, entry in enumerate(entries, 1):
        scenario = _scenario_from_entry(entry)
        values = run_index_policy_episode(
            scenario,
            entry["uncertainty_config_id"],
            model=model,
            stress_type=entry.get("stress_type"),
        )
        rows.append(_result_row(entry, "ppo", values, training_seed=training_seed))
        if number % 25 == 0:
            print(f"{suffix} ppo {training_seed}: {number}/{len(entries)}", flush=True)
    _write(path, {"metadata": metadata(), "policy": "ppo", "training_seed": training_seed, "rows": rows})
    return path


def _aggregate_ppo_rows(seed_rows: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for index in range(len(next(iter(seed_rows.values())))):
        members = [seed_rows[seed][index] for seed in PPO_TRAINING_SEEDS]
        scenario_ids = {row["scenario_id"] for row in members}
        if len(scenario_ids) != 1:
            raise RuntimeError("PPO seed rows are not scenario aligned")
        base = {
            key: members[0][key]
            for key in (
                "scenario_id",
                "scenario_seed",
                "generator_seed",
                "replication_id",
                "uncertainty_config_id",
                "stress_type",
            )
        }
        values = {
            metric: statistics.fmean(float(row[metric]) for row in members)
            for metric in NUMERIC_METRICS
        }
        for metric in (
            "safe_population",
            "initial_population",
            "decisions",
            "dispatches",
            "unsafe_dispatches",
            "capacity_violations",
            "route_failures",
            "closed_route_dispatches",
            "invalid_masked_actions",
            "exposed_person_minutes",
        ):
            values[metric] = statistics.fmean(float(row[metric]) for row in members)
        values["unsafe_dispatch_rate"] = values["unsafe_dispatch_rate_zero_filled"]
        values["decision_latency_ns"] = [
            value for row in members for value in row["decision_latency_ns"]
        ]
        values["actions"] = []
        rows.append({**base, "policy": "ppo_family", "training_seed": None, **values})
    return rows


def _summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(row["episode_return"]) for row in rows]
    summary = {
        "n": len(rows),
        "mean_episode_return": statistics.fmean(returns),
        "median_episode_return": statistics.median(returns),
        "std_episode_return": statistics.stdev(returns) if len(returns) > 1 else 0.0,
        "p10_episode_return": linear_quantile(returns, 0.10),
        "worst_decile_return": linear_quantile(returns, 0.10),
        "cvar_10": cvar_10(returns),
        "mean_safe_population_fraction": statistics.fmean(float(row["safe_population_fraction"]) for row in rows),
        "mean_exposed_person_timesteps": statistics.fmean(float(row["exposed_person_timesteps"]) for row in rows),
        "mean_time_to_safety": statistics.fmean(float(row["mean_time_to_safety"]) for row in rows),
        "mean_travel_person_minutes": statistics.fmean(float(row["mean_travel_person_minutes"]) for row in rows),
        "evacuation_completion_rate": statistics.fmean(float(row["completion"]) for row in rows),
        "safe_population_fraction_micro": sum(float(row["safe_population"]) for row in rows) / sum(float(row["initial_population"]) for row in rows),
        "unsafe_dispatches": sum(float(row["unsafe_dispatches"]) for row in rows),
        "dispatches": sum(float(row["dispatches"]) for row in rows),
        "capacity_violations": sum(float(row["capacity_violations"]) for row in rows),
        "route_failures": sum(float(row["route_failures"]) for row in rows),
        "closed_route_dispatches": sum(float(row["closed_route_dispatches"]) for row in rows),
        "invalid_masked_actions": sum(float(row["invalid_masked_actions"]) for row in rows),
    }
    summary["unsafe_dispatch_rate"] = summary["unsafe_dispatches"] / summary["dispatches"] if summary["dispatches"] else None
    summary["capacity_violation_rate"] = summary["capacity_violations"] / summary["dispatches"] if summary["dispatches"] else 0.0
    summary["route_failure_rate"] = summary["route_failures"] / summary["dispatches"] if summary["dispatches"] else 0.0
    return summary


def _aligned(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {str(row["scenario_id"]): row for row in rows}
    if len(result) != len(rows):
        raise RuntimeError("duplicate scenario result")
    return result


def _macro_nsu(
    policy: Sequence[dict[str, Any]],
    lower: Sequence[dict[str, Any]],
    upper: Sequence[dict[str, Any]],
) -> float | None:
    estimates = []
    for config_id in UNCERTAINTY_IDS:
        p = [row["episode_return"] for row in policy if row["uncertainty_config_id"] == config_id]
        l = [row["episode_return"] for row in lower if row["uncertainty_config_id"] == config_id]
        u = [row["episode_return"] for row in upper if row["uncertainty_config_id"] == config_id]
        value = normalised_safe_utility(p, l, u)
        if value is None:
            return None
        estimates.append(value)
    return statistics.fmean(estimates)


def _bootstrap_effects(
    ppo_by_seed: dict[int, list[dict[str, Any]]],
    baseline_rows: list[dict[str, Any]],
    lower_rows: list[dict[str, Any]],
    *,
    config_id: str | None = None,
    stress_type: str | None = None,
    resamples: int | None = None,
) -> dict[str, BootstrapInterval]:
    draws = resamples or FROZEN_PHASE10_CONFIG.bootstrap_resamples
    seed_maps = {seed: _aligned(rows) for seed, rows in ppo_by_seed.items()}
    baseline_map = _aligned(baseline_rows)
    lower_map = _aligned(lower_rows)
    ids = [
        scenario_id for scenario_id, row in baseline_map.items()
        if (config_id is None or row["uncertainty_config_id"] == config_id)
        and (stress_type is None or row.get("stress_type") == stress_type)
    ]
    if set(ids) - set(lower_map) or any(set(ids) - set(values) for values in seed_maps.values()):
        raise RuntimeError("paired bootstrap rows are incomplete")

    def calculate(sampled_seeds: Sequence[int], sampled_ids: Sequence[str]) -> dict[str, float | None]:
        policy_returns = [statistics.fmean(seed_maps[seed][item]["episode_return"] for seed in sampled_seeds) for item in sampled_ids]
        policy_exposure = [statistics.fmean(seed_maps[seed][item]["exposed_person_timesteps"] for seed in sampled_seeds) for item in sampled_ids]
        policy_unsafe = [statistics.fmean(seed_maps[seed][item]["unsafe_dispatch_rate_zero_filled"] for seed in sampled_seeds) for item in sampled_ids]
        baseline_returns = [baseline_map[item]["episode_return"] for item in sampled_ids]
        baseline_exposure = [baseline_map[item]["exposed_person_timesteps"] for item in sampled_ids]
        baseline_unsafe = [baseline_map[item]["unsafe_dispatch_rate_zero_filled"] for item in sampled_ids]
        lower_returns = [lower_map[item]["episode_return"] for item in sampled_ids]
        denominator = statistics.fmean(baseline_returns) - statistics.fmean(lower_returns)
        nsu_difference = None if denominator <= FROZEN_PHASE10_CONFIG.epsilon_den else (statistics.fmean(policy_returns) - statistics.fmean(baseline_returns)) / denominator
        exposure = relative_exposure_reduction(statistics.fmean(policy_exposure), statistics.fmean(baseline_exposure))
        policy_tail = tail_nsu(policy_returns, lower_returns, baseline_returns)
        tail_difference = None if policy_tail is None else policy_tail - 1.0
        return {
            "nsu_difference": nsu_difference,
            "exposure_reduction": exposure,
            "tail_nsu_difference": tail_difference,
            "unsafe_difference": statistics.fmean(policy_unsafe) - statistics.fmean(baseline_unsafe),
        }

    estimates = calculate(list(PPO_TRAINING_SEEDS), ids)
    position = {item: index for index, item in enumerate(ids)}
    ppo_return = np.asarray(
        [[seed_maps[seed][item]["episode_return"] for item in ids] for seed in PPO_TRAINING_SEEDS],
        dtype=float,
    )
    ppo_exposure = np.asarray(
        [[seed_maps[seed][item]["exposed_person_timesteps"] for item in ids] for seed in PPO_TRAINING_SEEDS],
        dtype=float,
    )
    ppo_unsafe = np.asarray(
        [[seed_maps[seed][item]["unsafe_dispatch_rate_zero_filled"] for item in ids] for seed in PPO_TRAINING_SEEDS],
        dtype=float,
    )
    baseline_return = np.asarray([baseline_map[item]["episode_return"] for item in ids], dtype=float)
    baseline_exposure = np.asarray([baseline_map[item]["exposed_person_timesteps"] for item in ids], dtype=float)
    baseline_unsafe = np.asarray([baseline_map[item]["unsafe_dispatch_rate_zero_filled"] for item in ids], dtype=float)
    lower_return = np.asarray([lower_map[item]["episode_return"] for item in ids], dtype=float)
    rng = np.random.default_rng(
        FROZEN_PHASE10_CONFIG.bootstrap_seed
        + (0 if config_id is None else UNCERTAINTY_IDS.index(config_id) + 1)
    )
    arrays: dict[str, list[np.ndarray]] = {key: [] for key in estimates}
    strata = UNCERTAINTY_IDS if config_id is None else (config_id,)
    stratum_positions = [
        np.asarray(
            [position[item] for item in ids if baseline_map[item]["uncertainty_config_id"] == stratum],
            dtype=int,
        )
        for stratum in strata
    ]
    produced = 0
    while produced < draws:
        batch = min(250, draws - produced)
        sampled_seeds = rng.integers(0, len(PPO_TRAINING_SEEDS), size=(batch, len(PPO_TRAINING_SEEDS)))
        sampled_scenarios = np.concatenate(
            [members[rng.integers(0, len(members), size=(batch, len(members)))] for members in stratum_positions],
            axis=1,
        )
        policy_return = ppo_return[
            sampled_seeds[:, :, None], sampled_scenarios[:, None, :]
        ].mean(axis=1)
        policy_exposure = ppo_exposure[
            sampled_seeds[:, :, None], sampled_scenarios[:, None, :]
        ].mean(axis=1)
        policy_unsafe = ppo_unsafe[
            sampled_seeds[:, :, None], sampled_scenarios[:, None, :]
        ].mean(axis=1)
        base_return = baseline_return[sampled_scenarios]
        base_exposure = baseline_exposure[sampled_scenarios]
        base_unsafe = baseline_unsafe[sampled_scenarios]
        random_return = lower_return[sampled_scenarios]
        denominator = base_return.mean(axis=1) - random_return.mean(axis=1)
        arrays["nsu_difference"].append(
            np.where(
                denominator > FROZEN_PHASE10_CONFIG.epsilon_den,
                (policy_return.mean(axis=1) - base_return.mean(axis=1)) / denominator,
                np.nan,
            )
        )
        mean_base_exposure = base_exposure.mean(axis=1)
        arrays["exposure_reduction"].append(
            np.where(
                mean_base_exposure > 0,
                (mean_base_exposure - policy_exposure.mean(axis=1)) / mean_base_exposure,
                np.nan,
            )
        )
        tail_count = max(1, int(0.1 * sampled_scenarios.shape[1]))
        policy_tail = np.partition(policy_return, tail_count - 1, axis=1)[:, :tail_count].mean(axis=1)
        base_tail = np.partition(base_return, tail_count - 1, axis=1)[:, :tail_count].mean(axis=1)
        random_tail = np.partition(random_return, tail_count - 1, axis=1)[:, :tail_count].mean(axis=1)
        tail_denominator = base_tail - random_tail
        arrays["tail_nsu_difference"].append(
            np.where(
                tail_denominator > FROZEN_PHASE10_CONFIG.epsilon_den,
                (policy_tail - random_tail) / tail_denominator - 1.0,
                np.nan,
            )
        )
        arrays["unsafe_difference"].append(
            policy_unsafe.mean(axis=1) - base_unsafe.mean(axis=1)
        )
        produced += batch
    values = {
        key: np.concatenate(parts) for key, parts in arrays.items()
    }
    result = {}
    for key, estimate in estimates.items():
        valid = values[key][np.isfinite(values[key])]
        invalid = draws - len(valid)
        if invalid / draws > FROZEN_PHASE10_CONFIG.maximum_invalid_bootstrap_fraction:
            result[key] = BootstrapInterval(estimate, None, None, len(valid), invalid)
        else:
            result[key] = BootstrapInterval(
                estimate,
                float(np.quantile(valid, 0.025, method="linear")),
                float(np.quantile(valid, 0.975, method="linear")),
                len(valid),
                invalid,
            )
    return result


def _gate_from_effects(
    effects: dict[str, BootstrapInterval],
    ppo_rows: Sequence[dict[str, Any]],
    baseline_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    ppo_summary = _summary(ppo_rows)
    baseline_summary = _summary(baseline_rows)
    passed, benefits = gate_passes(
        nsu_difference=effects["nsu_difference"].estimate,
        nsu_interval=effects["nsu_difference"],
        exposure_reduction=effects["exposure_reduction"].estimate,
        exposure_interval=effects["exposure_reduction"],
        tail_nsu_difference=effects["tail_nsu_difference"].estimate,
        tail_interval=effects["tail_nsu_difference"],
        ppo_unsafe_rate=float(ppo_summary["unsafe_dispatch_rate"] or 0.0),
        baseline_unsafe_rate=float(baseline_summary["unsafe_dispatch_rate"] or 0.0),
        unsafe_interval=effects["unsafe_difference"],
    )
    return {
        "passes": passed,
        "supported_benefits": list(benefits),
        "effects": {key: value.to_dict() for key, value in effects.items()},
    }


def summarize_normal() -> None:
    planner_rows = {
        policy: _read(OUTPUT / f"_normal_{policy}.json")["rows"]
        for policy in (*PRACTICAL_POLICIES, "observation_matched_greedy")
    }
    ppo_by_seed = {
        seed: _read(OUTPUT / f"_normal_ppo_{seed}.json")["rows"]
        for seed in PPO_TRAINING_SEEDS
    }
    ppo_family = _aggregate_ppo_rows(ppo_by_seed)
    lower = planner_rows["random_valid"]
    baseline = planner_rows[FROZEN_PHASE10_CONFIG.principal_comparator]
    ids = [row["scenario_id"] for row in lower]
    for rows in [*planner_rows.values(), *ppo_by_seed.values(), ppo_family]:
        if [row["scenario_id"] for row in rows] != ids:
            raise RuntimeError("ordinary result rows are not exactly aligned")

    all_rows = [row for rows in planner_rows.values() for row in rows]
    all_rows += [row for rows in ppo_by_seed.values() for row in rows]
    _write(
        OUTPUT / "heldout_raw_results.json",
        {"metadata": metadata(), "rows": all_rows},
    )

    policy_summaries = {}
    for policy, rows in {**planner_rows, "ppo_family": ppo_family}.items():
        value = _summary(rows)
        value["nsu_practical"] = _macro_nsu(rows, lower, baseline)
        value["normalisation"] = "practical"
        policy_summaries[policy] = value
    _write(
        OUTPUT / "planner_summary.json",
        {
            "metadata": metadata(),
            "principal_comparator": FROZEN_PHASE10_CONFIG.principal_comparator,
            "policies": {key: policy_summaries[key] for key in planner_rows},
        },
    )

    seed_summaries = {}
    for seed, rows in ppo_by_seed.items():
        value = _summary(rows)
        value["nsu_practical"] = _macro_nsu(rows, lower, baseline)
        seed_summaries[str(seed)] = value
    principal_metrics = (
        "nsu_practical",
        "mean_safe_population_fraction",
        "mean_exposed_person_timesteps",
        "cvar_10",
        "evacuation_completion_rate",
    )
    across = {
        metric: {
            "mean": statistics.fmean(seed_summaries[str(seed)][metric] for seed in PPO_TRAINING_SEEDS),
            "std": statistics.pstdev(seed_summaries[str(seed)][metric] for seed in PPO_TRAINING_SEEDS),
            "min": min(seed_summaries[str(seed)][metric] for seed in PPO_TRAINING_SEEDS),
            "max": max(seed_summaries[str(seed)][metric] for seed in PPO_TRAINING_SEEDS),
        }
        for metric in principal_metrics
    }
    _write(
        OUTPUT / "ppo_seed_summary.json",
        {"metadata": metadata(), "seeds": seed_summaries, "across_seed": across, "representative_seed": 4404},
    )

    uncertainty = {}
    for config_id in UNCERTAINTY_IDS:
        uncertainty[config_id] = {}
        for policy, rows in {**planner_rows, "ppo_family": ppo_family}.items():
            selected = [row for row in rows if row["uncertainty_config_id"] == config_id]
            value = _summary(selected)
            selected_lower = [row for row in lower if row["uncertainty_config_id"] == config_id]
            selected_upper = [row for row in baseline if row["uncertainty_config_id"] == config_id]
            value["nsu_practical"] = normalised_safe_utility(
                [row["episode_return"] for row in selected],
                [row["episode_return"] for row in selected_lower],
                [row["episode_return"] for row in selected_upper],
            )
            uncertainty[config_id][policy] = value
    _write(OUTPUT / "uncertainty_summary.json", {"metadata": metadata(), "strata": uncertainty})

    combined_effects = _bootstrap_effects(ppo_by_seed, baseline, lower)
    combined_gate = _gate_from_effects(combined_effects, ppo_family, baseline)
    strata_gates = {}
    for config_id in UNCERTAINTY_IDS:
        effects = _bootstrap_effects(ppo_by_seed, baseline, lower, config_id=config_id)
        strata_gates[config_id] = _gate_from_effects(
            effects,
            [row for row in ppo_family if row["uncertainty_config_id"] == config_id],
            [row for row in baseline if row["uncertainty_config_id"] == config_id],
        )
    pairwise = {
        "metadata": metadata(),
        "bootstrap_seed": FROZEN_PHASE10_CONFIG.bootstrap_seed,
        "bootstrap_resamples": FROZEN_PHASE10_CONFIG.bootstrap_resamples,
        "method": "two-level training-seed then paired scenario-cluster percentile bootstrap",
        "combined": combined_gate,
        "strata": strata_gates,
    }
    _write(OUTPUT / "pairwise_bootstrap.json", pairwise)
    outcome = decide_rl_usefulness(
        combined_gate=bool(combined_gate["passes"]),
        stratum_gates=[bool(value["passes"]) for value in strata_gates.values()],
        tail_gate=False,
        stress_gates=[],
        supported_safety_regression=False,
    )
    _write(
        OUTPUT / "heldout_summary.json",
        {
            "metadata": metadata(),
            "suite": _read(HELDOUT_MANIFEST),
            "principal_comparator": FROZEN_PHASE10_CONFIG.principal_comparator,
            "policies": policy_summaries,
            "pairwise": pairwise,
            "pre_stress_formal_result": outcome,
            "formal_result": outcome,
        },
    )
    _write(
        OUTPUT / "observation_matched_diagnostic.json",
        {
            "metadata": metadata(),
            "policy": "observation_matched_greedy",
            "information": "384-vector, fixed action map, and mask only; no EpisodeState or pending schedule",
            "planner": policy_summaries["observation_matched_greedy"],
            "ppo_family": policy_summaries["ppo_family"],
            "ppo_minus_diagnostic_return": policy_summaries["ppo_family"]["mean_episode_return"] - policy_summaries["observation_matched_greedy"]["mean_episode_return"],
            "ppo_minus_diagnostic_exposure": policy_summaries["ppo_family"]["mean_exposed_person_timesteps"] - policy_summaries["observation_matched_greedy"]["mean_exposed_person_timesteps"],
        },
    )


def summarize_stress() -> None:
    planner_rows = {
        policy: _read(OUTPUT / f"_stress_{policy}.json")["rows"]
        for policy in PRACTICAL_POLICIES
    }
    ppo_by_seed = {
        seed: _read(OUTPUT / f"_stress_ppo_{seed}.json")["rows"]
        for seed in PPO_TRAINING_SEEDS
    }
    ppo_family = _aggregate_ppo_rows(ppo_by_seed)
    lower = planner_rows["random_valid"]
    baseline = planner_rows[FROZEN_PHASE10_CONFIG.principal_comparator]
    categories = {}
    stress_gate_values = []
    for stress_type in STRESS_TYPES:
        selected = {
            policy: [row for row in rows if row["stress_type"] == stress_type]
            for policy, rows in {**planner_rows, "ppo_family": ppo_family}.items()
        }
        category_lower = selected["random_valid"]
        category_upper = selected[FROZEN_PHASE10_CONFIG.principal_comparator]
        summaries = {}
        for policy, rows in selected.items():
            value = _summary(rows)
            value["nsu_practical"] = normalised_safe_utility(
                [row["episode_return"] for row in rows],
                [row["episode_return"] for row in category_lower],
                [row["episode_return"] for row in category_upper],
            )
            summaries[policy] = value
        effects = _bootstrap_effects(
            ppo_by_seed, baseline, lower, stress_type=stress_type
        )
        gate = _gate_from_effects(effects, selected["ppo_family"], category_upper)
        stress_gate_values.append(bool(gate["passes"]))
        categories[stress_type] = {"policies": summaries, "ppo_vs_principal": gate}
    payload = {
        "metadata": metadata(),
        "suite": _read(STRESS_MANIFEST),
        "categories": categories,
        "rows": [row for rows in planner_rows.values() for row in rows]
        + [row for rows in ppo_by_seed.values() for row in rows],
    }
    _write(OUTPUT / "stress_results.json", payload)
    heldout = _read(OUTPUT / "heldout_summary.json")
    pairwise = heldout["pairwise"]
    final = decide_rl_usefulness(
        combined_gate=bool(pairwise["combined"]["passes"]),
        stratum_gates=[bool(value["passes"]) for value in pairwise["strata"].values()],
        tail_gate=False,
        stress_gates=stress_gate_values,
        supported_safety_regression=False,
    )
    heldout["stress_gate_results"] = dict(zip(STRESS_TYPES, stress_gate_values))
    heldout["formal_result"] = final
    _write(OUTPUT / "heldout_summary.json", heldout)


def _semantic(action: dict[str, Any]) -> tuple[str, str | None, str | None]:
    return action["action_type"], action.get("physical_zone"), action.get("physical_shelter")


def evaluate_permutations(training_seed: int) -> Path:
    path = OUTPUT / f"_permutation_ppo_{training_seed}.json"
    if path.exists():
        print(f"reuse {path.name}", flush=True)
        return path
    from src.training_v3.evaluation import deterministic_diagnostic_config

    manifest = _read(PERMUTATION_MANIFEST)
    model = MaskablePPO.load(
        ROOT / "models" / "v3" / f"ppo_seed{training_seed}_best.zip", device="cpu"
    )
    pairs = []
    for number, entry in enumerate(manifest["base_scenarios"], 1):
        scenario = _scenario_from_entry(entry)
        config = deterministic_diagnostic_config(entry["uncertainty_config_id"])
        original = run_index_policy_episode(scenario, config, model=model)
        for permutation_seed in manifest["permutation_seeds"][str(entry["index"])]:
            variant, mapping = permute_heldout_scenario(scenario, permutation_seed)
            permuted = run_index_policy_episode(variant, config, model=model)
            compared = min(len(original["actions"]), len(permuted["actions"]))
            equivalent = sum(
                _semantic(original["actions"][index]) == _semantic(permuted["actions"][index])
                for index in range(compared)
            ) / max(len(original["actions"]), len(permuted["actions"]), 1)
            pairs.append(
                {
                    "training_seed": training_seed,
                    "base_index": entry["index"],
                    "scenario_id": entry["scenario_id"],
                    "permutation_seed": permutation_seed,
                    "mapping": mapping,
                    "action_equivalence_rate": equivalent,
                    "return_delta": permuted["episode_return"] - original["episode_return"],
                    "safe_population_delta": permuted["safe_population_fraction"] - original["safe_population_fraction"],
                    "exposure_delta": permuted["exposed_person_timesteps"] - original["exposed_person_timesteps"],
                }
            )
        if number % 10 == 0:
            print(f"permutation ppo {training_seed}: {number}/100", flush=True)
    _write(path, {"metadata": metadata(), "training_seed": training_seed, "pairs": pairs})
    return path


def summarize_permutations() -> None:
    pairs = [
        row
        for seed in PPO_TRAINING_SEEDS
        for row in _read(OUTPUT / f"_permutation_ppo_{seed}.json")["pairs"]
    ]
    heldout = _read(OUTPUT / "heldout_summary.json")
    lower_return = heldout["policies"]["random_valid"]["mean_episode_return"]
    upper_return = heldout["policies"][FROZEN_PHASE10_CONFIG.principal_comparator]["mean_episode_return"]
    denominator = upper_return - lower_return
    if denominator <= FROZEN_PHASE10_CONFIG.epsilon_den:
        nsu_deltas: list[float] = []
    else:
        nsu_deltas = [row["return_delta"] / denominator for row in pairs]
    mean_abs_safe = statistics.fmean(abs(row["safe_population_delta"]) for row in pairs)
    median_abs_nsu = statistics.median(abs(value) for value in nsu_deltas) if nsu_deltas else None
    alarm = bool(
        median_abs_nsu is None
        or median_abs_nsu > 0.05
        or mean_abs_safe > 0.05
    )
    by_seed = {}
    for seed in PPO_TRAINING_SEEDS:
        selected = [row for row in pairs if row["training_seed"] == seed]
        selected_nsu = [row["return_delta"] / denominator for row in selected] if nsu_deltas else []
        by_seed[str(seed)] = {
            "pairs": len(selected),
            "mean_action_equivalence_rate": statistics.fmean(row["action_equivalence_rate"] for row in selected),
            "mean_signed_nsu_delta": statistics.fmean(selected_nsu) if selected_nsu else None,
            "median_absolute_nsu_delta": statistics.median(abs(value) for value in selected_nsu) if selected_nsu else None,
            "mean_absolute_safe_population_delta": statistics.fmean(abs(row["safe_population_delta"]) for row in selected),
            "mean_absolute_exposure_delta": statistics.fmean(abs(row["exposure_delta"]) for row in selected),
            "worst_permutation_return_delta": min(row["return_delta"] for row in selected),
        }
    payload = {
        "metadata": metadata(),
        "base_scenarios": 100,
        "permutations_per_base": 5,
        "pairs_per_seed": 500,
        "total_pairs": len(pairs),
        "ordinary_nsu_denominator": denominator,
        "mean_action_equivalence_rate": statistics.fmean(row["action_equivalence_rate"] for row in pairs),
        "mean_signed_nsu_delta": statistics.fmean(nsu_deltas) if nsu_deltas else None,
        "median_absolute_nsu_delta": median_abs_nsu,
        "mean_absolute_safe_population_delta": mean_abs_safe,
        "mean_absolute_exposure_delta": statistics.fmean(abs(row["exposure_delta"]) for row in pairs),
        "worst_permutation_return_delta": min(row["return_delta"] for row in pairs),
        "alarm": "POTENTIAL_SLOT_SHORTCUT" if alarm else "PASS",
        "thresholds": {"median_absolute_nsu_delta": 0.05, "mean_absolute_safe_population_delta": 0.05},
        "by_seed": by_seed,
        "pairs": pairs,
    }
    _write(OUTPUT / "permutation_robustness.json", payload)


def _latency_summary(values_ns: Sequence[int]) -> dict[str, Any]:
    values = [value / 1_000_000 for value in values_ns[: FROZEN_PHASE10_CONFIG.latency_minimum_decisions]]
    return {
        "n": len(values),
        "mean_ms": statistics.fmean(values),
        "median_ms": linear_quantile(values, 0.50),
        "p90_ms": linear_quantile(values, 0.90),
        "p95_ms": linear_quantile(values, 0.95),
        "std_ms": statistics.pstdev(values),
        "maximum_ms": max(values),
    }


def evaluate_latency(policy: str) -> Path:
    path = OUTPUT / f"_latency_{policy}.json"
    if path.exists():
        print(f"reuse {path.name}", flush=True)
        return path
    entries = _read(HELDOUT_MANIFEST)["entries"]
    values: list[int] = []
    model = None
    training_seed = None
    if policy.startswith("ppo_"):
        training_seed = int(policy.split("_", 1)[1])
        model = MaskablePPO.load(
            ROOT / "models" / "v3" / f"ppo_seed{training_seed}_best.zip", device="cpu"
        )
    # First episode provides at least ten warm-up decisions on the identical code path.
    warm_scenario = _scenario_from_entry(entries[0])
    if model is not None:
        warm = run_index_policy_episode(warm_scenario, entries[0]["uncertainty_config_id"], model=model)
    elif policy == "observation_matched_greedy":
        warm = run_index_policy_episode(
            warm_scenario,
            entries[0]["uncertainty_config_id"],
            observation_matched=ObservationMatchedGreedy(),
        )
    else:
        warm = run_planner_episode(warm_scenario, entries[0]["uncertainty_config_id"], policy)
    del warm
    for number, entry in enumerate(entries, 1):
        scenario = _scenario_from_entry(entry)
        if model is not None:
            row = run_index_policy_episode(scenario, entry["uncertainty_config_id"], model=model)
        elif policy == "observation_matched_greedy":
            row = run_index_policy_episode(
                scenario,
                entry["uncertainty_config_id"],
                observation_matched=ObservationMatchedGreedy(),
            )
        else:
            row = run_planner_episode(scenario, entry["uncertainty_config_id"], policy)
        values.extend(row["decision_latency_ns"])
        if number % 10 == 0:
            print(f"latency {policy}: {min(len(values), 1000)}/1000", flush=True)
        if len(values) >= FROZEN_PHASE10_CONFIG.latency_minimum_decisions:
            break
    if len(values) < FROZEN_PHASE10_CONFIG.latency_minimum_decisions:
        raise RuntimeError(f"insufficient latency decisions for {policy}")
    _write(
        path,
        {
            "metadata": metadata(),
            "policy": policy,
            "training_seed": training_seed,
            "method": "one process; warmed; already-built policy input/mask to returned action",
            "excluded": "scenario/observation/mask construction, transitions, initialization, loading, logging, rendering",
            "summary": _latency_summary(values),
        },
    )
    return path


def summarize_latency() -> None:
    names = [*PRACTICAL_POLICIES, "observation_matched_greedy", *(f"ppo_{seed}" for seed in PPO_TRAINING_SEEDS)]
    policies = {name: _read(OUTPUT / f"_latency_{name}.json")["summary"] for name in names}
    policies["ppo_family"] = {
        metric: statistics.fmean(policies[f"ppo_{seed}"][metric] for seed in PPO_TRAINING_SEEDS)
        for metric in ("n", "mean_ms", "median_ms", "p90_ms", "p95_ms", "std_ms", "maximum_ms")
    }
    _write(
        OUTPUT / "latency_results.json",
        {
            "metadata": metadata(),
            "minimum_decisions_per_policy": FROZEN_PHASE10_CONFIG.latency_minimum_decisions,
            "method": "Phase 1 §17 already-built input/mask decision latency",
            "policies": policies,
        },
    )


def _svg_bars(path: Path, title: str, labels: Sequence[str], values: Sequence[float], *, lower_is_better: bool = False) -> None:
    width, height = 980, 520
    maximum = max(max(values), 1e-12)
    minimum = min(min(values), 0.0)
    span = maximum - minimum or 1.0
    bar_width = max(18, int(760 / max(len(values), 1)) - 10)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0b132b"/>',
        f'<text x="40" y="42" fill="#f5f7ff" font-family="sans-serif" font-size="24">{title}</text>',
        f'<text x="40" y="68" fill="#a8b2d1" font-family="sans-serif" font-size="13">{"Lower" if lower_is_better else "Higher"} is better · generated from Phase 10 JSON</text>',
    ]
    zero_y = 430 - ((0 - minimum) / span) * 320
    parts.append(f'<line x1="50" y1="{zero_y:.2f}" x2="940" y2="{zero_y:.2f}" stroke="#8090b0"/>')
    for index, (label, value) in enumerate(zip(labels, values)):
        x = 65 + index * (850 / max(len(values), 1))
        value_y = 430 - ((value - minimum) / span) * 320
        y = min(zero_y, value_y)
        h = max(1.0, abs(zero_y - value_y))
        color = "#49c6a5" if value >= 0 else "#ef6f6c"
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width}" height="{h:.2f}" fill="{color}"/>')
        parts.append(f'<text x="{x:.2f}" y="{max(95, y - 7):.2f}" fill="#f5f7ff" font-family="sans-serif" font-size="11">{value:.4f}</text>')
        parts.append(f'<text transform="translate({x + 8:.2f},455) rotate(35)" fill="#d9e1f2" font-family="sans-serif" font-size="11">{label}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def generate_figures() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    heldout = _read(OUTPUT / "heldout_summary.json")
    policies = heldout["policies"]
    names = [*PRACTICAL_POLICIES, "ppo_family"]
    charts = [
        ("01_nsu_practical.svg", "NSU-practical by policy", "nsu_practical", False),
        ("02_safe_population.svg", "Safe population fraction", "mean_safe_population_fraction", False),
        ("03_exposure.svg", "Exposed person-timesteps", "mean_exposed_person_timesteps", True),
        ("04_cvar10.svg", "CVaR10 episode return", "cvar_10", False),
        ("05_completion.svg", "Evacuation completion rate", "evacuation_completion_rate", False),
    ]
    for filename, title, metric, lower in charts:
        _svg_bars(FIGURES / filename, title, names, [float(policies[name][metric]) for name in names], lower_is_better=lower)
    uncertainty = _read(OUTPUT / "uncertainty_summary.json")["strata"]
    regime_labels, regime_values = [], []
    for regime in UNCERTAINTY_IDS:
        for name in (FROZEN_PHASE10_CONFIG.principal_comparator, "ppo_family"):
            regime_labels.append(f"{regime[3:-3]}-{name}")
            regime_values.append(float(uncertainty[regime][name]["nsu_practical"]))
    _svg_bars(FIGURES / "06_uncertainty.svg", "NSU by uncertainty regime", regime_labels, regime_values)
    seeds = _read(OUTPUT / "ppo_seed_summary.json")["seeds"]
    _svg_bars(FIGURES / "07_ppo_seeds.svg", "Five-seed PPO NSU variability", [str(seed) for seed in PPO_TRAINING_SEEDS], [float(seeds[str(seed)]["nsu_practical"]) for seed in PPO_TRAINING_SEEDS])
    effects = heldout["pairwise"]["combined"]["effects"]
    effect_names = ["NSU", "Exposure", "Tail NSU", "Unsafe"]
    effect_keys = ["nsu_difference", "exposure_reduction", "tail_nsu_difference", "unsafe_difference"]
    _svg_bars(FIGURES / "08_paired_effects.svg", "PPO minus principal paired effects", effect_names, [float(effects[key]["estimate"] or 0.0) for key in effect_keys])
    permutation = _read(OUTPUT / "permutation_robustness.json")
    _svg_bars(FIGURES / "09_permutation.svg", "Held-out permutation sensitivity", ["action equivalence", "median |NSU Δ|", "mean |safe Δ|"], [float(permutation["mean_action_equivalence_rate"]), float(permutation["median_absolute_nsu_delta"] or 0.0), float(permutation["mean_absolute_safe_population_delta"])])
    stress = _read(OUTPUT / "stress_results.json")["categories"]
    _svg_bars(FIGURES / "10_stress.svg", "PPO-family stress NSU", list(STRESS_TYPES), [float(stress[item]["policies"]["ppo_family"]["nsu_practical"] or 0.0) for item in STRESS_TYPES])
    latency = _read(OUTPUT / "latency_results.json")["policies"]
    _svg_bars(FIGURES / "11_latency.svg", "Median decision latency (ms)", names, [float(latency[name]["median_ms"]) for name in names], lower_is_better=True)


def generate_qualitative_trace() -> None:
    manifest = _read(HELDOUT_MANIFEST)
    scored = []
    for entry in manifest["entries"]:
        scenario = _scenario_from_entry(entry)
        population = sum(item.population_initial_remaining for item in scenario.zones)
        weighted_hazard = sum(
            item.population_initial_remaining * item.initial_flood_severity
            for item in scenario.zones
        ) / population
        travel = [
            item.travel_time_mean
            for item in scenario.network.routes
            if item.reachable and item.travel_time_mean is not None
        ]
        score = weighted_hazard + statistics.fmean(travel) / 55.0
        scored.append((score, entry["index"], entry))
    scored.sort(key=lambda item: (item[0], item[1]))
    score, _, entry = scored[len(scored) // 2]
    risk = _aligned(_read(OUTPUT / "_normal_risk_greedy.json")["rows"])[entry["scenario_id"]]
    ppo = _aligned(_read(OUTPUT / "_normal_ppo_4404.json")["rows"])[entry["scenario_id"]]
    timesteps = sorted({0, 3, int(entry["horizon_steps"]) // 2, int(entry["horizon_steps"]) - 1})

    def selected(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"timestep": timestep, "action": actions[timestep]}
            for timestep in timesteps
            if timestep < len(actions)
        ]

    _write(
        OUTPUT / "qualitative_trace.json",
        {
            "metadata": metadata(),
            "selection_rule": "median initial population-weighted zone severity plus mean reachable travel/55; manifest index tie-break",
            "selection_score": score,
            "scenario": entry,
            "important_timesteps": timesteps,
            "risk_greedy": selected(risk["actions"]),
            "strongest_practical_planner": {
                "policy": "risk_greedy",
                "note": "The frozen strongest latency-eligible planner is risk_greedy, so this is intentionally the same trace.",
                "decisions": selected(risk["actions"]),
            },
            "ppo_representative_seed_4404": selected(ppo["actions"]),
            "interpretation": "Explanatory example only; it provides no evidence of superiority.",
        },
    )


def _fmt(value: float | None, digits: int = 4) -> str:
    return "NA" if value is None else f"{value:.{digits}f}"


def generate_report() -> None:
    heldout = _read(OUTPUT / "heldout_summary.json")
    seeds = _read(OUTPUT / "ppo_seed_summary.json")
    uncertainty = _read(OUTPUT / "uncertainty_summary.json")["strata"]
    observation = _read(OUTPUT / "observation_matched_diagnostic.json")
    permutation = _read(OUTPUT / "permutation_robustness.json")
    stress = _read(OUTPUT / "stress_results.json")["categories"]
    latency = _read(OUTPUT / "latency_results.json")["policies"]
    trace = _read(OUTPUT / "qualitative_trace.json")
    pair = heldout["pairwise"]["combined"]
    names = [*PRACTICAL_POLICIES, "ppo_family"]
    labels = {
        "random_valid": "Random valid",
        "nearest_safe": "Nearest safe",
        "risk_greedy": "Risk greedy",
        "lookahead_k2": "Lookahead-2",
        "lookahead_k3": "Lookahead-3",
        "sampled_mpc": "Sampled MPC",
        "ppo_family": "PPO five-seed aggregate",
    }
    lines = [
        "# Sentinel-Agent V3 — Frozen Held-Out Policy Evaluation",
        "",
        "> **SYNTHETIC EXPERIMENT ONLY.** This report does not establish real-world emergency-response effectiveness.",
        "",
        "## Research question",
        "",
        "Does the frozen five-seed MaskablePPO family provide a measurable decision advantage over strong non-learned planning on unseen stochastic V3 scenarios?",
        "",
        "## Pre-registered evaluation rules",
        "",
        "Stage 10A commit `c92173dc0001e60cd7db69d89fab8f391d202905` froze 600 ordinary scenarios, all seeds, policies, metrics, the two-level 10,000-draw bootstrap, stress/permutation suites, latency, and the Phase 1 YES/NO/MIXED function before generation. No training or checkpoint mutation occurred.",
        "",
        "## Frozen policies, suite, and PPO seed handling",
        "",
        "The ordinary suite has 600 new `v3-heldout-generator-v1` scenarios (200 LOW, 200 MEDIUM, 200 HIGH), 4–6 zones, 6–9 shelters, horizon 10–16, and replication 0. All Phase 6 planners and all best checkpoints for seeds 1101, 2202, 3303, 4404, and 5505 run every unit. The PPO-family row is an equal-weight per-scenario seed mean; seed identity remains retained. Seed 4404 is only the pre-frozen representative trace model.",
        "",
        "## Principal baseline",
        "",
        "`risk_greedy` is the pre-test principal comparator. Gate 6 excluded lookahead-2/3 and MPC from principal eligibility at the 100 ms p95 budget; risk-greedy beat nearest-safe outside the 0.002 tie band. The ineligible stronger planners remain fully reported.",
        "",
        "## Main results",
        "",
        "| Policy | NSU-practical | Safe pop. | Exposure | CVaR10 | Completion | Unsafe | Median ms | p95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in names:
        row = heldout["policies"][name]
        timing = latency[name]
        lines.append(
            f"| {labels[name]} | {_fmt(row['nsu_practical'])} | {_fmt(row['mean_safe_population_fraction'])} | {_fmt(row['mean_exposed_person_timesteps'], 2)} | {_fmt(row['cvar_10'])} | {_fmt(row['evacuation_completion_rate'])} | {_fmt(row['unsafe_dispatch_rate'])} | {_fmt(timing['median_ms'], 3)} | {_fmt(timing['p95_ms'], 3)} |"
        )
    effects = pair["effects"]
    lines.extend(
        [
            "",
            "NSU-practical is the Phase 1 ratio of aggregate paired means and is not NSU-exact. Values are intentionally unclipped.",
            "",
            "## Paired statistical comparison and tail behavior",
            "",
            f"- NSU difference: {_fmt(effects['nsu_difference']['estimate'])}, 95% CI [{_fmt(effects['nsu_difference']['lower'])}, {_fmt(effects['nsu_difference']['upper'])}].",
            f"- Exposure relative reduction: {_fmt(effects['exposure_reduction']['estimate'])}, 95% CI [{_fmt(effects['exposure_reduction']['lower'])}, {_fmt(effects['exposure_reduction']['upper'])}].",
            f"- Tail-NSU difference: {_fmt(effects['tail_nsu_difference']['estimate'])}, 95% CI [{_fmt(effects['tail_nsu_difference']['lower'])}, {_fmt(effects['tail_nsu_difference']['upper'])}]. Higher return CVaR10 is better.",
            f"- Unsafe-rate difference: {_fmt(effects['unsafe_difference']['estimate'])}, 95% CI [{_fmt(effects['unsafe_difference']['lower'])}, {_fmt(effects['unsafe_difference']['upper'])}].",
            f"- Combined Phase 1 gate: `{pair['passes']}`; supported benefit channels: `{', '.join(pair['supported_benefits']) or 'none'}`.",
            "",
            "## LOW / MEDIUM / HIGH",
            "",
            "| Regime | PPO NSU | PPO safe | PPO exposure | PPO p10 | PPO CVaR10 | Gate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for regime in UNCERTAINTY_IDS:
        row = uncertainty[regime]["ppo_family"]
        gate = heldout["pairwise"]["strata"][regime]["passes"]
        lines.append(f"| {regime[3:-3]} | {_fmt(row['nsu_practical'])} | {_fmt(row['mean_safe_population_fraction'])} | {_fmt(row['mean_exposed_person_timesteps'], 2)} | {_fmt(row['p10_episode_return'])} | {_fmt(row['cvar_10'])} | {gate} |")
    lines.extend(
        [
            "",
            "## Five-seed PPO variability",
            "",
            "| Seed | NSU-practical | Safe pop. | Exposure | CVaR10 | Completion | Median latency |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for seed in PPO_TRAINING_SEEDS:
        row = seeds["seeds"][str(seed)]
        timing = latency[f"ppo_{seed}"]
        lines.append(f"| {seed} | {_fmt(row['nsu_practical'])} | {_fmt(row['mean_safe_population_fraction'])} | {_fmt(row['mean_exposed_person_timesteps'], 2)} | {_fmt(row['cvar_10'])} | {_fmt(row['evacuation_completion_rate'])} | {_fmt(timing['median_ms'], 3)} ms |")
    across = seeds["across_seed"]["nsu_practical"]
    lines.extend(
        [
            "",
            f"Across-seed NSU: mean {_fmt(across['mean'])}, population SD {_fmt(across['std'])}, minimum {_fmt(across['min'])}, maximum {_fmt(across['max'])}.",
            "",
            "## Observation-matched planner diagnostic and information asymmetry",
            "",
            f"The secondary `observation_matched_greedy` sees only the 384-vector, mask, and public action map. PPO-family return minus this diagnostic is {_fmt(observation['ppo_minus_diagnostic_return'])}; PPO-family exposure minus it is {_fmt(observation['ppo_minus_diagnostic_exposure'], 2)}. The original planners retain exact pending-arrival detail, so the principal comparison is conservative against PPO; this diagnostic estimates but cannot eliminate the representation/modeling gap.",
            "",
            "## Slot-permutation robustness",
            "",
            f"Across 100 separate bases × five variants × five PPO seeds, mean action equivalence is {_fmt(permutation['mean_action_equivalence_rate'])}, median absolute NSU delta is {_fmt(permutation['median_absolute_nsu_delta'])}, mean absolute safe-population delta is {_fmt(permutation['mean_absolute_safe_population_delta'])}, and the frozen alarm is `{permutation['alarm']}`. The Phase 9 alarm remains historical evidence regardless of this reproduction result.",
            "",
            "## Stress robustness",
            "",
            "| Category | PPO NSU-practical | PPO safe | PPO exposure | Gate |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for stress_type in STRESS_TYPES:
        item = stress[stress_type]
        row = item["policies"]["ppo_family"]
        lines.append(f"| {stress_type} | {_fmt(row['nsu_practical'])} | {_fmt(row['mean_safe_population_fraction'])} | {_fmt(row['mean_exposed_person_timesteps'], 2)} | {item['ppo_vs_principal']['passes']} |")
    latency_order = [
        *PRACTICAL_POLICIES,
        "observation_matched_greedy",
        *(f"ppo_{seed}" for seed in PPO_TRAINING_SEEDS),
        "ppo_family",
    ]
    latency_labels = {
        **labels,
        "observation_matched_greedy": "Observation-matched greedy",
        **{f"ppo_{seed}": f"PPO {seed}" for seed in PPO_TRAINING_SEEDS},
    }
    lines.extend(
        [
            "",
            "## Decision latency",
            "",
            "Latency is a separate warmed, one-process, ≥1,000-decision Phase 1 benchmark from already-built policy input/mask to action; loading, mask/observation construction, and transition time are excluded.",
            "",
            "| Policy | Median ms | p90 ms | p95 ms | Maximum ms |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name in latency_order:
        timing = latency[name]
        lines.append(
            f"| {latency_labels[name]} | {_fmt(timing['median_ms'], 3)} | {_fmt(timing['p90_ms'], 3)} | {_fmt(timing['p95_ms'], 3)} | {_fmt(timing['maximum_ms'], 3)} |"
        )
    total_unsafe = sum(float(heldout["policies"][name]["unsafe_dispatches"]) for name in names)
    total_capacity = sum(float(heldout["policies"][name]["capacity_violations"]) for name in names)
    total_closed = sum(float(heldout["policies"][name]["closed_route_dispatches"]) for name in names)
    total_invalid = sum(float(seeds["seeds"][str(seed)]["invalid_masked_actions"]) for seed in PPO_TRAINING_SEEDS)
    lines.extend(
        [
            "",
            "## Safety and mechanical integrity",
            "",
            f"Across the ordinary all-policy table: unsafe dispatches `{total_unsafe:g}`, capacity violations `{total_capacity:g}`, known-closed-route dispatches `{total_closed:g}`. Across individual PPO seeds, invalid masked selections are `{total_invalid:g}`. Any nonzero mechanical count is treated as a defect rather than a tradeoff.",
            "",
            "## Fixed qualitative trace",
            "",
            f"The policy-independent median-difficulty rule selected manifest index `{trace['scenario']['index']}` (`{trace['scenario']['scenario_id']}`). Important-timestep decisions for risk-greedy/the strongest practical planner and representative PPO seed 4404 are recorded in `qualitative_trace.json`. The trace is explanatory only and did not select any model, threshold, or conclusion.",
            "",
            "## Final frozen RL usefulness conclusion",
            "",
            f"# {heldout['formal_result']}",
            "",
            "This label is generated by the Phase 1 gate, not assigned narratively. See the paired benefit channels, regime gates, and stress gates above for the exact reason.",
            "",
            "## Representation robustness",
            "",
            f"# {permutation['alarm']}",
            "",
            "## Limitations and next action",
            "",
            "The environment, hazards, populations, routes, and reward weights are synthetic modeling choices. The principal planner has richer pending-arrival information. The flat MLP has known semantic-slot sensitivity. There is one stochastic replication per scenario, Phase 4 has no post-departure route failures, the observation-matched heuristic is stateless, and latency is machine-specific. No real-world operational effectiveness or general RL superiority is claimed.",
            "",
            "Phase 10 stops here. Any Phase 11 dashboard or future permutation-aware architecture experiment requires separate project-owner direction and cannot rewrite this result.",
        ]
    )
    (ROOT / "V3_POLICY_EVALUATION.md").write_text("\n".join(lines) + "\n")


def run_all(workers: int) -> None:
    if not HELDOUT_MANIFEST.exists():
        generate_manifests()
    for policy in (*PRACTICAL_POLICIES, "observation_matched_greedy"):
        evaluate_planner_policy("heldout", policy, workers)
    for seed in PPO_TRAINING_SEEDS:
        evaluate_ppo_policy("heldout", seed)
    summarize_normal()
    for seed in PPO_TRAINING_SEEDS:
        evaluate_permutations(seed)
    summarize_permutations()
    for policy in PRACTICAL_POLICIES:
        evaluate_planner_policy("stress", policy, workers)
    for seed in PPO_TRAINING_SEEDS:
        evaluate_ppo_policy("stress", seed)
    summarize_stress()
    for policy in (*PRACTICAL_POLICIES, "observation_matched_greedy", *(f"ppo_{seed}" for seed in PPO_TRAINING_SEEDS)):
        evaluate_latency(policy)
    summarize_latency()
    generate_qualitative_trace()
    generate_figures()
    generate_report()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "normal-planner", "normal-ppo", "summarize-normal", "permutation", "summarize-permutation", "stress-planner", "stress-ppo", "summarize-stress", "latency", "summarize-latency", "trace", "figures", "report", "all"))
    parser.add_argument("--policy")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--workers", type=int, default=max(1, min(6, (mp.cpu_count() or 2) - 1)))
    args = parser.parse_args()
    if args.command == "generate":
        generate_manifests()
    elif args.command in {"normal-planner", "stress-planner"}:
        if args.policy not in {*PRACTICAL_POLICIES, "observation_matched_greedy"}:
            parser.error("--policy is required and must be frozen")
        evaluate_planner_policy("heldout" if args.command == "normal-planner" else "stress", args.policy, args.workers)
    elif args.command in {"normal-ppo", "stress-ppo", "permutation"}:
        if args.seed not in PPO_TRAINING_SEEDS:
            parser.error("--seed must be one of the five frozen PPO seeds")
        if args.command == "permutation":
            evaluate_permutations(args.seed)
        else:
            evaluate_ppo_policy("heldout" if args.command == "normal-ppo" else "stress", args.seed)
    elif args.command == "summarize-normal":
        summarize_normal()
    elif args.command == "summarize-permutation":
        summarize_permutations()
    elif args.command == "summarize-stress":
        summarize_stress()
    elif args.command == "latency":
        if not args.policy:
            parser.error("--policy is required")
        evaluate_latency(args.policy)
    elif args.command == "summarize-latency":
        summarize_latency()
    elif args.command == "trace":
        generate_qualitative_trace()
    elif args.command == "figures":
        generate_figures()
    elif args.command == "report":
        generate_report()
    else:
        run_all(args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
