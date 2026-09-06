# Sentinel-Agent V3 — Pre-registered Evaluation Plan

> **Status: FROZEN BEFORE V3 RESULTS.** This protocol is committed before the V3
> simulator, stochastic dynamics, planners, reward, or PPO implementation exists. It
> defines how those systems will be judged; it is not evidence that any of them works.

## 1. Scope and evaluation philosophy

V1 showed why a learned component is not a contribution merely because it runs. Its
one-step reward was fully observable and closed form, so greedy argmax was the oracle and
outperformed PPO. Gate 1A.5 then showed why `% exactly optimal` can mislead: a heuristic
was exactly optimal on only about half the instances yet captured median normalised score
0.992, while a two-step planner captured 1.000 at practical latency. The exact-match rate
counted a negligible miss and a catastrophic miss equally.

V3 therefore evaluates utility, safety, tail behavior, and latency together. The main PPO
comparator is the **strongest practical non-learned policy**, selected on validation data,
not random or a deliberately weak greedy rule. Every policy sees paired scenarios and
paired exogenous stochastic outcomes. Negative results are valid outcomes: if planning
matches or beats PPO, the conclusion is that RL was evaluated and was not necessary for
this formulation.

This plan applies to V3 only. It does not alter `EVALUATION.md`, `EVALUATION_V1.md`, the
V1 tag, or the Gate 1A/1A.5 results.

## 2. Evaluation units and frozen splits

An evaluation unit is:

```text
(scenario_id, scenario_seed, stochastic_replication_id, uncertainty_stratum)
```

All policies are evaluated on the same frozen units. Development data may be regenerated.
Validation seeds select planner configuration, PPO checkpoint/hyperparameters, and the
principal practical baseline. Held-out test seeds are opened only after those choices are
frozen. Stress suites are separate and never pooled into the in-distribution test result.

Final suite sizes and the number of stochastic replications are **to be fixed before the
first final experiment**, after Phase 2–4 runtime measurement but before policy results.
The master-plan target is 200 validation and 500 test scenarios (minimum fallback: 100 and
250), with LOW/MEDIUM/HIGH represented equally.

## 3. Primary metric: normalised safe utility

For policy `p` over an evaluation set `S`, let `R_p(i)` be undiscounted episode return on
unit `i`, `L(i)` the lower-reference return, and `U(i)` the applicable upper/reference
return. Define:

```text
mean_R_p = mean_i∈S R_p(i)
mean_L   = mean_i∈S L(i)
mean_U   = mean_i∈S U(i)

normalised_safe_utility(p, S) =
    (mean_R_p - mean_L) / (mean_U - mean_L)
```

The ratio is computed from paired aggregate means, not by averaging unstable per-episode
ratios. Values below 0 and above 1 are retained: they mean worse than the lower reference
or better than the nominated reference. They are not clipped.

For distribution diagnostics only, define per-unit headroom capture
`h_p(i) = (R_p(i) - L(i)) / (U(i) - L(i))` wherever the per-unit denominator exceeds
`epsilon_den`. Its median and p10 are reported with the valid/invalid unit counts. This
diagnostic is used by the Gate 6A tail rule; it does not replace the aggregate primary
metric and is never averaged to manufacture a headline value.

### 3.1 Lower reference

`random_valid` is the lower reference. On each evaluation unit it selects uniformly from
the current valid-action mask using a policy RNG independent of environment RNG. To
reduce dependence on one lucky action sequence, `L(i)` is the arithmetic mean return of
**five pre-generated random-policy seeds** on the same unit. Those five seeds will be
derived and stored before final evaluation.

### 3.2 Two upper/reference regimes

| Label | Evaluation set | `U(i)` | Permitted interpretation |
| --- | --- | --- | --- |
| `NSU-exact` | tractable small instances only | exact clairvoyant oracle return | fraction of sampled-future upper-bound headroom |
| `NSU-practical` | larger operational instances | strongest practical non-learned baseline, selected on validation and then frozen | gain relative to the best deployable planner tested |

The exact oracle may inspect the complete sampled future and is always labeled
**CLAIRVOYANT UPPER BOUND**. It is not a deployable baseline. The practical reference is
chosen from `nearest_safe`, `risk_greedy`, `lookahead_k2`, `lookahead_k3`, and sampled
MPC using validation `normalised_safe_utility`, with safety and latency eligibility
applied first. Ties within 0.002 use lower p95 decision latency, then the simpler method.

`NSU-exact` and `NSU-practical` must appear in separate columns/tables. They must never
be averaged, pooled, or shown under one unlabeled “normalised utility” number. The primary
final policy comparison on operational-size scenarios is `NSU-practical`; `NSU-exact`
diagnoses headroom on the small suite.

### 3.3 Zero and near-zero denominators

`V3_REWARD_SPEC.md` must declare a theoretical episode-return range
`[R_min, R_max]`. Define:

```text
epsilon_den = 0.01 * (R_max - R_min)
```

If `mean_U - mean_L <= epsilon_den`, normalisation for that set/stratum is **undefined**
and reported `NA`; the denominator is never replaced, clipped, or padded. Raw paired
return differences, safety metrics, exposure, and latency are still reported. If the
range is unbounded or cannot be established, this is a blocking metric defect that must
be amended under §15 before final experiments.

The same cutoff applies to each `h_p(i)` diagnostic; invalid units are excluded only from
that diagnostic and their count/fraction is reported. They remain in every aggregate raw
metric and in the primary ratio of means.

Bootstrap replicates whose denominator is non-positive or at most `epsilon_den` are
invalid. Their fraction is reported. If more than 5% of replicates are invalid, no
confidence interval for that normalised result is claimed.

## 4. Secondary decision metrics

Let `P0` be initial population, `H` the terminal time in minutes, `D` the count of
executed dispatches, and `A` the count of all executed decisions including WAIT.
Population is counted in people, not dispatch batches.

| Metric | Computable definition |
| --- | --- |
| `evacuation_completion_rate` | Mean of `1[safely_arrived_population == P0]` across episodes at termination. |
| `safe_population_fraction` | `safely_arrived_population / P0` at termination. A person counts only after a successful arrival accepted by a shelter under the frozen safety semantics. |
| `exposed_person_timesteps` | `Σ_t Σ_g people(g,t) × hazard(g,t)` over all people not yet safe, including waiting zones and in-transit groups. One step at severity 1.0 contributes one exposed person-timestep per person. Also report person-minutes by multiplying by `timestep_minutes`. |
| `mean_time_to_safety` | Restricted person-weighted mean `Σ_j min(T_safe(j), H) / P0`; people not safely arrived receive `H`, preventing survivor-only bias. Report minutes. |
| `unsafe_dispatch_rate` | Executed dispatches classified unsafe at decision time under §5, divided by `D`. If `D=0`, report `NA` and separately report zero dispatches. |
| `capacity_violation_rate` | Executed dispatches that cause/reserve occupancy above capacity or are accepted with insufficient available capacity, divided by `D`. |
| `route_failure_rate` | Dispatches valid at departure that subsequently fail to reach their destination because the route becomes unavailable, divided by dispatches started. Known-closed-route attempts are unsafe dispatches, not post-departure failures. |
| `mean_travel_person_minutes` | Total realized person-minutes spent in transit, including time before a failed/stranded dispatch terminates, divided by `P0`. |
| `decision_latency_ms` | Wall-clock milliseconds from receipt of an already-built observation and mask until an action is returned. Excludes environment transition, model/planner initialization, model loading, logging, and rendering. |
| `episode_return` | Undiscounted `Σ_t reward_t` from reset through termination. Evaluation does not apply PPO's training discount. |
| `worst_decile_return` | Empirical 10th percentile of episode return (`p10`, linear quantile interpolation). This named field intentionally duplicates the required p10 output for auditability. |
| `CVaR_10` | Mean of the lowest 10% of episode returns, using fractional weight at the boundary so exactly 10% of empirical mass is included. Higher is better. |

For count rates, reports include numerator, denominator, and percentage. Aggregate
population metrics are additionally recomputed as micro-averages so episodes with small
populations cannot dominate an unlabelled macro-average.

### Decisions deferred but required before experiments

The following are not guessed in Phase 1. Each must be fixed in the named phase and
committed before generating final results:

- Phase 3/4: route-hazard aggregation for in-transit exposure.
- Phase 3/5: whether shelter degradation after arrival can revoke “safely arrived” status;
  if so, conservation and exposure accounting must follow those people.
- Phase 3: exact terminal treatment of dispatches still in transit.
- Phase 5: hard hazard threshold, restricted-shelter semantics, terminal-deadline rule,
  and the complete deterministic hard-rule registry.
- Phase 8: episode-return bounds and reward weights used by `epsilon_den`.
- Phase 10: suite sizes/replications if runtime requires the documented fallback.

## 5. Safety metric semantics

Safety labels come from simulator state and versioned deterministic rules, never from a
natural-language explanation at scoring time.

An **unsafe dispatch** is an executed non-WAIT `(zone, shelter)` action for which at least
one frozen hard predicate is false at decision time, including: no population to send,
no dispatch/fleet availability, insufficient unreserved capacity for the batch, shelter
not in an accepting status, destination hazard at/above the hard threshold, route known
closed/unreachable, or arrival beyond a forbidden terminal deadline. Each violation is
logged by rule ID.

An **unsafe shelter recommendation** is a selected destination that fails a shelter-level
hard predicate at decision time: accepting status, sufficient unreserved capacity, or
destination hazard threshold. Route and source-zone failures do not by themselves make
the shelter unsafe; they make the dispatch unsafe.

A **route failure** is a post-departure event where a dispatch that was route-valid when
executed cannot arrive because subsequent stochastic route state removes all permitted
paths. Travel delay without failure is not a route failure. A known-closed or unreachable
route selected at decision time is an unsafe/unreachable attempt and is reported
separately, even if the simulator rejects it before movement.

A **capacity violation** occurs if reservations plus occupied places exceed total current
capacity at any transition, or if a dispatch is accepted/reserved when available capacity
is smaller than its batch. Capacity lost after a valid reservation is logged separately
as `capacity_loss_after_dispatch`; whether it also becomes a violation is one of the
Phase 5 semantics that must be frozen before experiments.

Primary safety rates count **executed actions only**. Actions removed by a mask are not
denominator events and cannot be claimed as unsafe dispatches avoided. Proposed masked
actions, rejected actions, mask cardinality, and `masked_action_attempt_rate` are separate
diagnostics. In the safety-OFF ablation, actions that would fail the same frozen hard
predicates are still labeled unsafe even though the mask does not block them.

## 6. Paired stochastic evaluation

No algorithm receives an easier set of futures.

- Every algorithm runs every frozen evaluation unit.
- Exogenous randomness uses deterministic, event-keyed draws derived from
  `(scenario_seed, replication_id, timestep, event_type, entity_ids)`, not one mutable RNG
  whose sequence shifts when policies take different actions.
- Thus a route/timestep shock has the same potential draw for every policy that exposes
  that event, while policies are not forced to experience events their own actions never
  encounter.
- Scenario generation, regional flood shocks, local flood noise, travel noise, route
  closure, shelter failure, and policy exploration receive separate namespaces/streams.
- Planner rollouts may sample only from the agent-visible stochastic model with planner
  RNG derived from a separate recorded seed. They may not inspect realized future draws.
- PPO evaluation is deterministic given its observation unless a separately labeled
  stochastic-policy experiment is pre-registered. PPO training RNG never changes the
  environment outcome stream.
- `random_valid` policy seeds are frozen independently from environment seeds.

Each result row stores scenario seed, replication ID, environment stream/version,
algorithm/config hash, policy or training seed, and outcome. Missing/failed runs are not
silently dropped; counts and causes are reported, and paired comparisons use only the
common completed set with the loss of units disclosed.

## 7. Statistical reporting

For each policy and important paired policy-minus-baseline comparison, report:

- sample size and missing count;
- mean, median, and sample standard deviation;
- p10 and p90;
- paired bootstrap 95% confidence interval;
- `CVaR_10` for return, normalised utility where defined, exposure, and safe-population
  fraction where a lower tail is meaningful;
- raw numerator/denominator for safety rates;
- effect in native units and percentage/relative effect where defined.

Use a frozen bootstrap seed and at least 10,000 resamples. Resample scenario IDs as
clusters so stochastic replications of one scenario stay together. For PPO comparisons,
use a two-level bootstrap: resample PPO training seeds, then paired scenario clusters.
The interval is the 2.5th–97.5th percentile. No unpaired interval may be presented as the
primary comparison.

The combined LOW/MEDIUM/HIGH result is an equal-weight macro-average of the three stratum
estimates, regardless of minor count imbalance. Each stratum is also reported separately.
Multiplicity is handled by naming the combined practical-reference comparison as primary;
stratum, stress, and secondary-metric findings are labeled secondary rather than mined for
an unqualified win.

## 8. Required baseline hierarchy

Every final policy benchmark includes:

1. `random_valid`
2. `nearest_safe`
3. `risk_greedy`
4. `lookahead_k2`
5. `lookahead_k3`
6. sampled MPC
7. MaskablePPO
8. clairvoyant exact oracle on tractable small instances only

An additional stronger legitimate baseline discovered before final evaluation must be
included; it cannot be omitted because it reduces PPO's apparent advantage. Planner
budgets and tuning use validation data only. The principal PPO comparator is the strongest
practical non-learned baseline after safety and latency eligibility, never
`random_valid`, nearest, or greedy merely because they are easier to beat.

## 9. RL usefulness decision gate

Let `B` be the frozen strongest practical non-learned baseline. PPO is supportable as a
claimed decision contribution only when **at least one** material benefit holds:

1. `NSU-practical(PPO) - NSU-practical(B) >= 0.02`; or
2. PPO reduces mean `exposed_person_timesteps` by at least 5% relative to `B`; or
3. PPO improves **tail-normalised utility** by at least 0.02, where

```text
tail_NSU(p) =
    (CVaR_10(return_p) - CVaR_10(return_random_valid))
    / (CVaR_10(return_B) - CVaR_10(return_random_valid))
```

and the same `epsilon_den`/`NA` rules apply.

The 0.02 tail threshold is frozen now because it is scale-free, matches the primary
two-percentage-point materiality floor, and avoids inventing a raw-return cutoff before
the reward scale is defined.

In addition to a material benefit, **all** of the following are required:

- PPO's unsafe-dispatch point estimate does not exceed `B`'s.
- If either policy has an unsafe dispatch, the upper endpoint of the paired 95% bootstrap
  interval for `unsafe_rate_PPO - unsafe_rate_B` must be `<= 0`.
- The paired 95% bootstrap interval for the claimed improvement excludes zero in the
  favorable direction.
- The claim survives aggregation across the five PPO training seeds; one lucky seed is
  insufficient.

A statistically directional but sub-material change is reported as “detectable but not
material.” A material point estimate whose interval crosses zero is “inconclusive,” not
a win. Improving reward while increasing unsafe actions cannot support an RL contribution.

## 10. Pre-registered conclusion labels

| Conclusion | Evidence required |
| --- | --- |
| **YES — RL materially contributes** | The §9 gate passes on the combined, equal-weight LOW/MEDIUM/HIGH operational test result, with no uncertainty stratum showing a supported safety regression. |
| **MIXED — regime/tail-dependent contribution** | The combined gate does not pass, but §9 passes in a pre-registered uncertainty stratum or via the pre-registered tail criterion, with no safety regression. The qualifying and non-qualifying strata must both be named. |
| **NO — strong planning remains sufficient** | Neither YES nor MIXED conditions pass; or planners match/beat PPO; or any apparent PPO utility gain requires increased unsafe actions. |

Stress-only gains are evidence of robustness and may support `MIXED` only if the relevant
stress category was pre-registered and the same §9 materiality, interval, and safety rules
pass. They cannot be promoted to an unqualified YES.

## 11. Uncertainty strata

LOW, MEDIUM, and HIGH are frozen analysis strata. Their numeric severity noise, travel
variance, closure probability, shock persistence, and shelter-degradation parameters are
**not selected here**; Phase 4 must set and version them before planner/PPO results exist.
HIGH must remain plausible and cannot be exaggerated to favor learning.

Report every metric for each stratum and the equal-weight combined result. Policy ranking,
paired effects, confidence intervals, safety, and latency are shown by stratum. Strata are
never silently merged after inspecting which one favors PPO.

## 12. Robustness and stress categories

The separate frozen stress suite will contain:

- sudden flood surge outside the common training pattern;
- route-closure cascade;
- high-capacity shelter failure;
- demand/population distribution shift;
- longer travel-lag distribution.

Exact generators and severity levels are **to be fixed before experiment** in the suite
manifest. All policies receive the same paired stress units. Stress results remain
separate from in-distribution results and are reported category by category.

## 13. PPO training seeds and selection

The final result uses **five independent PPO training seeds**. Each seed is evaluated on
every frozen unit. Report each seed's metrics, mean and standard deviation across seeds,
the pooled per-unit mean across seeds, worst seed, and the two-level paired bootstrap from
§7. Checkpoints are selected using validation performance only under one frozen selection
rule established before training.

If compute failure prevents five completed seeds, three is the minimum reportable set.
Reducing from five requires a dated, pre-test-results amendment documenting runtime or
hardware evidence; it cannot be decided because the first seeds look unfavorable.

## 14. Demo-scenario firewall

The hand-built V1 demo scenario and any V3 presentation scenario derived from it:

- cannot select a checkpoint;
- cannot tune reward weights;
- cannot select features or hyperparameters;
- cannot choose a planner configuration or principal baseline;
- cannot determine whether PPO succeeds;
- cannot be included in validation or held-out test aggregates.

It is presentation-only. A visually attractive demo result cannot override the frozen
held-out conclusion.

## 15. Metric-change governance

After this commit, no primary metric, materiality threshold, principal-baseline rule, or
YES/NO/MIXED interpretation may be silently changed after observing V3 results.

If a rule proves mathematically invalid or materially misleading:

1. preserve this original text and the original result;
2. add a dated amendment with the defect, evidence, replacement, and commit;
3. make the amendment before rerunning or unblinding affected held-out results whenever
   possible;
4. report original and amended analyses side by side where computable;
5. label any post-result amendment exploratory.

Implementation-only clarifications may not change which policy wins. Reward and simulator
semantics marked “to be fixed before experiment” must be committed before results and are
not retroactive metric changes.

## 16. Explicit planning STOP condition

Before PPO, Gate 6A compares the strongest practical planner with the clairvoyant exact
upper bound on at least 100 tractable stochastic scenarios. Stop PPO implementation, or
retain it only as a non-contribution comparison, if the planner achieves:

```text
median per-unit h_exact >= 0.99
p10 per-unit h_exact    >= 0.97
p95 decision latency <= 100 ms on the recorded reference machine
no safety regression relative to other constrained baselines
```

The 100 ms limit is an absolute operational budget, not a multiple of an unusually fast
neural forward pass—the denominator mistake exposed by Gate 1A.5. Hardware, warm-up,
thread count, and number of decisions timed must be recorded. If Gate 6A passes, “a strong
planner essentially solves this formulation at acceptable latency” is the result; extra
complexity must not be invented merely to rescue an RL claim.

## 17. Latency protocol

Latency is measured after warm-up on one recorded reference machine and fixed software
environment. Use one process and a fixed thread configuration; run at least 1,000 timed
decisions per algorithm across representative states. Report median, mean, p90, p95, and
standard deviation. Model loading, scenario parsing, environment stepping, logging,
network calls, and dashboard rendering are excluded from decision latency and reported
separately if relevant. Planner sampling budgets are frozen on validation data.

## 18. Computability audit

| Required value | Planned source |
| --- | --- |
| initial/remaining/safe population | simulator population-conservation ledger |
| arrival time and status | dispatch event queue and arrival log |
| zone/transit hazard by timestep | hazard state plus route-state history |
| shelter status/capacity/reservations | shelter state and capacity ledger |
| route reachability/failure | route state and dispatch event log |
| unsafe rule IDs | hard-safety audit emitted with every action |
| executed/masked/rejected actions | action and mask audit log |
| travel person-minutes | departure/arrival/failure timestamps and group size |
| episode return | per-step reward-component ledger |
| decision latency | benchmark wrapper around policy action selection only |
| paired randomness provenance | scenario, replication, stream, policy, and training seeds |

Every required metric maps to planned simulator state or an explicit event ledger. The
open semantics listed in §4 are blocking decisions for their owning phases and must be
resolved before final experiment generation. No metric depends on retrospective
natural-language judgment.

## 19. Phase 1 acceptance checklist

- [x] Primary metric and both reference regimes defined.
- [x] Zero/near-zero denominator behavior defined.
- [x] Secondary metrics have computable formulas.
- [x] Safety events map to deterministic simulator state.
- [x] Paired RNG and reporting protocol defined.
- [x] Strong baseline hierarchy and principal comparator frozen.
- [x] RL materiality, uncertainty, tail, and safety gate frozen.
- [x] YES/NO/MIXED interpretations frozen.
- [x] Uncertainty strata and stress categories pre-registered without invented values.
- [x] Five PPO seeds pre-registered, with a constrained three-seed fallback.
- [x] Demo scenario isolated from scientific choices.
- [x] Metric-amendment governance and planner STOP condition recorded.
- [x] No V3 implementation or result was created in this phase.
