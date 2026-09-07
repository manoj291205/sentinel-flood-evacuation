# 5-minute demo script

Click-by-click, with what to say. Timings are targets, not a schedule — expect to be
interrupted, and use the interruptions ([REVIEW_NOTES.md](REVIEW_NOTES.md) has the
answers).

**Nothing in this demo needs the network or an API key.** The constraint output is cached
in `data/constraints_output.json`. Say that out loud early — it is a foreseeable question.

---

## Before the room (2 minutes, off the clock)

Cold terminal:

```bash
cd ~/sentinel-sprint
.venv/bin/python run_demo.py            # sanity check, must exit 0
.venv/bin/streamlit run src/dashboard/app.py
```

The dashboard opens at `http://localhost:8501`. Leave it on the browser tab, scrolled to
the top, with the constraint toggle **off**. Keep the terminal open on a second tab — it
is the fallback and also useful evidence.

---

## 0:00–0:30 — What this is

Point at the title and the grey banner under it.

> "Flood evacuation decision support. Given a flooded zone and a set of shelters, it picks
> where to send people. The banner says what is real and what is not: the guideline
> document behind every citation is a genuine 2008 NDMA publication, 168 pages. The grid,
> the shelters, the capacities and the severities are all fictional, and the verdicts are
> a language model's judgements, not any agency's. That is stated on the page so it
> travels with the demo."

## 0:30–1:15 — The recommendation

Point at the four tiles: **S5 · 41 min · 1,010 spare · score 0.650**.

> "It recommends shelter S5. Minimal flooding, takes all 700 people, 41 minutes away."

Then point at the word **SUBOPTIMAL** in the fourth tile.

> "And it says the policy is suboptimal here — S4 scores 0.724, so this pick costs 0.074
> in regret. I will come back to why that label is there rather than being hidden."

## 1:15–2:30 — The point of the whole project: the toggle

Flip **"Show what this system would recommend without the RAG-grounded constraint step."**

> "Same policy, same scenario, constraints removed. Now it picks S1: the closest shelter
> at 8 minutes, with room for all 700, scoring a perfect 1.0 on capacity and travel. It
> also sits in a cell with flood severity 0.85 — severe. Without the constraint layer this
> system sends people into the flood zone."

Then, before anyone asks whether that is one lucky example:

> "That is not a single anecdote. Across a 60-scenario held-out suite, the naive
> nearest-shelter rule picks an unsafe shelter 22 times out of 60. With the constraint
> layer, unsafe picks drop to 4 out of 60, and all four are scenarios where no safe
> shelter existed at all."

Flip the toggle back off.

## 2:30–3:15 — The evidence, not the assertion

Scroll to **Hazard grid**, then to **Why each shelter was excluded**. Open S1's panel.

> "Every exclusion carries a reason, a verbatim quote from the NDMA document, and a
> VERIFIED badge. Verified means we checked the quote actually appears, character for
> character, in the text that was retrieved — not that the model said so. Seven of seven
> citations verified on this run."

If asked whether retrieval is doing the reasoning, be straight about it: it is not — an
ablation flipped 7 of 63 verdicts, none of them on an unsafe shelter, while verifiable
citations went from 63/63 to 0/63.
Retrieval makes the verdicts checkable, not correct.

## 3:15–4:30 — The S6/S7 bug (the strongest story — do not skip it)

Natural cue: the **SUBOPTIMAL** label, or the shelter table where S6 and S7 sit at the
bottom. Point at them.

> "S6 is at capacity, S7 is closed for structural damage — in this scenario. When I
> measured the policy on a held-out suite it scored 45% optimal against the oracle's 93%,
> while scoring 94% on its own training data. Looking at which shelters it picked gave it
> away: it never picked S6 or S7. Not once in 60 scenarios, where the oracle picked them
> 17 times.
>
> The randomiser was jittering every attribute except status, so those two slots were
> masked out in every single training episode. The policy had learned 'slots 6 and 7 are
> dead' — true on this scenario, wrong everywhere else. It learned slot identity instead
> of the features. Drawing every attribute independently took it from 45% to 73%.
>
> And this is why the SUBOPTIMAL label is on the screen: the fixed policy picks S5 rather
> than S4 on this scenario. I kept the version that is better on held-out data and
> labelled the demo honestly, rather than retraining until the demo looked good. The bug
> was completely invisible on this screen — it only showed up because there was a held-out
> suite."

## 4:30–5:00 — Close on what it does not do

> "The evaluation is in EVALUATION.md, including the results that undercut it. The
> headline one: because the reward is fully computable, a two-line greedy rule is the
> oracle by construction and beats the trained policy, 93% to 73%. The RL framing is
> scaffolding for the multi-step problem, not a win here. The LLM agreement numbers rest
> on 63 verdicts from 9 scenarios, because the free tier allows 20 requests a day. And
> nothing here is validated against real evacuation outcomes. That is the largest gap."

---

## If the dashboard will not start

Do not debug on stage. Switch to the terminal tab and run:

```bash
.venv/bin/python run_demo.py
```

It prints the whole pipeline end to end in about ten seconds from cache: the scenario, a
live retrieval hit from the real PDF with its page number, the seven verdicts with
per-citation verification, and — the part that matters — **Stage 6**, which prints both
answers:

```
with the RAG-grounded constraints : S5  (severity 0.05, score 0.6500)
with NO constraints at all        : S1  (severity 0.85, score 1.0000)
```

That is the same comparison as the toggle, computed the same way. Deliver 1:15–2:30 off
that output.

Second fallback, if Python itself is unavailable — open these files and read from them:

- `EVALUATION.md` §1 and §2 — the safety table and the baseline table
- `data/constraints_output.json` — the seven verdicts with their quotes and
  `citation_verified` flags
- `REVIEW_NOTES.md` — the answers to everything above

## Two things not to say

- Not "trained against LLM-generated constraints." Training used a deterministic proxy
  rule; the Gemini mask is used at demo and inference time only.
- Not "the RAG layer makes the decisions." It makes them evidenceable. Without it, 7 of
  63 verdicts flip — but none on an unsafe shelter, so no safety outcome changes.
