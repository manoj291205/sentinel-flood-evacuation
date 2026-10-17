# V4_D27_DECISION — Phase 27 decision (Lead, 2026-10-17)

Source: `data/eval_results/phase27/analysis.json` (merged from `m27-eval` @ 1998eb6), read against
`specs/V4_EVALUATION_PREREG.md` §8 with thresholds unchanged. Confidential until P0 is filed.

## Audit of the inputs
- 7 systems × 3 regimes × 60 seeds (1_050_000 – 1_050_059; full range, the §2 budget projection was 30.6 h < 48 h)
  = 1,260 episodes, every one `status = OK`, 60 unique seeds per (system, regime). `P_v4-high` (71 lines) and
  `P-noFC_v4-high` (84 lines) contain duplicate lines from an interrupted-and-resumed run; every duplicate is
  identical to its first copy except `wall_seconds`, and the analysis keys rows by seed, so they do not count twice.
- Baseline B stress seeds 1_050_040 – 1_050_059 were also run on a second laptop (`m27-runs-remote`, not merged): all
  20 rows equal the merged file except `wall_seconds` — an independent reproduction.
- `scripts/phase27_analyze.py` re-run by Lead on the branch tree: `analysis.json` byte-identical. E1 mean and R
  recomputed independently from the run files: identical.
- No prereg amendment; no seed, metric, threshold or system changed.

## Bars (prereg §4–§5)
| Bar | Test | Result | Pass |
|---|---|---|---|
| 1 (Q1) | E1 CI upper < 0 **and** R ≥ 0.95 | E1 = −0.2296, 95 % CI [−0.2640, −0.1965] (120 pairs; A rate 0.2369, P rate 0.0073); **R = 0.2139** | **no** (guard R) |
| 2 (Q2) | joint fewer errors than each marginal rule, McNemar p < 0.05 | errors joint 179 / product 243 / separate 243 (all false blocks; 0 false accepts each); 64 vs 0 discordant, p = 1.08e-19; 227 borderline excluded of 4,798 | yes |
| 3 (Q3) | median Var_indep / Var_CRN ≥ 2.0 | 1.071 over 50 states | no |
| 4 (Q4) | share of states with a false accept ≤ 0.01 | 0 / 400 (CP 95 % upper 0.0075) | yes |

Mean per episode (primary regimes, 120 episodes each): dispatched groups A 16.6, A2 16.6, B 8.2, **P 3.3**, P-noFC 6.6;
people safely arrived A 228.1, A2 223.8, B 132.9, **P 47.9**, P-noFC 104.4 (initial population 312.1). P-noHyst is identical
to P in all 180 episodes: P migrated only twice in total, so hysteresis never binds in these regimes (the ablation is
uninformative here, not evidence either way). Q5 latency (laptop, n = 256): certify-only p95 1,059 ms (target 100 ms),
end-to-end p95 13.9 s (target 10 s) — both missed; no bar.

## D-27
1. **Bar 1 fails → no effect claim on outcomes** (prereg §8). The certified gate cuts the group failure rate from 23.7 % to
   0.7 %, but it does so by dispatching about a fifth as many groups and delivers 21 % of the people A2 delivers (guard
   ≥ 95 %). The specification must not claim better evacuation outcomes, fewer failed trips at equal throughput, or
   any outcome effect from these runs. The failure-rate numbers may be reported only together with R.
2. **Bars 2 and 4 pass → decision-level support stands.** The joint within-future indicator makes fewer classification
   errors than the product of marginals and than separate checks (179 vs 243, all false blocks, p ≈ 1e-19; −26 % false blocks,
   secondary target 30 % missed), with zero false accepts by any rule; the certified false-accept share is 0/400 (≤ δ).
   These are the technical effects the gate can be described with: a fail-closed, statistically certified dispatch decision
   whose joint coupling rejects fewer feasible dispatches than marginal rules at no observed safety cost.
3. **Bar 3 fails → keyed CRN only as a non-effect dependent** (no variance-reduction effect stated).
4. **Whether to file the gate at all** is the review prereg §8 requires on a Bar 1 failure. Lead's input: the decision-level
   results (Bars 2, 4) are real and pre-registered, but the system-level result shows the gate, as configured
   (`v4-cert-eval-v1`, δ = 0.05 dispatch), is too conservative to be useful for throughput. **This is the user's decision**
   (with the patent agent), taken before 29a; it is recorded as open in `STATUS.md`. Nothing in this file changes the
   prereg or authorises a rerun with other parameters — any new evaluation needs a new pre-registration.
5. Escrow embodiment (Phase 35): not recommended by this result.
