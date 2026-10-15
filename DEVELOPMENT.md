# DEVELOPMENT.md — Sentinel-Agent

Flood-evacuation decision support on real Fort Kochi roads with simulated hazards (V3 phases 0–19 done),
being extended with a certified dispatch gate (V4, phases 20–36). **Private repository — confidential,
unfiled invention. Never make it public or show the gate work before the Indian provisional (P0) is filed.**

## Start of every session
1. Read `docs/patent-roadmap/STATUS.md` (live ledger) and the prompt file the user pasted.
2. Read only the files your prompt or spec names. Do not read `DOCUMENTATION.md` or frozen data in full.
3. Roles and switching rules: `docs/patent-roadmap/03_MODEL_WORKFLOW.md`.

## Environment (Windows)
- Python 3.12 venv: `.venv/Scripts/python`
- Tests (≈ 6 min, 735 pass):
  `PYTHONUTF8=1 HF_HUB_OFFLINE=1 .venv/Scripts/python -m pytest tests/ -p no:cacheprovider -o addopts="" -q`
  (`pytest.ini` already adds `-q`; `-o addopts=""` keeps the summary visible). Drop `PYTHONUTF8=1` after Phase 20.
- Git: `core.autocrlf=false` locally until `.gitattributes` lands (Phase 20); otherwise frozen hashes break.
- `GEMINI_API_KEY` and `GROQ_API_KEY` come from the environment only — never write them to a file or commit them.

## Two builders (read docs/patent-roadmap/LANES.md)
- Builder S = **Lane S** (this folder, branches `m<NN>-*`). the Lane X agent = **Lane X** (worktree
  `D:/Project - 1/sentinel-lane-x`, branches `lane-x/m<NN>-*`, instructions in `AGENTS.md`).
- Edit only files your lane owns. Never edit, rebase, merge or delete `lane-x/*` branches or Lane X files
  (`src/api/`, `src/presentation/`, `web/`, `hil/`, `src/hil/`, `docs/course/`, 14B and 14C files, `tests/test_lx_*`).
  Report bugs there in `STATUS.md` -> Notes for the Lane X agent.
- Only Lead merges into `main`, after auditing both lanes (LANES.md -> Merge and audit).

## Hard rules
- Frozen, read-only: `data/eval_v3/**`, `data/eval_results/**` (existing files), `models/**`, `data/geospatial_v3/**`.
- New behaviour only behind new `v4-*` config IDs; legacy results must stay bit-identical.
- Lead writes specs (`specs/V4_*_SPEC.md`) and acceptance tests (`tests/test_p<NN>_*.py`); Builder S must not
  edit or weaken them — escalate instead (`docs/patent-roadmap/escalations/`).
- Work autonomously through the build order; do not stop to ask the user between steps. Commit as you go
  (`Phase NN: …`; no Co-Authored-By trailer); **push once per milestone** when its tests and the
  full suite are green, with `STATUS.md` updated in that commit.
- Design decisions the spec does not settle, failures that survive 3 attempts, and failed gates go to the
  `lead-advisor` subagent (`docs/workflow/agents/lead-advisor.md`). Only if it answers NEEDS_HUMAN or its fix
  fails, stop and show the user a `⚠ NEEDS YOU` block (see the build prompts).
- **Naming and authorship:** never put an AI tool or model name in a branch name, commit message, or
  file name, and never add `Co-Authored-By` or similar trailers. Branches are `m<NN>-<slug>` (Lane S) and
  `lane-x/m<NN>-<slug>` (Lane X).
- Never invent results. A number appears only after the run that produced it.
- Runner subagent `task-runner` (`docs/workflow/agents/task-runner.md`) is for test runs, grep, mechanical
  edits, fixtures and doc counts only.
- Web console scope: exactly 5 pages (Overview, Live Operations with guided demo, Decisions & Certificates,
  Evidence & Results, System & Hardware). Design: `docs/patent-roadmap/04_DESIGN_BRIEF.md`.
