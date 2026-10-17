# V4_RELEASE_SPEC — Phase 34B: release (CI, dev scripts, demo script, hosting, POLICY count)

Lane S · branch `m34b-release` (from `main`) · acceptance `tests/test_p34b_release.py` · contracts `deploy_check.json`,
`claims_policy.json`, `certificate.schema.json` (`POLICY`), `demo_step.schema.json`, `evidence.schema.json`.
34B touches CI, scripts, docs and one Lane S module; the web app and the API (`src/api/**`, `web/**`) belong to Lane X
(34A). Nothing here imports unmerged 34A code: every check of the running app goes through the HTTP contract in
`deploy_check.json`, and the acceptance test drives it against a stub server.
**Confidential until P0 is filed:** any deployment is private or password-protected; a public link only after the user
confirms in chat that P0 is filed (recorded in the STATUS decision log). **D-27:** no outcome-effect claim in any text.

## 1. Files (Lane S; add the new paths to LANES.md — done by Lead with this spec)
New: `scripts/dev.ps1`, `scripts/dev.sh`, `scripts/deploy_check.py`, `Dockerfile`, `.dockerignore`, `requirements-runtime.txt`,
`docs/HOSTING.md`, `DEMO_SCRIPT_V4.md`, `tests/test_s_p34b_*.py`. Modified: `.github/workflows/ci.yml`, `README.md`
(new section only), `simulation_demo.py` and `review_dashboard.py` (legacy label only), `src/certify/certificate.py`
(POLICY, §2), `src/simulation_session.py` (`certification()`, §2a), `tests/test_s_p15p_gate.py` (its POLICY assertion, §2). Do not touch `src/api/**`, `web/**`, `docs/course/**`.

## 2. POLICY count in certificates (Wave B audit follow-up)
`build_certificate` drops `POLICY` from each candidate's `outcome_counts` (`if k != "POLICY"`), so `n` minus the sum is the
only way to recover rule-blocked futures. New rule: **keep `POLICY` (also when 0) exactly when `params.params_id`
contains `"+rules-"`** (document rules were active); otherwise omit it as today, so every certificate made without rules
— the Phase 25 fixture hashes, the replay batch, the 34A demo trace — stays byte-identical.
```text
rules_active = "+rules-" in params.params_id
counts = {k: int(v) for k, v in cc.outcome_counts.items() if k != "POLICY"}
if rules_active: counts["POLICY"] = int(cc.outcome_counts.get("POLICY", 0))
```
The HOLD row keeps `{}`. `replay_certificate` rebuilds through `build_certificate`, so replay needs no change. Update the
last assertion of `tests/test_s_p15p_gate.py::test_tampered_chunk_blocks_dispatch_and_is_audited` (your own test) to the
new rule: every non-HOLD candidate has `POLICY` and its counts sum to `n`.

## 2a. `SimulationSession.certification()` (for Phase 34C, Lane X)
Add a public read-only method to `src/simulation_session.py`: `certification() -> tuple[CertificationResult, CertificateInputs] | None`
— `None` when not certified or the episode is terminal; otherwise the pending result for the current step from the same
cache `context()` uses (compute it through the same path if the cache is empty or stale). Calling it never commits, never
re-certifies a step already evaluated, and returns the identical objects on repeated calls. 34C reads it through its own
adapter (falling back to the cache until this lands), so 34C does not wait for 34B.

## 3. CI (`.github/workflows/ci.yml`)
Keep the `test` job unchanged. Add:
- `web` (ubuntu-latest): `actions/setup-node@v4` with Node 20 and npm cache on `web/package-lock.json`; in `web/`:
  `npm ci`, `npx tsc --noEmit`, `npm run test`, `npx playwright install --with-deps chrome`, `npm run test:e2e`.
- `web-live` (ubuntu-latest, `needs: web`, runs only `if: hashFiles('web/e2e/p34a_live_demo.spec.ts') != ''`): Python 3.12
  + CPU torch step as in `test` + `requirements.txt` + `requirements-api.txt`, Node as above, then `npm run test:e2e:live`.
- `docker` (ubuntu-latest, runs only `if: hashFiles('data/demo_v4/demo_trace.json') != ''`): `docker build -t sentinel-demo .`,
  `docker run -d -p 8000:8000 -e SENTINEL_DEMO_PASSWORD=ci-only-password sentinel-demo`, wait for `/api/health` (≤ 60 s),
  `python scripts/deploy_check.py http://127.0.0.1:8000 --password ci-only-password`.
The script names `test:e2e` / `test:e2e:live` are fixed by `V4_WIRING_SPEC.md` §7. No secrets in any job.

## 4. Dev scripts
`scripts/dev.ps1` (Windows) and `scripts/dev.sh` (bash): check `.venv` and Node ≥ 20 (clear message otherwise), run
`npm ci` in `web/` if `web/node_modules` is missing, then start the API
(`.venv/Scripts/python -m uvicorn src.api.app:create_app --factory --port 8000 --reload`; `.venv/bin/python` on bash)
and the console (`npm run dev` in `web/`, port 5173); print both URLs; stop both on Ctrl+C. `-Mock` / `--mock` starts
only the console with `VITE_API_MOCK=1`. They never set `SENTINEL_DEMO_PASSWORD` or any key.

## 5. Hosting
- `requirements-runtime.txt`: exact pins (copied from `requirements.txt`) of what the API imports — `numpy`, `scipy`,
  `networkx`, `jsonschema` (Lead checked 2026-10-17: importing `src.api.app` and the certify/constraints modules loads
  no torch, sentence-transformers, streamlit, google-genai, chromadb, gymnasium or stable-baselines3). Verify with a
  clean venv: `pip install -r requirements-runtime.txt -r requirements-api.txt` then `python -c "import src.api.app"`.
- `Dockerfile`, two stages: `FROM node:20-bookworm-slim AS web` — copy `web/package*.json`, `npm ci`, copy `web/` and
  `specs/contracts/` (the mock handlers import contract files), `npm run build`; then `FROM python:3.12-slim` — install
  `requirements-runtime.txt` + `requirements-api.txt`, copy `src/`, `specs/contracts/`, `specs/approvals/`, `data/`
  (only what the API reads: `data/geospatial_v3/`, `data/eval_results/`, `data/eval_v3/phase10/`,
  `data/eval_v3/phase13/`, `data/constraints_v4/`, `data/demo_v4/`), and the built `web/dist` from stage 1; `ENV
  SENTINEL_WEB_DIST=/app/web/dist SENTINEL_DEMO_SOURCE=RECORDED`; `EXPOSE 8000`; non-root user; `CMD ["python", "-m",
  "uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]` (a `PORT` env override for
  hosts that assign one is fine). Never `ENV`/`ARG` a password or key. `.dockerignore`: `.git`, `.venv`, `.env*`,
  `web/node_modules`, `web/dist`, `models/`, `src/rag/chroma_db/`, `**/__pycache__`, `.claude/`.
- `docs/HOSTING.md`: (1) local `docker build` / `docker run -e SENTINEL_DEMO_PASSWORD=…`; (2) step by step for **one**
  free host (Render web service from the Dockerfile, or a Hugging Face Docker Space — pick one, say why), setting
  `SENTINEL_DEMO_PASSWORD` as a secret in the host's dashboard; (3) the alternative: static `web/dist` on a static host +
  the API container; (4) `python scripts/deploy_check.py <url> --password …` after every deploy; (5) the disclosure rule
  verbatim: "Until P0 is filed the deployment must be private or password-protected (SENTINEL_DEMO_PASSWORD); a public
  link is switched on only after the user confirms P0 is filed." The hosted demo needs no API key and calls no model.
- `scripts/deploy_check.py <base_url> [--password P] [--json PATH] [--timeout S]`: the checks of `deploy_check.json`
  in order, stdlib only (`urllib`), schema validation with `jsonschema` against `specs/contracts/*`; password also from
  `SENTINEL_DEMO_PASSWORD`; never prints it. `main(argv) -> int` importable for tests.

## 6. Docs
- `DEMO_SCRIPT_V4.md`: a 5-minute judge walkthrough built around **Run demo**: sections headed `## m:ss–m:ss <title>`
  covering all five pages (Overview, Live Operations, Decisions & Certificates, Evidence & Results, System & Hardware)
  and a **Live session** segment (start seed 620003 on `v4-medium-dt2-v1`, show the HOLD with uncertified alternatives,
  Accept, Step on, Override with a reason, the new certificate and audit row; say an override to an uncertified action is
  refused and recorded), the last ending at or before `5:00`; what to click and what to say. It must say the demo is a recorded run of the real
  engine with the fast parameter set (not the evaluated configuration), that the hazards are simulated, and that the
  pre-registered evaluation makes **no outcome-effect claim** (Bar 1 failed; R = 21.4 % is the number to quote with any
  failure rate). A first line `Confidential until P0 is filed — do not show outside the project.` Every number must come
  from the Evidence page or a frozen result file — quote none you have not read there. No banned pattern of `claims_policy.json`.
- `README.md`: new section `## V4 web console` (dev scripts, mock mode, Docker, link to `docs/HOSTING.md` and
  `DEMO_SCRIPT_V4.md`); the V3 Streamlit sections get the heading suffix ` (legacy)`.
- `simulation_demo.py`, `review_dashboard.py`: first rendered element `st.warning(LEGACY_NOTE)` with
  `LEGACY_NOTE = "Legacy V3 dashboard — the V4 web console (web/) replaces it."` No other behaviour change.

## 7. Acceptance (`tests/test_p34b_release.py`, milestone `P34B`) and manual checks
POLICY rule (with rules → present and sums to `n`; without → absent; fixture hashes unchanged); `deploy_check.main`
passes against a conforming stub server, fails `replay-tamper` against one that always answers MATCH, fails
`auth-required` when the server is open but a password is given, and never prints the password; Dockerfile / `.dockerignore`
/ runtime requirements / CI / dev scripts / HOSTING / README / legacy label / DEMO_SCRIPT_V4 content rules above.
Manual at the Lead review: clean-clone Windows run from README in ≤ 10 minutes; `docker build` + `docker run` serves the
demo locally and `deploy_check.py` passes; all CI jobs green after both lanes merge.
Runner may: write the stub-server fixture data, README/HOSTING tables, run tests. Out of scope: deploying anywhere,
any public link, any change to the API or console.

## Amendments
- 2026-10-17 (Lead): Phase 34C added — §2a `SimulationSession.certification()` and a Live session segment in `DEMO_SCRIPT_V4.md`.
