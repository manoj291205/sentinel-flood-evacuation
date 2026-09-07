# Sentinel-Agent V3 — Fixed-Dimension Gymnasium Environment Specification

> **Status: FROZEN IN PHASE 7 BEFORE ENVIRONMENT IMPLEMENTATION.**
>
> Version: `v3-env-v1` · Gymnasium: `1.3.0` · Stable-Baselines3: `2.9.0`
> · sb3-contrib: `2.9.0`

## 1. Scope and training firewall

Phase 7 wraps the already validated V3 stochastic simulator in a fixed-dimensional
Gymnasium API. It does not change simulator physics, safety rules, scenario generation,
or the Phase 1 evaluation plan. It does not train or instantiate PPO/MaskablePPO.

The only Phase 7 reward is the API-required zero placeholder identified by
`PHASE7_PLACEHOLDER_ZERO`. It has no research meaning. The environment exposes
`training_ready = False` and **MUST NOT be used for PPO training until Phase 8 freezes
and integrates the V3 reward specification.**

## 2. Fixed envelope and why it is mandatory

`v3-env-v1` fixes:

```text
MAX_ZONES = 6
MAX_SHELTERS = 9
dispatch slots = 6 * 9 = 54
WAIT_INDEX = 54
action space = Discrete(55)
```

Standard MLP policies and MaskablePPO require one stable observation and action space.
A policy cannot alternate among `Discrete(21)`, `Discrete(36)`, and `Discrete(55)` as
scenario size changes. Every valid V3 episode therefore exposes `Discrete(55)` and the
same 384-element observation. Nonexistent entity combinations are padding and are
masked. Scenarios with more than six zones or nine shelters fail loudly; nothing is
silently truncated. Gate 6 uses at most four zones and five shelters, so this envelope is
compatible with the existing generator without expanding for hypothetical future scale.
Because one fixed route slot represents one zone-shelter relation, a scenario with
multiple route IDs for the same pair also fails loudly rather than hiding an ambiguous
choice.

## 3. Canonical slots and integer actions

Zones are sorted by `zone_id` and shelters by `shelter_id`, independent of JSON order.
Real entities occupy the leading slots and remaining slots are absent padding. The
environment retains public audit maps from slot to ID; textual IDs are not numeric policy
features.

For a real dispatch pair:

```text
index = zone_slot * MAX_SHELTERS + shelter_slot
```

Indices `0..53` are possible dispatch slots and index `54` is always WAIT. Encoding and
decoding round-trip exactly. A padded slot or real pair with no route has no executable
dispatch semantic and is masked false. WAIT is true in every nonterminal mask. Once an
episode is done, all 55 mask values, including WAIT, are false.

## 4. Fixed observation

The observation is a flat `numpy.float32` vector in a `Box(0.0, 1.0, (384,))`. Feature
groups are concatenated in this order:

```text
6 zones * 6 features       = 36
9 shelters * 8 features   = 72
54 routes * 5 features    = 270
6 global features         = 6
total                     = 384
```

### Zone slot — 6 features

1. presence
2. `population_remaining / initial_population_total_for_zone` (zero if total is zero)
3. current flood severity
4. normalized recent trend: `clip((current - previous + 1) / 2, 0, 1)` using the
   public observed severity change; an observed zero change maps to `0.5`
5. public next-step forecast mean
6. public forecast uncertainty transformed as `u / (u + 1)` for finite `u >= 0`

Subgroup counts are omitted because the simulator moves undifferentiated people and does
not track dynamic vulnerable or medical populations.

### Shelter slot — 8 features

1. presence
2. available capacity / total capacity
3. occupied capacity / total capacity
4. reserved capacity / total capacity
5. current flood severity
6. OPEN indicator
7. RESTRICTED indicator
8. CLOSED indicator

Zero-capacity shelters use zero capacity fractions. Status is categorical one-hot, not
ordinal.

### Zone–shelter route slot — 5 features

1. route presence
2. current reachability
3. expected travel time normalized as `m / (m + horizon_minutes)`
4. travel uncertainty normalized as `u / (u + horizon_minutes)`
5. estimated closure probability

`horizon_minutes = timestep_minutes * horizon_steps`. For absent or currently
unreachable routes, the non-presence/reachability values are zero. No realized future
travel time or future closure outcome is exposed.

### Global — 6 features

1. `current_timestep / horizon_steps`
2. total remaining population / initial evacuation population
3. people in transit / initial evacuation population
4. people safely arrived / initial evacuation population
5. `vehicle_capacity / (vehicle_capacity + initial_evacuation_population)`
6. whether at least one dispatch is currently allowed by the configured Phase 5 mask

Initial shelter occupants are not evacuation population. Remaining, transit, and safe
fractions sum to one within floating precision when initial evacuation population is
positive; all three are zero for a valid zero-population scenario. The finite timestep is
visible for Markov adequacy. Literal uncertainty-stratum labels, algorithm identity,
scenario/root seeds, and replication IDs are absent.

## 5. Padding and numeric safety

Each entity group begins with a presence bit so a physical zero differs from absence.
For every absent zone, shelter, or route slot, presence and all other features are zero.
Observation arrays are newly built on every reset/step, so a large-to-small reset cannot
retain stale values. Invalid denominators, missing values, NaN, or infinity raise a clear
observation error for a purportedly valid public state; defined zero-denominator cases
use the formulas above. Values are validated against `[0,1]` rather than silently hiding
material out-of-range public data.

## 6. Scenario source and reset/replication semantics

The environment accepts a scenario source; Phase 7 provides `FixedScenarioSource` and a
callable adapter without defining a Phase 9 training distribution. Every supplied
`ScenarioV3` is schema-validated already and is checked against the 6×9 envelope.

`reset(seed=s)` calls `super().reset(seed=s)`. A supplied nonnegative Gym seed maps
directly to the Phase 4 stochastic `replication_id = s`; the scenario's configured root
seed is unchanged. When no seed is supplied, reset uses a private monotonically
increasing episode replication counter starting at zero. Gymnasium's mutable `np_random`
does not generate environmental dynamics. Therefore the same scenario, reset seed, and
integer action sequence reproduce observations, masks, requested/executed semantics,
physical state, audit events, and termination exactly; different reset seeds normally
produce different outcomes in a sufficiently stochastic trajectory.

Policy-facing reset/step info omits both replication ID and root seed. Reset info includes
scenario ID, environment config ID, counts, slot maps, allowed-action count, safety
config, and placeholder-reward status.

## 7. Masks and hard safety

`action_masks()` returns a copied Boolean NumPy array with shape `(55,)`. For each real
dispatch semantic it uses the corresponding `final_allowed` value from the canonical
Phase 5 `evaluate_actions` snapshot. The environment does not recreate mechanical or
safety predicates. Padding and route-absent pairs are false. WAIT uses the Phase 5 WAIT
result.

With hard safety on, mechanics and `v3-safety-v1` are enforced. With hard safety off,
Phase 5 continues to evaluate and label its synthetic hazard rule but does not enforce
it; mechanics, route existence/reachability, capacity, fleet, padding, and terminal state
remain mandatory.

## 8. Step, invalid fallback, and episode end

The wrapper decodes a valid integer and delegates the executed semantic action to
`StochasticSimulator.step`; it owns no transition physics. Out-of-range or non-integral
actions raise `ValueError`.

An in-range but masked request is converted to semantic WAIT before simulator execution.
Time advances normally, the requested dispatch never executes, no Phase 7 penalty is
invented, and info records `invalid_action_attempted`, requested and executed semantics,
and cumulative invalid-attempt count. This defensive path keeps Gym checkers safe and
cannot bypass mechanics or hard safety. It does not alter the simulator's own
transactional rejection behavior.

Terminal mapping is fixed:

```text
ALL_EVACUATED   -> terminated=True,  truncated=False
HORIZON_REACHED -> terminated=False, truncated=True
```

Both flags are never true for a normal end. Calling `step()` after either flag raises
`RuntimeError`; the environment never silently auto-resets.

## 9. Placeholder reward and future injection boundary

`ZeroPlaceholderReward` is the sole Phase 7 reward provider and returns exactly `0.0`
for every transition. The environment exposes:

```text
reward_spec_version = PHASE7_PLACEHOLDER_ZERO
training_ready = False
```

Every info dictionary contains `reward_defined=False` and the same version. The provider
boundary exists solely so Phase 8 can replace it cleanly after its own pre-results
specification. Phase 7 includes no safe-population, exposure, travel, invalid-action, or
terminal reward component.

## 10. Information boundary and planner parity

Dynamic features are derived from `EpisodeState.to_policy_observation()` or its detached
`StochasticSimulator.observe()` result. The wrapper never reads hidden regional state,
future keyed outcomes, oracle futures, Gate 6 scores, or planner internals for policy
features.

| Information | Practical planners | PPO observation |
| --- | --- | --- |
| current zone/shelter severity | yes | yes |
| recent observed severity change | yes | yes, normalized |
| next-step public forecast mean/uncertainty | yes | yes, normalized |
| remaining population | yes | yes, normalized |
| occupancy/reservations/available capacity | yes | yes, normalized |
| current shelter status | yes | yes, one-hot |
| expected travel/travel uncertainty | yes | yes, normalized |
| current reachability/closure probability | yes | yes |
| timestep/horizon and vehicle capacity | yes | yes, normalized |
| current safety-allowed dispatch existence | yes | yes |
| literal LOW/MEDIUM/HIGH label or raw config | yes | no; observable quantities remain |
| pending-arrival details | yes | aggregate in-transit only; fixed flat Phase 7 design |
| exact future closure/travel/hazard | no | no |
| environment root seed/replication ID | no | no |
| Gate 6 utility, oracle, or best action | no | no |

The flat vector contains the essential current decision quantities used by practical
planners without adding private outcomes. Pending dispatch details are not individually
encoded in Phase 7; current reservations and aggregate transit expose their immediate
resource consequences. This limitation should be revisited only through a future
pre-results observation amendment if Markov adequacy requires an arrival-queue encoding.

Evaluation/debug info may include current physical counts and current transition audit
events, but future training code must never feed info into the policy.

## 11. Deferred work and known limitations

- no real PPO/MaskablePPO training and no Phase 8 reward;
- fixed maximum 6×9 slots and a standard flat MLP-style observation;
- no recurrent policy, graph network, or subgroup-specific dispatch action;
- no per-dispatch pending-arrival queue in the numeric observation;
- canonical slots can become shortcuts if a future generator correlates IDs with
  attributes—Phase 9 must randomize attributes and run slot/entity permutation
  diagnostics and evaluation under permuted slot identity;
- no geospatial route graph, RAG/Gemini changes, dashboard work, human override, or final
  held-out evaluation.
