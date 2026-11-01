# Sentinel-Agent Sprint — Build Documentation

A chronological build log and current inventory of the project. The dated entries
record additions in the order they were made; the overview near the top reflects the
repository as it exists now.

This file is source-controlled (it is not covered by any `.gitignore` rule) and is
intended to be read top-to-bottom as the story of how the prototype was built.

> **Project honesty rule:** nothing fabricated is ever described here as real. Every
> simplified, fictional, or placeholder element is labelled as such in the entry that
> introduces it. Historical entries may name bootstrap files that are no longer present;
> those references are retained as provenance, not as current setup instructions.

---

## Current V3 status — offline geospatial demo available; Phase 14B paused

Phase 14A freezes `v3-claim-support-challenge-v1`, a construction-labeled,
AI-assisted claim–evidence support challenge built from all 45 final Phase 13 questions.
For each question, the lexicographically first frozen grade-2 chunk is selected without
using retriever identity or rank. The resulting 45 question-level evidence selections
(31 distinct chunk IDs because some questions share evidence) produce 135 pairs: 45
`SUPPORTED`, 45 `PARTIALLY_SUPPORTED`, and 45 `UNSUPPORTED` claims. Every question's
three variants use the same locally reconstructed authoritative chunk.

The machine-readable artifact stores stable chunk/source/page provenance and exact
passage SHA-256, but no full authoritative passage text. Phase 14A distinguishes
deterministic source integrity, Phase 13 retrieval relevance, and semantic claim support;
it formalizes the compatible V1 quote check as `quote-integrity-v1`. Only `SUPPORTED`
maps to `SAFE_TO_CITE`. The future semantic verifier must return supporting spans, and
each span must pass deterministic verbatim validation before the citation can pass the
two-layer architecture.

This is not an independently human-gold or expert-annotated entailment benchmark.
Claims and controlled labels were constructed with AI assistance from authoritative
evidence. Negative variants are synthetic challenges and not disaster policy. The
primary future metric is frozen as three-class Macro-F1; secondary metrics, leakage
controls, label-independent evaluation order, and the all-conditions usefulness gate
are frozen in [`V3_CLAIM_SUPPORT_SPEC.md`](V3_CLAIM_SUPPORT_SPEC.md).

**NO COMPLETE PHASE 14B CLAIM-SUPPORT PERFORMANCE RESULT IS AVAILABLE.** Phase 14B is
paused because the existing Gemini project reached its daily request quota. Partial
accuracy, F1, and other semantic performance are intentionally not calculated or shown.
The frozen benchmark, prompt, model, temperature, and evaluation order remain unchanged.

The standalone review dashboard now includes an offline **Human Override & Audit** tab.
It composes the existing synthetic simulator, deterministic safety mask, Risk-Greedy
planner, and locally reconstructed frozen Phase 13 evidence. Its Phase 19 Live Decision
integration supports reproducible multi-timestep playback under the existing LOW,
MEDIUM, and HIGH uncertainty configurations. Operators may accept, reject, or select a
different currently allowed action. The dashboard renders actual simulator events and
population ledgers, keeps a session-only decision audit, and exports the audit as CSV
and its computed summary as JSON. This feature makes no Gemini or other network request
and is a demonstration layer, not a new research experiment.

Phase 16/17 geospatial integration now projects the existing synthetic incident onto a
committed 622-node, 1,358-directed-edge Fort Kochi road graph derived from OpenStreetMap.
The graph is loaded locally, fingerprint-verified, and routed with NetworkX. Closed edges
are excluded and unreachable pairs remain unreachable. Graph path metrics flow through
the existing route abstraction into the unchanged safety mask and Risk-Greedy planner.
The dashboard renders a tile-free offline graph with the recommendation highlighted.
**Road topology may be derived from real geographic data, while flood hazards,
population demand, shelter conditions and evacuation decisions remain simulated.**

### Frozen Phase 13 retrieval result

Phase 13A froze `v3-retrieval-benchmark-spec-v1` and prepared 60 `MACHINE_PROPOSED`
questions plus 647 deduplicated passage-review rows. Phase 13A.1 preserves those
historical artifacts and derives a balanced 45-question, 485-passage review set.

The project owner adopted the supplied AI-assisted question recommendations, recorded as
`PROJECT_OWNER_ADOPTED_AI_ASSISTED_QUESTION_REVIEW` with review method
`PROJECT_OWNER_ADOPTED_AI_ASSISTED_RECOMMENDATIONS`. This was not blind, independent, or
multi-reviewer annotation. The project owner later elected not to manually annotate all
485 retained passages, so Phase 13A.2 froze the separate
`v3-retrieval-benchmark-ai-assisted-v1` label set without altering the unfinished human
review artifacts. **The benchmark's passage-level relevance judgments are AI-assisted,
not independently human annotated.**

Phase 13B ran its required pre-metric coverage gate using the final 45 question texts.
The three frozen retrievers produced 434 unique top-five question/chunk pairs: 415 had
frozen labels and 19 gaps belonged to the four project-owner-edited questions `Q003`,
`Q008`, `Q016`, and `Q034`. The gate stopped evaluation before any metric.

Phase 13A.3 blind-labeled exactly those 19 frozen gaps under the unchanged protocol and
created `v3-retrieval-benchmark-ai-assisted-v2`. The compact combined set contains 504
unique labels and has fingerprint
`393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7`.
Frozen preflight label presence is now 434/434. The original 485-row v1 label artifact
and fingerprint remain unchanged.

Phase 13B subsequently passed coverage at 434/434 and evaluated the unchanged frozen
retrievers. Hybrid minus Dense DirectHit@5 was `+0.2000`, with paired 95% bootstrap CI
`[0.0889, 0.3111]`; the formal verdict is `HYBRID_SUPPORTED`. BM25 nevertheless had the
highest DirectHit@5 at 39/45 (`0.8667`), versus Hybrid 37/45 and Dense 28/45. Do not claim
Hybrid beat BM25.

### Frozen Phase 12 retrieval configuration

Phase 12 freezes `v3-retrieval-v1`: `dense-minilm-v1`, `bm25-okapi-v1`, and
`hybrid-rrf-v1` operate through one citation-compatible `RetrievedChunk` interface over
the exact same 1,797 Phase 11 chunks. Dense preserves local 384-dimensional
`all-MiniLM-L6-v2` cosine-distance retrieval; lexical retrieval uses explicit Okapi BM25
parameters and deterministic Unicode tokenization; hybrid joins stable chunk IDs with
reciprocal rank fusion (`RRF_K=60`) over `max(20, requested_k)` candidates per component.
The Chroma index refuses a mismatched corpus version, fingerprint, or chunk count.
Detailed frozen behavior is in [`V3_RETRIEVAL_SPEC.md`](V3_RETRIEVAL_SPEC.md).

Phase 12 introduces retrieval alternatives but does not establish that BM25 or hybrid
retrieval is superior to dense retrieval. Retrieval quality will be evaluated only after
Phase 13 creates a human-reviewed relevance benchmark. The frozen Phase 10
decision-policy result remains unchanged.

### Frozen Phase 10 scientific firewall

[`V3_PHASE10_EVAL_SPEC.md`](V3_PHASE10_EVAL_SPEC.md) was committed as Stage 10A before
any held-out, permutation, or stress scenario was generated. It freezes
`v3-phase10-eval-spec-v1`: all suite and policy seeds, 600 ordinary units (200 each
LOW/MEDIUM/HIGH), replication 0, five best PPO checkpoints, six unchanged Phase 6
planners, the observation-matched diagnostic, 10,000-draw two-level bootstrap, 100×5
permutation diagnostic, five 50-unit stress categories, Phase 1 latency method, and the
literal YES/NO/MIXED function. Phase 10 contains no training or checkpoint changes.

The principal baseline is `risk_greedy`, selected before test generation from the sealed
Gate 6 planner record. It was the stronger of the two safety-clean planners eligible
under the frozen 100 ms p95 budget. Lookahead-2, lookahead-3, and sampled MPC remained in
the full evaluation despite being ineligible for principal-baseline selection.

### Held-out result

The new `v3-heldout-generator-v1` uses disjoint seeds `1000000..1000599`, the supported
4–6 zone × 6–9 shelter × horizon 10–16 envelope, opaque semantic IDs, and Phase 9's broad
distributional basis under independent Phase 10 RNG namespaces. Every planner and all
five best-validation PPO checkpoints completed all 600 paired units.

| Policy | NSU-practical | Safe fraction | Exposure | CVaR10 | Completion |
| --- | ---: | ---: | ---: | ---: | ---: |
| Random valid | 0.0000 | 0.6595 | 1839.73 | 0.0004 | 0.0623 |
| Nearest safe | 0.7615 | 0.7317 | 1384.40 | 0.0325 | 0.1783 |
| Risk greedy (principal) | 1.0000 | 0.7596 | 1456.02 | 0.0509 | 0.1083 |
| Lookahead-2 | 1.4752 | 0.8236 | 1322.76 | 0.1012 | 0.1900 |
| Lookahead-3 | **1.5309** | 0.8300 | **1318.64** | **0.1030** | **0.2217** |
| Sampled MPC | 1.4594 | **0.8308** | 1469.18 | 0.1020 | **0.2217** |
| PPO five-seed family | 0.2091 | 0.6826 | 1817.49 | 0.0038 | 0.0963 |

Against the principal comparator, PPO's paired NSU difference was `-0.7919` (95% CI
`[-0.8384,-0.7453]`), exposure relative reduction was `-0.2483`
(`[-0.2613,-0.2358]`; negative means more exposure), and tail-NSU difference was
`-0.9314` (`[-1.1988,-0.8216]`). Unsafe-rate difference was zero. No LOW, MEDIUM, HIGH,
or combined gate passed. All five PPO seeds were retained; individual NSU ranged from
0.1632 to 0.2426.

### Information and representation diagnostics

The secondary `observation-matched-greedy-v1` consumes only the 384-vector, mask, and
public fixed action map. It achieved NSU 0.5204 and still exceeded PPO-family mean return
by 0.0269 while producing 258.56 fewer exposed person-timesteps. This does not remove the
known richer pending-arrival information available to the original Phase 6 planners, but
shows that the headline loss is not explained solely by that asymmetry.

The independent held-out permutation suite used 100 separate bases, five variants per
base, and all five PPO seeds (2,500 paired variants). Mean physical-action equivalence was
0.1157, median absolute NSU delta 0.6092, and mean absolute safe-population delta 0.0929.
The frozen result is again `POTENTIAL_SLOT_SHORTCUT`; Phase 9's original alarm is
preserved.

### Stress, safety, latency, and artifacts

All policies completed 250 separate stress scenarios: sudden surge, correlated route
closure cascade, high-capacity shelter failure, demand shift, and 1.75× travel lags. PPO
NSU by category was respectively 0.1641, 0.3062, 0.2446, 0.1646, and -0.0044. No stress
gate passed.

Hard safety remained ON. Ordinary evaluation recorded zero unsafe dispatches, capacity
violations, known-closed-route dispatches, post-departure route failures, or PPO masked
invalid selections. The warmed one-process latency audit timed at least 1,000 decisions
per policy from already-built input/mask to action. Principal risk-greedy measured 0.158
ms median / 0.467 ms p95; PPO-family 0.638 / 1.895 ms; lookahead-2 13.479 / 47.299 ms;
lookahead-3 189.992 / 1,442.111 ms; and sampled MPC 555.458 / 1,613.113 ms.

The detailed result is [`V3_POLICY_EVALUATION.md`](V3_POLICY_EVALUATION.md). Structured
artifacts are under `data/eval_v3/phase10/`; eleven reproducible SVGs are under
`artifacts/figures/phase10/`. A policy-independent median-difficulty trace is stored in
`qualitative_trace.json`. An allocation-free expected-model implementation optimization
was checked against the original planner: argmax actions and full episode returns match,
with only `2.8e-17` score roundoff and no horizon/sample/weight/pruning change.

### Frozen conclusion

`NO`

Under the Phase 1 rule, neither the combined ordinary result, any uncertainty stratum,
the tail criterion, nor any stress category supports a material PPO contribution. Strong
non-learned planning remains sufficient for this synthetic formulation. Separately,
representation robustness is `POTENTIAL_SLOT_SHORTCUT`.

This result is limited to the synthetic V3 environment and synthetic reward; it does not
establish real-world emergency-response effectiveness. Phase 10 stops after the Stage
10B result commit. Phase 11 and model repair remain deferred.

---

## Conventions used in this document

Each step gets one section containing:

| Field | Meaning |
| --- | --- |
| **Goal** | What the step was supposed to achieve. |
| **Added** | Every file or directory created, with its purpose. |
| **Dependencies** | Anything appended to `requirements.txt` in that step. |
| **How it was verified** | The command run and what it actually produced. |
| **Real vs. simplified** | Which parts come from real sources, which are invented for the demo. |
| **Commit** | The commit that carries the change. |

---

## Project at a glance

| Area | Path | Status |
| --- | --- | --- |
| Scenario data | `data/scenario.json` | **Built (Step 1)** — fictional grid, 9 cells, 7 shelters |
| Real source documents | `data/raw_docs/` | **Expanded (V3 Phase 11)** — 3 distinct real NDMA PDFs, 652 pages, provenance registry and exclusion log |
| Local RAG (embed + retrieve) | `src/rag/` | **Expanded (V3 Phase 12)** — dense, BM25, and hybrid-RRF over 1,797 fingerprint-checked chunks |
| Gemini constraint step | `src/constraints/` | **Built (Step 3)** — 7/7 verdicts, all citations verified |
| Gymnasium env + training | `src/env/` | **Built (Step 4)** — MaskablePPO. Current measured figure is **73% optimal on the held-out suite** (`EVALUATION.md` §2); the 91.5% below is the superseded pre-retrain training-distribution number. |
| Streamlit dashboard | `src/dashboard/` | **Built (Step 5)** — verified rendering in a real browser |
| Trained checkpoints | `models/` | **Built (Step 4)** — `maskable_ppo_shelter.zip` |
| End-to-end runner | `run_demo.py` | **Built (Step 6)** — rebuilds from nothing, exit-code checked |
| Evaluation suite | `src/eval/` | **Built** — 60 held-out scenarios, baselines, ablations |
| V3 sequential environment | `src/sim/`, `src/safety/`, `src/planners/`, `src/env_v3/` | **Built through V3 Phase 10** — stochastic simulator, hard safety, strong planners, fixed 6×9 Gymnasium API, frozen reward, five trained PPO seeds, and held-out evaluation |
| Tests | `tests/` | **Built** — 714 collected offline tests across V1 and V3 |
| Measured results | `EVALUATION.md` | **Written** — including the unflattering ones |
| Frozen v1 results | `EVALUATION_V1.md` | **Archived** — immutable comparison point for the evaluated v1 demo |
| Reviewer material | `REVIEW_NOTES.md`, `DEMO_SCRIPT.md` | **Written** — defence sheet and five-minute walkthrough |
| v2 decision experiments | `scripts/`, `data/eval_results/` | **Stopped at Gate 1A.5** — cheap lookahead closes the available planning gap |
| Closed expansion plan | `PHASE1_PLAN.md` | **Stopped** — §3 was deliberately not built after the gate failed |

### Current repository inventory

| Group | Current contents |
| --- | --- |
| Entrypoints | `run_demo.py`; `src/dashboard/app.py` |
| Core packages | `src/rag/`, `src/constraints/`, `src/env/`, `src/eval/`, `src/sim/`, `src/safety/`, `src/planners/`, `src/env_v3/` |
| Scenario and constraints | `data/scenario.json`, `data/constraints_output.json`, `data/scenarios_v3/example_v3_scenario.json` |
| Evaluation inputs/results | `data/eval_scenarios.json`, `data/eval_results/*.json`; V3 sanity, Gate 6, training/validation, frozen Phase 10 artifacts, Phase 11/12 engineering summaries, and pending Phase 13A review sheets in `data/eval_v3/` |
| Real source corpus | `data/raw_docs/README.md`, `MANIFEST.json`, `excluded_sources.json`, and three canonical NDMA PDFs |
| Model artifact | `models/maskable_ppo_shelter.zip` |
| Experiment utilities | `scripts/greedy_check.py`, `tail_check.py`, `tail_analysis.py`, `retrieval_q2.py`, `phase4_stochastic_sanity.py`, `phase5_safety_sanity.py`, `run_gate6.py`, `phase7_env_sanity.py`, `phase8_reward_sanity.py`, `run_phase10.py`, `phase12_retrieval_sanity.py`, `phase13a_prepare_review.py`, `phase13a1_apply_question_review.py`, `phase13a2_prepare_blind_payload.py`, `phase13a2_label_passages.py` |
| Automated verification | `tests/`, `pytest.ini`, `.github/workflows/ci.yml` |
| Project guidance | `README.md`, `EVALUATION.md`, `EVALUATION_V1.md`, `REVIEW_NOTES.md`, `DEMO_SCRIPT.md`, `PHASE1_PLAN.md`, `V3_BASELINE.md`, `V3_EVALUATION_PLAN.md`, `V3_SAFETY_SPEC.md`, `V3_PLANNER_SPEC.md`, `V3_GATE6_RESULT.md`, `V3_ENV_SPEC.md`, `V3_REWARD_SPEC.md`, `V3_TRAINING_SPEC.md`, `V3_TRAINING_RESULT.md`, `V3_PHASE10_EVAL_SPEC.md`, `V3_POLICY_EVALUATION.md`, `V3_CORPUS_AUDIT.md`, `V3_RETRIEVAL_SPEC.md`, `V3_RETRIEVAL_BENCHMARK_SPEC.md`, `V3_RETRIEVAL_BENCHMARK_AI_AMENDMENT.md`, `V3_RETRIEVAL_HUMAN_REVIEW.md`, `V3_RETRIEVAL_FINAL_PASSAGE_REVIEW.md`, `V3_RETRIEVAL_AI_LABEL_SPOTCHECK.md` |
| Runtime configuration | `requirements.txt`, `.python-version`, `.streamlit/config.toml`, `.gitignore` |

Generated local state is intentionally not part of that inventory: `.venv/`,
`src/rag/chroma_db/`, `.pytest_cache/`, `__pycache__/`, and local AI-assistant settings
are ignored. The virtual environment and Chroma index may exist locally and are retained
because they make the current demo runnable without reinstalling or re-indexing.

---

## Step 0 — Project scaffold

**Goal.** Stand up the repository skeleton, a Python 3.11 virtual environment, and an
empty dependency manifest, and confirm the Gemini API key is present *before* any
code that would call it gets written.

### Added

| Path | Purpose |
| --- | --- |
| `.git/` | Repository initialised here; the directory was not previously under version control. |
| `data/raw_docs/` | Destination for **real** published flood-management PDFs. Contains a `README.md` stating that only genuine documents belong there and that the RAG step must refuse to run rather than invent a corpus. |
| `data/` | Will hold `scenario.json` (Step 1). |
| `src/rag/` | Local embedding + retrieval package. `__init__.py` only so far. |
| `src/constraints/` | Gemini constraint-generation package. `__init__.py` only so far. |
| `src/env/` | Gymnasium environment + training package. `__init__.py` only so far. |
| `src/dashboard/` | Streamlit app. Deliberately **not** a Python package — Streamlit runs it as a script, so it has no `__init__.py`. |
| `models/` | Trained policy checkpoints (Step 4). Empty, held by `.gitkeep`. |
| `.gitignore` | Excludes `.venv/`, `__pycache__/`, the generated Chroma store at `src/rag/chroma_db/`, `.env`, and `.DS_Store`. |
| `requirements.txt` | Created **empty** apart from a header comment. `DEVELOPMENT.md` requires dependencies to be added step by step as they are actually used, not declared up front. |
| `.python-version` | Records `3.11` as the intended interpreter. |

### Environment

- **Interpreter:** the venv at `.venv` runs **Python 3.11.3**.
  The machine's default `python3` is **3.9.6**, which is below the 3.11+ floor set in
  `DEVELOPMENT.md`, so the venv was created from the Python 3.11 binary supplied by the
  local Anaconda install. The resulting venv is standalone; Anaconda is only its base
  interpreter, not a runtime dependency of the project.
- **`GEMINI_API_KEY`:** confirmed **present** in the shell environment (53 characters).
  Only its *existence* was checked. The key has **not** been validated against the
  Gemini API yet, because no packages were installed at this point — the first real
  API call happens in Step 3, and that is where an invalid key would surface.

### Dependencies

None. `requirements.txt` is intentionally empty after this step.

### How it was verified

```
$ git ls-files
.gitignore
.python-version
DEVELOPMENT.md
KICKOFF_PROMPT.md
data/raw_docs/.gitkeep
data/raw_docs/README.md
models/.gitkeep
requirements.txt
src/__init__.py
src/constraints/__init__.py
src/env/__init__.py
src/rag/__init__.py

$ .venv/bin/python --version
Python 3.11.3
```

Working tree clean after commit.

### Real vs. simplified

Nothing in this step is data of any kind — it is structure only. No claims about the
real world are made yet.

### Notes

- The empty directories `data/raw_docs/` and `models/` are tracked via `.gitkeep`
  placeholder files, since git does not track empty directories. These are
  placeholders, not content.

### Commit

`65cd74c` — *Step 0: project scaffold, venv, gitignore, empty requirements*

---

## Step 0.1 — GitHub remote and this document

**Goal.** Put the project on GitHub as a **private** repository and start the running
documentation file.

### Added

| Path | Purpose |
| --- | --- |
| `DOCUMENTATION.md` | This file. A per-step record of every addition to the project, committed alongside the code it documents. |

### Repository

- **Remote:** `iamnoob96/sentinel-sprint` on github.com
- **Visibility:** **private**
- **Pushed as:** GitHub account `iamnoob96` (the account the local `gh` CLI is
  authenticated against).

### Dependencies

None.

### Real vs. simplified

Not applicable — repository plumbing only.

### Commit

Recorded in the commit that adds this file; see `git log` for the current hash.

---

## Step 1 — The scenario

**Goal.** Produce the single scenario file every later step reads from: the RAG step
retrieves clauses to judge it, the Gemini constraint step marks each shelter
allowed/excluded against it, the RL environment draws its observation and reward from
it, and the dashboard renders it. This step therefore fixes the data contract for
Steps 3–6.

### Added

| Path | Purpose |
| --- | --- |
| `data/scenario.json` | The whole deliverable. A fictional ward-scale flood scenario: a 3×3 grid of 9 cells with a flood-severity gradient, one flooded source cell holding the evacuee population, and 7 candidate shelters with capacity, occupancy, status, and travel cost. |

### Shape of the file

Top-level keys: `_disclaimer`, `scenario_id` (`flood-evac-demo-01`), `schema_version`,
`provenance`, `hazard_model`, `grid`, `source`, `shelters`, `field_notes`.

- **`grid`** — 9 cells `C1`–`C9` addressed by `(row, col)` **grid indices only**. There
  are no latitudes, longitudes, ward names, or agency names anywhere in the file;
  `DEVELOPMENT.md` forbids inventing real-sounding administrative detail. Cells carry a
  generic descriptor (`"upstream channel-adjacent cell"`) instead of a fake place name.
- **`hazard_model`** — documents the 0.0–1.0 `flood_severity` scale and the thresholds
  behind each `severity_band` label, so the band labels are reproducible rather than
  hand-assigned.
- **`source`** — cell `C1`, `population_to_evacuate: 700`.
- **`shelters`** — 7 entries, each with exactly: `shelter_id`, `cell_id`,
  `capacity_total`, `current_occupancy`, `status`, `travel_cost_minutes`.

**Capacity headroom is derived, never stored** (`capacity_total - current_occupancy`),
so the two numbers cannot drift out of agreement.

### The deliberate trap

The spread was designed so the demo actually proves something. If travel cost alone
picked the right shelter, the entire RAG-plus-constraint layer would be decoration.

| ID | Cell | Severity | Cap | Occ | Headroom | Travel | Fits 700? | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | C2 | 0.85 severe | 1000 | 100 | **900** | **8** | **YES** | operational |
| S2 | C4 | 0.63 high | 250 | 240 | 10 | 14 | no | operational |
| S3 | C5 | 0.48 moderate | 600 | 180 | 420 | 21 | no | operational |
| S4 | C8 | 0.10 low | 900 | 150 | **750** | 34 | **YES** | operational |
| S5 | C9 | 0.05 minimal | 1100 | 90 | **1010** | 41 | **YES** | operational |
| S6 | C6 | 0.35 moderate | 500 | 500 | 0 | 26 | no | at_capacity |
| S7 | C7 | 0.22 low | 350 | 60 | 290 | 30 | no | closed_structural_damage |

- **S1 is the trap.** It is nearest by a wide margin (8 min vs. a next-best of 14) and
  has enough headroom for all 700 evacuees, so the unconstrained reward ranks it first —
  but it sits inside a `severe` flood cell. Only the constraint step rules it out.
- **S6 and S7 fail on shelter status alone** (full; closed for structural damage).
- **The live trade-off is S4 vs. S5** — fits-everyone-and-closer against
  safest-and-roomiest. That is precisely the tension Step 4's reward has to weigh.

### No pre-baked verdicts

`scenario.json` stores **raw facts only**. No shelter carries an `allowed` or `excluded`
field; verified by grep, the strings appear nowhere as a JSON value. Deciding viability
is Step 3's job against real NDMA/NIDM text — hardcoding verdicts here would reduce the
Gemini call to theatre.

### Dependencies

None. `json` is in the standard library. `requirements.txt` remains empty.

### How it was verified

Ran assertions plus a derived decision table through `.venv/bin/python`:

```
All structural assertions PASSED
cells=9  shelters=7  population_to_evacuate=700

Cheapest by travel cost alone -> S1 (8 min) in a 'severe' flood cell (severity 0.85)  <-- the trap
Shelters that fit all 700: ['S4', 'S5']
```

The assertions checked: valid JSON; exactly 9 cells (inside the 8–10 bound); 7 shelters
(inside the 5–8 bound); the 3×3 positions are unique and complete; the source cell
resolves; every shelter's `cell_id` resolves to a real cell; no shelter is over-occupied;
shelter IDs are unique; every shelter object carries an identical key set; and every
`severity_band` label agrees with the thresholds declared in `hazard_model`.

### Real vs. simplified

**Real** — used only as background inspiration, and recorded in
`provenance.real_background`: the August 2018 Kerala floods peaked in mid-August 2018;
severely affected districts included Idukki, Ernakulam, Alappuzha, Thrissur, and
Wayanad; the flooding was worsened by controlled dam releases including from the Idukki
reservoir. **No number in the file derives from these facts** — they informed only the
*shape* of the scenario (an upstream-to-downstream severity gradient).

**Fictional** — everything else, listed explicitly in `provenance.fictional_elements`:
the grid and all cell IDs, all `(row, col)` positions, all seven shelters and their
capacities/occupancies/statuses, all severity values, all travel costs, and the evacuee
population.

**Out of scope**, recorded in `provenance.out_of_scope`: IoT/sensor feeds, satellite
imagery, and traffic APIs are **cut entirely, not deferred**. In particular
`travel_cost_minutes` is a static abstract cost baked into the file — it is *not*
computed from any road network, routing engine, or traffic feed.

The `_disclaimer` field at the top of the file states in one line that this is inspired
by the 2018 Kerala floods using a simplified fictional grid for demo purposes, and is
not real GPS or administrative data.

### Commit

See `git log` for the hash of *Step 1: fictional Kerala-inspired flood scenario*.

---

## Step 2 — Real RAG corpus

**Goal.** Put genuine published flood-management guidelines on disk and make their
clauses retrievable, so the Step 3 constraint call can cite real text. If retrieval
returned nothing real, Step 3's citations would be invented — which `DEVELOPMENT.md` forbids
outright. Everything in this step runs locally: no API key, no paid service.

### Added

| Path | Purpose |
| --- | --- |
| `src/rag/fetch_docs.py` | Downloads the source PDFs, verifies each really is a PDF (`%PDF` magic bytes), deduplicates by content hash, and writes a provenance manifest. Never creates a placeholder: on failure it reports and exits non-zero. |
| `src/rag/ingest.py` | Extracts page text with `pypdf`, chunks it, embeds locally with `sentence-transformers`, and writes a Chroma collection. |
| `src/rag/retrieve.py` | `retrieve(query, k)` → `RetrievedChunk(text, source_document, page, score)`. This is the reusable function Step 3 imports. |
| `src/rag/test_retrieval.py` | Prints top-3 chunks for the required query plus two Step-3-shaped probes, so a human can confirm the text is real. |
| `data/raw_docs/ndma_flood_guidelines.pdf` | The real source document (6,120,219 bytes). **Committed**, so the demo runs with no network. |
| `data/raw_docs/MANIFEST.json` | Provenance: URL, mirror URLs, SHA-256, byte size, page count, retrieval timestamp. |

### Two real findings about the source URLs

**1. The kickoff prompt's NIDM URL 404s.** `https://nidm.gov.in/pdf/guidelines/floods.pdf`
(lowercase `pdf`) returns HTTP 404 — that host's paths are case-sensitive.
`https://nidm.gov.in/PDF/guidelines/floods.pdf` serves the file. Same host, same
filename, corrected casing; **not** a substituted document. That host also answers
`HEAD` with 404 while answering `GET` with 200, so the fetcher never uses `HEAD` to test
for existence.

**2. The two URLs serve the same file.** The NDMA and NIDM URLs return **byte-identical**
content — SHA-256 `2fc4518a29c249c91d223eb6edb6f5cba23d3fa85eaaa8a71d319bdde451981f`,
6,120,219 bytes both. This was confirmed with `curl` independently of the fetch script,
so it is not an artefact of fetching one URL twice. NIDM mirrors the NDMA file.

> **Consequence, and why it mattered.** Indexing both would have put every chunk into the
> corpus twice, letting a "top 3" retrieval return three copies of one passage while
> looking like three independent citations. `fetch_docs.py` now deduplicates by SHA-256:
> it keeps one canonical file, deletes the redundant copy, and records the second URL
> under `mirror_urls` with a manifest note stating mirrors are **not** separate documents.
>
> **The corpus is therefore one real document, not two.** That clears the kickoff's bar
> ("at least one real document"), but it should not be described as two sources.

### What the document actually is

Identified by reading the extracted text, not by trusting the filename or metadata:

- **Title:** *National Disaster Management Guidelines: Management of Floods*
- **Publisher:** National Disaster Management Authority (NDMA), Government of India
- **Dated:** signed *"New Delhi … 17 January, 2008"* in the foreword
- **Pages:** 168

Two pieces of metadata about this file are **wrong and were not trusted**: the PDF's own
`/CreationDate` claims 2004, and the `file` utility reports "31 pages" because it
misreads linearized PDFs. `pypdf` reports the true 168.

### How chunking preserves citations

Chunks are **page-scoped** — a chunk never spans a page boundary — so every chunk keeps
an exact page number and Step 3 can cite "document, page N" truthfully. Windows are
~1,000 characters with ~150 of overlap; chunks under 200 characters are dropped.
Metadata per chunk is `source_document` (named to match the Step 3 schema field), `page`,
and `chunk_index`.

Embeddings are computed by us with `all-MiniLM-L6-v2` and **passed to Chroma explicitly**,
so Chroma never silently falls back to downloading and using its own default embedding
model. Re-running `ingest.py` deletes and rebuilds the collection, so it is idempotent
rather than accumulating duplicates.

### Dependencies

Added to `requirements.txt`: `pypdf==6.16.2`, `sentence-transformers==6.0.1`,
`chromadb==1.5.9`. All free and local. `torch` 2.13.0 (CPU) arrives as a
`sentence-transformers` dependency and is the bulk of the install.

The Chroma store at `src/rag/chroma_db/` (6.4 MB) is **gitignored** — it is fully
regenerable from the committed PDF via `ingest.py`.

### How it was verified

```
$ .venv/bin/python -m src.rag.fetch_docs
[ndma_flood_guidelines.pdf]  saved, bytes 6,120,219, pages 168
[nidm_floods.pdf]            DUPLICATE: byte-identical -- recorded as a mirror URL
1 distinct document(s) in data/raw_docs/ from 2 source URL(s) (1 duplicate mirror URL(s))

$ .venv/bin/python -m src.rag.ingest
pages with a text layer: 162      characters extracted: 374,292
chunks kept: 480
Embedded 480 chunks, dimension 384
Indexed 480 chunks into 'flood_guidelines'

$ .venv/bin/python -m src.rag.test_retrieval
QUERY 'flood evacuation shelter capacity' -> #1 [page 86, distance 0.3567]
  "...An important component of preparedness for floods is the construction of
   suitable shelters for the flood-affected people during the relief period. The
   state governments will design such shelters..."
QUERY 'shelter site selection flood-free elevated land' -> #1 [page 64, distance 0.3489]
  "...providing raised platforms for flood shelter for men and cattle, raising the
   public utility installation especially the platforms for drinking water hand
   pumps and bore wells above flood level..."
```

162 of 168 pages yielded a text layer, so the PDF is digital text and not a scan — no
OCR fallback was needed (none exists in this prototype; `ingest.py` warns loudly if
extraction comes back nearly empty rather than indexing emptiness).

### Real vs. simplified

**Entirely real.** Every chunk in the index is extracted verbatim from the genuine NDMA
guidelines PDF. Nothing in this step is synthesised. The retrieved passages quoted above
are actual text from pages 86 and 64 of that document.

### Known limitation

Retrieval sometimes surfaces front-matter — a table-of-contents line (page 10) and the
abbreviations list (page 18) appeared among lower-ranked results. Top-ranked hits are
substantive, so this is left as-is rather than over-filtered, but it is a real weakness:
the Step 3 prompt should be tolerant of an occasional low-value chunk.

### Commit

See `git log` for the hash of *Step 2: real NDMA guideline corpus with local embedding and retrieval*.

---

## Step 3 — The constraint step

**Goal.** Join Step 1's verdict-free scenario to Step 2's real guideline corpus with
**exactly one structured Gemini call per scenario**, marking every candidate shelter
`allowed` or `excluded` with a one-sentence reason and the clause it rests on. This is
the load-bearing step: the Step 1 data was built so a distance-minimising baseline picks
the unsafe S1, and only this step rules it out.

### Added

| Path | Purpose |
| --- | --- |
| `src/constraints/generate.py` | Retrieval of context, prompt construction, the single Gemini call, schema validation, the grounding check, and disk caching. |
| `src/constraints/test_constraints.py` | Runs the step standalone and prints the verdict table, every reason and cited clause, and the raw JSON. |
| `data/constraints_output.json` | The validated result, **committed** so Steps 4–6 and the live demo need no API call. |

### Model substitution — a spec change, approved

`DEVELOPMENT.md` originally fixed `gemini-2.5-flash` / `gemini-2.5-flash-lite`. **Both return
`404 NOT_FOUND` on this key:**

```
This model models/gemini-2.5-flash is no longer available to new users.
Please update your code to use models/gemini-3.6-flash
```

Note that `client.models.list()` still *advertises* both models — the failure only
appears on an actual generate call, so listing the catalogue is not a valid availability
check. `gemini-3.6-flash` was verified working, and was adopted **with the project
owner's explicit approval**. `DEVELOPMENT.md` has been updated to record the substitution and
its reason rather than leaving a dead model id in the spec.

Still free tier: a Google AI Studio key with no billing attached cannot call anything
outside it, so a successful call is itself evidence the model is free-tier eligible.

### The three defences against a fabricated citation

1. **Schema validation** (hard, triggers the retry) — top-level keys, matching
   `scenario_id`, exactly one entry per shelter with no missing and no invented
   `action_id`, `status` ∈ {allowed, excluded}, non-empty reason and excerpt.
2. **`source_document` must be a filename actually listed in
   `data/raw_docs/MANIFEST.json`** — a citation naming a document not in the corpus is
   the most plausible-looking way a fabricated source would slip past a reader.
3. **Verbatim grounding check** — each `source_excerpt` must appear, whitespace-normalised
   and case-insensitive, inside a chunk actually retrieved. Failure retries once; if it
   still fails the result is kept but marked `citation_verified: false` and rendered
   **UNVERIFIED**. The demo never hard-fails on stage, and the system detects its own
   ungrounded citations instead of trusting the model.

**The retry is not decorative — it fired on the first real run.** Attempt 1 returned
`"source_document": "ndma_flood_guidelines.pdf (page 89)"`, appending a page number to
the filename. Check 2 rejected all seven entries, the errors were fed back, and attempt 2
returned clean filenames.

### A prompt fix worth recording

The first passing run was structurally perfect but **weak where it mattered**: five of
seven constraints cited the same generic sentence ("Evacuation of human population and
livestock is the only prescribed means...") regardless of the actual reason. The quotes
were real and verbatim, but a citation that does not support its specific reason is
useless — and the explainability claim is the whole point of the step.

Inspecting the retrieved chunks showed the corpus *did* contain strong, specific clauses
(e.g. page 111: *"Plinth levels of all buildings should be 0.6 m above the drainage/flood
submersion lines"*). The model was simply defaulting to one generic quote. The prompt now
requires the excerpt to be the clause most directly supporting that shelter's specific
verdict, and forbids reusing one generic sentence.

Result: **7 distinct excerpts across 7 constraints**, and it now passes on attempt 1.

### Schema conformance

All five `DEVELOPMENT.md`-mandated fields are present on every constraint, unchanged. Two
additions are **additive only** and break no consumer:

- `citation_verified` (bool) on each constraint — required to surface UNVERIFIED.
- `_meta` at top level — model name, scenario fingerprint, retrieved chunk list, attempts
  used, and unverified ids.

### Caching

The result is written to `data/constraints_output.json` keyed by a **scenario
fingerprint** (a hash of the decision-relevant scenario facts). A rerun reuses the cache;
editing the scenario invalidates it automatically; `--refresh` forces a new call. This
keeps free-tier quota intact and means the live demo works with no network.

### Dependencies

`google-genai==2.21.0` added to `requirements.txt`.

### How it was verified

```
$ .venv/bin/python -m src.constraints.test_constraints --refresh
Calling gemini-3.6-flash (attempt 1 of 2)...

ID  verdict    severity             headroom  travel   citation
S1  EXCLUDED   0.85 severe               280       8   ndma_flood_guidelines.pdf [VERIFIED]
S2  EXCLUDED   0.63 high                  10      14   ndma_flood_guidelines.pdf [VERIFIED]
S3  EXCLUDED   0.48 moderate             420      21   ndma_flood_guidelines.pdf [VERIFIED]
S4  ALLOWED    0.1 low                   750      34   ndma_flood_guidelines.pdf [VERIFIED]
S5  ALLOWED    0.05 minimal             1010      41   ndma_flood_guidelines.pdf [VERIFIED]
S6  EXCLUDED   0.35 moderate               0      26   ndma_flood_guidelines.pdf [VERIFIED]
S7  EXCLUDED   0.22 low                  290      30   ndma_flood_guidelines.pdf [VERIFIED]

ALLOWED  (2): ['S4', 'S5']
EXCLUDED (5): ['S1', 'S2', 'S3', 'S6', 'S7']
attempts used: 1
All citations verified verbatim against the retrieved NDMA text.
```

Independent assertions over the written file:

```
PASS: all 5 DEVELOPMENT.md-mandated fields present on all 7 constraints
PASS: only additive field is 'citation_verified'
PASS: one entry per shelter, no duplicates, no invented shelters
verified citations: 7 / 7
distinct excerpts used: 7
PASS: GEMINI_API_KEY appears in no file in the repo
```

**The trap worked.** S1 — nearest at 8 minutes — was excluded for sitting in a 0.85
severe-flood cell, citing a real clause about roof and first-floor levels needing to sit
above 100-year flood levels. S6 was excluded as at-capacity, S7 as closed with the apt
quote *"Maintenance of shelters is a major issue."* S4 and S5 remain allowed, which is
exactly the trade-off Step 4 has to weigh.

### Real vs. simplified

**Real:** the guideline text, every excerpt, and the Gemini call itself. Every quoted
clause was checked to be verbatim present in the retrieved NDMA text.

**Model-generated:** the verdicts and reasons. These are `gemini-3.6-flash`'s judgements
about fictional shelters — not official determinations by any agency, and they should
never be described as such.

**Fictional:** everything the verdicts are *about* — the shelters, capacities, statuses,
and severities, per Step 1.

### Deliberately not done

No deterministic pre-filter removing full or closed shelters before the model sees them.
The kickoff says the LLM marks each shelter; letting code silently pre-decide would
overstate what the LLM is actually doing.

### Commit

See `git log` for the hash of *Step 3: RAG-grounded Gemini constraint step*.

---

## Step 4 — The RL environment

**Goal.** Turn Step 3's constraint set into a decision. Per `DEVELOPMENT.md` this is a
**single-decision, contextual-bandit-style** task: one action per candidate shelter, one
step per episode, small enough to train in minutes. Excluded shelters are made
**structurally unselectable** via `MaskablePPO` action masking rather than discouraged
with a penalty.

### Added

| Path | Purpose |
| --- | --- |
| `src/env/shelter_env.py` | `ShelterChoiceEnv` — `Discrete(7)` actions, 28-dim observation, one step per episode, `action_masks()` for MaskablePPO. |
| `src/env/train.py` | Trains MaskablePPO, runs `check_env` first, evaluates against an oracle, saves the checkpoint. |
| `src/env/evaluate.py` | Example decisions, including the real scenario using the actual Gemini mask, plus a 1,000-episode masking assertion. |
| `models/maskable_ppo_shelter.zip` | The trained checkpoint. **Committed** — the demo loads it. |

### Reward

```
fit          = min(headroom / population, 1.0)     # 1.0 once it can take all 700
travel_score = 1 - normalised travel cost
reward       = 0.65 * fit + 0.35 * travel_score
```

Fit is **capped**, so space beyond "fits everyone" earns nothing and travel cost breaks
the tie between shelters that both fit. This was a deliberate choice: it models the real
question ("can it take everyone?") rather than rewarding a shelter for space nobody uses.

### THE MOST IMPORTANT CAVEAT — the training mask is not the LLM

The action mask has **two different sources**:

| Mode | Mask source |
| --- | --- |
| **Training** (`randomise=True`) | `proxy_exclusion_rule()` — a small deterministic rule (severe flooding / no headroom / not operational) |
| **Demo & inference** (`randomise=False`) | the **real Step 3 Gemini output** from `data/constraints_output.json` |

Training runs tens of thousands of episodes; calling the Gemini API once per episode
would be neither free nor fast, and `DEVELOPMENT.md` forbids paid usage. The proxy imitates
the *kind* of exclusions the LLM makes — **it is not the LLM, and it is not derived from
the NDMA documents.**

> **Do not describe the policy as "trained against LLM-generated constraints."** It is
> trained against a proxy rule and *evaluated* against real LLM constraints. This is
> stated in the module docstring as well as here, because a reviewer could reasonably
> assume otherwise.

### A second finding, and the fix for it

The first version of this step had a real weakness, found by checking rather than
assuming. With S1's original headroom of 280, the reward function **already** disfavoured
it (its `fit` term was only 0.4 despite being closest), so:

```
argmax with NO constraints at all : S4
argmax WITH the Gemini mask       : S4
```

The mask made S1 unselectable but did not change which shelter won. The claim
"the constraints stopped the unsafe recommendation" would have been false.

**Fix (approved):** S1's capacity was raised to 1,000 with 100 occupied — headroom 900.
It now fits all 700 evacuees *and* is still the closest at 8 minutes, so it scores a
perfect **1.0**, while remaining in the 0.85 severe-flood cell. Result:

```
  S1  reward 1.0000  EXCLUDED     S5  reward 0.6500  allowed
  S2  reward 0.2956  EXCLUDED     S6  reward 0.1591  EXCLUDED
  S3  reward 0.6021  EXCLUDED     S7  reward 0.3860  EXCLUDED
  S4  reward 0.7242  allowed

argmax with NO constraints : S1        <-- a shelter inside the flood zone
argmax WITH Gemini mask    : S4
CONSTRAINTS CHANGE THE ANSWER: True
```

**Without the constraint layer this system recommends a shelter inside the severe-flood
zone.** That is now a demonstrable claim, not a hopeful one.

Gemini was re-run against the modified scenario and **still excluded S1** — now purely on
hazard grounds, since the capacity objection had disappeared: *"Shelter S1 is located in
a severely flooded cell with a flood severity of 0.85, making it unsafe to receive
evacuees."* The policy was retrained because the shelter templates changed.

### How it was verified

```
$ .venv/bin/python -m src.env.train
Checking the environment against the Gymnasium API...
  environment OK
Training MaskablePPO for 40,000 timesteps (CPU)...
  picked the optimal allowed shelter : 91.5%
  mean reward        : 0.6751
  oracle mean reward : 0.6792
  mean regret        : 0.0041
  masked-action violations : 0  (must be 0)

$ .venv/bin/python -m src.env.evaluate
DECISION ON THE REAL SCENARIO  (mask from the actual Gemini constraint step)
S1   masked out   0.85    900    8   1.0000   <-- top score, but EXCLUDED
S4   SELECTABLE   0.1     750   34   0.7242   <-- CHOSEN
S5   SELECTABLE   0.05   1010   41   0.6500
  RECOMMENDED SHELTER : S4      regret 0.0000

EXAMPLE DECISIONS ON RANDOMISED SCENARIOS — 8/8 optimal

Masking check over 1,000 random episodes...
  episodes where an EXCLUDED shelter was chosen: 0  (must be 0)
```

`check_env` from Stable-Baselines3 passes before training, so the environment conforms to
the Gymnasium API.

### On the 91.5% figure — do not oversell it

With only a handful of allowed actions per episode this is an **easy** problem. A high
optimal rate shows the wiring is correct; it is not evidence of a sophisticated policy.
The training script prints this caveat itself so it cannot be quietly dropped.

> **Superseded — read this before quoting any number in this section.** 91.5% was measured
> on the *training* distribution, and by a policy that was later found to be broken (the
> S6/S7 bug, in the post-demo section below). The current policy scores **73% optimal on
> the held-out suite** against a greedy oracle's 93%, and on this demo scenario it now
> recommends **S5** (0.650, regret 0.074), **not** the S4 with regret 0.0000 printed
> above. See `EVALUATION.md` §2.

### Dependencies

`gymnasium==1.3.0`, `stable-baselines3==2.9.0`, `sb3-contrib==2.9.0`.

### Real vs. simplified

**Real:** the masking mechanism, the training, and the evaluation numbers above.

**Simplified:** the training-time exclusion proxy (above); the episode randomisation,
which jitters the fictional Step 1 shelters; and the reward weights (0.65 / 0.35), which
are a modelling choice, not a figure from any source.

### Commit

See `git log` for the hash of *Step 4: single-decision Gymnasium env + MaskablePPO*.

---

## Step 5 — The dashboard

**Goal.** The only part shown live. It has to make the pipeline legible to someone who
has not read the code, and must not overstate what the system does.

### Added

| Path | Purpose |
| --- | --- |
| `src/dashboard/app.py` | Single-page Streamlit app. Renders what the pipeline produced; reimplements no decision logic. |
| `.streamlit/config.toml` | Pins a **light** theme so the app looks identical on any machine. |

### Layout, top to bottom

1. **Provenance banner above the fold** — states that the NDMA document is real and that the grid, shelters, capacities, statuses, severities and travel costs are all fictional, and that the verdicts are a language model's judgements, not any agency's determinations.
2. **Recommendation** — four stat tiles: shelter, travel time, spare capacity, policy score with regret.
3. **The constraint toggle** — see below.
4. **Hazard grid** — 3×3, shaded by severity, source cell marked, each shelter shown in its cell with its verdict.
5. **Shelter table** — every shelter with severity, headroom, travel, status, score, verdict badge.
6. **Exclusion evidence** — for every excluded shelter: reason, the verbatim NDMA quote, document and date, and a VERIFIED/UNVERIFIED badge.

### An accessibility failure found by measuring, not guessing

The palette validator was run on the ALLOWED/EXCLUDED colour pair:

```
[FAIL] CVD separation  #d03b3b <-> #0ca30c  ΔE 4.1 (deutan)
[PASS] Normal-vision floor  ΔE 33.9
```

**Green-vs-red is essentially invisible to a deuteranope** — roughly 1 in 12 men. A
verdict encoded by colour alone would have been unreadable to a reviewer in the room.

Mitigation, applied everywhere a verdict appears: **icon + text label**, colour only as
reinforcement — `✓ ALLOWED` / `✕ EXCLUDED`, never a bare coloured dot. Likewise **flood
severity is printed numerically in every grid cell**, so magnitude is never carried by
shade alone.

### Colour choices

- **Severity = sequential magnitude → one hue, light→dark**: the validated blue ramp
  (`#cde2fb` → `#0d366b`), which also reads naturally as water depth. Not a rainbow.
- **Verdicts** = the fixed status palette (`#0ca30c` / `#d03b3b`), with the icon+label
  mitigation above.
- No new categorical palette was introduced, so no further validation was required.

### The constraint toggle

Off → the real Gemini mask applies → **S4** (**since the post-demo retrain this is S5**,
labelled `SUBOPTIMAL`; see below). On → the mask is dropped and **the same
policy is re-run on an all-allowed mask** → **S1**, with an explanation that it is the
closest shelter with room for everyone but sits in a severe-flood cell.

The unconstrained result is **computed, not hardcoded** — the dashboard actually re-runs
the policy. Hardcoding "S1" would have made the demo's central claim theatre.

S1's exclusion panel auto-expands when it is the unconstrained pick, so the evidence is
already open when the question gets asked.

### Offline by construction

`@st.cache_resource` for the checkpoint, `@st.cache_data` for scenario and constraints.
The app reads the **cached** `data/constraints_output.json` and **never calls Gemini**, so
the demo runs with no network. Missing checkpoint or constraints produces the exact
command to run, not a traceback.

### How it was verified

Streamlit only executes the script when a client connects, so "the server started" proves
nothing. A real browser (Playwright driving Chrome) was used instead:

```
page errors: none
  OK  'Sentinel-Agent'     OK  'Why each shelter was excluded'
  OK  'Recommendation'     OK  'VERIFIED'
  OK  'S4'                 OK  'EXCLUDED' / 'ALLOWED'
  OK  'Hazard grid'        OK  'NDMA'

toggle ON -> 'Unsafe recommendation': True
toggle ON -> mentions S1            : True
```

Screenshots of the top, the toggled comparison, and the exclusion evidence were captured
and **visually inspected** for collisions and overflow. An initial headless-Chrome
`--screenshot` attempt captured only Streamlit's loading skeleton — the virtual clock
never let the websocket finish — which is why a real driver was used.

**Playwright is verification tooling only and is deliberately NOT in
`requirements.txt`** — the app does not need it.

### Dependencies

`streamlit==1.63.0`.

### Real vs. simplified

Everything rendered is produced upstream; the dashboard invents nothing. The banner at
the top of the page states the real/fictional split, so it travels with the demo rather
than depending on the presenter remembering to say it.

### Commit

See `git log` for the hash of *Step 5: Streamlit dashboard*.

---

## Step 6 — Tie it together

**Goal.** Make the whole pipeline one command, and write a README that states plainly
what is real, what is invented, what it costs, and what would have to change to make it
rigorous.

### Added

| Path | Purpose |
| --- | --- |
| `run_demo.py` | Six-stage end-to-end runner. Rebuilds anything missing, skips anything present. |
| `README.md` | The project's public account of itself: real vs. fictional, free-tier services, how to run, honesty mechanisms, known limitations, and the path to a rigorous version. |

### `run_demo.py` stages

1. **Preflight** — Python version, package imports, `GEMINI_API_KEY`. The key is only
   *required* when constraints must actually be regenerated; a cached run reports that no
   key and no network are needed.
2. **Scenario** — grid, source cell, and all seven shelters with derived headroom.
3. **Corpus** — fetches the PDF if absent, embeds if the vector store is absent, then runs
   a **live top-1 retrieval** so the RAG layer is visibly working rather than assumed.
4. **Constraints** — cached or regenerated; prints the verdict table and per-citation
   verification.
5. **Policy** — trains if no checkpoint exists, else loads.
6. **Decision** — runs the policy with the real mask, **then again on an all-allowed
   mask**, and prints both.

Stage 6 exists because the with/without comparison is the project's central claim; the
end-to-end script should *demonstrate* it, not assert it. The unconstrained result is
computed, never hardcoded.

### How it was verified

Three runs, not one:

```
1. Everything cached
   "Using cached constraints from constraints_output.json (no API call)."
   RECOMMENDED SHELTER : S4
   with NO constraints at all : S1  (severity 0.85, score 1.0000)
   EXIT CODE: 0

2. Vector store deleted first  (proves "no manual steps" rather than assuming it)
   $ rm -rf src/rag/chroma_db && .venv/bin/python run_demo.py
   No vector store — chunking and embedding locally (no API call)...
     chunks kept: 480
     Indexed 480 chunks into 'flood_guidelines'
   top hit: ndma_flood_guidelines.pdf, page 86  (cosine distance 0.3567)
   RECOMMENDED SHELTER : S4
   EXIT CODE: 0

3. Failure path  (a broken stage must not exit 0)
   $ env -u GEMINI_API_KEY .venv/bin/python run_demo.py --refresh-constraints
   GEMINI_API_KEY: NOT SET — required, because constraints must be generated.
   FAILED: preflight
   EXIT CODE: 1
```

Every factual claim in the README was checked against the repo before writing it — page
count (168), byte size (6,120,219), SHA-256, chunk count (480), model id
(`gemini-3.6-flash`), allowed set (S4, S5), citations verified (7/7), and the pinned
dependency versions.

### Dependencies

None added. `run_demo.py` only orchestrates existing modules.

### Real vs. simplified

The README is the authoritative statement of this and contains the full table. In short:
the NDMA document, every quoted clause, and the 2018 Kerala background are real; the
grid, the shelters and every number attached to them are fictional; the verdicts are a
language model's judgements about fictional shelters.

### Commit

See `git log` for the hash of *Step 6: end-to-end runner and README*.

---

## Post-demo — making the claims defensible

**Goal.** Every claim the prototype made rested on **one hand-built scenario that was
tuned to produce the desired result**. This work replaces assertions with measurements.
Full write-up in `EVALUATION.md`; this entry records what changed and what it cost.

### Added

| Path | Purpose |
| --- | --- |
| `src/eval/generate_scenarios.py` | 60 seeded held-out scenarios, distribution declared in the output file. |
| `src/eval/baselines.py` | Random / nearest / max-capacity / greedy, constrained and unconstrained. |
| `src/eval/run_study.py` | The ablation study and baseline table. |
| `src/eval/constraint_agreement.py` | LLM-vs-safety-rule agreement, and the retrieval ablation. |
| `data/eval_scenarios.json` | Generated, seeded held-out suite consumed by the evaluation runners. |
| `data/eval_results/ablation_study.json` | Policy/baseline and constrained/unconstrained measurements. |
| `data/eval_results/constraint_agreement.json` | Aggregated LLM agreement and retrieval-ablation results. |
| `data/eval_results/constraint_agreement_cache.json` | Per-scenario resumable cache for quota-limited LLM evaluation. |
| `tests/` (5 files, 43 tests) | Real invariants, offline, 0.18 s. |
| `pytest.ini` | Pytest configuration, including the project import path. |
| `.github/workflows/ci.yml` | Runs those tests with **no** API key. |
| `EVALUATION.md` | Method, every table, and the honest reading of each. |

### What the measurements showed

- **The constraint layer works, measurably.** Unsafe picks fall from **40% to 7%** across
  60 scenarios, and all four residual failures are scenarios where *no* safe shelter
  existed. The single anecdote is now a rate.
- **RL is not justified on this task.** The reward is fully computable, so greedy-argmax
  *is* the oracle: **93%** versus the policy's **73%**. A 5× longer run gave 72% — a
  plateau, not a budget problem.
- **The LLM errs safely.** Zero false-allows (unsafe shelter permitted) against six
  false-excludes (usable shelter barred) across 21 verdicts. **At n=63 (below) this
  became 0 false-allows against 20 false-excludes.**
- **Retrieval does not change the verdicts — it makes them evidenceable.** 0/21 verdicts
  flipped when retrieval was removed, but verbatim-verifiable citations fell from 21/21
  to 0/21. **This was later overturned at n=63 — see the entry below.**

### A bug the evaluation found that the demo could never have

The policy scored 45% optimal on held-out scenarios versus 94% on its own training
distribution, with near-identical marginal feature distributions. The cause was visible
only in *which* shelters it picked: **S6 and S7 zero times in 60 scenarios**, where the
oracle picked them 17 times.

`_perturb()` kept `status = base["status"]`, and S6 is `at_capacity` while S7 is
`closed_structural_damage` — so those two slots were masked out in **every training
episode**. The policy learned slot identity instead of the features. Drawing every
attribute independently fixed it: **45% → 73%**, S6/S7 picks **0/0 → 7/8**.

This was invisible on the demo scenario and would have stayed invisible without a
held-out suite.

**Honest consequence:** the retrained policy picks **S5** (0.650) on the demo scenario
rather than the optimal **S4** (0.724). The configuration was chosen on held-out
performance, **not** by retraining until the demo looked right. The dashboard now shows
`SUBOPTIMAL` and names the better shelter instead of claiming "best available".

### A hard limit worth knowing

`gemini-3.6-flash` free tier allows **20 requests per DAY**
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) — per day, not per minute. At two
calls per scenario that caps the LLM study at 10 scenarios/day, which is why the
agreement and ablation results rest on 3 scenarios. The runner caches per scenario,
survives quota errors without losing work, and resumes on a later day. (It was resumed on
2026-09-04 — see the entry below.)

### How it was verified

```
run_demo exit: 0
43 tests passed (offline, no API key)
dashboard: page errors none · shows SUBOPTIMAL · recommends S5
scenario generation: deterministic (regenerated and diffed)
```

### Commit

See `git log` for the evaluation commits.

---

## 2026-09-04 — Resuming the LLM study, and the conclusion it overturned

**Goal.** Spend a day's free-tier quota extending the smallest sample in the project: the
LLM-agreement and retrieval-ablation study, which rested on 3 scenarios because the cap is
20 requests per day.

### What was run

`src/eval/constraint_agreement.py`, unchanged, twice — it resumes from its per-scenario
cache. No new code was written for this; the runner was built to be resumable and it was.

Scenarios scored went **3 → 9** (of an intended 10), verdicts **21 → 63**. `eval-009`
remains unscored: the daily cap landed mid-scenario, after the retry loop had waited
through nine 429s over ~9 minutes.

### The finding — a previous conclusion did not survive

`EVALUATION.md` §4 previously said, flatly, that **retrieval does not change the
verdicts** (0 of 21 flipped). At 63 verdicts:

| | n=21 (2026-09-02) | n=63 (2026-09-04) |
| --- | --- | --- |
| verdicts flipped without retrieval | 0 (0%) | **7 (11.1%)** |
| flips on an **unsafe** shelter | 0 | **0** |
| agreement with the safety rule | 71.4% | 68.3% |
| false-allow (unsafe permitted) | 0 | **0** |
| false-exclude (usable barred) | 6 | 20 |
| citations verifiable verbatim | 21/21 → 0/21 | **63/63 → 0/63** |

All 7 flips are on shelters the safety rule considers **safe** — 5 that retrieval allowed
and the ablation barred, 2 the other way. **Zero flips on an unsafe shelter**, so the
safety property is untouched: every unsafe shelter was excluded in both conditions.

The corrected claim is narrower than the old one and survives the larger sample:
**retrieval does not change the safety decisions; it changes some marginal cost decisions,
and it changes whether any decision can be evidenced at all.**

The flips are concentrated in 2 of the 9 scenarios (5 in `eval-003`, 2 in `eval-004`), so
11.1% is not a uniform noise floor. That concentration is itself a caveat and is recorded
as one.

> **Why this entry matters more than the numbers in it.** The overturned claim was
> repeated in five documents and in `DEVELOPMENT.md`'s "findings that contradict the spec"
> list — it had become one of the project's headline results. It was produced by a sample
> one third the size. Everything else in `EVALUATION.md` rests on samples of the same
> order, and should be read with that in mind.

### Two failure modes that look like quota exhaustion and are not

Recorded because the runner's own message misattributes the first one:

1. **`503 UNAVAILABLE`** — "this model is currently experiencing high demand." Transient
   overload, not the cap. It stopped the run after 6 scenarios; re-running resumed from
   cache and continued straight through.
2. **A DNS resolution failure** (`nodename nor servname provided`) during the quota-wait
   loop.

The runner stops cleanly and keeps its cache on any API exception, which is right. Its
message attributing the stop to the daily cap is not always right.

### Also verified that day

One live end-to-end constraint call on the demo scenario (`gemini-3.6-flash`, 1 attempt,
7/7 citations verified verbatim). **All seven verdicts matched the committed cache
exactly**, confirming `data/constraints_output.json` is a faithful recording of the live
pipeline rather than a divergence from it. Written to a scratchpad file; the committed
cache was asserted byte-unchanged.

One difference worth noting: that run used **4 distinct excerpts across 7 constraints**,
where the committed cache uses 7 distinct ones — a partial regression of the
citation-specificity problem fixed in Step 3. Verdicts are stable run to run; the choice
of supporting quote is not.

### Files changed

`EVALUATION.md` §3, §4, the quota section and the limitations list; the derived claims in
`README.md`, `DEVELOPMENT.md`, `REVIEW_NOTES.md` and `DEMO_SCRIPT.md`; and the two files under
`data/eval_results/`.

### Commit

See `git log` for *Resume the LLM study at n=63*.

---

## 2026-09-05 — Phase 0 and Gate 1A (`EXPANSION_PLAN.md`)

**Goal.** Preserve v1, then answer the one question that decides whether Phase 1 is worth
building: **would a multi-resource allocation task actually be harder than greedy?** v1's
central negative finding is that its reward is a closed-form function of one observation,
so greedy-argmax *is* the oracle and RL cannot win. Adding resources does not
automatically fix that.

### Phase 0 — preserve the working demo

| Path | Purpose |
| --- | --- |
| tag `v1-capstone-demo` | The evaluated single-decision system. Verified at tag: `run_demo.py` exit 0 (recommends S5, unconstrained S1), 43 tests pass. |
| branch `v2-resources` | All expansion work. `main` is untouched. |
| `EVALUATION_V1.md` | Frozen copy of the v1 evaluation, with a banner stating that v2 numbers measure a different task, reward and oracle and **must not** be shown side by side with these. |

### Gate 1A — the decision experiment

| Path | Purpose |
| --- | --- |
| `scripts/greedy_check.py` | Throwaway. Not part of the package, imported by nothing. Builds tiny allocation instances, solves them **exhaustively**, and measures how often hand-written heuristics hit the true optimum. |
| `data/eval_results/gate1a_*.json` | Results, with the generation distribution declared inside each file. |

The proposed task carries all three non-separability sources: **complementarity** (a
shelter protects nobody until it holds a minimum bundle of *every* resource, so the first
delivery is worth exactly zero), **contention** (one finite depot), and
**time-dependence** (scripted severity paths, reward accruing per timestep).

**A deliberate departure from the plan's method.** `EXPANSION_PLAN.md` §1.2 names
`myopic_greedy` as the comparison. Measured against only that, the gate passes easily —
and would have green-lit a rebuild that a 20-line heuristic beats. So four heuristics were
written, including `bundle_aware`, which sees complementarity, the horizon and (in variant
B) transit time, and **the gate is decided on the strongest of them**. A gate decided
against a strawman is worse than no gate.

### Result 1 — the plan's proposed design fails the gate

At the prescribed size (3 cells, 2 resources, 3 timesteps):

| policy | optimal | mean gap | median gap |
| --- | --- | --- | --- |
| `random_allowed` | 8.5% | 638.6% | 162.1% |
| `myopic_pure` | 33.0% | 141.2% | 91.4% |
| `myopic_tiebreak` | 62.0% | 432.1% | 0.0% |
| **`bundle_aware`** | **100.0%** | **0.0%** | **0.0%** |

**200 of 200 instances solved exactly by a hand-written heuristic.** By the plan's own
threshold table (>95% → *stop, strengthen the design*), Phase 1 as specified would have
reproduced v1's finding for far more work.

### Result 2 — but the verdict was an artifact of instance size

Brute force forces tiny instances, and at 3 timesteps with one delivery per step only a
single bundle can ever be completed, so "pick the best completable bundle" is trivially
optimal. Re-running the same design at larger horizons:

| size | 3×3 | 3×4 | 3×5 | 4×5 | 4×6 |
| --- | --- | --- | --- | --- | --- |
| `bundle_aware` optimal | 100.0% | 99.5% | 98.0% | 95.0% | 91.7% |

It degrades, but slowly — even at 4×6 the heuristic is 91.7% optimal with a 0.4% mean
gap. **That is less headroom than v1 already had** (greedy 93% vs the policy's 73%), so
building Phase 1 on this design would have been a poor bet.

### Result 3 — one design change fixes it

Per §1.1's instruction to strengthen the design, **variant B adds per-cell delivery lag**:
a dispatch to cell *c* arrives `lag[c]` timesteps later, so goods sit in transit and the
depot can supply another cell meanwhile. This is physical — it is travel time, which v1
already models — and it creates scheduling structure that per-bundle greedy cannot see.

| size | 3×3 | 3×4 | 3×5 | 4×5 | 4×6 |
| --- | --- | --- | --- | --- | --- |
| A — no lag | 100.0% | 99.5% | 98.0% | 95.0% | 91.7% |
| **B — delivery lag** | 100.0% | 97.0% | **79.3%** | **61.0%** | **48.3%** |

Full table for variant B at 4×6 (60 instances, 5.77 M leaves brute-forced):

| policy | optimal | mean gap | median gap | p90 gap |
| --- | --- | --- | --- | --- |
| `random_allowed` | 0.0% | 1224.9% | 201.3% | 2009.3% |
| `myopic_pure` | 6.7% | 839.2% | 186.0% | 1217.7% |
| `myopic_tiebreak` | 40.0% | 172.2% | 16.5% | 435.3% |
| **`bundle_aware`** | **48.3%** | 71.2% | **1.1%** | 56.4% |

### The honest reading of that 48.3%

**Do not report it as "the heuristic fails half the time."** Its **median gap is 1.1%** —
on most instances it is near-optimal and simply misses ties. The headroom is in the tail:
p90 gap 56.4%, and a handful of instances where it is catastrophically wrong. So the
finding is *"a good heuristic is usually nearly right and occasionally very wrong"*, which
is a reasonable place for a learned policy to add value, but **not** a promise that RL will
win. v1's lesson stands: this is a hypothesis to be measured at Gate 1B, not a result.

### Verdict

- **Do not build variant A.** It is greedy-solvable, exactly like v1.
- **Build variant B**, with delivery lag, and size instances at **≥4 cells × ≥5–6
  timesteps**. Below that the task cannot discriminate between planning and greed.
- The 3×3 size prescribed in `EXPANSION_PLAN.md` §1.2 is **too small to run this gate on**.
  Had the gate been run only at that size, as written, it would have returned a confident
  and misleading STOP.

### How it was verified

Exhaustiveness is asserted, not assumed: every instance's search tree is independently
recounted and the counts must match; the best plan is re-scored and must reproduce its own
value; and no heuristic may exceed the brute-force optimum on any instance (the plan's own
§1.8 invariant). 5.77 M leaves at 4×6. Disabling lag reproduced the pre-refactor numbers
**exactly**, confirming the transit rewrite changed nothing else.

One bug found and fixed in the harness itself: the declared generation distribution was
snapshotted at import from the default config, so a `--size` run would have written a
distribution block describing a different experiment than the one it ran.

### Real vs. simplified

Everything in this experiment is **fictional** — populations, severities, demands, stock
and lags are invented, as in v1. Nothing here is real data, and no claim about the world
is made. The measurements of heuristic-versus-optimum are real.

### Commit

See `git log` on branch `v2-resources`.

---

## 2026-09-05 (later) — Gate 1A.5 stops Phase 1, and the metric decision is why

**Goal.** Before building anything from `PHASE1_PLAN.md` §3, characterise the tail that
Gate 1A's headline rested on. Gate 1A cleared variant B because `bundle_aware` scored
**48.3% optimal** at 4×6 — but with a **median gap of 1.1%**, which is the signature of a
statistic that is not measuring what it appears to.

### Added

| Path | Purpose |
| --- | --- |
| `scripts/tail_check.py` | Generates 200 instances at 4×6 with lag, brute-forces each, and runs six policies **with per-decision wall-clock timing**. |
| `scripts/tail_analysis.py` | The four Q's, including Q3's shuffled-label null and Q4's latency comparison. |
| `scripts/retrieval_q2.py` | The pre-registered marginality test (§4 below). |
| `data/eval_results/gate1a5_*.json`, `retrieval_q2_marginality.json` | Results. |

Three method fixes were **pre-registered and committed at `213cb3b`, before any of these
scripts were written**. That commit order is the evidence, and for the retrieval test it
is the whole point.

### Q1 — the headroom was largely a denominator artifact

| policy | % optimal | ratio-gap mean | **normalised score (median)** | norm p10 |
| --- | --- | --- | --- | --- |
| `random_allowed` | 0.5% | 641.7% | 0.000 | 0.000 |
| `myopic_tiebreak` | 38.5% | 135.6% | 0.905 | 0.045 |
| `bundle_aware` | 48.5% | 49.7% | **0.992** | 0.772 |

**`bundle_aware` was already capturing 99.2% of the achievable headroom.** The "48.3%
optimal" that cleared Gate 1A counted a 0.1% miss identically to a 2000% miss. Under the
metric declared in `PHASE1_PLAN.md` §2 — *declared before these numbers existed* — the
gate that produced the plan would not have passed as written.

### Q2 — the improvement is concentrated, but small

46.4% of all remaining regret sits in the worst 10% of instances (28.1% in the worst 5%),
and mean regret is 17.3% of the mean optimum. Concentrated, and above the 5% floor — so
on this evidence alone there was still something to chase.

### Q3 — structure exists, but barely clears its null

| | AUC |
| --- | --- |
| real (5-fold CV, top-decile regret) | 0.624 |
| shuffled-label null, mean | 0.496 |
| shuffled-label null, 95th percentile | 0.612 |
| permutation *p* | 0.025 |

Separated from the null, but by 0.012 of AUC. **Reported as weak.** Without the null this
would have been written up as "AUC 0.62, the tail is structured", which would have been an
overstatement — the guard earned its keep on the first use.

### Q4 — the decisive one: a 40-line planner closes it, at affordable latency

| policy | normalised score (median) | % optimal | ms/decision | × vs policy |
| --- | --- | --- | --- | --- |
| `bundle_aware` | 0.992 | 48.5% | 0.012 | 0× |
| **`lookahead_k2`** | **1.000** | 89.5% | **1.641** | **13×** |
| `lookahead_k3` | 1.000 | 92.5% | 8.353 | 67× |
| `beam_w5` | 0.379 | 13.5% | 0.210 | 2× |

Reference: v1's `MaskablePPO.predict()` measured at **0.124 ms/decision**.

**A 2-step lookahead planner scores a median normalised 1.000 with a p10 of 0.991** — even
its bottom decile captures 99.1% of achievable headroom. There is no tail left for a
learned policy to win.

### The verdict, and a correction to my own stop rule

The pre-registered rule said *≥95% at ≤10× latency is a clean stop; at ≫100× it is a
judgement call*. The measurement landed at **13×**, and the script therefore printed
"JUDGEMENT". **On inspection the rule was written in the wrong unit.** 13× of an unusually
fast baseline is **1.64 ms in absolute terms**, against a re-planning loop that runs in
seconds. That is comfortably affordable, so the right reading is the *clean stop*, not the
judgement branch. A multiple of a forward pass was the wrong denominator; the deadline is.

> **GATE 1A.5: STOP. Do not build `PHASE1_PLAN.md` §3.** The task is solved, to within a
> fraction of a percent of the optimum, by ~40 lines of lookahead at 1.6 ms per decision.
> Training a policy would re-run v1's experiment at greater cost.

### What would change this answer

The planner has the **exact dynamics** — deterministic severity paths and known lags — so
it can search a perfect model. That is a real advantage and it is legitimate here only
because this task hands it over. If severity became stochastic or the lags unknown, the
planner's model advantage disappears and the case for a learned policy genuinely returns.
**That, not more resources, is the direction with an open question in it.**

### §4 — the retrieval question, pre-registered and failed

`retrieval_q2.py`, per the definition committed at `213cb3b`: flips do **not** concentrate
near the safety rule's boundaries. Median margin 0.322 for flipped versus 0.271 for
unflipped — the opposite direction. Odds ratio 0.42, Fisher *p* = 0.90, Mann–Whitney
*p* = 0.61. Under the pre-registered decision rule **the sharpened claim is not made**, and
the 11.1% in `EVALUATION.md` §4 stays unexplained variance. With 7 events this fails to
show presence and cannot establish absence.

Recorded post-hoc and **explicitly not tested**: all 7 flips fall in the "operational,
below the severity threshold, but cannot take the whole population" group — 7 of 24 inside
it, 0 of 39 outside. No *p*-value is attached, because the grouping was chosen after seeing
the data. It becomes a pre-registered hypothesis for a future run.

The construct was wrong in **form**, not subject: it measured proximity to a boundary when
the pattern looks categorical — a region, not its edge.

### The pattern worth noticing

Three plans in a row have now been overturned by measuring rather than assuming: v1's RL
justification (§2 of `EVALUATION.md`), the "retrieval changes nothing" claim (n=21 → n=63),
and now Phase 1 itself, stopped by a gate that cost a day. **The measurement discipline is
the deliverable.** The systems it keeps rejecting are the evidence that it works.

### Commit

See `git log` on branch `v2-resources`.

---

## 2026-09-06 — Repository inventory and local-metadata cleanup

**Goal.** Bring this document's overview in line with the complete repository and remove
machine-specific residue without disturbing the runnable environment.

### Documentation brought into the inventory

The overview now explicitly records additions that existed in git but were previously
only described indirectly or in later prose:

- `REVIEW_NOTES.md` — a compact defence sheet for likely reviewer questions.
- `DEMO_SCRIPT.md` — a five-minute, click-by-click dashboard walkthrough.
- `EVALUATION_V1.md` — the frozen evaluation attached to tag `v1-capstone-demo`.
- `PHASE1_PLAN.md` — the v2 plan, now marked stopped at Gate 1A.5; its implementation
  section was intentionally never built.
- `pytest.ini`, the five test modules, the generated held-out suite, and the persisted
  evaluation result/cache files.
- The Gate 1A and Gate 1A.5 scripts and their result artifacts under `scripts/` and
  `data/eval_results/`.

The Step 1 decision table was also corrected to match the current scenario: S1 has
capacity 1,000, occupancy 100, and headroom 900. That makes it a stronger trap because
it is both the nearest shelter and large enough for the full population, while remaining
unsafe due to severe flooding.

### Cleanup

Removed local-only tool folders, `.pytest_cache/`, and project `__pycache__/` directories.
Added local tool folders and `.pytest_cache/` to `.gitignore`; Python bytecode caches were already
ignored. `.venv/` and `src/rag/chroma_db/` remain ignored but were deliberately retained
so the checked-out demo stays immediately runnable. These removed directories contained
no tracked source or evaluation data and can be recreated by their respective tools.

Historical mentions of `DEVELOPMENT.md` and other bootstrap instructions remain in earlier
entries because those sections describe the state and rules at the time each step was
built. They should not be read as the current repository inventory.

### Real vs. simplified

No scenario, source, model, or measured result changed in this maintenance step. The
inventory and cleanup describe repository state only.

### Commit

See `git log` for the repository-inventory and local-metadata cleanup commit.

---

## 2026-09-06 — V3 Phase 0: freeze, audit, and baseline

**Goal.** Create a reproducible baseline before any V3 simulator, stochastic dynamics,
planner, or RL implementation begins.

### Added

| Path / ref | Purpose |
| --- | --- |
| branch `v3-dynamic-stochastic` | Isolates V3 work without rewriting `main`, `v2-resources`, or the frozen V1 tag. |
| `V3_BASELINE.md` | Records commit/ref provenance, Python and dependency pins, test/model checks, held-out metrics, RAG state, demo output, dashboard smoke status, artifact hashes, and limitations. |

The branch starts at `d998aac`, the tip of `v2-resources` after repository cleanup. This
is intentional: `main` remains at the V1 capstone state, while the v2 branch contains the
Gate 1A and Gate 1A.5 negative results that directly motivate V3's dynamic stochastic
design. The tag `v1-capstone-demo` still resolves to `f19cccc`.

### Dependencies

None added. All nine direct dependencies remain pinned in `requirements.txt`; Phase 0
records that the project has no transitive lockfile.

### How it was verified

```text
43 passed in 0.31 s
run_demo.py: exit 0 in explicit Hugging Face offline mode
model load: MaskablePPO, observation Box(28), action Discrete(7)
Chroma collection: flood_guidelines, 480 chunks
Streamlit: localhost health "ok"; initial HTML returned
Streamlit AppTest: 0 exceptions, 1 title
```

The offline demo used the committed PDF, local Chroma index, cached Gemini output, and
committed checkpoint. It recommended S5 with constraints and S1 without them, exactly as
the documented baseline states. No Gemini call or artifact rebuild occurred.

### Measured results frozen

From the unchanged 60-scenario evaluation artifact:

| Measure | Result |
| --- | ---: |
| constrained RL held-out optimal rate | 73.33% (44/60) |
| constrained greedy-oracle optimal rate | 93.33% (56/60) |
| unsafe picks with constraints | 6.67% (4/60) |
| unsafe picks without constraints | 40.00% (24/60) |

The RAG baseline remains one distinct 168-page authoritative document, 480 page-scoped
chunks, cached `gemini-3.6-flash` output, and 7/7 verbatim-verified demo citations.

### Real vs. simulated

The NDMA document and its provenance are real. The flood scenario and shelters are
fictional. The constraint verdicts are model-generated. Test, retrieval, model-load,
dashboard, and held-out figures reported here were measured from the current checkout.

### Known limitations

- The normal demo path tries Hugging Face metadata `HEAD` requests before using its local
  cache; explicit `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` avoids that delay.
- Phase 0's dashboard check proves server health and exception-free app execution, not a
  new pixel-level accessibility audit.
- V1's policy remains worse than its greedy oracle. Phase 0 preserves that negative
  result; it does not begin the V3 formulation intended to address it.

### Commit

See `git log` for *V3 Phase 0: freeze baseline and create expansion branch*.

---

## 2026-09-06 — V3 Phase 1: pre-register evaluation and decision gates

**Goal.** Freeze how V3 will be judged before its simulator, stochastic parameters,
planners, reward, or PPO results exist.

### Added

| Path | Purpose |
| --- | --- |
| `V3_EVALUATION_PLAN.md` | Pre-registers metrics, paired stochastic evaluation, baseline hierarchy, statistical reporting, PPO materiality rules, conclusion labels, governance, and the pre-PPO planning stop gate. |

### Dependencies

None. This phase adds scientific protocol only.

### Frozen decisions

- The primary operational metric is `NSU-practical`, a ratio of paired mean episode
  returns relative to five-seed `random_valid` and the strongest validation-selected
  practical planner.
- Small exact-oracle results use the separate label `NSU-exact`. Exact and practical
  normalization may not be pooled or shown as one number.
- Near-zero denominators produce `NA`, never an adjusted or clipped score.
- The principal PPO comparator is the strongest eligible practical non-learned baseline,
  not whichever weak baseline PPO beats most easily.
- Final PPO reporting uses five independent training seeds; three is permitted only by a
  dated, pre-results resource amendment.
- The V1 demo scenario is barred from checkpoint, reward, feature, hyperparameter,
  baseline, and success decisions.

PPO can support a claimed decision contribution only if it clears at least one material
threshold: +0.02 `NSU-practical`, at least 5% lower exposure, or +0.02 tail-normalised
utility. The paired bootstrap interval must support the claimed direction, the result
must survive aggregation across training seeds, and unsafe-dispatch rate may not increase.

The conclusion vocabulary is fixed in advance: **YES** for a combined material gain,
**MIXED** for a pre-registered regime/tail/robustness gain only, and **NO** when planning
remains sufficient or a gain requires worse safety.

### How it was verified

The metric computability audit maps every required value to a planned simulator ledger:
population, arrivals, hazards, shelter capacity/reservations, route events, action masks,
travel time, reward components, latency, and RNG provenance. `git diff --check` passes.

Semantic choices that cannot honestly be made before the relevant implementation—route
hazard aggregation, post-arrival shelter degradation, terminal in-transit handling, hard
safety thresholds, reward bounds, and final suite replication count—are explicitly marked
**to be fixed before experiment** in their owning phases.

### Real vs. simulated

No data or result was generated. This phase defines a future evaluation of simulated V3
disaster dynamics. Existing real NDMA provenance, model-generated constraints, and
measured V1/V2 results remain untouched.

### Known limitations

- Exact suite sizes depend on measured runtime and must be frozen before final results.
- Reward-dependent denominator scale cannot be instantiated until the reward specification
  declares a finite theoretical range.
- The protocol reduces researcher degrees of freedom but cannot eliminate all design
  judgment; every later amendment must remain visible and dated.

### Commit

See `git log` for *V3 Phase 1: pre-register evaluation metrics and decision gates*.

---

## 2026-09-07 — V3 Phase 2: dynamic scenario data contract

**Goal.** Define the immutable, versioned inputs required by a future multi-zone,
multi-shelter, multi-timestep, route-aware stochastic evacuation simulator, without
implementing any simulator behavior.

### Added

| Path | Purpose |
| --- | --- |
| `src/sim/__init__.py` | Public exports for the V3 scenario contract. |
| `src/sim/schemas.py` | Frozen standard-library dataclasses, enums, validation, canonical ordering, and JSON load/dump helpers for schema `3.0`. |
| `data/scenarios_v3/example_v3_scenario.json` | Two-zone, two-shelter, four-route synthetic development fixture; one route is explicitly unreachable. |
| `tests/test_v3_schemas.py` | 52 schema tests covering validation, references, serialization, immutability, provenance, ordering, and V1 separation. |

### Dependencies

None. Standard-library dataclasses were chosen instead of Pydantic because the contract's
validation is compact and explicit; adding a new runtime validation dependency would not
buy enough here.

### Schema decisions

- `schema_version` must equal `"3.0"`; V1 input is rejected with an explicit unsupported-
  version error and continues to load through the unchanged V1 loader.
- The top-level immutable definition contains provenance, time, zones, shelters, aggregate
  fleet limits, route/network definitions, hazard-scale metadata, a Phase 4 stochastic-
  parameter interface, and optional policy/evidence version references.
- Locations use exactly one representation: abstract node, future graph node, or future
  coordinates. The development fixture uses abstract nodes and invents no geography.
- `vulnerable_population` and `medical_priority_population` are potentially overlapping
  operational groups. Each may not exceed total population, but their sum may.
- Shelter status is the explicit enum `OPEN`, `RESTRICTED`, or `CLOSED`; V1's more specific
  strings are not silently collapsed or migrated.
- Available shelter capacity is derived from total capacity minus initial occupancy. No
  authoritative `capacity_remaining` is serialized.
- Reachable routes require positive mean travel, nonnegative standard deviation, and a
  closure probability in `[0,1]`. Unreachable routes use `reachable: false` and `null`
  metrics, never a fake large travel-time sentinel.
- Canonical zone, shelter, and route views sort by stable IDs without mutating or
  reordering the source JSON.
- The root seed is metadata for future independently derived Phase 4 streams. Loading the
  schema performs no random draw.

Mutable episode quantities—current population/severity/time, in-transit groups, shelter
occupancy/reservations, road closures, and pending arrivals—are deliberately absent.

### Validation invariants

Validation covers nonempty/unique identities, nonnegative seed and populations, subgroup
bounds, initial remaining population, shelter capacity/occupancy, normalized severity and
accessibility, fleet consistency, route IDs and references, reachable/unreachable route
semantics, normalized closure probability, valid time configuration, provenance enums,
unknown fields, and the supported schema version.

### How it was verified

```text
V3 schema tests: 52 passed in 0.14 s
combined suite: 95 passed in 0.34 s
legacy V1 tests: 43 unchanged and passing
fixture JSON syntax: PASS
example load: 2 zones, 2 shelters, 4 routes (3 reachable)
canonical order: Z1/Z2 and S1/S2
JSON dump/reload semantic equality: True
```

The current V1 scenario, model, cached constraints, and evaluation artifacts were checked
for accidental changes and remain untouched.

### Real vs. simulated

The example is prominently labeled **SIMULATED / FICTIONAL DEVELOPMENT FIXTURE — NOT
REAL FLOOD OR SHELTER DATA**. Its populations, shelters, initial severities, travel
distributions, closure probabilities, accessibility scores, abstract nodes, and routes
are invented solely to validate the schema. No real geospatial network or forecast is
present. The provenance enum can separately label components `REAL`, `SIMULATED`,
`FICTIONAL`, `MODEL_GENERATED`, or `MEASURED` when later scenarios legitimately mix them.

### Semantics deferred to later phases

- capacity reservation timing and arrival/overbooking behavior;
- dispatch batch and partial-batch behavior;
- timestep transition ordering and terminal in-transit handling;
- exact LOW/MEDIUM/HIGH stochastic parameters and forecast semantics;
- flood evolution, road closure, travel-noise, and shelter-degradation dynamics;
- restricted-shelter hard-rule interpretation and other safety thresholds;
- reward components and weights.

### Known limitations

- This is a data contract, not a dynamic simulator; nothing transitions over time yet.
- Stochastic fields are typed placeholders and deliberately `null` in the fixture until
  Phase 4 freezes their meaning and values.
- `GRAPH_NODE` and `COORDINATES` are supported representations, but no graph, OSM data,
  shortest-path calculation, or real coordinate is included.
- `RESTRICTED` has no runtime intake semantics until the hard-safety phase.

### Commit

See `git log` for *V3 Phase 2: dynamic scenario schema and validation*.

---

## 2026-09-07 — V3 Phase 3: deterministic multi-step evacuation simulator

### Goal

Build and freeze the sequential logistics mechanics before uncertainty, safety policy,
reward design, planners, or RL are introduced. The simulator consumes the immutable
Phase 2 `ScenarioV3` definition and returns new immutable `EpisodeState` snapshots.

### Added

| Path | Purpose |
| --- | --- |
| `src/sim/events.py` | Semantic dispatch/WAIT actions, deterministic dispatch events, rejection codes, and serializable audit records. |
| `src/sim/state.py` | Frozen runtime zone, shelter, route, and episode snapshots, plus derived population/transit/capacity views. |
| `src/sim/transition.py` | Pure initialization, mechanical action validation, arrival processing, dispatch execution, timestep advancement, and terminal handling. |
| `src/sim/invariants.py` | Fail-fast population, capacity, reservation, event, entity-ID, nonnegative-value, and terminal-state checks. |
| `tests/test_v3_transitions.py` | 60 tests for initialization, dispatch, arrival, capacity, partial batches, routes, status, WAIT, rejection, termination, conservation, serialization, and replay. |

`src/sim/__init__.py` was modified to export the Phase 3 runtime API. No new data fixture
was necessary; tests derive clearly synthetic variants from the existing Phase 2 fixture
without writing them back to disk.

### Runtime-state model

`ScenarioV3` remains the immutable static input. `EpisodeState` separately records the
current timestep; per-zone remaining population and severity; per-shelter occupancy,
reservation, status, and severity; current route reachability/travel time; dispatch
events; safely arrived population; the configured aggregate dispatch limit and usage;
terminal state; and audit log. All collections are tuples and every transition returns a
replacement snapshot.

`people_in_transit`, total remaining population, pending dispatches, and available
capacity are derived views. Initial shelter occupants are not part of the evacuation
population and never count as newly safe arrivals.

### Capacity reservation semantics

Capacity is reserved when a dispatch is accepted:

```text
available = capacity_total - occupancy_current - capacity_reserved
```

The shelter occupancy does not change at dispatch. When the scheduled event arrives,
the same count moves from `capacity_reserved` to `occupancy_current`, so availability is
unchanged by that conversion. This prevents concurrent in-transit groups from
overbooking a destination.

### Population semantics

People leave `population_remaining` and enter the in-transit event ledger at dispatch.
They enter `people_safely_arrived` only when their arrival is processed. Phase 3 has no
failure/casualty bucket, so every accepted state must satisfy:

```text
initial_evacuation_population
= population_remaining + people_in_transit + people_safely_arrived
```

The invariant checker also reconciles each source zone against all events dispatched
from that zone; population cannot silently move between zones.

### Travel-lag semantics

Phase 3 uses only the static reachable route's `travel_time_mean`:

```text
travel_lag_steps = max(1, ceil(travel_time_mean / timestep_minutes))
arrival_timestep = departure_timestep + travel_lag_steps
```

`travel_time_std`, closure probability, and stochastic configuration are deliberately
ignored. Event IDs are deterministic and monotonic: `dispatch-000001`,
`dispatch-000002`, and so on.

### Partial-batch semantics

One semantic dispatch sends:

```text
min(vehicle_capacity, zone population remaining, shelter capacity available)
```

The count must be positive. Exact-capacity and final partial source batches are valid.
The Phase 3 API exposes one action opportunity per call and one call advances one
timestep. The schema's higher aggregate dispatch limits remain available for a future
multi-action interface; this phase executes at most one successful dispatch per step.

### RESTRICTED semantics

`CLOSED` is mechanically unavailable. `OPEN` and `RESTRICTED` are both mechanically
dispatchable in Phase 3 when population, route, fleet, travel, and capacity checks pass.
`RESTRICTED` does not yet imply a capacity multiplier or safety exclusion; Phase 5 must
freeze that policy meaning.

### Transition ordering

Each accepted call uses this fixed order:

1. Process dispatch arrivals scheduled for the current timestep, converting reservation
   to occupancy and counting people safe.
2. Apply the deterministic exogenous-update position; it is an explicit Phase 3 no-op,
   so route and hazard state do not change.
3. Reset dispatch availability for the timestep.
4. Validate the semantic action mechanically.
5. Execute a dispatch or WAIT and append audit records.
6. Advance the clock by one timestep.
7. Check completion first, then the configured horizon.
8. Assert every runtime invariant.

This makes arrivals available to the same-timestep decision while ensuring a dispatch
never arrives during its own departure step.

### Invalid-action semantics

An invalid action returns a structured `TransitionResult` with a machine-readable
rejection code and human-readable message. It does not advance time or mutate runtime
state. Validation is transactional: arrivals are first evaluated on a working snapshot,
but that snapshot is discarded if the action is rejected. The rejection audit record is
returned in the result rather than inserted into the unchanged state log; retrying a
valid action at the same timestep then processes the due arrivals exactly once.

### Terminal semantics

`ALL_EVACUATED` requires both zero remaining population and zero people in transit.
Empty zones alone do not complete an episode. After incrementing the clock, an otherwise
incomplete episode reaching `horizon_steps` terminates as `HORIZON_REACHED`; unserved
people and pending in-transit events remain explicit in the terminal snapshot and no
post-horizon arrivals are invented. Calls against any terminal state are rejected
without advancing time.

### Invariant checks

Checks run after initialization and every accepted dispatch, WAIT, arrival-containing
transition, and terminal transition. They verify:

- global and per-source population conservation;
- nonnegative zone populations, shelter occupancy/reservations/availability, and event
  group sizes;
- `occupancy_current + capacity_reserved <= capacity_total` for every shelter;
- reservations equal the active in-transit events addressed to each shelter;
- current occupancy equals initial occupants plus arrived evacuation events;
- in-transit people equal the sum of active event groups;
- runtime zone, shelter, and route IDs match the scenario;
- event IDs, lag equations, references, and terminal reasons are coherent.

### Tests and how verified

```text
Phase 3 transition suite: 60 passed
Phase 2 schema suite:     52 passed
legacy V1 suite:          43 passed
full suite:              155 passed
deterministic replay:     PASS
```

The scripted trace used the actual `example_v3_scenario.json` values:

```text
INITIAL: t=0 Z1_remaining=500 S1_occ=150 S1_reserved=0 S1_available=750 in_transit=0 safe=0
ACTION Z1->S1: dispatched=50 event=dispatch-000001 arrival_t=2
AFTER DISPATCH: t=1 Z1_remaining=450 S1_occ=150 S1_reserved=50 S1_available=700 in_transit=50 safe=0
WAIT: arrivals=0
AFTER WAIT: t=2 Z1_remaining=450 S1_occ=150 S1_reserved=50 S1_available=700 in_transit=50 safe=0
WAIT: arrivals=[('dispatch-000001', 50)]
AFTER ARRIVAL: t=3 Z1_remaining=450 S1_occ=200 S1_reserved=0 S1_available=700 in_transit=0 safe=50
```

The trace is generated from the engine, not hardcoded into application source.

### Real vs. simulated

All Phase 3 transitions operate on the Phase 2 **SIMULATED / FICTIONAL DEVELOPMENT
FIXTURE — NOT REAL FLOOD OR SHELTER DATA**. The mechanics make no forecast and add no
real Kerala geography, road network, shelter, population, or disaster event. The real
NDMA source corpus and all V1/V2 measured artifacts remain unchanged.

### Known limitations

- The transition interface intentionally permits only one action per timestep even if a
  future scenario configures a larger aggregate dispatch limit.
- Multiple routes for the same zone/shelter pair are mechanically ambiguous because the
  semantic action does not select a route; such an action is rejected rather than making
  a hidden route choice.
- Runtime-state serialization is a JSON-compatible audit view, not a checkpoint loader.
- Rejected attempts are returned as audit records but are not persisted into the
  unchanged state snapshot.

### Deferred semantics

There is still no stochastic flood model. There are still no road closures. There is no
RL environment. There is no reward function. There are no planners. There are no RAG
changes.

Also deferred are stochastic travel, route failures, shelter degradation, scripted or
sampled hazard evolution, congestion, route selection, Phase 5 safety thresholds and
evidence rules, observation/action masking, reward accounting, planning, Gymnasium/PPO
integration, and final terminal-deadline policy. `RESTRICTED` remains mechanically
allowed until the safety phase freezes its operational treatment.

### Commit

See `git log` for *V3 Phase 3: deterministic multi-step evacuation simulator*.

---

## 2026-09-07 — V3 Phase 4: stochastic flood, travel, route, and shelter dynamics

### Goal

Introduce explicit, controlled uncertainty without changing Phase 3 population,
reservation, arrival, rejection, or terminal semantics. Future policies receive current
realized state and imperfect one-step forecasts, never future realized draws.

> **All stochastic parameters in Phase 4 are synthetic modeling assumptions and are not
> empirically calibrated flood, road-closure, travel, or shelter-failure probabilities.**

### Added

| Path | Purpose |
| --- | --- |
| `src/sim/configs.py` | Frozen, validated `v3-low-v1`, `v3-medium-v1`, and `v3-high-v1` uncertainty configurations and mandatory disclaimer. |
| `src/sim/randomness.py` | Stable SHA-256 keyed uniform/normal values in five independent stochastic namespaces. |
| `src/sim/hazard.py` | Bounded regional/local flood evolution and observable one-step forecasts. |
| `src/sim/routes.py` | Pre-geospatial route-hazard proxy, closure probability, absorbing closures, route expectations, and realized travel. |
| `src/sim/stochastic.py` | Two-stage `observe()`/`step()` harness, private current latent context, shelter degradation, and stochastic transition ordering. |
| `tests/test_v3_stochastic.py` | 53 tests covering timing, RNG independence, flood, forecasts, travel, closures, shelters, pairing, leakage, invariants, and sanity results. |
| `scripts/phase4_stochastic_sanity.py` | Reproducible process-only study over fixed seeds 41000–41199. |
| `data/eval_v3/phase4_stochastic_sanity.json` | Generated LOW/MEDIUM/HIGH process diagnostics; explicitly not a policy evaluation. |

The existing schema documentation, event, state, transition, invariant, public-export,
Phase 3 regression-test, and documentation files were extended only where required. No
new scenario fixture was needed; the clearly fictional Phase 2 fixture supports all
Phase 4 mechanics.

### Arrival-timing regression

The Phase 3 convention was correct and did not require a behavior change. A dispatch with
`departure_timestep=0` and `arrival_timestep=2` is processed by the transition whose
**pre-step** state has `current_timestep == 2`. Arrival audit occurs before that timestep's
action, and the accepted post-step snapshot has `current_timestep == 3`. Both the Phase 3
and Phase 4 suites now assert those values explicitly. V1/V2 results are unaffected.

### RNG architecture

No mutable global seed and no shared draw cursor exists. Each value is a pure function of:

```text
SHA-256(
  generator-version,
  scenario root seed,
  uncertainty config ID,
  replication ID,
  subsystem namespace,
  timestep/entity/event key,
  digest lane
)
```

Uniform values come directly from stable digest bits. Standard-normal values use two
independently keyed digest lanes and the Box–Muller transform. The namespaces are
`regional_hazard`, `local_hazard`, `travel`, `route_closure`, and
`shelter_degradation`. Adding or removing one subsystem query cannot advance or shift an
unrelated subsystem because there is no sequential stream position.

The root seed remains the validated nonnegative scenario seed. `replication_id` creates a
separate repeat of the same scenario/config without mixing environment and future policy
exploration randomness.

### Exogenous versus action-conditional randomness

Exogenous values are keyed independently of actions:

- regional hazard innovation by timestep;
- local hazard innovation by entity kind, entity ID, and timestep;
- closure outcome by route and timestep;
- shelter degradation outcome by shelter and timestep.

Travel is action-conditional and is keyed by departure timestep, route ID, and deterministic
dispatch event ID. A dispatch on one policy path therefore cannot change another policy's
weather, route-closure, or shelter-degradation values. Repeating the same dispatch key
reproduces the exact travel value.

### LOW / MEDIUM / HIGH configurations

All hazard values use the normalized `[0,1]` scale. Travel noise is a fractional
multiplier; closure/degradation values are synthetic per-timestep probabilities.

| Parameter | LOW `v3-low-v1` | MEDIUM `v3-medium-v1` | HIGH `v3-high-v1` |
| --- | ---: | ---: | ---: |
| regional innovation sigma | 0.008 | 0.018 | 0.035 |
| regional persistence | 0.30 | 0.50 | 0.65 |
| local innovation sigma | 0.005 | 0.012 | 0.025 |
| directed zone drift magnitude | 0.006 | 0.008 | 0.010 |
| configured travel-noise fraction | 0.04 | 0.10 | 0.18 |
| route-hazard travel factor | 0.20 | 0.30 | 0.45 |
| base closure multiplier | 0.35 | 0.70 | 1.15 |
| hazard-to-closure strength | 0.015 | 0.035 | 0.070 |
| maximum closure probability | 0.12 | 0.25 | 0.40 |
| restricted / closed status thresholds | 0.78 / 0.95 | 0.68 / 0.90 | 0.60 / 0.84 |
| maximum per-step degradation coefficient | 0.006 | 0.018 | 0.040 |

Travel multipliers are clipped to 0.60–1.60, 0.55–1.80, and 0.50–2.00 respectively.
These configs were selected for interpretable, bounded, overlapping regimes—not to favor
any future algorithm. Every active value, unit/scale, validation range, and description is
version controlled.

### Flood model

At timestep `t > 0`, the simulator computes:

```text
regional_t = persistence * regional_(t-1) + keyed Normal(0, regional_sigma)
severity_next = clip(current + directed_drift + regional_t + keyed_local_noise, 0, 1)
```

The regional term correlates entity movement and local terms prevent identical paths.
Phase 4 explicitly interprets `RISING`/`FALLING` zone trend metadata as the sign of the
config's small deterministic drift; `STEADY` and `UNKNOWN` add no drift. Shelter severity
has no invented trend drift. This is a synthetic normalized process, not physical flood
forecasting.

### Forecast semantics

Each decision view includes current/previous severity, observed recent change, next-step
forecast mean, and configured forecast uncertainty. At `t=0`, the zone forecast uses the
declared trend direction and shelters use persistence of their initial level. Later means
extrapolate only the most recently observed change. Forecast standard deviation is the
root-sum-square of configured regional and local innovation sigmas.

The forecast function accepts no random stream and cannot inspect the latent regional
component or next keyed innovation. Forecasts are therefore reproducible and imperfect,
and uncertainty increases from LOW through HIGH.

### Travel model

Until graph routes exist, route hazard is the maximum of current source-zone and
destination-shelter severity. It is explicitly a simplified endpoint proxy, not measured
inundation along a road.

```text
expected travel = base mean * (1 + route_hazard_factor * hazard_proxy)
noise sigma = config travel fraction + 0.25 * (static travel std / base mean)
realized travel = expected travel * clipped(1 + keyed Normal(0, sigma))
```

Realized travel is finite and positive and retains Phase 3's
`max(1, ceil(realized_minutes / timestep_minutes))` lag rule. Policy observations expose
the expected time, uncertainty, proxy, and closure estimate—but not the travel realization
for an action that has not occurred. Accepted events/audit records retain the realized
value for later explanation.

### Route-closure model

For statically reachable routes:

```text
p_close = clip(
  base_closure_probability * regime_multiplier
  + hazard_to_closure_strength * route_hazard_proxy,
  0,
  maximum_closure_probability
)
```

The function is monotonic in hazard and always bounded. Closures start at `t=1`, are
exogenous/keyed per route/timestep, and are absorbing for the rest of Phase 4. Closure
audits record route ID, current hazard proxy, modeled probability, timestep, and config ID.
An already-departed dispatch keeps its realized arrival schedule if its route later
closes; closures block new dispatches only.

### Shelter degradation

Shelter severity can cause monotonic `OPEN -> RESTRICTED -> CLOSED` degradation through
synthetic status thresholds plus a small severity-scaled keyed degradation probability.
There is no automatic reopening. `capacity_total` never changes.

`RESTRICTED` remains mechanically usable, exactly as Phase 3 froze it. `CLOSED` blocks new
dispatches. Existing reservations remain valid and their arrivals are processed even if
the destination later closes; no evacuee is silently dropped or rerouted.

### Transition timing

The stochastic harness has an explicit two-stage interface so an action can react to the
current realization:

1. `observe()` prepares the timestep: arrivals first; then, for `t > 0`, flood evolution,
   route estimates/closures, and shelter degradation; then public forecasts.
2. The returned detached policy view contains that updated current state and forecast.
3. `step(action)` validates against exactly the prepared state, realizes travel only for
   an accepted dispatch, writes audit records, increments time, applies terminal rules,
   and checks invariants.

At `t=0`, initial scenario severities, route reachability, and shelter statuses are
preserved for the first decision; forecasts and route expectations are available, but no
hazard shock, closure, or shelter degradation is applied. Invalid actions transactionally
discard the prepared changes, do not advance time, and reproduce the same keyed current
state on retry.

### Leakage prevention and paired-policy fairness

Latent state consists only of the current regional AR(1) component and keyed-stream
metadata held by the simulator harness. There is no pre-generated future schedule.
`EpisodeState.to_policy_observation()` returns a fresh detached structure containing only
current/past values, current availability, and forecasts. It omits root seed, replication
metadata, latent regional state, future hazard/closure/shelter outcomes, action-conditioned
travel realizations, and the audit log.

The simulator exposes current internal metadata only through a separately named diagnostic
snapshot that contains no future schedule. Tests mutate an observation without affecting
runtime state, scan policy serialization for prohibited fields, and compare different
action sequences under the same seed/config. Shared exogenous hazard, route, and shelter
paths remain identical; only the path that dispatches receives a travel realization.

### Process sanity statistics

The committed artifact embeds each complete config, uses 200 fixed seeds per config
(41000–41199), the fictional Phase 2 fixture, and WAIT at every timestep. Potential
action-keyed travel is sampled only for process diagnostics. This is **not a performance
benchmark** and contains no policy result.

| Statistic | LOW | MEDIUM | HIGH |
| --- | ---: | ---: | ---: |
| mean absolute severity change | 0.00848 | 0.01925 | 0.03662 |
| severity clipping frequency | 0.0000 | 0.0123 | 0.0958 |
| fraction initially reachable routes ever closed | 0.2967 | 0.5017 | 0.7183 |
| shelter restriction transitions / shelter-episode | 0.0075 | 0.0075 | 0.0600 |
| shelter closure transitions / shelter-episode | 0.0100 | 0.0175 | 0.0725 |
| mean realized/base travel ratio | 1.1263 | 1.1921 | 1.2871 |
| travel-ratio standard deviation | 0.0926 | 0.1729 | 0.2946 |
| mechanically actionable timestep fraction | 0.9971 | 0.9696 | 0.8442 |

All regimes produce some closures without closing every route; clipping is limited; HIGH
does not immediately eliminate almost all choices; travel stays finite; and every episode
has at least one mechanically valid opportunity. The ordered severity movement, travel
variability, and closure frequency confirm that the config labels broadly behave as
intended without asserting episode-by-episode dominance.

### Tests and how verified

```text
Phase 4 stochastic suite: 53 passed
Phase 3 transition suite: 60 passed
Phase 2 schema suite:     52 passed
legacy V1 suite:          43 passed
full suite:              208 passed
same-seed replay:          PASS
paired-action exogenous:   PASS
policy-view leakage:       PASS
```

The sanity artifact is regenerated with:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.phase4_stochastic_sanity
```

### Fixed-seed stochastic trace

The actual MEDIUM `v3-medium-v1` fixture trace at root seed 12345 begins:

```text
decision t=0: Z1 current=0.680000, forecast(t=1)=0.688000 ±0.021633
               R-Z1-S1 OPEN, p_close=0.058800, S1 OPEN
action Z1->S1: accepted, realized travel=27.227090 min, arrival_t=3
decision t=1: Z1 current=0.690030, forecast(t=2)=0.700060 ±0.021633
               R-Z2-S1 closes (p=0.056926, proxy=0.426464); R-Z1-S1 remains OPEN
action WAIT
decision t=2: Z1 current=0.690285, forecast(t=3)=0.690539 ±0.021633
action WAIT
decision t=3: arrival dispatch-000001 processed before WAIT; Z1 current=0.671119
post-step t=4: S1 occupancy=200, reservation=0, safe=50
```

Current realization, next forecast, action, and subsequent realization are distinct. The
trace is generated from the engine and is not hardcoded into source.

### Real versus simulated

All Phase 4 stochastic values and the development scenario are synthetic/fictional. No
web research, Kerala geography, OSM route, empirical flood calibration, official closure
probability, or real shelter-failure rate was added. Existing real NDMA source provenance
and every frozen V1/V2 measurement remain unchanged.

### Known limitations

- There is no geospatial or edge-level route state; endpoint maximum severity is only a
  pre-geospatial proxy.
- Closures and shelter degradation are absorbing; reopening is not modeled.
- In-transit journeys are neither rerouted nor failed by later route/shelter closure.
- Existing reservations arrive even after a destination closes.
- There is no empirical calibration or learned forecasting model.
- `observe()` must be used as the policy-facing interface; the committed post-step state
  is a transition ledger snapshot until the next timestep is prepared.

### Deferred work

There is no planner, reward, V3 Gymnasium environment, PPO implementation, RAG/Gemini
change, formal Phase 5 safety-threshold layer, geospatial routing, dashboard change, human
override, or final evaluation suite. Those remain in their named later phases.

### Commit

See `git log` for *V3 Phase 4: stochastic flood, travel and closure dynamics*.

---

## 2026-09-07 — V3 Phase 5: deterministic hard-safety engine and action masks

### Goal

Freeze a small, deterministic, auditable V3 safety layer before any Phase 6 planner or
PPO result exists. The layer consumes the current simulator decision state, reports
simulator-owned mechanical failures, applies one additional synthetic hard-safety rule,
and returns a mask bundled with its canonical semantic actions.

The normative rule registry and boundary semantics are frozen in
[`V3_SAFETY_SPEC.md`](V3_SAFETY_SPEC.md).

> **Phase 5 safety thresholds are synthetic modeling assumptions unless explicitly
> documented otherwise. They are not official NDMA flood-safety cutoffs.**

### Added

| Path | Purpose |
| --- | --- |
| `V3_SAFETY_SPEC.md` | Pre-planner deterministic safety specification, rule registry, provenance, safety-OFF interpretation, and open limitations. |
| `src/safety/models.py` | Frozen, serializable rule, action-evaluation, and aligned safety-snapshot models. |
| `src/safety/hard_rules.py` | Versioned `v3-safety-v1` configuration and the minimal destination-hazard rule. |
| `src/safety/masks.py` | Canonical semantic action enumeration and pure per-state action/mask evaluation. |
| `src/safety/audit.py` | Translation of authoritative simulator validation into structured reasons, stable JSON serialization, and human-readable rendering. |
| `src/safety/__init__.py` | Public Phase 5 safety API. |
| `tests/test_v3_safety.py` | 37 focused tests spanning mechanics, hard safety, safety-OFF, WAIT, dynamics, ordering, audit, purity, leakage, and the committed sanity artifact. |
| `scripts/phase5_safety_sanity.py` | Deterministic 1,080-state cyclic safety exercise and generated three-case example. |
| `data/eval_v3/phase5_safety_sanity.json` | Summary-only safety-engine sanity artifact; not a policy benchmark or effectiveness result. |

No planner, reward, V3 Gymnasium environment, PPO code, RAG/Gemini behavior, routing,
dashboard, or human-override code was added.

### Mechanical validity versus hard safety

`src.sim.transition.validate_action` remains the single source of truth for whether an
action can execute. The safety evaluator calls it once and translates its result into a
`MECHANICAL` verdict with `SIMULATOR_MECHANIC` provenance. It does not independently
recalculate routes, capacity, population, status, fleet, dispatch, travel, identifier, or
terminal checks.

Mechanical rejection continues to cover terminal episodes, unsupported action types,
unknown zone/shelter IDs, missing/ambiguous/unreachable routes, invalid current travel,
empty sources, `CLOSED` shelters, zero capacity, disabled evacuation, and unavailable
dispatch opportunities. These checks remain enforced when hard safety is disabled.

Phase 5 adds exactly one rule:

```text
SAFETY_DESTINATION_HAZARD
pass iff current destination shelter severity < 0.70
```

It applies only after a dispatch passes simulator mechanics. Equality is explicitly
unsafe: `0.70` fails, as does any value above it. A high-hazard `OPEN` or `RESTRICTED`
shelter can therefore be mechanically usable but safety-excluded.

### Safety configuration and provenance

The frozen configuration is `v3-safety-v1`, version 1, with
`max_destination_hazard=0.70`. The value preserves the V1 synthetic training-proxy
boundary for project continuity; it was not selected from V3 planner/PPO performance and
is not claimed as an official NDMA threshold. The comparison remains the V1 `>=` exclusion
semantics, expressed positively as `severity < limit` to pass.

Every verdict includes a rule ID, layer, pass/fail, machine reason code, human reason,
current values, config version, enforcement flag, and provenance. Phase 5 emits only
`SIMULATOR_MECHANIC` and `SYNTHETIC_SAFETY_RULE`. `DOCUMENT_POLICY` is future-compatible
vocabulary only and produces no decisions yet.

### Partial dispatch, RESTRICTED, horizon, and safe-arrival decisions

Phase 3 partial sizing remains unchanged:

```text
dispatch_people = min(vehicle_capacity, source_remaining, capacity_available)
```

Thus 20 available places permit a valid 20-person dispatch; Phase 5 does not introduce a
full-vehicle capacity rule. This resolves Phase 1's sufficient-capacity language using
the actual executable batch.

`RESTRICTED` remains mechanically and safety usable when current severity is below 0.70;
the status word alone adds no unexplained exclusion. `CLOSED` remains mechanical.

No arrival-before-horizon rule was invented. Existing Phase 3 horizon treatment remains:
accepted journeys may remain in transit at horizon termination. Existing reservations
also survive later route/shelter closure, and previously arrived people remain in the
safe ledger after later shelter degradation. Numeric capacity does not degrade in the
current simulator, so post-dispatch capacity loss remains a future specification issue if
that mechanic is ever added.

### Canonical actions and mask semantics

`enumerate_canonical_actions()` uses the Phase 2 canonical ordering, independent of input
JSON order:

```text
Z1->S1, Z1->S2, ..., Zn->Sm, WAIT
```

It is the zone-major Cartesian product of canonical zones and shelters, followed by WAIT.
All pairs are represented even if a route is absent or unreachable, so their mechanical
reason is visible. No flattened RL IDs exist yet.

`SafetySnapshot` binds `canonical_actions`, `allowed_mask`, and structured evaluations in
one immutable object. Construction fails if lengths, order, or Boolean outcomes disagree.
The engine recomputes the snapshot on every call; hazard threshold crossings, closures,
reservations, arrivals, source depletion, and terminal changes therefore update the mask
without cache invalidation risk.

Every false mask entry has at least one failed, enforced structured reason. A nonterminal
WAIT passes mechanics and has no additional hard-safety predicate, so the legal action set
cannot be empty. At terminal state every action, including WAIT, is mechanically rejected
and the terminal mask is all false.

### Safety ON/OFF and unsafe-dispatch mapping

With `enable_hard_safety=True`, final allowance requires both mechanical validity and the
destination-hazard rule. With it `False`, mechanics still apply and only the synthetic
hard-safety exclusion is bypassed. The failed hard-safety verdict is still emitted with
`enforced=false`; this retains the frozen unsafe label for later RQ1 scoring.

Consistent with the frozen Phase 1 plan, an **executed unsafe dispatch** is an executed
non-WAIT action whose Phase 5 hard-safety predicate failed at decision time. In this
version that means current destination severity `>= 0.70`. Mechanical impossibilities are
normally rejected, so they are attempt/rejection diagnostics rather than executed-action
denominator events. Masked candidates are not counted as executed unsafe dispatches.

### Policy-facing inputs, purity, and determinism

The rule reads only action IDs and current destination severity after mechanical
validation reads current route/status/capacity/population/fleet/terminal state. It does
not access forecasts, future hazard, future closures, future degradation, unrealized
travel, latent regional state, root/random keys, embeddings, Gemini, network services, or
documents.

Safety evaluation is read-only: it does not mutate the scenario or episode state, append
to audit/event ledgers, change population/reservations, or query an RNG. Stable JSON from
identical inputs is byte reproducible. Paired stochastic tests confirm inserting safety
evaluation does not change later simulator observations or transition results.

### 1,080-state safety sanity result

The generated exercise used all LOW/MEDIUM/HIGH uncertainty configs, 30 deterministic
seeds per config, and all 12 fixture decision timesteps: 1,080 states total. At each
state, all four dispatch pairs plus WAIT were evaluated. A fixed cyclic selector rotates
among currently allowed dispatches and uses WAIT every fourth timestep; it is deliberately
not a planner or policy benchmark.

```text
states examined:                                      1,080
candidate dispatch actions:                           4,320
total candidates including WAIT:                      5,400
mechanically invalid dispatch candidates:             2,011
mechanically valid hard-safety exclusions:                 1
finally allowed candidates including WAIT:            3,388
allowed dispatches failing simulator validation:          0
allowed actions violating enabled hard-safety rules:      0
excluded actions missing a structured reason:             0
nonterminal states with zero allowed actions incl WAIT:    0
```

The small number of hazard-only exclusions is a process result, not evidence that the
threshold is effective: the development fixture begins with low shelter severities and
the Phase 4 simulator may mechanically close a shelter as it degrades. Final safety
effectiveness is intentionally not evaluated here.

### Human-readable generated example

The script modifies only current fixture shelter severities, evaluates the real engine,
then formats its structured results:

```text
A. mechanically invalid
Z2->S2
MECHANICALLY INVALID
reason: MECHANICAL_ROUTE_UNREACHABLE — route is unreachable

B. mechanically valid but safety-excluded
Z2->S1
MECHANICALLY VALID
HARD SAFETY: EXCLUDED
reason: SAFETY_DESTINATION_HAZARD — current severity 0.75 is at/above limit 0.70

C. mechanically valid and safety-allowed
Z1->S2
MECHANICALLY VALID
HARD SAFETY: ALLOWED
```

The labels, reasons, values, and action outcomes come from the evaluation objects; the
script does not hardcode the decisions.

### Tests and how verified

```text
Phase 5 safety suite:      37 passed
Phase 4 stochastic suite: 53 passed
Phase 3 transition suite: 60 passed
Phase 2 schema suite:     52 passed
legacy V1 suite:          43 passed
full suite:              245 passed
1,080-state sanity:       PASS
purity/no-RNG:             PASS
future leakage:           PASS
three-case rendering:     PASS
```

The sanity artifact and example are regenerated with:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.phase5_safety_sanity
```

### Real versus simulated

The safety threshold, test fixture, uncertainty processes, and sanity statistics are
synthetic. The evaluator itself and its verification results are real software behavior.
No real shelter, route, flood observation, empirical calibration, or new policy source
was introduced. Existing NDMA documents and V1/V2 artifacts were not modified.

### Known limitations

- The rule set is intentionally minimal: destination hazard is the only added safety
  predicate.
- There is no RAG policy interpretation, document-backed dynamic safety rule, or Gemini
  call.
- Route hazard remains a simplified endpoint proxy; there is no geospatial edge flooding.
- No terminal-arrival deadline safety rule is active.
- No planner, reward, V3 Gymnasium environment, PPO, human override, dashboard change, or
  final safety-effectiveness study exists.

### Deferred work

Phase 6 planners and every later phase remain deferred. In particular, no threshold may
be retuned after inspecting planner/PPO results without an explicit versioned safety-spec
change and disclosure.

### Commit

See `git log` for *V3 Phase 5: deterministic hard-safety engine and action masks*.

---

## 2026-09-07 — V3 Phase 6A: pre-results planner and gate specification

### Goal

Freeze every decision that could otherwise be tuned after observing planner results.
Stage 6B comparative execution is prohibited until this specification commit exists.
The normative contract is [`V3_PLANNER_SPEC.md`](V3_PLANNER_SPEC.md), version
`v3-planner-spec-v1`.

### Planning objective

Phase 1 defined NSU but deferred raw reward to Phase 8, so a dated pre-results
clarification was appended—not overwritten—to `V3_EVALUATION_PLAN.md`. The bounded
Gate-6-only utility is:

```text
G6U = 0.70 * safe population fraction
    - 0.25 * normalized exposed person-timesteps
    - 0.05 * normalized in-transit person-timesteps
```

Its range is `[-0.30,0.70]`, making `epsilon_den=0.01`. Hard safety applies before score
optimization. G6U is not the future PPO reward and does not replace final
`NSU-practical`.

### Frozen planner definitions

- `random_valid` follows Phase 1 literally and samples uniformly from every allowed
  action including WAIT, using independent policy seeds.
- `nearest_safe` selects the highest-current-severity source, then its lowest expected
  travel destination.
- `risk_greedy` freezes six normalized components and weights: urgency `0.30`, destination
  safety `0.20`, useful capacity `0.25`, travel `0.10`, closure safety `0.10`, travel
  certainty `0.05`.
- `lookahead_k2` and `lookahead_k3` exhaustively search depths 2 and 3 in a separate
  deterministic expected model built only from policy-visible state. No beam pruning or
  clone of the real stochastic simulator is allowed.
- sampled MPC freezes `N=16`, `H=3`, arithmetic-mean aggregation, risk-greedy sampled
  continuation, and planner-owned SHA-256 randomness rooted at master seed `76001`.
- `oracle_small` is an exhaustive, five-second-limited **CLAIRVOYANT UPPER BOUND — NOT A
  PRACTICAL POLICY**, isolated behind a separate oracle-only interface.

Every deterministic tie selects the earliest Phase 5 canonical semantic action.

### Information and RNG boundaries

Practical planners receive a detached policy observation, current safety snapshot, public
time/fleet metadata, and the public uncertainty configuration. They do not receive the
scenario root seed, replication ID, simulator, private stochastic context, latent state,
random stream, audit log, or future outcome. MPC/random-valid randomness is independent
of the environment.

### Frozen synthetic suites

Generator `v3-gate6-generator-v1` uses explicit fixed synthetic distributions and a
separate SHA-derived environment seed. Acceptance requires schema validity and one
mechanically and safety-allowed t0 dispatch only; it never conditions on future outcomes
or planner performance.

- Exact: 120 scenarios (`610000..610119`), 2 zones, 2 shelters, horizon 5, 40 each
  LOW/MEDIUM/HIGH, replication 0.
- Practical: 120 scenarios (`620000..620119`), 4 zones, 5 shelters, horizon 10, 40 each
  LOW/MEDIUM/HIGH, replication 0, no oracle claim.

The Phase 5 observation of one hard-safety exclusion in 4,320 candidates is recorded but
does not alter the threshold or generator.

### NSU-exact, latency, and STOP rule

The exact lower reference is the mean of five random-valid policy seeds `73001..73005`;
the upper reference is the exact clairvoyant oracle. Per-unit denominators `<=0.01` are
`NA`, scores are not clipped, and more than 5% invalid or timed-out units makes the gate
inconclusive.

Timing uses `perf_counter_ns`, 20 warm-ups, and excludes input construction, safety
evaluation, transition, logging, and imports. The recorded reference is an Apple M1
MacBook Air with 8 cores/8 GB, arm64 macOS 26.6.2, Python 3.11.3. Phase 1's absolute p95
limit remains 100 ms; the prior mistake of comparing only against a very fast neural
forward-pass multiple is not repeated.

The unchanged gate requires one practical non-clairvoyant planner to achieve median
NSU-exact `>=0.99`, p10 `>=0.97`, and p95 latency `<=100 ms`. Passing means `STOP_RL`;
otherwise `PROCEED_TO_RL`, unless a genuine exactness, leakage, timeout, or normalization
failure makes the gate inconclusive.

### Commit

See `git log` for *V3 Phase 6A: freeze planner and planning-gate specification*.

---

## 2026-09-07 — V3 Phase 6B: strong planners and planning-headroom gate

### Implementation

Added observable-only common planner inputs/results, the bounded Gate-6 utility ledger,
random-valid, nearest-safe, risk-greedy, exhaustive expected lookahead-2/3, sampled MPC,
an isolated exhaustive clairvoyant oracle, the frozen synthetic generator, and the Gate 6
runner. Pending dispatch metadata was added to policy observations without exposing
realized travel or future outcomes.

The complete result and limitations are in
[`V3_GATE6_RESULT.md`](V3_GATE6_RESULT.md). Raw and summarized artifacts live under
`data/eval_v3/gate6_*`.

### Oracle and suite validation

All 120 exact scenarios completed with zero timeouts, zero invalid normalization
denominators, zero oracle replay mismatches, and no practical result above its exact
oracle. A hand-solvable short-route fixture is recovered exactly. The oracle expanded
28,177 states and 84,612 branches; median exact search time was 195.83 ms per unit.

Both frozen suites contain 120 synthetic scenarios with 40 LOW, 40 MEDIUM, and 40 HIGH.
The exact suite is 2 zones × 2 shelters × horizon 5; the practical suite is 4 × 5 ×
horizon 10. One fixed environment replication is used per scenario.

### Exact headroom and latency

| Planner | Median NSU-exact | p10 | Mean | Median ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Random valid | 0.0000 | 0.0000 | 0.0000 | 0.0015 | 0.0028 |
| Nearest safe | 0.7075 | -0.0486 | 0.5514 | 0.0037 | 0.0069 |
| Risk greedy | 0.8305 | 0.0236 | 0.6279 | 0.0078 | 0.0150 |
| Lookahead-2 | 0.9817 | 0.3999 | 0.8277 | 0.3291 | 2.0305 |
| Lookahead-3 | **0.9954** | **0.4306** | **0.8448** | 0.4140 | 6.9601 |
| Sampled MPC | 0.9644 | 0.3417 | 0.8323 | 6.5326 | 18.0360 |

Lookahead-3 crosses the median 0.99 threshold but misses the p10 0.97 threshold by a
large margin. This is why normalized headroom distribution—not `% exactly optimal`—was
the registered gate measure.

On the 1,200-decision-per-planner practical suite, p95 latency was 135.26 ms for
lookahead-2, 1,948.89 ms for lookahead-3, and 251.42 ms for MPC. The frozen unpruned
algorithms were not changed after seeing scaling costs.

### Leakage, RNG, and pairing

Focused tests prove that risk-greedy, lookahead-2/3, and fixed-seed MPC return identical
actions for identical public state under different hidden environment seeds. MPC scores
are repeatable, planner RNG does not shift the environment, different planner actions
retain paired exogenous paths, all selected actions pass the current safety mask, and
selection is read-only.

### Tests and verification

```text
Phase 6 planner suite:    39 passed
Phase 5 safety suite:     37 passed
Phase 4 stochastic suite: 53 passed
Phase 3 transition suite: 60 passed
Phase 2 schema suite:     52 passed
legacy V1 suite:          43 passed
full suite:              284 passed
exact Gate units:        120 complete, 0 timeouts, 0 invalid normalization
practical Gate units:    120 complete
```

The offline benchmark is reproduced with:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  .venv/bin/python -m scripts.run_gate6
```

### Safety diagnostic

For lookahead-3's exact trajectory states, 2,396 dispatch candidates comprised 942
mechanical exclusions, 228 additional hard-safety exclusions, and 1,226 allowed actions.
All executed dispatches were safety-allowed. The 0.70 threshold and all generator ranges
remain unchanged.

### Gate verdict

`PROCEED_TO_RL`

No practical planner satisfies median `>=0.99`, p10 `>=0.97`, and exact-suite p95 latency
`<=100 ms` together. The planning gate therefore found sufficient remaining lower-tail
clairvoyant headroom to justify testing a learned policy. It does not establish that RL
is necessary or that PPO will win.

### Known limitations

G6U is a Gate-only utility, exact cases are small, practical cases have no oracle, there
is one replication per synthetic scenario, expected lookahead is deliberately simple,
MPC has 16 futures, unpruned planning scales poorly, and current Phase 4 semantics produce
no post-departure route failures. No real-world effectiveness claim is made.

### Deferred work

Phase 7 and later work remain untouched. Even with `PROCEED_TO_RL`, no Gymnasium/PPO work
starts without project-owner direction.

### Commit

See `git log` for *V3 Phase 6B: strong planners and planning-headroom gate*.

---

## 2026-09-07 — V3 Phase 7: fixed-dimension Gymnasium evacuation environment

### Goal

Wrap the validated V3 stochastic simulator in an RL-compatible interface without
training a policy or defining the Phase 8 reward. The normative pre-implementation
contract is [`V3_ENV_SPEC.md`](V3_ENV_SPEC.md), version `v3-env-v1`.

### Why fixed dimensions are necessary

MaskablePPO and standard MLP policies require stable Gymnasium spaces across episodes.
Variable scenario sizes therefore use one fixed 6-zone × 9-shelter envelope rather than
changing action or observation dimensions. Real entities occupy canonical leading slots;
padding is explicitly identified and masked.

### Environment configuration and files

The `src/env_v3/` package adds:

- `config.py`: authoritative `v3-env-v1` dimensions, WAIT index, fallback, and
  placeholder-reward boundary;
- `action_space.py`: canonical ID slots, integer encode/decode, fixed-mask alignment,
  and envelope errors;
- `observation.py`: policy-safe normalization and the 384-element flat vector;
- `scenario_source.py`: fixed and callable scenario-provider interfaces without a
  training distribution;
- `evacuation_env.py`: Gymnasium reset/step/mask wrapper around `StochasticSimulator`;
- `__init__.py`: public Phase 7 API.

`tests/test_v3_env.py` provides behavioral verification. The compact executable trace is
`scripts/phase7_env_sanity.py`; its API-only artifact is
`data/eval_v3/phase7_env_sanity.json`.

### Maximum slots and action mapping

```text
MAX_ZONES = 6
MAX_SHELTERS = 9
dispatch index = zone_slot * 9 + shelter_slot
dispatch indices = 0..53
WAIT index = 54
action space = Discrete(55)
```

Zones and shelters are sorted by ID, independent of source JSON order. Scenarios over the
envelope, and ambiguous multiple routes for one zone-shelter pair, fail loudly instead of
being truncated. Real entity pairs without routes and every padded combination are
masked. WAIT remains the final stable action.

### Observation features and dimension

The environment returns `Box(low=0, high=1, shape=(384,), dtype=float32)`:

| Group | Slots × features | Features |
| --- | ---: | --- |
| Zones | 6 × 6 | presence, remaining fraction, current severity, normalized observed trend, public forecast mean, monotonic forecast-uncertainty transform |
| Shelters | 9 × 8 | presence, available/occupied/reserved fractions, current severity, OPEN/RESTRICTED/CLOSED one-hot |
| Routes | 54 × 5 | presence, reachability, monotonic expected-travel transform, monotonic travel-uncertainty transform, closure probability |
| Global | 6 | timestep, remaining/transit/safe fractions, vehicle-capacity transform, any allowed dispatch |

Zone population uses the static zone total. Global population fractions use initial
evacuation population. Travel values use `x/(x+horizon_minutes)`, forecast uncertainty
uses `x/(x+1)`, and vehicle capacity uses `capacity/(capacity+initial_population)`.
Every transform is finite and bounded; zero denominators have explicit behavior.
Subgroup features are not fabricated because V3 currently dispatches undifferentiated
people.

### Padding and presence semantics

Every entity group begins with a presence indicator. An absent slot has presence zero and
all remaining features zero, distinguishing padding from a real entity whose physical
value is zero. Observations are rebuilt on each reset, and the verified large-to-small
reset leaves no stale padded values.

### Scenario source and stochastic reset

`FixedScenarioSource` supports deterministic tests and a callable adapter permits future
episode-varying scenarios without freezing the Phase 9 distribution. Every provided
scenario is checked against the fixed envelope.

`reset(seed=s)` calls Gymnasium's standard superclass reset and maps `s` directly to the
Phase 4 replication ID while retaining the scenario root seed. The replication ID/root
seed remain private. With no reset seed, a private episode counter supplies replications.
Same scenario + reset seed + integer actions exactly reproduces observations, masks,
semantic requests/executions, physical state, audit events, and termination. Different
seeds produced different trajectories in the stochastic sanity check.

### Safety masks and invalid-action fallback

`action_masks()` has Boolean shape `(55,)` and aligns real dispatches with Phase 5's
canonical `evaluate_actions()` results. No mechanical or hard-safety rule is duplicated.
Safety OFF bypasses only enforcement of the synthetic hazard predicate; missing/closed
routes, zero capacity, fleet mechanics, padding, and terminal exclusions still apply.

An in-range masked action is converted to WAIT before simulator execution. The requested
invalid dispatch never executes, time advances normally, and info records requested vs.
executed semantics plus diagnostic counts. Phase 7 adds no penalty. Out-of-range or
non-integral actions fail clearly, and stepping after episode end requires reset.

### Termination semantics

```text
ALL_EVACUATED   -> terminated=True,  truncated=False
HORIZON_REACHED -> terminated=False, truncated=True
```

Normal episode endings never set both flags.

### Placeholder reward

> **Phase 7 reward is an API-required zero placeholder. It has no research meaning and
> the environment is not approved for PPO training until Phase 8 freezes and integrates
> the RL reward.**

Every transition returns exactly `0.0`, with
`reward_spec_version=PHASE7_PLACEHOLDER_ZERO`, `reward_defined=False`, and
`training_ready=False`. There is no exposure, safe-population, transit, terminal, or
invalid-action reward component. The provider boundary exists only for clean Phase 8
integration.

### Leakage boundary and planner/PPO parity

The numeric vector is built from the detached public Phase 4 observation plus current
Phase 5 mask results. It exposes current hazard, forecast, capacity, categorical shelter
status, expected travel, travel uncertainty, reachability, closure probability, time,
population, and vehicle scale. It omits root seed, replication ID, regional latent state,
future exact hazard/closure/travel, oracle values, Gate 6 scores, algorithm identity, and
literal uncertainty labels.

Two simulators with the same public state and different hidden environment seeds produce
identical Gym observations and masks. Step info includes only sanitized current audit
event type/timestep/reason, not realized future travel values. Compared with practical
planners, the flat Phase 7 vector retains essential decision quantities but only aggregate
in-transit population, not individual pending-arrival records; this is documented as a
future observation-adequacy limitation rather than silently changed.

### Gymnasium verification and tests

Installed and verified versions are Gymnasium `1.3.0`, Stable-Baselines3 `2.9.0`, and
sb3-contrib `2.9.0`.

```text
Phase 7 environment suite: 23 passed
Phase 6 planner suite:     39 passed
Phase 5 safety suite:      37 passed
Phase 4 stochastic suite:  53 passed
Phase 3 transition suite:  60 passed
Phase 2 schema suite:      52 passed
legacy V1 suite:           43 passed
full suite:               307 passed
Gymnasium check_env:       PASS
DummyVecEnv (2 envs):      PASS
sb3-contrib mask support:  PASS
same-seed replay:          PASS
different-seed variation: PASS
large-to-small padding:    PASS
hidden-future leakage:     PASS
safety ON/OFF:             PASS
```

The sanity artifact is regenerated without training by:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  .venv/bin/python -m scripts.phase7_env_sanity
```

### Real versus simulated

The environment behavior and test outcomes are real software results. The exercised
scenarios, uncertainty regimes, and safety threshold remain explicit synthetic modeling
assumptions or fictional data. No real-world evacuation effectiveness claim is made.

### Known limitations

- no PPO or MaskablePPO training and only a meaningless zero reward;
- fixed 6×9 envelope and flat MLP-style representation;
- no recurrent or graph policy and no subgroup-specific dispatch action;
- no individual pending-arrival encoding in the numeric observation;
- canonical slot identity can become a shortcut if a future generator correlates IDs
  with attributes;
- no geospatial route graph, RAG/Gemini change, dashboard work, human override, or final
  held-out evaluation.

### Deferred work

Phase 8 must independently freeze and integrate the real RL reward before any training.
Phase 9 must define the training distribution, randomize entity attributes, and include
slot/entity permutation diagnostics and evaluation under permuted slot identity. No
Phase 8 work was started here.

### Commit

See `git log` for *V3 Phase 7: fixed-dimension Gymnasium evacuation environment*.

---

## 2026-09-07 — V3 Phase 8A: frozen RL reward specification

### Goal

Freeze the exact scalar RL reward before implementing it or running any PPO optimization.
The normative contract is [`V3_REWARD_SPEC.md`](V3_REWARD_SPEC.md). No reward result or
learned-policy experiment exists in Stage 8A.

### Reward design and normalization

For initial evacuation population `N0`, horizon steps `H`, and horizon minutes `M`, the
primary `v3-reward-balanced-v1` transition reward is:

```text
+ 0.55 * newly arrived people / N0
- 0.30 * post-action current zone exposure / (N0 * H)
- 0.05 * (dispatched people / N0) * realized_travel / (realized_travel + M)
- 0.10 * horizon-terminal unfinished people / N0
```

Arrival credit is paid only when a pending event processes, not at dispatch. Exposure
uses post-action population and current already-realized hazard. Travel uses the realized
duration only after the dispatch transition. The unfinished term applies only to
`HORIZON_REACHED`; in-transit people remain unfinished. WAIT has no arbitrary constant.

Population-zero schema/test cases remain numerically safe but are not training-ready.
Under frozen simulator invariants the primary conservative episode range is
`[-0.45,0.55]`, giving Phase 1 `epsilon_den=0.01`.

### Primary and sensitivity weights

| Config | Safe | Exposure | Travel | Terminal |
| --- | ---: | ---: | ---: | ---: |
| `v3-reward-balanced-v1` (primary) | 0.55 | 0.30 | 0.05 | 0.10 |
| `v3-reward-evacuation-v1` | 0.65 | 0.20 | 0.05 | 0.10 |
| `v3-reward-exposure-v1` | 0.50 | 0.40 | 0.05 | 0.05 |

The alternatives are frozen for later sensitivity reporting, not post-results selection.

### Safety separation and assumptions

Reward includes no Phase 5 `0.70` threshold, unsafe-action penalty, closed-route penalty,
or invalid-mask penalty. Safety remains structural. Safety-OFF reward does not secretly
recreate the hard rule. Vulnerability and medical weights are omitted because subgroup
movement is not represented.

> **Reward weights are synthetic project modeling choices frozen before PPO training.
> They are not official disaster-management utility weights.**

### Pending-arrival partial observability

The feed-forward PPO observation has aggregate transit and reservations but no individual
arrival countdown. Delayed arrival reward therefore preserves partial observability.
The existing practical-planner boundary actually includes pending-event arrival metadata,
so later comparisons must disclose that planner information advantage; Stage 8A does not
change either frozen interface merely to claim parity.

### Commit

See `git log` for *V3 Phase 8A: freeze RL reward specification*.

---

## 2026-09-07 — V3 Phase 8B: integrated frozen RL reward

### Implementation and provider architecture

Added `src/env_v3/rewards.py` with immutable registered reward configurations, a pure
`FrozenV3RewardProvider`, structured JSON-serializable `RewardBreakdown`, the retained
`ZeroPlaceholderReward`, and an explicit component-combination function. The calculator
accepts the prepared previous state, finalized transition result/state, and scenario. It
does not mutate inputs, consume RNG, import planners, call a network/model, or inspect
future simulator context.

The breakdown records raw normalized safe gain, exposure, travel, and terminal unfinished
components; signed weighted contributions; total reward; and config identity. Gym returns
only the scalar total and places the full breakdown in debug/evaluation `info`, never the
policy observation.

### Gym integration and training readiness

`EvacuationEnvV3` now accepts an explicit `reward_provider`. Omitting it preserves Phase
7 placeholder behavior:

```text
PHASE7_PLACEHOLDER_ZERO
reward_defined=False
training_ready=False
```

Supplying a recognized frozen provider on a reset positive-population scenario exposes
the selected reward version, returns the physical reward, and sets `training_ready=True`.
`assert_training_ready()` additionally verifies the recognized provider, valid safety
configuration, fixed 55-action space, fixed 384-element float32 observation space, and
positive population. Zero-population scenarios remain finite but fail readiness.

### Tests and verification

```text
Phase 8 reward suite:      24 passed
Phase 7 environment suite: 23 passed
Phase 6 planner suite:     39 passed
Phase 5 safety suite:      37 passed
Phase 4 stochastic suite:  53 passed
Phase 3 transition suite:  60 passed
Phase 2 schema suite:      52 passed
legacy V1 suite:           43 passed
full suite:               331 passed
```

Tests cover exact weights, config immutability, arrival timing, post-action exposure,
horizon normalization, realized-travel transform, terminal unfinished population,
monotonicity, all required micro-case orderings, consequence-only WAIT, initial shelter
occupants, masked fallback equivalence, purity, deterministic replay, safety independence,
planner independence, serializability, scalar Gym output, readiness, zero population,
extreme finite travel, and NaN/infinity rejection.

### Reward sanity study

`scripts/phase8_reward_sanity.py` ran 200 fixed synthetic random-valid episodes across
LOW/MEDIUM/HIGH (`67/67/66`) without a learned policy. The artifact is
`data/eval_v3/phase8_reward_sanity.json`.

```text
episodes:                    200
steps:                     2,000
minimum step reward:    -0.104032
maximum step reward:     0.174680
minimum episode return: -0.197509
maximum episode return:  0.318095
NaN count:                       0
infinity count:                  0
micro-case checks:          6/6 PASS
monotonicity checks:        4/4 PASS
```

These are reward-magnitude and semantic diagnostics only. No policy ranking was inferred,
and the Stage 8A weights were not changed after observing them.

### No-leakage, safety, and planner independence

Reward reads only arrivals and realized travel belonging to the completed transition,
post-action current zone state, and final terminal ledgers. It does not use forecast or
next-step hazards, future closure/arrival/failure values, root seed, stochastic context,
or policy observation changes. Source and behavioral checks confirm no `src.planners`
dependency, Gate-6/oracle/lookahead/MPC term, or Phase 5 `0.70` branch.

Safety ON masks a high-destination-hazard dispatch; safety OFF may execute it. In both
cases the reward itself contains only ordinary physical components and does not recreate
the hard rule. A masked request receives the executed WAIT transition reward without a
special implementation-artifact penalty.

### Known limitations

- No PPO, optimizer, gradient update, discount-factor choice, checkpoint, or learned
  policy evaluation exists.
- Reward weights and all sanity scenarios are synthetic project modeling choices, not
  official disaster-management utility weights.
- PPO remains feed-forward and partially observable because individual pending-arrival
  timing is absent; frozen practical planners retain more detailed pending metadata.
- No vulnerability/medical subgroup reward exists because subgroup movement is absent.
- No reward normalization wrapper, adaptive scaling, clipping, RAG/Gemini, geospatial,
  dashboard, recurrent, graph-policy, or final held-out work was added.

### Commit

See `git log` for *V3 Phase 8B: integrate frozen RL reward*.

---

## 2026-09-07 — V3 Phase 9A: frozen MaskablePPO training specification

### Pre-training publication and cleanliness check

Before Phase 9 work, the remote branch was queried directly. Both Phase 8 commits were
already published: `origin/v3-dynamic-stochastic` and local `HEAD` resolved to
`318989fedf29396ac90c9e48e131cb7dc39a18c1`, and the working tree was clean. No history
was rewritten.

### Frozen training contract

[`V3_TRAINING_SPEC.md`](V3_TRAINING_SPEC.md) freezes
`v3-ppo-training-spec-v1` before any `model.learn(...)` call. The primary algorithm is
sb3-contrib `MaskablePPO` with `MlpPolicy`, two 256-unit ReLU layers, hard safety ON, and
the balanced Phase 8 reward. Five seeds (`1101`, `2202`, `3303`, `4404`, `5505`) each
receive exactly 250,000 CPU timesteps with no performance early stopping.

The frozen optimizer/advantage values are learning rate `3e-4`, 10 epochs, gamma `0.99`,
GAE lambda `0.95`, clip `0.2`, entropy coefficient `0.01`, value coefficient `0.5`, and
maximum gradient norm `0.5`. Four synchronous environments collect 1,250 steps each,
giving an exact 5,000-transition rollout divided into 250-example batches. This
pre-results choice replaces the suggested 1,024/256 pair so checkpoints and validation
occur at exact 10,000-step boundaries and SB3 cannot overshoot the exact 250,000 budget.

The installed training environment is Python `3.11.3`, Gymnasium `1.3.0`,
Stable-Baselines3 `2.9.0`, sb3-contrib `2.9.0`, and PyTorch `2.13.0` on arm64 macOS.
PyTorch reports MPS unavailable, so CPU is frozen for debug and every primary seed.

### Procedural generator and semantic slots

`src/training_v3/` defines immutable config, `v3-ppo-train-generator-v1`, validation
manifest construction, deterministic stream-key derivation, and semantic-ID permutation.
The generator samples zones uniformly from 4–6, shelters from 6–9, horizon from 10–16,
and LOW/MEDIUM/HIGH uncertainty uniformly. It randomizes all required physical entity,
fleet, and route properties and ensures usable dispatch choices exist at reset.

Physical profiles receive independently randomized opaque IDs. Canonical sorting thus
moves a feature profile among every available slot without changing the within-episode
mapping. This directly prevents the fixed S6/S7-style identity association seen in V1.

### Validation and permutation manifests

`data/eval_v3/training/validation_manifest.json` freezes 150 scenarios under
`v3-ppo-validation-v1`, with exactly 50 per uncertainty level. Every entry commits its
generator seed, environment root seed, sizes, horizon, uncertainty ID, generation
attempt, and SHA-256 of the full scenario. Seeds `930000`–`930149` are disjoint from the
five training roots and both Gate 6 seed ranges.

Checkpoint ranking is deterministic masked evaluation by mean undiscounted balanced
reward. Ties use lower cumulative normalized exposure, higher safe fraction, then the
earlier checkpoint. This validation criterion is not a final claim metric and no planner,
oracle, demo, or Phase 10 result participates.

`permutation_manifest.json` freezes 30 validation bases and five semantic-ID
permutations each. Since Phase 4 stochastic draws themselves use entity IDs as keys, this
diagnostic pre-registers a deterministic transform of the selected uncertainty config;
it removes random innovations, closures, degradation, and travel noise solely so IDs are
the only difference between each paired trajectory. Training and ordinary validation
still use the unmodified LOW/MEDIUM/HIGH configurations.

The alarm label is `POTENTIAL_SLOT_SHORTCUT`, triggered by median absolute normalized
return delta above `0.05`, mean absolute safe-population delta above `0.05`, or a large
systematic conditioned slot-selection bias. An alarm is reported and stops silent
generator changes; it does not justify post-hoc retraining.

### Information boundary and deferred comparison

The feed-forward PPO observation still omits exact individual pending-arrival schedules,
while existing strong planners may consume them. Planner-versus-PPO comparison is
therefore conservative against PPO and is not perfectly information matched. Phase 10
must include the frozen `OBSERVATION-MATCHED PLANNER DIAGNOSTIC`; Phase 9 does not alter
Phase 6 or enlarge the observation.

### Training gate

No optimizer or gradient update was run in Stage 9A. The 20,000-step debug run and all
five primary runs are permitted only after the exact commit named
*V3 Phase 9A: freeze PPO training specification* exists. Phase 10 data remains unseen.

---

## 2026-09-07 — V3 Phase 9B: trained pre-registered MaskablePPO policies

### Outcome

Executed the frozen Stage 9A contract without changing its generator, reward, safety,
architecture, hyperparameters, validation suite, seeds, or budget. The detailed record is
[`V3_TRAINING_RESULT.md`](V3_TRAINING_RESULT.md); structured results live under
`data/eval_v3/training/`, and separately named best/final models plus metadata live under
`models/v3/`.

The 20k seed-1101 debug run was finite, mask-clean, save/load capable, and deterministic
at inference. Repeating it reproduced every validation metric exactly, although ZIP bytes
differed; exact model-byte reproducibility is not claimed.

All five primary seeds completed exactly 250,000 timesteps and 25 deterministic
150-scenario validations. No performance early stopping or seed replacement occurred.

| Seed | Best step | Validation return | Safe pop. | Exposure | Completion | Invalid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1101 | 240,000 | 0.282728 | 0.708929 | 0.231826 | 0.133333 | 0 |
| 2202 | 200,000 | 0.282436 | 0.711290 | 0.238310 | 0.140000 | 0 |
| 3303 | 220,000 | 0.278508 | 0.703620 | 0.234598 | 0.113333 | 0 |
| 4404 | 200,000 | 0.279870 | 0.705327 | 0.234300 | 0.080000 | 0 |
| 5505 | 190,000 | 0.273840 | 0.697315 | 0.236535 | 0.120000 | 0 |

Mean validation return was `0.279477` with population standard deviation `0.003231`,
range `0.273840`–`0.282728`. The frozen median-validation rule selects seed 4404 as the
representative, but Phase 10 must evaluate every best checkpoint.

### Learning and compute artifacts

`learning_curves.csv` and `learning_curves.svg` report validation return, safe population,
and exposure for every seed at every 10k interval plus cross-seed mean/std. Mean return
moved from `0.240915` at 10k to `0.274342` at 250k. Per-episode CSV files retain reward,
safe fraction, exposure, travel, completion, invalid actions, and allowed-action stats.

All runs used CPU with four Torch threads and deterministic algorithms. Summed process
wall time was 4,034 seconds; concurrent seed pairs shared the same machine. Peak memory
was not measured.

### Slot diagnostic — alarm triggered

The frozen diagnostic evaluated all five best models on 30 base scenarios × five ID
permutations (750 total pairs). Physical-feature and route remapping tests passed, so only
semantic IDs/slots varied under deterministic paired dynamics.

```text
mean remapped action equivalence:             0.099608
median absolute normalized return delta:      0.057137
mean absolute safe-population delta:           0.096927
alarm:                         POTENTIAL_SLOT_SHORTCUT
```

Both quantitative alarm thresholds (`0.05`) were exceeded, and every seed triggered.
No generator change or retraining followed. V3 fixes the exact V1 permanent-S6/S7-mask
data bug, but its flat MLP remains materially position sensitive despite broad opaque-ID
randomization. This limitation must be reported in Phase 10.

### Information boundary and stopping point

The PPO observation still has only aggregate transit/reservation information; strong
practical planners retain detailed pending-arrival metadata. Comparison remains
conservative against PPO and not information matched. The Phase 10
`OBSERVATION-MATCHED PLANNER DIAGNOSTIC` remains mandatory and unimplemented.

Training/validation performance does not establish PPO superiority. No Phase 10 suite,
planner comparison, oracle target, or college demo evaluation was run. Work stops after
the Phase 9B commit.

---

## 2026-09-07 — V3 Phase 10: frozen held-out planner-versus-PPO evaluation

### Outcome

Phase 10 followed a two-commit firewall. Stage 10A committed
[`V3_PHASE10_EVAL_SPEC.md`](V3_PHASE10_EVAL_SPEC.md) before any held-out data was
generated. Stage 10B then evaluated the unchanged six Phase 6 planners, all five frozen
best-validation PPO checkpoints, and a secondary observation-matched greedy diagnostic.
No training or checkpoint selection occurred.

The independent `v3-heldout-generator-v1` suite contains 600 paired scenarios, balanced
200/200/200 across LOW/MEDIUM/HIGH uncertainty, plus 250 separate stress scenarios and
100 independent permutation bases with five variants each. Full structured outputs are
stored in `data/eval_v3/phase10/`, and eleven reproducible figures are stored in
`artifacts/figures/phase10/`.

The pre-selected principal comparator was `risk_greedy`. PPO-family NSU-practical was
`0.2091` versus `1.0000` for that comparator. The paired NSU difference was `-0.7919`
with 95% CI `[-0.8384, -0.7453]`; none of the combined, uncertainty-stratum, tail, or
stress gates passed. The frozen Phase 1 result is therefore `NO`. The fresh permutation
diagnostic independently reproduced `POTENTIAL_SLOT_SHORTCUT`. Hard-safety and mechanical
violation counts remained zero.

The full scientific record, uncertainty and seed breakdowns, bootstrap intervals,
latency measurements, stress results, limitations, and trace are documented in
[`V3_POLICY_EVALUATION.md`](V3_POLICY_EVALUATION.md). This result applies only to the
synthetic V3 environment and synthetic reward; Phase 11 was not started.

---

## 2026-09-07 — V3 Phase 11: authoritative disaster-guidance corpus expansion

### Goal and baseline

Phase 11 expands the evidence base used by RAG while leaving retrieval architecture and
the frozen decision-policy experiment alone. The baseline was one genuinely distinct
NDMA flood guideline: 168 pages and 480 page-scoped chunks. The target was three to eight
high-quality canonical documents covering complementary flood-response policy topics,
with no mirrors, rescans, or cosmetic variants counted as independent evidence.

Corpus expansion changes the evidence base only. It does not change the frozen Phase 10
decision-policy result.

### Candidate-source methodology and authority criteria

Candidate research prioritized Government of India, NDMA, and NIDM publication channels.
A document was eligible only when its institutional publisher and stable title were
identifiable, its provenance URL and local file could be recorded, its text was
meaningfully extractable, its content supported a project policy topic on inspected
pages, and its SHA-256 did not duplicate a retained source. Publication date, stable PDF
pagination, and direct official hosting were preferred. Title overlap triggered a
version/near-duplicate review rather than automatic inclusion.

Eight URLs were examined and six candidate files were downloaded during this phase.
Three canonical sources were retained. The five exclusion-log entries include two exact
duplicate URLs, one near-duplicate URL, and documents whose text layer was unusable
without OCR. The existing NIDM flood URL remains a provenance mirror of the byte-identical
NDMA document and never becomes a second source.

### Documents retained and spot checks

All three retained items are **REAL AUTHORITATIVE DOCUMENTS** published by India's
National Disaster Management Authority:

| Source ID | Document | Date | PDF pages | Readable pages | Chunks | Inspected pages/sections |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `ndma-flood-guidelines-2008` | *National Disaster Management Guidelines: Management of Floods* | 17 Jan 2008 | 168 | 162 | 480 | pp. 56 preparedness/flood-safe shelters; 63 evacuation and relief responsibilities; 66 patient evacuation |
| `ndma-national-disaster-management-plan-2019` | *National Disaster Management Plan 2019* | Nov 2019 | 384 | 379 | 1,099 | pp. 111 inclusive response; 115 disability support; 256 shelter access; 306 evacuation routes; 313 relief logistics |
| `ndma-temporary-shelters-2019` | *National Guidelines for Temporary Shelters* | Sep 2019 | 100 | 94 | 218 | pp. 37 inclusive site/design guidance; 40 water and sanitation; 49 disability facilities; 54 shelter logistics |

The dedicated *Disability Inclusive Disaster Risk Reduction* guideline was authoritative
and relevant but rejected: its 106-page official PDF exposed only eight pages and 6,780
characters without OCR. The NIDM copy was byte-identical, while a Gujarat-hosted
repackaging was a malformed near duplicate. The official *Guidelines on Minimum
Standards of Relief* scan exposed no extractable text. Exact titles, URLs, publishers,
relationships, and reasons are preserved in `data/raw_docs/excluded_sources.json`.

### Manifest, duplicate handling, and fingerprint

`data/raw_docs/MANIFEST.json` is now the schema-2 canonical registry. Each entry records
source ID, title, publisher, date, document type, canonical and alternate URLs, local
filename, SHA-256, bytes, PDF page count, retrieval time, topics, authority class,
duplicate relationship, notes, and at least three relevance spot checks. Validation
rejects missing files, size/hash drift, duplicate canonical IDs, filenames or hashes,
invalid topics/authority classes, and fingerprint drift. `src/rag/fetch_docs.py` fetches
only registered URLs and fails loudly if downloaded content differs from the expected
hash; an intentional update therefore requires reviewing the new file and updating the
manifest/version explicitly.

The version is `v3-authoritative-corpus-v1`. Its fingerprint is
`a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`, defined as SHA-256
over UTF-8 records `<source_id>\t<source_sha256>\n`, sorted lexicographically by source
ID. This makes it deterministic and independent of manifest ordering.

### Topic coverage

| Topic | Supporting source IDs | Coverage note |
| --- | --- | --- |
| Flood management | flood guideline; national plan | Strong domestic national coverage |
| Evacuation | all three | Planning, response duties, routes, and shelter movement |
| Relief shelter | all three | Strongest in the dedicated temporary-shelter guideline |
| Vulnerability/accessibility | national plan; temporary-shelter guideline | Moderate; dedicated disability PDF could not be safely extracted |
| Logistics/transport | all three | Response movement, access routes, stocks, and regional logistics |

### Ingestion, chunk counts, and offline capability

Manifest-driven ingestion verifies all local PDFs before extracting page-scoped text.
The existing 1,000-character windows, 150-character overlap, and 200-character minimum
were retained. The embedding baseline is unchanged: local `all-MiniLM-L6-v2`, 384
dimensions. The versioned Chroma collection `v3_authoritative_corpus_v1` was rebuilt
successfully with 1,797 chunks across 652 PDF pages (635 pages with usable text).

Every chunk carries source filename, source ID, source SHA-256, corpus version, 1-based
PDF page, and within-page chunk index. The three PDFs are committed, and embedding model
loading explicitly uses local files only. Normal ingestion, retrieval, dashboard use,
and tests therefore have no PDF-download dependency; the local model cache remains a
documented runtime prerequisite when rebuilding embeddings.

### Retrieval smoke test and citation compatibility

Top-five dense smoke queries were `evacuation`, `relief shelter`, `flood-safe location`,
`vulnerable groups`, and `transport access`. Retrieval executed against the rebuilt
collection; together the returned results represented all three canonical source IDs,
and every result retained source ID, filename, page, text, and score. This is an
interface/metadata smoke test only, not evidence of retrieval accuracy. Hybrid search,
BM25, reranking, and retrieval evaluation remain Phase 12/13 work.

`RetrievedChunk` gained an additive `source_id` field with a backward-compatible default.
The existing verbatim citation-grounding check continues to consume source filename,
page, text, and score; no Gemini regeneration or production constraint-cache change was
made.

### Tests and verification

`tests/test_v3_corpus.py` adds 22 offline tests covering manifest loading, unique IDs and
filenames, valid and matching hashes, canonical counting, exact-duplicate rejection,
fingerprint determinism/order independence, publisher/provenance/topic integrity, PDF
page and extraction checks, spot-check records, vector ingestion, chunk provenance,
three-source coverage, multi-source retrieval output, exclusion/summary reconciliation,
and citation compatibility. The Phase 11 module passes 22/22; the full suite passes
405/405, including all 383 earlier V1/V3 regressions. The production corpus was also
rebuilt using the real cached MiniLM model and returned 1,797 384-dimensional vectors.

### Real versus simulated

The retained PDFs, publishers, publication metadata, bytes, hashes, and inspected text
are real authoritative evidence. Chunk counts, embeddings, vector distances, and smoke
results are locally measured/computed. Scenario data and shelter entities remain
simulated; generated constraints remain model-generated. An authoritative source does
not by itself make a generated claim entailed or operationally correct.

### Known limitations

- The corpus is deliberately small and all retained documents share one publisher.
- Vulnerability/accessibility coverage is weaker than intended because the dedicated
  disability guideline needs OCR, which was unavailable and outside this phase.
- Several policy documents are older and may not capture later operational practice.
- PDF extraction quality varies; some retained PDF pages lacked useful text, and a known
  NUL-encoded `ti` ligature is repaired during extraction.
- Source presence does not prove retrieval relevance, and institutional authority does
  not prove a generated claim is entailed. Phase 13 and Phase 14 address those questions.

### Artifacts and commit

The detailed audit is [`V3_CORPUS_AUDIT.md`](V3_CORPUS_AUDIT.md); the machine-readable
sanity record is `data/eval_v3/phase11_corpus_summary.json`; the rejection history is
`data/raw_docs/excluded_sources.json`. The change is committed as
`V3 Phase 11: expand authoritative disaster-guidance corpus`. Phase 12 is not started.

---

## 2026-09-07 — V3 Phase 12: dense, BM25, and hybrid retrieval

### Goal and scientific boundary

Phase 12 asks whether Sentinel-Agent can expose dense, lexical, and hybrid retrieval
through one clean, reproducible, offline interface over the exact same 1,797 chunks. It
does not ask which method is most accurate. `V3_RETRIEVAL_SPEC.md` freezes
`v3-retrieval-v1` before any Phase 13 relevance labels exist.

> Phase 12 introduces retrieval alternatives but does not establish that BM25 or hybrid
> retrieval is superior to dense retrieval. Retrieval quality will be evaluated only
> after Phase 13 creates a human-reviewed relevance benchmark.

No Hit@k, Recall, MRR, nDCG, gold labels, or reranker were created. The corpus, chunking,
Gemini prompt, production constraint cache, simulator, reward, planners, PPO checkpoints,
and frozen Phase 10 result (`NO`) are unchanged.

### Retrieval terminology and common interface

- **Dense retrieval** finds chunks whose vector embeddings are semantically close to a
  query, even when exact wording differs.
- **BM25** is a lexical ranking algorithm that rewards query terms appearing in a chunk
  while accounting for term rarity and chunk length.
- **Hybrid retrieval** uses more than one retrieval strategy.
- **Reciprocal Rank Fusion (RRF)** combines ranked lists using rank positions instead of
  directly comparing incompatible raw scores.

All three implementations expose `retrieve(query: str, k: int) -> list[RetrievedChunk]`
and are selected centrally through `get_retriever()`. The common immutable result carries
stable chunk ID, source ID, filename/source document, page, original citation text,
method ID, output rank, component scores/ranks, and corpus version/fingerprint. The old
module-level dense `retrieve()` and the original `score`, `source_document`, and
`citation()` fields remain compatible with Gemini and the demo.

Stable IDs have the form `<source_id>-p<page>-c<chunk_index>`. Dense, BM25, and hybrid
therefore refer to the same logical passages, including multiple chunks on one page.
Fusion joins only by chunk ID and rejects mismatched source/page/text metadata. It never
joins by text, page, filename, or rank.

### Dense baseline

`dense-minilm-v1` preserves the existing local `all-MiniLM-L6-v2` model, 384 dimensions,
raw query behavior, page-scoped chunks, and cosine-space Chroma collection. Chroma emits
cosine **distance**, so `dense_score` is lower-is-better and is not called similarity.
Exact score ties resolve by ascending chunk ID. Model loading explicitly uses
`local_files_only=True`.

The rebuilt local collection records both `v3-authoritative-corpus-v1` and fingerprint
`a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`. Dense retrieval
fails loudly if collection version, fingerprint, or the expected 1,797 count differs.

### BM25 and tokenizer

`bm25-okapi-v1` is a small explicit local Okapi implementation, so no package, server,
or model download was added. Parameters are frozen at `k1=1.5`, `b=0.75`, and
`epsilon=0.25`; negative Robertson/Sparck-Jones IDF values use the documented epsilon
floor. It rebuilds in deterministic source-ID/page/chunk-index/chunk-ID order from the
same verified `PreparedCorpus`. Its IDs exactly equal the canonical chunk IDs.

Tokenizer `nfkc-casefold-alphanumeric-v1` applies Unicode NFKC, `casefold()`, and Unicode
alphanumeric word runs using regex `[^\W_]+`. It performs no stopword removal, stemming,
or lemmatization. Normalization is internal only: returned citation text is unchanged.
An empty/whitespace query raises `ValueError`; no-vocabulary-overlap returns `[]`, not
arbitrary zero-score passages. BM25 ranks by decreasing score and ascending chunk ID.

### Hybrid reciprocal-rank fusion

`hybrid-rrf-v1` retrieves `max(20, requested_k)` candidates independently from dense and
BM25 and unions them by stable chunk ID. For 1-based component ranks:

```text
RRF_score(chunk) = Σ_system 1 / (60 + rank_system(chunk))
```

A passage in both lists receives both contributions; a passage in only one receives one.
If BM25 has no lexical overlap, hybrid still returns dense-derived results. A real dense
backend failure propagates instead of silently becoming BM25-only. Results sort by
decreasing fusion score and ascending chunk ID, with `fusion_rank=1..N`. No artificial
source diversity is imposed.

### Validation, determinism, citations, and offline operation

All methods reject `k <= 0`, prevent duplicate result IDs, and safely cap output at the
available candidates. Repeated calls for the fixed smoke inputs produced identical ranked
IDs and component metadata for dense, BM25, and hybrid. The synthetic A/B/C versus C/A/D
unit fixture verifies the exact RRF values and deterministic A/C/B/D order.

All methods preserve identical source ID, filename, PDF page, and original text for the
same chunk. Existing verbatim citation verification accepts the expanded result object;
no Gemini behavior or cache changed. After the already-established model/dependencies
are local, index construction and every normal query require no web access. SHA-256, not
Python's randomized `hash()`, protects corpus identity.

### Engineering smoke and latency

The offline sanity script ran top-five dense, BM25, and hybrid retrieval for
`evacuation`, `temporary shelter`, `flood-safe location`, `vulnerable groups`,
`transport access`, `relief camp sanitation`, and `route accessibility`. Each method
returned citable source/page/chunk metadata, and each method's combined results included
all three canonical source IDs. Examples show exact terms contributing to BM25 and
passages receiving both dense and lexical contributions in hybrid; these observations
are not correctness judgments.

Warmed timings use 35 calls per method and exclude one-time MiniLM/Chroma loading and
BM25 construction. BM25 construction took 14,534.94 ms on this machine.

| Retriever | Median (ms) | p90 (ms) | p95 (ms) |
| --- | ---: | ---: | ---: |
| Dense | 8.611 | 8.938 | 9.038 |
| BM25 | 0.393 | 0.617 | 0.642 |
| Hybrid RRF | 10.030 | 10.220 | 10.281 |

These are local engineering timings, not retrieval-quality metrics. Full result metadata,
startup scopes, and samples are in `data/eval_v3/phase12_retrieval_sanity.json`.

### Tests and verification

`tests/test_v3_retrieval.py` adds 48 offline tests covering the frozen corpus identity,
1,797 IDs and three sources, tokenizer behavior, dense metadata and offline loading,
explicit BM25 parameters and lexical behavior, deterministic ties, exact synthetic RRF
math, component contributions, fusion integrity/fallback, factory selection, query/`k`
validation, fingerprint/version rejection, no-network operation, and citation
compatibility. Phase 12 passes 48/48, Phase 11 passes 22/22, and the complete suite passes
453/453 including every earlier V3 and all 43 legacy V1 tests.

### Real versus computed data and limitations

The three NDMA PDFs and their source metadata remain real authoritative documents.
Chunks, token statistics, BM25 scores, dense distances, fusion scores, ranks, and latency
are locally computed. Smoke results are not human relevance judgments.

- Only three canonical documents are present, all from NDMA.
- No human-reviewed relevance labels or official accuracy figures exist yet.
- The BM25 tokenizer is intentionally simple and the dense model is unchanged from V1.
- `RRF_K=60` and candidate pool 20 are frozen retrieval design choices, not physical
  facts or empirically proven optima.
- There is no cross-encoder reranker.
- Source authority does not prove passage relevance; relevance does not prove citation
  entailment. Phase 13 and Phase 14 respectively address those questions.

### Artifacts and commit

The frozen design is [`V3_RETRIEVAL_SPEC.md`](V3_RETRIEVAL_SPEC.md); the reproducible
script is `scripts/phase12_retrieval_sanity.py`; its structured engineering artifact is
`data/eval_v3/phase12_retrieval_sanity.json`. The change is committed as
`V3 Phase 12: dense, BM25 and hybrid retrieval interfaces`. Phase 13 is not started.

---

## 2026-09-08 — V3 Phase 13A: human retrieval benchmark preparation

### Goal and human-label requirement

Phase 13A freezes the methodology and prepares review material; it does not evaluate
retriever accuracy. Machine generation may propose questions, seed passages,
explanations, and suggested grades, but those are explicitly `MACHINE_PROPOSED` and
cannot become gold truth. Only an actual human reviewer can accept/edit/reject a question
or assign passage relevance.

> **No retrieval-quality result has been calculated from machine-proposed relevance
> labels.**

The candidate version is `v3-retrieval-benchmark-candidate-v1`; the reserved future
human-reviewed version `v3-retrieval-benchmark-gold-v1` does not yet exist. Phase 13B
readiness fails until exactly 45 reviewed questions and all their passage grades satisfy
the frozen checks.

### Candidate question creation and balance

Sixty questions were drafted from direct inspection of canonical chunks before running
retrieval pools. Each records a stable source ID, filename, one-based physical PDF page,
chunk ID, verbatim supporting excerpt, and machine explanation. Questions avoid page
references, document-title hints, copied long answers, trivial metadata, and synthetic
policy facts. The simulator's `0.70` threshold is not treated as NDMA guidance.

The candidate set intentionally provides rejection room above the final 45-question
target:

| Primary topic | Candidates | Human-reviewed final target |
| --- | ---: | ---: |
| Flood risk / flood management | 12 | 9 |
| Evacuation / movement planning | 12 | 9 |
| Temporary shelters / relief camps | 12 | 9 |
| Vulnerable groups / accessibility | 12 | 9 |
| Logistics / transport / coordination | 12 | 9 |

Each topic contains four lexical, four semantic-paraphrase, and four operational
questions, yielding 20 candidates per query style. Final targets are 15 per style. Seed
coverage is 20 questions from the Flood Guidelines, 19 from the National Plan, and 21
from Temporary Shelters. Twenty-eight questions are machine-proposed as potentially
multi-source; all claimed sources appear in their review pools, but humans must determine
whether those passages are actually directly relevant.

### Frozen pooling method

For each already-written question, the unchanged `v3-retrieval-v1` systems contribute
top 10 Dense, top 10 BM25, and top 10 Hybrid results. The union is deduplicated by stable
chunk ID, and the source-derived seed is forcibly included even when retrieval misses it.
The review reduction retains the seed, every method's top five, and passages appearing in
at least two method lists; it then orders seed first, best pooled rank ascending, and
chunk ID ascending, with a cap of 18 passages per question.

This produced 647 passage-review rows. Every source/page/text tuple was checked against
the canonical 1,797-chunk catalog. Retrieval rank metadata is preserved without changing
the original citation text.

> Relevance judgments are based on a pooled candidate set from the three evaluated
> retrieval systems plus source-derived seed evidence. Relevant chunks outside the pool
> may exist.

### Relevance grades and human workflow

The human relevance scale is frozen:

- `2 — DIRECTLY RELEVANT`: directly answers or materially supports the question and
  could reasonably be cited.
- `1 — PARTIALLY RELEVANT`: useful context but insufficient by itself.
- `0 — NOT RELEVANT`: does not materially help answer the exact question.

Grade 2 defines direct gold evidence. Seed evidence carries only a machine-suggested
grade and is not pre-locked. `question_review.csv` asks the project owner to mark each
question `ACCEPT`, `EDIT`, or `REJECT`; edits require human wording. `human_review.csv`
requires a grade for every pooled passage belonging to a retained question. All 60
question statuses currently remain `PENDING`; all 647 human grades are blank and passage
statuses `PENDING`.

After the first review, exactly ten accepted questions will be selected deterministically
with seed `131313` for a second-pass, single-reviewer consistency audit. This is not
independent inter-rater reliability. The consistency CSV currently contains only its
header because no question has been accepted.

### Frozen metrics and claim rule

The primary metric for future Phase 13B is mean `DirectHit@5` over exactly 45 questions:
one when a human grade-2 passage appears in the first five, zero otherwise. Secondary
metrics are `DirectHit@1`, `DirectHit@3`, `DirectHit@5`, `MRR@5`, graded `nDCG@5`, and
`pooled Recall@5`. Pooled recall uses all human grade-2 passages in the judged pool as its
denominator and is not exhaustive corpus recall.

The principal comparison remains Hybrid versus Dense; BM25 comparisons are secondary.
Uncertainty uses 10,000 paired bootstrap resamples of whole questions with seed `131313`
and 95% percentile intervals. `HYBRID_SUPPORTED` requires all of:

1. Hybrid minus Dense DirectHit@5 of at least `0.05`;
2. a paired 95% CI lower bound strictly above zero;
3. Hybrid nDCG@5 no lower than Dense nDCG@5 minus `0.02`.

Otherwise the future result is `HYBRID_NOT_SUPPORTED`. No actual method scores or claim
were calculated in Phase 13A. Synthetic metric fixtures only verify the arithmetic.

### Review safeguards and tests

`src/rag/benchmark.py` validates candidate provenance, applies the frozen pool rule,
implements an explicit Phase 13B readiness gate, deterministically selects the future
consistency subset, and provides metric/bootstrap helpers for synthetic tests. Readiness
requires exactly nine retained questions per topic, fifteen per style, complete human
grades, a grade-2 passage for every question, grade-2 evidence from each canonical source
for at least eight questions, and at least eight genuinely multi-source grade-2 questions.

`tests/test_v3_retrieval_benchmark.py` adds 43 tests covering versions, corpus/retrieval
freeze, 60-question balance, unique questions and seed traceability, three-source
coverage, pool deduplication/cap/top-five/seed retention, rank and citation integrity,
blank human fields, readiness failures, consistency selection, metric formulas, paired
question bootstrap, and the absence of results/reranking. Phase 13A passes 43/43; the
full suite passes 496/496, including all Phase 12, Phase 11, earlier V3, and 43 legacy V1
tests.

### Real, machine-proposed, and human-reviewed status

The NDMA source text, PDFs, page locations, and corpus hashes remain real authoritative
material. Retrieval results and ranks are measured/computed. Questions, explanations,
multi-source suggestions, seed-grade suggestions, and selection proposals are machine
generated and not verified. There are currently zero human-accepted questions and zero
human passage labels.

Limitations include pooled rather than exhaustive judgments, one intended project-owner
reviewer, possible machine wording/selection bias, only three documents from one
publisher, and no current evidence about which retriever performs better. No answer
generation or entailment evaluation occurs here.

### Artifacts, commit, and stopping point

- methodology: `V3_RETRIEVAL_BENCHMARK_SPEC.md`
- human-readable packet: `V3_RETRIEVAL_HUMAN_REVIEW.md`
- provenance manifest: `data/eval_v3/phase13/candidate_question_manifest.json`
- question review: `data/eval_v3/phase13/question_review.csv`
- passage review: `data/eval_v3/phase13/human_review.csv`
- consistency template: `data/eval_v3/phase13/review_consistency.csv`
- reproducible generator: `scripts/phase13a_prepare_review.py`

The change is committed as
`V3 Phase 13A: freeze human retrieval benchmark and review packet`. Current status is
`WAITING FOR HUMAN REVIEW`. Phase 13B has not started.

---

## 2026-09-08 — V3 Phase 13A.1: adopted question review and final passage packet

### Actual question-review provenance

The project owner explicitly adopted AI-assisted recommendations for all 60 candidate
questions. The provenance record uses:

- status: `PROJECT_OWNER_ADOPTED_AI_ASSISTED_QUESTION_REVIEW`;
- method: `PROJECT_OWNER_ADOPTED_AI_ASSISTED_RECOMMENDATIONS`;
- reviewer role: `project_owner`;
- AI assistance: `true`.

This was not blind, independent, or multi-reviewer human annotation. It is accurately
described as project-owner adoption of AI-assisted question recommendations. This step
does not adopt any machine-proposed passage grade and does not constitute passage-level
human relevance review.

### Final question decisions and balance

The adopted decisions retain 45 questions: 41 `ACCEPT` decisions and four `EDIT`
decisions. Fifteen candidates are `REJECT`. The edited effective questions are:

- `Q003`: Where should flood shelters and disaster relief centres be located so that
  they remain functional during floods?
- `Q008`: How should flood warning information be presented to affected communities?
- `Q016`: What personnel, equipment, and procedures are needed to move patients safely
  during evacuation?
- `Q034`: What should authorities do when essential water, sanitation, or other services
  at a temporary shelter are disrupted?

The retained set satisfies the frozen balance exactly: nine questions in each of the
five topics and fifteen questions in each of the lexical, semantic-paraphrase, and
operational/task-oriented styles. The original 60-question candidate manifest remains
byte-for-byte unchanged.

### Retained passage review

Rejected question IDs are absent from the derived retained files, while the historical
647-row Phase 13A pool remains preserved. The retained pool contains 485 rows over 45
questions: mean 10.78 passages per question, minimum 9, and maximum 14. Every retained
row preserves its original chunk ID, source, filename, physical PDF page, authoritative
excerpt, Dense/BM25/Hybrid ranks, seed flag, and machine suggestion.

All 485 `human_grade` fields remain blank and all passage statuses remain `PENDING`.
The main final-review packet hides retriever identity, rank, seed status, and machine
suggestions to reduce anchoring during judgment. Its technical appendix preserves those
values. Exact duplicate text may be grouped only for presentation; underlying chunk
rows remain separate in the CSV.

The frozen seed-`131313` consistency selection now applies to the retained set and
selects `Q006`, `Q012`, `Q030`, `Q033`, `Q035`, `Q037`, `Q041`, `Q045`, `Q055`, and
`Q056`. No rejected question is selected, so no methodology amendment is required.
First- and second-pass consistency grades remain blank.

`tests/test_v3_retrieval_question_review.py` adds 26 Phase 13A.1 checks for the exact
decisions and edits, retained balance and provenance, immutable candidate history,
frozen passage metadata, blank human grades, consistency selection, bias-reduced packet,
unchanged corpus/retrievers, absence of reranking, and absence of official result files.
Together with the prior 496 tests, the complete suite contains 522 tests.

### Artifacts and stopping point

- retained questions: `data/eval_v3/phase13/retained_question_review.csv`
- retained passages: `data/eval_v3/phase13/retained_passage_review.csv`
- review provenance: `data/eval_v3/phase13/question_review_provenance.json`
- bias-reduced passage packet: `V3_RETRIEVAL_FINAL_PASSAGE_REVIEW.md`
- reproducible decision application: `scripts/phase13a1_apply_question_review.py`

No actual `DirectHit@1/3/5`, `MRR@5`, `nDCG@5`, pooled `Recall@5`, paired bootstrap, or
hybrid-support decision has been calculated. Current status is
`WAITING_FOR_PASSAGE_RELEVANCE_REVIEW`. Phase 13B has not started.

---

## 2026-09-08 — V3 Phase 13A.2: AI-assisted passage relevance labels

### Why the benchmark was amended

The original Phase 13 design required human passage-level relevance judgments for all
retained passages. The project owner chose not to manually annotate the 485-row set, so
that human-gold design remains unfinished. Phase 13A.2 does not rewrite that history or
fill any human field. It creates a separate AI-assisted relevance benchmark under the
formal `V3_RETRIEVAL_BENCHMARK_AI_AMENDMENT.md` amendment.

> **The benchmark's passage-level relevance judgments are AI-assisted, not independently
> human annotated.**

The new benchmark version is `v3-retrieval-benchmark-ai-assisted-v1`; its protocol is
`v3-ai-relevance-labeler-v1`. The reserved `v3-retrieval-benchmark-gold-v1` is not
created. Both historical review CSVs retain blank `human_grade` fields and `PENDING`
human status.

### Blind label procedure

All 485 fixed question–passage pairs were copied into a sanitized payload containing
only question ID, effective question, topic, query style, chunk ID, source ID, filename,
physical PDF page, and original passage text. Dense/BM25/Hybrid identities, ranks,
scores, fusion information, seed flags, machine-suggested grades, and human fields were
excluded. SHA-256 ordering of `question_id + NUL + chunk_id` also removes the historical
seed-first row-order hint.

Each pair was judged in the frozen order: assign grade 2 when the passage directly
answers or materially supports the question; otherwise assign grade 1 when it provides
specific useful but insufficient context; otherwise assign grade 0. Same-topic text
alone does not qualify. Each row includes a concise text-specific rationale and
`HIGH`/`MEDIUM`/`LOW` confidence, with confidence recorded separately from grade.

### Label set, answerability, and fingerprint

The completed AI-assisted set contains:

| AI grade | Rows | Percentage |
| --- | ---: | ---: |
| 2 — directly relevant | 118 | 24.3299% |
| 1 — partially relevant | 116 | 23.9175% |
| 0 — not relevant | 251 | 51.7526% |

Confidence totals are 108 `HIGH`, 377 `MEDIUM`, and 0 `LOW`. All 45 questions have at
least one grade-2 passage; none failed the pre-evaluation answerability check. Neither
distribution sanity flag is raised: grade 2 is below 90% and there are at least 45
direct rows. Grades were not altered to obtain these totals.

The row-order-independent label fingerprint is
`bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92`.
Rows are sorted by question/chunk, normalized to the published CSV string fields,
serialized as compact key-sorted UTF-8 JSON with non-ASCII text preserved, newline
joined with a final newline, and hashed with SHA-256. The manifest records the exact
procedure, parent commit, timestamp, balances, counts, and frozen corpus/retrieval IDs.

### AI labeling consistency and limitations

The unchanged deterministic subset contains ten questions and 107 passage pairs. A
second blind invocation of the same deterministic label protocol did not receive the
first-pass label fields. Exact agreement is 1.0 and linear weighted Cohen's kappa is
1.0; grade-2/1 and grade-2/0 disagreements are both zero. This establishes deterministic
protocol reproducibility, not inter-rater reliability or independent validation. No
reconciliation occurs and the primary first-pass AI labels remain authoritative.

The chief limitation is that passage relevance is AI-assisted rather than independently
human annotated. Deterministic agreement cannot reveal shared protocol errors, and the
label set may reflect model interpretation bias. A deterministic 15-row transparency
packet includes five examples per grade but does not mark them human reviewed.

### Artifacts, tests, and stopping point

- formal amendment: `V3_RETRIEVAL_BENCHMARK_AI_AMENDMENT.md`
- blind payload: `data/eval_v3/phase13/ai_labeling_payload.jsonl`
- frozen AI labels: `data/eval_v3/phase13/ai_assisted_passage_labels.csv`
- label manifest: `data/eval_v3/phase13/ai_assisted_label_manifest.json`
- consistency audit: `data/eval_v3/phase13/ai_label_consistency.csv`
- transparency packet: `V3_RETRIEVAL_AI_LABEL_SPOTCHECK.md`
- reproducible scripts: `scripts/phase13a2_prepare_blind_payload.py` and
  `scripts/phase13a2_label_passages.py`

`tests/test_v3_ai_assisted_relevance_labels.py` adds 46 checks covering versions,
balances, blind payload fields/order, label completeness, rationale/confidence,
human-field immutability, corpus traceability, deterministic fingerprinting,
answerability, consistency math and isolation, absence of retrieval results, and the
retrieval/corpus freeze. The complete suite contains 568 tests: 46 Phase 13A.2 tests and
522 prior tests.

**No official retrieval-quality metrics have been calculated.** No real DirectHit,
MRR, nDCG, pooled Recall, paired bootstrap, or hybrid-support decision was run. Phase
13B has not started.

---

## 2026-09-08 — V3 Phase 13B: retrieval label-coverage preflight

### Frozen inputs and AI-assisted benchmark status

Phase 13B began with the mandatory pre-metric gate for evaluation version
`v3-retrieval-evaluation-ai-assisted-v1`. The preflight verified the exact 45 final
question texts, including the adopted edits to `Q003`, `Q008`, `Q016`, and `Q034`; the
485-row `v3-ai-relevance-labeler-v1` label set; and label fingerprint
`bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92`.

Question selection was project-owner adopted with disclosed AI assistance. Passage
relevance labels were generated using a blind AI-assisted labeling protocol. The
benchmark is therefore an AI-assisted relevance benchmark and should not be represented
as independently human-annotated gold data.

The corpus remains `v3-authoritative-corpus-v1`, with fingerprint
`a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`,
three canonical documents, and 1,797 canonical chunks. Retrieval remains
`v3-retrieval-v1`: `dense-minilm-v1`, `bm25-okapi-v1`, and `hybrid-rrf-v1` retain all
Phase 12 parameters. No label, corpus content, tokenizer, embedding model, fusion rule,
or candidate depth changed, and no reranker was added.

### Coverage gate and stopping result

Each frozen retriever was run at `k=5` for every final effective question, receiving
only the query text and requested depth. The union was joined to labels by
`question_id + chunk_id`, never chunk ID alone. The result was:

| Coverage field | Result |
| --- | ---: |
| Unique top-five question/chunk pairs | 434 |
| Frozen labeled pairs | 415 |
| Unlabeled pairs | 19 |
| Affected questions | 4 |

The affected IDs are `Q003`, `Q008`, `Q016`, and `Q034`, exactly the four questions
whose final wording differs from the original pooling query. The 19 unique gaps account
for 25 retriever/rank occurrences. They are deduplicated by question/chunk in
`data/eval_v3/phase13/phase13b_label_coverage_gaps.json`, with every contributing
retriever and rank retained alongside canonical source, filename, physical PDF page,
corpus identity, and deterministic SHA-256 of the exact chunk text. Passage text for
coverage-extension labeling is reconstructed locally from the frozen corpus using
`chunk_id`. The Git-tracked gap artifact stores provenance metadata rather than
duplicating authoritative source text.

The frozen status is:

`PHASE13B_STATUS = NEEDS_LABEL_COVERAGE_EXTENSION`

Missing pairs were not assigned, inferred, or defaulted to grade 0. The original 485 AI
labels remain authoritative and byte-unchanged. The preflight script exits after writing
the gap artifact, and its explicit guard rejects any official metric path unless the
coverage status is `PASS` with zero unlabeled pairs.

### Metrics, bootstrap, and hybrid verdict

No `DirectHit@1`, `DirectHit@3`, `DirectHit@5`, `MRR@5`, `nDCG@5`, or pooled
`Recall@5` value was calculated. The 10,000-resample paired bootstrap with seed `131313`
was not run. Consequently there is no Hybrid-minus-Dense estimate, confidence interval,
nDCG guardrail result, or `HYBRID_SUPPORTED`/`HYBRID_NOT_SUPPORTED` verdict.

Topic and query-style subgroup metrics, Hybrid/Dense head-to-head counts, rank-level
comparisons, source-distribution diagnostics, and post-metric failure analysis were also
not performed. Those analyses require complete coverage and remain deferred; no
retrieval behavior was tuned in response to the observed gaps.

### Scientific boundaries

This stopped preflight evaluates label coverage only. It establishes neither retrieval
quality nor better disaster decisions, safer evacuation, or improved real-world
outcomes. Passage relevance is also not claim entailment, and no conclusion about
generated citation support is made. Phase 14 has not started. The frozen Phase 10 RL
usefulness result remains `NO`.

### Reproducibility, tests, artifact, and commit

`scripts/phase13b_retrieval_preflight.py` verifies every frozen identifier, reconstructs
the canonical corpus, runs the exact three retrievers, captures the top-five union, and
writes deterministic gap output. Repeated execution produces the same 434/415/19 result
and the same ranked gap records.

`tests/test_v3_retrieval_evaluation.py` adds 26 checks covering exact evaluation,
benchmark, label, corpus, and retrieval identities; final edited queries; actual gap
counts; composite-key joining; canonical traceability; cross-retriever deduplication;
local chunk reconstruction with provenance and text-hash validation; absence of tracked
passage text; label immutability; grade-0 refusal; metric blocking; leakage isolation;
deterministic replay; the complete-coverage control path; absence of results; and the
no-reranker freeze. The complete suite contains 594 tests after adding these checks.

- gap artifact: `data/eval_v3/phase13/phase13b_label_coverage_gaps.json`
- reproducible preflight: `scripts/phase13b_retrieval_preflight.py`
- regression tests: `tests/test_v3_retrieval_evaluation.py`
- commit: `V3 Phase 13B preflight: identify retrieval label coverage gaps`

Phase 13B stops here. A separately instructed pre-metric label-coverage extension is
required before any official retrieval metric may be computed.

---

## 2026-09-08 — V3 Phase 13A.3: pre-metric label coverage extension

### Why the extension was required

The Phase 13B coverage gate used the final effective question text and found that the
adopted wording changes for `Q003`, `Q008`, `Q016`, and `Q034` changed top-five retrieval
membership. Of 434 unique top-five question/chunk pairs, 415 were present in the frozen
Phase 13A.2 label set and 19 were not. The gate correctly returned
`NEEDS_LABEL_COVERAGE_EXTENSION` and stopped before any retrieval-quality metric,
bootstrap interval, or hybrid verdict was calculated.

Commit `b2435a5d8d8ea98c4702ba67601c72dbc13fd5ce` froze and sanitized the exact 19-pair
gap set before labeling. Phase 13A.3 uses all and only those pairs; it does not rerun
retrieval to discover a different set, expand to top ten, or select gaps based on
observed quality.

### Local reconstruction and blind labeling

Passage text for coverage-extension labeling is reconstructed locally from the frozen
1,797-chunk corpus using `chunk_id`. Every chunk resolved exactly once, and its source
ID, filename, physical PDF page, corpus identity, and SHA-256 matched the frozen gap
metadata. The Git-tracked gap and label-extension artifacts store provenance and hashes
rather than duplicating authoritative source text.

The blind labeler received only question ID, effective question, chunk ID, source ID,
filename, page, and locally reconstructed passage text. It did not receive retriever
identity, rank, score, fusion data, seed status, old machine suggestions, prior labels,
or an indication of which method exposed a gap. Rows were presented in neutral
`question_id + chunk_id` order. The unchanged `v3-ai-relevance-labeler-v1` decision
protocol was applied to each passage independently.

### Extension and combined labels

The coverage extension version is `v3-retrieval-label-coverage-extension-v1`:

| Extension grade | Rows |
| --- | ---: |
| 2 — directly relevant | 3 |
| 1 — partially relevant | 8 |
| 0 — not relevant | 8 |

Confidence totals are 6 `HIGH`, 13 `MEDIUM`, and 0 `LOW`. Each row is `COMPLETE`, has a
concise passage-specific rationale, preserves the original protocol, and stores a source
passage SHA-256 rather than passage text.

The original 485-row `v3-retrieval-benchmark-ai-assisted-v1` artifact remains
byte-for-byte unchanged with parent fingerprint
`bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92`.
The new combined benchmark is `v3-retrieval-benchmark-ai-assisted-v2`:

| Combined-label field | Result |
| --- | ---: |
| Parent rows | 485 |
| Extension rows | 19 |
| Total unique question/chunk rows | 504 |
| Grade 2 | 121 |
| Grade 1 | 124 |
| Grade 0 | 259 |

Its extended fingerprint is
`393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7`.
The compact combined CSV excludes passage text, includes source-passage SHA-256 and label
origin, and uses the exact field list published in the extended manifest. Fingerprinting
coerces each included value to its CSV string, serializes a compact key-sorted UTF-8 JSON
object with non-ASCII preserved, sorts rows by question/chunk, joins records with LF and
one final LF, and applies SHA-256.

### Coverage, answerability, and repeat diagnostic

All 19/19 frozen gap pairs are present in v2. Because the parent artifact and fingerprint
are unchanged, all 415/415 previously labeled preflight pairs remain present; frozen
preflight label coverage is therefore 434/434 with zero unlabeled pairs. This is only a
label-presence verification and is not Hit@k or any other quality metric. All 45
questions still have at least one grade-2 passage in the combined set.

The tiny consistency diagnostic selects five pairs by SHA-256 of
`question_id + "|" + chunk_id`, independent of relevance and retriever metadata. A
separate blind pass agreed on all five labels: exact agreement 1.0, zero disagreements,
and absolute grade difference zero for every pair. Weighted kappa is not reported for
this tiny diagnostic. No reconciliation occurred; first-pass extension labels remain
authoritative.

### Scientific and frozen-integrity boundaries

This extension is allowed because the pre-registered gate found and froze the complete
gap set before any metric, and the same blind protocol was applied without changing a
retriever or selecting only convenient passages. The benchmark remains AI-assisted,
not human gold, human annotated, independently human reviewed, or expert annotated.
Human passage labels created remain zero.

Dense `dense-minilm-v1`, BM25 `bm25-okapi-v1`, Hybrid `hybrid-rrf-v1`, MiniLM,
chunking, tokenizer, BM25 parameters, `RRF_K=60`, candidate depth, and the corpus remain
unchanged. No reranker was added. No DirectHit, MRR, nDCG, pooled Recall, Hybrid-minus-
Dense difference, bootstrap, `HYBRID_SUPPORTED`, or `HYBRID_NOT_SUPPORTED` result was
calculated. The Phase 10 RL usefulness result remains `NO`, and Phase 14 has not started.

### Artifacts, tests, commit, and stopping point

- extension labels: `data/eval_v3/phase13/ai_assisted_passage_label_extension.csv`
- compact combined labels: `data/eval_v3/phase13/ai_assisted_passage_labels_extended.csv`
- extended manifest: `data/eval_v3/phase13/ai_assisted_label_manifest_extended.json`
- tiny repeat diagnostic: `data/eval_v3/phase13/ai_label_extension_consistency.csv`
- reproducible generator: `scripts/phase13a3_extend_labels.py`
- regression tests: `tests/test_v3_retrieval_label_extension.py`

The new tests add 33 behavioral checks for the frozen gap set, local reconstruction,
blind-input isolation, exact extension labels, compact combined data, deterministic
fingerprints, 434/434 label presence, answerability, tiny consistency replay, absence of
quality metrics, human-field immutability, and retrieval/corpus freeze. Together with the
594 prior tests, the complete suite contains 627 tests.

The change is committed as
`V3 Phase 13A.3: extend blind relevance labels for coverage`. Phase 13A.3 stops after
freezing v2. Full Phase 13B evaluation has not been run and must start from scratch in a
separate phase.

---

## 2026-09-08 — V3 Phase 13B: frozen retrieval benchmark evaluation

### Frozen inputs and rerun boundary

Phase 13B evaluates `v3-retrieval-benchmark-ai-assisted-v2`, containing 504 unique
question/chunk labels across 45 final questions. Its fingerprint is
`393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7`; the unchanged
485-label parent fingerprint remains
`bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92`.

The corpus remains `v3-authoritative-corpus-v1`, fingerprint
`a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`, with three
documents and 1,797 chunks. Dense `dense-minilm-v1`, BM25 `bm25-okapi-v1`, and Hybrid
`hybrid-rrf-v1` were reconstructed and rerun at `k=5` for every final effective query.
BM25 remains `k1=1.5`, `b=0.75`, `epsilon=0.25`; Hybrid remains RRF with constant 60 and
per-component candidate depth `max(20,k)`. No reranker, query edit, corpus change, label
change, or retrieval change was introduced.

Passage text for coverage-extension labeling is reconstructed locally from the frozen
corpus using `chunk_id`. The Git-tracked gap artifact stores provenance metadata rather
than duplicating authoritative source text. Phase 13B result and ranking artifacts are
also compact and contain no full passage text.

### Fresh coverage gate

The evaluator recomputed the union of all top-five `(question_id, chunk_id)` pairs and
joined it to the extended labels using that composite key. Coverage passed at 434/434
unique pairs with zero unlabeled pairs. Missing labels are never interpreted as grade
zero; an incomplete join raises a hard error before every metric path.

### Official metrics

Grade 2 alone counts for DirectHit and MRR. nDCG uses grades 0/1/2 with gain
`2^relevance - 1` and an ideal ranking from all labels for the question. PooledRecall@5
is the fraction of the question's distinct pooled grade-2 chunks retrieved in the top
five; it is not exhaustive corpus recall.

| Retriever | DirectHit@1 | DirectHit@3 | DirectHit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.5111 | 0.5778 | 0.6222 | 0.5519 | 0.5208 | 0.4129 |
| BM25 | 0.5333 | 0.7778 | 0.8667 | 0.6619 | 0.5906 | 0.5901 |
| Hybrid | 0.5111 | 0.7556 | 0.8222 | 0.6256 | 0.5950 | 0.5892 |

Raw DirectHit@5 counts are Dense 28/45, BM25 39/45, and Hybrid 37/45. BM25 comparisons
remain secondary and descriptive; the pre-registered principal comparison is Hybrid
versus Dense.

### Principal result and frozen verdict

Hybrid minus Dense DirectHit@5 is `+0.2000`, equivalent to a net advantage of nine
questions. The exactly 10,000-resample paired question-level percentile bootstrap with
seed `131313` gives a 95% interval of `[0.0889, 0.3111]`. All three frozen support
conditions pass: the difference is at least 0.05, the interval lower bound is above
zero, and Hybrid nDCG@5 is no worse than Dense nDCG@5 minus 0.02. The formal verdict is:

`HYBRID_SUPPORTED`

With 45 questions, one question equals 0.02222, two equal 0.04444, and three equal
0.06667; therefore the frozen 0.05 effect threshold requires a net advantage of at
least three questions.

### Diagnostics and limitations

Hybrid and Dense both hit on 28 questions, Hybrid alone hit on nine, Dense alone hit on
zero, and neither hit on eight. Among the 28 shared successes, Hybrid placed the first
direct passage earlier twice, tied 24 times, and placed it later twice. Descriptive
topic results use five groups of nine questions, and query-style results use three
groups of 15. Full six-metric subgroup tables, secondary deltas, compact per-case failure
analysis, and top-five source distributions are recorded in
`V3_RETRIEVAL_EVALUATION.md` and the structured result JSON.

The full benchmark was executed twice from fresh retriever objects. Top-five IDs,
coverage, per-question metrics, overall metrics, bootstrap interval, and verdict were
identical. Retrieval received only query text and `k`; labels, seed evidence, topic, and
query style were excluded from ranking.

This result is based on AI-assisted blind passage judgments and project-owner-adopted
AI-assisted question review. It is not independently human-annotated gold data. The 19
coverage-extension pairs were blindly labeled before metrics because the pre-registered
gate required complete top-five coverage; labels were not changed after results. The
three-document, single-publisher pool is small, and pooled recall is not exhaustive.
Passage relevance does not prove claim entailment, and retrieval quality does not prove
safer decisions or improved real-world outcomes.

Phase 13 has no authority to revise the Phase 10 RL usefulness result, which remains
`NO`. Phase 14 has not been started.

### Phase 13B artifacts

The Phase 13B regression module contains 37 checks, and the complete repository suite
passes all 638 collected tests.

- evaluator: `scripts/phase13b_evaluate_retrieval.py`
- structured result: `data/eval_v3/phase13/phase13b_retrieval_results_v2.json`
- 45-row question metrics: `data/eval_v3/phase13/phase13b_per_question_v2.csv`
- compact 675-row ranking provenance: `data/eval_v3/phase13/phase13b_rankings_v2.csv`
- evaluation report: `V3_RETRIEVAL_EVALUATION.md`
- regression coverage: `tests/test_v3_retrieval_evaluation.py`

---

## 2026-09-08 — V3 Phase 14A: claim–evidence support benchmark

### Goal and conceptual boundary

Phase 14A freezes the terminology, benchmark construction, interface, metrics, leakage
controls, and future decision gate needed to test whether evidence supports an exact
claim. It separates three properties: source integrity asks whether provenance resolves
and a quote exists verbatim; retrieval relevance asks whether a passage helps answer an
information need; claim support asks whether the evidence establishes every material
proposition in a claim. A citation may pass the first two and fail the third.

The V1 deterministic `check_grounding` behavior remains backward compatible and is
formalized as `quote-integrity-v1`. It answers source/quote existence, not semantic claim
support. No existing constraint-generation, citation, corpus, or retrieval module was
refactored.

### Construction-labeled challenge and evidence selection

The challenge is `v3-claim-support-challenge-v1`, built under
`v3-claim-support-construction-v1`. It is construction-labeled with AI-assisted claim
writing; it is not independently human-gold, expert annotated, or an independent human
annotation exercise.

All 45 final Phase 13 questions are included. For each question, every frozen grade-2
chunk is collected, stable chunk IDs are sorted ascending, and the first is selected.
The selector never consumes Dense/BM25/Hybrid identity, rank, score, or Phase 13 method
performance. This gives 45 question-level evidence selections comprising 31 unique
underlying chunk IDs because some questions legitimately share one directly relevant
passage.

Every selection was reconstructed from the frozen 1,797-chunk corpus and verified for
chunk uniqueness, source ID, filename, physical PDF page, corpus identity, and exact
UTF-8 passage SHA-256. Full authoritative passage text is absent from the machine-readable
benchmark; only metadata and hashes are tracked there. The review packet contains short
local excerpts for inspection.

Each question has a concise supported paraphrase, a realistic partial overstatement,
and a plausible same-domain unsupported claim over exactly the same evidence. Totals are
135 pairs with exact 45/45/45 class balance. All rows are synthetic variants and are
marked `not_authoritative_policy=true`; negative rows are prominently marked in the
review packet. For supported rows, that flag means the generated paraphrase is not
authoritative wording even though the evidence supports its proposition.

### Interface and two-layer verification

`src/constraints/claim_support.py` freezes `EvidenceChunk`, `ClaimSupportVerdict`,
`ClaimSupportResult`, and the future
`verify_claim_support(claim, evidence) -> ClaimSupportResult` interface. The Phase 14A
entry point intentionally raises `NotImplementedError`; semantic execution belongs only
to Phase 14B.

Layer 1 deterministically checks source provenance, text hash, and whether every returned
supporting span occurs verbatim in the evidence. Layer 2 will semantically classify
`SUPPORTED`, `PARTIALLY_SUPPORTED`, or `UNSUPPORTED`. A semantic result cannot override
a failed integrity layer. Supported and partial results require supporting spans.

The future provider payload contains only the claim, authoritative evidence, and source
provenance. Tests reject leakage of construction label/reason/subtype, synthetic flags,
Phase 13 grades, retriever identity/rank, and expected verdict.

### Frozen metrics and decision gate

Only `SUPPORTED` maps to `SAFE_TO_CITE`; partial and unsupported claims are unsafe as-is.
The primary Phase 14B metric is three-class Macro-F1. Secondary measures are accuracy,
per-class precision/recall/F1, confusion matrix, supported precision, safe-to-cite
precision/recall, unsafe citation acceptance, and source/span integrity failure rate.
Unsafe acceptance divides partial-or-unsupported examples predicted supported by the
fixed denominator 90.

The future verifier is useful only if all four project engineering thresholds pass:
Macro-F1 >= 0.75, supported precision >= 0.85, unsafe acceptance <= 0.15, and
span/integrity failure <= 0.05. Otherwise it is not yet reliable. The evaluation order
sorts by SHA-256 of pair ID plus the frozen challenge fingerprint and never uses labels.
Metric code was exercised only on toy fixtures.

### Fingerprint, audit, and limitations

The challenge fingerprint is
`54efc3722593fcba154ce360fe22452c8524bd1d195fc0ee96bc4ebbffd5fcc0`.
Canonical records sort by pair ID, serialize the published fields as compact UTF-8 JSON
arrays in fixed field order, use LF separators plus one final LF, and are SHA-256 hashed.
The 15-example inspection sample has five examples per class. The duplicate audit found
zero exact claims, zero normalized duplicates, zero supported claims copied verbatim in
full, zero unresolved evidence chunks, and zero hash mismatches.

Controlled constructions can differ from naturally occurring model errors and may make
some cases easier. The corpus remains three documents from one publisher. Construction
labels do not provide independent semantic validation, and future performance must be
reported with that limitation.

### Files and verification

- specification: `V3_CLAIM_SUPPORT_SPEC.md`
- challenge: `data/eval_v3/phase14/claim_support_challenge.json`
- manifest: `data/eval_v3/phase14/claim_support_manifest.json`
- deterministic spotcheck: `data/eval_v3/phase14/claim_support_spotcheck.json`
- human-readable audit: `V3_CLAIM_SUPPORT_CHALLENGE_REVIEW.md`
- interface and helpers: `src/constraints/claim_support.py`
- reproducible builder: `scripts/phase14a_prepare_claim_support.py`
- regression tests: `tests/test_v3_claim_support_benchmark.py`

The Phase 14A module passes 38 focused tests, and the complete offline regression suite
passes 676/676. The frozen Phase 10 result remains RL
usefulness `NO`; Phase 13 remains `HYBRID_SUPPORTED` versus Dense, and BM25 remains the
highest DirectHit@5 method. No reranker, PPO retraining, corpus change, retrieval change,
question edit, or relevance-label change occurred.

> **NO OFFICIAL CLAIM-SUPPORT VERIFIER PERFORMANCE RESULT WAS CALCULATED IN PHASE 14A.**

Phase 14B later began under the frozen Phase 14A protocol and is currently paused due to
the Gemini daily quota. No complete or partial performance metric is reported here.

---

## 2026-09-09 — V3 demo: human override and audit trail

### Purpose and boundaries

The standalone project-review dashboard now demonstrates Sentinel-Agent as a
human-in-the-loop decision-support system rather than an autonomous disaster commander.
The feature is entirely offline and does not constitute a new research experiment. It
does not change the simulator, planner, safety rules, corpus, retrieval benchmark, PPO,
or any frozen scientific result.

The tab prominently preserves the scientific posture: Phase 10 RL usefulness remains
`NO`; Phase 13 remains `HYBRID_SUPPORTED` versus Dense; BM25 retains the highest
DirectHit@5; and Phase 14B is `PAUSED — API quota`. No partial Phase 14B accuracy or F1
is calculated or displayed.

### Existing components reused

The demo instantiates the existing deterministic Gate 6 practical scenario generated
from seed `620000`, runs it through `StochasticSimulator` under the frozen medium
uncertainty configuration, recomputes the existing deterministic Phase 5 safety mask,
and obtains the recommendation from `RiskGreedyPlanner`. Current zone populations and
flood severities, shelter status/capacity/severity, and route reachability/travel
estimates are rendered directly from the policy-safe simulator observation.

An offline evidence card selects an existing direct-evidence Phase 13 Hybrid result for
Q015, reconstructs the chunk from the unchanged local corpus, and displays only a short
excerpt plus document, page, and chunk provenance. The audit record stores provenance,
not the authoritative passage text. The dashboard explains that relevant retrieved
context is distinct from the separately evaluated Phase 14 semantic support question.

### Human controls and deterministic enforcement

- `ACCEPT` executes the current planner recommendation; its note is optional.
- `OVERRIDE` requires a reason and offers only alternatives in the current deterministic
  allowed-action mask. The chosen action is re-evaluated through the same mechanical and
  hard-safety checks immediately before simulator execution.
- `REJECT` requires a reason, records `executed_action=NONE`, and does not advance the
  simulator.

The core decision helper rejects an action outside the current canonical action set,
any mechanically invalid action, any hard-safety exclusion, an override that repeats the
recommendation, and a reasonless override or rejection. ACCEPT and valid OVERRIDE use
the unchanged simulator `step` implementation and advance the synthetic incident.

### Session audit trail

Each record contains `audit_id`, UTC timestamp, scenario ID, timestep, planner,
recommended action, decision, executed action, mechanical validity, safety result,
human reason, and evidence source/page/chunk ID. Records remain in Streamlit session
state only, are shown as a dataframe, and can be downloaded with Streamlit's built-in
CSV download control. The feature does not persist personal information or full source
passages.

### Verification and limitations

Focused tests exercise ACCEPT, required REJECT reasons, safe OVERRIDE choices, explicit
blocking of excluded actions, audit-to-dataframe/CSV behavior, dashboard compilation,
tab rendering, a UI ACCEPT interaction, and absence of Gemini/network integration. The
demonstration uses one fixed synthetic scenario and one planner; it is not operational
emergency-response validation, and session audit rows are not a durable production
audit store.

### Files

- `review_dashboard.py`
- `src/human_decision.py`
- `tests/test_human_decision_demo.py`
- `README.md`
- `DOCUMENTATION.md`

---

## 2026-09-09 — Phase 19 Live Decision and Timeline integration milestone

### Scope

This milestone extends the existing Human Override & Audit feature using the master
plan's Phase 19 **Dashboard V3 / Live Decision / Timeline** terminology. It does not
declare all of Phase 19 complete: later verification and broader dashboard work remain. It connects
the already implemented stochastic simulator, deterministic safety layer, Risk-Greedy
planner, contextual offline evidence, human control, and audit trail into one
multi-timestep review flow. No scientific experiment was run and no frozen result was
changed.

The default remains the existing Gate 6 practical generator seed `620000` with the
existing `v3-medium-v1` uncertainty configuration. The existing LOW, MEDIUM, and HIGH
configurations may be selected and take effect only after **Reset Scenario**. Reset is
deterministic for a selected configuration and clears browser-session playback data; it
does not write to evaluation artifacts.

### Interactive episode

The live panel shows timestep/horizon and the conserved population ledgers (total,
remaining, in transit, and safely arrived). It renders actual zone flood state, initial
vulnerable population, shelter status/capacity/occupancy/reservations, route state and
travel estimates, and pending dispatch ETA. ACCEPT and a permitted OVERRIDE each execute
exactly one transition through the unchanged simulator; REJECT records `NONE` without a
transition. The event timeline is made from the human record and the transition's real
audit events, including dispatches, arrivals, flood updates, route closures, and shelter
degradation only when those events actually occur.

Population progress is session playback, not an evaluation metric. The live summary
computes decision counts, population ledgers, and unsafe executed actions from actual
audit validation fields. The terminal summary reports the single synthetic episode
without comparing it statistically with frozen research policies.

### Audit, evidence, and exports

Decision rows now include the fixed generator seed, generated scenario seed, uncertainty
regime/configuration, and compact source-zone and destination-shelter state snapshots in
addition to the original recommendation, decision, execution, validation, reason, and
evidence provenance. They contain no complete authoritative passage. The Phase 13 card
remains explicitly contextual: semantic claim-support verification is still incomplete
in Phase 14B.

The browser session provides a CSV decision-audit download and JSON summary download.
Nothing is written to a database. The Phase 14B card reports the 135-example benchmark,
paused daily-quota state, and 21/135 dispositions without calculating or displaying a
partial accuracy, Macro-F1, confusion matrix, or success rate.

### Boundaries and verification

The feature is fully offline and makes no Gemini, OpenAI, web, map, weather, or flood-feed
request. It does not modify the reward, PPO, policy evaluation, Phase 10 artifacts,
Phase 11 corpus, retrievers, Phase 13 artifacts, Phase 14A benchmark, or any frozen Phase
14B prompt/model/order/cache. Focused tests cover deterministic initialization/reset,
all supported uncertainty configurations, allowed planner output, one-step ACCEPT and
OVERRIDE behavior, non-advancing REJECT behavior, population and shelter ledgers, actual
timeline events, progress history, audit/summary serialization, Streamlit interactions,
offline-only source checks, and preservation of the Phase 14B cache.

---

## 2026-09-09 — Phase 16/17 cached geospatial and hazard-routing integration

### Architecture and provenance

The project now has the master plan's Phase 16 **Geospatial Road Network** and Phase 17
**Integrate Stochastic Hazards With Graph Routing** demonstration layer. A one-time
Overpass development download was reduced to the compact, versioned local artifact
`data/geospatial_v3/fort_kochi_osm_drive_v1.json`; the raw response is not tracked and
the review dashboard needs no network. The manifest freezes the Fort Kochi bounds,
source/ODbL attribution, OSM snapshot time, exact query, filter, coordinate semantics,
622-node and 1,358-directed-edge counts, and graph fingerprint
`dff7f2065ab5be8685ffd1195cdab1eaf8ce0b28716f5553f146c7565906a6e3`.

The SHA-256 covers canonical static topology and entity mappings, never dynamic hazard
or closure state. Loading recomputes and verifies it. OSM node and way identifiers are
retained in deterministic graph IDs. Edge length comes from WGS84 node coordinates;
class-based speed and travel time are explicitly synthetic assumptions.

Four fictional zone points and five fictional shelter candidates are deterministically
mapped to real road nodes. They are not claims about local population, certified
shelters, or operational facilities. **Road topology may be derived from real geographic
data, while flood hazards, population demand, shelter conditions and evacuation
decisions remain simulated.**

### Routing, stochastic evolution, and integration

NetworkX finds the shortest directed path by current edge travel time. Closed edges are
removed; a disconnected pair is returned as `UNREACHABLE` with no Euclidean fallback.
At each prepared simulator timestep, the geospatial overlay interpolates edge hazard
from the existing simulated zone/shelter state, adds only keyed local stochastic
variation, applies the selected frozen uncertainty configuration's travel and closure
parameters, and retains absorbing closures. The same seed, configuration, and action
sequence produce identical road states and paths.

The adapter uses the simulator's existing intervention hook and projects graph path
metrics into existing route-level state. This preserves the planner interface: the
Risk-Greedy implementation is unchanged. The existing deterministic safety evaluator
mechanically excludes any dispatch with no open graph path, so planner candidates and
human override choices cannot include graph-impossible destinations.

A dispatched group remains committed to its existing source, destination, population,
and arrival event. Later closures affect new dispatches but do not delete or retroactively
reroute it. This intentionally preserves the current simulator semantics rather than
implementing the master plan's possible future next-node rerouting approximation.

### Dashboard, audit, and limits

The Human Override tab now has a tile-free Altair road view that renders without a live
basemap. It labels simulated zones and shelters, distinguishes open and closed directed
roads, and highlights the current recommendation path. The recommendation and override
preview display graph status, distance, estimated time, edge count, and compact path ID.
Decision audits store graph version, fingerprint, local artifact provenance, compact path
hash, distance, estimated time, and edge count—not giant node/edge arrays.

A non-scientific local responsiveness diagnostic measured a current-path query at about
1.15 ms mean and 1.32 ms maximum during the fixed-seed ten-step review episode. This is
not a policy benchmark or performance claim. Known limits include OSM data quality,
straight segments between OSM nodes, assumed speeds, simulated hazards/closures, no live
traffic or flood data, fictional entity placements, and no in-transit rerouting. The
full technical contract and boundary statement are in `V3_GEOSPATIAL_SPEC.md`.

No Gemini request, retrieval run, PPO training, policy evaluation, partial Phase 14B
metric, or frozen research-artifact modification occurred.

---

## 2026-09-09 — Complete university project-review dashboard

### Presentation-only scope

`review_dashboard.py` is now organized as one six-tab faculty-review experience:
**Overview**, **Live Evacuation**, **Policy & RL**, **Evidence / RAG**, **Human Override
& Audit**, and **Research Progress**. Review Mode is enabled by default and exposes a
concise three-minute demonstration sequence in the sidebar and Research Progress tab.
This work reads committed artifacts and invokes only the existing local simulator,
safety, planning, retrieval-display, geospatial, and audit logic. It does not train PPO,
rerun Phase 10 or Phase 13, call Gemini, calculate incomplete Phase 14B metrics, or alter
any frozen research artifact.

### Review narrative and artifact-backed facts

The Overview loads and displays 600 held-out stochastic scenarios, five PPO seeds,
250,000 timesteps per seed (1.25 million total), three NDMA documents, 1,797 corpus
chunks, 45 retrieval questions, 135 claim-support examples, and the 622-node / 1,358
directed-edge Fort Kochi graph. It explicitly distinguishes the real road topology from
simulated flood, population, shelter, traffic, closure, and decision conditions.

The Policy & RL tab combines frozen training, held-out evaluation, and latency trade-off
views. It preserves the five-seed validation-return chart, representative seed `4404`,
the `POTENTIAL_SLOT_SHORTCUT` diagnostic, all frozen NSU values, and PPO minus
Risk-Greedy at `-0.7919` with 95% CI `[-0.8384, -0.7453]`. The conclusion remains
`RL USEFULNESS = NO`: PPO was evaluated rather than assumed superior, and the negative
result was retained.

The Evidence / RAG tab presents exact frozen DirectHit@1/3/5 counts and nDCG@5 for
Dense, BM25, and Hybrid. It reports `HYBRID_SUPPORTED` versus Dense, the `+0.2000`
DirectHit@5 difference (nine questions; 95% CI `[0.0889, 0.3111]`), and separately
preserves the unexpected result that BM25 had the highest DirectHit@5. The offline
evidence explorer reconstructs short source excerpts locally and labels Phase 13
relevance judgments as AI-assisted.

### Live geography, human authority, and progress

Live Evacuation renders the local Fort Kochi graph, zone/shelter state, open and closed
roads, route distance and closure state, in-transit groups, the highlighted recommended
path, and planner/safety/graph checks. ACCEPT executes one recommendation, OVERRIDE is
limited to valid, safe, graph-reachable alternatives and requires a reason, and REJECT
records a reason without dispatching. Human Override & Audit presents the current
recommendation, operator authority, full session audit table, compact graph and NDMA
provenance, eight live summary values, and CSV/JSON exports. Full authoritative passage
text is never stored in the audit.

Research Progress distinguishes completed work from Phase 14B's paused semantic
claim-support evaluation. It shows only the operational progress facts—21/135 official
dispositions, 19 successful predictions, and two invalid outputs—and explicitly states
that the incomplete run has no official scientific result. The claim-support explanation
separates source integrity, retrieval relevance, and exact claim support using a clearly
marked conceptual example. Phase 14A examples remain described as AI-assisted,
construction-labeled data.

### Verification

Presentation checks cover all six tabs and artifact-backed KPIs; offline evidence choices;
the real road view and highlighted recommendation path; ACCEPT, OVERRIDE, and REJECT;
audit updates and graph provenance; paused Phase 14B communication; and absence of
Gemini/network clients. The focused dashboard/human/geospatial suite passes 38 tests.
The complete offline repository suite passes all 714 collected tests. The dashboard
compiles with `python -m py_compile review_dashboard.py` and is launched with
`streamlit run review_dashboard.py`.

---
