# V4_WIRING_SPEC — Phase 34A: wire the API and web console to the real gate

Lane X · branch `lane-x/m34a-wire` (from `origin/main`) · Python acceptance `tests/test_p34a_wiring.py` · web acceptance
`specs/acceptance/web/p34a_live_demo.spec.ts` (copy **unchanged** to `web/e2e/`) · contracts `demo_trace.schema.json`,
`rule_tiers.schema.json`, `deploy_check.json`, `claims_policy.json`, `certificate.schema.json` (now with `POLICY`),
`decision_why.schema.json` (now with `RECORDED`), `evidence_manifest.json` (Phase 10/13 and Bar 1 R items).
Confidential until P0 is filed: local only, no screenshots or recordings leave the machine.

## 1. Goal
Replace the Wave A contract fixtures behind `/api/demo/*`, `/api/certificates*` and `/api/decisions/{id}/why` with
output of the merged Phase 25/26 engine, so the guided demo, certificates, replay and "why" are genuine. Show each
document rule's tier exactly as the P15T2 loader recorded it. Serve the built console from FastAPI (one port) behind
optional basic auth, which the 34B Dockerfile and `scripts/deploy_check.py` rely on.
**D-27 (`specs/V4_D27_DECISION.md`) applies to every word the console shows:** no outcome-effect claim (no better
evacuation outcomes, more people delivered, fewer failed trips, lives saved). Captions describe what the gate did,
never what it achieved. Checked against `claims_policy.json`.

## 2. Files (Lane X only)
New: `src/api/demo_live.py` (trace builder + CLI), `src/api/why.py` (reason templates), `src/presentation/rule_tiers.py`,
`data/demo_v4/demo_trace.json` (written by the CLI, committed; Lane X owns `data/demo_v4/**`), `tests/test_lx_p34a_*.py`.
Modified: `src/api/app.py`, `src/api/fixtures.py`, `src/api/dto.py`, `src/presentation/evidence.py`, `web/**`
(incl. `web/playwright.config.ts`, `web/package.json` scripts). Lane S code is **imported read-only**:
`src.geospatial.v4_runtime.build_v4_runtime`, `src.geospatial.load_road_graph`, `src.certify.gate.CertifiedGate`,
`src.certify.ledger.SimLedgerAdapter`, `src.certify.params.get_cert_params`,
`src.certify.recertify.{RecertPolicy, recertify_in_transit}`, `src.safety.evaluate_actions`,
`src.certify.replay.replay_certificate`, `src.certify.certificate.{CertificateInputs, validate_certificate, verify_chain}`,
`src.constraints.t2_wiring.load_t2_approval`, `src.constraints.ndma_rules.load_rules`. No other Lane S symbol, no
change to any Lane S file. `scripts/phase27_run.py::run_episode` is the reference for the epoch loop (read it, do not import it).

## 3. Recorded demo trace (`v4-demo-trace-v1`)
Fixed config (in `demo_trace.schema.json`): world `v4-medium-dt2-v1`, generator seed `620003`, params `v4-cert-test-v1`,
6 epochs from timestep 0, operator `{decision: ACCEPT, actor: demo-operator, reason: ""}`, `RecertPolicy()` defaults.
`seed_note` = `"Seed chosen during planning (2026-10-17) because its first six epochs include an escalated hold,
dispatches, in-transit re-checks and a re-route; a demonstration, not a performance sample. Parameters v4-cert-test-v1
are the fast CI set, not the evaluated configuration (v4-cert-eval-v1)."` (Lead's pilot of this config, 2026-10-17: epoch 0 HOLD with every option UNDECIDED, then DISPATCH in epochs 1–5, KEEP
re-checks from epoch 2, a MIGRATION in epoch 4 and a COOLDOWN in epoch 5 — 7 certificates. The committed trace is
whatever the run produces; never edit it by hand.)
```text
build_demo_trace(config=DEMO_CONFIG, graph=None) -> dict:
  graph = graph or load_road_graph()
  scenario, sim, graph, overlay, world = build_v4_runtime(world_id, generator_seed=seed, graph=graph)
  ledger = SimLedgerAdapter(sim); gate = CertifiedGate(scenario, graph, world, get_cert_params(params_id), ledger, world_id=world_id)
  histories = {}; steps, step_certs, recert = [], [], []
  for epoch in range(6):                                   # stop early only if sim.state.terminal (then fewer steps → error)
      sim.observe(); state = sim.prepared_state_for_debug()
      before = len(ledger.certificates())
      decisions = recertify_in_transit(gate, state, overlay.road_state, sim.transit_plans(), histories, RecertPolicy())
      state = sim.prepared_state_for_debug()
      result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
      decision = gate.commit(result, inputs, operator=OPERATOR)
      new_certs = ledger.certificates()[before:]
      recert += rows(decisions)                             # group_id = event_id; cert_id of a MIGRATION else null
      steps.append(step_from(epoch, state, result, decision, decisions, new_certs, sim))   # §3.1
      step_certs.append([c["cert_id"] for c in new_certs])
  return {contract, config, graph_fingerprint, steps, step_certificates, certificates: ledger.certificates(),
          inputs: {c.cert_id: ledger.inputs(c.cert_id).to_dict()}, recert}
```
CLI: `python -m src.api.demo_live --write` writes `data/demo_v4/demo_trace.json` as
`json.dumps(trace, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` (LF). `--check` rebuilds and exits 1 if the
file differs. The trace has no wall-clock values (no `ms` in captions or meta), so a rebuild is byte-identical.

### 3.1 Step mapping (each step validates `demo_step.schema.json`)
Zone/shelter ids are displayed as `Z-03` / `S-05` (two digits); action keys as `Z-03 → S-05`; `WAIT` as `HOLD`.
- `kind`: `NEW DISPATCH` (epoch certificate kind DISPATCH) · `HOLD + ESCALATE` (HOLD and `decision.escalate`) ·
  `HOLD` (other HOLD) · `AUTOMATIC SAFETY ACTION` if the epoch committed a MIGRATION and nothing else needs the operator.
- `pipeline_stage`: 4 for DISPATCH/HOLD steps (operator decides), 3 when only re-certification happened.
- `gate.candidates`: one row per certificate candidate (action key as `id`, display label, `status` = verdict with
  `ALWAYS_ALLOWED` → `ALWAYS ALLOWED`, `lower`/`upper`, `meta` = `"{successes}/{n} futures OK"`; HOLD row meta `"always allowed"`).
  `gate.meta` = `"n = {futures_used} futures · {looks} look(s) · 1 − ε = {1-eps_dispatch:.2f} · {params_id}"`.
- `suggestion`: title = chosen label or `HOLD`; meta = `"{people} people · certificate {cert_id}"`; `why` = the three
  reasons of §4 for that certificate.
- `caption` templates (fill the slots only; no other wording):
  DISPATCH `"{n} sampled futures checked for every option; {feasible} option(s) cleared the bar, {undecided} undecided, {infeasible} infeasible. Suggested: {label}."`;
  HOLD + ESCALATE `"No dispatch option cleared the bar across {n} sampled futures, so the gate holds (fail-closed) and escalates to the field team."`;
  re-check line appended when the epoch re-checked groups: `" {k} group(s) on the road re-checked: {keep} keep, {migrate} re-routed."`.
- `decision_required` true for DISPATCH and HOLD steps; `certificate_id` = the epoch's DISPATCH certificate id, else null;
  `hold_record` = `"HOLD logged as {cert_id}"` for HOLD; `auto_note` = `"Re-routed automatically as {cert_id} (operator notified)."` for a MIGRATION, else null;
  `override_alternatives` = labels of other FEASIBLE candidates.
- `kpis`: `waiting` = `state.population_remaining`, `on_road` = `state.people_in_transit`, `safe` = `state.people_safely_arrived`
  (state after the commit), `certificates_issued` = certificates so far. `events` = this epoch's simulator audit events
  mapped to `ok/bad/warn/info` (arrival ok, stranding/unsafe bad, closure warn, else info), text from the event message.
- `groups`, `shelters`, `moving_group`, `highlight_zone`, `default_selection`, `g0009_label`: from the real state
  (`moving_group` null, `g0009_label` `""` when not applicable). Never copy values from `demo_steps.json`.

## 4. "Why" reasons (`src/api/why.py`, `GET /api/decisions/{cert_id}/why`, `source = RECORDED`)
`decision_id` = `cert_id`. For the chosen candidate `c` of a DISPATCH/MIGRATION/OVERRIDE certificate:
1. `"Certified lower bound {c.lower:.3f} ≥ threshold {1-eps:.2f} over {cert.futures_used} sampled futures ({looks} look(s))."`
2. `"In {OK} of {n} futures the group arrives safely; {STRANDED} stranded, {UNSAFE} unsafe, {OVERFLOW} overflow{, POLICY rule-blocked}."`
3. `"{f} other option(s) also cleared the bar, {u} undecided, {i} infeasible; HOLD is always allowed."`
HOLD: (1) `"No dispatch option reached the threshold {1-eps:.2f} over {futures_used} sampled futures."`, (2) best
candidate by `lower` with its `{lower:.3f}` and verdict, (3) `"The gate holds (fail-closed) and escalates; nothing was dispatched."`.
`certified_lower` = `c.lower` (null for HOLD), `threshold` = `1 − eps_dispatch`, `futures_used` from the certificate.
Each reason ≤ 160 characters. Unknown cert → 404.

## 5. API changes (`src/api/app.py`)
| Item | Rule |
|---|---|
| Source switch | env `SENTINEL_DEMO_SOURCE` = `RECORDED` (default) or `FIXTURE` (Wave A fixtures, for MSW parity and P30 tests). Body `source` and header `X-Sentinel-Source` carry it. |
| `/api/demo/*` | RECORDED: playback over `trace.steps` (same next/prev/reset semantics as `DemoPlayback`); trace loaded once at startup and checked against `demo_trace.schema.json`; a missing/invalid trace never stops startup (health, sessions, evidence keep working) — the demo, certificate and why endpoints then answer 503 with a clear message (never a silent fixture fallback). |
| `/api/certificates`, `/{cert_id}` | RECORDED: the trace certificates, newest first in the list; GET returns the certificate exactly (schema-bound, headers per the 2026-10-15 amendment). |
| `POST /{cert_id}/replay` | RECORDED: `replay_certificate(cert, CertificateInputs.from_dict(inputs[cert_id]), graph=graph)`; `tamper: true` replays a copy whose `forecast_hash` is replaced by `sha256(b"tampered").hexdigest()`; response `{result, mismatched_fields}` from the real `ReplayReport`. Run in a threadpool (`def` endpoint), not on the event loop. |
| `GET /api/constraints/tiers` | `rule_tiers.schema.json`, from `src/presentation/rule_tiers.py` (§6). |
| `GET /api/evidence` | add format `fixed3` → `f"{value:.3f}"`. Nothing else changes. |
| `StateDTO.kpis.certificates_issued` | unchanged (0 for legacy sessions). |
| Static console | if `SENTINEL_WEB_DIST` (default `web/dist`) contains `index.html`, mount it at `/` with SPA fallback (unknown non-`/api`, non-`/ws` paths → `index.html`). |
| Basic auth | if `SENTINEL_DEMO_PASSWORD` is set and non-empty: every request except `GET /api/health` needs `Authorization: Basic` with user `sentinel` and that password (`secrets.compare_digest`); else 401 + `WWW-Authenticate: Basic realm="sentinel"`. WebSocket: same check on the upgrade request. Never log the password. Unset → no auth (local dev). |
| CORS | unchanged (`http://localhost:5173` only). |

## 6. Rule tiers — read through, never inferred (`src/presentation/rule_tiers.py`)
`rule_tiers(results_path=…/data/constraints_v4/p15t2/tier_results.json, approval_path=t2_wiring.APPROVAL_PATH) -> dict`:
missing file → `status MISSING`, `rules []`. Else parse; `status CURRENT` only if `schema == "p15t2-tier-results-v1"`,
`approval_record_sha256 == load_t2_approval(approval_path).record_sha256`, `t2_enabled` equals that approval's `enabled`,
and `rules_file_sha256` equals the SHA-256 of the file named in `rules_file`. Otherwise `status STALE` with the first
failing check as `status_reason`, and **every `tier` null** with note `"tier result is stale; re-run P15T2"`.
CURRENT: one row per record, `tier` copied verbatim, `semantic_outcome` / `source_integrity_pass` from `record.semantic`
(null when not called), `predicate` from `load_rules(rules_file)` by `rule_id`, `note` null. The module never imports
`claim_support_p14c.http_transport`, never calls `load_tiered_rules`, never reads the 14D score, and makes no network call.
Evidence & Results shows the rows in a table **Document rules (Phase 15′ tiers)**: Rule · Predicate · Tier · 14D answer ·
Integrity · Note (the table's accessible name starts with `Document rules`), with the caption "Tier from the P15T2 tiering run; T2 needs a SUPPORTED answer from the 14D verifier."

## 7. Web changes (`web/`)
- Live Operations: source RECORDED → banner text `Recorded run of the real engine · demo parameters v4-cert-test-v1 (not the evaluated configuration)`;
  FIXTURE keeps "scripted preview". Show the trace `seed_note` under the guided-demo bar. Pipeline label `FORECAST 256+ FUTURES` → `SAMPLE FUTURES` (n varies).
  In RECORDED mode Accept shows the recorded certificate; Override/Reject keep the required-reason form but submit shows
  `Not committed: the recorded demo replays the operator's ACCEPT. Use a live session to override.`
- Decisions & Certificates: outcome counts show `POLICY` as a fifth value only when present; data from the real API.
- Evidence & Results: claim-support group in this order — 14D first, labelled **evaluation of record**; 14C labelled
  **failed** with its reasons; 14B **superseded** (always `-`). Phase 10 and Phase 13 tables from the new manifest items.
  Phase 27 section shows the R item next to the bars. Rule tiers table (§6). Never show T2 unless the API row says `T2`.
- `web/package.json` scripts: `test:e2e` (mock mode, all existing specs) and `test:e2e:live` (Playwright project
  `live`: starts `uvicorn src.api.app:create_app --factory --port 8000` with `SENTINEL_DEMO_SOURCE=RECORDED` and the
  Vite dev server **without** `VITE_API_MOCK`, runs only `p34a_live_demo.spec.ts` and, from 34C, `p34c_live_session.spec.ts`).
  The mock project ignores both.
  34B's CI calls exactly these two script names.

## 8. Edge cases
Trace build fails or ends early (terminal before 6 epochs) → raise, never pad. A replay MISMATCH on an untampered trace
certificate is a bug (report it; do not hide it). `fixed3` on a non-number → `-` + note. Basic auth header malformed → 401.
`SENTINEL_DEMO_SOURCE` unknown value → startup error.

## 9. Acceptance
`tests/test_p34a_wiring.py` (milestone `P34A`): trace reproducible and schema-valid; every trace certificate validates,
chain intact, replays MATCH from stored inputs; API demo/certificates/replay/why = direct computation; tamper MISMATCH names
`forecast_hash`; FIXTURE mode still serves Wave A fixtures; rule tiers CURRENT with R01/R02 = T1 and read-through of the
file (T2 shown only when the file says T2 and the approval matches; STALE → null); no network in the tiers path; new
manifest items render; static + basic auth; no banned outcome wording in trace text. Web: `p34a_live_demo.spec.ts` via
`npm run test:e2e:live`, plus `tsc`, Vitest, `npm run test:e2e` (p31/p32/p33 mock specs unchanged and green).
Runner: not available to Lane X. Out of scope: hosting (34B), any Lane S change. Live certified sessions are Phase 34C (§10).

## 10. Phase 34C — live certified session (added 2026-10-17 at the judges' request)
Lane X · branch `lane-x/m34c-live-session` (from `origin/main` after X34A.9 is pushed, merging your pushed
`lane-x/m34a-wire`; before 36) · acceptance `tests/test_p34c_live_session.py`, web `specs/acceptance/web/p34c_live_session.spec.ts`
(copy unchanged) · contracts `live_context.schema.json`, `live_ws_message.schema.json`. Files: `src/api/**` (new
`live_session.py`), `web/**`, `tests/test_lx_p34c_*.py`. Lane S code imported read-only: `SimulationSession(certified=True)`
as merged (`context`, `decide`, `certificates`, `ledger.inputs`), `replay_certificate`, `CertificateInputs`.

**10.1 API.** `POST /api/sessions` gains `certified: bool = false` and `params_id: str | null`. `certified: true` needs
`regime` in {`v4-low-dt2-v1`, `v4-medium-dt2-v1`, `v4-high-dt2-v1`} and `params_id` = `v4-cert-test-v1` (the fast demo
set; omitted → that value); anything else → 422. It builds `SimulationSession(seed, regime, graph=graph, certified=True,
params_id=params_id)`; the `SessionDTO` adds `certified` and `params_id`. Without `certified` nothing changes (P30 parity).
- `GET /sessions/{id}/context` (certified) = the Wave A `ContextDTO` plus `certified` (`live_context.schema.json`):
  `params_id`, `timestep`, `threshold` = `1 − eps_dispatch`, `futures_used`, `looks`; `recommendation` (the certifier's
  choice: action key, label, verdict, lower, upper, successes, n, outcome counts; `WAIT` → `HOLD`, verdict `ALWAYS_ALLOWED`,
  bounds null); `why` = three reasons by the §4 templates, computed from the pending `CertificationResult` (DISPATCH or HOLD
  form); `candidates` = every certified candidate; `alternatives` = up to 3 FEASIBLE candidates other than the choice
  (by `mean_utility`, highest first), then up to 3 others by `lower`, each with `certified` (= FEASIBLE) and `comparison`:
  FEASIBLE `"Chosen over {alt}: both cleared the bar; the choice has the higher mean utility over the same {n} futures ({u_c:.2f} vs {u_a:.2f})."`;
  not FEASIBLE `"{alt} is not certified ({verdict}, lower bound {l:.3f} < {thr:.2f}), so the gate will not dispatch it."`;
  for a HOLD choice every alternative uses the second form. `note` = `"Live sessions certify each new dispatch. Re-checks of
  groups already on the road are shown in the recorded demo."` The pending result comes from one adapter,
  `live_session.certification_of(session)`: `session.certification()` when that public method exists (Lane S adds it in
  P34B.8), else `session._gate_cache[1:]`; no other private Lane S attribute is read, and nothing is re-certified.
- `POST /sessions/{id}/decisions` (certified): ACCEPT; OVERRIDE with `selected_action` = a key from `allowed_override_actions`
  (certified alternatives and HOLD) and a non-empty `reason`; REJECT with a reason (committed as a HOLD certificate). It calls
  `session.decide` exactly like the Wave A path (so the audit row equals a direct call) and the session advances one step.
  Response adds `certificates` = the certificates this decision committed. **Uncertified override** (a key that is a
  certificate candidate but not FEASIBLE, or any key outside the mask): nothing is committed and the step does not advance;
  422 with `{"detail": ..., "flag": "UNCERTIFIED_OVERRIDE_REFUSED", "action_key", "verdict"}`, and a refusal row
  `{timestep, decision: "OVERRIDE", action_key, verdict, reason, flag, utc}` is appended to a per-session `refusals` list
  (API layer, in memory) — never to the Lane S audit.
- `GET /sessions/{id}/audit` adds `refusals`; `GET /sessions/{id}/certificates` → `{certificates}` (session ledger, oldest first);
  `POST /sessions/{id}/certificates/{cert_id}/replay` → real replay from `session.ledger.inputs(cert_id)`.
- WebSocket (`live_ws_message.schema.json`): after a decision `decision`, then one `certificate` per committed certificate,
  then the timeline `event`s, then `state`; a refusal pushes one `refusal`. `seq` strictly increasing per session.
- `context` and `decisions` are plain `def` endpoints (threadpool) holding the session lock, so certification (≈ 2–3 s) never
  blocks the event loop. Certified sessions count toward the 8-session LRU limit like any other.

**10.2 Web.** Live Operations gets a mode switch `Guided demo` / `Live session` (radiogroup named `Mode`). Live session:
`Seed` number input (default 620003), `World` select (the three worlds), `Start` button; then map, KPI tiles, suggestion card
with the three `why` reasons, an `Alternatives` list (`aria-label="Alternatives"`, each row: label, verdict word + shape,
lower bound, comparison text), Accept / Override (choose a certified alternative, `REASON …` input with `required`, submit
button `Confirm override`) / Reject (reason required),
a `role="status"` indicator `Certifying…` while context or decision requests run, the newly committed certificate id linking
to `/decisions?cert=…` (the Decisions page lists live-session certificates when `?session=` is set), the latest audit row,
and a `Step on` button that fetches the next context. Uncertified alternatives are listed (so the operator sees why they are
blocked) with `Override` disabled and the text `Not certified — the gate will not dispatch this`; a refused attempt (422)
shows `Refused: not certified` and the refusal row. Banner: `Live session · simulated hazards · demo parameters
v4-cert-test-v1 (not the evaluated configuration)`. No number appears unless the API sent it; no banned wording.

**10.3 Acceptance.** `tests/test_p34c_live_session.py` (milestone `P34C`): validation of the new request fields; certified
context parity with a direct `SimulationSession(certified=True)` twin (recommendation, schema, why from the pending result,
comparisons); ACCEPT, OVERRIDE and REJECT audit rows and certificates equal the twin's after the same decisions; uncertified
override refused, flagged, recorded, nothing committed; session certificates replay MATCH; WebSocket order; no banned wording.
Web: `p34c_live_session.spec.ts` in the `live` project. Out of scope: in-transit re-certification in live sessions,
persistence across restarts, multi-user sessions.

## Amendments
