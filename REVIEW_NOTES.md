# Review notes — the hard questions

One page. Every number here comes from [`EVALUATION.md`](EVALUATION.md); the section
references are to that file. If a number is not in there, do not claim it.

---

### "Your RL policy is worse than a two-line greedy rule. Why is it there?" (§2)

It is, and that is measured: **73% optimal for the policy, 93% for greedy**, on 60
held-out scenarios. The reason is structural, not a tuning failure. The reward is fully
computable from the observation — `0.65 · min(headroom/population, 1) + 0.35 · (1 −
travel_norm)` — so an argmax over the allowed set **is the oracle by construction**. The
policy can at best tie it. A 200,000-step run scored 72%, so this is a plateau, not a
compute problem.

The honest position: **on this task, RL is not justified on performance grounds.** The
contextual-bandit framing is scaffolding for the multi-step version — splitting a
population across shelters, sequencing departures, re-planning as conditions change —
where the reward stops being a closed-form function of one observation and greedy stops
being optimal. It does not win here, and I am not claiming it does.

### "Does the RAG layer actually do anything?" (§4)

Not to the decisions. Removing retrieval flipped **0 of 21 verdicts** — the model reaches
the same conclusions from the scenario facts alone. What it does is **evidentiary**:
citations verifiable verbatim went from **21/21 with retrieval to 0/21 without**.

The ablation caught something worth telling. With no excerpts supplied, the model first
returned empty `source_excerpt` fields — honest. Pushed by the schema retry, it then
**fabricated citations naming the real NDMA document**. The verbatim grounding check
flagged all seven as UNVERIFIED. That is the third defence doing exactly its job,
observed rather than hypothesised. So: retrieval is not driving the reasoning, and I do
not describe it that way. It is what makes a verdict checkable by a human.

### The S6/S7 training bug — the strongest story here

The first study run scored the policy at **45% optimal** on held-out scenarios while it
scored 94% on its own training distribution. Feature distributions looked nearly
identical, so it was not gross distribution shift. The giveaway was *which* shelters it
picked: **S6 and S7 zero times in 60 scenarios**, where the oracle picked them 17 times.

Cause: the training randomiser perturbed each shelter's numbers but kept
`status = base["status"]`. S6 is `at_capacity` and S7 is `closed_structural_damage`, so
those two slots were masked out in **every single training episode**. The policy learned
"slots 6 and 7 are dead" — a positional prior that is correct on the demo scenario and
wrong everywhere else. It had learned slot identity instead of the features.

Drawing every attribute independently fixed it: **45% → 73% optimal**, mean reward
0.6481 → 0.7213, S6/S7 picks 0/0 → 7/8.

**This was invisible on the demo scenario** — the demo looked fine the whole time. It
only appeared because there was a held-out suite. That is the argument for having built
one.

### "Why does the demo pick S5 when S4 is better?"

Because the fix above changed the policy, and this is what it costs. S5 scores 0.650, S4
scores 0.724 — **regret 0.074**. S5 is still allowed, still safe (severity 0.05), and
still fits all 700. The dashboard labels it **`SUBOPTIMAL`** and names S4 rather than
calling it "best available".

The point to make: the configuration was chosen on **held-out** performance, not by
retraining until the demo looked good. Taking the better held-out policy and accepting a
worse-looking demo is the right trade. And the safety claim does not depend on the policy
being optimal — only on the unsafe option being unselectable.

### The safety headline — the number to lead with (§1, §2)

`nearest_unconstrained` is the naive "send them to the nearest shelter" rule a system
without this project would use. It picks an **unsafe shelter 22 out of 60 times**.

With the constraint layer, unsafe picks fall to **4/60 (7%)**, and all four are the
`no_safe_shelter` scenarios where every option is unsafe and no mask can help. **On every
scenario where a safe shelter existed, the constraint layer produced zero unsafe picks.**
Unconstrained, the policy itself is unsafe 24/60 (40%).

On the LLM's own accuracy (§3): across 21 verdicts, **zero false-allows** (unsafe shelter
permitted) against six false-excludes (usable shelter barred). It errs conservatively,
which is the direction you want a safety layer to err.

### Limitations — say these before they are found

- **§3 and §4 rest on 21 verdicts from 3 scenarios.** The free tier is 20 requests *per
  day* and each scenario costs two calls. Directionally interesting, not statistically
  strong. No confidence intervals claimed.
- **The 60-scenario suite is synthetic.** Plausible inputs, not real floods.
- **Nothing is validated against real evacuation outcomes.** Largest gap in the project.
- **The corpus is one document**, not two — the NDMA and NIDM URLs serve byte-identical
  files.
- **The safety rule is a yardstick, not ground truth.** Agreement with it is not proof
  the LLM is right; both could be wrong the same way.
- **Single seed per configuration**, so training variance is unmeasured. One reward
  function, no sensitivity analysis on the 0.65/0.35 weights.
- **The training mask is a deterministic proxy rule, not the LLM.** Gemini is used at
  demo and inference time only. Calling it 40,000 times would be neither free nor fast.
  Do not let anyone leave thinking the policy was trained against LLM constraints.
