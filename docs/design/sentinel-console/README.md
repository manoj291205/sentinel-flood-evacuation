# Sentinel console — design source (exported from the design tool)

Confidential. This is the reference design for the V4 web console (Phases 31–33). The live, interactive
version is a private the design tool artifact owned by the project lead; these files are its source so that
every builder (Builder S and the Lane X agent) can read it from the repo.

| File | Page |
|---|---|
| `Overview.dc.html` | 1 · Overview |
| `Main.dc.html` | 2 · Live Operations — map, **guided demo** (6 scripted steps), side tabs Suggestion / In transit / Shelters, event feed |
| `Decisions.dc.html` | 3 · Decisions & Certificates — Why it was allowed / Certificate & replay / Audit trail |
| `Evidence.dc.html` | 4 · Evidence & Results — Safety rules (NDMA) / Results / About the project |
| `System.dc.html` | 5 · System & Hardware — Scenario control / Hardware-in-the-loop / Architecture & site map |
| `Components.dc.html` | Design system — colour tokens (Day + Night), type, gate-verdict chips, buttons, rules |
| `canvas.json` | Board layout / page order |
| `fort_kochi_map_geometry.json` | Projected Fort Kochi road geometry used by the map (880 × 789 px, `px_per_m` ≈ 0.892; zones, shelters, major/minor roads, closed segments as SVG path data) |

## How to read a `.dc.html` file

They are HTML templates for the the design tool runtime (they will not render on their own in a browser):

- Markup between `<x-dc>` tags is the page. `{{name}}` is a value computed in the script; `<sc-for list="{{x}}" as="i">`
  repeats its children; `<sc-if value="{{x}}">` shows its children conditionally.
- The `<style>` block in `<helmet>` holds the **design tokens** as CSS variables (`--ground`, `--surface`,
  `--ink`, `--primary`, `--ok`, `--warn`, `--bad`, `--info`, water ramp `--w1..--w4`) with a `[data-theme="Night"]` override.
- The `<script type="text/x-dc">` at the bottom is a small class whose `renderVals()` returns every
  value the template uses — this is where the **sample data** lives (e.g. the six guided-demo steps in
  `Main.dc.html`: caption, suggestion, "why" bullets, gate candidates with bounds, events, KPIs).

When implementing in React (`web/`), port layout, tokens, copy and interaction 1:1; replace the sample
data with API data (`specs/contracts/**`). The guided-demo step content becomes the fixture
`specs/contracts/demo_steps.json` until the real demo endpoint is wired (Phase 34A).
