# SENTINEL-AGENT — FINAL VERIFICATION AND RELEASE SIGN-OFF

Date: 2026-10-26. Private engineering record. This final-verification section supersedes the older counts and numerical hypothesis in the archived integration report below.

**Verdict: READY FOR REVIEW, VERIFICATION GAPS REMAIN.** Private review is appropriate; unconditional merge sign-off is withheld. A supervised university demonstration is supported by actual API/browser evidence, with the stated limitations.

## Starting and final Git state

The mission started clean at `498fcc5`, on `lane-x/m40-full-integration-hardening`, in `/Users/aksharsinha/worktrees/sentinel-integration/sentinel-sprint`. Git confirmed exactly seven local commits and 88 changed files from original main `52f2451846cefc320afdde2b9a1b48173118ae31`. Those seven commits were retained without amendment.

New local correction commits:

| Commit | Purpose |
|---|---|
| `b9ec1b1` | Atomic decision receipts, full live certificate input binding, planner provenance, ordered WebSocket attachment and backend/engine regressions |
| `9426db1` | Actual committed-action display, client reconciliation and serialized session lifecycle, real browser contract regression |
| `71c2746` | Strict trace forensics and separate versioned portability diagnostic |

The final documentation commit follows `71c2746`; its exact identity is reported in the final chat and `git log -1`. No source changes follow the verified correction commits. `git ls-remote origin refs/heads/main` still reports the original `52f2451` baseline. No upstream divergence requiring a merge was found. No merge, rebase, push, branch switch or historical-checkout reset was performed during this verification mission.

## Strict trace root cause and classification

**The original strict test still FAILS under the default runtime.** Neither the test nor the frozen trace was changed. The failure also reproduces against untouched starting-main source.

The five differing values are all raw severity floats under `inputs/CERT-000007/forecast` at step 5: zone Z2 and shelters S1, S2, S4, S5. Every value differs by exactly one binary64 ULP. Certificates, certificate hashes, decisions, routes, timings, ledgers and all other trace fields agree exactly. Differences exist before JSON encoding; JSON round-trips preserve them.

The RNG on this path is keyed SHA-256 with Box–Muller standard-library math, not NumPy RNG. The causal path is `EpisodeRandomStreams.normal` → `math.cos` → regional AR(1) hazard → observable forecast. For the regional timestep-3 angle `0x1.e44d077d985b7p-1`, native cosine returns `0x1.2b86d4616a392p-1`; independent 100- and 180-digit reference calculations return `0x1.2b86d4616a393p-1`.

Replacing only that cosine in a diagnostic process reconstructs the ENTIRE stored trace exactly, with zero differing fields. A generic process-only reference-cosine override also passes the **original unmodified strict pytest test: 1 passed in 12.35 seconds**. Replacing log or sqrt alone does not remove the five mismatches. No production override, coefficient adjustment, timestep special case, new RNG dependency or test tolerance was shipped.

The same native cosine is observed on available Python 3.11.3, 3.12.15 and 3.13.5. Full reconstruction was compared on Python 3.11/NumPy 2.4.6 and Python 3.12/NumPy 2.5.4/SciPy 1.18.1, including untouched main. The original trace commit `d99ea4d` identifies Python 3.11 but does not pin its microversion, C library, compiler or platform. Later runtime requirements cannot establish that missing producer identity.

Classification: **B (numerical environment compatibility) is supported by isolated causal reproduction; D (missing exact historical environment) remains relevant.** No integration algorithm regression (A) was found on this trace; JSON serialization (C) is ruled out. This does not prove the original producer used our reference routine or any particular operating system. CPython documents the platform C-library relationship in https://docs.python.org/3.12/library/math.html.

See `docs/TRACE_REPRODUCIBILITY_V1.md` and `docs/audit-remediation/trace-forensics.json` for all five hex pairs, source identities and environment observations.

### Separate portability contract

`sentinel-trace-portability-v1` is an explicit diagnostic, not a replacement acceptance test. It reports `strict_equal=false`, `hash_equivalent=true` and every differing path on this machine. It permits comparison normalization only for raw zone/shelter forecast severity arrays whose **existing registered forecast hash is identical**. That hash already uses nine decimal places; no new epsilon was invented. Every other field, including all certificates and v2 complete-input digests, remains exact. Semantic/configuration/route/hash changes are rejected by focused tests. This diagnostic is not used by operational authorization and validates only the recorded trajectory.

## Additional confirmed defects and corrections

| Issue found independently | Correction and evidence |
|---|---|
| A post-transition observation/response exception could leave an advanced world with a cached error or missing receipt; retry could not safely recover | Under the session lock, snapshot reversible session state, execute and serialize the response atomically; on unexpected failure restore the snapshot, version, sequence and refusal history, return retryable 503 without caching a false receipt. Fault injection spans V3/V4, observation/response and ValueError/RuntimeError. Retrying the identical UUID then commits exactly once. |
| Rollback would be invalid for an external or custom side-effect sink | API execution accepts exactly the in-memory simulation sink and refuses other implementations/subclasses before mutation. This does not claim hardware transactionality or durable crash recovery. |
| Certified human audit mislabeled the recommendation as Risk-Greedy | Use the actual recommendation planner; exported planner identity now agrees with certified_v4/risk_greedy mode. |
| WebSocket attachment could deliver a newer initial snapshot followed by an older queued message | Construct initial snapshot and register the subscriber in one session-lock cut; deterministic interleaving regression verifies increasing subsequent sequence. |
| V1 certificate hashes did not bind complete ordered candidate inputs; coordinated route-input mutation could escape the older edge-set checks | Prospective live v2 certificates include SHA-256 of complete canonical final-ID CertificateInputs. Authorizer verifies v2/digest before execution; replay fails closed on digest mismatch. Migration inherits v2 binding. Six altered-input classes and schema combinations are tested. |
| Client DECLINE or OVERRIDE→WAIT could display the recommended dispatch and path | Render the actual committed HOLD with no vehicle route or people movement. |
| Unknown-response retries could lose original KPI baseline; migration certificates could be attributed to the operator | Retain immutable submitted intent/context/baseline; distinguish automatic migration from human commitment. |
| Older cached receipts could regress displayed state; another client's committed actions could be missing | Guard state versions; reconcile committed certificates without duplicating local entries or counting migrations as operator actions. |
| Duplicate End, late hydration/context callbacks, close/start races and premature reattach IDLE could corrupt UI lifecycle | Serialize lifecycle, prohibit close/replacement during unresolved submit, generation-guard asynchronous callbacks, clear closed state and keep reattach busy until actionable context is ready. |
| Live test wrapper ignored CLI arguments; parallel certification caused readiness contention; mocked late calls could proxy into an unrelated local service | Forward arguments, default live tests to one worker, disable API proxy in fixture mode. Assertions and production certification remain intact. |

Sensitive baseline corrections were independently rechecked: authoritative planner masks, disabled fleet, hard-safety feasibility, V4 reservation release and population conservation, canonical evidence/citation integrity, approved-rule authentication, provider journal identity/quota handling, export/replay and state-bound human decisions. No additional unresolved material regression was established in the exercised paths. This is a bounded review, not proof that every possible execution is fault-free.

### Compatibility amendments

Frozen v1 certificates remain readable, schema-valid and replayable. Default historical generators still emit v1. New live sessions opt into v2; prospective actuation refuses unbound v1 inputs. The certificate schema and gate specification explicitly document this prospective format/authorization change. Existing prospective authorization fixtures and the live/reference parity fixtures were migrated to opt into v2, retaining their exact equality and authorization assertions. No frozen JSON was migrated. Normalizing only the prospective binding metadata yields the same v1 decision/state/certificate contents in regression tests.

## Final verification results

Counts below are recorded runs, not additive totals; selections overlap.

| Check | Result |
|---|---|
| Full Python 3.11 suite, final run | **1,273 passed, 1 failed, 0 skipped**, 614.67 s; only unchanged strict trace case failed |
| Python 3.12 integration/trace selection | **106 passed, 1 failed, 0 skipped**, 113.16 s; same strict case |
| Final Python 3.12 backend/engine/portability/hygiene boundaries | **39 passed, 0 failed, 0 skipped**, 35.53 s |
| Final backend, v2 reference/migration and portability boundary selection | **24 passed**, 61.61 s |
| Certificate contract/engine + hygiene selection | **21 passed**, 3.71 s |
| React components, independently rerun with default test timeouts | **52 passed**, 14 files, 9.96 s |
| TypeScript + production build | **PASS**, build 849 ms on recorded run |
| Fixture Playwright | **38 passed, 2 intentionally skipped**, 23 s; fixture results are not live-engine proof |
| Latest real API/React Playwright against v2 + rollback corrections | **12 passed, 0 skipped**, 1.6 min |
| Separate read-only recorded Phase 27 playback | **1 passed**, 5.6 s; no experiment regenerated |
| Standalone Python 3.12 release smoke | **9/9 passed**: health, auth-required, index, demo-start/walk, certificates, replay-match/tamper, evidence |
| Protected artifacts | **333/333 checksum matches** |
| Historical checkout | **296/296 captured file hashes unchanged**; original HEAD and dirty status unchanged |
| Docker | **NOT VERIFIED**: executable/daemon unavailable; no Docker build or container run claimed |
| GitHub Actions | **Infrastructure-blocked**: four failed jobs with zero executed steps, one skipped live job; no branch CI run exists because no push was authorized |

The first full run at takeover had 1,236 passes and the same one strict failure. An intermediate correction run had two additional v2 fixture-compatibility failures; they were corrected explicitly as described above. Final full-suite collection and subsequent focused runs are distinguished; late small schema/provenance/boundary changes were covered by their final focused tests rather than represented as a second full-suite run. Earlier resource-contention timeouts are retained in temporary logs and are not represented as successful runs. The independent final component run passed without increasing default test timeouts.

### Reproduction commands

From the integration root, the full suite used:

```bash
PYTHONDONTWRITEBYTECODE=1 \
HYPOTHESIS_STORAGE_DIRECTORY=/private/tmp/sentinel-final-signoff/hypothesis \
PYTHONPATH="$PWD/scripts/verification:$PWD" \
SENTINEL_PROTECT_WORKTREE=/Users/aksharsinha/Desktop/sentinel-sprint \
.venv/bin/python -m pytest tests/ -p no:cacheprovider -o addopts='' -q \
  --basetemp=/private/tmp/sentinel-final-signoff/pytest-final-all
```

Frontend from `web/`, using Node 22.22.3:

```bash
npm run test -- --maxWorkers=1 --no-file-parallelism
npm run build
npm run test:e2e
SENTINEL_PYTHON=/private/tmp/sentinel-remediation-verification/runtime312/bin/python \
SENTINEL_API_PORT=8100 PYTHONPATH="$PWD/../scripts/verification:$PWD/.." \
  npm run test:e2e:live
```

Final Python 3.12 boundary command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/scripts/verification:$PWD" \
SENTINEL_PROTECT_WORKTREE=/Users/aksharsinha/Desktop/sentinel-sprint \
/private/tmp/sentinel-remediation-verification/runtime312/bin/python -m pytest \
  tests/test_lx_final_backend_review.py tests/test_lx_final_engine_review.py \
  tests/test_lx_trace_portability.py tests/test_repo_hygiene.py \
  -p no:cacheprovider -o addopts='' -q \
  --basetemp=/private/tmp/sentinel-final-signoff/pytest-312-final-boundaries
```

Local release checks used the standalone `.venv-runtime` server on port 8102, the built `web/dist` and a disposable test-only Basic-auth password; `scripts/deploy_check.py http://127.0.0.1:8102` used that password from the environment. The server was stopped after verification. External API requests and protected writes were blocked by `scripts/verification/sitecustomize.py`; generated pytest data stayed in temporary directories.

Evidence logs are under `/private/tmp/sentinel-final-signoff/` (`python-final-all.log`, `python312-after-corrections.log`, `frontend-default-timeouts.log`, `release-check.json`, `protected-final.log`) and `/private/tmp/sentinel-remediation-verification/` (`final-client-real-browser-v2.log`, `final-client-mock-browser-rerun.log`, `final-client-build-v2.log`). Temporary logs are supporting local evidence, not frozen research artifacts or portable committed outputs.

## Real end-to-end evidence

`web/e2e/p34c_final_contract.spec.ts` exercises scenario initialization, current context, stochastic state, certification, authoritative route geometry and input digest, ACCEPT, permitted OVERRIDE, identical UUID retry without a second commit, conflicting-intent UUID 409, another client's advance followed by stale UI 409, REJECT→HOLD with no dispatch commands, ordered audit records, exports, certificate input/replay, reload reattachment, close and restart. The browser and backend agree on the committed action and route.

The latest real-engine lifecycle screenshot is `web/test-results/p34c_final_contract-real-o-12cbc-w-HOLD-reattach-and-exports-live/real-lifecycle.png`: step 4, four committed human decisions/certificates, 297 waiting, 40 in transit, zero safely arrived, zero stranded, and a pending next decision. It visibly shows ACCEPT/HOLD, OVERRIDE/dispatch, ACCEPT/dispatch and DECLINE/HOLD. Zero mandatory document rules and simulated conditions are explicit. The earlier `live-dispatch.png` captures a dispatch transition. These are generated real API browser evidence, not fixture screenshots; screenshots remain ignored, not scientific results.

## CI, artifact integrity and release limits

Fresh read-only GitHub inspection confirms run https://github.com/iamnoob96/sentinel-sprint/actions/runs/39157210783 at `52f2451`: web, docker, Windows and Ubuntu jobs each have zero executed steps. The annotation says account payments failed or the spending limit must increase. The live job was skipped. No account change or paid rerun was attempted. Local passing checks do not establish CI success.

The 333-entry manifest `docs/audit-remediation/protected-artifacts.sha256` itself remains SHA-256 `e6c3f21efef0b012aa2486a603ca1795fa13323970617c1f3a1df9cf27d62c73`. No `data/` or `models/` changes exist relative to the integration baseline. Historical checkout HEAD remains `c7207204a45aad93eadeb8d590ac8b56b17441d8`, with its original dirty status preserved. No model training, Gemini/Groq evaluation, official scientific rerun, new metric gate or frozen trace/graph/result change occurred.

Remaining limitations:

- Default strict trace reconstruction remains unmet; causal diagnosis is not a default-runtime pass. Exact original producer identity is unavailable.
- Docker and executed CI release evidence remain unavailable.
- Sessions/receipts are in-memory, single-worker and reversible only for the exact simulation sink. Process death loses sessions; this correction is not durable external-actuator transactionality.
- V2 digests detect input changes against trusted certificate content; they are not digital signatures or proof against a party who can rewrite all trusted state.
- There are zero enforced document T2 rules. Operational evidence is authenticated offline recorded guidance; no new online retrieval/semantic provider result is implied.
- Hazards are simulated on real road topology. No flood prediction, real emergency deployment or measured physical HIL readiness is established.
- Negative PPO results, construction-derived labels, Phase 14C failure, Phase 14D evaluation of record and failed Phase 27 throughput criteria remain explicit. No new scientific usefulness claim was generated.
- The real screenshot reveals a long event feed; useful for inspection, but a presenter should collapse/filter it. This is presentation debt, not a new scope-expanding UI redesign.

**Safe to push privately for review: YES, with these known failures disclosed; no push was performed. Safe to merge: NOT YET. University demonstration: YES, supervised and explicitly presented as a research prototype.** The next release decision should resolve the accepted numerical-runtime contract and obtain actual container/CI execution, without rewriting frozen evidence.

---

# Archived integration implementation report — predates final verification

The text below records the preceding integration mission. Its test counts and unresolved numerical hypothesis are historical, superseded by the final-verification section above.

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
