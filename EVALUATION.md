# Evaluation

The prototype's original claims all rested on **one hand-built scenario that was tuned to
produce the desired result** — S1's capacity was raised specifically so the constraint
step would look decisive. This document replaces those assertions with measurements, and
reports the results that do not flatter the system alongside the ones that do.

Reproduce with:

```bash
.venv/bin/python -m src.eval.generate_scenarios      # the held-out suite
.venv/bin/python -m src.eval.run_study               # ablation + baselines
.venv/bin/python -m src.eval.constraint_agreement    # LLM agreement + RAG ablation
.venv/bin/python -m pytest tests/                    # 43 invariant tests
```

---

## Method

**The suite.** 60 synthetic scenarios from a fixed seed (`data/eval_scenarios.json`),
disjoint from the demo scenario. The generation distribution is **declared inside the
file** so a reader can judge whether it is fair, and coverage is guaranteed for three
regimes:

| regime | count | meaning |
| --- | --- | --- |
| `mixed` | 52 | some shelters safe, some not |
| `all_safe` | 4 | the constraint layer can add nothing |
| `no_safe_shelter` | 4 | every option is unsafe; nothing can help |

The last two are included **on purpose**. A suite containing only cases where the
constraint layer helps would make every number below meaningless.

**The yardstick.** A deterministic safety rule — severe flooding (≥0.70), no headroom, or
not operational. It is *not* ground truth derived from the NDMA text; it encodes three
uncontroversial conditions and is used as an objective reference.

**Mask source.** The ablation study below uses the **deterministic rule**, not the LLM,
because scoring 60 scenarios through the API is impossible on the free tier (see the
quota finding). Those numbers measure the **architecture**, not the LLM's accuracy. The
LLM is scored separately in §3. **The two must not be conflated.**

---

## 1. Does the constraint layer change anything?

| | result |
| --- | --- |
| scenarios where it changed the chosen shelter | **24/60 (40%)** |
| unsafe pick **without** the constraint layer | **24/60 (40%)** |
| unsafe pick **with** the constraint layer | **4/60 (7%)** |

All four residual failures are the `no_safe_shelter` scenarios, where every option is
unsafe and no mask can help. **On every scenario where a safe shelter existed, the
constraint layer produced zero unsafe picks.**

The original single-anecdote claim is now a measured rate.

## 2. Baselines — what is 91.5% actually worth?

| strategy | mean reward | optimal | unsafe picks |
| --- | --- | --- | --- |
| `random_allowed` | 0.4700 | 17% | 4/60 |
| `nearest_allowed` | 0.6506 | 43% | 4/60 |
| `max_capacity_allowed` | 0.7031 | 57% | 4/60 |
| **`greedy_reward_allowed` (= oracle)** | **0.7580** | **93%** | 4/60 |
| `rl_policy_allowed` | 0.7213 | 73% | 4/60 |
| `nearest_unconstrained` | 0.6639 | 30% | **22/60** |
| `greedy_unconstrained` | 0.7987 | 68% | **19/60** |
| `rl_policy_unconstrained` | 0.7711 | 50% | **24/60** |

### The result that undercuts the RL component

**`greedy_reward_allowed` IS the oracle, by construction.** The reward is fully computable
from the observation:

```
reward = 0.65 · min(headroom/population, 1) + 0.35 · (1 − travel_norm)
```

so a one-line argmax over the allowed set cannot be beaten, and the trained policy can at
best tie it. It does not: **73% versus 93%**. A 200,000-step run was also measured and
scored **72%** — no gain for 5× the compute, so this is a plateau, not a budget problem.

**On this single-decision task, reinforcement learning is not justified on performance
grounds.** A two-line greedy rule is optimal, free, and interpretable. The honest
defence of the RL component is that the contextual-bandit framing is *scaffolding* for
the multi-step, multi-shelter problem where greedy stops being optimal — not that it wins
here. It does not win here.

### The result that supports the thesis

`nearest_unconstrained` — the naive "send them to the closest shelter" rule a system
without this project would use — picks an unsafe shelter **22 out of 60 times**. That
column, not the reward column, is the case for the constraint layer.

## 3. Is the LLM actually right?

**Sample: 21 shelter verdicts across 3 scenarios.** Small — see the quota finding.

| | with retrieval | without retrieval |
| --- | --- | --- |
| agreement with the safety rule | 71.4% | 71.4% |
| correctly excluded (unsafe) | 10 | 10 |
| correctly allowed (safe) | 5 | 5 |
| **false-allow** (unsafe permitted) | **0** | **0** |
| false-exclude (usable barred) | 6 | 6 |

The two error types are reported separately because they are **not equivalent**:

- **false-allow** permits an unsafe shelter — a **safety** failure. **Zero observed.**
- **false-exclude** bars a usable shelter — a **cost** failure. Six observed.

The model is **conservative**, and errs in the direction you would want a safety layer to
err. On this sample it never permitted a shelter the deterministic rule considered unsafe.

## 4. Does retrieval change the verdicts?

| | result |
| --- | --- |
| verdicts that flipped when retrieval was removed | **0/21 (0%)** |
| citations verifiable verbatim, **with** retrieval | **21/21** |
| citations verifiable verbatim, **without** retrieval | **0/21** |

**Retrieval does not change the decisions. It changes whether they can be evidenced.**

The model reaches the same verdicts from the scenario facts alone. What disappears
without retrieval is the ability to *substantiate* them. This is worth stating precisely,
because it is easy to imply the RAG layer is driving the reasoning. It is not — it is
doing **evidentiary** work.

### What the ablation caught the model doing

With no excerpts supplied, the model first returned **empty** `source_excerpt` fields —
honest, since it had no source. Pushed by the schema-validation retry, it then
**fabricated citations naming the real NDMA document**. The grounding check flagged all
seven as UNVERIFIED.

That is the third defence doing exactly the job it exists for, observed rather than
hypothesised.

## 5. Tests

43 pytest tests, 0.18 s, fully offline, run in CI with **no API key**. They cover the
invariants that actually matter: an excluded shelter is never selectable and the oracle is
never tempted by a higher-scoring excluded one; schema validation rejects invented,
missing and duplicate shelter ids and unknown source documents (including the exact
`"filename (page 89)"` failure seen in Step 3); the grounding check catches a paraphrase
while accepting whitespace and case variants; reward arithmetic including the
equal-travel divide-by-zero guard; and the eval suite must declare its distribution and
cover the regimes where the constraint layer cannot help.

---

## A bug this evaluation found

The first study run scored the policy at **45% optimal** on held-out scenarios against the
oracle's 93%, while scoring 94% on its own training distribution. Marginal feature
distributions were nearly identical, so it was not a gross distribution shift.

Looking at *which* shelters were picked gave it away: the policy chose **S6 and S7 zero
times in 60 scenarios**, where the oracle chose them 17 times.

The cause was in the training randomisation. `_perturb()` scaled each attribute from that
slot's values in the demo scenario and kept `status = base["status"]` — and S6 is
`at_capacity` while S7 is `closed_structural_damage`, so **those two slots were masked
out in every single training episode**. The policy learned "slots 6 and 7 are dead" as a
positional prior, which is correct on the demo scenario and wrong everywhere else. It had
learned slot identity instead of the features.

Drawing every attribute independently per shelter fixed it:

| | before | after |
| --- | --- | --- |
| held-out optimal | 45% | **73%** |
| held-out mean reward | 0.6481 | **0.7213** |
| S6 picks / S7 picks | 0 / 0 | 7 / 8 |

**This bug was invisible on the demo scenario** and would have stayed invisible without a
held-out suite. It is the clearest argument in this document for having built one.

**Honest consequence:** the retrained policy now picks **S5** (reward 0.650) on the demo
scenario rather than the optimal **S4** (0.724) — regret 0.074. S5 is still allowed, safe,
and fits all 700, and the central claim is untouched. The configuration was chosen on
held-out performance, **not** by retraining until the demo looked right. The dashboard
now labels such a pick `SUBOPTIMAL` and names the better shelter instead of calling it
"best available".

---

## Free-tier quota — a hard constraint

Measured 2026-09-02: `gemini-3.6-flash` allows

```
GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20 requests PER DAY
```

**per day, not per minute.** Each scenario in §3–§4 costs two calls (with-retrieval plus
ablation), so **at most 10 scenarios can be scored per day**. This is why §3 and §4 rest
on 3 scenarios rather than 20.

The runner caches per scenario, catches quota errors without losing completed work, and
resumes on a later day. Running it across three more days would complete the intended
subset.

---

## What these numbers do not show

- **§3 and §4 are 21 verdicts from 3 scenarios.** Directionally interesting, not
  statistically strong. No confidence intervals are claimed.
- **The safety rule is a yardstick, not truth.** Agreement with it is not proof the LLM
  is right; both could be wrong in the same direction.
- **The suite is synthetic.** It tests behaviour on plausible inputs, not on real floods.
  Nothing here is validated against real evacuation outcomes — still the project's
  largest gap.
- **One reward function.** No sensitivity analysis over the 0.65/0.35 weights.
- **Single seed per configuration.** Training-run variance is unmeasured.
