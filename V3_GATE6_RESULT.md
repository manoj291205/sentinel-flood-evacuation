# Sentinel-Agent V3 — Gate 6 Result

> **Verdict: `PROCEED_TO_RL`.** The pre-registered planning gate found sufficient
> remaining lower-tail clairvoyant headroom to justify testing a learned policy. This
> does not show that RL is necessary or that PPO will win.

## Question and pre-registered gate

Gate 6 asks whether a fast, non-clairvoyant planner essentially solves the frozen V3
stochastic sequential problem. Per `V3_PLANNER_SPEC.md`, `STOP_RL` requires one practical
planner to satisfy all three conditions on 120 exact units:

```text
median per-unit NSU-exact >= 0.99
p10 per-unit NSU-exact    >= 0.97
p95 decision latency      <= 100 ms
```

The specification, utility, planners, weights, information boundaries, generator,
suites, timeout, and gate were committed at `ae89e6456603e9892fcb1868f34bcf3f7ce8fdac`
before these results were generated.

## Planner definitions and information boundary

The run implements random-valid, nearest-safe, frozen six-component risk-greedy,
exhaustive expected-model lookahead at depths 2 and 3, and sampled MPC with `N=16/H=3`.
All use Phase 5 hard safety ON. Deterministic ties use canonical semantic order.

Practical planners received detached current observations, pending-arrival metadata,
current safety snapshots, public time/fleet values, and public uncertainty parameters.
They did not receive the environment root seed, replication ID, stochastic simulator,
private random streams, regional latent state, or future outcomes. MPC used separate
SHA-256 keyed planner randomness rooted at planner seed 76001.

The exact oracle was separately permitted to clone the real simulator and exhaustively
inspect realized futures. It remained subject to simulator mechanics, reservations,
arrivals, and Phase 5 safety and is labeled **CLAIRVOYANT UPPER BOUND — NOT A PRACTICAL
POLICY**.

## Scenario suites

- Exact: 120 synthetic scenarios, two zones, two shelters, horizon 5, seeds
  `610000..610119`, 40 each LOW/MEDIUM/HIGH, replication 0.
- Practical: 120 synthetic scenarios, four zones, five shelters, horizon 10, seeds
  `620000..620119`, 40 each LOW/MEDIUM/HIGH, replication 0.
- Generator: `v3-gate6-generator-v1`; all scenario/geography/data provenance is explicitly
  simulated or fictional.
- Exact lower reference: mean of random-valid policy seeds `73001..73005` per unit.

These balanced strata are an experimental design, not a real-world prevalence estimate.

## Oracle correctness and normalization

All 120 exact searches completed within the frozen five-second per-unit deadline. There
were zero timeouts, zero invalid denominators, zero search/replay mismatches, and no
practical planner exceeded its exact oracle.

The oracle expanded 28,177 states and evaluated 84,612 branches in total. Median search
time was 195.83 ms per exact unit; the maximum was 1.668 s. Hand-solvable tests verify
that a short route arriving inside the horizon beats a long route that cannot arrive, and
that the oracle obeys normal safety/mechanical masks.

`NSU-exact` used the frozen G6U range and `epsilon_den=0.01`. Values were not clipped.

## Main exact-headroom result

| Planner | Median NSU-exact | p10 | Mean | Mean safe pop. | Mean exposure | Median latency ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Random valid | 0.0000 | 0.0000 | 0.0000 | 0.4256 | 177.79 | 0.0015 | 0.0028 |
| Nearest safe | 0.7075 | -0.0486 | 0.5514 | 0.5664 | 153.06 | 0.0037 | 0.0069 |
| Risk greedy | 0.8305 | 0.0236 | 0.6279 | 0.5886 | 154.56 | 0.0078 | 0.0150 |
| Lookahead-2 | 0.9817 | 0.3999 | 0.8277 | 0.6335 | 151.43 | 0.3291 | 2.0305 |
| **Lookahead-3** | **0.9954** | **0.4306** | **0.8448** | **0.6413** | 153.07 | 0.4140 | 6.9601 |
| Sampled MPC | 0.9644 | 0.3417 | 0.8323 | 0.6449 | 157.54 | 6.5326 | 18.0360 |

Lookahead-3 crossed the median threshold and easily met exact-suite latency, but its p10
was 0.4306 rather than 0.97. The gate therefore does not repeat the old `% exactly
optimal` mistake: high median performance cannot hide a substantial lower tail.

## Results by uncertainty

| Regime | Strongest median planner | Median NSU-exact | Best p10 | Planner with best p10 |
| --- | --- | ---: | ---: | --- |
| LOW | Lookahead-3 | 1.0000 | 0.6719 | Sampled MPC |
| MEDIUM | Lookahead-3 | 0.9968 | 0.5279 | Lookahead-3 |
| HIGH | Lookahead-3 | 0.9761 | 0.0670 | Sampled MPC |

No uncertainty stratum individually meets the registered combined median/p10 rule. The
remaining headroom becomes markedly more severe in HIGH, consistent with—not proof
of—the intended partial-observability challenge.

## Practical-size latency and scaling

Each practical planner was timed for 1,200 decisions after 20 excluded warm-up calls.
Times cover action selection only via `perf_counter_ns` on the registered Apple M1
reference machine.

| Planner | Median ms | p95 ms | Maximum ms | Model transitions |
| --- | ---: | ---: | ---: | ---: |
| Random valid | 0.0021 | 0.0045 | 0.0317 | 0 |
| Nearest safe | 0.0062 | 0.0105 | 0.0956 | 0 |
| Risk greedy | 0.0338 | 0.0567 | 0.1114 | 0 |
| Lookahead-2 | 22.6825 | 135.2568 | 663.9500 | 159,670 |
| Lookahead-3 | 144.2123 | 1,948.8888 | 4,557.7113 | 2,016,867 |
| Sampled MPC | 101.0259 | 251.4226 | 432.7448 | 569,744 |

The STOP gate uses exact-suite latency as pre-registered. Practical scaling shows that
unpruned lookahead-2/3 and MPC exceed the 100 ms p95 project target at the larger action
set; this limitation is reported, not repaired post-results with unregistered pruning.

## Physical diagnostics

On the exact suite, mean safe-population fraction increased from 0.4256 for the five-seed
random lower reference to 0.6413 for lookahead-3 and 0.6449 for MPC. Lookahead-2 had the
lowest mean exposure among practical planners (151.43 person-timesteps); nearest-safe had
the lowest non-random mean transit burden after lookahead-2 (602.33 versus 530.92
person-minutes for lookahead-2). These diagnostics do not override the headroom gate.

Phase 4 currently lets valid in-transit journeys survive later closure, so observed route
failures are zero by model definition. All main planners used safety ON, so executed unsafe
dispatches were zero.

## Safety-exclusion diagnostic

Across the 599 exact decisions for lookahead-3 there were 2,396 dispatch candidates:
942 mechanically invalid, 228 mechanically valid but hard-safety excluded, and 1,226
allowed. Other practical trajectories saw 198–227 hard-safety exclusions. The Phase 5
threshold remained exactly 0.70; no distribution or threshold was tuned in response to
the earlier low exclusion count.

## Leakage, pairing, and RNG checks

- Same public input plus fixed planner seed reproduces MPC action and candidate scores.
- Risk-greedy, lookahead-2/3, and MPC give identical decisions under different hidden
  environment seeds when current public observations match.
- Random-valid and MPC planner randomness does not consume environment randomness.
- Different planner action sequences preserve paired exogenous hazard/closure paths.
- Practical planner types expose no oracle-context parameter; only `oracle_small.py`
  accesses private simulator futures.

## Gate verdict

`PROCEED_TO_RL`

No practical planner satisfies both headroom thresholds, even though every exact-suite
planner satisfies the latency threshold. The strongest median result leaves substantial
lower-tail headroom: lookahead-3 p10 is 0.4306. Therefore the pre-registered planning gate
found sufficient remaining headroom to justify testing whether a learned policy can
capture it.

This result does **not** establish that RL is necessary, that PPO will improve utility,
or that PPO will pass Phase 1's eventual materiality and safety gates.

## Limitations and next action

- G6U is a pre-results Gate-6 diagnostic utility, not the future PPO training reward.
- One stochastic replication per synthetic scenario limits variance characterization.
- Exact scenarios are deliberately small; practical scenarios have no oracle.
- Practical expected lookahead holds current route/status structure rather than predicting
  actual hidden discrete outcomes; MPC uses only 16 sampled futures.
- Unpruned practical lookahead scales poorly.
- Route failures are absent under current Phase 4 in-transit survival semantics.
- No real-world effectiveness or prevalence claim follows from these fictional suites.

The next permissible project phase is Phase 7, but it must not begin automatically.
Project-owner direction is required after reviewing this `PROCEED_TO_RL` result.
