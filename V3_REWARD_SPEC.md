# Sentinel-Agent V3 — Frozen RL Reward Specification

> **Status: FROZEN IN PHASE 8A BEFORE REWARD IMPLEMENTATION OR PPO TRAINING.**
>
> Primary version: `v3-reward-balanced-v1`
>
> **Reward weights are synthetic project modeling choices frozen before PPO training.
> They are not official disaster-management utility weights.**

## 1. Scope and scientific firewall

This specification defines the undiscounted physical reward that a later learned policy
may optimize. Phase 8A contains no reward implementation or performance result. Phase 8B
may implement only these formulas and sanity-check their arithmetic; it may not train,
instantiate, tune, or evaluate PPO.

The Phase 6 Gate-6 planning utility is not reused. The RL reward contains no oracle,
lookahead, MPC, best-action, future-state, citation, or LLM term. It is independent of
discounting, GAE, reward normalization, clipping, optimizer, and training hyperparameters.

## 2. Frozen conventions

For one scenario:

```text
N0 = sum(zone.population_initial_remaining)
H  = horizon_steps
M  = timestep_minutes * H
```

Initial shelter occupants are not part of `N0`. Training scenarios must have `N0 > 0`.
The calculator remains finite for schema/test scenarios with `N0 = 0` by returning zero
for every population-normalized component; such an environment is not training-ready.
The V3 schema guarantees `H > 1` and positive timestep minutes.

One Gym step uses the existing simulator order:

1. process arrivals due at the current pre-step timestep;
2. realize current exogenous hazard, route, and shelter state;
3. calculate the public forecast;
4. execute the valid semantic action, or the Phase 7 masked-action WAIT fallback;
5. finalize the physical transition and terminal state;
6. calculate reward from the just-completed transition.

The calculator receives the prepared pre-action state, `TransitionResult`, finalized
post-action state, and immutable scenario. It is a pure deterministic function and
consumes no RNG.

## 3. Component A — newly safe population

Let `A_t` be the sum of people in `transition_result.arrivals_processed`. These are
scenario evacuees whose previously pending dispatches successfully arrive during this
transition:

```text
safe_gain_t = A_t / N0
```

For `N0 > 0`, `0 <= safe_gain_t <= 1` and episode `sum_t safe_gain_t <= 1` under frozen
population conservation. Dispatch creates no safe credit. People still traveling receive
no credit. Initial shelter occupants never appear in the dispatch-arrival ledger and
cannot produce reward.

Arrival timing follows the simulator. If a dispatch departs at timestep 0 and is due at
pre-step timestep 3, credit occurs on the transition beginning at timestep 3—not at
departure.

## 4. Component B — current zone exposure

Using the finalized post-action state, whose hazards are the current already-realized
values for the transition:

```text
raw_exposure_t = sum_z(
    post_action_population_remaining[z]
    * current_flood_severity[z]
)

exposure_t = raw_exposure_t / (N0 * H)
```

Dispatching during timestep `t` removes those people from zone exposure for that
timestep. In-transit exposure is deliberately not included in this reward component;
travel has its own smaller dispatch burden. Forecasts, next-timestep severity, future
closures, and oracle trajectories are never used.

Under frozen invariants, `0 <= exposure_t <= 1/H` and cumulative episode exposure is in
`[0,1]` because there are at most `H` accepted decision transitions and zone severity is
in `[0,1]`.

## 5. Component C — realized dispatch travel burden

When the executed transition creates no dispatch event:

```text
travel_burden_t = 0
```

For the one dispatch event created by a valid transition, let `P_t` be its people and
`T_t > 0` its just-realized travel duration in minutes:

```text
travel_ratio_t  = T_t / (T_t + M)
travel_burden_t = (P_t / N0) * travel_ratio_t
```

Actual travel is allowed here only after the dispatch has executed and the value has
become part of the physical transition. It is never exposed in the pre-action policy
observation. The current simulator permits at most one dispatch event per transition.
For `N0 > 0`, each evacuee dispatches at most once, so cumulative travel burden is
`< 1`. Very long finite travel approaches but never reaches a ratio of one.

## 6. Component D — terminal unfinished fraction

Only a transition ending in `HORIZON_REACHED` receives:

```text
terminal_unfinished_t =
    (post_state.population_remaining + post_state.people_in_transit) / N0
```

People still traveling at the horizon are unfinished. `ALL_EVACUATED` and every
nonterminal transition use zero. Under population conservation the component is in
`[0,1]`.

## 7. Primary reward

The frozen primary configuration is `v3-reward-balanced-v1`:

| Component | Weight | Direction |
| --- | ---: | --- |
| newly safe population | `0.55` | positive |
| current zone exposure | `0.30` | negative |
| realized travel burden | `0.05` | negative |
| terminal unfinished fraction | `0.10` | negative |

```text
r_t = + 0.55 * safe_gain_t
      - 0.30 * exposure_t
      - 0.05 * travel_burden_t
      - 0.10 * terminal_unfinished_t
```

Safe arrival carries the largest positive weight because completed evacuation is the
primary objective. Exposure has a substantial penalty to value earlier removal from
flooded zones. Travel is modest so efficiency cannot dominate completion. The terminal
term discourages late dispatches that remain in transit. These rationales and numbers are
project modeling choices, not measured emergency-management preferences.

WAIT has no fixed reward or penalty. Its physical consequences alone determine reward:
arrivals may occur, exposure continues, and the horizon approaches.

## 8. Frozen sensitivity configurations

These alternatives are pre-registered for later sensitivity analysis and are not
candidates from which Phase 8 or Phase 9 may select a more favorable headline result.

| Config ID | Safe | Exposure | Travel | Terminal | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `v3-reward-balanced-v1` | `0.55` | `0.30` | `0.05` | `0.10` | **Primary**, balanced completion/exposure |
| `v3-reward-evacuation-v1` | `0.65` | `0.20` | `0.05` | `0.10` | More completed-arrival emphasis |
| `v3-reward-exposure-v1` | `0.50` | `0.40` | `0.05` | `0.05` | More rapid exposure-reduction emphasis |

All weights are nonnegative and sum to one within each configuration. The primary remains
balanced unless a mathematical defect is documented before PPO training. Later work must
report whether policy conclusions change across the two sensitivity configurations; it
must not promote whichever configuration makes PPO look strongest.

## 9. Safety and invalid-action separation

Reward contains no `0.70` branch, unsafe-dispatch penalty, destination-hazard cutoff,
closed-route penalty, or other Phase 5 rule. Safety ON prevents unsafe execution through
the action mask. Safety OFF may execute a high-destination-hazard action, and reward uses
only ordinary arrival, zone exposure, travel, and terminal outcomes. Unsafe-dispatch rate
remains an evaluation metric rather than a hidden objective.

A masked integer request converted to WAIT receives exactly the reward of the executed
WAIT transition. There is no invalid-attempt penalty. The diagnostic remains in Gym info.

## 10. No subgroup reward

Vulnerable and medical-priority counts receive no separate weight because the simulator
does not track which subgroup members dispatch, remain, or arrive. Adding such a term now
would invent movement. Subgroup-aware state, actions, and reward remain deferred.

## 11. Pending-arrival partial observability audit

Safe-arrival credit is delayed until a scheduled arrival actually processes. The Phase 7
feed-forward PPO observation exposes total in-transit population and shelter reservations
but not individual arrival countdowns. PPO therefore faces an intentional partially
observable sequential problem and may receive delayed arrival reward without seeing the
exact pending-event schedule. Phase 8 does not add countdown features or recurrent PPO.

The requested claim that pending timing is hidden from both PPO and practical planners
cannot be made literally: the frozen Phase 6 `PlannerInput` includes observable pending
dispatch metadata, including arrival timestep and lag, while `V3_ENV_SPEC.md` explicitly
records that PPO has aggregates only. This is a planner information advantage and must be
disclosed in later comparison. Phase 8 preserves both committed boundaries rather than
silently changing either to manufacture parity.

## 12. Theoretical component and return ranges

For `N0 > 0`, the frozen simulator invariants and at most `H` accepted transitions imply:

```text
0 <= episode sum safe_gain             <= 1
0 <= episode sum exposure              <= 1
0 <= episode sum travel_burden          < 1
0 <= terminal unfinished               <= 1
```

Conservative undiscounted episode-return ranges are therefore:

| Config | R_min | R_max | Width |
| --- | ---: | ---: | ---: |
| balanced | `-0.45` | `0.55` | `1.00` |
| evacuation | `-0.35` | `0.65` | `1.00` |
| exposure | `-0.50` | `0.50` | `1.00` |

The lower endpoints conservatively add all negative component maxima even where joint
attainment may be impossible; the travel maximum is a strict supremum. The upper endpoint
assumes all population receives arrival credit and no penalty. Under the primary range,
Phase 1's one-percent normalization cutoff is `epsilon_den = 0.01`.

These bounds depend on frozen population conservation, severity bounds, one-time
dispatch of each evacuee, positive finite travel, and episode length at most `H`. A future
change allowing redispatch, population creation, more than `H` reward transitions, or
unbounded travel semantics requires a dated pre-results reward-spec amendment.

## 13. Provider, breakdown, and training readiness

Phase 8B will add an immutable versioned `RewardConfig`, pure `RewardProvider`, and
serializable `RewardBreakdown` containing:

```text
safe_gain
exposure
travel_burden
terminal_unfinished
weighted_safe
weighted_exposure
weighted_travel
weighted_terminal
total_reward
reward_config_id
```

Gym returns `float(total_reward)` and exposes the breakdown only in debug/evaluation
`info`, never in the observation.

Placeholder construction retains `PHASE7_PLACEHOLDER_ZERO`, `reward_defined=False`, and
`training_ready=False`. A caller must explicitly supply a recognized frozen provider for
a positive-population scenario before `training_ready=True`. `assert_training_ready()`
must also verify the safety configuration and frozen Gym spaces. Zero-population scenarios
remain calculable but cannot pass readiness.

## 14. Sanity and amendment governance

Phase 8B must verify deterministic micro-cases: successful versus doing nothing, earlier
versus later equivalent evacuation, short versus long travel, arrived versus in transit
at horizon, consequence-only WAIT, and arrival-time credit. It must also record component
and return ranges across 200 fixed scripted/random-valid synthetic episodes balanced as
closely as possible across LOW/MEDIUM/HIGH. These runs are arithmetic sanity checks, not
policy performance or reward-weight selection.

Weights may change only for a formula defect, impossible sign, invalid normalization, or
numerical instability, with a dated amendment committed before training. They may not be
optimized against planners, oracles, anticipated PPO behavior, or later learned results.

## 15. Explicit exclusions and limitations

- no PPO/MaskablePPO construction, gradient update, checkpoint, or neural evaluation;
- no discount factor, GAE parameter, optimizer, reward wrapper, adaptive scaling, or
  clipping;
- no vulnerability/medical weighting or subgroup movement;
- no safety-threshold or invalid-action penalty in reward;
- no planner dependency or future-state access;
- baseline feed-forward PPO remains partially observable and has less pending-arrival
  detail than frozen practical planners;
- all scenarios and reward weights used for sanity are synthetic modeling choices;
- no RAG, Gemini, geospatial, dashboard, recurrent, graph-policy, or held-out work.

