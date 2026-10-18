# Lane X Phase 40 self-audit

The review captures below were generated locally by `web/e2e/lx40_live_operations.spec.ts` with the mock API and seed 620004. They show simulated incident data. The real API and old acceptance paths were checked separately. The walkthrough is restricted to the private repository.

## Ownership

Changed paths are `src/api/app.py`, `src/api/live_session.py`, `tests/test_lx_40_api.py`, `web/**`, `docs/course/DEMO_SCRIPT_V5.md`, `docs/course/LX40_self_audit.md`, `docs/course/LX40_shots/**`, and `docs/patent-roadmap/STATUS_LANE_X.md`. Each is Lane X owned in `LANES.md` and `AGENTS.md`. No spec, contract, frozen evaluation artifact, Lane S source, or acceptance spec was edited. The existing untracked `data/eval_results/phase14d/calls.jsonl` was left untouched and excluded from commits.

## Every action shows up everywhere

| # | Surface | Review evidence |
|---|---|---|
| 1 | Decision result: subject, certificate, state change | [Override result](LX40_shots/04-override.png), [Decline result](LX40_shots/06-decline.png) |
| 2 | Decisions log: newest-first cards and reason | [Override log](LX40_shots/04-override.png), [refusal card](LX40_shots/05-refused.png) |
| 3 | Readable event feed | [Accept feed](LX40_shots/02-accept.png), [refusal feed](LX40_shots/05-refused.png) |
| 4 | Map route marks: green accept, amber override, red refusal, grey decline; automatic re-route dashed | [Accept and override](LX40_shots/04-override.png), [refusal](LX40_shots/05-refused.png), [decline](LX40_shots/06-decline.png). Automatic re-route is covered by the real API acceptance flow, not this mock trace. |
| 5 | Six KPI tiles and short-lived deltas | [Accept](LX40_shots/02-accept.png), [override](LX40_shots/04-override.png) |
| 6 | Zone waiting and shelter occupied/reserved state | [Post-action shelter cards](LX40_shots/10-shelters.png), [zone cards](LX40_shots/11-zones.png) |
| 7 | Header live incident line | [Pending](LX40_shots/01-pending.png), [after override](LX40_shots/04-override.png) |
| 8 | Live Operations pending nav badge | [Pending red 1](LX40_shots/01-pending.png), [cleared after override](LX40_shots/04-override.png) |
| 9 | Overview live KPIs and last five decisions | [Overview](LX40_shots/07-overview.png) |
| 10 | Decisions session filter and newest certificate highlight | [Decisions](LX40_shots/08-decisions.png) |
| 11 | Four-second toast | [Accept toast](LX40_shots/02-accept.png), [override toast](LX40_shots/04-override.png), [refusal toast](LX40_shots/05-refused.png) |

The sticky bar is visible in the 1280×720 viewport before scrolling and remains in view after scrolling to the bottom, as asserted by the Phase 40 Playwright test. Its three buttons remain keyboard operable; the refusal request reaches the server and the modal stays open.

The recorded walkthrough uses the same decision bar, map, KPI strip, and modal for practice choices: [recorded practice decision](LX40_shots/12-practice.png).

## Actual DTO details

- The pending certificate decision is nested at `context.certified`. The recommendation action key is `WAIT` for HOLD; the backend POST decision for the UI's Decline is `REJECT`.
- The Phase 34C `/context` contract rejects extra candidate keys. The console requests `/context?include_subject=true` for the Phase 40 subject extension; the default response stays byte-for-byte equivalent to the established DTO.
- The state KPI object has `waiting`, `in_transit`, `safe`, and `certificates_issued`; stranded people are at top-level `people_stranded` on V4 state. When the latter is unavailable, the UI shows `—`.
- The simulator has a route's `travel_time_current` in minutes, which supplies the subject ETA. It does not expose a per-action route length or a list of closed graph edges in this DTO. Those subject fields remain null and display `—`. A non-OPEN `route_rows` entry describes a closed zone-to-shelter route, so the map legend says that rather than “closed road.”
- The simulator's canonical dispatch action identifies only zone and shelter; the batch size is derived from current vehicle capacity, people waiting, and free shelter seats, matching the simulator's dispatch rule. Zone and shelter display names are absent and remain null.
- Certified session creation accepts low, medium and high V4 dt2 worlds; `v4-stress-dt2-v1` is rejected by `SessionRegistry`, so the picker omits it.
- The POST response includes `state`, `certificates`, and `rechecks`. The store uses that state directly. Re-attaching fetches state, timeline, certificates, and audit/refusals; historical deltas are unavailable and display `—` on restored cards, whose certificate and chosen action are preserved.
- Recorded ACCEPT keeps the recording's certificate identifier for the established walkthrough. Practice overrides and declines carry no certificate identifier because the engine did not issue one for those choices.

## Verification and privacy

- `tests/test_lx_40_api.py`: subject schema, real state values, and original context keys.
- Vitest covers all six WebSocket message types, unavailable subject fields, and PRACTICE entries. The mock Playwright flows cover Accept, Override, refused override, Decline, cross-page state, sticky bar, axe, and a recorded practice decision through the shared modal.
- No external URL or credential was added to the web app. No secret is included in screenshots. The review branch and commits contain no AI/model/tool name.
- Full gate results and the branch tip are recorded in `STATUS_LANE_X.md` when the branch is ready for review.
