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
| Scenario data | `data/scenario.json` | Not built yet (Step 1) |
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
