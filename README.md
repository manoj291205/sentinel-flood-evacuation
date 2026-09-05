# Sentinel-Agent Sprint

A disaster-response decision-support **prototype**: given a flooded zone and a set of
candidate shelters, it retrieves real government flood-management guidelines, uses one
structured LLM call to mark each shelter allowed or excluded with a cited clause, and
feeds that as an action mask to a small reinforcement-learning policy that picks where to
send evacuees — all shown in an explainable dashboard.

> **This is a fast, zero-budget prototype built for a capstone demo. It is not
> production software and not a rigorous research system.** It runs entirely on free
> tiers and local models. Read *[What is real and what is not](#what-is-real-and-what-is-not)*
> before drawing any conclusion from it, and
> **[EVALUATION.md](EVALUATION.md)** for measured results — including the ones that
> undercut the system.

---

## What it demonstrates

The scenario is deliberately built so the **safest-looking answer is wrong**. Shelter S1
is the nearest at 8 minutes and has 900 spare places for 700 evacuees — on capacity and
travel cost alone it is the single most attractive option, scoring a perfect 1.0. It also
sits in a cell with flood severity 0.85.

```
with the RAG-grounded constraints : S5  (severity 0.05, score 0.6500)
with NO constraints at all        : S1  (severity 0.85, score 1.0000)
```

**Without the constraint layer, this system recommends a shelter inside the flood zone.**
The dashboard has a toggle that demonstrates this live, and the comparison is computed by
actually re-running the policy on an unmasked action space — not hardcoded.

This is not a one-off. Across a 60-scenario held-out suite, the unconstrained policy picks
an unsafe shelter **40% of the time**; with the constraint layer that falls to **7%**, and
every remaining case is a scenario where *no* safe shelter existed at all
([EVALUATION.md](EVALUATION.md) §1).

Note the constrained pick above is **S5, not the optimal S4** (0.724) — the policy is
suboptimal here by 0.074, and the dashboard says so rather than calling it "best
available". That honesty costs nothing: the safety claim does not depend on the policy
being optimal, only on the unsafe option being unselectable.

---

## What is real and what is not

| | Status |
| --- | --- |
| **The guideline document** | **Real.** *National Disaster Management Guidelines: Management of Floods*, National Disaster Management Authority (NDMA), Government of India, signed 17 January 2008. 168 pages, 6,120,219 bytes, SHA-256 `2fc4518a…`. Committed to this repo; provenance in `data/raw_docs/MANIFEST.json`. |
| **Every quoted clause** | **Real.** Extracted verbatim from that PDF and machine-checked to appear in the retrieved text. |
| **The 2018 Kerala flood background** | **Real.** The floods peaked mid-August 2018; severely affected districts included Idukki, Ernakulam, Alappuzha, Thrissur and Wayanad; flooding was worsened by controlled dam releases including from the Idukki reservoir. Used **only as background inspiration** — no number in this project derives from it. |
| **The grid, cells and coordinates** | **Fictional.** A 3×3 grid of 9 cells addressed by `(row, col)` indices. No latitude, longitude, ward name or agency name appears anywhere. |
| **All seven shelters** | **Fictional.** Their existence, capacities, occupancies, operational statuses, and travel costs are invented. |
| **All flood-severity values** | **Fictional.** |
| **The evacuee population (700)** | **Fictional.** |
| **The allowed/excluded verdicts and reasons** | **Model-generated.** These are `gemini-3.6-flash`'s judgements about fictional shelters. They are **not** determinations by NDMA or any agency, and must never be presented as such. |

Every fictional element is also labelled inside `data/scenario.json` itself, under
`provenance.fictional_elements`, and restated in a banner at the top of the dashboard.

**Explicitly out of scope** — cut, not deferred: IoT/sensor feeds, satellite imagery, and
traffic APIs. `travel_cost_minutes` is a static number written into the scenario file; it
is **not** derived from any road network, routing engine, or traffic source. There are no
live government API calls anywhere.

---

## Free-tier services used

| Component | What it uses | Cost |
| --- | --- | --- |
| Embeddings | `sentence-transformers` `all-MiniLM-L6-v2` | Free, **runs locally on CPU** |
| Vector store | Chroma, on disk | Free, local, no server |
| Constraint generation | Google Gemini API, `gemini-3.6-flash` | **Free tier**, no credit card. One call per scenario, cached |
| RL | `gymnasium`, `stable-baselines3`, `sb3-contrib` (`MaskablePPO`) | Free, local, CPU |
| Dashboard | Streamlit | Free, local |

**No paid API is used anywhere.** The only network call is the single Gemini request, and
its result is cached to `data/constraints_output.json`, so **the demo runs with no
network at all**.

> **Free-tier quota, measured 2026-09-02:** `gemini-3.6-flash` allows **20 requests per
> day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) — per *day*, not per minute.
> Ample for the demo, which makes one cached call, but it is the reason the evaluation in
> §3–§4 of [EVALUATION.md](EVALUATION.md) covers 9 scenarios rather than 20, scored
> across two days.

> **Note on the model id.** This project was specified against `gemini-2.5-flash` /
> `gemini-2.5-flash-lite`. As of 2 September 2026 both return
> `404 — "no longer available to new users. Please update your code to use
> models/gemini-3.6-flash"`. It uses `gemini-3.6-flash` instead. Be aware that
> `client.models.list()` still *advertises* the 2.5 models — the failure only appears on
> an actual generate call, so listing the catalogue is not a valid availability check.

---

## Setup

Requires **Python 3.11+**.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export GEMINI_API_KEY="..."   # free from Google AI Studio; only needed to regenerate constraints
```

## Run it

**Everything, end to end, one command:**

```bash
.venv/bin/python run_demo.py
```

It rebuilds anything missing (fetches the PDF, embeds the corpus, trains the policy) and
skips whatever already exists, so a rerun takes seconds. Flags: `--rebuild-index`,
`--refresh-constraints`, `--retrain`.

**The dashboard** (this is the part to show):

```bash
.venv/bin/streamlit run src/dashboard/app.py
```

**The evaluation:**

```bash
.venv/bin/python -m src.eval.generate_scenarios      # held-out suite (seeded)
.venv/bin/python -m src.eval.run_study               # ablation + baselines
.venv/bin/python -m src.eval.constraint_agreement    # LLM agreement + RAG ablation
.venv/bin/python -m pytest tests/                    # 43 offline tests
```

**Individual steps**, if you want to see one in isolation:

```bash
.venv/bin/python -m src.rag.fetch_docs           # download the real PDF
.venv/bin/python -m src.rag.ingest               # chunk + embed locally -> Chroma
.venv/bin/python -m src.rag.test_retrieval       # prove retrieval returns real text
.venv/bin/python -m src.constraints.test_constraints --refresh   # the Gemini call
.venv/bin/python -m src.env.train                # train MaskablePPO
.venv/bin/python -m src.env.evaluate             # example decisions
```

---

## How it works

```
data/scenario.json          fictional flood scenario (severity + shelter status only)
        |
        v
src/rag/                    real NDMA PDF -> 480 page-scoped chunks -> local embeddings -> Chroma
        |
        v
src/constraints/            ONE structured Gemini call -> allowed/excluded + cited clause
        |                   validated against the schema, retried once, citations verified
        v
src/env/                    Gymnasium single-decision env; constraints become an action
        |                   mask so excluded shelters are STRUCTURALLY unselectable
        v
src/dashboard/              Streamlit: recommendation, hazard grid, per-exclusion evidence
```

Chunks are **page-scoped** — no chunk spans a page boundary — so every citation's page
number is truthful.

### How citations are kept honest

Three independent defences, because "the model said so" is not evidence:

1. **Schema validation.** Exactly one verdict per shelter, no missing and no invented
   shelter ids, valid status, non-empty reason and excerpt. Failure triggers one retry
   with the errors fed back.
2. **`source_document` must be a real file** listed in `data/raw_docs/MANIFEST.json`. A
   citation naming a document not in the corpus is the most plausible-looking way a
   fabricated source would slip past a reader.
3. **Verbatim grounding.** Every `source_excerpt` must appear, whitespace-normalised and
   case-insensitive, inside a chunk actually retrieved. Failure retries once; if it still
   fails, the result is **kept but flagged `citation_verified: false`** and rendered
   **UNVERIFIED** on the dashboard rather than silently trusted.

On the current run: **7 of 7 citations verified verbatim.**

The retry is not decorative — on the first real run the model returned
`"ndma_flood_guidelines.pdf (page 89)"` as a filename and was corrected on the retry.

---

## Known limitations

Stated plainly, because these are the questions a reviewer should ask.

- **The corpus is one document, not two.** The NDMA URL and the NIDM URL
  (`nidm.gov.in/PDF/guidelines/floods.pdf`) return **byte-identical files** — same
  SHA-256. NIDM mirrors the NDMA document. The fetcher deduplicates by content hash and
  records the second URL as a mirror. One document clears the bar this prototype set,
  but it is not a corpus.
  - Related: the NIDM URL is **case-sensitive** — `/pdf/` returns 404, `/PDF/` works. That
    host also answers `HEAD` with 404 while answering `GET` with 200.
- **The training-time action mask is not the LLM.** Training runs 40,000 episodes;
  calling Gemini once per episode would be neither free nor fast. Training uses a
  deterministic proxy rule (severe flooding / no headroom / not operational) that
  imitates the *kind* of exclusions the LLM makes. **The real Gemini mask is used only at
  demo and inference time.** Do not describe the policy as "trained against
  LLM-generated constraints".
- **RL is not justified on this task, and that is now measured.** The reward is fully
  computable from the observation, so a one-line greedy argmax over the allowed set *is*
  the oracle. On a held-out suite it scores **93%** against the trained policy's **73%** —
  and a 5× longer training run gave no improvement (72%). The contextual-bandit framing
  is scaffolding for the multi-step problem where greedy stops being optimal; it does not
  win here. See [EVALUATION.md](EVALUATION.md) §2.
- **Retrieval does not change the verdicts — it makes them evidenceable.** Measured by
  ablation: removing the retrieved excerpts flipped **7 of 63** verdicts (11.1%) — but
  **none of them on an unsafe shelter**, so no safety outcome changed. Citations
  verifiable verbatim fell from **63/63 to 0/63**. The RAG layer is doing *evidentiary*
  work first and marginal-judgement work second; it is not what decides whether an unsafe
  shelter gets excluded. Do not describe it as driving the reasoning. (An earlier
  21-verdict sample showed 0 flips and this section said retrieval changed nothing at all
  — see [EVALUATION.md](EVALUATION.md) §4 for how that was overturned.)
- **Retrieval surfaces front matter.** A table-of-contents line and the abbreviations
  list occasionally appear among lower-ranked results. Top hits are substantive.
- **The evaluation suite is synthetic and small in places.** There is now a 60-scenario
  held-out suite with baselines and an ablation ([EVALUATION.md](EVALUATION.md)), but the
  LLM-agreement and retrieval-ablation results rest on **63 verdicts from 9 scenarios** —
  the free tier allows only 20 requests *per day*. Directionally interesting, not
  statistically strong: growing that sample from 21 verdicts already overturned one
  conclusion.
- **Nothing is validated against real evacuation outcomes.** Still the largest gap.
- **The reward weights (0.65 capacity / 0.35 travel) are a modelling choice**, not a
  figure from any source or standard.
- **No OCR.** If a source PDF were a scan rather than digital text, ingestion would warn
  and index nothing rather than silently proceeding.

---

## What would need to change for a rigorous version

Written from the gaps this build actually exposed, not from a wishlist.

1. **A real corpus, versioned.** One 2008 national guideline is not an evidence base.
   The rigorous version needs state-level SOPs, district disaster management plans, and
   current amendments, with document versioning — guidance changes, and a citation to a
   superseded clause is worse than no citation.
2. **Constraint generation inside the training loop.** Today the policy trains against a
   proxy rule and only meets real constraints at inference. A rigorous system would
   either generate constraints at scale offline and train on that distribution, or
   distil the constraint step into a fast local model that can run per episode.
3. **Real geography.** The fictional 3×3 grid would become actual ward or block
   geometry, with routing over a real road network and travel times that respond to
   flooding — which means the road-network and hazard-extent inputs this prototype
   deliberately cut.
4. **A real decision problem.** This is a single decision picking one shelter for one
   population. The real problem is **multi-step and multi-shelter**: splitting a
   population across shelters, sequencing departures, respecting vehicle and staffing
   limits, and re-planning as conditions change.
5. **Live hazard input.** Static severity values would become real forecast and gauge
   data (IMD, CWC), with the uncertainty carried through to the decision rather than
   collapsed to a point estimate.
6. **Validation against outcomes.** The single largest gap: **nothing here is validated
   against real evacuation outcomes.** A rigorous version needs historical replay,
   comparison against expert decisions and simple baselines, and measured performance
   under distribution shift — plus adversarial testing of the constraint step, since
   correctly excluding an unsafe shelter is a safety property, not a preference.
7. **Human-in-the-loop by design.** This is decision *support*. A deployable version
   needs an operator override path, an audit trail of what was recommended and why, and
   explicit accountability for who accepts a recommendation.

---

## Repository layout

```
data/scenario.json              the fictional scenario (severity + shelter status only)
data/raw_docs/                  the real NDMA PDF + MANIFEST.json provenance record
data/constraints_output.json    cached Gemini output — lets the demo run offline
src/rag/                        fetch, chunk, embed locally, retrieve
src/constraints/                the single structured Gemini call + validation
src/env/                        Gymnasium env, MaskablePPO training, evaluation
src/dashboard/app.py            the Streamlit app
models/                         trained policy checkpoint
run_demo.py                     the whole pipeline, one command
src/eval/                       held-out suite, baselines, ablation studies
tests/                          43 offline invariant tests (pytest, run in CI)
EVALUATION.md                   measured results, including the unflattering ones
DOCUMENTATION.md                per-step build log: every addition, and why
```

`DOCUMENTATION.md` records each step in detail, including the problems found along the
way and how they were fixed.
