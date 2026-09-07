# Sentinel-Agent V3 — Planner and Gate 6 Specification

> **Status: FROZEN IN STAGE 6A BEFORE COMPARATIVE PLANNER RESULTS.**
>
> Version: `v3-planner-spec-v1` · Generator: `v3-gate6-generator-v1`

## 1. Question and scientific firewall

Gate 6 asks whether cheap non-clairvoyant planning already captures essentially all
available clairvoyant headroom in the V3 stochastic sequential problem. Stage 6B must
implement this specification without tuning definitions, weights, depths, samples,
scenario distributions, or thresholds after results are observed.

The Phase 5 observation that only 1 of 4,320 sanity candidates was excluded solely by
hard safety is retained as a diagnostic. It does not change the frozen `0.70` safety
threshold and does not justify changing the generator to make safety look stronger.

Phase 6 contains no PPO, MaskablePPO, Gymnasium environment, RL training reward, neural
network, RAG/Gemini change, geospatial routing, dashboard work, human override, or final
held-out evaluation.

## 2. GATE-6 PLANNING UTILITY

Phase 1 froze normalization but left raw scalar episode return for Phase 8. Gate 6
therefore freezes this separate bounded diagnostic utility before planner results:

```text
S = safely_arrived_population / P0
E = exposed_person_timesteps / (P0 * H)
T = in_transit_person_timesteps / (P0 * H)

G6U = 0.70*S - 0.25*E - 0.05*T
```

`P0` is initial evacuation population and `H` is the number of decision timesteps.
Exposure is accumulated before each action over people not yet safe:

```text
sum(zone population_remaining * current zone severity)
+ sum(in-transit people * current route endpoint hazard proxy)
```

The route proxy is the existing Phase 4 maximum of current source and destination
severity. `T` counts pending people once per decision timestep. Thus `S`, `E`, and `T`
are in `[0,1]`, and `G6U` is bounded by `[-0.30, 0.70]`. Hard safety is enforced before
utility optimization, making safety lexically dominant; utility never trades an unsafe
dispatch for score. The weights prioritize safe arrival, then exposure, then travel and
were selected for transparent scale separation—not for planner performance.

This is the **GATE-6 PLANNING UTILITY**, not the future PPO training reward. Phase 8 must
still define `V3_REWARD_SPEC.md` independently.

## 3. NSU-exact and validity

For exact unit `i`, let `O(i)` be clairvoyant-oracle `G6U` and `L(i)` the arithmetic mean
of five `random_valid` runs using policy seeds `73001..73005` on the same paired unit:

```text
h_p(i) = (G6U_p(i) - L(i)) / (O(i) - L(i))
```

The utility range is `1.00`, so Phase 1's one-percent cutoff is
`epsilon_den = 0.01`. Units with `O-L <= 0.01` have undefined per-unit headroom and are
reported `NA`; they remain in raw physical summaries. More than 5% invalid or timed-out
exact units makes the gate `INCONCLUSIVE_GATE`. Values are not clipped. A practical
planner above the exact oracle by more than `1e-9` is a correctness failure.

Gate summaries report median, p10, and mean of valid `h_p(i)`, calling the statistic
**NSU-exact headroom capture**, never “percent exactly optimal.” Aggregate Phase 1
ratio-of-means may be reported separately and may not replace the STOP statistic.

## 4. Practical planner input boundary

Every practical planner receives one immutable `PlannerInput` containing:

- scenario ID, timestep, timestep minutes, horizon, and vehicle capacity;
- a detached `EpisodeState.to_policy_observation()` value;
- the current Phase 5 `SafetySnapshot` with hard safety ON;
- the public LOW/MEDIUM/HIGH uncertainty configuration.

`PlannerInput` deliberately omits `ScenarioV3.seed`, replication ID, simulator object,
private stochastic context, regional latent state, random stream, audit log, realized
future values, and any future schedule. It is the same conceptual information boundary
intended for a future policy. Practical planner APIs have no oracle-context parameter.

Each call returns a `PlannerDecision` with semantic action, planner name/version,
high-resolution decision latency, stable candidate score records where applicable, and
node/model-transition counts. Action selection must not mutate the input or simulator.

## 5. Common action and tie rules

All planners consume Phase 5 canonical semantic actions. Every main Gate 6 practical run
uses `v3-safety-v1` with hard safety ON. WAIT is chosen by deterministic planners only
when no dispatch is allowed, except `random_valid` as specified below. Equal deterministic
scores select the earliest action in canonical order. No set iteration or dictionary
insertion order determines a tie.

## 6. Frozen practical planners

### 6.1 `random_valid-v1`

Phase 1 says random valid samples uniformly from the current valid-action mask. Therefore
this baseline samples uniformly from **all** safety-allowed canonical actions, including
WAIT even when a dispatch exists. Sampling uses a planner-owned `random.Random` instance;
its policy seed is recorded and never shared with environment randomness.

### 6.2 `nearest-safe-v1`

Among source zones with at least one allowed dispatch, select the greatest current zone
severity. Ties use canonical zone order. For that source, select the allowed destination
with the smallest current expected route travel time; ties use canonical action order.
WAIT is selected only when no dispatch is allowed.

### 6.3 `risk-greedy-v1`

For each allowed dispatch, compute six `[0,1]` components; higher is always better:

| Component | Definition | Weight | Rationale |
| --- | --- | ---: | --- |
| source urgency | current source severity | `0.30` | prioritize currently exposed sources |
| destination safety | `1 - current destination severity` | `0.20` | prefer lower current receiving risk |
| capacity usefulness | `min(vehicle capacity, source remaining, available capacity) / vehicle capacity` | `0.25` | value useful safe movement while retaining partial dispatches |
| travel | `1 - min(expected travel / total horizon minutes, 1)` | `0.10` | prefer shorter expected movement |
| closure safety | `1 - estimated closure probability` | `0.10` | avoid currently estimated route risk |
| travel certainty | `1 - min(travel uncertainty / expected travel, 1)` | `0.05` | mildly prefer predictable travel |

The weighted sum uses exactly these weights, which sum to 1. Candidate diagnostics expose
every component and total. Canonical order breaks exact ties. WAIT is used only when no
dispatch is allowed.

### 6.4 Expected planning model

`lookahead_k2` and `lookahead_k3` use a separate deterministic expected model constructed
only from `PlannerInput`; they never clone the real stochastic simulator.

For each modeled step it:

1. processes modeled arrivals due at the current timestep;
2. uses current safety rules/mechanics to enumerate modeled actions;
3. applies an action with batch size `min(vehicle capacity, source remaining, available
   capacity)` and arrival lag `ceil(expected travel / timestep minutes)`;
4. advances one timestep;
5. sets each next severity to its exposed `forecast_mean_next`; later projected steps
   continue the most recently observable change, clipped to `[0,1]`;
6. keeps currently reachable routes reachable and currently closed routes closed; route
   closure probability remains a score/risk input rather than a clairvoyant binary draw;
7. keeps current shelter status fixed in deterministic expected rollouts.

Projected expected travel and closure probability are recomputed from public configuration
and projected endpoint severity. No actual future draw is read.

At a depth leaf, the G6U estimate uses accumulated modeled exposure/travel plus a frozen
terminal estimate: pending groups arriving by the real episode horizon receive safe-arrival
credit; other remaining people do not. For unsearched remaining timesteps, current leaf
severity and scheduled pending arrivals are propagated without choosing more dispatches.

### 6.5 `lookahead-k2-v1`

Exhaustively evaluate all allowed semantic action sequences to exactly two actions, or to
terminal state if earlier. Select the first action of the highest leaf estimate. No beam
pruning is used. Report model transitions/nodes.

### 6.6 `lookahead-k3-v1`

The same expected model and leaf rule, with depth exactly three. No adaptive depth or
beam pruning is used. Report model transitions/nodes.

### 6.7 `sampled-mpc-n16-h3-v1`

For each currently allowed first action, generate `N=16` hypothetical futures for horizon
`H=3`, execute only the first action, and replan on the next real timestep. After the
candidate first action, each sample uses `risk-greedy-v1` for the remaining two modeled
actions. Candidate score is arithmetic mean G6U leaf estimate across 16 samples; there is
no CVaR or risk penalty.

Sampled model hazard innovations, travel, closures, and shelter degradation follow the
public Phase 4 equations/configuration. Planner-owned samples use SHA-256 keys over:

```text
planner RNG version, planner master seed 76001, public scenario ID,
current timestep, candidate action key, sample index, modeled step, event namespace
```

They never include or inspect environment root seed, replication ID, stream object, or
future outcome key. Identical public input and planner seed must reproduce actions and
scores byte-for-byte; changing hidden environment futures may not change them.

## 7. Clairvoyant exact oracle

`clairvoyant-oracle-small-v1` is labeled **CLAIRVOYANT UPPER BOUND — NOT A PRACTICAL
POLICY**. It has a separate API accepting an explicit oracle context containing a cloneable
real simulator. It exhaustively branches over every Phase 5-allowed action at each future
decision, using actual keyed hazard, closure, degradation, and action-conditioned travel
realizations. It executes normal simulator transitions, reservations, partial batches,
arrivals, horizon rules, and hard safety; it cannot teleport people or bypass mechanics.

No heuristic pruning is permitted. Exact canonical tie-breaking selects the earliest
equal-utility sequence. Per unit it records states expanded, branches evaluated, and
elapsed wall time. A monotonic five-second deadline is checked during search. A timed-out
unit is not used for exact normalization; timeout rate above 5% makes the gate
inconclusive. Exactness is validated first on hand-solvable tiny deterministic cases and
by asserting the oracle is not below any tested practical trajectory on completed units.

## 8. Frozen synthetic generator

All generated entities are explicitly `SIMULATED` or `FICTIONAL`. Python's local
`random.Random(generator_seed)` generates static scenario values. A SHA-256-derived
episode root seed under a separate `environment-root-v1` namespace drives Phase 4, so
generator draws and episode stochastic draws are separate.

Common independent distributions:

| Attribute | Frozen distribution |
| --- | --- |
| zone population | discrete uniform `[20,60]` exact; `[40,120]` practical |
| vulnerable count | floor(population × uniform `[0.10,0.35]`) |
| medical count | floor(population × uniform `[0.05,0.20]`) |
| zone severity | uniform `[0.15,0.85]`, rounded to 6 decimals |
| trend | uniform categorical `RISING, STEADY, FALLING` |
| shelter capacity | discrete uniform `[50,100]` exact; `[100,260]` practical |
| initial occupancy | floor(capacity × uniform `[0.00,0.35]`) |
| shelter severity | uniform `[0.05,0.82]`, rounded to 6 decimals |
| shelter status | OPEN `0.80`, RESTRICTED `0.15`, CLOSED `0.05` |
| accessibility | uniform `[0.40,1.00]`, rounded to 6 decimals |
| route reachable | Bernoulli `0.85` independently |
| reachable travel mean | uniform `[5,25]` minutes exact; `[5,40]` practical |
| travel standard deviation | mean × uniform `[0.05,0.25]` |
| base closure probability | uniform `[0.01,0.12]` |
| fleet | enabled; 3 vehicles; capacity 20; one dispatch/timestep |

Unreachable routes carry null travel/closure values. Every zone-shelter pair has exactly
one route. Rejection sampling accepts the first attempt satisfying schema validation,
positive total population/capacity, and at least one mechanically reachable,
hard-safety-allowed dispatch at `t=0`; maximum 100 attempts, then generation fails loudly.
No future outcome or planner result participates in acceptance.

## 9. Frozen Gate 6 suites

### Exact suite

- 120 scenarios: generator seeds `610000..610119`.
- Exactly 2 zones, 2 shelters, and 5 decision timesteps.
- Seeds `610000..610039`: LOW; `610040..610079`: MEDIUM;
  `610080..610119`: HIGH.
- One environment replication, ID `0`, per scenario/config.
- Five random-valid policy seeds per unit define `L(i)`.

### Practical-size diagnostic suite

- 120 scenarios: generator seeds `620000..620119`.
- Exactly 4 zones, 5 shelters, and 10 decision timesteps.
- Forty scenarios each for LOW/MEDIUM/HIGH in the same contiguous ordering.
- One environment replication, ID `0`, per scenario/config.
- No oracle and no `NSU-exact` claim.

Both suite manifests store generator version, seed, structure, uncertainty config, and
replication ID. These balanced strata are experimental design, not real-world prevalence.

## 10. Pairing, metrics, and diagnostics

Each planner receives the same scenario/config/replication unit. Phase 4 keyed randomness
therefore supplies the same exogenous world; planner-specific RNG never advances an
environment cursor. Main runs record G6U, safe population fraction, completion, exposed
person-timesteps, in-transit person-minutes, unsafe dispatch count/rate, and route failures
where defined. Phase 5 mask diagnostics record candidate dispatches, mechanically invalid,
hard-safety excluded, and allowed counts. The `0.70` threshold remains unchanged.

## 11. Latency protocol and STOP rule

Decision timing uses `time.perf_counter_ns()` around planner action selection only. It
excludes scenario parsing, simulator transition, safety evaluation/input construction,
logging, and one-time imports. One process uses `PYTHONHASHSEED=0`; each planner receives
20 unrecorded warm-up calls. Report median, mean, p90, p95, maximum, and sample count
without rounding values to zero.

Reference machine: MacBook Air (`MacBookAir10,1`), Apple M1, 8 CPU cores (4 performance,
4 efficiency), 8 GB RAM, arm64, macOS 26.6.2, Python 3.11.3. The absolute project
interactivity requirement copied from Phase 1 is **p95 decision latency <= 100 ms** on
this machine. It is a project target, not an official emergency-response standard.

Gate latency uses exact-suite practical-planner decisions; practical-suite latency is a
separate scaling diagnostic with at least 1,000 decisions per planner.

The unchanged Phase 1 STOP condition is:

```text
at least one non-clairvoyant practical planner has
median per-unit NSU-exact >= 0.99
AND p10 per-unit NSU-exact >= 0.97
AND p95 decision latency <= 100 ms
```

- If satisfied: `STOP_RL`.
- If no planner satisfies it: `PROCEED_TO_RL` (permission to test, not evidence RL wins).
- If exactness/leakage/normalization fails, oracle timeout exceeds 5%, or invalid
  normalization exceeds 5%: `INCONCLUSIVE_GATE`.

STOP means Phase 7 does not begin automatically. Definitions/configurations may not be
weakened or made harder to reverse an inconvenient result.
