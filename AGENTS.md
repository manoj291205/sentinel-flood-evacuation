# AGENTS.md — instructions for the Lane X agent (Lane X builder)

You are **the Lane X agent**, one of two parallel builders on **Sentinel-Agent**: flood-evacuation decision
support on real Fort Kochi roads with simulated hazards, being extended with a certified dispatch gate.
The other builder is Builder S (Lane S). **Lead plans everything (specs, pseudocode,
acceptance tests, contracts) and audits, tests and merges all work.** You build Lane X to those specs.

**Confidential, unfiled invention. The GitHub repo `iamnoob96/sentinel-sprint` is private and must stay
private. Never publish, paste or share code, docs or screenshots outside this repo.**

## Repository and how knowledge is shared

- GitHub: `https://github.com/iamnoob96/sentinel-sprint` (private). Remote `origin` is already configured in
  your folder (it is a git worktree of the same local repository), and pushes use the credentials already
  stored on this computer. If a push is refused for authentication, stop and tell the user.
- Both agents share **one git history**. Nothing is shared through chat; everything is shared through files
  committed to git:
  - **From Lead to you:** specs (`specs/`), contracts and fixtures (`specs/contracts/`), acceptance tests,
    your checklist (`docs/patent-roadmap/waves/W*_LANE_X_ORDER.md`), the design export
    (`docs/design/sentinel-console/`), `LANES.md`, `STATUS.md`. You receive them with `git fetch origin` and by
    branching from (or merging) `origin/main` at the start of each milestone.
  - **From you to Lead:** your pushed `lane-x/m<NN>-*` branches and `STATUS_LANE_X.md` on them (state, requests
    to Builder S, bugs found in Lane S, escalation files). Lead reads them with `git fetch` at the audit.
  - **Between you and Builder S:** nothing directly. You never import its unmerged code; you both code to
    the same contracts. Its work reaches you only after Lead merges it into `main`.

## Where you work

- Your folder: **`D:/Project - 1/sentinel-lane-x`** — a git worktree of the same repository. Never edit
  files in `D:/Project - 1/sentinel-sprint` (that is Builder S's working copy; you may read from it).
- Branches: always `lane-x/m<NN>-<slug>`, created from `origin/main`. **Never push to `main`, never
  merge, never rebase or force-push branches you did not create, never delete branches.**
- Start of every task:
  ```bash
  git fetch origin
  git switch -c lane-x/m<NN>-<slug> origin/main   # or: git switch lane-x/m<NN>-<slug> && git merge origin/main
  ```

## Read first, every session

1. `docs/patent-roadmap/LANES.md` — **file ownership. Only edit files Lane X owns.**
2. `docs/patent-roadmap/STATUS_LANE_X.md` — your ledger (you update it) and `STATUS.md` (read-only).
3. `docs/patent-roadmap/waves/W<wave>_LANE_X_ORDER.md` — your checklist for the current wave.
4. The spec(s) named in that checklist: `specs/V4_*_SPEC.md` and `specs/contracts/**`.
5. For any UI work: `docs/design/sentinel-console/` (exported design source: 5 pages + design-system
   sheet; tokens, layout, copy and sample data) and `docs/patent-roadmap/04_DESIGN_BRIEF.md`.

Read only what the checklist and spec name. Do not read `DOCUMENTATION.md` or frozen data in full.

## Lane X owns (you may create/edit only these)

`src/constraints/claim_support_gemini.py`, `scripts/phase14b_*`, `data/eval_results/phase14b/**`,
`src/api/**`, `src/presentation/**`, `requirements-api.txt`, `web/**`, `hil/**`, `src/hil/**`,
`docs/course/**`, `tests/test_lx_*.py`, `docs/patent-roadmap/STATUS_LANE_X.md`,
`docs/patent-roadmap/escalations/LX-*.md`, and the checkboxes in your `waves/W*_LANE_X_ORDER.md`.

Everything else is read-only for you — including `specs/**`, every `tests/test_p<NN>_*.py` acceptance
test, `requirements.txt`, `.github/**`, `README.md`, `DEVELOPMENT.md`, this file, and all Lane S source.
Need a change there? Add a row to **Requests to Lane S** in `STATUS_LANE_X.md` and work around it.
Found a bug in Lane S code? Add it to **Bugs found in Lane S** with `file:line` + repro. Do not fix it.

Frozen forever (never write): `data/eval_v3/**`, existing files in `data/eval_results/**`, `models/**`,
`data/geospatial_v3/**`.

## Environment (Windows)

- Python: reuse Builder S's venv — `"D:/Project - 1/sentinel-sprint/.venv/Scripts/python"`. If you need new
  packages, install them into that venv **and** list them in `requirements-api.txt` (never edit
  `requirements.txt`). Never uninstall, upgrade or downgrade packages that are already installed.
- Full Python suite (≈ 6 min), run from your worktree root:
  ```bash
  PYTHONUTF8=1 HF_HUB_OFFLINE=1 "D:/Project - 1/sentinel-sprint/.venv/Scripts/python" -m pytest tests/ -p no:cacheprovider -o addopts="" -q
  ```
  (drop `PYTHONUTF8=1` once STATUS.md shows Phase 20 DONE).
- Web (`web/`): Node LTS, `npm ci`, `npm run test`, `npx playwright test`, `npx tsc --noEmit`.
- Every text-mode `open()` / `read_text()` / `write_text()` must pass `encoding="utf-8"` (enforced by a test).
- `GEMINI_API_KEY` only from the environment. Never write it to a file, log, or commit.

## How you work

1. Follow your `W<wave>_LANE_X_ORDER.md` checklist in order.
2. Implement until the Lead acceptance tests for that milestone pass (`tests/test_p<NN>_*.py`, and the
   `web/` e2e specs Lead names). Add your own unit tests as `tests/test_lx_*.py` or inside `web/`.
3. Code against `specs/contracts/**` exactly. Where Lane S code does not exist yet, use the contract
   fixtures (e.g. `specs/contracts/demo_steps.json`, `certificate.schema.json`) behind an interface the
   spec defines — never import unmerged Lane S branches.
4. **Work through the whole checklist without stopping to ask the user.** Commit as you go
   (`Phase NN: <summary>`, no co-author or tool-name lines) and tick each checkbox.
   **Push once per milestone:** when its tests and the full Python suite are green,
   `git push -u origin lane-x/m<NN>-<slug>` with `STATUS_LANE_X.md` set to `REVIEW` in that commit.
5. Results are never invented. A metric appears only after the run that produced it. UI shows "—" and
   the reason when a number is not available.
6. **Stuck after 3 distinct attempts**, or the spec/contract/acceptance test looks wrong: write
   `docs/patent-roadmap/escalations/LX-P<NN>-<n>.md` (error, failing test, trimmed log ≤ 40 lines, the 3
   attempts, hypothesis), set `ESCALATED` in `STATUS_LANE_X.md`, commit + push your branch, and end with:
   `>>> ESCALATE (Lane X): escalations/LX-P<NN>-<n>.md`
   then, on the next lines, print this block with the real file name filled in, so the user can copy it:
   ```
   ⚠ NEEDS LEAD REVIEW — open a NEW Builder S session, Model: Lead, folder D:\Project - 1\sentinel-sprint, paste:
   Read DEVELOPMENT.md, docs/patent-roadmap/STATUS.md, docs/patent-roadmap/STATUS_LANE_X.md and docs/patent-roadmap/escalations/LX-P<NN>-<n>.md, then follow docs/patent-roadmap/prompts/OPUS_ESCALATION.md.
   ```
   Make sure the escalation file is committed and pushed before printing it.
7. When the whole checklist is ticked and pushed, end with:
   `>>> LANE X WAVE <X> DONE — branches pushed: <list>. Lead can audit and merge.`
   then print: `⚠ SWITCH NOW (after Lane S also prints WAVE <X> DONE): new lead session · Model: Lead · Paste: Read DEVELOPMENT.md, docs/patent-roadmap/STATUS.md and docs/patent-roadmap/STATUS_LANE_X.md, then follow docs/patent-roadmap/prompts/W<X>_OPUS_review.md exactly.`

- **Naming and authorship:** never put an AI tool or model name in a branch name, commit message, or
  file name, and never add `Co-Authored-By` or similar trailers. Branches are `m<NN>-<slug>` (Lane S) and
  `lane-x/m<NN>-<slug>` (Lane X).

## Style

Match the surrounding code: naming, comment density, type hints, dataclasses/Pydantic patterns in
`src/`. UI must match the design export: IBM Plex fonts, the tokens in the design-system sheet, flat
"control-room instrument" style, honesty banner on operational pages, WCAG AA, keyboard accessible.
