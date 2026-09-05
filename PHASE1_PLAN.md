# Phase 1 plan — variant B (allocation with delivery lag)

Status: **draft for approval. Nothing here is built.** Supersedes `EXPANSION_PLAN.md`
§1.2–§1.8 where the two conflict; everything it does not mention still stands.

Written against the Gate 1A result (`DOCUMENTATION.md`, 2026-09-05) on branch
`v2-resources`. All numbers below are measured and traceable — Gate 1A results in
`data/eval_results/gate1a_*.json`, v1 results in `EVALUATION_V1.md`.

---

## 0. What changed since `EXPANSION_PLAN.md` was written

| | Plan as written | After Gate 1A |
| --- | --- | --- |
| The task | complementarity + contention + time-dependence | **plus per-cell delivery lag** — without it the design is greedy-solvable |
| Gate size | 3 cells × 3 timesteps | **≥4 cells × ≥5–6 timesteps.** At 3×3 the gate returns a confident, misleading STOP |
| Gate baseline | `myopic_greedy` | **the strongest hand-written heuristic**, currently `bundle_aware` |
| Gate criterion | % optimal only | **% optimal *and* absolute headroom** — 91.7% optimal with a 0.4% mean gap is not "workable" |
| Headline metric | unstated | **declared in §2 below, before any v2 training runs** |

---

## 1. Gate 1A.5 — tail characterisation (**do this first; it is the only remaining stop signal**)

Gate 1A said proceed, on `bundle_aware` scoring **48.3% optimal** at 4×6 with lag. That
number is not as strong as it looks:

```
optimal 48.3%   mean gap 71.2%   MEDIAN gap 1.1%   p90 gap 56.4%   max gap 2137.6%
```

A median gap of 1.1% means the heuristic is **usually near-optimal** and occasionally
catastrophic. Before building anything, establish whether that tail is real, structured,
and worth a learned policy. Four questions, all offline, no API calls:

**Q1 — Is the ratio inflated by near-zero optima?** `mean 71.2%` against `median 1.1%` is
the signature of dividing by a small denominator. Recompute every gap in absolute reward
units and as a normalised score (§2). If the tail evaporates under a sane denominator,
the headroom was an artifact.

**Q2 — Where does the improvement actually live?** Sort instances by absolute regret and
compute what fraction of total available improvement sits in the top decile. If ~90% of
it is in ~5% of instances, a policy trained on mean reward has almost no gradient toward
it, and "RL wins on average" is unlikely regardless of design.

**Q3 — Is the tail structured or arbitrary?** Fit a small decision tree predicting
"top-decile regret" from instance features (lag spread, stock tightness, severity
crossover, bundle cost, population spread), scored by cross-validated AUC.

> **A raw AUC here is uninterpretable and must not be reported alone.** A tree on this
> many features at this n will find *something*. The comparison that matters is against a
> null: **refit the identical pipeline on shuffled labels**, 200 permutations, and report
> the null AUC distribution (mean and 95th percentile) beside the real one. Real 0.72
> against a shuffled 0.68 is nothing. The claim is the *separation*, not the number — and
> having just watched `n=10` flip the strongest-heuristic identity on pure noise, this
> guard is mandatory, not optional.

**Q4 — the decisive one — can a cheap planner close the gap, and at what price?**
Implement `lookahead_planner`: exhaustive search over the next *k* dispatches, greedy
tail, k ∈ {2,3}, plus a beam-search variant (width 3–5). ~40 lines.

> **Score alone is not the comparison — the planner and a policy do not face the same
> clock.** A planner searching at decision time buys quality with latency; a trained
> policy is a forward pass. "Ship the planner" is the right call for a paper and possibly
> the wrong one for a system meant to re-plan as conditions change. So **record
> per-decision wall-clock cost alongside the score**, for every policy, with v1's
> `MaskablePPO.predict()` measured as the millisecond reference for what a learned policy
> actually costs.

### Gate 1A.5 decision rule

| Outcome | Action |
| --- | --- |
| Planner ≥ 95% normalised score **at latency within ~10× of policy inference** | **STOP. Do not build.** Clean stop: the task is solvable without learning, at a cost a real system would happily pay. Ship the planner. |
| Planner ≥ 95% **but at ≫100× the latency** | **Judgement, not a threshold.** The finding is "solvable, but not at re-planning speed", and the case for a learned policy becomes *latency*, not quality. Proceeding is then allowed only if that is stated as the entire justification — and it is a much weaker one than "RL plans better". |
| Tail AUC **not separated from its shuffled null** *and* absolute headroom over `bundle_aware` < 5% of mean optimum | **STOP / redesign.** Nothing learnable and nothing worth learning. |
| Planner leaves a real, structured gap | **Proceed to §3**, and the planner joins the permanent baseline set. |

The stop rule is deliberately not a single number. Which of these four we land in gets
stated explicitly in the write-up, rather than collapsed into "the gate passed".

**This gate can genuinely fail, and failing it is the cheapest good outcome available** —
it costs a day and saves the rebuild. Record the result in `DOCUMENTATION.md` either way,
as with Gate 1A.

---

## 2. The metric decision — declared now, before any results exist

v1 reported **% optimal**, which was fine there: tiny action space, cheap oracle, ties
rare. At 4×6 with lag it is actively misleading — it counts a 0.1% miss and a 2000% miss
identically, and Gate 1A's own `n=10` smoke run picked a *different* "strongest heuristic"
purely from small-sample noise.

**Primary metric: normalised score.**

```
normalised = (policy − random_allowed) / (optimum − random_allowed)
```

Bounded, insensitive to near-zero optima, and standard in RL benchmarking. Reported as
**median, p10 and mean**, over a frozen suite.

**Reported alongside, always:** absolute regret in reward units, % optimal (secondary,
for continuity with v1), and the **full regret distribution** rather than a single
summary. **Never** report a ratio-to-optimum mean again — that is the statistic that
produced 71.2%.

Declaring this before training exists is the point: a metric chosen after seeing results
is a metric chosen to flatter them.

**Oracle policy.** Brute force costs **2.2 s/instance at 4×6** (measured), so a
200-instance suite is ~7 minutes and every headline number keeps a true optimum. Instances
larger than 4×6 may appear as illustrations only, scored against baselines and an
explicit upper bound, and **must be labelled as having no oracle**. No percentage is ever
reported against an estimated optimum.

---

## 3. Build steps (only if Gate 1A.5 passes)

Each is a separate commit, run and shown, with a `DOCUMENTATION.md` entry.

**3.1 `data/scenario_v2.json`** — schema_version 2. Adds `resources` (depot stock),
per-cell `demand`, `timesteps`, `severity_path`, `functional_rule` (the minimum bundle),
and **`delivery_lag` per cell**. Every fictional element listed in
`provenance.fictional_elements`, as in v1 — and lag is fictional, like travel cost in v1.
Per `EXPANSION_PLAN.md` §1.3, check the SDRF/NDRF Norms of Assistance and the Sphere
Handbook for real per-person quantities; **cite only what is verified, label the rest
fictional.** v1's `scenario.json` is untouched.

**3.2 `src/env/allocation_env.py`** — new file; `shelter_env.py` is not modified, so the
v1 policy stays loadable. Sequential dispatch over T timesteps, one (resource → cell) per
step, action masking for infeasible pairs, `check_env` must pass.

> **Design note that decides whether the comparison is fair: the observation must include
> in-flight dispatches** (what is en route, to where, arriving when). Lag is the whole
> source of difficulty; hiding it makes the task partially observable and handicaps the
> policy against heuristics that can see the pending queue. Assert this in a test.

**3.3 `src/eval/baselines_v2.py`** — `random_allowed`, `myopic_pure`, `myopic_tiebreak`,
`bundle_aware`, `lookahead_planner` (from 1A.5), `brute_force_optimal` with an explicit
instance-size guard that **raises rather than silently running for hours**. `bundle_aware`
and the planner are ported from `scripts/greedy_check.py`, where they are already measured
— that continuity is deliberate.

**3.4 `src/eval/generate_scenarios_v2.py`** — seeded, deterministic, distribution declared
**inside** the output file, per v1's discipline. Regimes: `abundant`, `scarce`,
`severe_scarcity`, `static_severity`, `escalating`, `small_exact`, plus two new ones that
exist to make the result falsifiable:

| new regime | why |
| --- | --- |
| `zero_lag` | lag disabled — the control. Collapses to variant A, where a heuristic is ~92–100% optimal. **The registered prediction is that RL does not beat greedy here.** |
| `heterogeneous_lag` | wide lag spread — where planning depth should matter most |

**3.5 `tests/`** — port v1's invariants and add: stock conservation and never negative; a
masked pair is never selected across 1,000 episodes; the functional-bundle rule fires
exactly on completion; **brute-force optimum ≥ every baseline on every small instance**;
in-flight state is present in the observation; the suite declares its distribution and
covers all eight regimes. CI stays offline — no API key, no Ollama.

**3.6 Constraints v2** — deferred until §3.1–§3.5 are measured. It multiplies verdicts per
scenario, and at 20 requests/day that is the binding constraint (§4). Dashboard stays
deferred per `EXPANSION_PLAN.md` §1.9.

---

## 4. The two open questions on the retrieval finding

Both come out of the n=21 → n=63 reversal, and they matter for Phase 1 because §3.6
changes the constraint step. **Q2 is free and should be done alongside Gate 1A.5.**

**Q1 — Is "zero flips on unsafe shelters" a property, or just under-powered?** We said
"retrieval changes nothing" at n=21 and it was wrong at n=63. The same argument applies to
"0 unsafe flips at n=63": it could break at n=140. Gemini cannot settle this — the
remaining 11 suite scenarios cost 22 requests, over 2 days minimum, and the full suite far
more. **`qwen2.5:3b-instruct` is already pulled locally**, so the honest move is to run the
ablation at scale on the local model and report it as a **separate claim about a different
model**, never merged into the Gemini numbers. Finishing `eval-009` on Gemini (2 requests)
completes the intended 10 and costs almost nothing.

**Q2 — Why are the 7 flips concentrated in 2 of 9 scenarios?** (5 in `eval-003`, 2 in
`eval-004`.) Hypothesis: they sit on shelters near a decision boundary. Testable offline
from the existing cache — but "marginality" is a construct I am free to define, so if it
is defined after seeing which seven flipped, the sharpened claim is unfalsifiable. It is
therefore **pre-registered below, and this section is committed before the analysis is
run.** The commit order is the evidence.

#### Pre-registered definition (fixed; not to be revised after seeing results)

The deterministic safety rule turns on: `severity ≥ 0.70`, `headroom < 1`, and
`status != operational`. For each shelter, with `P` = the scenario's
`population_to_evacuate`, define three normalised distances to a decision boundary:

```
d_sev   = |flood_severity − 0.70| / 0.70          distance to the severity threshold
d_cap0  = |capacity_headroom − 1| / max(P, 1)     distance to the zero-headroom boundary
d_capP  = |capacity_headroom − P| / max(P, 1)     distance to "only just fits everyone"

margin  = min(d_sev, d_cap0, d_capP)
marginal := margin ≤ 0.15
```

A shelter whose `status != operational` is assigned `margin = 1.0` — "closed" is
unambiguous; there is no nearly-open. Marginality uses **only scenario facts**: no
verdict, no flip label, no model output enters it.

#### Pre-registered tests

- **T1, thresholded:** Fisher's exact test (one-sided) on the 2×2 of
  `marginal × flipped`. Report odds ratio and *p*.
- **T2, threshold-free:** Mann–Whitney *U* (one-sided) on `margin` for flipped versus
  unflipped shelters, so the result does not hinge on the 0.15 cutoff. Report medians.
- **Decision:** the sharpened claim — *"retrieval moves the verdict exactly where the call
  is close"* — may be made **only if T1 and T2 agree in direction and T2 gives p < 0.05**.
  Otherwise the 11.1% is reported as unexplained variance, which is the honest default.
- **Power, stated in advance:** there are **7 flip events**. This test can support a
  positive finding weakly; it cannot establish absence. A null result will be reported as
  "underpowered, no evidence either way" and never as "position on the boundary does not
  matter".

#### Disclosure — what I already knew before pre-registering

Full blindness is not available and claiming it would be worse than admitting it. Already
known: the flips are 5 in `eval-003` and 2 in `eval-004`; all 7 are on shelters the safety
rule calls **safe**; 5 are `allowed → excluded` and 2 the reverse. **Not** known: which
specific shelter ids flipped, or their severity and headroom values. The definition above
was written from the safety rule's own thresholds, not from inspecting the flipped rows,
but this test is weaker than a truly blind one and is reported as such.

---

## 5. Gate 1B and the registered prediction

Gate 1B is unchanged from `EXPANSION_PLAN.md` — measure RL against every baseline on the
frozen held-out suite and report whichever way it lands. Two additions:

**The suite and the metric are frozen before the first training run.** Written down, seeded,
committed. No regenerating the suite after seeing a bad number.

**A prediction registered in advance**, because we designed a task our own heuristic fails
and a reviewer will rightly ask whether it was rigged:

> On the `zero_lag` control regime we predict **RL does not beat `bundle_aware`**. If it
> does, the result is more likely a bug or an unfair baseline than a win, and will be
> investigated as such before being reported.

The defence against "you built a task to make RL look good" is that the design change is
physically motivated (lag is travel time, which v1 already modelled), was chosen before
any RL result existed, and ships with a control regime where we predict our own approach
loses.

---

## 6. Honesty ledger — new entries

| Caveat | Where it goes |
| --- | --- |
| Delivery lag is **fictional and deterministic** — not a routing model | `scenario_v2.json` provenance, README |
| The task was **designed by us until a heuristic failed on it** | Stated plainly; mitigated by the control regime and the registered prediction above |
| Instances above 4×6 have **no oracle** | Every table, per-row |
| v1 and v2 numbers are **not comparable** | Already enforced by the banner in `EVALUATION_V1.md` |
| "Trained against a proxy rule, not the LLM" | **Returns loudly** if §3.6 falls back to rule-generated training masks |

---

## 7. Sequencing

```
Gate 1A.5   tail characterisation + Q2 (offline)     <- START HERE; can say "don't build"
Q1 setup    finish eval-009 (2 Gemini requests)      cheap, completes the intended 10
3.1 - 3.2   scenario v2, allocation env
3.3 - 3.4   baselines, frozen eval suite
3.5         tests, CI green offline
Gate 1B     measure, with the §2 metric, and write it up whichever way it lands
3.6         constraints v2, only after Gate 1B
```

**If Gate 1A.5 fails, the correct output of this whole plan is a `DOCUMENTATION.md` entry
saying so** — "we designed a harder task, measured it, and a 40-line planner still won" is
a real finding and a cheap one. That is the same standard v1 was held to.
