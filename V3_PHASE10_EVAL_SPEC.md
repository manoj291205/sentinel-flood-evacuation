# Sentinel-Agent V3 — Phase 10 Held-Out Evaluation Specification

> **Status: FROZEN BEFORE HELD-OUT GENERATION OR POLICY EVALUATION.**  
> Version: `v3-phase10-eval-spec-v1`  
> Date: 2026-09-07  
> This document implements, but does not replace, `V3_EVALUATION_PLAN.md`.

## 1. Research question and firewall

Phase 10 asks whether the already-trained five-seed MaskablePPO family provides a
measurable decision advantage over strong non-learned planning on unseen synthetic
stochastic evacuation scenarios. Phase 10 performs zero gradient updates, never calls
`model.learn`, never changes a checkpoint, and never selects a model or threshold using
the held-out results. The V1/college demo scenario is excluded.

Stage 10B may start only after the commit named
`V3 Phase 10A: freeze held-out policy evaluation` exists. All outputs are limited to the
synthetic Sentinel-Agent V3 environment.

## 2. Frozen suites and seeds

### Ordinary held-out suite

Generator `v3-heldout-generator-v1` uses generator seeds `1000000..1000599` and its own
SHA-256 namespaces for structure, attributes, and environment roots. It copies the broad
Phase 9 distributional basis without calling the Phase 9 generator: 4–6 zones, 6–9
shelters, horizon 10–16, randomized opaque IDs, populations, hazard/trend, shelter state,
fleet, connectivity, travel, and closure propensity. Acceptance requires schema validity
and at least one initially allowed dispatch per zone; it does not inspect future draws or
policy behavior.

There are exactly 600 units: indices modulo three assign 200 each to LOW, MEDIUM, and
HIGH. Every unit uses stochastic replication ID 0. This resolves the counts deferred in
Phase 1 before generation. Seeds are disjoint from Phase 9 training streams, validation
`930000..930149`, Gate 6 `610000..610119` and `620000..620119`, stress, permutation,
and the demo.

### Fresh permutation suite

One hundred separate bases use seeds `1020000..1020099`; they are not ordinary held-out,
training, validation, Gate 6, stress, or demo scenarios. Five variants per base use
permutation seeds `1030000..1030499`. The Phase 9 semantic-ID remapping algorithm is
reused unchanged. Its deterministic uncertainty transform is used so semantic IDs/slots
are the only source of trajectory differences.

### Separate stress suite

Generator `v3-stress-generator-v1` uses seeds `1040000..1040249`: 50 consecutive units
for each pre-registered category, with LOW/MEDIUM/HIGH assigned cyclically within each
category (17/17/16). Stress never enters the ordinary aggregate.

- `sudden_flood_surge`: at decision timestep 3 add 0.18 to every zone severity and 0.10
  to every shelter severity, clipped at 1.0.
- `route_closure_cascade`: at timestep 3 close the first `ceil(35%)` of initially
  reachable routes under a deterministic SHA-256 ranking of scenario root and route ID.
- `shelter_failure`: at timestep 3 close the initially largest-capacity shelter; canonical
  shelter ID breaks capacity ties. Existing reservations/arrivals retain Phase 4 semantics.
- `demand_shift`: at generation multiply physical zone 0 population by a seeded uniform
  factor in `[1.65,2.20]` and other zones by `[0.85,1.05]`.
- `longer_travel_lags`: at generation multiply every reachable route mean and derived
  standard deviation by 1.75.

Dynamic interventions run after ordinary current-timestep exogenous updates and before
the policy observation. They append audit records, preserve simulator invariants, and are
identical for every policy on a unit. Every required policy runs all 250 stress units.
No computational subset or extrapolation is permitted; if completion is genuinely
impossible, Phase 10 stops and reports the incomplete experiment.

## 3. Frozen policy set

The Phase 6 implementations run without parameter changes:
`random_valid`, `nearest_safe`, `risk_greedy`, `lookahead_k2`, `lookahead_k3`, and
`sampled_mpc` (`N=16`, `H=3`, master seed 76001). The lower reference for every unit is
the arithmetic mean of random-valid policy seeds `73001..73005`.

All five best-validation MaskablePPO checkpoints run deterministically with masks:
`models/v3/ppo_seed{1101,2202,3303,4404,5505}_best.zip`. Results retain both training seed
and scenario identity. For each scenario the headline PPO family value is the equal mean
of the five seed-specific physical values. Tables also report every seed and the mean,
population standard deviation, minimum, and maximum across seed-level aggregates. Seed
4404 alone is frozen for qualitative traces and never substitutes for the family result.

## 4. Principal practical comparator

Phase 1 requires validation selection after safety and latency eligibility. The already
sealed Gate 6 results are the pre-test planner-validation record. On the practical suite,
`lookahead_k2` (p95 135.26 ms), `lookahead_k3` (1,948.89 ms), and `sampled_mpc`
(251.42 ms) fail the frozen 100 ms budget. `nearest_safe` and `risk_greedy` are eligible
and safety-clean. Risk-greedy has higher Gate 6 validation NSU-exact mean (0.6279 versus
0.5514), higher median (0.8305 versus 0.7075), and higher practical G6U (0.21794 versus
0.21133). The difference exceeds the 0.002 tie band.

Therefore the principal comparator is permanently `risk_greedy`. This is not a choice
from Phase 10 results. All stronger-but-latency-ineligible planners remain in every table
and may visibly outperform both policies; they are not hidden or weakened.

## 5. Observation-matched diagnostic

`observation-matched-greedy-v1` receives exactly three objects: the already-built
384-value float observation, the 55-value Boolean mask, and the public fixed action map.
It is stateless and cannot receive `EpisodeState`, `ScenarioV3`, a simulator, uncertainty
configuration, root seed, audit log, pending arrival entries/times, or future outcomes.

For every allowed dispatch it applies the already-frozen risk-greedy weights to the
visible source-severity, destination-safety, available-capacity fraction, monotonic travel
feature, closure-safety, and monotonic travel-uncertainty feature. Highest score wins;
lowest action index breaks ties; WAIT is used only when no dispatch is allowed. The
capacity and travel components necessarily differ from full risk-greedy because absolute
batch/capacity and exact minutes are not recoverable. It is a secondary one-step
diagnostic, not the principal comparator and not a fake model planner.

## 6. Metrics and aggregation

The Phase 1 definitions are literal. Episode return is undiscounted balanced Phase 8
reward. At each decision, exposure sums waiting-zone population times current zone hazard
plus every in-transit group times the route hazard proxy. Restricted mean time to safety
weights each successful group by `arrival_timestep × timestep_minutes`; every person not
safe at termination receives the fixed scenario horizon in minutes.

Travel person-minutes use each completed event's realized continuous travel minutes. An
event still in transit at horizon contributes the lesser of its realized duration and
elapsed minutes from departure to horizon. The sum is divided by initial population.
Current Phase 4 routes fail only before departure; consequently post-departure route
failure is measured and expected to remain zero. Unsafe, capacity, known-closed-route,
mechanically invalid, and masked-fallback numerators and denominators are retained.

`NSU-practical` is the ratio of paired aggregate means:

```text
(mean return(policy) - mean return(random_valid five-seed lower))
/
(mean return(risk_greedy) - mean return(random_valid five-seed lower))
```

It is unclipped. Denominators `<=0.01` are `NA`; invalid bootstrap draws over 5% suppress
the CI. It is never labeled or combined with NSU-exact. LOW/MEDIUM/HIGH are reported
separately and their estimates receive exactly one-third weight in the combined result.
The report includes completion, safe fraction, exposure (and person-minutes), restricted
time to safety, safety/mechanical rates, travel person-minutes, return, linear p10,
worst-decile return, fractional-boundary CVaR10 (higher return is better), and latency.
Population metrics are shown as episode macro means and explicitly labeled micro totals.

## 7. Statistics

Bootstrap seed `10010007` and exactly 10,000 draws are frozen. Scenarios are indivisible
clusters; no seed×scenario row is treated as an independent environmental sample. PPO
comparisons use the Phase 1 two-level bootstrap: independently resample five training
seeds with replacement, then resample paired scenario clusters with replacement, and
compute the five-seed mean within sampled scenarios. CIs are percentile 2.5%–97.5%.

The principal report gives paired mean and median native differences where meaningful,
plus CIs for NSU-practical difference, exposure relative reduction
`(B-PPO)/B`, tail-NSU difference, and unsafe-rate difference. Tail NSU uses Phase 1:

```text
(CVaR10(PPO)-CVaR10(random))/(CVaR10(risk_greedy)-CVaR10(random))
```

with the same 0.01 cutoff. Missing or failed runs are disclosed and only common complete
clusters enter a paired comparison.

## 8. Permutation diagnostic and alarm

For every PPO seed, each original and five remapped variants are compared after mapping
actions back to physical node identity. Report action equivalence, signed and median
absolute NSU deltas, absolute safe-population and exposure deltas, and worst return delta.
The NSU delta uses the frozen ordinary practical return denominator; because the common
references cancel, it is `(variant return-original return)/ordinary denominator`.

The Phase 9 alarm is reproduced if median absolute normalized return/NSU delta exceeds
0.05 or mean absolute safe-population delta exceeds 0.05. The label remains
`POTENTIAL_SLOT_SHORTCUT`. It is a separate representation conclusion and does not
rewrite the formal Phase 1 usefulness rule.

## 9. Latency

Phase 1 §17 is authoritative over this continuation prompt's suggestion to include
observation and mask creation. Timing begins with an already-built observation/mask and
ends when an action is returned. It excludes scenario parsing, observation/mask building,
environment transition, initialization, model loading, logging, rendering, and network
calls. All policies are loaded and warmed first; one process with fixed Torch threads is
used for a separate latency pass over representative ordinary states. At least 1,000
decisions per policy are timed. Report mean, median, p90, p95, population standard
deviation, and maximum in milliseconds, plus hardware/software metadata.

## 10. Safety and qualitative trace

`v3-safety-v1` hard safety is ON for every main and stress policy. Any selected action is
checked against the exact pre-action snapshot; PPO selection outside its mask is counted
before WAIT fallback. Mechanical violations are implementation defects, not tradeoffs.

The qualitative scenario is selected without policy output: compute for every ordinary
scenario its initial population-weighted mean zone severity plus mean reachable-route
travel divided by 55; choose the median score, with manifest index as tie-breaker. The
trace shows risk-greedy, the principal planner (the same policy, noted explicitly), and
PPO seed 4404. It explains behavior but supplies no inferential evidence.

## 11. Frozen decision logic

For a set, the Phase 1 §9 gate passes only if at least one supported benefit holds:

- PPO minus baseline NSU-practical is at least 0.02 and its 95% CI is above zero; or
- exposure relative reduction is at least 5% and its 95% CI is above zero; or
- PPO minus baseline tail NSU is at least 0.02 and its 95% CI is above zero;

and PPO unsafe rate does not exceed the baseline. If either has unsafe executions, the
upper CI for PPO-minus-baseline unsafe rate must be at most zero. The benefit must survive
the five-seed aggregate.

The generated function returns exactly:

- `YES` when the combined equal-weight gate passes and no stratum has a supported safety
  regression;
- `MIXED` when combined does not pass but a frozen stratum, tail, or stress-category gate
  passes without safety regression;
- `NO` otherwise, including a safety tradeoff or planners matching/beating PPO.

The slot result is reported independently as `PASS` or `POTENTIAL_SLOT_SHORTCUT`.

## 12. Reproducibility and stop conditions

All manifests store full scenario hashes, generator/environment seeds, uncertainty,
replication, sizes, and versions. Raw rows retain policy/training seed and failures.
Ten figures are generated directly from structured results, never manually edited.
Stage 10B creates its listed JSON artifacts, report, tests, figures, and documentation,
then commits `V3 Phase 10B: held-out planner-versus-PPO evaluation` and stops. Phase 11,
retraining, reward changes, observation changes, and slot repair remain out of scope.

## 13. Pre-results acceptance checklist

- [x] 600 normal units and 200/200/200 balance frozen.
- [x] All normal, permutation, policy, bootstrap, and stress seeds frozen.
- [x] New independent generator and structural range frozen.
- [x] Replication 0 and paired keyed randomness frozen.
- [x] Six planners, five best PPO checkpoints, and aggregation frozen.
- [x] Gate-6-selected `risk_greedy` principal comparator frozen.
- [x] Phase 1 metrics, two-level bootstrap, and decision function implemented.
- [x] Observation-matched information boundary and score frozen.
- [x] Fresh 100×5 permutation diagnostic and old alarms frozen.
- [x] Five 50-unit stress categories and interventions frozen.
- [x] Phase 1 latency method and prompt conflict recorded.
- [x] Hard safety ON; no training or model change.
- [x] No held-out/stress/permutation scenario has been generated or evaluated.
