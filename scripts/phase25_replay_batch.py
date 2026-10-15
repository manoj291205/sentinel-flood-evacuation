"""Phase 25 replay batch: certify real decisions (v4-cert-test-v1) and replay each from stored inputs.

    python scripts/phase25_replay_batch.py --n 1000 --workers 16

Seeds start at 1_060_000; each seed is a fresh v4 episode driven by the certifier until the
episode ends or enough decisions are collected. Writes data/eval_results/phase25/replay_batch.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data/eval_results/phase25/replay_batch.json"
FIRST_SEED = 1_060_000
OPERATOR = {"decision": "AUTO", "actor": "phase25-batch", "reason": ""}
WORLD = "v4-medium-dt2-v1"


def run_seed(args):
    seed, max_decisions = args
    from src.actuation.commands import InMemorySink
    from src.certify.gate import CertifiedGate
    from src.certify.ledger import SimLedgerAdapter
    from src.certify.params import get_cert_params
    from src.certify.replay import replay_certificate
    from src.geospatial import load_road_graph
    from src.geospatial.v4_runtime import build_v4_runtime
    from src.safety import evaluate_actions

    graph = load_road_graph()
    scenario, sim, graph, overlay, world = build_v4_runtime(WORLD, generator_seed=seed, graph=graph)
    ledger = SimLedgerAdapter(sim)
    gate = CertifiedGate(scenario, graph, world, get_cert_params("v4-cert-test-v1"), ledger,
                         sink=InMemorySink(), world_id=WORLD)
    matched, bad = 0, []
    while not sim.state.terminal and matched + len(bad) < max_decisions:
        sim.observe()
        state = sim.prepared_state_for_debug()
        result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
        decision = gate.commit(result, inputs, operator=OPERATOR)
        cert = decision.certificate
        report = replay_certificate(cert, ledger.inputs(cert["cert_id"]), graph=graph)
        if report.result == "MATCH":
            matched += 1
        else:
            bad.append({"seed": seed, "cert_id": cert["cert_id"], "fields": list(report.mismatched_fields)})
    return seed, matched, bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--per-seed", type=int, default=20)
    args = parser.parse_args()
    started = time.perf_counter()
    matched, mismatches, seeds = 0, [], 0
    next_seed = FIRST_SEED
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        while matched + len(mismatches) < args.n:
            need = args.n - matched - len(mismatches)
            batch = [(next_seed + i, args.per_seed) for i in range(args.workers)]
            next_seed += args.workers
            for seed, ok, bad in pool.map(run_seed, batch):
                seeds += 1
                matched += ok
                mismatches += bad
            print(f"{matched + len(mismatches)}/{args.n} decisions, {len(mismatches)} mismatches, "
                  f"{round(time.perf_counter() - started)} s", flush=True)
    total = matched + len(mismatches)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "world_id": WORLD, "params_id": "v4-cert-test-v1", "first_seed": FIRST_SEED, "seeds_used": seeds,
        "n": total, "matched": matched, "match_rate": matched / total if total else None,
        "mismatches": mismatches, "wall_seconds": round(time.perf_counter() - started),
    }, indent=2), encoding="utf-8")
    print("match_rate", matched / total if total else None, "n", total)
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
