"""Phase 27 episode runs (V4_EVALUATION_PREREG.md section 4). Raw output only; no analysis here.

    python scripts/phase27_run.py --system P --regime v4-medium-dt2-v1 --seeds 1050000-1050059 --workers 16
    python scripts/phase27_run.py --budget          # time 2 seeds per system, write budget.json

One JSONL line per episode in data/eval_results/phase27/runs/<system>_<regime>.jsonl, resumable by
(system, regime, seed). System P also stores every decision state with candidates (inputs + certificate
summary) in data/eval_results/phase27/states/<regime>_<seed>.jsonl.gz for the decision-level study.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data/eval_results/phase27"
SYSTEMS = ("A", "A2", "HOLD", "B", "P", "P-noFC", "P-noHyst")
PRIMARY = ("v4-medium-dt2-v1", "v4-high-dt2-v1")
STRESS = "v4-stress-dt2-v1"
SEEDS_FULL = (1_050_000, 1_050_059)
SEEDS_HALF = (1_050_000, 1_050_029)
OPERATOR = {"decision": "AUTO", "actor": "phase27-runner", "reason": ""}
_GRAPH = None


def _init():
    global _GRAPH
    from src.geospatial import load_road_graph

    _GRAPH = load_road_graph()


def run_episode(task):
    system, regime, seed = task
    started = time.perf_counter()
    for attempt in (1, 2):
        try:
            record = _run_episode(system, regime, seed)
            record["wall_seconds"] = round(time.perf_counter() - started, 3)
            record["attempts"] = attempt
            return record
        except Exception as exc:  # crashed episodes are rerun once with the same seed (prereg 7)
            error = f"{type(exc).__name__}: {exc}"
    return {"system": system, "regime": regime, "seed": seed, "status": "MISSING", "error": error,
            "wall_seconds": round(time.perf_counter() - started, 3), "attempts": 2}


def _run_episode(system: str, regime: str, seed: int) -> dict:
    from src.certify.baselines import BaselineBPlanner, relax_fail_closed
    from src.certify.gate import CertifiedGate
    from src.certify.ledger import SimLedgerAdapter
    from src.certify.params import get_cert_params
    from src.certify.recertify import GroupHistory, RecertPolicy, recertify_in_transit
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.planners import LookaheadK2Planner, RiskGreedyPlanner, build_planner_input
    from src.safety import evaluate_actions
    from src.sim import WaitAction
    from src.sim.events import AuditEventType, DispatchStatus

    scenario, sim, graph, overlay, world = build_v4_runtime(regime, generator_seed=seed, graph=_GRAPH)
    certified = system.startswith("P")
    params = get_cert_params("v4-cert-eval-v1")
    policy = RecertPolicy()
    if system == "P-noHyst":
        import dataclasses

        params = dataclasses.replace(params, eps_keep=params.eps_dispatch)
        policy = RecertPolicy(cooldown_steps=0)
    if certified:
        ledger = SimLedgerAdapter(sim)
        gate = CertifiedGate(scenario, graph, world, params, ledger, world_id=regime)
    planner_a = RiskGreedyPlanner()
    planner_a2 = LookaheadK2Planner()
    planner_b = BaselineBPlanner(scenario, graph, world, params) if system == "B" else None
    histories: dict = {}
    decisions = futures_total = recert_checks = migrations = no_alt = 0
    arrival_pred: list[tuple[str, float | None]] = []
    state_lines: list[str] = []
    while not sim.state.terminal:
        sim.observe()
        state = sim.prepared_state_for_debug()
        if certified:
            for d in recertify_in_transit(gate, state, overlay.road_state, sim.transit_plans(), histories, policy):
                recert_checks += 1
                migrations += d.action == "MIGRATE"
                no_alt += d.action == "KEEP_ESCALATE"
            state = sim.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state)
        if system == "A":
            action = planner_a.choose_action(build_planner_input(scenario, state, snapshot, sim.config)).action
        elif system == "A2":
            action = planner_a2.choose_action(build_planner_input(scenario, state, snapshot, sim.config)).action
        elif system == "HOLD":
            action = WaitAction()
        elif system == "B":
            action = planner_b.choose(state, overlay.road_state, snapshot, sim.transit_plans())
            futures_total += planner_b.last_futures
        else:
            result, inputs = gate.evaluate(state, overlay.road_state, snapshot)
            if system == "P-noFC":
                result = relax_fail_closed(result)
            futures_total += result.n_final
            decision = gate.commit(result, inputs, operator=OPERATOR)
            decisions += 1
            cert = decision.certificate
            if decision.certificate["kind"] == "DISPATCH":
                cand = next(c for c in inputs.candidates if c.action_key == result.chosen_key)
                fs = gate.last_futureset
                arrivals = [
                    r.arrival_timestep
                    for r in (gate.rollout(cand, fs.future(k), inputs.ledger, world, params, graph)
                              for k in range(1, min(result.n_final, 64) + 1))
                    if r.arrival_timestep is not None
                ]
                arrival_pred.append((cert["chosen"]["group_id"],
                                     statistics.median(arrivals) if arrivals else None))
            if system == "P" and inputs.candidates:
                state_lines.append(json.dumps({
                    "regime": regime, "seed": seed, "timestep": state.current_timestep,
                    "chosen_key": result.chosen_key, "n_final": result.n_final, "looks": result.looks,
                    "verdicts": {c.action_key: c.verdict.value for c in result.candidates},
                    "inputs": inputs.to_dict(),
                }, sort_keys=True))
            continue
        decisions += 1
        if not sim.step(action).accepted:
            raise RuntimeError(f"{system} chose a rejected action {action}")
    final = sim.state
    events = final.dispatch_events
    count = lambda status: sum(e.status is status for e in events)  # noqa: E731
    people = lambda status: sum(e.people for e in events if e.status is status)  # noqa: E731
    live = {e.event_id: e.arrival_timestep for e in events}
    agree = [abs(live[g] - p) for g, p in arrival_pred if p is not None and g in live]
    if state_lines:
        folder = OUT / "states"
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / f"{regime}_{seed}.jsonl.gz", "wt", encoding="utf-8") as handle:
            handle.write("\n".join(state_lines) + "\n")
    return {
        "system": system, "regime": regime, "seed": seed, "status": "OK",
        "dispatched_groups": len(events),
        "arrived_groups": count(DispatchStatus.ARRIVED),
        "stranded_groups": count(DispatchStatus.STRANDED),
        "unsafe_groups": count(DispatchStatus.ARRIVAL_UNSAFE),
        "overflow_groups": count(DispatchStatus.ARRIVAL_OVERFLOW),
        "stranded_people": final.people_stranded, "unsafe_people": final.people_unsafe_arrival,
        "overflow_people": final.people_overflow, "people_safely_arrived": final.people_safely_arrived,
        "initial_population": final.initial_evacuation_population, "terminal_step": final.current_timestep,
        "decisions": decisions, "futures_total": futures_total,
        "recert_checks": recert_checks, "migrations": migrations, "keep_escalations": no_alt,
        "migration_events": sum(r.event_type is AuditEventType.GROUP_MIGRATED for r in final.audit_log),
        "arrival_abs_error_median": statistics.median(agree) if agree else None,
        "arrival_pairs": len(agree),
        "group_hours": sum(e.travel_lag_steps for e in events) * world.timestep_minutes / 60.0,
    }


def parse_range(text: str) -> tuple[int, int]:
    a, b = text.split("-")
    return int(a), int(b)


def done_seeds(path: Path) -> set[int]:
    if not path.exists():
        return set()
    seeds = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("status") == "OK" or row.get("attempts") == 2:
                seeds.add(row["seed"])
    return seeds


def run_many(system: str, regime: str, seeds: tuple[int, int], workers: int) -> None:
    path = OUT / "runs" / f"{system}_{regime}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    todo = [(system, regime, s) for s in range(seeds[0], seeds[1] + 1) if s not in done_seeds(path)]
    print(f"{system} {regime}: {len(todo)} episodes to run", flush=True)
    if not todo:
        return
    with Pool(workers, initializer=_init) as pool, path.open("a", encoding="utf-8") as out:
        for row in pool.imap_unordered(run_episode, todo):
            out.write(json.dumps(row, sort_keys=True) + "\n")
            out.flush()
            print(system, regime, row["seed"], row["status"], row["wall_seconds"], flush=True)


def budget(workers: int) -> None:
    """Time 2 seeds per system (medium regime), project section 4 on 16 workers, pick the seed range."""
    tasks = [(s, PRIMARY[0], seed) for s in SYSTEMS for seed in (SEEDS_FULL[0], SEEDS_FULL[0] + 1)]
    started = time.perf_counter()
    with Pool(workers, initializer=_init) as pool:
        rows = pool.map(run_episode, tasks, chunksize=1)
    per_system = {}
    for s in SYSTEMS:
        times = [r["wall_seconds"] for r in rows if r["system"] == s and r["status"] == "OK"]
        per_system[s] = statistics.fmean(times) if times else None
    missing = [s for s, t in per_system.items() if t is None]
    regimes = len(PRIMARY) + 1  # primary regimes + the stress regime
    full_seconds = sum(t * regimes * 60 for t in per_system.values() if t is not None) / 16
    use_half = full_seconds / 3600 > 48
    seeds = SEEDS_HALF if use_half else SEEDS_FULL
    result = {
        "timing_regime": PRIMARY[0], "timing_seeds": [SEEDS_FULL[0], SEEDS_FULL[0] + 1],
        "timing_workers": workers, "mean_episode_seconds": per_system, "systems_without_timing": missing,
        "projection_full_hours_on_16_workers": round(full_seconds / 3600, 2),
        "rule": "if the projection exceeds 48 h use seeds 1050000-1050029 for every system",
        "chosen_seed_range": list(seeds), "seeds_per_regime": seeds[1] - seeds[0] + 1,
        "timing_wall_seconds": round(time.perf_counter() - started, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "budget.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=SYSTEMS)
    parser.add_argument("--regime")
    parser.add_argument("--seeds", type=parse_range)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--budget", action="store_true")
    args = parser.parse_args()
    if args.budget:
        budget(args.workers)
        return 0
    if not (args.system and args.regime and args.seeds):
        parser.error("--system, --regime and --seeds are required")
    run_many(args.system, args.regime, args.seeds, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
