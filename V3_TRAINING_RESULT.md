# Sentinel-Agent V3 — Phase 9 MaskablePPO Training Result

> **Status: PHASE 9 COMPLETE; `POTENTIAL_SLOT_SHORTCUT` TRIGGERED.**
>
> Training/validation results do not establish PPO superiority. Final comparison occurs
> only on the frozen Phase 10 held-out suite.

## 1. Registered experiment executed

Stage 9A commit `5b13c59` froze `v3-ppo-training-spec-v1` before any gradient update.
Stage 9B then ran exactly that contract: sb3-contrib MaskablePPO, `MlpPolicy`, two
256-unit ReLU layers, four synchronous environments, CPU, and the primary
`v3-reward-balanced-v1` reward under `v3-safety-v1` hard masks.

```text
learning rate:       3e-4
n_steps:             1,250 per environment
rollout:             5,000 transitions
batch size:          250
epochs:              10
gamma:               0.99
GAE lambda:          0.95
clip range:          0.2
entropy coefficient: 0.01
VF coefficient:      0.5
maximum grad norm:   0.5
timesteps per seed:  250,000 exact
checkpoint/eval:     every 10,000 exact
training seeds:      1101, 2202, 3303, 4404, 5505
```

Training used the broad `v3-ppo-train-generator-v1` distribution. Checkpoint selection
used only deterministic masked mean undiscounted balanced reward on the committed 150
scenario `v3-ppo-validation-v1` suite, with the frozen exposure/safe/earlier tie-breaks.
No early stopping, seed replacement, planner comparison, exact oracle, demo scenario, or
Phase 10 data was used.

## 2. Debug gate and reproducibility

The required seed-1101 debug ran 20,000 timesteps and was labeled `NOT A PRIMARY RESULT`.
It produced 1,548 completed training episodes, nonconstant episode returns from
`-0.188565` to `0.528711`, finite optimizer/logger values, and zero invalid actions.
The saved model reloaded successfully and deterministic masked inference reproduced an
episode exactly.

The same 20,000-step debug was repeated with identical seed, software, CPU thread count,
deterministic PyTorch setting, generator streams, and validation suite. Every recorded
validation metric at 10k and 20k matched exactly (`maximum absolute difference = 0.0`).
The ZIP bytes differed, so exact model-byte reproducibility is not claimed.

At the best debug checkpoint (10k), validation return was `0.263455`, safe-population
fraction `0.687386`, cumulative normalized exposure `0.249794`, completion `0.100000`,
and invalid actions `0`. Save/load and deterministic inference both passed.

## 3. Five-seed best-validation results

| Seed | Best timestep | Validation return | Safe pop. | Exposure | Completion | Invalid actions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1101 | 240,000 | 0.282728 | 0.708929 | 0.231826 | 0.133333 | 0 |
| 2202 | 200,000 | 0.282436 | 0.711290 | 0.238310 | 0.140000 | 0 |
| 3303 | 220,000 | 0.278508 | 0.703620 | 0.234598 | 0.113333 | 0 |
| 4404 | 200,000 | 0.279870 | 0.705327 | 0.234300 | 0.080000 | 0 |
| 5505 | 190,000 | 0.273840 | 0.697315 | 0.236535 | 0.120000 | 0 |

Across all five best checkpoints:

| Metric | Mean | Std. dev. | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: |
| validation return | 0.279477 | 0.003231 | 0.273840 | 0.282728 |
| safe-population fraction | 0.705296 | 0.004809 | 0.697315 | 0.711290 |
| cumulative normalized exposure | 0.235114 | 0.002190 | 0.231826 | 0.238310 |
| completion fraction | 0.117333 | 0.020913 | 0.080000 | 0.140000 |

The frozen representative rule selects seed **4404**, whose validation return is the
five-seed median. Phase 10 must evaluate all five best-validation checkpoints rather than
using only this representative model.

The cross-seed mean validation return increased from `0.240915 ± 0.024165` at 10k to
`0.274342 ± 0.003118` at the final 250k checkpoints. Mean safe-population fraction moved
from `0.654639` to `0.697769`, while mean cumulative normalized exposure moved from
`0.255152` to `0.235755`. These are learning/validation diagnostics, not superiority
claims.

## 4. Mask and action-space diagnostics

MaskablePPO produced zero invalid-action attempts in all five primary training streams
and all 18,750 best-checkpoint validation episodes used for checkpoint selection across
seeds/checkpoints. Best-checkpoint validation mean allowed-action counts ranged from
`14.779` to `15.162`; minimum allowed count was one. Mean WAIT-only timesteps per episode
ranged from `1.533` to `1.627`, reflecting legitimate late-episode/closure states rather
than episodes beginning with degenerate masks.

## 5. Compute

All runs used Python `3.11.3`, PyTorch `2.13.0`, Gymnasium `1.3.0`,
Stable-Baselines3 `2.9.0`, and sb3-contrib `2.9.0` on arm64 macOS with deterministic
PyTorch algorithms, four Torch threads, and CPU. MPS was unavailable. Approximate peak
memory was not measured.

| Seed | Process wall time (s) | Timesteps/s |
| --- | ---: | ---: |
| 1101 | 732.3 | 341.4 |
| 2202 | 841.9 | 296.9 |
| 3303 | 844.2 | 296.1 |
| 4404 | 806.4 | 310.0 |
| 5505 | 809.2 | 309.0 |

Summed process wall time was 4,034 seconds (67.2 minutes). Seeds 2202/3303 and 4404/5505
ran as concurrent CPU pairs, so process times include shared-machine contention.

## 6. Semantic-slot permutation diagnostic

Every best checkpoint was evaluated on 30 base validation scenarios and five independent
consistent ID permutations per base: 150 paired variants per seed, 750 total. The paired
diagnostic uses the pre-registered deterministic transform so semantic IDs are the only
changed input. Physical zone/shelter properties, routes, trends, and action remapping were
verified by tests.

| Seed | Action equivalence | Median abs. normalized return delta | Mean abs. safe-pop. delta | Alarm |
| --- | ---: | ---: | ---: | --- |
| 1101 | 0.094892 | 0.051949 | 0.095464 | triggered |
| 2202 | 0.107499 | 0.058468 | 0.092528 | triggered |
| 3303 | 0.100479 | 0.055322 | 0.091750 | triggered |
| 4404 | 0.090528 | 0.053019 | 0.097585 | triggered |
| 5505 | 0.104641 | 0.062134 | 0.107311 | triggered |

Across all 750 pairs:

```text
mean action-equivalence rate:                 0.099608
mean signed return delta:                    -0.009079
median absolute normalized return delta:      0.057137
mean absolute safe-population delta:           0.096927
mean signed exposure delta:                    0.000938
```

The frozen alarm triggers when median absolute normalized return delta exceeds `0.05` or
mean absolute safe-population delta exceeds `0.05`. Both thresholds were exceeded, and
all five seed-level diagnostics also exceeded at least one threshold. The correct result
is therefore:

> **`POTENTIAL_SLOT_SHORTCUT`**

No generator, architecture, reward, hyperparameter, seed, or model was changed after
observing this result, and no post-hoc retraining was performed.

### V1 failure-mode comparison

V1 selected S6/S7 `0/0` times in 60 scenarios while the comparison selected them `7/8`;
those slots had been permanently masked by fixed training statuses. V3 removed that
specific generator defect: opaque-ID tests show the same physical positions reach every
available zone and shelter slot, and no physical quality is permanently tied to S6/S7.

However, the V3 paired diagnostic shows that randomization alone did not make the flat
MLP policy permutation invariant. Changing only semantic IDs materially changed both
actions and episode outcomes. V3 therefore avoids the exact V1 data-construction bug but
still exhibits a broader positional sensitivity that must be carried into Phase 10 and
future architecture work.

## 7. Artifacts

- `data/eval_v3/training/training_summary.json`: five-seed and compute summary;
- `seed_<seed>.json` plus `seed_<seed>_episodes.csv`: every validation checkpoint and
  per-episode training diagnostics;
- `learning_curves.csv` and `learning_curves.svg`: all seeds plus mean/std curves;
- `permutation_diagnostic.json`: all 750 paired results and slot counts;
- `debug_seed1101.json` and repeat artifacts: debug/reproducibility evidence;
- `models/v3/ppo_seed<seed>_best.zip`: five best-validation policies;
- `models/v3/ppo_seed<seed>_final.zip`: five final-timestep policies;
- adjacent metadata JSON: spec, Git base, software, seed, dimensions, validation score,
  checkpoint, device, and compute fields.

Every 10k checkpoint was serialized temporarily before evaluation. The best was promoted;
non-best intermediate ZIPs were discarded after their metrics were durably recorded, so
the repository retains the required five best and five final archives without 125
redundant model copies.

## 8. Known limitations and deferred work

- Validation is for checkpoint selection, not final comparison; no Phase 10 result was
  generated or inspected.
- The slot-leakage alarm triggered materially. Phase 10 must report it with all five
  seeds; a future pre-results experiment may consider an inherently permutation-aware
  architecture, but Phase 9 did not adapt post hoc.
- The feed-forward PPO observation omits exact pending-arrival schedules. Strong existing
  practical planners may access them, making their comparison conservative against PPO
  and not perfectly information matched.
- Phase 10 must include the frozen **OBSERVATION-MATCHED PLANNER DIAGNOSTIC** in addition
  to the stronger existing practical planner.
- Exact debug validation metrics reproduced, but exact ZIP bytes did not; neural
  model-byte reproducibility is not claimed.
- Scenarios, rewards, and uncertainty are synthetic modeling constructs, not evidence of
  real-world evacuation effectiveness.

## 9. Acceptance

- [x] Stage 9A spec, generator, five seeds, manifest, architecture, budget, cadence,
  checkpoint rule, slot strategy, alarms, and information asymmetry frozen and committed
  before gradients.
- [x] 20k debug plus same-seed reproducibility run finite; masks, save/load, and
  deterministic inference verified.
- [x] All five primary seeds trained for exactly 250k under one unchanged contract.
- [x] Five best and five final policies plus model metadata stored separately.
- [x] All validation and per-episode structured logs stored; no test/demo/oracle used.
- [x] Zero invalid masked actions and finite numerical logs.
- [x] All seeds, including the weakest, reported.
- [x] 30×5 permutation diagnostic run on all five best checkpoints; alarm disclosed.
- [x] Individual and aggregate learning curves generated.
- [x] Reward, uncertainty, safety, observation, prior artifacts, and scientific thresholds
  unchanged.
- [x] Phase 10 planner/PPO comparison not started.

The Phase 9B commit is the Git commit named
`V3 Phase 9B: train pre-registered MaskablePPO policies`.
