# Sentinel-Agent Sprint Prototype

A demo-able disaster-response decision-support prototype for a capstone project review. Scope: evacuation routing from a flooded zone to an available shelter, using a RAG-grounded LLM constraint step feeding a small action-masked RL policy, shown in an explainable dashboard. This is a fast, zero-budget prototype, not the production or patent-grade version — favor working, simple, and free over rigorous.

## CURRENT STATE — read this first (updated 2026-09-02)

**All six kickoff steps are BUILT, committed and pushed.** This file's "Working style"
section below describes how the project was originally built; do not re-plan steps 0-6 as
if they were pending.

Start by reading, in this order:

| File | What it tells you |
| --- | --- |
| `DOCUMENTATION.md` | Per-step build log: every addition, every problem hit and how it was fixed. The fastest way to understand how the project got here. |
| `EVALUATION.md` | Measured results, **including the ones that undercut the system**. Read before repeating any claim about performance. |
| `README.md` | Real vs. fictional data, free-tier services, how to run everything. |

Verify it still works with `.venv/bin/python run_demo.py` (exits 0) and
`.venv/bin/python -m pytest tests/` (43 offline tests, no API key needed).

### Findings that contradict the obvious reading of this spec

Do not repeat these claims without checking `EVALUATION.md` first:

- **RL is not justified on this task.** The reward is fully computable, so a one-line
  greedy argmax over the allowed set *is* the oracle: 93% vs the trained policy's 73% on a
  held-out suite. 5x more training gave no gain.
- **Retrieval does not change the verdicts** (0/21 flipped in an ablation) — it makes them
  *evidenceable* (verbatim-verifiable citations went 21/21 to 0/21 without it). The RAG
  layer does evidentiary work, not decision work.
- **The corpus is ONE document.** The NDMA and NIDM URLs serve byte-identical files.
- **The training action mask is a deterministic proxy rule, NOT the LLM.** The real Gemini
  mask is used only at demo/inference time. Never say the policy was "trained against
  LLM-generated constraints".
- **The demo policy is suboptimal on the demo scenario** — it picks S5 (0.650) over S4
  (0.724). Known, labelled `SUBOPTIMAL` in the dashboard, and it does not weaken the
  safety claim.

### Hard constraint to plan around

`gemini-3.6-flash` free tier = **20 requests per day**, resetting at midnight Pacific.
Each evaluation scenario costs 2 calls. This is why
`src/eval/constraint_agreement.py` has scored only 3 of 10 scenarios; it caches per
scenario and resumes. Budget API calls deliberately — the demo itself needs none, since
`data/constraints_output.json` is cached and committed.

## Hard scope boundaries (do not expand without asking first)

- No live government API calls (no live IMD/NDMA/Bhuvan integration). Use static/historical sample data only.
- Exactly two data inputs matter: flood/hazard severity and shelter status. IoT sensors, satellite imagery, and traffic APIs are out of scope entirely — not deferred, actually cut.
- Exactly one action type: evacuation routing to a shelter. Do not add shelter allocation, dispatch, or traffic diversion.
- The constraint step is one structured LLM call per scenario (schema below) — not a rule-extraction or conflict-arbitration pipeline.
- The RL environment is a small grid (8-10 cells) framed as a single-decision (contextual-bandit-style) task — not a multi-step realistic city simulation. Deliberate, so training finishes in minutes, not hours.
- No paid APIs anywhere in this project. Every tool and model call must run on a free tier or fully locally. If you're about to reach for something that needs a credit card, stop and ask instead of proceeding.
- Do not invent specific-sounding real-world details (exact GPS coordinates, ward names, agency names) that aren't from an actual source. Label anything simplified or fictionalized clearly, in code comments and in the README.

## Tech stack (fixed, all free — don't substitute without asking)

- Python 3.11+, one virtual environment for the whole project
- Embeddings: `sentence-transformers` (`all-MiniLM-L6-v2`), runs locally on CPU. No API key, no internet needed after the model downloads once.
- Vector store: Chroma (local, no server needed)
- Constraint-generation LLM call: Google Gemini API, free tier, via the `google-genai` Python package. No credit card needed — sign up at Google AI Studio for a `GEMINI_API_KEY`. Assume it's set as an environment variable already.
  - **Model: `gemini-3.6-flash`.** This spec originally fixed `gemini-2.5-flash` / `gemini-2.5-flash-lite`, but as of 2026-09-02 both return `404 NOT_FOUND` — *"no longer available to new users. Please update your code to use models/gemini-3.6-flash"*. Substituted with the project owner's explicit approval. Still free tier.
- RL: `gymnasium` for the environment, `stable-baselines3` for training, `sb3-contrib` for `MaskablePPO` (action masking)
- Dashboard: Streamlit
- Track dependencies in `requirements.txt` as you add them, not all at once up front

## Project structure

- `data/raw_docs/` — real source documents (NDMA/state SOP PDFs). If empty when needed, ask rather than fabricating one.
- `data/scenario.json` — the hardcoded historical scenario (flood severity + shelter status only)
- `src/rag/` — local embedding + retrieval
- `src/constraints/` — the Gemini constraint-generation step
- `src/env/` — the Gymnasium environment + training script
- `src/dashboard/` — the Streamlit app
- `models/` — trained policy checkpoints
- `README.md` — must state plainly what is real data vs. synthetic/simplified, and which free-tier services are used

## Constraint output schema (every consumer depends on this exact shape)

```json
{
  "scenario_id": "string",
  "constraints": [
    {
      "action_id": "string",
      "status": "allowed",
      "reason": "one sentence",
      "source_document": "filename",
      "source_excerpt": "the specific clause this is based on"
    }
  ]
}
```

## Working style

- Use plan mode for each numbered step in the kickoff prompt before writing code. Show the plan, wait for confirmation, then implement.
- After each step: run it, show real output, `git commit` with a clear message, then stop and wait before starting the next step. Don't chain multiple steps together unprompted.
- Never present fabricated data as real, in code, comments, or the README — mark every simplification explicitly.
