"""GATE 1A.5 -- tail characterisation. Is the headroom real, structured, and worth it?

Gate 1A cleared variant B on bundle_aware scoring 48.3% optimal at 4x6. But its MEDIAN
gap was 1.1%: the heuristic is usually near-optimal and occasionally catastrophic. Four
questions, per PHASE1_PLAN.md 1A.5, all offline:

  Q1  is the 71.2% mean gap a small-denominator artifact?      -> absolute + normalised
  Q2  where does the available improvement actually live?      -> regret concentration
  Q3  is the tail structured or arbitrary?                     -> tree AUC vs SHUFFLED null
  Q4  can a cheap planner close it, and AT WHAT LATENCY?       -> score + per-decision cost

Q3's null and Q4's latency are not optional extras: a tree on this many features at this n
will find something, and a planner that buys quality with seconds per decision is not
comparable to a policy that answers in milliseconds.

Everything is fictional, as in Gate 1A. Run: .venv/bin/python scripts/tail_check.py
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "eval_results" / "gate1a5_tail_check.json"

_spec = importlib.util.spec_from_file_location("gc_mod", Path(__file__).parent / "greedy_check.py")
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)

N_INSTANCES = 200
gc.CFG.update({"cells": 4, "timesteps": 6, "stock_scale": 2, "lag": True})


# ---------------------------------------------------------------------------------
# generic mid-episode rollout, so a planner can search from an arbitrary state
# ---------------------------------------------------------------------------------
def advance(inst, delivered, pending, t):
    d2 = [dict(d) for d in delivered]
    for (at, pr, pc) in pending:
        if at <= t:
            d2[pc][pr] += 1
    return d2, tuple(q for q in pending if q[0] > t)


def apply_action(inst, stock, pending, act, t):
    s2 = dict(stock)
    p2 = pending
    if act is not None:
        r, c = act
        s2[r] -= 1
        p2 = pending + ((t + inst["cells"][c]["lag"], r, c),)
    return s2, p2


def rollout_from(inst, t, stock, delivered, pending, prefix, tail_choose):
    """Total reward from timestep t to the horizon, applying `prefix` then `tail_choose`."""
    total = 0.0
    for tt in range(t, gc.CFG["timesteps"]):
        act = (prefix[tt - t] if tt - t < len(prefix)
               else tail_choose(inst, stock, delivered, tt, pending))
        stock, pending = apply_action(inst, stock, pending, act, tt)
        delivered, pending = advance(inst, delivered, pending, tt)
        total += gc.step_reward(inst, delivered, tt)
    return total


def make_lookahead(k: int):
    """Exhaustive over the next k dispatches, bundle_aware tail, commit the first action."""
    def choose(inst, stock, delivered, t, pending=()):
        best_val, best_act, seen = None, None, False
        def rec(depth, st, dl, pd, tt, prefix):
            nonlocal best_val, best_act, seen
            if depth == k or tt >= gc.CFG["timesteps"]:
                val = rollout_from(inst, t, dict(stock), [dict(d) for d in delivered],
                                   pending, prefix, gc.bundle_aware)
                seen = True
                if best_val is None or val > best_val:
                    best_val, best_act = val, prefix[0] if prefix else None
                return
            for act in gc.legal_actions(inst, st, dl, pd):
                s2, p2 = apply_action(inst, st, pd, act, tt)
                d2, p3 = advance(inst, dl, p2, tt)
                rec(depth + 1, s2, d2, p3, tt + 1, prefix + [act])
        rec(0, dict(stock), [dict(d) for d in delivered], pending, t, [])
        return best_act if seen else None
    return choose


def make_beam(width: int):
    """Beam search over the full remaining horizon, bundle_aware used only for scoring."""
    def choose(inst, stock, delivered, t, pending=()):
        beams = [(0.0, dict(stock), [dict(d) for d in delivered], pending, None)]
        for tt in range(t, gc.CFG["timesteps"]):
            nxt = []
            for (acc, st, dl, pd, first) in beams:
                for act in gc.legal_actions(inst, st, dl, pd):
                    s2, p2 = apply_action(inst, st, pd, act, tt)
                    d2, p3 = advance(inst, dl, p2, tt)
                    nxt.append((acc + gc.step_reward(inst, d2, tt), s2, d2, p3,
                                first if first is not None or tt > t else act))
            nxt.sort(key=lambda x: -x[0])
            beams = nxt[:width]
            if not beams:
                return None
        return beams[0][4]
    return choose


def run_timed(inst, choose):
    """Run a policy, returning (total reward, seconds per decision)."""
    stock = dict(inst["stock"])
    delivered = [{r: 0 for r in gc.RESOURCES} for _ in range(gc.CFG["cells"])]
    pending: tuple = ()
    total, elapsed, decisions = 0.0, 0.0, 0
    for t in range(gc.CFG["timesteps"]):
        t0 = time.perf_counter()
        act = choose(inst, stock, delivered, t, pending)
        elapsed += time.perf_counter() - t0
        decisions += 1
        stock, pending = apply_action(inst, stock, pending, act, t)
        delivered, pending = advance(inst, delivered, pending, t)
        total += gc.step_reward(inst, delivered, t)
    return total, elapsed / decisions


# ---------------------------------------------------------------------------------
def features(inst) -> dict:
    lags = [c["lag"] for c in inst["cells"]]
    pops = [c["population"] for c in inst["cells"]]
    need = sum(sum(c["need"].values()) for c in inst["cells"])
    stock = sum(inst["stock"].values())
    sev0 = [c["severity"][0] for c in inst["cells"]]
    sevT = [c["severity"][-1] for c in inst["cells"]]
    inversions = sum(
        1 for i in range(len(sev0)) for j in range(i + 1, len(sev0))
        if (sev0[i] - sev0[j]) * (sevT[i] - sevT[j]) < 0
    )
    return {
        "lag_spread": max(lags) - min(lags),
        "lag_mean": statistics.fmean(lags),
        "stock_tightness": stock / need if need else 0.0,
        "severity_crossovers": inversions,
        "sev_mean": statistics.fmean(sev0 + sevT),
        "sev_range": max(sev0 + sevT) - min(sev0 + sevT),
        "pop_spread": max(pops) / max(min(pops), 1),
        "pop_total": sum(pops),
        "bundle_cost_mean": need / len(inst["cells"]),
        "n_rising": sum(1 for c in inst["cells"] if c["trend"] == "rise"),
    }


def main() -> int:
    import random
    rng = random.Random(gc.SEED)
    prng = random.Random(gc.SEED + 1)
    policies = {
        "random_allowed": gc.random_allowed(prng),
        "myopic_tiebreak": gc.myopic_tiebreak,
        "bundle_aware": gc.bundle_aware,
        "lookahead_k2": make_lookahead(2),
        "lookahead_k3": make_lookahead(3),
        "beam_w5": make_beam(5),
    }
    rows = []
    lat = {k: [] for k in policies}
    t_start = time.time()
    for i in range(N_INSTANCES):
        inst = gc.make_instance(rng)
        opt, _plan, _leaves = gc.brute_force(inst)
        rec = {"optimum": opt, "features": features(inst), "scores": {}}
        for name, choose in policies.items():
            val, per_dec = run_timed(inst, choose)
            assert val <= opt + 1e-9, f"{name} beat the optimum -- oracle is wrong"
            rec["scores"][name] = val
            lat[name].append(per_dec)
        rows.append(rec)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{N_INSTANCES} instances ({time.time()-t_start:.0f}s)", flush=True)

    OUT.write_text(json.dumps({
        "_note": "Gate 1A.5 raw data. Fictional instances. 4 cells x 6 timesteps, lag on.",
        "config": dict(gc.CFG), "n": N_INSTANCES, "seed": gc.SEED,
        "latency_seconds_per_decision": {k: statistics.fmean(v) for k, v in lat.items()},
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name} ({time.time()-t_start:.0f}s total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
