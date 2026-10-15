"""Phase 27 decision-level study (V4_EVALUATION_PREREG.md section 5): raw tables only.

    python scripts/phase27_decision_sample.py --workers 16

Samples every 5th decision state (with at least one candidate) of the P episodes, ordered by regime
(medium, high), seed, timestep, at most 400 states, from data/eval_results/phase27/states/*.jsonl.gz.
For each state and candidate it records the oracle frequency p* (futures k = 100_001..104_096), the joint
certifier verdict on the first 1,024 futures, the product-of-marginals verdict ("P-marginal") and the
separate-checks verdict from disjoint 256-future blocks (k 1-256 joint, 257-512 path, 513-768 shelter,
769-1024 capacity, as in the G23 amendment), plus Q3 variances on the first 50 states with >= 2 candidates.
Writes decisions.jsonl: lines of type "state", "candidate", "q3".
"""

from __future__ import annotations

import argparse
import dataclasses
import gzip
import json
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data/eval_results/phase27"
REGIMES = ("v4-medium-dt2-v1", "v4-high-dt2-v1")
EVERY = 5
MAX_STATES = 400
ORACLE_FIRST, ORACLE_N = 100_001, 4_096
BLOCK = 256
Q3_STATES, Q3_REPEATS = 50, 200
THRESHOLD = 0.95
_GRAPH = None


def _init():
    global _GRAPH
    from src.geospatial import load_road_graph

    _GRAPH = load_road_graph()


class OpenView:
    """Future view with every edge open: isolates the shelter / capacity marginals."""

    def __init__(self, f):
        self._f = f
        self.k, self.start_timestep, self.steps = f.k, f.start_timestep, f.steps

    def edge_open(self, edge_id, t):
        return True

    def __getattr__(self, name):
        return getattr(self._f, name)


def select_states() -> list[dict]:
    rows = []
    for regime in REGIMES:
        for path in sorted((OUT / "states").glob(f"{regime}_*.jsonl.gz"),
                           key=lambda p: int(p.stem.split("_")[-1].split(".")[0])):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                rows += [json.loads(line) for line in handle if line.strip()]
    chosen = rows[::EVERY][:MAX_STATES]
    for i, row in enumerate(chosen):
        row["state_id"] = i
    return chosen


def evaluate_state(row: dict) -> list[dict]:

    from src.certify.certificate import CertificateInputs
    from src.certify.certifier import Verdict, certify, clopper_pearson
    from src.certify.futures import FutureSet, root_key
    from src.certify.gate import ledger_view_hash
    from src.certify.params import get_cert_params
    from src.certify.rollout import candidate_key_for_no_crn, rollout_components, rollout_joint
    from src.sim.world import get_world_config

    started = time.perf_counter()
    inputs = CertificateInputs.from_dict(row["inputs"])
    world = get_world_config(inputs.world_id)
    params = get_cert_params(inputs.params_id)
    fc, view = inputs.forecast, inputs.ledger
    root = root_key(incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
                    graph_fingerprint=_GRAPH.graph_fingerprint, ledger_hash=ledger_view_hash(view),
                    params_id=params.params_id, backend=params.backend)
    fs = FutureSet(fc, _GRAPH, world, root, inputs.horizon_steps, edge_ids=inputs.edge_ids)
    cands = list(inputs.candidates)
    # joint verdict: the certifier itself, first 1,024 futures (three looks 256 / 512 / 1024)
    result = certify(cands, fs, view, world, params, _GRAPH)
    joint = {c.action_key: c for c in result.candidates}
    alpha = params.delta / (params.max_looks * fs.A_MAX)
    # disjoint 256-future blocks for the marginals
    marg = {}
    for c in cands:
        path = shelter = cap = 0
        for i in range(BLOCK):
            r = rollout_joint(c, fs.future(BLOCK + 1 + i), view, world, params, _GRAPH)
            path += bool(r.path_ok)
            f = fs.future(2 * BLOCK + 1 + i)
            r = rollout_components(c, OpenView(f), f, f, view, world, params, _GRAPH)
            shelter += bool(r.shelter_ok)
            f = fs.future(3 * BLOCK + 1 + i)
            r = rollout_components(c, OpenView(f), f, f, view, world, params, _GRAPH)
            cap += bool(r.capacity_ok)
        marg[c.action_key] = (path, shelter, cap)
    fs._cache.clear()
    # oracle over 4,096 disjoint futures; utilities kept for Q3
    oracle_ok = {c.action_key: 0 for c in cands}
    utilities = {c.action_key: np.zeros(ORACLE_N) for c in cands}
    for j in range(ORACLE_N):
        f = fs.future(ORACLE_FIRST + j)
        for c in cands:
            r = rollout_joint(c, f, view, world, params, _GRAPH)
            oracle_ok[c.action_key] += bool(r.z)
            utilities[c.action_key][j] = r.utility
        if j % 256 == 255:
            fs._cache.clear()
    out = [{"type": "state", "state_id": row["state_id"], "regime": row["regime"], "seed": row["seed"],
            "timestep": row["timestep"], "candidates": len(cands), "looks": result.looks,
            "n_final": result.n_final, "seconds": round(time.perf_counter() - started, 1)}]
    for c in cands:
        key = c.action_key
        cc = joint[key]
        p_path, p_shelter, p_cap = (m / BLOCK for m in marg[key])
        product = p_path * p_shelter * p_cap
        prod_lo, _ = clopper_pearson(int(round(product * BLOCK)), BLOCK, alpha)
        sep_lo = [clopper_pearson(m, BLOCK, alpha)[0] for m in marg[key]]
        p_star = oracle_ok[key] / ORACLE_N
        out.append({
            "type": "candidate", "state_id": row["state_id"], "action_key": key, "people": c.people,
            "p_star": p_star, "borderline": abs(p_star - THRESHOLD) < 0.007,
            "joint_verdict": cc.verdict.value, "joint_lower": cc.lower, "joint_upper": cc.upper,
            "joint_n": cc.n, "joint_successes": cc.successes,
            "p_path": p_path, "p_shelter": p_shelter, "p_capacity": p_cap, "p_product": product,
            "product_lower": prod_lo, "product_feasible": prod_lo >= THRESHOLD,
            "separate_lowers": sep_lo, "separate_feasible": all(lo >= THRESHOLD for lo in sep_lo),
        })
    if len(cands) >= 2:  # the analysis uses the first 50 such states by state_id
        order = sorted(cands, key=lambda c: -oracle_ok[c.action_key])[:2]
        a, b = (utilities[order[0].action_key], utilities[order[1].action_key])
        rng = np.random.default_rng(27_000 + row["state_id"])
        span = ORACLE_N - BLOCK + 1
        off_b = int(candidate_key_for_no_crn(order[1])[:8], 16) % span
        crn, indep = [], []
        for _ in range(Q3_REPEATS):
            o = int(rng.integers(0, span))
            crn.append(float((a[o:o + BLOCK] - b[o:o + BLOCK]).mean()))
            o2 = (o + off_b) % span
            indep.append(float(a[o:o + BLOCK].mean() - b[o2:o2 + BLOCK].mean()))
        out.append({"type": "q3", "state_id": row["state_id"], "keys": [c.action_key for c in order],
                    "var_crn": float(np.var(crn, ddof=1)), "var_indep": float(np.var(indep, ddof=1)),
                    "repeats": Q3_REPEATS})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    states = select_states()
    path = OUT / "decisions.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(l)["state_id"] for l in path.read_text(encoding="utf-8").splitlines()
                if l.strip() and json.loads(l)["type"] == "state"}
    todo = [s for s in states if s["state_id"] not in done]
    print(f"{len(states)} sampled states, {len(todo)} to evaluate", flush=True)
    with Pool(args.workers, initializer=_init) as pool, path.open("a", encoding="utf-8") as out:
        for lines in pool.imap_unordered(evaluate_state, todo):
            for line in lines:
                out.write(json.dumps(line, sort_keys=True) + "\n")
            out.flush()
            print("state", lines[0]["state_id"], lines[0]["seconds"], "s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
