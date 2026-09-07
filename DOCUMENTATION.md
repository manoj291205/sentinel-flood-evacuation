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
| Real source documents | `data/raw_docs/` | **Built (Step 2)** — 1 real NDMA PDF, 168 pages |
| Local RAG (embed + retrieve) | `src/rag/` | **Built (Step 2)** — 480 chunks in local Chroma |
| Gemini constraint step | `src/constraints/` | **Built (Step 3)** — 7/7 verdicts, all citations verified |
| Gymnasium env + training | `src/env/` | **Built (Step 4)** — MaskablePPO. Current measured figure is **73% optimal on the held-out suite** (`EVALUATION.md` §2); the 91.5% below is the superseded pre-retrain training-distribution number. |
| Streamlit dashboard | `src/dashboard/` | **Built (Step 5)** — verified rendering in a real browser |
| Trained checkpoints | `models/` | **Built (Step 4)** — `maskable_ppo_shelter.zip` |
| End-to-end runner | `run_demo.py` | **Built (Step 6)** — rebuilds from nothing, exit-code checked |
| Evaluation suite | `src/eval/` | **Built** — 60 held-out scenarios, baselines, ablations |
| V3 sequential environment | `src/sim/`, `src/safety/`, `src/planners/`, `src/env_v3/` | **Built through V3 Phase 7** — stochastic simulator, hard safety, strong planners, and fixed 6×9 Gymnasium API; Phase 7 reward is placeholder-only |
| Tests | `tests/` | **Built** — 307 tests total: 23 Phase 7, 39 Phase 6, 37 Phase 5, 53 Phase 4, 60 Phase 3, 52 Phase 2, and 43 legacy tests |
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
| Evaluation inputs/results | `data/eval_scenarios.json`, `data/eval_results/*.json`; Phase 4/5 sanity, Gate 6, and Phase 7 API-only sanity artifacts in `data/eval_v3/` |
| Real source corpus | `data/raw_docs/README.md`, `MANIFEST.json`, and `ndma_flood_guidelines.pdf` |
| Model artifact | `models/maskable_ppo_shelter.zip` |
| Experiment utilities | `scripts/greedy_check.py`, `tail_check.py`, `tail_analysis.py`, `retrieval_q2.py`, `phase4_stochastic_sanity.py`, `phase5_safety_sanity.py`, `run_gate6.py`, `phase7_env_sanity.py` |
| Automated verification | `tests/`, `pytest.ini`, `.github/workflows/ci.yml` |
| Project guidance | `README.md`, `EVALUATION.md`, `EVALUATION_V1.md`, `REVIEW_NOTES.md`, `DEMO_SCRIPT.md`, `PHASE1_PLAN.md`, `V3_BASELINE.md`, `V3_EVALUATION_PLAN.md`, `V3_SAFETY_SPEC.md`, `V3_PLANNER_SPEC.md`, `V3_GATE6_RESULT.md`, `V3_ENV_SPEC.md` |
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

Removed local-only `.claude/`, `.pytest_cache/`, and project `__pycache__/` directories.
Added `.claude/` and `.pytest_cache/` to `.gitignore`; Python bytecode caches were already
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
