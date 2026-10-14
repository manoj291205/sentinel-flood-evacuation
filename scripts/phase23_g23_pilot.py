"""G23 pilot: does the joint first-hitting indicator disagree with product-of-marginals?

Per world (MEDIUM / HIGH) Baseline A drives practical seeds 620000-620059; at every decision
state each mechanically valid dispatch is evaluated with n futures (disjoint k-blocks of one
FutureSet: joint, path, shelter, capacity). Settings follow the 2026-10-14 amendment in
specs/V4_ROLLOUT_SPEC.md (n = 256, restricted edge set, adaptive horizon, noise-floor criterion).

    python scripts/phase23_g23_pilot.py --world v4-medium-dt2-v1 --max-pairs 1300
    python scripts/phase23_g23_pilot.py --merge
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

from src.certify.forecast import forecast_from_state, ledger_hash
from src.certify.futures import FutureSet, root_key
from src.certify.ledger_view import ledger_view_from_state
from src.certify.params import CertParams
from src.certify.rollout import Candidate, rollout_components, rollout_joint
from src.geospatial import load_road_graph, shortest_valid_path
from src.geospatial.v4_runtime import build_v4_runtime
from src.planners import RiskGreedyPlanner, build_planner_input
from src.safety import evaluate_actions
from src.sim import DispatchAction
from src.sim.transit import edge_travel_minutes

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/eval_results/phase23"
THRESHOLD = 0.95


class OpenView:
    """Future view with every edge open: isolates the shelter / capacity marginals."""

    def __init__(self, f):
        self._f = f
        self.k, self.start_timestep, self.steps = f.k, f.start_timestep, f.steps

    def edge_open(self, edge_id, t):
        return True

    def __getattr__(self, name):
        return getattr(self._f, name)


class Block:
    """A disjoint k-block of a FutureSet, indexed 0..n-1."""

    def __init__(self, fs: FutureSet, offset: int):
        self.fs, self.offset = fs, offset

    def __getitem__(self, i: int):
        return self.fs.future(self.offset + i + 1)


def canonical_paths(graph, road_state, scenario):
    paths = {}
    for zone in scenario.zones:
        for shelter in scenario.shelters:
            p = shortest_valid_path(
                graph, road_state, graph.zone_node_map[zone.zone_id], graph.shelter_node_map[shelter.shelter_id]
            )
            if p.reachable:
                paths[(zone.zone_id, shelter.shelter_id)] = p.edge_ids
    return paths


def horizon(paths, graph, world, remaining):
    worst = 0.0
    for edge_ids in paths.values():
        worst = max(worst, sum(
            edge_travel_minutes(graph.edges_by_id[e].length_m, graph.edges_by_id[e].assumed_speed_kph, 0.0, world)
            for e in edge_ids))
    h = math.ceil((world.boarding_minutes + 1.5 * worst) / world.timestep_minutes) + 1
    return max(1, min(remaining, h))


def evaluate_candidate(c, blocks, ledger, world, params, graph, end):
    n = len(blocks[0])
    joint = path = shelter = cap = beyond = 0
    for i in range(n):
        r = rollout_joint(c, blocks[0][i], ledger, world, params, graph)
        late = r.arrival_timestep is not None and r.arrival_timestep > end
        beyond += late
        joint += r.z and not late
        r = rollout_joint(c, blocks[1][i], ledger, world, params, graph)
        path += r.path_ok
        fs = blocks[2][i]
        r = rollout_components(c, OpenView(fs), fs, fs, ledger, world, params, graph)
        shelter += bool(r.shelter_ok) and not (r.arrival_timestep > end)
        fc = blocks[3][i]
        r = rollout_components(c, OpenView(fc), fc, fc, ledger, world, params, graph)
        cap += bool(r.capacity_ok) and not (r.arrival_timestep > end)
    p_j, p_path, p_sh, p_cap = joint / n, path / n, shelter / n, cap / n
    return p_j, p_path * p_sh * p_cap, beyond / n


def run_world(world_id: str, seeds, max_pairs: int, n: int, graph) -> dict:
    params = CertParams()
    planner = RiskGreedyPlanner()
    pairs = []
    started = time.perf_counter()
    for seed in seeds:
        scenario, sim, _, overlay, world = build_v4_runtime(world_id, generator_seed=seed, graph=graph)
        while not sim.state.terminal and len(pairs) < max_pairs:
            sim.observe()
            state = sim.prepared_state_for_debug()
            snapshot = evaluate_actions(scenario, state)
            valid = [e.action for e in snapshot.evaluations
                     if e.mechanically_valid and isinstance(e.action, DispatchAction)]
            if valid:
                paths = canonical_paths(graph, overlay.road_state, scenario)
                edge_union = tuple(sorted({e for p in paths.values() for e in p}))
                h = horizon(paths, graph, world, world.horizon_steps - state.current_timestep)
                forecast = forecast_from_state(state, overlay.road_state, scenario)
                root = root_key(incident_id=forecast.incident_id, forecast_hash=forecast.forecast_hash(),
                                graph_fingerprint=graph.graph_fingerprint, ledger_hash=ledger_hash(state),
                                params_id=params.params_id)
                fs = FutureSet(forecast, graph, world, root, horizon_steps=h, edge_ids=edge_union)
                blocks = [Block(fs, i * n) for i in range(4)]
                blocks = [_Sized(b, n) for b in blocks]
                ledger = ledger_view_from_state(state, {})
                end = state.current_timestep + fs.steps
                for action in valid:
                    key = (action.zone_id, action.shelter_id)
                    if key not in paths:
                        continue
                    zone, shelter = state.zone(action.zone_id), state.shelter(action.shelter_id)
                    people = min(scenario.fleet.vehicle_capacity, zone.population_remaining,
                                 shelter.capacity_available)
                    if people <= 0:
                        continue
                    cand = Candidate(action.zone_id, action.shelter_id, people, paths[key], state.current_timestep)
                    p_j, p_m, beyond = evaluate_candidate(cand, blocks, ledger, world, params, graph, end)
                    pairs.append({"seed": seed, "t": state.current_timestep, "action": f"{key[0]}->{key[1]}",
                                  "p_J": p_j, "p_M": p_m, "beyond_H": beyond})
                print(world_id, seed, state.current_timestep, len(pairs),
                      round(time.perf_counter() - started), flush=True)
            decision = planner.choose_action(build_planner_input(scenario, state, snapshot, sim.config))
            sim.step(decision.action)
        if len(pairs) >= max_pairs:
            break
    return {"world_id": world_id, "n": n, "pairs": pairs, "runtime_seconds": round(time.perf_counter() - started)}


class _Sized:
    def __init__(self, block, n):
        self.block, self.n = block, n

    def __len__(self):
        return self.n

    def __getitem__(self, i):
        return self.block[i]


def flip_probability(p_hat: float, n: int) -> float:
    from scipy.stats import binom

    need = math.ceil(THRESHOLD * n - 1e-9)
    q = float(binom.sf(need - 1, n, p_hat))
    return 2 * q * (1 - q)


def merge() -> None:
    pairs, n, beyond = [], 256, []
    for path in sorted(OUT_DIR.glob("g23_pilot_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        n = data["n"]
        pairs += data["pairs"]
    diffs = [p["p_M"] - p["p_J"] for p in pairs]
    mean = sum(diffs) / len(diffs)
    rng = random.Random(0)
    boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(2000))
    lo, hi = boots[49], boots[1949]
    disagree = sum((p["p_J"] >= THRESHOLD) != (p["p_M"] >= THRESHOLD) for p in pairs) / len(pairs)
    floor = sum(flip_probability(p["p_J"], n) for p in pairs) / len(pairs)
    beyond_share = sum(p["beyond_H"] for p in pairs) / len(pairs)
    result = {
        "gate": "G23",
        "n_futures_per_estimate": n,
        "pairs": len(pairs),
        "mean_p_M_minus_p_J": mean,
        "mean_p_M_minus_p_J_ci95": [lo, hi],
        "mean_abs_diff": sum(abs(d) for d in diffs) / len(diffs),
        "verdict_disagreement": disagree,
        "noise_floor": floor,
        "net_disagreement": disagree - floor,
        "share_arrival_beyond_horizon": beyond_share,
        "checks": {
            "pairs_ge_2000": len(pairs) >= 2000,
            "ci_excludes_zero": lo > 0 or hi < 0,
            "net_disagreement_ge_1pct": disagree - floor >= 0.01,
            "beyond_horizon_le_1pct": beyond_share <= 0.01,
        },
    }
    c = result["checks"]
    result["passed"] = c["pairs_ge_2000"] and (c["ci_excludes_zero"] or c["net_disagreement_ge_1pct"])
    (OUT_DIR / "g23.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world")
    parser.add_argument("--max-pairs", type=int, default=1300)
    parser.add_argument("--seeds", type=int, default=60)
    parser.add_argument("--n", type=int, default=256)
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.merge:
        merge()
        return
    result = run_world(args.world, range(620000, 620000 + args.seeds), args.max_pairs, args.n, load_road_graph())
    (OUT_DIR / f"g23_pilot_{args.world}.json").write_text(json.dumps(result) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
