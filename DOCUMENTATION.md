# Sentinel-Agent Sprint — Build Documentation

A running log of **every addition to this project**, in the order it was added.
Updated and committed at the end of each step, alongside the code it describes.

This file is source-controlled (it is not covered by any `.gitignore` rule) and is
intended to be read top-to-bottom as the story of how the prototype was built.

> **Honesty rule carried over from `DEVELOPMENT.md`:** nothing fabricated is ever
> described here as real. Every simplified, fictional, or placeholder element is
> labelled as such in the entry that introduces it.

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
| Gymnasium env + training | `src/env/` | **Built (Step 4)** — MaskablePPO, 91.5% optimal |
| Streamlit dashboard | `src/dashboard/` | **Built (Step 5)** — verified rendering in a real browser |
| Trained checkpoints | `models/` | **Built (Step 4)** — `maskable_ppo_shelter.zip` |
| End-to-end runner | `run_demo.py` | **Built (Step 6)** — rebuilds from nothing, exit-code checked |
| Evaluation suite | `src/eval/` | **Built** — 60 held-out scenarios, baselines, ablations |
| Tests | `tests/` | **Built** — 43 offline invariant tests, CI on GitHub Actions |
| Measured results | `EVALUATION.md` | **Written** — including the unflattering ones |

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
| S1 | C2 | 0.85 severe | 400 | 120 | 280 | **8** | no | operational |
| S2 | C4 | 0.63 high | 250 | 240 | 10 | 14 | no | operational |
| S3 | C5 | 0.48 moderate | 600 | 180 | 420 | 21 | no | operational |
| S4 | C8 | 0.10 low | 900 | 150 | **750** | 34 | **YES** | operational |
| S5 | C9 | 0.05 minimal | 1100 | 90 | **1010** | 41 | **YES** | operational |
| S6 | C6 | 0.35 moderate | 500 | 500 | 0 | 26 | no | at_capacity |
| S7 | C7 | 0.22 low | 350 | 60 | 290 | 30 | no | closed_structural_damage |

- **S1 is the trap.** It is nearest by a wide margin (8 min vs. a next-best of 14), so a
  naive distance-minimising baseline picks it — but it sits inside a `severe` flood
  cell. Only the constraint step rules it out.
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

Off → the real Gemini mask applies → **S4**. On → the mask is dropped and **the same
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
| `tests/` (5 files, 43 tests) | Real invariants, offline, 0.18 s. |
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
  false-excludes (usable shelter barred) across 21 verdicts.
- **Retrieval does not change the verdicts — it makes them evidenceable.** 0/21 verdicts
  flipped when retrieval was removed, but verbatim-verifiable citations fell from 21/21
  to 0/21.

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
survives quota errors without losing work, and resumes on a later day.

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
