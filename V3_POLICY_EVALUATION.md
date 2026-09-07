# Sentinel-Agent V3 — Frozen Held-Out Policy Evaluation

> **SYNTHETIC EXPERIMENT ONLY.** This report does not establish real-world emergency-response effectiveness.

## Research question

Does the frozen five-seed MaskablePPO family provide a measurable decision advantage over strong non-learned planning on unseen stochastic V3 scenarios?

## Pre-registered evaluation rules

Stage 10A commit `c92173dc0001e60cd7db69d89fab8f391d202905` froze 600 ordinary scenarios, all seeds, policies, metrics, the two-level 10,000-draw bootstrap, stress/permutation suites, latency, and the Phase 1 YES/NO/MIXED function before generation. No training or checkpoint mutation occurred.

## Frozen policies, suite, and PPO seed handling

The ordinary suite has 600 new `v3-heldout-generator-v1` scenarios (200 LOW, 200 MEDIUM, 200 HIGH), 4–6 zones, 6–9 shelters, horizon 10–16, and replication 0. All Phase 6 planners and all best checkpoints for seeds 1101, 2202, 3303, 4404, and 5505 run every unit. The PPO-family row is an equal-weight per-scenario seed mean; seed identity remains retained. Seed 4404 is only the pre-frozen representative trace model.

## Principal baseline

`risk_greedy` is the pre-test principal comparator. Gate 6 excluded lookahead-2/3 and MPC from principal eligibility at the 100 ms p95 budget; risk-greedy beat nearest-safe outside the 0.002 tie band. The ineligible stronger planners remain fully reported.

## Main results

| Policy | NSU-practical | Safe pop. | Exposure | CVaR10 | Completion | Unsafe | Median ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Random valid | 0.0000 | 0.6595 | 1839.73 | 0.0004 | 0.0623 | 0.0000 | 0.007 | 0.013 |
| Nearest safe | 0.7615 | 0.7317 | 1384.40 | 0.0325 | 0.1783 | 0.0000 | 0.023 | 0.040 |
| Risk greedy | 1.0000 | 0.7596 | 1456.02 | 0.0509 | 0.1083 | 0.0000 | 0.158 | 0.467 |
| Lookahead-2 | 1.4752 | 0.8236 | 1322.76 | 0.1012 | 0.1900 | 0.0000 | 13.479 | 47.299 |
| Lookahead-3 | 1.5309 | 0.8300 | 1318.64 | 0.1030 | 0.2217 | 0.0000 | 189.992 | 1442.111 |
| Sampled MPC | 1.4594 | 0.8308 | 1469.18 | 0.1020 | 0.2217 | 0.0000 | 555.458 | 1613.113 |
| PPO five-seed aggregate | 0.2091 | 0.6826 | 1817.49 | 0.0038 | 0.0963 | 0.0000 | 0.638 | 1.895 |

NSU-practical is the Phase 1 ratio of aggregate paired means and is not NSU-exact. Values are intentionally unclipped.

## Paired statistical comparison and tail behavior

- NSU difference: -0.7919, 95% CI [-0.8384, -0.7453].
- Exposure relative reduction: -0.2483, 95% CI [-0.2613, -0.2358].
- Tail-NSU difference: -0.9314, 95% CI [-1.1988, -0.8216]. Higher return CVaR10 is better.
- Unsafe-rate difference: 0.0000, 95% CI [0.0000, 0.0000].
- Combined Phase 1 gate: `False`; supported benefit channels: `none`.

## LOW / MEDIUM / HIGH

| Regime | PPO NSU | PPO safe | PPO exposure | PPO p10 | PPO CVaR10 | Gate |
|---|---:|---:|---:|---:|---:|---:|
| low | 0.1272 | 0.7016 | 1762.01 | 0.0751 | 0.0241 | False |
| medium | 0.1879 | 0.6956 | 1825.70 | 0.0624 | 0.0063 | False |
| high | 0.3123 | 0.6505 | 1864.76 | 0.0465 | -0.0142 | False |

## Five-seed PPO variability

| Seed | NSU-practical | Safe pop. | Exposure | CVaR10 | Completion | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| 1101 | 0.2220 | 0.6848 | 1821.41 | -0.0067 | 0.0783 | 0.644 ms |
| 2202 | 0.2009 | 0.6810 | 1814.99 | -0.0096 | 0.1083 | 0.642 ms |
| 3303 | 0.2426 | 0.6863 | 1819.01 | -0.0079 | 0.0983 | 0.633 ms |
| 4404 | 0.2170 | 0.6843 | 1817.67 | -0.0088 | 0.1033 | 0.634 ms |
| 5505 | 0.1632 | 0.6765 | 1814.37 | -0.0142 | 0.0933 | 0.638 ms |

Across-seed NSU: mean 0.2091, population SD 0.0265, minimum 0.1632, maximum 0.2426.

## Observation-matched planner diagnostic and information asymmetry

The secondary `observation_matched_greedy` sees only the 384-vector, mask, and public action map. PPO-family return minus this diagnostic is -0.0269; PPO-family exposure minus it is 258.56. The original planners retain exact pending-arrival detail, so the principal comparison is conservative against PPO; this diagnostic estimates but cannot eliminate the representation/modeling gap.

## Slot-permutation robustness

Across 100 separate bases × five variants × five PPO seeds, mean action equivalence is 0.1157, median absolute NSU delta is 0.6092, mean absolute safe-population delta is 0.0929, and the frozen alarm is `POTENTIAL_SLOT_SHORTCUT`. The Phase 9 alarm remains historical evidence regardless of this reproduction result.

## Stress robustness

| Category | PPO NSU-practical | PPO safe | PPO exposure | Gate |
|---|---:|---:|---:|---:|
| sudden_flood_surge | 0.1641 | 0.6435 | 2369.50 | False |
| route_closure_cascade | 0.3062 | 0.6620 | 1870.11 | False |
| shelter_failure | 0.2446 | 0.6450 | 1847.92 | False |
| demand_shift | 0.1646 | 0.6166 | 2115.81 | False |
| longer_travel_lags | -0.0044 | 0.5154 | 2260.95 | False |

## Decision latency

Latency is a separate warmed, one-process, ≥1,000-decision Phase 1 benchmark from already-built policy input/mask to action; loading, mask/observation construction, and transition time are excluded.

| Policy | Median ms | p90 ms | p95 ms | Maximum ms |
|---|---:|---:|---:|---:|
| Random valid | 0.007 | 0.012 | 0.013 | 4.299 |
| Nearest safe | 0.023 | 0.035 | 0.040 | 6.632 |
| Risk greedy | 0.158 | 0.376 | 0.467 | 6.329 |
| Lookahead-2 | 13.479 | 38.960 | 47.299 | 89.996 |
| Lookahead-3 | 189.992 | 1045.666 | 1442.111 | 3816.887 |
| Sampled MPC | 555.458 | 1358.219 | 1613.113 | 2660.287 |
| Observation-matched greedy | 0.049 | 0.107 | 0.131 | 4.899 |
| PPO 1101 | 0.644 | 1.118 | 1.765 | 9.571 |
| PPO 2202 | 0.642 | 1.153 | 2.257 | 9.877 |
| PPO 3303 | 0.633 | 1.106 | 1.904 | 9.702 |
| PPO 4404 | 0.634 | 1.116 | 1.861 | 12.362 |
| PPO 5505 | 0.638 | 1.088 | 1.687 | 10.405 |
| PPO five-seed aggregate | 0.638 | 1.116 | 1.895 | 10.384 |

## Safety and mechanical integrity

Across the ordinary all-policy table: unsafe dispatches `0`, capacity violations `0`, known-closed-route dispatches `0`. Across individual PPO seeds, invalid masked selections are `0`. Any nonzero mechanical count is treated as a defect rather than a tradeoff.

## Fixed qualitative trace

The policy-independent median-difficulty rule selected manifest index `599` (`v3-heldout-generator-v1-00000000000f4497`). Important-timestep decisions for risk-greedy/the strongest practical planner and representative PPO seed 4404 are recorded in `qualitative_trace.json`. The trace is explanatory only and did not select any model, threshold, or conclusion.

## Final frozen RL usefulness conclusion

# NO

This label is generated by the Phase 1 gate, not assigned narratively. See the paired benefit channels, regime gates, and stress gates above for the exact reason.

## Representation robustness

# POTENTIAL_SLOT_SHORTCUT

## Limitations and next action

The environment, hazards, populations, routes, and reward weights are synthetic modeling choices. The principal planner has richer pending-arrival information. The flat MLP has known semantic-slot sensitivity. There is one stochastic replication per scenario, Phase 4 has no post-departure route failures, the observation-matched heuristic is stateless, and latency is machine-specific. No real-world operational effectiveness or general RL superiority is claimed.

Phase 10 stops here. Any Phase 11 dashboard or future permutation-aware architecture experiment requires separate project-owner direction and cannot rewrite this result.
