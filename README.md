## Sentinel-Agent V3

**Sentinel-Agent** is an evidence-grounded decision-support prototype for dynamic flood evacuation under uncertainty.

The project investigates how a disaster-response system can combine:

- authoritative disaster-management guidance,
- retrieval-augmented generation,
- deterministic safety constraints,
- stochastic multi-step evacuation simulation,
- strong planning algorithms,
- reinforcement learning,
- reproducible evaluation,
- and an auditable human-facing decision interface.

The project deliberately follows a **measurement-first approach**. Algorithms are not retained simply because they are more complex. Every major component is compared against strong baselines, and negative experimental results are preserved.

> **Important:** The current flood scenarios, evacuation populations, shelter capacities, stochastic flood evolution, road disruptions, and reward weights are simulation/modeling assumptions unless explicitly identified as real data. The system is a research prototype and does not claim real-world emergency-response effectiveness.

---

### Research Goal

The central decision-making question is:

> **When, if ever, does reinforcement learning provide a meaningful advantage over strong deterministic planning for stochastic multi-step flood evacuation?**

The project also studies:

1. whether safety constraints reduce unsafe evacuation decisions;
2. whether evidence-grounded retrieval improves the traceability of policy constraints;
3. how decision strategies behave under flood, travel-time, route-closure, and shelter uncertainty;
4. whether learned policies remain robust when the identities and positions of zones and shelters are permuted.

---

## Current V3 Architecture

```text
Authoritative Disaster Guidance
            |
            v
      Local RAG Pipeline
            |
            v
 Evidence / Constraint Layer
            |
            v
+-------------------------------+
| Deterministic Safety Engine   |
|                               |
| capacity | status | routes    |
| hazard   | action masks       |
+---------------+---------------+
                |
                v
+-------------------------------------------+
| Dynamic Stochastic Evacuation Simulator   |
|                                           |
| zones | shelters | routes | flood state   |
| travel lag | closures | in-transit groups |
+--------------------+----------------------+
                     |
           +---------+----------+
           |                    |
           v                    v
   Planning Algorithms      MaskablePPO
           |                    |
           +---------+----------+
                     |
                     v
             Held-Out Evaluation
                     |
                     v
          Decision-Support Interface
```

---

## Live Simulation Demo

```bash
streamlit run simulation_demo.py
```

`simulation_demo.py` is the interactive end-to-end simulation; `review_dashboard.py`
is the research/evaluation presentation dashboard. Run from this checkout with the
project requirements installed (`python -m pip install -r requirements.txt`).

The live demo uses the existing StochasticSimulator, deterministic mechanical and
hard-safety mask, unchanged Risk-Greedy planner, offline Fort Kochi graph adapter,
and human-decision audit. Default generator seed: **620000**; regime: **MEDIUM**.
Presets select standard MEDIUM or HIGH uncertainty without changing outcomes.
Seed/regime changes take effect on **RESET**.

**STEP / ADVANCE** or **ACCEPT RECOMMENDATION** executes exactly one transition.
**OVERRIDE** exposes only allowed alternatives and requires a reason; select WAIT
to advance without dispatch. **REJECT** requires a reason and records no execution
or time advancement, preserving the existing human-decision semantics.

The map highlights the current recommendation. Population metrics, zones, shelters,
routes, current transit groups, actual events, population progress, shelter utilization,
and hazard history update from simulator state. Short trips may arrive at the next
observation; the actual post-dispatch snapshot and chart show their transit stage.
CSV decisions and JSON session history/summary can be downloaded. Session state is
browser-local and reset clears it. NDMA context reads frozen local artifacts with
source/page/chunk references; it does not imply semantic support for every claim.

**REAL ROAD TOPOLOGY + SIMULATED DISASTER CONDITIONS. NOT OPERATIONALLY VALIDATED.**
No Gemini, network requests, PPO training, or policy/retrieval evaluations run in the
demo. Phase 14B was superseded (its provider was unusable; it was never scored); the
claim-support evaluation of record is Phase 14D. Later closures affect future dispatches;
the simulator retains existing transit/arrival semantics without rerouting groups.

Focused offline verification:

```bash
python -m py_compile simulation_demo.py
python -m pytest tests/test_simulation_demo.py tests/test_v3_geospatial_integration.py tests/test_human_decision_demo.py
```

---

## Project Review Dashboard

Launch the standalone, artifact-backed review UI locally:

```bash
streamlit run review_dashboard.py
```

The six-tab review flow covers **Overview**, **Live Evacuation**, **Policy & RL**,
**Evidence / RAG**, **Human Override & Audit**, and **Research Progress**. A sidebar
Review Mode provides a concise three-minute faculty walkthrough. The live view connects
the existing synthetic V3 simulator, deterministic safety mask, Risk-Greedy planner,
and committed Fort Kochi OpenStreetMap road topology. It supports ACCEPT, safe OVERRIDE,
and reasoned REJECT decisions and highlights the current graph route without runtime
internet access. All flood, closure, population, shelter, traffic, and decision
conditions remain simulated; only the road topology is real.

The research tabs read frozen Phase 9/10/13/14 artifacts without rerunning experiments.
They retain the negative Phase 10 result (`RL usefulness = NO`), the Phase 13 result
(`HYBRID_SUPPORTED` versus Dense), and the secondary finding that BM25 had the highest
DirectHit@5. Phase 14B was superseded and is not scored; Phases 14C and 14D are
reported in the V4 console. Decision records remain in the browser session and can be
downloaded as CSV, with the summary available as JSON. Authoritative evidence text is
not copied into the audit log. This is a presentation layer, not a new scientific
experiment or an operationally validated emergency system.

---

## Development Status

<!-- MILESTONE-TABLE:START — refreshed by the reviewer at every merge into main from docs/patent-roadmap/STATUS.md -->
Last refreshed: 2026-10-17 · base branch `main` · live ledger: `docs/patent-roadmap/STATUS.md`

V3 (phases 0–19) is complete. V4 extends it with a certified dispatch layer; V4 internals are confidential
and described only in the private roadmap. Work is built on milestone branches and appears here only after
it has been reviewed and merged into `main`.

### V3 — complete

| Phase | Component                                              | Status        |
| ----- | ------------------------------------------------------ | ------------- |
| 0     | V1 baseline freeze and repository audit                | ✅ Complete   |
| 1     | Pre-registered evaluation framework                    | ✅ Complete   |
| 2     | Versioned V3 scenario/data contract                    | ✅ Complete   |
| 3     | Deterministic multi-timestep evacuation simulator      | ✅ Complete   |
| 4     | Stochastic flood, travel, closure and shelter dynamics | ✅ Complete   |
| 5     | Deterministic hard-safety engine and action masks      | ✅ Complete   |
| 6     | Strong planning baselines and pre-PPO headroom gate    | ✅ Complete   |
| 7     | Fixed-dimension Gymnasium environment                  | ✅ Complete   |
| 8     | Pre-registered RL reward and integration               | ✅ Complete   |
| 9     | Five-seed MaskablePPO training                         | ✅ Complete   |
| 10    | Frozen held-out planner-vs-PPO evaluation              | ✅ Complete   |
| 11    | Authoritative RAG corpus expansion                     | ✅ Complete   |
| 12    | Dense + BM25 + hybrid retrieval                        | ✅ Complete   |
| 13    | AI-assisted retrieval benchmark                        | ✅ Complete   |
| 14A   | Construction-labeled claim-support challenge           | ✅ Complete   |
| 16    | Cached geospatial road graph and routing engine        | ✅ Complete   |
| 17    | Dynamic hazard-aware graph routing integration         | ✅ Complete   |
| 18    | Human-in-the-loop override and session audit trail     | ✅ Complete   |
| 19    | Streamlit review dashboard (legacy)                    | ✅ Complete   |

### V4 — in progress

| Phase  | Component                                                   | Status                                   |
| ------ | ----------------------------------------------------------- | ---------------------------------------- |
| 20     | Verified baseline (frozen-artifact guard, UTF-8, CI)        | ✅ Complete                              |
| 14B    | Semantic claim-support evaluation (first provider)          | ⛔ Superseded (provider unusable; not scored) |
| 14C    | Semantic claim-support evaluation (second provider)         | ✅ Complete — verdict NOT_YET_RELIABLE   |
| 14D    | Semantic claim-support evaluation (evaluation of record)    | ✅ Complete — verdict USEFUL             |
| 15′    | Tier-verified NDMA constraints (incl. T2 wiring)            | ✅ Complete — rules R01, R02 at T1       |
| 21     | V4 simulated world (multi-step transit, failures)           | ✅ Complete                              |
| 22–24  | Certification engine (confidential)                         | ✅ Complete                              |
| 25–26  | Dispatch gate, certificates, replay, re-routing (confidential) | ✅ Complete                           |
| 27     | Pre-registered evaluation and decision D-27                 | ✅ Complete — no outcome-effect claim    |
| 28     | Hardware-in-the-loop rig (simulated publisher until parts)  | ✅ Complete                              |
| 30–31  | FastAPI service and React console with guided demo          | ✅ Complete                              |
| 32–33  | Decisions & Certificates, Overview, Evidence, System pages  | ✅ Complete                              |
| 34A    | Console wired to the real engine (recorded run)             | 🔄 Built — awaiting review               |
| 34C    | Live session: accept / override while the simulation runs   | 🔄 Built — awaiting review               |
| 34B    | Release: dev scripts, CI web jobs, demo script, Docker      | 🔄 In progress                           |
| 36     | Course submission pack                                      | 🔄 In progress                           |
| 35-lite| Network-outage capacity shares (exploratory)                | ⏳ Requested, not yet planned            |
| 37     | Conference paper                                            | ⏳ Planned (after Wave C)                |
| 38     | Journal extension                                           | ⏳ Optional                              |
| P0, 29 | Patent filing                                               | ⏸ On hold                                |
| 35     | Full escrow embodiment                                      | ✖ Dropped (D-27)                         |
<!-- MILESTONE-TABLE:END -->

----- | ------------------------------------------------------ | ----------- |
| 0     | V1 baseline freeze and repository audit                | ✅ Complete |
| 1     | Pre-registered evaluation framework                    | ✅ Complete |
| 2     | Versioned V3 scenario/data contract                    | ✅ Complete |
| 3     | Deterministic multi-timestep evacuation simulator      | ✅ Complete |
| 4     | Stochastic flood, travel, closure and shelter dynamics | ✅ Complete |
| 5     | Deterministic hard-safety engine and action masks      | ✅ Complete |
| 6     | Strong planning baselines and pre-PPO headroom gate    | ✅ Complete |
| 7     | Fixed-dimension Gymnasium environment                  | ✅ Complete |
| 8     | Pre-registered RL reward and integration               | ✅ Complete |
| 9     | Five-seed MaskablePPO training                         | ✅ Complete |
| 10    | Frozen held-out planner-vs-PPO evaluation              | ✅ Complete |
| 11    | Authoritative RAG corpus expansion                     | ✅ Complete |
| 12    | Dense + BM25 + hybrid retrieval                        | ✅ Complete |
| 13    | AI-assisted retrieval benchmark                        | ✅ Complete |
| 14A   | Construction-labeled claim-support challenge           | ✅ Complete |
| 14B   | Semantic claim-support evaluation                      | ⏸ Paused   |
| 15    | Re-scoped to 15′ (tier-verified constraints)           | ⏳ Planned  |
| 16    | Cached geospatial road graph and routing engine        | ✅ Complete |
| 17    | Dynamic hazard-aware graph routing integration         | ✅ Complete |
| 18    | Human-in-the-loop override and session audit trail     | ✅ Complete |
| 19    | Streamlit review dashboard (legacy)                    | ✅ Complete |
| 20    | Verified baseline (frozen-artifact guard, UTF-8, CI)   | ✅ Complete |

---

## Dynamic Simulation

V3 replaces the original one-step shelter-selection formulation with a multi-step stochastic evacuation environment.

The simulator currently supports:

- multiple evacuation zones;
- multiple shelters;
- finite shelter capacity;
- reserved capacity for in-transit evacuees;
- deterministic and stochastic travel delays;
- evolving flood severity;
- correlated regional and local hazard uncertainty;
- route closures;
- shelter degradation;
- in-transit evacuation groups;
- finite decision horizons;
- reproducible seeded stochastic episodes.

Population conservation is enforced throughout an episode:

```text
initial population
=
population remaining
+ population in transit
+ population safely arrived
```

Shelter reservations prevent multiple in-transit groups from overbooking the same capacity.

---

## Safety Architecture

Operational mechanics and safety policy are deliberately separated.

### Mechanical constraints

Examples include:

```text
closed route
unreachable destination
zero shelter capacity
closed shelter
empty evacuation zone
```

These constraints can never be disabled.

### Hard-safety layer

V3 currently includes a versioned synthetic destination-hazard rule:

```text
v3-safety-v1
maximum destination hazard = 0.70
```

A destination must have severity strictly below `0.70` to pass this rule.

The value is a **project modeling assumption reused for continuity with V1**. It is not claimed to be an official NDMA flood-safety threshold.

The safety layer can be disabled experimentally while mechanical constraints remain active, allowing a clean safety-ablation study.

---

## Planning Algorithms

The following non-learned decision policies were implemented before reinforcement learning:

- Random Valid
- Nearest Safe
- Risk Greedy
- 2-Step Lookahead
- 3-Step Lookahead
- Sampled Model Predictive Control
- Clairvoyant exhaustive oracle for small tractable scenarios

Practical planners receive current observable information and forecasts but cannot inspect exact future stochastic outcomes.

The clairvoyant oracle is used only as an experimental upper bound on small instances.

---

## Why Reinforcement Learning Was Tested

A pre-PPO planning gate was established before training.

The gate required a fast practical planner to capture:

```text
median exact headroom >= 0.99
and
p10 exact headroom >= 0.97
```

while satisfying the frozen latency requirement.

The strongest median planner, 3-step lookahead, achieved:

```text
Median NSU-exact: 0.9954
p10 NSU-exact:    0.4306
```

The median was near the clairvoyant upper bound, but lower-tail performance remained far below the pre-registered threshold.

Therefore the gate result was:

```text
PROCEED_TO_RL
```

This result justified **testing** reinforcement learning. It did not imply that reinforcement learning would be superior.

---

## Reinforcement Learning

The V3 learned policy uses:

```text
Algorithm:      MaskablePPO
Policy:         MLP [256, 256], ReLU
Observation:    384-dimensional normalized vector
Action space:   Discrete(55)
Maximum zones:  6
Maximum shelters: 9
Training seeds: 5
Timesteps/seed: 250,000
Total primary training timesteps: 1,250,000
```

Five independent primary training seeds were frozen before training:

```text
1101
2202
3303
4404
5505
```

All five models were retained regardless of performance.

No held-out test data were used for checkpoint selection.

---

## RL Reward

The primary reward was frozen before PPO training:

```text
v3-reward-balanced-v1
```

with:

```text
reward =
+ 0.55 × safe-arrival gain
- 0.30 × flood exposure
- 0.05 × travel burden
- 0.10 × unfinished population at horizon
```

The reward does not reproduce the hard-safety cutoff and does not use planner or oracle information.

Reward weights are synthetic project modeling choices rather than official emergency-management utility weights.

---

# Primary Held-Out Result

The final RL comparison used:

```text
600 unseen held-out scenarios
200 LOW uncertainty
200 MEDIUM uncertainty
200 HIGH uncertainty
```

plus:

```text
250 distribution-shift stress scenarios
```

All five PPO checkpoints and all planning baselines were evaluated on paired stochastic worlds.

### Main Results

| Policy                                | NSU-Practical | Safe Population |    Exposure |     CVaR10 |
| ------------------------------------- | ------------: | --------------: | ----------: | ---------: |
| Random Valid                          |        0.0000 |          0.6595 |     1839.73 |     0.0004 |
| Nearest Safe                          |        0.7615 |          0.7317 |     1384.40 |     0.0325 |
| Risk Greedy                           |        1.0000 |          0.7596 |     1456.02 |     0.0509 |
| Lookahead-2                           |        1.4752 |          0.8236 |     1322.76 |     0.1012 |
| Lookahead-3                           |        1.5309 |          0.8300 |     1318.64 |     0.1030 |
| MPC                                   |        1.4594 |          0.8308 |     1469.18 |     0.1020 |
| **MaskablePPO — five-seed aggregate** |    **0.2091** |      **0.6826** | **1817.49** | **0.0038** |

`NSU-Practical` is normalized against the frozen practical reference policies. Values greater than `1.0` are possible when a policy performs better than the reference planner used for normalization.

---

## Pre-Registered RL Conclusion

The principal practical comparator for the frozen RL usefulness test was:

```text
Risk Greedy
```

PPO produced:

```text
NSU difference:
-0.7919

95% paired bootstrap CI:
[-0.8384, -0.7453]

Exposure:
24.8% higher than the principal comparator

Unsafe-dispatch difference:
0.0
```

PPO also failed the pre-registered usefulness criteria separately under:

```text
LOW uncertainty
MEDIUM uncertainty
HIGH uncertainty
flood-surge stress
route-closure stress
shelter-failure stress
demand-shift stress
long-travel stress
```

The frozen Phase 1 result is therefore:

```text
RL USEFULNESS RESULT: NO
```

This result is intentionally preserved.

The project does **not** replace the result by retraining PPO until it wins.

---

## Observation-Matched Diagnostic

The strongest practical planner has access to somewhat richer pending-arrival information than the PPO observation.

To investigate whether that information advantage explains PPO's deficit, an observation-matched heuristic was also evaluated using only information available to the learned policy.

Results:

```text
Observation-matched planner NSU: 0.5204
MaskablePPO NSU:                 0.2091
```

Therefore the information asymmetry does not fully explain the learned policy's lower performance.

---

## Representation Robustness

A pre-registered semantic slot-permutation test was used to detect whether the flat MLP learns shortcuts based on entity positions rather than physical scenario features.

The held-out test measured:

```text
Action equivalence after remapping: 0.1157
Median absolute NSU change:         0.6092
Mean absolute safe-population Δ:    0.0929
```

Result:

```text
POTENTIAL_SLOT_SHORTCUT
```

This indicates material sensitivity to zone/shelter slot permutation.

The issue is preserved as a limitation rather than repaired after observing the held-out result.

Permutation-aware representations such as set-based, attention-based, recurrent, or graph architectures are treated as future research rather than replacements for the frozen primary experiment.

---

## Safety and Mechanical Integrity

Across the primary Phase 10 evaluation:

```text
Unsafe dispatches:            0
Capacity violations:          0
Closed-route dispatches:      0
Invalid PPO masked actions:   0
```

The simulator, safety layer, and action masks therefore maintained their intended operational invariants throughout the evaluation.

---

## Testing

The full offline regression suite was verified on Windows without `PYTHONUTF8` with
`python -m pytest tests/ -ra`:

```text
1056 passed, 41 xfailed, 2 xpassed   (main, 2026-10-17)
```

The xfailed tests are acceptance tests for Wave C milestones not yet merged; they become
active when each milestone is reviewed and merged.

Coverage includes:

- scenario validation;
- population/capacity conservation;
- stochastic reproducibility;
- RNG independence;
- future-information leakage;
- safety masks;
- planner information boundaries;
- exact-oracle correctness;
- Gymnasium compatibility;
- reward semantics;
- MaskablePPO integration;
- checkpoint loading;
- slot-permutation diagnostics;
- paired held-out evaluation;
- bootstrap statistics.

Historical V1 tests and artifacts remain preserved.

---

## Experimental Philosophy

Sentinel-Agent deliberately avoids assuming that the most complex algorithm is the best algorithm.

Several project hypotheses have been rejected after measurement.

The V3 RL study is one example:

```text
Hypothesis:
Sequential uncertainty may make reinforcement learning preferable.

Experiment:
Strong planners + five-seed MaskablePPO + held-out evaluation.

Result:
PPO did not provide a material advantage.

Decision:
Retain strong planning as the primary decision approach.
```

A negative result is considered a valid research outcome.

---

## Next Development Stages

The decision-policy and retrieval studies are frozen. Remaining work (see the table above):

```text
Wave C   34A/34C review, 34B release, 36 course pack, 35-lite network-outage demo
After C  37 conference paper, 38 journal extension (optional)
On hold  patent filing
```

---

## Data and Provenance

Sentinel-Agent explicitly distinguishes:

### Real

- authoritative disaster-management source documents;
- later cached public road-network topology where identified as such.

### Simulated

- evacuation populations;
- flood progression;
- shelter capacities unless explicitly verified;
- road closures;
- travel disturbances;
- stochastic scenarios.

### Model-Generated

- natural-language policy interpretations or constraint explanations.

### Measured

- benchmark scores;
- evaluation results;
- latency measurements;
- safety statistics;
- retrieval metrics.

This distinction is maintained throughout the project to avoid presenting synthetic experimental data as real disaster-response evidence.

---

## Disclaimer

Sentinel-Agent is a research and educational decision-support prototype.

It is **not**:

- an official disaster-management system;
- an operational flood forecasting platform;
- a replacement for emergency authorities;
- validated for real-world evacuation deployment.

The current evaluation demonstrates behavior only within the project's controlled synthetic experimental environment.

---

## V4 Roadmap

V4 roadmap: private, see `docs/patent-roadmap/`.
