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
