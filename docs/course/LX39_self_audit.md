# Phase 39 Lane X self-audit

Branch: `lane-x/m39-console-showcase`. This is the Lane X review handoff. The requested
`docs/patent-roadmap/audits/` location is Lead-owned under `AGENTS.md` and `LANES.md`, so this audit and
the screenshots are in `docs/course/` (Lane X-owned). A move or ownership grant is requested in
`STATUS_LANE_X.md`.

## Ownership and frozen artifacts

The changed source paths are `src/api/**`, `src/presentation/**`, `web/**`, `tests/test_lx_39_api.py`,
`docs/course/**`, and `docs/patent-roadmap/STATUS_LANE_X.md`. These are Lane X-owned. No spec,
acceptance test, engine, frozen data, or other builder's file was edited. The unrelated untracked
`data/eval_results/phase14d/calls.jsonl` remains uncommitted.

The new API reads frozen Phase 27 and V3 artifacts. It does not write them. The index de-duplicates
interrupted Phase 27 run lines by system, world and seed, as the D-27 analysis does, and serializes
non-finite artifact values as JSON `null` rather than fabricating a number.

## Source tracing and limits

| Console display | Source | Limit shown to the operator |
|---|---|---|
| 1,260 runs, system/world/seed metrics, 180 P traces, distribution dots | `data/eval_results/phase27/runs/*.jsonl`; `phase27/states/*.jsonl.gz` | Only P has step traces. A, A2, B, HOLD, P-noFC and P-noHyst have final summaries only. |
| Replay choices, candidate people, hazard severity, road closures, shelter ledger | The selected `phase27/states/<world>_<seed>.jsonl.gz` and `data/geospatial_v3/fort_kochi_osm_drive_v1.json` | These traces lack per-step safe, stranded, unsafe and transit totals, so the player shows `—` with the reason. |
| D-27 bars and failure rates beside throughput R | `data/eval_results/phase27/analysis.json` | Bars 1 and 3 fail; 2 and 4 pass. No outcome-effect claim. |
| Phase 10, 13 and 14 result cards | `/api/evidence`, whose values are backed by the approved evidence manifest and frozen artifacts | Missing values remain `—` with a reason. 14D is the evaluation of record; 14C failed; 14B is superseded. |
| Journey test count and milestone rows | `README.md` reviewed milestone table, dated in the tile | The README's 1,112 test count is dated 2026-10-17 and is not represented as this branch's test result. Ranges count as one milestone row; the timeline expands 46 named cards. |
| Corpus chunks | `data/eval_v3/phase11_corpus_summary.json` | Artifact count, not a claim of retrieval accuracy. |
| Recorded escrow/last-known comparison | `data/eval_results/phase35lite/outages.json` | Exploratory, not pre-registered, no outcome-effect claim. |
| Live population, shelter, transit, audit and certificates | Local `/api/sessions/{id}` endpoints and WebSocket | Live demo parameters are labelled as distinct from the evaluated configuration. Refused uncertified override is never committed. |
| NDMA page/chunk in the decision modal | Existing local operator audit reference `ndma-flood-guidelines-2008`, page 64, chunk `ndma-flood-guidelines-2008-p64-c0` | The modal states that certification comes from the simulated forecast, not the text. |

The Phase 27 claim language was checked against `specs/V4_D27_DECISION.md` and
`specs/contracts/claims_policy.json`. The 23.7% and 0.7% group failure rates appear together with
R = 0.214 and the lower delivery count. Bars 1/3 FAIL and 2/4 PASS appear on the library and story pages.

## Local-only and disclosure check

`rg -n 'http|https' web/src` found only MSW's local API handler name and the WebSocket protocol choice in
`LiveSession.tsx`; no external map tile, CDN or network URL was added. The SVG map uses the local Fort Kochi
graph. No API keys or key fragments are in changed files. Branch and commit names carry no tool/model
attribution; commit messages have no co-author trailers. The course pack remains RESTRICTED.

## Verification

- Targeted Python API and new library tests: 12 passed after preserving the original KPI object shape.
- TypeScript: `npx tsc --noEmit` passed.
- Production web build: `npm run build` passed.
- Vitest: 21 passed.
- Mock Playwright including seven page-level axe checks: 36 passed, one conditional screenshot case skipped.
- Live Playwright against the local API: 10 passed.
- Full Python suite: pending final rerun after the KPI compatibility fix. The earlier run found that one
  extra KPI key broke `test_p30_api.py`; the targeted 12 tests now pass. Update this line before REVIEW.

The Playwright capture case was run separately against the local API after the library index loaded.
Screenshots: `LX39_shots/overview.png`, `live.png`, `live-modal.png`, `simulations.png`,
`decisions.png`, `evidence.png`, `system.png`, and `journey.png`.

## Review notes

The Phase 27 trace stores certifier inputs and choices, not per-step arrivals or group transit positions.
The library therefore animates route decisions over the real road graph and displays final metrics from
the run summaries. A2 comparison has a final summary and an explicitly unavailable per-step map.
The live session exposes transit progress through a read-only state field. The session registry accepts
low, medium and high worlds; the recorded stress world is available in the library, not the live cards.
The UI shows the existing five core navigation links in `Main` and two showcase links in a sibling nav so
the unchanged P31 accessibility acceptance remains valid.
