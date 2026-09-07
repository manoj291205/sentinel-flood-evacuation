# Sentinel-Agent V3 — Deterministic Safety Specification

> **Status: FROZEN IN PHASE 5 BEFORE V3 PLANNER OR PPO RESULTS.**
>
> Phase 5 safety thresholds are synthetic modeling assumptions unless explicitly
> documented otherwise. They are not official NDMA flood-safety cutoffs.

## 1. Scope and configuration

This specification defines the deterministic action-safety layer used by later V3
planners and action masks. It uses only the current decision state, contains no random
draw, model call, retrieval, or network access, and does not modify the simulator.

The frozen configuration is `v3-safety-v1` (version 1):

| Parameter | Frozen value | Semantics | Provenance |
| --- | ---: | --- | --- |
| `max_destination_hazard` | `0.70` | A destination is hard-safety compliant only when its current normalized severity is strictly `< 0.70`. Equality fails. | Synthetic project modeling threshold reused from the V1 training proxy for continuity; not an official NDMA cutoff. |

The value was frozen before Phase 6 planners exist and must not be tuned against future
planner or PPO results. No other configurable safety knob exists in version 1.

## 2. Three distinct layers

### Layer A — simulator mechanical validity

`src.sim.transition.validate_action` is the sole authority for whether an action can
physically/logistically execute. Phase 5 consults that result and translates it into a
structured audit verdict; it does not reimplement the checks.

| Simulator rejection code | Meaning | Provenance |
| --- | --- | --- |
| `EPISODE_TERMINAL` | No action, including WAIT, executes after termination. | Simulator mechanic |
| `INVALID_ACTION_TYPE` | The value is not a supported semantic action. | Simulator mechanic |
| `UNKNOWN_ZONE`, `UNKNOWN_SHELTER` | An action references an unknown entity. | Simulator mechanic |
| `NO_ROUTE`, `AMBIGUOUS_ROUTE`, `ROUTE_UNREACHABLE` | The route relation cannot currently execute. A stochastic closure is represented by current unreachability. | Simulator mechanic |
| `INVALID_TRAVEL_TIME` | A reachable route lacks a positive finite current travel time. | Simulator mechanic |
| `NO_POPULATION` | The source has no evacuees remaining. | Simulator mechanic |
| `SHELTER_CLOSED` | The destination cannot accept new dispatches. | Simulator mechanic |
| `NO_CAPACITY` | Available capacity is zero. | Simulator mechanic |
| `EVACUATION_DISABLED`, `NO_DISPATCH_AVAILABILITY` | No fleet dispatch can currently execute. | Simulator mechanic |

Positive capacity smaller than vehicle capacity remains valid. The simulator dispatches
`min(vehicle capacity, remaining source population, available destination capacity)`, so
20 available places permit a 20-person partial dispatch rather than requiring a full
50-person batch.

### Layer B — Phase 5 deterministic hard safety

The initial rule registry is deliberately minimal:

| Rule ID | Exact semantics | Inputs | Origin |
| --- | --- | --- | --- |
| `SAFETY_DESTINATION_HAZARD` | For a mechanically valid dispatch, pass iff `current destination shelter flood severity < max_destination_hazard`. Severity equal to or greater than the limit fails. | Action destination shelter ID; current destination severity; `v3-safety-v1.max_destination_hazard` | `SYNTHETIC_SAFETY_RULE` |

The rule does not use a forecast, future flood draw, future closure, future shelter
degradation, unrealized travel time, private random key, or hidden regional state.

No separate capacity, route, source-population, fleet, or CLOSED-shelter safety rule is
created because those are already authoritative simulator mechanics.

### Layer C — evidence-grounded document policy

No `DOCUMENT_POLICY` rule is active in Phase 5. NDMA retrieval, citations, Gemini
interpretation, and natural-language policy remain deferred to Phase 15. Phase 5 reason
strings explain deterministic code and are not evidence citations.

## 3. Status, horizon, and arrival semantics

- `OPEN` is mechanically usable and is governed by the current destination-hazard rule.
- `RESTRICTED` remains mechanically usable. It is not excluded merely because of its
  label; current destination severity may independently exclude it.
- `CLOSED` blocks new dispatches as a simulator mechanic.
- Phase 5 adds no “arrival before deadline” predicate. The existing simulator horizon
  semantics remain authoritative: a dispatch may be mechanically accepted even when its
  arrival is beyond the horizon, and pending people remain in transit at horizon
  termination.
- An existing reservation remains valid if its route or destination later closes.
- Phase 4 does not reduce numeric shelter capacity. If that changes in a future phase,
  post-dispatch capacity-loss classification must be separately specified before use.
- People counted safely arrived remain in the safe-arrival ledger if their destination
  later degrades; Phase 5 does not revoke past safe status.

## 4. Action enumeration and masks

The canonical semantic order is the Cartesian product of Phase 2 canonical zones and
canonical shelters, zone-major and shelter-minor, followed by `WAIT`:

```text
for zone in scenario.canonical_zones:
    for shelter in scenario.canonical_shelters:
        DispatchAction(zone, shelter)
WAIT
```

Every `SafetySnapshot` stores the action tuple, Boolean mask, and structured evaluation
tuple together and rejects misaligned lengths/order. No integer RL action IDs are assigned
in Phase 5.

The mask is recomputed from the current state at every decision timestep. It is not
cached across hazard, route, status, population, reservation, capacity, arrival, or
terminal changes.

## 5. WAIT and terminal behavior

WAIT passes hard safety and is mechanically executable in every nonterminal state. It
therefore prevents an empty final action set when all dispatches are mechanically invalid
or hard-safety excluded. In a terminal state, simulator validation rejects every action,
including WAIT, with `EPISODE_TERMINAL`; a terminal mask is consequently all false.

## 6. Safety enabled and disabled

With `enable_hard_safety=True`, an action is finally allowed only when simulator mechanics
pass and every Phase 5 hard-safety rule passes.

With `enable_hard_safety=False`, simulator mechanics still apply. A mechanically possible
high-hazard dispatch becomes finally allowed, while closed routes, zero capacity, CLOSED
shelters, empty sources, invalid identifiers, and terminal actions remain excluded. The
hard-safety verdict is still computed and stored with `enforced=false`, preserving the
frozen unsafe label for the later safety-OFF ablation without blocking the action.

## 7. Unsafe-dispatch mapping to the Phase 1 evaluation plan

An executed non-WAIT dispatch is classified unsafe when at least one frozen Phase 5
`HARD_SAFETY` predicate failed at its decision timestep. In `v3-safety-v1`, this means
the current destination severity was `>= 0.70`. Safety-OFF bypasses enforcement but not
classification.

Mechanical impossibilities are normally rejected and therefore are not executed-dispatch
denominator events. Attempts and rejections retain mechanical rule IDs as diagnostics.
Phase 1's “sufficient unreserved capacity for the batch” is interpreted using the actual
Phase 3 partial batch: any positive available capacity is sufficient for the smaller
executable dispatch. This preserves the frozen simulator rather than silently changing
it into a full-vehicle requirement.

## 8. Audit and provenance contract

Every rule verdict records:

- rule ID and layer;
- `SIMULATOR_MECHANIC` or `SYNTHETIC_SAFETY_RULE` provenance;
- pass/fail and whether it is enforced;
- machine-readable reason code and human-readable reason;
- relevant current values;
- simulator-mechanics or safety configuration version.

Every false mask entry has at least one failed, enforced exclusion. A safety snapshot is
JSON serializable and includes no future outcome or random-stream metadata.

## 9. Purity and limitations

Evaluation is a pure read-only function of `(scenario, current runtime state, safety
config, enabled flag)`. It does not mutate scenario/state, append audits, change event or
reservation ledgers, consume RNG, or alter subsequent stochastic outcomes.

Known limitations intentionally retained after Phase 5:

- one synthetic hard-safety rule only;
- no document-backed dynamic policy rule or evidence;
- no route-edge/geospatial flood rule; route mechanics still use the endpoint proxy;
- no arrival-deadline safety rule;
- no planner, reward, V3 Gymnasium environment, PPO, human override, dashboard change,
  or final safety-effectiveness evaluation.
