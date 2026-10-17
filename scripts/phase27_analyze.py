"""Phase 27 analysis (V4_EVALUATION_PREREG.md). Run ONCE after all runs finish; writes analysis.json.

    python scripts/phase27_analyze.py

Raw numbers and bar flags only. D-27 is Lead's decision.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation_v4.stats import (  # noqa: E402
    clopper_pearson_upper,
    mcnemar_exact,
    paired_bootstrap_ci,
    stratified_bootstrap_ci,
)

OUT = ROOT / "data/eval_results/phase27"
PRIMARY = ("v4-medium-dt2-v1", "v4-high-dt2-v1")
STRESS = "v4-stress-dt2-v1"
BOOT, BOOT_SEED = 10_000, 27_001
DELTA = 0.01
BAND = 0.007


def load_runs() -> dict[tuple[str, str], dict[int, dict]]:
    runs: dict[tuple[str, str], dict[int, dict]] = {}
    for path in sorted((OUT / "runs").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                runs.setdefault((row["system"], row["regime"]), {})[row["seed"]] = row
    return runs


def failure_rate(row: dict) -> float:
    if row.get("status") != "OK":
        return 1.0  # a missing episode counts as a failure for that system (prereg 7)
    n = row["dispatched_groups"]
    return 0.0 if n == 0 else (row["stranded_groups"] + row["unsafe_groups"] + row["overflow_groups"]) / n


def arrivals(row: dict) -> float:
    return float(row["people_safely_arrived"]) if row.get("status") == "OK" else 0.0


def cvar(values: list[float], q: float = 0.10) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = max(1, int(round(q * len(ordered))))
    return statistics.fmean(ordered[:k])


def episode_endpoints(runs) -> dict:
    systems = sorted({s for s, _ in runs})
    out = {"systems": {}, "missing": {}}
    for system in systems:
        for regime in (*PRIMARY, STRESS):
            rows = runs.get((system, regime), {})
            if not rows:
                continue
            ok = [r for r in rows.values() if r.get("status") == "OK"]
            groups = sum(r["dispatched_groups"] for r in ok)
            hours = sum(r.get("group_hours", 0.0) for r in ok)
            out["systems"].setdefault(system, {})[regime] = {
                "episodes": len(rows), "missing": len(rows) - len(ok),
                "dispatched_groups": groups,
                "stranded_rate": sum(r["stranded_groups"] for r in ok) / groups if groups else None,
                "unsafe_rate": sum(r["unsafe_groups"] for r in ok) / groups if groups else None,
                "overflow_rate": sum(r["overflow_groups"] for r in ok) / groups if groups else None,
                "mean_group_failure_rate": statistics.fmean(failure_rate(r) for r in rows.values()),
                "mean_safe_arrivals": statistics.fmean(arrivals(r) for r in rows.values()),
                "cvar10_safe_arrivals": cvar([arrivals(r) for r in rows.values()]),
                "migrations": sum(r.get("migrations", 0) for r in ok),
                "migrations_per_group_hour": (sum(r.get("migrations", 0) for r in ok) / hours) if hours else None,
                "median_arrival_abs_error_steps": (
                    statistics.median([r["arrival_abs_error_median"] for r in ok
                                       if r.get("arrival_abs_error_median") is not None] or [float("nan")])),
                "mean_wall_seconds": statistics.fmean(r["wall_seconds"] for r in rows.values()),
            }
    return out


def paired(runs, a: str, b: str, regimes) -> dict[str, list[float]]:
    """Per-regime lists of (failure_rate(a) - failure_rate(b)) over shared seeds."""
    diffs = {}
    for regime in regimes:
        ra, rb = runs.get((a, regime), {}), runs.get((b, regime), {})
        diffs[regime] = [failure_rate(ra[s]) - failure_rate(rb[s]) for s in sorted(set(ra) & set(rb))]
    return {k: v for k, v in diffs.items() if v}


def e1(runs, a: str, b: str, regimes=PRIMARY) -> dict:
    diffs = paired(runs, a, b, regimes)
    if not diffs:
        return {"available": False}
    flat = [x for v in diffs.values() for x in v]
    lo, hi = stratified_bootstrap_ci(diffs, resamples=BOOT, seed=BOOT_SEED)
    mean_b = statistics.fmean(failure_rate(r) for regime in diffs for r in runs[(b, regime)].values())
    return {"available": True, "n_pairs": len(flat), "mean_diff": statistics.fmean(flat), "ci95": [lo, hi],
            "mean_rate_baseline": mean_b,
            "relative_reduction": (-statistics.fmean(flat) / mean_b) if mean_b else None}


def decision_level() -> dict:
    path = OUT / "decisions.jsonl"
    if not path.exists():
        return {"available": False}
    states, cands, q3 = {}, [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        {"state": lambda r: states.__setitem__(r["state_id"], r),
         "candidate": cands.append, "q3": q3.append}[row["type"]](row)
    graded = [c for c in cands if not c["borderline"]]

    def wrong(c, feasible: bool) -> bool:
        return (not feasible and c["p_star"] >= 0.95) or (feasible and c["p_star"] < 0.95)

    rules = {
        "joint": lambda c: c["joint_verdict"] == "FEASIBLE",
        "product_of_marginals": lambda c: c["product_feasible"],
        "separate_checks": lambda c: c["separate_feasible"],
    }
    errors = {name: [wrong(c, f(c)) for c in graded] for name, f in rules.items()}
    q2 = {"candidates": len(cands), "graded": len(graded), "borderline_excluded": len(cands) - len(graded),
          "total_errors": {k: sum(v) for k, v in errors.items()},
          "false_blocks": {k: sum(1 for c, w in zip(graded, v) if w and c["p_star"] >= 0.95)
                           for k, v in errors.items()},
          "false_accepts": {k: sum(1 for c, w in zip(graded, v) if w and c["p_star"] < 0.95)
                            for k, v in errors.items()}}
    mc = {}
    for other in ("product_of_marginals", "separate_checks"):
        b = sum(1 for j, o in zip(errors["joint"], errors[other]) if not j and o)  # joint right, other wrong
        c_ = sum(1 for j, o in zip(errors["joint"], errors[other]) if j and not o)
        mc[other] = {"joint_only_right": b, "other_only_right": c_, "p": mcnemar_exact(b, c_)}
    q2["mcnemar"] = mc
    fb_j, fb_p = q2["false_blocks"]["joint"], q2["false_blocks"]["product_of_marginals"]
    q2["false_block_reduction_vs_product"] = (1 - fb_j / fb_p) if fb_p else None
    bar2 = all(q2["total_errors"]["joint"] < q2["total_errors"][o] and mc[o]["p"] < 0.05 for o in mc)
    first = sorted(q3, key=lambda r: r["state_id"])[:50]
    ratios = [r["var_indep"] / r["var_crn"] for r in first if r["var_crn"] > 0]
    q3_out = {"states": len(first), "median_var_ratio": statistics.median(ratios) if ratios else None,
              "futures_to_decide_with_and_without_crn": "not computed (secondary)"}
    bar3 = bool(ratios) and statistics.median(ratios) >= 2.0
    by_state: dict[int, bool] = {}
    for c in cands:
        fa = c["joint_verdict"] == "FEASIBLE" and c["p_star"] < 0.95 - BAND
        by_state[c["state_id"]] = by_state.get(c["state_id"], False) or fa
    n_states, n_fa = len(by_state), sum(by_state.values())
    q4 = {"states": n_states, "states_with_false_accept": n_fa,
          "share": n_fa / n_states if n_states else None,
          "cp95_upper": clopper_pearson_upper(n_fa, n_states) if n_states else None}
    bar4 = n_states > 0 and n_fa / n_states <= DELTA
    return {"available": True, "q2": q2, "q3": q3_out, "q4": q4,
            "bars": {"bar2": {"pass": bar2}, "bar3": {"pass": bar3}, "bar4": {"pass": bar4}}}


def main() -> int:
    runs = load_runs()
    budget = json.loads((OUT / "budget.json").read_text(encoding="utf-8")) if (OUT / "budget.json").exists() else None
    episodes = episode_endpoints(runs)
    primary = e1(runs, "P", "A")
    p_arr = [arrivals(r) for regime in PRIMARY for r in runs.get(("P", regime), {}).values()]
    a2_arr = [arrivals(r) for regime in PRIMARY for r in runs.get(("A2", regime), {}).values()]
    ratio = (statistics.fmean(p_arr) / statistics.fmean(a2_arr)) if p_arr and a2_arr and statistics.fmean(a2_arr) else None
    hold_arr = [arrivals(r) for regime in PRIMARY for r in runs.get(("HOLD", regime), {}).values()]
    nsu = None
    if p_arr and a2_arr and hold_arr:
        lower, upper = statistics.fmean(hold_arr), statistics.fmean(a2_arr)
        nsu = {"lower_HOLD": lower, "upper_A2": upper, "P": statistics.fmean(p_arr)}
    bar1 = bool(primary.get("available") and primary["ci95"][1] < 0 and ratio is not None and ratio >= 0.95)
    decisions = decision_level()
    bars = {"bar1": {"pass": bar1, "numbers": {"E1": primary, "R_P_over_A2": ratio}}}
    for k, v in decisions.get("bars", {}).items():
        bars[k] = {**v, "numbers": decisions.get({"bar2": "q2", "bar3": "q3", "bar4": "q4"}[k])}
    latency = OUT / "latency.json"
    analysis = {
        "budget": budget, "episodes": episodes, "E1_P_vs_A": primary, "E2_ratio_P_over_A2": ratio, "NSU": nsu,
        "secondary": {
            "P_vs_B": e1(runs, "P", "B"), "P_noFC_vs_A": e1(runs, "P-noFC", "A"),
            "P_noHyst_vs_A": e1(runs, "P-noHyst", "A"), "P_vs_A_stress": e1(runs, "P", "A", (STRESS,)),
            "P_vs_A_per_regime": {r: e1(runs, "P", "A", (r,)) for r in PRIMARY},
        },
        "decision_level": decisions, "bars": bars,
        "latency_q5": json.loads(latency.read_text(encoding="utf-8")) if latency.exists() else None,
    }
    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v["pass"] for k, v in bars.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
