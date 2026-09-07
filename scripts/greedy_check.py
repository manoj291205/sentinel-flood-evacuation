"""GATE 1A -- is a multi-resource allocation task actually harder than greedy?

Throwaway decision experiment for EXPANSION_PLAN.md Phase 1. NOT part of the package,
imported by nothing, and deliberately self-contained: it exists to answer one question
before any of the v2 environment is built.

  v1's finding was that the reward is a closed-form function of one observation, so
  greedy-argmax IS the oracle by construction and the RL policy cannot beat it. Adding
  resources does not automatically fix that. If the v2 reward still decomposes into
  independent per-allocation terms, greedy stays optimal and the rebuild arrives at the
  same result for far more work.

So: build 200 tiny instances of the PROPOSED v2 task, solve each EXHAUSTIVELY by brute
force, and see how often simple heuristics hit the true optimum.

The proposed task has all three non-separability sources from EXPANSION_PLAN.md 1.1:
  (a) COMPLEMENTARITY  -- a shelter protects nobody until it holds a minimum bundle of
                          EVERY resource type. The first delivery to a shelter is worth
                          exactly zero on its own.
  (b) CONTENTION       -- one finite depot, so supplying A forecloses supplying B.
  (c) TIME-DEPENDENCE  -- severity follows a scripted path and reward accrues per
                          timestep, so completing a bundle early is worth more than
                          completing it late, and a cell that is calm now may be severe
                          in two steps.

HONESTY NOTE ON THE BASELINES. The gate is only meaningful if the heuristics are the
best ones a competent person would write by hand. A strawman myopic baseline would
"pass" this gate and green-light a rebuild that a 20-line heuristic could beat. So four
heuristics are measured, including a bundle-aware, horizon-aware one, and THE GATE IS
DECIDED ON THE STRONGEST OF THEM, not on the myopic one.

Everything here is fictional: populations, severities, stock and demands are invented for
this experiment, as in v1. Nothing is presented as real data.

Run:  .venv/bin/python scripts/greedy_check.py
"""

from __future__ import annotations

import itertools
import json
import random
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "eval_results" / "gate1a_greedy_check.json"

SEED = 20260905
N_INSTANCES = 200
RESOURCES = ("water", "medical")

# Instance size. EXPANSION_PLAN 1.2 prescribes 3 cells / 3 timesteps, which is what the
# gate is decided on. --sweep re-runs the same task at larger horizons, to separate "this
# DESIGN is greedy-solvable" from "these INSTANCES were too small to need planning".
CFG = {"cells": 3, "timesteps": 3, "stock_scale": 1, "lag": False}

# DESIGN VARIANT B -- delivery lag. A dispatch to cell c arrives lag[c] timesteps later,
# so supplies sit in transit. This is the strengthening EXPANSION_PLAN 1.1 asks for when
# the gate fails: it adds scheduling structure that per-bundle greedy cannot see, because
# while one cell's goods are in transit the depot can be dispatching to another. Physical
# and defensible -- it is travel time, which v1 already models as travel_cost_minutes.
SEVERE = 0.70          # the severity at which unmet demand starts costing
UNMET_PENALTY = 0.50   # weight on the unmet-critical-demand term

# Declared generation distribution -- written into the output file so a reader can judge
# whether the instances are fair rather than tuned to produce a verdict.
def distribution() -> dict:
    return {
        "n_instances": N_INSTANCES,
        "seed": SEED,
        "cells": CFG["cells"],
        "timesteps": CFG["timesteps"],
        "resources": list(RESOURCES),
        "population_per_cell": "randint(50, 400) rounded to 10",
        "need_water_per_cell": "randint(1, 2) units",
        "need_medical_per_cell": "1 unit",
        "severity_t0": "uniform(0.05, 0.95)",
        "severity_path": "per cell, one of rise/fall/flat; step = uniform(0.10, 0.30), clipped to [0,1]",
        "depot_stock_water": "randint(1, 3) units",
        "depot_stock_medical": "randint(1, 2) units",
        "deliveries_per_timestep": 1,
        "delivery_lag_per_cell": ("randint(0, 2) timesteps (variant B)" if CFG["lag"]
                                 else "disabled (variant A)"),
        "note": (
            "Stock is deliberately scarce relative to total demand, so the instances contain "
            "genuine contention. All values are FICTIONAL, invented for this experiment."
        ),
    }


# ---------------------------------------------------------------------------------
# the proposed v2 task
# ---------------------------------------------------------------------------------
def make_instance(rng: random.Random) -> dict:
    cells = []
    for _ in range(CFG["cells"]):
        s = rng.uniform(0.05, 0.95)
        trend = rng.choice(("rise", "fall", "flat"))
        step = rng.uniform(0.10, 0.30)
        path = []
        for _t in range(CFG["timesteps"]):
            path.append(round(min(1.0, max(0.0, s)), 3))
            s += step if trend == "rise" else (-step if trend == "fall" else 0.0)
        cells.append({
            "population": rng.randrange(50, 401, 10),
            "need": {"water": rng.randint(1, 2), "medical": 1},
            "severity": path,
            "trend": trend,
            "lag": rng.randint(0, 2) if CFG["lag"] else 0,
        })
    return {
        "cells": cells,
        "stock": {"water": rng.randint(1, 3) * CFG["stock_scale"],
                  "medical": rng.randint(1, 2) * CFG["stock_scale"]},
    }


def committed(delivered: list[dict], pending: tuple, c: int, r: str) -> int:
    """Units of r that cell c already has OR has in transit. Dispatching beyond need is
    waste, so the mask uses this rather than arrivals alone."""
    return delivered[c][r] + sum(1 for (_at, pr, pc) in pending if pc == c and pr == r)


def legal_actions(inst: dict, stock: dict, delivered: list[dict], pending: tuple = ()) -> list[tuple[str, int] | None]:
    """Masked action set: (resource, cell), plus hold.

    Infeasible pairs are structurally excluded -- no stock left, or that cell's need for
    that resource is already met (over-delivery is pure waste and only inflates the
    search). This is the same masking principle as v1, which is the part that works.
    """
    acts: list[tuple[str, int] | None] = []
    for r in RESOURCES:
        if stock[r] <= 0:
            continue
        for c in range(CFG["cells"]):
            if committed(delivered, pending, c, r) < inst["cells"][c]["need"][r]:
                acts.append((r, c))
    acts.append(None)  # hold
    return acts


def functional(inst: dict, delivered: list[dict], c: int) -> bool:
    """COMPLEMENTARITY: every resource type must meet its need. Partial bundles are worth
    nothing -- a shelter with water but no medical team protects no one."""
    need = inst["cells"][c]["need"]
    return all(delivered[c][r] >= need[r] for r in RESOURCES)


def step_reward(inst: dict, delivered: list[dict], t: int) -> float:
    total = 0.0
    for c, cell in enumerate(inst["cells"]):
        sev = cell["severity"][t]
        if functional(inst, delivered, c):
            total += cell["population"] * sev / 1000.0
        elif sev >= SEVERE:
            total -= UNMET_PENALTY * cell["population"] * sev / 1000.0
    return total


def rollout(inst: dict, plan: list[tuple[str, int] | None]) -> float:
    """Score a full action sequence. Reward accrues AFTER each timestep's delivery, which
    is what makes finishing a bundle early worth more than finishing it late."""
    stock = dict(inst["stock"])
    delivered = [{r: 0 for r in RESOURCES} for _ in range(CFG["cells"])]
    pending: list = []
    total = 0.0
    for t, act in enumerate(plan):
        if act is not None:
            r, c = act
            stock[r] -= 1
            pending.append((t + inst["cells"][c]["lag"], r, c))
        for (at, pr, pc) in [q for q in pending if q[0] <= t]:
            delivered[pc][pr] += 1
        pending = [q for q in pending if q[0] > t]
        total += step_reward(inst, delivered, t)
    return total


# ---------------------------------------------------------------------------------
# the oracle -- exhaustive, with the exhaustiveness actually asserted
# ---------------------------------------------------------------------------------
def brute_force(inst: dict) -> tuple[float, list, int]:
    best_val, best_plan, leaves = float("-inf"), None, 0

    def advance(delivered, pending, t):
        """Apply arrivals due at t. Returns (new_delivered, new_pending)."""
        arrived = [dict(d) for d in delivered]
        for (at, pr, pc) in pending:
            if at <= t:
                arrived[pc][pr] += 1
        return arrived, tuple(q for q in pending if q[0] > t)

    def recurse(t, stock, delivered, pending, plan, acc):
        nonlocal best_val, best_plan, leaves
        if t == CFG["timesteps"]:
            leaves += 1
            if acc > best_val:
                best_val, best_plan = acc, list(plan)
            return
        for act in legal_actions(inst, stock, delivered, pending):
            if act is None:
                d2, p2 = advance(delivered, pending, t)
                plan.append(None)
                recurse(t + 1, stock, d2, p2, plan, acc + step_reward(inst, d2, t))
                plan.pop()
            else:
                r, c = act
                stock[r] -= 1
                p_new = pending + ((t + inst["cells"][c]["lag"], r, c),)
                d2, p2 = advance(delivered, p_new, t)
                plan.append(act)
                recurse(t + 1, stock, d2, p2, plan, acc + step_reward(inst, d2, t))
                plan.pop()
                stock[r] += 1

    recurse(0, dict(inst["stock"]),
            [{r: 0 for r in RESOURCES} for _ in range(CFG["cells"])], (), [], 0.0)
    return best_val, best_plan, leaves


def count_leaves(inst: dict) -> int:
    """Independent recount of the search tree, used to assert the search really is
    exhaustive rather than pruned by a bug."""
    def rec(t, stock, delivered, pending):
        if t == CFG["timesteps"]:
            return 1
        n = 0
        for act in legal_actions(inst, stock, delivered, pending):
            if act is None:
                p_new = pending
            else:
                r, c = act
                stock[r] -= 1
                p_new = pending + ((t + inst["cells"][c]["lag"], r, c),)
            d2 = [dict(d) for d in delivered]
            for (at, pr, pc) in p_new:
                if at <= t:
                    d2[pc][pr] += 1
            n += rec(t + 1, stock, d2, tuple(q for q in p_new if q[0] > t))
            if act is not None:
                stock[act[0]] += 1
        return n
    return rec(0, dict(inst["stock"]),
               [{r: 0 for r in RESOURCES} for _ in range(CFG["cells"])], ())


# ---------------------------------------------------------------------------------
# heuristics -- the gate is decided on the STRONGEST of these
# ---------------------------------------------------------------------------------
def run_policy(inst: dict, choose) -> float:
    stock = dict(inst["stock"])
    delivered = [{r: 0 for r in RESOURCES} for _ in range(CFG["cells"])]
    pending: tuple = ()
    total = 0.0
    for t in range(CFG["timesteps"]):
        act = choose(inst, stock, delivered, t, pending)
        if act is not None:
            r, c = act
            stock[r] -= 1
            pending = pending + ((t + inst["cells"][c]["lag"], r, c),)
        for (at, pr, pc) in pending:
            if at <= t:
                delivered[pc][pr] += 1
        pending = tuple(q for q in pending if q[0] > t)
        total += step_reward(inst, delivered, t)
    return total


def _immediate(inst, delivered, pending, act, t):
    """Reward at t if `act` is dispatched now, accounting for what arrives at t."""
    d2 = [dict(d) for d in delivered]
    p2 = pending + ((t + inst["cells"][act[1]]["lag"], act[0], act[1]),) if act else pending
    for (at, pr, pc) in p2:
        if at <= t:
            d2[pc][pr] += 1
    return step_reward(inst, d2, t)


def myopic_pure(inst, stock, delivered, t, pending=()):
    """Maximise THIS timestep's reward only. Ties broken by first legal action.

    The baseline EXPANSION_PLAN 1.2 names. Under complementarity the first delivery to a
    shelter scores zero, so on most steps every action ties and this policy is blind."""
    best, best_act = None, None
    for act in legal_actions(inst, stock, delivered, pending):
        val = _immediate(inst, delivered, pending, act, t)
        if best is None or val > best:
            best, best_act = val, act
    return best_act


def myopic_tiebreak(inst, stock, delivered, t, pending=()):
    """Same, but ties broken sensibly: prefer the cell with the most people at risk now.
    A fairer reading of 'myopic greedy' than the pure version."""
    best, best_act = None, None
    for act in legal_actions(inst, stock, delivered, pending):
        val = _immediate(inst, delivered, pending, act, t)
        tie = (-1.0 if act is None
               else inst["cells"][act[1]]["population"] * inst["cells"][act[1]]["severity"][t] / 1000.0)
        if best is None or (val, tie) > best:
            best, best_act = (val, tie), act
    return best_act


def bundle_aware(inst, stock, delivered, t, pending=()):
    """The strong hand-written heuristic, and the one the gate is decided on.

    Sees complementarity, the horizon AND transit time: for each unfinished cell it
    computes exactly when the bundle would land if it committed to that cell now --
    dispatches go one per timestep, and each arrives lag[c] later -- checks the depot can
    cover the remainder, and values it by population times the severity over the
    timesteps remaining AFTER arrival. Then it commits to the best cell and feeds it.

    This is what a competent engineer writes instead of training a policy, and it is
    given the correct arrival model so the gate is not decided against a strawman. What
    it does NOT do is interleave dispatches to several cells while goods are in transit
    -- that is precisely the planning structure the lag variant introduces."""
    horizon = CFG["timesteps"]
    best_score, best_cell = 0.0, None
    for c, cell in enumerate(inst["cells"]):
        if functional(inst, delivered, c):
            continue
        missing = {r: cell["need"][r] - committed(delivered, pending, c, r) for r in RESOURCES}
        cost = sum(max(0, v) for v in missing.values())
        if any(missing[r] > stock[r] for r in RESOURCES):
            continue                                  # depot cannot cover the remainder
        in_flight = [at for (at, _pr, pc) in pending if pc == c]
        # last dispatch lands at t + cost - 1 + lag; already-flying units land at their own time
        arrival = max(in_flight + ([t + cost - 1 + cell["lag"]] if cost else [t]))
        if arrival > horizon - 1:
            continue                                  # cannot land in time to be worth anything
        payoff = cell["severity"][arrival:]
        if not payoff:
            continue
        score = cell["population"] * sum(payoff) / 1000.0
        score += UNMET_PENALTY * cell["population"] * sum(
            s for s in payoff if s >= SEVERE) / 1000.0        # penalty avoided
        if score > best_score:
            best_score, best_cell = score, c
    if best_cell is None:
        return myopic_tiebreak(inst, stock, delivered, t, pending)
    cell = inst["cells"][best_cell]
    for r in RESOURCES:
        if committed(delivered, pending, best_cell, r) < cell["need"][r] and stock[r] > 0:
            return (r, best_cell)
    return None


def random_allowed(rng):
    def choose(inst, stock, delivered, t, pending=()):
        return rng.choice(legal_actions(inst, stock, delivered, pending))
    return choose


# ---------------------------------------------------------------------------------
def evaluate(n_instances: int = N_INSTANCES, quiet: bool = False) -> dict:
    rng = random.Random(SEED)
    pol_rng = random.Random(SEED + 1)
    policies = {
        "random_allowed": random_allowed(pol_rng),
        "myopic_pure": myopic_pure,
        "myopic_tiebreak": myopic_tiebreak,
        "bundle_aware": bundle_aware,
    }
    stats = {k: {"optimal": 0, "gaps": []} for k in policies}
    degenerate = 0
    total_leaves = 0
    instances = []

    for _ in range(n_instances):
        inst = make_instance(rng)
        opt, plan, leaves = brute_force(inst)

        # exhaustiveness assertions
        assert leaves == count_leaves(inst), "search tree was pruned -- not exhaustive"
        assert plan is not None and len(plan) == CFG["timesteps"]
        assert abs(rollout(inst, plan) - opt) < 1e-9, "best plan does not reproduce its value"
        total_leaves += leaves

        scores = {}
        for name, choose in policies.items():
            val = run_policy(inst, choose)
            assert val <= opt + 1e-9, f"{name} beat the brute-force optimum -- oracle is wrong"
            scores[name] = val

        span = opt - min(scores.values())
        if abs(span) < 1e-9 and all(abs(v - opt) < 1e-9 for v in scores.values()):
            degenerate += 1        # every policy ties: the instance decides nothing

        for name, val in scores.items():
            if val >= opt - 1e-9:
                stats[name]["optimal"] += 1
            denom = abs(opt) if abs(opt) > 1e-9 else 1.0
            stats[name]["gaps"].append((opt - val) / denom)

        instances.append({"optimum": round(opt, 4),
                          "scores": {k: round(v, 4) for k, v in scores.items()},
                          "leaves": leaves})

    rows = []
    for name in policies:
        gaps = stats[name]["gaps"]
        rows.append({
            "policy": name,
            "optimal_pct": 100.0 * stats[name]["optimal"] / n_instances,
            "mean_gap_pct": 100.0 * statistics.fmean(gaps),
            "median_gap_pct": 100.0 * statistics.median(gaps),
            "p90_gap_pct": 100.0 * sorted(gaps)[int(0.9 * len(gaps)) - 1],
            "max_gap_pct": 100.0 * max(gaps),
        })

    strongest = max(rows, key=lambda r: r["optimal_pct"])
    pct = strongest["optimal_pct"]
    verdict = ("STOP -- still greedy-solvable; strengthen the design (EXPANSION_PLAN 1.1)"
               if pct > 95 else
               "WORKABLE -- there is headroom for RL to be worth something" if pct >= 70
               else "IDEAL -- proceed to Phase 1")

    summary = {"rows": rows, "strongest": strongest, "verdict": verdict,
               "degenerate": degenerate, "leaves": total_leaves, "n": n_instances,
               "cfg": dict(CFG)}
    if quiet:
        return summary

    w = 78
    print("=" * w)
    print(f"GATE 1A -- greedy vs brute force on the proposed v2 task"
          f"  ({n_instances} instances, seed {SEED})")
    print("=" * w)
    print(f"{'policy':<20}{'optimal':>10}{'mean gap':>11}{'median':>10}"
          f"{'p90 gap':>10}{'max gap':>10}")
    print("-" * w)
    for r in rows:
        print(f"{r['policy']:<20}{r['optimal_pct']:>9.1f}%{r['mean_gap_pct']:>10.1f}%"
              f"{r['median_gap_pct']:>9.1f}%{r['p90_gap_pct']:>9.1f}%{r['max_gap_pct']:>9.1f}%")
    print("-" * w)
    print(f"search: {total_leaves:,} leaves brute-forced, exhaustiveness asserted per instance")
    print(f"instances where every policy tied the optimum (decide nothing): "
          f"{degenerate}/{n_instances}")
    print()
    print(f"GATE DECIDED ON THE STRONGEST HEURISTIC: {strongest['policy']} at {pct:.1f}% optimal")
    print(f"VERDICT: {verdict}")
    print("=" * w)

    OUT.write_text(json.dumps({
        "_note": (
            "Gate 1A decision experiment for EXPANSION_PLAN.md Phase 1. Fictional "
            "instances. The gate is decided on the STRONGEST heuristic, not the myopic "
            "one, so that a weak baseline cannot green-light the rebuild."
        ),
        "distribution": distribution(),
        "results": rows,
        "strongest_heuristic": strongest["policy"],
        "verdict": verdict,
        "degenerate_instances": degenerate,
        "total_brute_force_leaves": total_leaves,
        "instances": instances,
    }, indent=2) + "\n")
    return summary


def sweep() -> int:
    """Re-run the SAME task at larger horizons.

    Gate 1A's prescribed size (3 cells, 3 timesteps, 1 delivery per step) allows at most
    one bundle to be completed, so "pick the best completable bundle" is trivially
    optimal. That is a property of the INSTANCE SIZE, not necessarily of the design. This
    separates the two: if bundle_aware stays at 100% as the horizon grows and several
    bundles start competing, the design really is greedy-solvable and Phase 1 must be
    redesigned. If it degrades, the gate instances were simply too small.
    """
    sizes = [
        {"cells": 3, "timesteps": 3, "stock_scale": 1, "n": 200},
        {"cells": 3, "timesteps": 4, "stock_scale": 1, "n": 200},
        {"cells": 3, "timesteps": 5, "stock_scale": 2, "n": 150},
        {"cells": 4, "timesteps": 5, "stock_scale": 2, "n": 100},
        {"cells": 4, "timesteps": 6, "stock_scale": 2, "n": 60},
    ]
    w = 78
    print("=" * w)
    print("GATE 1A SWEEP -- does the greedy verdict survive a longer horizon?")
    print("=" * w)
    print(f"{'cells x steps':<16}{'n':>5}{'leaves/inst':>13}{'bundle_aware':>15}"
          f"{'myopic_tiebreak':>17}{'random':>10}")
    print("-" * w)
    out = []
    for s in sizes:
        n = s.pop("n")
        CFG.update(s)
        r = evaluate(n_instances=n, quiet=True)
        by = {row["policy"]: row for row in r["rows"]}
        print(f"{CFG['cells']}x{CFG['timesteps']:<14}{n:>5}{r['leaves'] // n:>13,}"
              f"{by['bundle_aware']['optimal_pct']:>14.1f}%"
              f"{by['myopic_tiebreak']['optimal_pct']:>16.1f}%"
              f"{by['random_allowed']['optimal_pct']:>9.1f}%")
        out.append({"cfg": dict(CFG), "n": n,
                    "bundle_aware_optimal_pct": by["bundle_aware"]["optimal_pct"],
                    "bundle_aware_mean_gap_pct": by["bundle_aware"]["mean_gap_pct"],
                    "myopic_tiebreak_optimal_pct": by["myopic_tiebreak"]["optimal_pct"]})
    print("-" * w)
    best = max(o["bundle_aware_optimal_pct"] for o in out)
    worst = min(o["bundle_aware_optimal_pct"] for o in out)
    print(f"bundle_aware across sizes: {worst:.1f}% - {best:.1f}% optimal")
    if worst > 95:
        print("READING: the hand-written heuristic stays optimal as the horizon grows.")
        print("         The DESIGN is greedy-solvable. Phase 1 must be redesigned (1.1).")
    else:
        print("READING: the heuristic degrades as the horizon grows, so the design is not")
        print("         inherently greedy-solvable -- the 3x3 gate instances were too")
        print("         small to require planning. Re-gate at the larger size.")
    print("=" * w)
    (OUT.parent / "gate1a_sweep.json").write_text(json.dumps(
        {"_note": "Gate 1A horizon sweep. Fictional instances.", "sizes": out}, indent=2) + "\n")
    return 0


def compare() -> int:
    """Variant A (no lag) vs variant B (delivery lag), at each size.

    This is the 'return to 1.1 and strengthen the design' step: it measures whether
    adding transit time actually buys planning depth, or just adds a parameter."""
    sizes = [
        {"cells": 3, "timesteps": 3, "stock_scale": 1, "n": 200},
        {"cells": 3, "timesteps": 4, "stock_scale": 1, "n": 200},
        {"cells": 3, "timesteps": 5, "stock_scale": 2, "n": 150},
        {"cells": 4, "timesteps": 5, "stock_scale": 2, "n": 100},
        {"cells": 4, "timesteps": 6, "stock_scale": 2, "n": 60},
    ]
    w = 78
    print("=" * w)
    print("GATE 1A -- design variant A (no lag) vs B (delivery lag)")
    print("bundle_aware = the strongest hand-written heuristic; lower is better for RL")
    print("=" * w)
    print(f"{'cells x steps':<16}{'n':>5}{'A: no lag':>14}{'B: lag':>12}"
          f"{'A mean gap':>13}{'B mean gap':>13}")
    print("-" * w)
    out = []
    for s in sizes:
        n = s.pop("n")
        row = {"size": f"{s['cells']}x{s['timesteps']}", "n": n}
        for label, lag in (("A", False), ("B", True)):
            CFG.update(s); CFG["lag"] = lag
            r = evaluate(n_instances=n, quiet=True)
            ba = next(x for x in r["rows"] if x["policy"] == "bundle_aware")
            row[label] = ba["optimal_pct"]; row[label + "_gap"] = ba["mean_gap_pct"]
        print(f"{row['size']:<16}{n:>5}{row['A']:>13.1f}%{row['B']:>11.1f}%"
              f"{row['A_gap']:>12.1f}%{row['B_gap']:>12.1f}%")
        out.append(row)
    print("-" * w)
    bw = min(r["B"] for r in out)
    prescribed = next(r for r in out if r["size"] == "3x3")
    print(f"At the size EXPANSION_PLAN 1.2 prescribes (3x3): "
          f"A {prescribed['A']:.1f}% -> B {prescribed['B']:.1f}% optimal")
    print(f"Worst case for the heuristic under B: {bw:.1f}% optimal")
    gate = ("STOP -- still greedy-solvable" if bw > 95 else
            "WORKABLE -- headroom exists" if bw >= 70 else "IDEAL -- proceed")
    print(f"VERDICT on variant B: {gate}")
    print("=" * w)
    (OUT.parent / "gate1a_variants.json").write_text(json.dumps(
        {"_note": "Gate 1A: design variant comparison. Fictional instances.",
         "variant_A": "complementarity + contention + time-dependence",
         "variant_B": "variant A plus per-cell delivery lag (transit time)",
         "rows": out, "verdict_variant_B": gate}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    import sys
    if "--compare" in sys.argv:
        raise SystemExit(compare())
    if "--sweep" in sys.argv:
        raise SystemExit(sweep())
    if "--lag" in sys.argv:
        CFG["lag"] = True
    for i, a in enumerate(sys.argv):
        if a == "--size":                      # e.g. --size 4x6
            c, s = sys.argv[i + 1].split("x")
            CFG["cells"], CFG["timesteps"] = int(c), int(s)
            CFG["stock_scale"] = 2 if int(s) >= 5 else 1
        if a == "--n":
            globals()["N_INSTANCES"] = int(sys.argv[i + 1])
    evaluate(n_instances=N_INSTANCES)
    raise SystemExit(0)
