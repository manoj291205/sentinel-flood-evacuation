"""Gate G21: do v4 worlds make transit long and fallible?

Runs Baseline A (Risk-Greedy + V3_SAFETY_V1 mask) on the v4 worlds for practical seeds
620000-620119, replication 0, and writes data/eval_results/phase21/g21.json.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from src.geospatial import load_road_graph, path_for_action
from src.geospatial.v4_runtime import build_v4_runtime
from src.planners import RiskGreedyPlanner, build_planner_input
from src.safety import evaluate_actions
from src.sim import DispatchAction
from src.sim.events import DispatchStatus
from src.sim.world import V4_WORLDS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/eval_results/phase21/g21.json"
FAIL = (DispatchStatus.STRANDED, DispatchStatus.ARRIVAL_UNSAFE, DispatchStatus.ARRIVAL_OVERFLOW)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def run_level(world_id: str, seeds: range, graph) -> dict:
    started = time.perf_counter()
    planner = RiskGreedyPlanner()
    lags: list[int] = []
    exposure: list[float] = []
    severity: list[float] = []
    counts = {"dispatched": 0, "stranded": 0, "unsafe": 0, "overflow": 0}
    for seed in seeds:
        scenario, sim, _, overlay, _ = build_v4_runtime(
            world_id, generator_seed=seed, graph=graph, replication_id=0
        )
        while not sim.state.terminal:
            sim.observe()
            state = sim.prepared_state_for_debug()
            snapshot = evaluate_actions(scenario, state)
            decision = planner.choose_action(
                build_planner_input(scenario, state, snapshot, sim.config)
            )
            action = decision.action
            if isinstance(action, DispatchAction):
                path = path_for_action(graph, overlay.road_state, action)
                shelter = state.shelter(action.shelter_id)
                if path is not None and path.hazard_exposure is not None and shelter:
                    exposure.append(path.hazard_exposure)
                    severity.append(shelter.flood_severity_current)
            if not sim.step(action).accepted:
                raise RuntimeError("planner chose a rejected action")
        for event in sim.state.dispatch_events:
            counts["dispatched"] += 1
            lags.append(event.travel_lag_steps)
            counts["stranded"] += event.status is DispatchStatus.STRANDED
            counts["unsafe"] += event.status is DispatchStatus.ARRIVAL_UNSAFE
            counts["overflow"] += event.status is DispatchStatus.ARRIVAL_OVERFLOW
    failed = counts["stranded"] + counts["unsafe"] + counts["overflow"]
    n = counts["dispatched"]
    return {
        "world_id": world_id,
        "episodes": len(seeds),
        **counts,
        "failure_rate": failed / n if n else None,
        "stranded_rate": counts["stranded"] / n if n else None,
        "unsafe_rate": counts["unsafe"] / n if n else None,
        "overflow_rate": counts["overflow"] / n if n else None,
        "median_lag_steps": statistics.median(lags) if lags else None,
        "p90_lag_steps": percentile(lags, 0.9),
        "hazard_severity_correlation": pearson(exposure, severity),
        "runtime_seconds": round(time.perf_counter() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=120)
    args = parser.parse_args()
    graph = load_road_graph()
    seeds = range(620000, 620000 + args.seeds)
    levels = {}
    for world_id in V4_WORLDS:
        level = world_id.split("-")[1]
        levels[level] = run_level(world_id, seeds, graph)
        print(level, json.dumps(levels[level]), flush=True)
    high, medium, low = levels["high"], levels["medium"], levels["low"]
    corr = medium["hazard_severity_correlation"]
    checks = {
        "failure_rate_high_ge_3pct": (high["failure_rate"] or 0) >= 0.03,
        "failure_rate_medium_ge_1pct": (medium["failure_rate"] or 0) >= 0.01,
        "median_lag_ge_3_all_levels": all((v["median_lag_steps"] or 0) >= 3 for v in levels.values()),
        "correlation_medium_gt_0_1": corr is not None and corr > 0.1,
    }
    result = {
        "gate": "G21",
        "baseline": "risk_greedy + V3_SAFETY_V1",
        "seeds": [seeds.start, seeds.stop - 1],
        "replication_id": 0,
        "levels": levels,
        "checks": checks,
        "passed": all(checks.values()),
    }
    if args.seeds == 120:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("G21", "PASS" if result["passed"] else "FAIL", checks)


if __name__ == "__main__":
    main()
