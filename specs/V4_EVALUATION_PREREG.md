# V4_EVALUATION_PREREG — Phase 27: pre-registered evaluation and decision D-27

Written by Opus on 2026-10-15, **before any Phase 27 run**. Frozen: `tests/test_p27_eval.py` pins this
file's SHA-256. Any change after the first run must be a dated amendment at the end, which reports the
change and why, and every affected endpoint is then labelled "amended" in the results.
Lane S (Claude Sonnet) runs; Opus decides D-27. Branch `m27-eval`. Outputs `data/eval_results/phase27/`.
Confidential until P0 is filed.

## 1. Questions
- **Q1 (effect, primary).** Does the certified gate reduce failed trips (stranded + unsafe + overflow)
  against the decision-time mask, at a small loss of people delivered?
- **Q2 (coupling).** Does the joint within-future indicator classify candidates better than marginal
  rules (product of marginals; separate checks)?
- **Q3 (keyed CRN).** Do common keyed futures cut the variance of paired comparisons by ≥ 2×?
- **Q4 (safety).** Is the certified false-accept rate ≤ δ?
- **Q5 (hardware, secondary).** Latency and energy on the laptop and on a Raspberry Pi (27C).

## 2. Worlds, seeds, replication
Primary regimes: `v4-medium-dt2-v1`, `v4-high-dt2-v1`. Secondary stress regime: `v4-stress-dt2-v1`
(registered in Phase 27 step 1: base `v3-high-v1`, `walk_in_rate = 2.0`, everything else as
`v4-high-dt2-v1`) — reported, never used for pass bars.
Seeds: generator seeds **1_050_000 – 1_050_059** (60 per regime, unused by any earlier phase),
replication 0. Every system sees the same (regime, seed) worlds.
**Budget rule (fixed now, depends on runtime only):** step 27.2 times 2 seeds per system. If the
projected wall time of §4 on 16 worker processes exceeds 48 h, use seeds 1_050_000 – 1_050_029 only
(30 per regime) for every system. No other reduction is allowed.

## 3. Systems
| ID | Definition |
|---|---|
| A | Risk-Greedy + `V3_SAFETY_V1` decision-time mask (today's decision layer) |
| A2 | Lookahead-2 (`LookaheadK2Planner`) + `V3_SAFETY_V1` — NSU reference |
| HOLD | Always WAIT — NSU lower anchor |
| B | `src/certify/baselines.py` industry/academic combination: (i) disable edges whose current hazard ≥ 0.70 ("safe-until" deterministic), (ii) drop shelters with `occupancy + reserved + people > capacity` now, (iii) independent Monte Carlo per candidate: 128 futures from a per-candidate root (`root_key(... params_id="baseline-b-v1:" + action_key)`), accept if mean joint success ≥ 0.95 (no bound, no CRN); pick the accepted candidate with the highest mean utility, else WAIT |
| P | Certified gate: `CertifiedPlanner` over `v4-cert-eval-v1` + Phase 26 re-certification |
| P-noFC | P, but UNDECIDED candidates with point estimate ≥ 0.95 are allowed (no fail-closed) |
| P-noHyst | P with `eps_keep = eps_dispatch` and `cooldown_steps = 0` |

`v4-cert-eval-v1` = `v4-cert-v1` with `max_looks = 3` (256 / 512 / 1024) and `deadline_ms = inf`
(deterministic: no wall-clock deadline in evaluation). Episodes run without a human (operator AUTO).
P-noCRN and P-marginal are decision-level ablations (§5), not episode systems.

## 4. Episode runs (Q1)
`scripts/phase27_run.py --system <ID> --regime <id> --seeds <a>-<b> --workers N` → one JSONL line per
episode: seed, regime, system, dispatched groups, stranded / unsafe / overflow groups and people,
people safely arrived, initial population, decisions, futures per decision (P*), wall time.
**Primary endpoint E1:** group failure rate = (stranded + unsafe + overflow groups) / dispatched groups,
per episode. Paired difference P − A per (regime, seed); 95 % paired-bootstrap CI (10,000 resamples,
seed 27_001), regimes pooled, stratified by regime.
**Guard E2:** delivered-people ratio R = mean(safe arrivals P) / mean(safe arrivals A2), pooled.
NSU is also reported with lower = HOLD, upper = A2 (same paired worlds).
**Bar 1 (Q1) PASS** iff the E1 CI upper bound < 0 **and** R ≥ 0.95.
Secondary (reported, no bar): relative reduction (target ≥ 50 %), P vs B on E1 (same test), per-outcome
rates, CVaR10 of safe arrivals, live-vs-rollout arrival agreement for executed dispatches,
`v4-stress-dt2-v1` results, P-noFC and P-noHyst E1 and reroute oscillations per group-hour.

## 5. Decision-level study (Q2, Q3, Q4)
Sample: from the P episodes of §4 take every 5th decision state (in seed, timestep order), at most 400
states; stored as `CertificateInputs` (Phase 25) so each state is replayable.
**Oracle:** per state and candidate, joint success frequency over futures k = 100_001 … 104_096 (4,096,
disjoint from those used by P); `p*`. Candidates with `|p* − 0.95| < 0.007` are "borderline" and excluded
from Q2/Q4 error counts (oracle noise); their count is reported.
- **Q2.** On the first 1,024 futures of each state compute: joint verdict (certifier, `v4-cert-eval-v1`);
  product-of-marginals verdict (CP bound applied to p_path·p_shelter·p_capacity via disjoint k-blocks as in
  the G23 amendment, with n = 256 per block — reported as "P-marginal"); separate-checks verdict (each
  marginal's own CP lower bound ≥ 0.95). Error = false block (not FEASIBLE but p* ≥ 0.95) or false accept
  (FEASIBLE but p* < 0.95). **Bar 2 PASS** iff the joint rule has fewer total errors than **each** marginal
  rule with a two-sided exact McNemar p < 0.05 on candidate-level paired errors. Secondary: false-block
  reduction vs product of marginals (target ≥ 30 %).
- **Q3.** Top-2 candidates by p* per state: paired utility difference estimated with CRN (same k) vs
  independent futures (`candidate_key_for_no_crn` offsets), n = 256, 200 repeats of k-offsets per state
  on 50 states. **Bar 3 PASS** iff median over states of Var_indep / Var_CRN ≥ 2.0. Secondary: futures to
  decide all candidates with and without CRN.
- **Q4.** Per state, a false accept is any FEASIBLE candidate with p* < 0.95 − 0.007. **Bar 4 PASS** iff
  the share of states with ≥ 1 false accept is ≤ δ = 0.01 (point estimate); its 95 % CP upper bound is
  reported.
Also logged per candidate: p_path, p_shelter, p_capacity (n = 256 blocks) so the G23 question can be
re-scored.

## 6. Hardware (Q5, 27C, secondary)
`scripts/phase27_latency.py`: certify-only and end-to-end latency at n = 256 on 20 sampled states, laptop
and Raspberry Pi 4/5 (once Phase 28 hardware exists), plus energy if a USB power meter is available.
Targets p95 ≤ 100 ms certify-only, ≤ 10 s end-to-end. **No bar for the lead claim**; a miss removes the
latency effect from the patent specification text. An optional fast path (vectorised / Philox) is
allowed only with a test proving bit-identity to the sha256 path on 64 futures.

## 7. Stopping and integrity rules
No peeking at E1–E4 before all runs finish (the run script writes only raw JSONL; analysis is one
script, `scripts/phase27_analyze.py`, run once). Crashed episodes are rerun with the same seed; an episode
that fails twice is reported as missing and counted as a failure for that system. No seed, metric,
threshold or system definition may change after the first run except via a dated amendment.
Results: `data/eval_results/phase27/{runs/*.jsonl, decisions.jsonl, analysis.json}`; STATUS gets raw
numbers only.

## 8. D-27 (Opus decides from `analysis.json`)
- Bars 1, 2, 4 pass → lead claim = joint certified gate (elements C + D + E); Bar 3 pass adds the keyed-CRN
  dependent with its effect; Bar 3 fail → CRN only as a non-effect dependent.
- Bar 2 fails (1 and 4 pass) → joint coupling loses its effect support: lead with fail-closed gate +
  certification-triggered atomic migration (Phase 26), coupling as a dependent embodiment.
- Bar 1 fails → no effect claim on outcomes; Opus reviews whether to file the gate at all (report §19).
- Bar 4 fails → stop: the certifier is wrong; fix before any claim.
