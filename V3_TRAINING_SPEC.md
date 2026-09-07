# Sentinel-Agent V3 — Frozen MaskablePPO Training Specification

> **Status: FROZEN IN PHASE 9A BEFORE ANY GRADIENT UPDATE.**
>
> Specification: `v3-ppo-training-spec-v1`
>
> This is a synthetic research experiment. Training or validation performance cannot
> establish PPO superiority; final comparison is reserved for the unseen Phase 10 suite.

## 1. Scientific firewall

Phase 9 does not change the Phase 1 metrics or thresholds, Phase 4 uncertainty
configurations, Phase 5 hard-safety rule, Phase 6 gate result, Phase 7 observation, or
Phase 8 reward. It never uses Gate 6 oracle output, planner actions, the demo scenario,
or Phase 10 data as rewards, labels, curricula, validation targets, or checkpoint rules.
The validation suite may select checkpoints and monitor learning only. It may not drive
reward, uncertainty, architecture, or test-set changes.

The baseline feed-forward PPO observation omits exact individual pending-arrival
schedules. Existing strong planners may access more detailed pending-arrival metadata.
Therefore planner-vs-PPO comparison is conservative against PPO and is not a perfect
information-matched comparison.

Phase 10 must add an **OBSERVATION-MATCHED PLANNER DIAGNOSTIC** alongside the existing
strong practical planners. It is explicitly deferred and is not a Phase 9 baseline.

## 2. Frozen primary configuration

| Field | Frozen value |
| --- | --- |
| Algorithm | `sb3_contrib.MaskablePPO` |
| Policy architecture | `MlpPolicy`, MLP `[256, 256]`, ReLU |
| `MAX_ZONES` | 6 |
| `MAX_SHELTERS` | 9 |
| Observation dimension | 384 float32 values in `[0,1]` |
| Action dimension | 55 (`WAIT=54`) |
| Reward | `v3-reward-balanced-v1`: `+0.55 safe -0.30 exposure -0.05 travel -0.10 terminal` |
| Safety | hard safety ON, `v3-safety-v1` |
| Learning rate | `3e-4` |
| `n_steps` | 1,250 per environment |
| Batch size | 250 |
| Epochs | 10 |
| Gamma | 0.99 |
| GAE lambda | 0.95 |
| Clip range | 0.2 |
| Entropy coefficient | 0.01 |
| Value-function coefficient | 0.5 |
| Maximum gradient norm | 0.5 |
| Vector environments | 4 synchronous, independent streams |
| Rollout size | 5,000 transitions |
| Total timesteps | exactly 250,000 per primary seed |
| Debug timesteps | exactly 20,000; `NOT A PRIMARY RESULT` |
| Checkpoint interval | exactly 10,000 timesteps |
| Validation interval | exactly 10,000 timesteps |
| Early stopping | none for primary runs; numerical/infrastructure failure stops and restarts the affected seed |
| Training seeds | 1101, 2202, 3303, 4404, 5505 |
| Training generator | `v3-ppo-train-generator-v1` |
| Validation generator | `v3-ppo-validation-v1`, seeds 930000–930149 |
| Device | CPU for debug and all primary runs |
| Representative checkpoint | seed whose best validation score is closest to five-seed median; lower seed breaks an exact tie |
| Permutation alarms | median absolute normalized return delta `>0.05`, or mean absolute safe-population delta `>0.05`, or large systematic conditioned slot bias |

The suggested 1,024/256 rollout/batch pair is pre-results amended to 1,250/250. With
four environments this makes each rollout 5,000 transitions, divisible into 20 complete
batches. It also makes every 10,000-step checkpoint/validation boundary and the 250,000
maximum exact; SB3 therefore cannot overshoot the frozen cadence or budget by finishing
a partial rollout.

Gamma discounts learning targets internally. The physical reward and every reported
episode return remain undiscounted.

## 3. Training distribution

Each environment rank receives an independent deterministic stream keyed by training
seed, rank, and episode index. A stream entry samples independently of policy behavior:

- zones uniformly from `{4,5,6}`;
- shelters uniformly from `{6,7,8,9}`;
- horizon uniformly from integer steps 10–16;
- uncertainty uniformly from LOW/MEDIUM/HIGH (`v3-low-v1`, `v3-medium-v1`,
  `v3-high-v1`), with no literal label in the observation;
- zone population, severity, trend, subgroup descriptors, and connectivity;
- shelter capacity, occupancy, severity, valid initial status, and accessibility;
- route travel mean, travel uncertainty, base closure risk, and reachability;
- fleet count and vehicle capacity.

At least two physically safe/open destination profiles and one route from every zone to
each are constructed before schema and safety acceptance, preventing generator-created
WAIT-only starts. Later stochastic closures may legitimately reduce action availability.
No planner performance enters generation.

### Semantic-slot randomization

Physical profiles receive random opaque IDs before each scenario is validated. Canonical
lexicographic sorting therefore moves every physical profile uniformly among the slots
available for that scenario. IDs and properties remain stable within an episode, and
all dependent routes/actions use the same mapping. Counts below the fixed envelope leave
only trailing padding slots, as required by the frozen Phase 7 encoding.

## 4. Frozen validation suite and checkpoint selection

`data/eval_v3/training/validation_manifest.json` freezes 150 procedural scenarios before
training: exactly 50 LOW, 50 MEDIUM, and 50 HIGH. Its generator seeds, generated root
seeds, sizes, uncertainty IDs, and scenario SHA-256 values are committed. Training stream
coordinates, both Gate 6 seed ranges, the demo, and Phase 10 are disjoint.

At every 10,000 transitions, each model runs deterministic masked inference once on all
150 scenarios. The checkpoint metric is mean undiscounted `v3-reward-balanced-v1`
episode return. Ties use lower mean cumulative normalized exposure, then higher mean
safe-population fraction, then earlier checkpoint. This is not the final Phase 1 claim
metric. No planner comparison or exact oracle enters checkpoint selection.

All five best-validation checkpoints and all five final-timestep checkpoints are saved.
Phase 10 will evaluate all five best checkpoints; it will not headline a lucky seed.

## 5. Debug and primary-run protocol

Only after the Phase 9A commit exists, seed 1101 runs a 20,000-step debug session labeled
`NOT A PRIMARY RESULT`. It verifies finite losses/rewards, changing rewards, masks,
zero invalid validation selections, save/load, and deterministic validation inference.
Only crashes, NaNs, mask integration, serialization, or an obvious implementation error
may be fixed after debug without a new scientific preregistration.

The five primary seeds then run the same 250,000-step budget, generator, model,
hyperparameters, suite, cadence, and checkpoint rule. No performance early stopping is
allowed. Infrastructure failure restarts that seed from timestep zero; weak learning is
kept and reported. Environment scenario/root RNG and replication streams are separate
from PPO exploration RNG.

CPU is frozen because the installed PyTorch reports MPS unavailable and the model is a
small MLP. The four environments are synchronous to avoid multiprocessing variance.
Python, OS/hardware, SB3, sb3-contrib, Gymnasium, PyTorch, wall time, throughput, and
available memory are recorded. Exact scenario/evaluation replay is required. Exact
neural model-byte reproduction is not promised; a repeated small debug run measures
practical reproducibility under seeded CPU settings.

## 6. Logging and artifacts

Per seed, structured JSON and CSV under `data/eval_v3/training/` record training timestep
and episode return plus validation mean/median return, safe fraction, cumulative
normalized exposure and travel, completion, invalid-action count, mean/minimum allowed
action count, and WAIT-only timesteps. TensorBoard is optional and never the only log.

Models are stored separately under `models/v3/`:

```text
ppo_seed1101_best.zip   # BEST VALIDATION
ppo_seed1101_final.zip  # FINAL TIMESTEP
...
```

Each has JSON metadata containing the source Git commit, spec/environment/reward/safety
versions, training seed, software versions, Python, device, total/checkpoint timesteps,
validation score, observation/action dimensions, and compute measurements. No seed may
overwrite another.

## 7. Mask and numerical diagnostics

Validation requires exactly zero masked-action selections; any occurrence is an
integration failure rather than an ordinary result. Training monitors the environment's
defensive `invalid_action_attempted` value and reports any nonzero count. Every episode
records mean/minimum allowed actions and WAIT-only timesteps so generator or mask
degeneracy remains visible. All reported rewards, losses, and aggregate metrics must be
finite.

## 8. Frozen semantic-permutation diagnostic

Before primary training, `permutation_manifest.json` freezes 30 validation bases (the
first 30, balanced 10/10/10 by interleaved uncertainty) and five independent ID
permutations per base: 150 paired variants. Zone IDs, shelter IDs, route endpoints, and
action semantics are remapped consistently while all physical features stay fixed.

Because Phase 4 keyed stochastic draws include entity IDs, ordinary stochastic replay
would change hidden outcomes when an ID changes. To isolate slot identity, this one
diagnostic uses a deterministic transform of each scenario's already selected frozen
uncertainty config: random innovations, route closures, shelter degradation, and travel
noise are zero; deterministic trend and hazard-dependent expected travel remain. This
does not alter any Phase 4 config or any training/validation run.

For every best model, report original and remapped action sequences, action-equivalence
rate after mapping physical node identities, raw slot-selection frequencies, episode
return delta, normalized return delta using the frozen balanced reward width 1.0,
safe-population delta, and exposure delta. Flag `POTENTIAL_SLOT_SHORTCUT` if the median
absolute normalized return difference exceeds 0.05, mean absolute safe-population
difference exceeds 0.05, or a large systematic slot bias persists after conditioning on
the semantic permutations. The alarm is diagnostic; it is never silently followed by a
changed generator or retraining.

This directly tests the V1 S6/S7 failure question: whether changing only entity IDs while
preserving physical meaning materially changes policy behavior or performance.

## 9. Completion boundary

Phase 9 produces `V3_TRAINING_RESULT.md`, per-seed logs and metadata, aggregate learning
curves, five best and five final models, debug evidence, and the permutation diagnostic.
It runs all Phase 9 and prior tests and commits Stage 9B. It does not generate, inspect,
or evaluate the Phase 10 held-out suite and does not run the college demo.
