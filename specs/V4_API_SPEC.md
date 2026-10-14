# V4_API_SPEC — Phase 30: FastAPI service layer

Lane X · branch `lane-x/m30-api` · tests `tests/test_p30_api.py` · contracts `specs/contracts/`

## Goal
A local HTTP + WebSocket API over the **existing** `SimulationSession` (real planner, real mask, real
human-decision audit), plus demo / certificate / "why" endpoints that in Wave A are served from frozen
contract fixtures and in Wave C (34A) from the real Phase 25/26 gate. The web console (31–33) talks
only to this API.

## Files (Lane X)
`src/api/__init__.py`, `src/api/app.py` (`create_app()`), `src/api/sessions.py` (`SessionRegistry`),
`src/api/dto.py` (Pydantic v2 models), `src/api/routes_*.py`, `src/api/fixtures.py`,
`src/presentation/artifacts.py` (frozen-result loaders), `src/presentation/map_geometry.py`,
`requirements-api.txt` (`fastapi`, `uvicorn[standard]`), `tests/test_lx_*.py` (your unit tests).
Run: `python -m uvicorn src.api.app:create_app --factory --port 8000`.

## Rules
- Import Lane S code, never modify it. `SimulationSession` methods are the source of truth:
  `state`, `context()`, `decide(...)`, `summary()`, `export_csv()`, `export_json()`, `route_rows()`,
  `timeline`. DTOs are built from existing `to_dict()` outputs — do not re-implement simulation logic.
- `SessionRegistry`: in-memory dict `session_id (uuid4 hex) -> SimulationSession`, max 8 sessions,
  LRU eviction, a `threading.Lock` per session (decisions are serialized).
- Every response carries `"simulated": true` and `"honesty": "REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED"`.
- Fixture-backed responses carry `"source": "FIXTURE"`; real ones `"source": "LIVE"`. The UI shows
  "scripted preview" for FIXTURE.
- No secrets, no outbound network, CORS only for `http://localhost:5173`.

## Endpoints (v1, prefix `/api`)
| Method | Path | Body → Response | Backed by |
|---|---|---|---|
| GET | `/health` | → `{status:"ok", version, graph_fingerprint}` | live |
| POST | `/sessions` | `{seed=620000, regime="v3-medium-v1"}` → `SessionDTO` | live |
| GET | `/sessions/{id}/state` | → `StateDTO` (`state.to_policy_observation()` + `summary()` + `route_rows()`) | live |
| GET | `/sessions/{id}/context` | → `ContextDTO` (recommendation action + label, `snapshot.to_dict()`, allowed override actions) | live |
| POST | `/sessions/{id}/decisions` | `{decision: ACCEPT|OVERRIDE|REJECT, selected_action?, reason, evidence:{source_id,page,chunk_id}}` → `{audit_record, state: StateDTO}`; 422 on `HumanDecisionError` | live |
| GET | `/sessions/{id}/audit` · `/audit.csv` · `/audit.json` · `/timeline` | exports | live |
| GET | `/map/geometry` | → projected SVG geometry (same shape as `docs/design/sentinel-console/fort_kochi_map_geometry.json`) | live, computed from the loaded graph |
| POST | `/demo/start` · `/demo/step` `{action: next|prev|reset}` · GET `/demo/state` | → `DemoStateDTO` (validates `demo_step.schema.json`) | FIXTURE (`demo_steps.json`) until 34A |
| GET | `/certificates` · `/certificates/{cert_id}` | → list / `certificate.schema.json` | FIXTURE (`certificates_fixture.json`) until 34A |
| POST | `/certificates/{cert_id}/replay` | `{tamper: bool=false}` → `{result: MATCH|MISMATCH, mismatched_fields: [...]}` | FIXTURE: MATCH unless tamper (then MISMATCH on `forecast_hash`) |
| GET | `/decisions/{decision_id}/why` | → `decision_why.schema.json` | FIXTURE until 34A |
| WS | `/ws/sessions/{id}` | server → `{seq, type: "state"|"event"|"decision", payload}` | live |

WebSocket: `seq` strictly increasing per session from 1; on connect send one `state`; after each
decision send `decision`, then each new timeline `event` in ledger order, then `state`.

## DTO notes
`ContextDTO.recommendation = {action_key, label, planner_id}` with `action_key = src.human_decision.action_key(action)`
(e.g. `"Z4->S3"`) and `label = action_label(action)`. Path parameters are named `session_id`, `cert_id`,
`decision_id`. `GET /health` also returns `simulated` and `honesty` like every other response.
`SessionDTO {session_id, scenario_id, seed, regime, timestep, horizon_steps, timestep_minutes, graph_version, graph_fingerprint}`.
`StateDTO` adds KPI block `{waiting, in_transit, safe, certificates_issued}` (`certificates_issued` = 0 live
until 34A). `DemoStateDTO {source, step_index, step_count, step}` where `step` is one element of
`demo_steps.json`.

## Acceptance (tests/test_p30_api.py, uses `fastapi.testclient`)
Health; create session → state timestep 0 for seed 620000; context recommendation equals
`SimulationSession.context().recommendation` (parity); ACCEPT decision → audit row identical to
calling `SimulationSession.decide` directly on a twin session (API-vs-direct parity); REJECT without
reason → 422; demo start/next/prev/reset walk all steps and every payload validates the schema;
certificate replay MATCH / tamper MISMATCH; why endpoint validates; WS sequence strictly increasing and
first message is `state`; OpenAPI document lists every path above.
