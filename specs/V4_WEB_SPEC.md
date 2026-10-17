# V4_WEB_SPEC — Phase 31: React shell + Live Operations with guided demo

Lane X · branch `lane-x/m31-web` · acceptance `specs/acceptance/web/p31_guided_demo.spec.ts`
Design source: `docs/design/sentinel-console/` (read its README first). Pages 32–33 are specified in Wave B.

## Stack
`web/` — Vite + React 18 + TypeScript (strict) + TanStack Query + React Router; Vitest + React Testing
Library; Playwright; `@axe-core/playwright`. No UI kit, no CSS framework: plain CSS modules +
CSS variables copied from the design tokens. Fonts: IBM Plex Sans / Mono / Sans Condensed (Google
Fonts link in `index.html`). Map: hand-drawn SVG from `/api/map/geometry` (no tile server, works offline).
Dev: `npm run dev` on port 5173 proxied to `http://localhost:8000/api`. Mock mode
`VITE_API_MOCK=1` serves `specs/contracts/*.json` through MSW so the UI runs without Python.

## Shell (all pages)
64 px header (SENTINEL mark, incident id `KOCHI-SIM-620000`, `t = x / H`, clock, Day/Night toggle
persisted in `localStorage` with try/catch, operator label) · honesty banner · left nav with exactly five
entries in three groups: OPERATE (Overview, Live Operations), VERIFY (Decisions & Certificates),
EVIDENCE (Evidence & Results), SYSTEM (System & Hardware). Pages 1, 3, 4, 5 are placeholder routes in
Wave A ("Arrives in Phase 32/33"). Tokens: `--ground --surface --sunk --ink --ink2 --ink3 --rule
--primary --onprimary --ok --warn --bad --info --w1..--w4 --road --roadc --route` with `[data-theme="Night"]`
overrides — values exactly as in `Main.dc.html`.

Routes: `/` Overview, `/live` Live Operations, `/decisions`, `/evidence`, `/system`. Accessible names the
acceptance test relies on: nav `aria-label="Main"`; buttons "Reset", "Run demo" / "Pause demo" /
"Replay demo", `aria-label="Next step"`, `aria-label="Previous step"`, "Accept", "Override", "Reject";
the theme button's name contains "theme"; caption is `role="status"`; step counter text `Step N / 6`;
override reason input labelled "REASON …" with the `required` attribute; the map scrolls inside its own
frame so the page never scrolls horizontally at 390 px.

## Live Operations page — port `Main.dc.html` 1:1
Components (each with a Vitest test): `GuidedDemoBar` (Back / Run demo|Pause demo|Replay demo / Next /
Reset, step counter, progress dots, `role="status" aria-live="polite"` caption), `PipelineStrip` (6
stages; current = filled primary, done = solid border, future = dashed), `KpiTiles` (4),
`OperationsMap` (grid 89.18 px = 100 m, north arrow, 100 m scale bar, flood circles, minor/major roads
with dashed centre lines, closed roads dashed + label, zone rectangles + decals, shelter squares with
state encoding and ID plates that invert when selected, capacity rings, group glyphs, highlighted
suggestion zone, moving group, selected route path), `Legend`, `SideTabs` (Suggestion · In transit ·
Shelters), `SuggestionCard` (kind, title, meta, "WHY THIS SUGGESTION" list), `GatePanel` (candidate rows
as buttons with interval bars on a 0.80–1.00 scale, threshold line at 75 %, shape + word verdicts),
`DecisionConsole` (Accept / Override with certified-only alternatives + required reason / Reject with
required reason; hidden when the step has no decision; accepted state names the certificate and links
to Decisions), `TransitList`, `ShelterLedger` (occupied + reserved bars), `EventFeed` (newest first, max 7,
shape per kind).

Data: Wave A uses `/api/demo/*` (FIXTURE). Auto-play: 1.5 s before the first tick; on a decision step
show it accepted (2.2 s) before advancing; otherwise advance every 4.2 s; stop at the last step
("Replay demo" restarts). Any manual Back/Next/Reset stops auto-play. Selecting a gate row changes only
the drawn route. Keyboard: every control reachable; visible focus ring; no hover-only information.

States: loading skeleton (rules, no spinner over data), API error banner with retry, STALE (dashed
outline + age) if no successful fetch for 5 s in live mode.

## Acceptance
- `npx tsc --noEmit`, `npm run test` (Vitest), `npx playwright test` green; axe: zero serious/critical.
- Copy `specs/acceptance/web/p31_guided_demo.spec.ts` **unchanged** to `web/e2e/p31_guided_demo.spec.ts`
  (Lead audits the hash). It checks: five nav entries; honesty banner text; Run demo walks steps 1→6 and
  ends with "Replay demo"; step 4 shows `UNDECIDED` before and the 512-future certification caption;
  step 5 suggests HOLD; Accept on step 3 shows `CERT-000127`; Override requires a reason; Day/Night toggle
  flips `data-theme`; layout has no horizontal scroll at 390 px width.

---

# Wave B — Phase 32 and Phase 33 (added 2026-10-15, Lead)

Lane X · branches `lane-x/m32-decisions` (from `main`), `lane-x/m33-pages` (from `lane-x/m32-decisions`)
· acceptance `specs/acceptance/web/p32_decisions.spec.ts`, `specs/acceptance/web/p33_pages.spec.ts`
(copy **unchanged** into `web/e2e/`), API tests `tests/test_p33_api.py`. Design sources:
`docs/design/sentinel-console/Decisions.dc.html`, `Overview.dc.html`, `Evidence.dc.html`, `System.dc.html`.
Rule for every page: **numbers only from the API**, which reads them from frozen artifacts or fixtures;
anything absent is shown as `-` with a one-line reason. Never type a number into the UI code. Every page
keeps the honesty banner. Gate pages are confidential until P0 is filed (local only, no screenshots out).

## Phase 32 — Decisions & Certificates (`/decisions`)
Data: `GET /api/certificates`, `GET /api/certificates/{cert_id}`, `POST /api/certificates/{cert_id}/replay`,
`GET /api/decisions/{decision_id}/why` (all FIXTURE until 34A; the why fixture's `decision_id` values map
to certificates by `cert_id`; show "No explanation recorded" when 404).
- Heading `Decisions & Certificates` (h1). Action keys are shown as `Z-03 → S-04` everywhere (arrow U+2192, spaces). List `aria-label="Decision list"`: one row per certificate,
  newest first, each a button whose accessible name starts with the cert id (e.g. `CERT-000127 · DISPATCH ·
  Z-03 → S-04 · 40`). `?cert=<id>` in the URL selects a row (deep link from Live Operations "accepted" state).
- Detail `aria-label="Decision detail"`: kind, timestep, futures used, looks, params (ε, δ, A_MAX), operator
  decision and reason; candidate table (verdict word + shape, successes / n, interval bar lower–upper on a
  0.80–1.00 scale with the `1 − ε` line, outcome counts OK / STRANDED / UNSAFE / OVERFLOW); hash chain
  strip `prev_cert_hash → cert_hash` (first 12 hex chars, full value in a `title` and copy button).
- `Replay certificate` button → caption (`role="status"`) `MATCH — regenerated bit-for-bit` or
  `MISMATCH — <fields>`; checkbox `Tamper with forecast (demo)` sends `{tamper: true}`.
- "Why this suggestion" panel: exactly the three reasons from the why document, `certified_lower` vs
  `threshold`, futures used.
- Filters: kind (All / Dispatch / Migration / Hold / Override) as a `radiogroup` named `Kind`.
- States: loading rules, error banner with Retry, empty list text `No certificates yet`.

## Phase 33 — Overview (`/`), Evidence & Results (`/evidence`), System & Hardware (`/system`)
New API (Lane X, `src/api/`, `src/presentation/`): see `V4_API_SPEC.md` "Wave B additions".
- **Overview** h1 `Incident overview`: KPI tiles from `/api/demo/state` (FIXTURE) or a live session
  state; sections `Population ledger`, `Shelters`, `Dispatch gate activity` (counts by kind from
  `/api/certificates`), `System health` (from `/api/system/status`), `Latest certificates` (5, links to
  `/decisions?cert=…`), `What is real vs simulated` (static honesty text — not numbers).
- **Evidence & Results** h1 `Evidence & Results`: one table per manifest `group` from `/api/evidence`
  (label, display value, unit, `source_path` shown as a small monospace link-free label, `-` + note when
  value is null). Section `Patent experiments (Phase 27 · pre-registered)` shows bar names from the
  `p27-analysis` item or `-  Not run yet` — never placeholders that look like results.
- **System & Hardware** h1 `System & Hardware`: `Devices` table from `/api/system/status` (device id, kind,
  online word + shape, last seen, age), `MQTT topics` list, `Actuator command log` (acks, newest first,
  max 20; empty text `No commands yet`), `How a suggestion becomes a dispatch` (static 6-step text), latency
  `-` until `data/eval_results/phase28/latency.json` exists.
- Every page: works at 390 px without horizontal scroll; axe zero serious/critical (Day and Night).

## Acceptance (Wave B web)
`npx tsc --noEmit`, Vitest (one test per new component), Playwright including the two copied Lead specs
and your own axe spec for the three new pages. Mock mode serves the new contract fixtures
(`evidence` from a mock built **only** from `specs/contracts/evidence_manifest.json` with every value null,
`system_status_fixture.json`).

---

# Wave C — Phase 34A (added 2026-10-17, Lead)
Web changes are specified in `specs/V4_WIRING_SPEC.md` §7 (RECORDED banner and seed note, `SAMPLE FUTURES` pipeline label,
RECORDED decision-console note, `POLICY` count, Evidence order 14D → 14C failed → 14B superseded, Phase 10/13 tables, R beside
the Phase 27 bars, `Document rules` tiers table) with the live acceptance spec `specs/acceptance/web/p34a_live_demo.spec.ts`
run by `npm run test:e2e:live`. The p31/p32/p33 specs keep running in mock mode (`npm run test:e2e`).
