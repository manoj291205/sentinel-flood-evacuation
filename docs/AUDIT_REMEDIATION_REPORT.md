# SENTINEL-AGENT — FULL INTEGRATION & STABILIZATION REPORT

Date: 2026-10-26. Private engineering report; no external publication authorized.

## Executive summary

Implemented the remediation across the simulator, planners, operational evidence boundary, provider tooling, API, React console, exports, tests and documentation. This was implementation work, not another read-only audit.

The integrated live path has been exercised against the real API: initialize the stochastic world, obtain a certified recommendation and its actual graph route, authorize the displayed decision, execute one transition, observe population changes, export the audit and replay the certificate with the same ordered path. The real browser test observed waiting fall from 337 to 317 and in-transit population rise from 0 to 20 for CERT-000002. The current engine clock and the reviewed decision clock are now distinguished.

Verification is substantial but not completely green. The second full Python run finished with **1,228 passed and one failed**. The remaining strict trace-reconstruction failure also reproduces on untouched starting main: five unrounded forecast values differ by approximately one or two floating-point units from the committed trace. Certificates, hashes, decisions and other fields agree exactly. The precise original numerical environment is not established. The strict test and the frozen trace were preserved rather than relaxed or regenerated.

The final frontend tests/build and real browser tests passed. Local authenticated release checks passed 9/9. Docker is unavailable, and remote CI is blocked before execution by account billing/spending restrictions. There were no provider evaluation requests, training runs, official experiment reruns, pushes or merges.

## Git branch, worktree and commits

- Starting remote main, verified before implementation: `52f2451846cefc320afdde2b9a1b48173118ae31`.
- Branch: `lane-x/m40-full-integration-hardening`.
- Isolated managed worktree: `/Users/aksharsinha/worktrees/sentinel-integration/sentinel-sprint`.
- Historical checkout preserved: `/Users/aksharsinha/Desktop/sentinel-sprint`, branch `v3-dynamic-stochastic`, HEAD `c7207204a45aad93eadeb8d590ac8b56b17441d8`.

Local engineering commits:

| Commit | Change |
|---|---|
| `89f3a32` | Planner masks, truthful outcomes, command binding and prospective accounting |
| `5abed36` | Operational evidence, approved-rule loader, provider durability and dense compatibility |
| `b34dcc9` | State-bound API, explicit lifecycle, authoritative routes and replay exports |
| `032ea0b` | React intent handling, modes, clocks, routes and browser regressions |
| `de630db` | Consistent event-feed order after reattachment |
| `64effa0` | Future provider implementation/schema identity and retained quota history |

The final documentation/environment commit contains this report and the checksum manifest. It is identified by HEAD after finalization. Cross-subsystem changes and explicit contract/test amendments follow the user's full-mission authorization. Nothing was pushed or merged.

## Corrected architecture

```text
Versioned synthetic scenario + cached OSM graph
  → stochastic observation, closures and transit outcomes
  → mechanical and modeled hard-safety checks
  → graph routing + planning/certification
  → authenticated approved T2 predicates, when genuinely available
  → API context: state version, recommendation identity, routes, rule status
  → React operator review
  → UUID-bound action/reason under the session lock
  → one revalidated simulator transition
  → truthful state/events + audit + pinned executed route
  → versioned JSON export and certificate replay
```

The live API does not perform a fresh retrieval or semantic provider call per decision. It authenticates evidence references and loads recorded rule approvals offline. The current catalog has zero mandatory T2 rules. Frozen retrieval/claim-support studies, recorded walkthroughs, fixtures and live sessions remain distinct.

## Operator decision integrity

Decision requests now require a UUID, expected state version and displayed recommendation identity. The identity includes the session, current state, recommendation and authoritative safety snapshot. The complete request also binds the action and reason.

Under the session lock, identical retries return the original cached status/body; UUID reuse with different content and stale state/recommendation identities are rejected before execution. Concurrent identical retries produce one audit entry. Concurrent distinct requests against one old state cannot both commit. Cached receipts remain retrievable after terminal state. V3 REJECT records without advancing time; certified V4 REJECT commits HOLD and advances.

Receipts are cached before WebSocket notifications. A disconnected observer cannot turn a committed decision into an uncached failure. Notification queues are bounded; slow consumers disconnect with a resynchronization signal. Explicit session closure disconnects observers and read/context operations recheck closure under the lock. Initial WebSocket state preparation no longer blocks the event loop on a thread lock.

Both React mutation callers send the required identity. Unknown transport outcomes retain the same UUID/body, stop fast-forward and require retry/review; stale responses refresh context without automatically submitting another action. Existing API acceptance callers were explicitly migrated, preserving simulator/certificate parity assertions and adding identity/evidence assertions.

## Planner and safety correctness

Lookahead-2, Lookahead-3 and MPC now intersect root candidates with the supplied authoritative mask and current modeled feasibility. Future states preserve fleet availability and safety-disabled behavior. A mask cannot grant a dispatch that violates the modeled current hazard threshold. Invalid modeled transitions are rejected. Empty-population utility no longer divides by zero.

Prospective identities are `lookahead-k2-v2`, `lookahead-k3-v2` and `sampled-mpc-n16-h3-v2`. Regressions cover disabled fleet, exhausted dispatch allowance, certification excluding every dispatch, partial masks, valid actions, projected feasibility, safety-disabled operation and custom thresholds. Forty-eight new engine regressions exist; the broader adjacent engine selection passed 294 tests, and the subsequent threshold selection passed 49.

The future command authorizer now checks group identity, the ordered candidate route, a FEASIBLE chosen row, people/destination, and trusted forecast/graph/ledger/edge-set input identities. It remains a software authorization boundary, not proof of physical actuator readiness. No historical Phase 10 results were changed.

## V4 simulation outcomes and event ordering

V4 distinguishes `ALL_EVACUATED`, `ALL_FAILED`, `MIXED_OUTCOME` and `HORIZON_REACHED`. An all-stranded outcome cannot say everyone arrived safely. API state, summary and terminal UI expose stranded, unsafe-arrival and overflow counts separately. Conservation invariants still include all V4 outcome categories.

Audit production order now follows the implemented causes: hazard/road/shelter updates, then transit outcomes, then walk-ins. Tests cover all-safe, failed, mixed and horizon outcomes. Stored historical logs were not regenerated. The React event feed also restores in the same newest-first display order used for incoming live events; the canonical backend timeline remains causal and append ordered.

## Approved-rule integration

`src/constraints/runtime_rules.py` authenticates approval/configuration identities, rule-file hashes, canonical evidence, semantic verdicts and supporting sentence spans before returning enforceable T2 rules. Changed parameters, hashes, source identities, invalid spans and malformed approval metadata do not become active constraints. A certified live session refuses an unauthenticated/stale catalog instead of silently dropping required rules.

Actual R01/R02 records remain **T1 advisory**. The API exposes the configured rules, enforced count, digest, source hashes, status and inactivity reason. React explicitly displays **zero enforced document rules**. Mandatory mechanical, modeled safety and certification checks still operate.

An ephemeral authorized fixture uses an existing predicate and demonstrates a POLICY failure through the actual session/gate rollout where the rule-free rollout succeeds. It is a synthetic integration authorization, not a newly invented or promoted real NDMA rule. Rule-free frozen evaluations remain unchanged.

## Geospatial and React route fidelity

The backend supplies ordered edge IDs, path identity/hash, graph fingerprint, timestep/state identity and SVG geometry. Pending certified routes come from certification inputs; executed and replayed routes come from saved ledger inputs. Transit geometry comes from the stored actual/migrated transit plan. Current road-closure geometry comes from current state, independently of a retained historical recommendation.

React uses these authoritative paths and preserves committed route marks across subsequent closures, reroutes and reattachment. It does not substitute a static shortest-distance route when authoritative geometry is missing. The audited Fort Kochi seed 620003 mismatch is reproduced by a regression that requires the displayed path to equal the engine path and differ from the old static shortcut.

The real browser acceptance checks graph edges, displayed SVG, selected action, executed path, waiting-population change, audit configuration identity and replay MATCH with the same route. Drive-time text now says “road travel estimate”; it does not present a sub-minute road estimate as the complete boarding/arrival time.

## Claim-support and evidence authenticity

Operational evidence is resolved only from the approved canonical corpus fingerprint and hash-validated PDF sources. Source/page/chunk mismatches and self-consistent invented chunks are rejected. Operational citation eligibility additionally requires SUPPORTED, source integrity and valid verbatim supporting spans.

The verdict-only `safe_to_cite` mapping is retained and documented as a frozen classification helper, not operational permission. Its historical metric semantics were not changed. The live audit reference authenticates a source; it is not presented as a fresh entailment result for every recommendation.

Phase 14B remains superseded and unscored. Phase 14C and Phase 14D remain distinct frozen evaluations. No partial 14B performance metrics were computed, no exhausted items were rerun and no frozen predictions/results were rewritten.

## API and React integration

Corrected LIVE ENGINE entry from a fresh page, the global mode header, hidden/legacy decision paths, sticky controls, decline/reject wording, committed-decision counts, migration subjects and migration IDs. Refusals and automatic reroutes no longer inflate human decision counts. Reattachment does not duplicate migration entries.

The global header, toolbar and overview prefer the actual engine timestep. The result bar explicitly labels the reviewed decision's earlier timestep. The map uses current closures while retaining the executed route. This distinction was found and corrected during manual browser review, after the initial automated browser pass.

Live, recorded and fixture sources are labeled. Recorded-mode acceptance tests now explicitly choose recorded mode. Matching browser acceptance specifications were updated with the executable tests; successful state, certificate and refusal assertions were retained.

## Audit, CSV and replay provenance

CSV serialization prefixes formula-leading strings, including mixed Unicode whitespace/control prefixes. Canonical audit/JSON reasons preserve the original text, including whitespace; validation still requires nonblank reasons where appropriate.

The `sentinel-session-v2` JSON export includes scenario and seeds, source commit, Python-source-tree hash and its scope, runtime/dependency versions, simulator/world/certification configuration and digest, graph identity, planner identity, active-rule provenance, canonical evidence references, human actions, events, certificates, serialized certificate inputs, recertification history and replay requirements. API exports also include state/session identity, refusals and idempotency receipts. Container builds can supply the source commit explicitly; missing identity is marked unavailable rather than invented.

Exported certificate inputs reconstruct independently and replay successfully against the matching graph/rules. This is certificate replay, not a claim of automatic durable restoration of an entire server session.

Sessions are bounded and in memory. Capacity refuses a new session rather than silently evicting another audit. Explicit DELETE releases a session. Request history refuses new intents at its bound while retaining previous receipts. Export before close/restart; use one server process. Database persistence and multi-worker deployment remain outside the demonstrated prototype.

## Provider and retrieval reliability

Future provider runs persist INTENT and ISSUING before transport invocation, atomically persist outcomes, fsync dispositions and bind committed rows by hash. Single-writer locks and request budgets protect continuation. Network ambiguity and successful responses lacking a committed disposition fail closed for reconciliation; they are not silently repeated. Known quota/server failures remain in the attempt history even after an explicitly invoked later success.

Tests use fake providers only, including actual runner interruption and hard subprocess exit after issuance/response. Non-finite provider data cannot corrupt durable JSON; normal parse handling remains intact. Future journals bind runner/provider source hashes, response-schema hash, request settings, model/protocol/prompt identity and runtime versions. A changed response schema cannot resume an existing future run. Archived 14B live CLI execution is disabled; its fake mode counts underlying calls rather than claim items.

Prospective dense indexes pin the locally verified MiniLM revision and validate model/revision/dimension/corpus compatibility. Missing historical revision metadata is rejected as unverifiable. No historical index was rebuilt and no missing old weight identity was invented.

## Scientific integrity

- Frozen Phase 10 still says **RL usefulness = NO**. No PPO retraining, reward changes or favorable reinterpretation occurred.
- Hybrid passed the registered comparison with Dense. **BM25 had the highest DirectHit@5**: 39/45, versus Hybrid 37/45 and Dense 28/45.
- Phase 13's perfect consistency statistic replays a deterministic judgment table. It is not independent annotation agreement. Frozen labels/results remain intact; README/course/legacy UI now explain the limitation.
- Phase 14C failed its gate. The separate Phase 14D passed its registered gate on construction-derived labels; this does not establish independent human-gold generalization.
- Phase 27 did not establish improved overall evacuation outcomes: the throughput guard was about 21.4%, below the registered 95% requirement.
- Synthetic hazards are not real flood observations. Cached OSM topology does not change that. Simulated HIL does not establish physical deployment readiness.
- PPO timeout bootstrapping/information asymmetry and MPC's stochastic approximation are documented limitations. Their historical experimental methods were not silently changed.

Future accounting explicitly opts into `action_accounting_version="executed-actions-v2"`, separating requested, blocked and executed dispatches/actions. The legacy Phase 10 accounting default and saved results remain preserved.

## Previous findings closure matrix

Statuses are scoped to this integration branch. “Verified” describes the stated software/reporting correction, not real-world disaster validation or newly established historical provenance.

| Finding | Status | Evidence / remaining limit |
|---|---|---|
| A01 Operator intent | RESOLVED AND VERIFIED | UUID/state/recommendation binding; retry, stale and concurrency tests |
| A02 Planner masks | RESOLVED AND VERIFIED | Authoritative-mask intersection, future feasibility and versioned planners |
| A03 Runtime rules | RESOLVED AND VERIFIED | Authenticated loader, stale-catalog refusal, actual zero T2, rule-sensitive fixture |
| A04 Consistency reporting | RESOLVED AND VERIFIED | Deterministic replay clarified; no independent annotation claimed |
| A05 Route fidelity | RESOLVED AND VERIFIED | Real edge/SVG/action/export/replay agreement in browser |
| A06 Terminal truth | RESOLVED AND VERIFIED | Safe/failed/mixed/horizon tests and outcome counters |
| A07 Event chronology | RESOLVED AND VERIFIED | Causal simulator records and consistent restored UI order |
| A08 Evidence trust | RESOLVED AND VERIFIED | Canonical membership and operational span/integrity checks |
| A09 CSV safety | RESOLVED AND VERIFIED | Formula/control/Unicode regressions; original JSON preserved |
| A10 Export/lifecycle | RESOLVED AND VERIFIED | Versioned replay package; explicit bounded in-memory lifecycle |
| A11 Provider issuance | RESOLVED AND VERIFIED | Preissue durable journal, hard-exit and fake-runner recovery tests |
| A12 Release verification | BLOCKED | CI billing, absent Docker, one pre-existing strict raw-float reconstruction failure |
| A13 Console consistency | RESOLVED AND VERIFIED | Modes, counts, migration identity, actual/reviewed clocks and current closures |
| A14 Dense provenance | PARTIALLY RESOLVED | Prospective guards verified; historical weight revision remains unverifiable |
| A15 Action accounting | RESOLVED AND VERIFIED | Explicit future executed-actions-v2; historical outputs untouched |
| A16 Command binding | RESOLVED AND VERIFIED | Group, ordered route, feasible choice and trusted-input tamper tests |
| A17 Maintenance/history | PARTIALLY RESOLVED | Current docs/UI corrected; protected historical helpers/checkpoints unchanged |
| F01 Issuance durability | RESOLVED AND VERIFIED | Future runners journal before issuance; ambiguous continuation stops |
| F02 Quota history | RESOLVED AND VERIFIED | 429/503 retained before later 200 in durable history |
| F03 Planner masks | RESOLVED AND VERIFIED | Disabled/exhausted/certification/partial-mask regressions |
| F04 Citation integrity | RESOLVED AND VERIFIED | Operational helper checks complete result and authenticated evidence |
| F05 Label consistency | RESOLVED AND VERIFIED | Reporting correction; frozen statistic preserved as historical output |
| F06 CI dependencies | PARTIALLY RESOLVED | Runtime dependencies/version aligned and locally verified; CI unexecuted |
| F07 Checkpoint validation | PARTIALLY RESOLVED | New journal identity/row hashes checked; old incomplete logs require reconciliation |
| F08 Evidence authenticity | RESOLVED AND VERIFIED | Operational canonical membership; generic historical fixtures are not authority |
| F09 Runtime/schema identity | PARTIALLY RESOLVED | New source/schema/runtime binding; historical missing provenance cannot be recreated |
| F10 14B stability accounting | NOT APPLICABLE | Superseded historical study not resumed; 14D is a separate protocol |
| F11 CSV formulas | RESOLVED AND VERIFIED | Boundary escaping with original canonical reason preservation |
| F12 Session provenance | RESOLVED AND VERIFIED | Configuration/source/runtime/evidence/certificate inputs exported |
| F13 PPO bootstrap | STILL PRESENT | Frozen design limitation disclosed; no training or unsupported numerical claim |
| F14 MPC approximation | STILL PRESENT | Approximation disclosed; no silent replacement of frozen stochastic design |
| F15 Requested/executed | RESOLVED AND VERIFIED | Prospective versioned counters and invalid-action fixtures |
| F16 Dense model identity | PARTIALLY RESOLVED | New mismatch checks; old weight identity not invented |
| F17 Original labeling traces | BLOCKED | Independent historical annotation provenance unavailable; no replacement fabricated |
| F18 Staging risks | PARTIALLY RESOLVED | New runtime/journal/environment ignores; protected old checkout remains unchanged |
| F19 Architecture claims | RESOLVED AND VERIFIED | Actual offline/live trust boundaries documented |
| F20 Status/counts | RESOLVED AND VERIFIED | Duplicate stale table removed; old counts identified as historical; legacy 14B corrected |
| F21 Old recovery helper | NOT APPLICABLE | Historical-only helper preserved; superseded live CLI disabled in current branch |

## Tests and exact commands

Commands below were run from the integration worktree unless noted. Selections overlap; counts must not be added together.

| Verification | Observed result |
|---|---|
| First full Python run | 1,177 passed, 12 failed; defects/test-fixture issues investigated, loopback permission failures rerun safely |
| Second full Python run | **1,228 passed, 1 failed**, 755.55 seconds |
| Python 3.12 integration selection | **85 passed**, 378.33 seconds; later provider additions checked separately below |
| Final provider identity/hygiene selection | **18 passed**, fake providers only |
| Adjacent engine selection | **294 passed**; subsequent threshold selection **49 passed** |
| Existing RAG/corpus selection | **70 passed** |
| Independent API review | **14 passed** |
| Final Vitest | **42 passed**, 14 test files; serial workers, unchanged timeouts |
| TypeScript and production build | **PASS** |
| Fixture Playwright suite | **38 passed, 2 intentional skips** |
| Full real API Playwright suite | **11 passed** |
| Final real route/clock/closures/export check | **1 passed** |
| Authenticated local release checker | **9/9 passed** |
| Frozen checksums | **333/333 unchanged** |

Full Python command (with loopback permission; external sockets and protected writes still blocked):

```bash
PYTHONDONTWRITEBYTECODE=1 \
HYPOTHESIS_STORAGE_DIRECTORY=/private/tmp/sentinel-remediation-verification/hypothesis \
PYTHONPATH="$PWD/scripts/verification:$PWD" \
SENTINEL_PROTECT_WORKTREE=/Users/aksharsinha/Desktop/sentinel-sprint \
.venv/bin/python -m pytest tests/ -p no:cacheprovider -o addopts='' -q \
  --basetemp=/private/tmp/sentinel-remediation-verification/pytest-full-2
```

The full compatibility suite used Python 3.11 and read-only reuse of existing heavy ML packages, with API/test additions isolated in the new worktree. Separately, an independent Python 3.12 environment installed the declared runtime/API requirements, ran API/integration tests and served the release check. A standalone project-local `.venv-runtime`/`.runtime` now supports launching the application without the historical checkout or temporary interpreter paths.

The integration process collected 85 cases before the final three provider schema/quota cases were added. Those additions passed in the separate final 18-case provider/hygiene run. The full-suite count is its recorded run, not a claim that every later test addition was included in that process. Final changes were checked by the corresponding focused selections; overlapping counts are not summed.

Final integration selection:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/scripts/verification:$PWD" \
SENTINEL_PROTECT_WORKTREE=/Users/aksharsinha/Desktop/sentinel-sprint \
/private/tmp/sentinel-remediation-verification/runtime312/bin/python -m pytest \
  tests/test_lx_decision_integrity.py tests/test_lx_decision_review.py \
  tests/test_lx_export_integrity.py tests/test_lx_live_route_state.py \
  tests/test_lx_route_fidelity.py tests/test_lx_runtime_evidence.py \
  tests/test_lx_dense_identity.py tests/test_lx_provider_journal.py \
  tests/test_lx_verification_guard.py tests/test_p30_api.py \
  tests/test_p34c_live_session.py tests/test_lx_p34c_session.py \
  -p no:cacheprovider -o addopts='' -q \
  --basetemp=/private/tmp/sentinel-remediation-verification/pytest-final-delta
```

Frontend commands, from `web/`, used the available Node 22 binary:

```bash
export PATH="/Users/aksharsinha/.nvm/versions/node/v22.22.3/bin:$PATH"
npm ci
npm run test -- --maxWorkers=1 --no-file-parallelism
npm run build
npm run test:e2e
SENTINEL_PYTHON=/private/tmp/sentinel-remediation-verification/runtime312/bin/python \
SENTINEL_API_PORT=8100 \
PYTHONPATH="$PWD/../scripts/verification:$PWD/.." npm run test:e2e:live
```

Final provider/hygiene command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/scripts/verification:$PWD" .venv/bin/python -m pytest tests/test_lx_provider_journal.py tests/test_repo_hygiene.py -p no:cacheprovider -o addopts='' -q` — 18 passed in 8.55 seconds.

The real suite used port 8100 because an unrelated service already occupies 8000; that service was not stopped. Browser fixtures were made action-aware rather than used as substitutes for real execution. Two overlapping diagnostic frontend runs experienced resource timeouts; the final serial run passed without increasing test timeouts.

The strict remaining test is `tests/test_p34a_wiring.py::test_trace_rebuilds_byte_identically_and_validates`. Example: reconstructed `0.5385857466871293` versus stored `0.5385857466871294`. Independent comparison against untouched main found the same five differences. No assertion was weakened and no tolerance was substituted for its byte-equality requirement. The encoding-hygiene checker was corrected to recognize binary `os.open` descriptors, with positive/negative checker tests; text-stream encoding requirements remain enforced.

## Browser and Docker verification

Playwright verified actual API behavior, not recorded/mock substitution. Manual browser review additionally exercised live start, HOLD, STEP ON, a 20-person ACCEPT dispatch and session reattachment. It exposed the initial-mode and stale-clock/closure issues that were then corrected and regression tested.

A real-dispatch screenshot is available in the ignored browser output: `web/test-results/p34c_live_session-live-eng-71032-ate-replay-and-audit-export-live/live-dispatch.png`. It shows engine step 2, reviewed decision step 1, CERT-000002, waiting 317, in transit 20, two decisions and zero mandatory document rules.

The password-protected standalone release instance passed health, authentication, built index, recorded start/walk, certificates, replay match, tamper detection and evidence checks. The checker was run after health readiness. Temporary verification servers were stopped, with the synthetic manual audit exported first.

Docker build/run: **NOT EXECUTED — Docker is not installed**. The Dockerfile now includes canonical PDFs and required offline authentication dependencies, and accepts a source-commit build argument. Local runtime verification does not substitute for a container test.

## CI and external blockers

Read-only inspection of run `39157210783`, head `52f2451846cefc320afdde2b9a1b48173118ae31`, confirmed four jobs failed before any steps ran and the live job was skipped. GitHub's annotation says recent payments failed or the spending limit needs increasing. This is not a Python failure. No billing settings, money or workflow reruns were authorized or performed.

CI now reads `.python-version` (3.12), includes API/runtime dependencies and runs Python tests with the opt-in offline/protected-artifact guard. Remote execution, Windows locking and the container remain unverified. Run link: https://github.com/iamnoob96/sentinel-sprint/actions/runs/39157210783

## Files changed

The changes are confined to this branch. Major groups:

- Engine: `src/planners/{model,lookahead,mpc}.py`, `src/sim/{state,transition,invariants,stochastic}.py`, `src/actuation/commands.py`, `scripts/run_phase10.py`.
- Evidence/tooling: `src/constraints/{claim_support,evidence,runtime_rules,provider_journal}.py`, `src/rag/{ingest,retrieve}.py`, `scripts/phase14{b,c,d}_run_claim_support.py`.
- Integration: `src/api/{app,dto,sessions,live_session}.py`, `src/presentation/map_geometry.py`, `src/simulation_session.py`, `src/human_decision.py`.
- React: shared session store and request identity helper; Live Operations/CommandCentre/LiveSession/DecisionModal/OperationsMap; App/Overview/Decisions; fixtures, unit tests, browser tests and configurable local API routing.
- Explicit contract amendments: `specs/V4_API_SPEC.md`, `specs/contracts/live_context.schema.json`, matching browser acceptance specifications.
- Regression tests: new `tests/test_lx_*` behavior tests plus migrated API/corpus/encoding/legacy presentation fixtures. Simulator/certificate parity and negative assertions were preserved.
- Environment/reporting: `.python-version`, `.github/workflows/ci.yml`, `.gitignore`, `requirements-runtime.txt`, `Dockerfile`, README, hosting/course/architecture documentation, legacy dashboard and its presentation test, verification guard, lane ledger and this report/checksum manifest.

Exact file inventory is available with `git diff --name-only 52f2451846cefc320afdde2b9a1b48173118ae31 HEAD`. No `data/` or `models/` file was changed or generated.

## Protected artifact checksums

The before-implementation manifest covers 333 files under `data/eval_v3`, `data/eval_results`, `data/eval_v4`, `models`, `data/geospatial_v3`, `data/geospatial_v4` and `data/demo_v4`. Every hash matches after verification. The saved manifest is `docs/audit-remediation/protected-artifacts.sha256`.

Manifest SHA-256: `e6c3f21efef0b012aa2486a603ca1795fa13323970617c1f3a1df9cf27d62c73`.

```bash
shasum -a 256 -c docs/audit-remediation/protected-artifacts.sha256
```

The historical checkout's 296 recorded non-environment files, HEAD and exact Git status also match the initial snapshot. Its uncommitted scientific checkpoint files remain intact. Git metadata gained the authorized fetch, new worktree and local branch/commits; no historical source branch was switched/reset/cleaned/stashed. Training: no. Gemini/Groq evaluation requests: no. Frozen experimental reruns: no. Merge/rebase/push: no.

## Remaining defects

1. **Strict raw-float trace reconstruction remains failing on this machine.** It predates these changes. Preserve the frozen trace/test, establish its original numerical environment or separately approve a portable comparison protocol before calling the release fully reproduced. Certificates and executed decisions currently agree exactly.
2. **Remote CI and Docker verification remain blocked.** Local success is not a claim that those checks passed.
3. **Session persistence remains intentionally in memory.** Export-before-close and single-worker limitations are explicit; this is not an operational multi-user deployment.
4. **Historical embedding/annotation/runtime provenance cannot be retroactively manufactured.** New guards prevent pretending those identities are known.
5. **Research/model limitations remain:** construction-derived labels, no independent gold reliability, synthetic dynamics, frozen PPO bootstrap interpretation, approximate MPC and unverified physical hardware.

No further provider requests, benchmark changes, retraining or frozen-artifact edits are justified to make those limitations disappear.

The strict-test evidence and three independent checks are recorded for review in `docs/patent-roadmap/escalations/LX-P40-1.md`. No push or automatic handoff was performed.

## Final university demonstration readiness

**Ready for a supervised research demonstration and technical review with these limitations stated. Not ready for an unconditional fully reproduced release or real emergency deployment claim.**

The defensible demonstration now includes a real stochastic state, mandatory modeled checks, actual road paths, honest rule status, state-bound human control, truthful population/outcome reporting and auditable certificate replay. The strongest research story retains the negative PPO finding, BM25 comparison, claim-support limits and failed throughput guard.

Before final submission, resolve/record the strict reconstruction issue and obtain a real CI/container run. Do not describe zero mandatory NDMA rules as active NDMA policy enforcement, or simulated HIL as tested physical deployment.

## Exact commands to launch the integrated application

The project-local standalone runtime and production web build are prepared in this worktree:

```bash
cd /Users/aksharsinha/worktrees/sentinel-integration/sentinel-sprint
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/scripts/verification:$PWD" \
SENTINEL_WEB_DIST="$PWD/web/dist" \
.venv-runtime/bin/python -m uvicorn src.api.app:create_app \
  --factory --host 127.0.0.1 --port 8101
```

Open `http://127.0.0.1:8101/live`. One server worker; no keys are needed. The optional verification guard blocks external requests and protected writes. Port 8101 avoids the existing unrelated service on 8000. These temporary verification servers are not left running by this task.

To rebuild the frontend after edits:

```bash
cd /Users/aksharsinha/worktrees/sentinel-integration/sentinel-sprint/web
export PATH="/Users/aksharsinha/.nvm/versions/node/v22.22.3/bin:$PATH"
npm run build
```

For a future container check, once Docker exists, use `docker build --build-arg SENTINEL_SOURCE_COMMIT="$(git rev-parse HEAD)" -t sentinel-demo .`; this command was not executed here.

## Five-minute live demonstration procedure

1. **Minute 1:** Open LIVE ENGINE. Select Medium and seed 620003. State clearly that topology is real, hazards/people/capacities are simulated, and `v4-cert-test-v1` is the fast demonstration configuration.
2. **Minute 2:** Start. Show zero enforced document rules and explain why advisory T1 is not mandatory T2. Inspect the initial HOLD and uncertified alternatives; ACCEPT the HOLD.
3. **Minute 3:** STEP ON. Review the next certified 20-person route and its road travel estimate. ACCEPT. Show waiting 337→317, in transit 0→20, engine step 2 versus reviewed step 1 and the committed route.
4. **Minute 4:** Open Decisions & Certificates for the live certificate. Replay to MATCH, then demonstrate tamper detection. Explain that replay checks stored computation, not real-world flood truth. A reasoned override/decline can be shown as time permits.
5. **Minute 5:** Download JSON/CSV before ending the session. Point to source/configuration/evidence/graph identities and the frozen-results limitations: PPO NO, BM25 highest hit, deterministic annotation replay, 14D construction labels and Phase 27 throughput failure.

## Local commits and Git status

All implementation commits are local on `lane-x/m40-full-integration-hardening`; final reporting/environment changes are included in the final local HEAD. No push, merge, rebase, reset, stash or clean was performed. The historical worktree is preserved. The branch is prepared for review, with the known strict-test and external verification blockers recorded rather than hidden.

## Final verdict

**PARTIALLY COMPLETE WITH DOCUMENTED BLOCKERS**

The feasible engineering corrections are implemented and extensively verified. Full verification remains blocked by the strict pre-existing reconstruction discrepancy, unavailable Docker and billing-blocked CI. No results or tests were falsified to claim otherwise.
