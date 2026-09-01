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
| Real source documents | `data/raw_docs/` | Empty — awaiting real NDMA/NIDM PDFs (Step 2) |
| Local RAG (embed + retrieve) | `src/rag/` | Not built yet (Step 2) |
| Gemini constraint step | `src/constraints/` | Not built yet (Step 3) |
| Gymnasium env + training | `src/env/` | Not built yet (Step 4) |
| Streamlit dashboard | `src/dashboard/` | Not built yet (Step 5) |
| Trained checkpoints | `models/` | Empty (Step 4) |
| End-to-end runner | `run_demo.py` | Not built yet (Step 6) |

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
