"""Retrieval Q2 -- do the 7 verdict flips concentrate on shelters near a decision boundary?

The marginality construct and both tests are PRE-REGISTERED in PHASE1_PLAN.md 4, committed
at 213cb3b BEFORE this script was written. Nothing here may deviate from that definition.

Offline: reads the existing constraint_agreement cache. No API calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scipy.stats import fisher_exact, mannwhitneyu   # noqa: E402
from src.constraints.generate import shelter_facts    # noqa: E402
from src.eval.baselines import is_unsafe              # noqa: E402

MARGINAL_CUTOFF = 0.15      # pre-registered


def margin(fact: dict, population: int) -> float:
    """Pre-registered: min normalised distance to any boundary of the safety rule.

    A non-operational shelter is unambiguous -- there is no nearly-open -- so it is
    assigned the maximal (least marginal) value.
    """
    if fact["status"] != "operational":
        return 1.0
    p = max(population, 1)
    d_sev = abs(fact["flood_severity"] - 0.70) / 0.70
    d_cap0 = abs(fact["capacity_headroom"] - 1) / p
    d_capP = abs(fact["capacity_headroom"] - p) / p
    return min(d_sev, d_cap0, d_capP)


def main() -> int:
    cache = json.loads((ROOT / "data/eval_results/constraint_agreement_cache.json").read_text(encoding="utf-8"))
    suite = json.loads((ROOT / "data/eval_scenarios.json").read_text(encoding="utf-8"))
    scen = {s["scenario_id"]: s for s in suite["scenarios"]}

    rows = []
    for sid, entry in sorted(cache.items()):
        s = scen[sid]
        pop = s["source"]["population_to_evacuate"]
        facts = {f["shelter_id"]: f for f in shelter_facts(s)}
        a = {c["action_id"]: c["status"] for c in entry["with_rag"]["constraints"]}
        b = {c["action_id"]: c["status"] for c in entry["without_rag"]["constraints"]}
        for sh, fact in facts.items():
            rows.append({
                "scenario": sid, "shelter": sh,
                "margin": margin(fact, pop),
                "flipped": a.get(sh) != b.get(sh),
                "unsafe": is_unsafe(fact),
                "severity": fact["flood_severity"],
                "headroom": fact["capacity_headroom"],
                "status": fact["status"],
            })

    flipped = [r for r in rows if r["flipped"]]
    unflipped = [r for r in rows if not r["flipped"]]
    marg = lambda rs: [r["margin"] for r in rs]

    # T1 -- Fisher exact on marginal x flipped
    a = sum(1 for r in flipped if r["margin"] <= MARGINAL_CUTOFF)
    b = len(flipped) - a
    c = sum(1 for r in unflipped if r["margin"] <= MARGINAL_CUTOFF)
    d = len(unflipped) - c
    odds, p_fisher = fisher_exact([[a, b], [c, d]], alternative="greater")

    # T2 -- threshold-free Mann-Whitney (flipped expected to have SMALLER margins)
    u, p_mw = mannwhitneyu(marg(flipped), marg(unflipped), alternative="less")

    med = lambda xs: sorted(xs)[len(xs) // 2]
    w = 80
    print("=" * w)
    print("RETRIEVAL Q2 -- do flips concentrate near the decision boundary?")
    print("pre-registered in PHASE1_PLAN.md section 4, commit 213cb3b")
    print("=" * w)
    print(f"shelters: {len(rows)}   flipped: {len(flipped)}   unflipped: {len(unflipped)}")
    print()
    print(f"{'':<22}{'marginal (<=0.15)':>19}{'not marginal':>15}")
    print(f"{'flipped':<22}{a:>19}{b:>15}")
    print(f"{'unflipped':<22}{c:>19}{d:>15}")
    print()
    print(f"T1 Fisher exact (one-sided): odds ratio {odds:.2f}, p = {p_fisher:.4f}")
    print(f"T2 Mann-Whitney  (one-sided): U = {u:.1f}, p = {p_mw:.4f}")
    print(f"   median margin, flipped   : {med(marg(flipped)):.4f}")
    print(f"   median margin, unflipped : {med(marg(unflipped)):.4f}")
    print()
    supported = (p_mw < 0.05) and (odds > 1.0)
    print("PRE-REGISTERED DECISION RULE: claim only if T1 and T2 agree in direction")
    print("                              AND T2 p < 0.05")
    print(f"VERDICT: {'CLAIM SUPPORTED' if supported else 'NOT SUPPORTED -- report the 11.1% as unexplained variance'}")
    if not supported:
        print("         (7 flip events: this cannot establish absence, only fail to show presence)")
    print("=" * w)
    print("\nthe 7 flipped shelters:")
    for r in flipped:
        print(f"  {r['scenario']} {r['shelter']}  margin={r['margin']:.3f}  "
              f"sev={r['severity']:.2f}  headroom={r['headroom']}  {r['status']}")

    (ROOT / "data/eval_results/retrieval_q2_marginality.json").write_text(json.dumps({
        "_note": "Pre-registered in PHASE1_PLAN.md section 4 (commit 213cb3b) before running.",
        "cutoff": MARGINAL_CUTOFF,
        "contingency": {"flipped_marginal": a, "flipped_not": b,
                        "unflipped_marginal": c, "unflipped_not": d},
        "fisher": {"odds_ratio": odds, "p": p_fisher},
        "mannwhitney": {"U": u, "p": p_mw},
        "median_margin_flipped": med(marg(flipped)),
        "median_margin_unflipped": med(marg(unflipped)),
        "claim_supported": bool(supported),
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
