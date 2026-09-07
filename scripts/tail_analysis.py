"""GATE 1A.5 analysis. Reads gate1a5_tail_check.json; adds the RL latency reference.

Q3's shuffled-label null and Q4's latency comparison are mandatory per PHASE1_PLAN.md.
"""
from __future__ import annotations
import json, statistics, time, warnings
from pathlib import Path
import numpy as np
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "data/eval_results/gate1a5_tail_check.json").read_text())
rows, lat = D["rows"], D["latency_seconds_per_decision"]
POLICIES = list(rows[0]["scores"])
W = 84

opt = np.array([r["optimum"] for r in rows])
rnd = np.array([r["scores"]["random_allowed"] for r in rows])
val = {p: np.array([r["scores"][p] for r in rows]) for p in POLICIES}
denom = np.where(np.abs(opt - rnd) < 1e-9, np.nan, opt - rnd)

print("=" * W); print("GATE 1A.5 -- tail characterisation"); print("=" * W)
print(f"{D['n']} instances, {D['config']['cells']}x{D['config']['timesteps']}, lag on\n")

# ---- Q1: is the ratio metric an artifact? -------------------------------------------
print("Q1  DOES THE HEADROOM SURVIVE A SANE DENOMINATOR?")
print(f"{'policy':<18}{'%opt':>7}{'ratio-gap mean':>16}{'norm score med':>16}"
      f"{'norm p10':>10}{'abs regret med':>16}")
print("-" * W)
q1 = {}
for p in POLICIES:
    reg = opt - val[p]
    ratio = reg / np.where(np.abs(opt) < 1e-9, 1.0, np.abs(opt))
    norm = (val[p] - rnd) / denom
    norm = norm[~np.isnan(norm)]
    q1[p] = {"pct_optimal": float((reg <= 1e-9).mean() * 100),
             "ratio_gap_mean_pct": float(ratio.mean() * 100),
             "norm_median": float(np.median(norm)), "norm_p10": float(np.percentile(norm, 10)),
             "abs_regret_median": float(np.median(reg)), "abs_regret_mean": float(reg.mean())}
    print(f"{p:<18}{q1[p]['pct_optimal']:>6.1f}%{q1[p]['ratio_gap_mean_pct']:>15.1f}%"
          f"{q1[p]['norm_median']:>16.3f}{q1[p]['norm_p10']:>10.3f}{q1[p]['abs_regret_median']:>16.3f}")

# ---- Q2: where does the improvement live? -------------------------------------------
reg_ba = opt - val["bundle_aware"]
srt = np.sort(reg_ba)[::-1]
top10 = srt[: max(1, len(srt) // 10)].sum() / srt.sum() * 100
top5 = srt[: max(1, len(srt) // 20)].sum() / srt.sum() * 100
head_pct = reg_ba.mean() / opt.mean() * 100
print(f"\nQ2  WHERE THE AVAILABLE IMPROVEMENT LIVES  (over bundle_aware)")
print(f"    share of total regret in the worst 10% of instances : {top10:.1f}%")
print(f"    share in the worst 5%                               : {top5:.1f}%")
print(f"    mean regret as a share of mean optimum              : {head_pct:.1f}%")

# ---- Q3: structured or arbitrary, against a shuffled null ---------------------------
feat_names = list(rows[0]["features"])
X = np.array([[r["features"][f] for f in feat_names] for r in rows])
y = (reg_ba >= np.percentile(reg_ba, 90)).astype(int)
clf = DecisionTreeClassifier(max_depth=3, random_state=0)
cv = StratifiedKFold(5, shuffle=True, random_state=0)
real_auc = float(cross_val_score(clf, X, y, cv=cv, scoring="roc_auc").mean())
rs = np.random.RandomState(0)
null = []
for _ in range(200):
    yp = rs.permutation(y)
    null.append(cross_val_score(clf, X, yp, cv=cv, scoring="roc_auc").mean())
null = np.array(null)
p_perm = float((null >= real_auc).mean())
print(f"\nQ3  IS THE TAIL STRUCTURED?  (5-fold CV AUC, top-decile regret)")
print(f"    real AUC                    : {real_auc:.3f}")
print(f"    shuffled-label null AUC     : mean {null.mean():.3f}, 95th pct {np.percentile(null,95):.3f}")
print(f"    permutation p               : {p_perm:.3f}")
structured = p_perm < 0.05 and real_auc > np.percentile(null, 95)
print(f"    -> {'STRUCTURED (separated from null)' if structured else 'NOT SEPARATED FROM NULL -- no learnable structure shown'}")

# ---- Q4: planner score AND latency --------------------------------------------------
print(f"\nQ4  CAN A CHEAP PLANNER CLOSE IT, AND AT WHAT LATENCY?")
try:
    from sb3_contrib import MaskablePPO
    import numpy as _np
    m = MaskablePPO.load(str(ROOT / "models/maskable_ppo_shelter.zip"), device="cpu")
    obs = _np.zeros(m.observation_space.shape, dtype=_np.float32)
    mask = _np.ones(m.action_space.n, dtype=bool)
    for _ in range(20):
        m.predict(obs, action_masks=mask, deterministic=True)
    t0 = time.perf_counter()
    for _ in range(300):
        m.predict(obs, action_masks=mask, deterministic=True)
    rl_lat = (time.perf_counter() - t0) / 300
    print(f"    reference: v1 MaskablePPO.predict() = {rl_lat*1e3:.3f} ms/decision (measured)")
except Exception as e:                                    # noqa: BLE001
    rl_lat = None
    print(f"    reference unavailable: {e}")

print(f"\n{'policy':<18}{'norm score med':>16}{'%opt':>8}{'ms/decision':>14}{'x vs policy':>14}")
print("-" * W)
q4 = {}
for p in POLICIES:
    ms = lat[p] * 1e3
    mult = (lat[p] / rl_lat) if rl_lat else float("nan")
    q4[p] = {"norm_median": q1[p]["norm_median"], "ms_per_decision": ms, "x_vs_policy": mult}
    print(f"{p:<18}{q1[p]['norm_median']:>16.3f}{q1[p]['pct_optimal']:>7.1f}%{ms:>14.3f}{mult:>13.0f}x")

best = max((p for p in POLICIES if p != "random_allowed"), key=lambda p: q1[p]["norm_median"])
bn, bx = q1[best]["norm_median"], q4[best]["x_vs_policy"]
print(f"\nstrongest planner: {best}  norm score {bn:.3f}  at {bx:.0f}x policy latency")

if bn >= 0.95 and bx <= 10:
    verdict = "STOP -- do not build. Solvable without learning at comparable latency; ship the planner."
elif bn >= 0.95:
    verdict = (f"JUDGEMENT -- solvable ({bn:.3f}) but at {bx:.0f}x policy latency. The case for a "
               "learned policy becomes LATENCY, not quality, and must be stated as such.")
elif not structured and head_pct < 5:
    verdict = "STOP / redesign -- tail not separated from null and headroom under 5% of mean optimum."
else:
    verdict = "PROCEED -- a real gap the planner does not close; planner joins the baseline set."
print("\n" + "=" * W); print(f"VERDICT: {verdict}"); print("=" * W)

(ROOT / "data/eval_results/gate1a5_analysis.json").write_text(json.dumps({
    "_note": "Gate 1A.5 analysis. Q3 null and Q4 latency per PHASE1_PLAN.md.",
    "q1_metrics": q1,
    "q2_regret_concentration": {"top10pct_share": top10, "top5pct_share": top5,
                                "mean_regret_share_of_optimum": head_pct},
    "q3_structure": {"real_auc": real_auc, "null_mean": float(null.mean()),
                     "null_p95": float(np.percentile(null, 95)), "perm_p": p_perm,
                     "structured": bool(structured)},
    "q4_latency": q4, "rl_reference_ms": (rl_lat * 1e3) if rl_lat else None,
    "strongest_planner": best, "verdict": verdict,
}, indent=2) + "\n")
