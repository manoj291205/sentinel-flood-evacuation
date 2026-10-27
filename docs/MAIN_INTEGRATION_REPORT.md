# Main branch consolidation report

Date: 2026-10-28. Private repository; no visibility change.

## Result and chosen source

GitHub default branch is `main`. The complete source selected at the start was
`lane-x/m40-full-integration-hardening` at `2f894e53fe76aa6219a9a42b83276b837cc371a5`,
22 commits ahead of `origin/main` (`52f2451846cefc320afdde2b9a1b48173118ae31`).
That source contains the V4 simulator/gate/API, all seven redesigned console pages,
live authorization, graph routing, audit exports, replay and the frozen research record.
No open pull request was awaiting integration.

The refreshed inventory contains **35 remote branches and 6 local branches**.
Of the remote branches, 32 are ancestors of the selected integration source.
The three exceptions were inspected individually below. The local V3 histories
have rewritten commit IDs but exactly equal trees to their remote counterparts.
No branch was selected solely because of its timestamp.

The old local `main` at `d5eefe5ed2117cce610233b88b1373c45f151a14` diverges in
history from current GitHub main. `git log --cherry-pick --right-only --no-merges
origin/main...main` returned no unmatched non-merge patches. Its history is preserved
under `archive/main-before-consolidation-20261028` rather than forced into the canonical
remote history. The final main is a descendant of existing GitHub main, so its
publication uses a normal fast-forward push, without force or history rewriting.

## Necessary corrections

- Recovered the Phase 14B side branch's clean server-error stop and integer-status
  precedence. Its absent offline tests were restored and extended. Durable attempt
  journals and strict request budgets remain in place. Its live CLI remains disabled;
  no historical provider run was resumed and no experiment was scored or regenerated.
- Added `scripts/run_console.sh`: one process serves the built React UI and FastAPI
  on localhost, using the standalone runtime first, with an overridable port.
- Updated the README's authoritative entry point and Python 3.12 runtime-only setup.
  Research/model dependencies remain optional for operating the console.
- Fixed Docker runtime inputs missing from the methodology/research views: README,
  corpus summary, planning-gate summary and training summary/curve metadata. A
  temporary runtime-file-layout test compares actual metadata functions against the
  full checkout. Virtual environments, local operation files and browser captures
  are excluded from Docker build context. No Docker daemon was available for a real
  image build/run; the file-layout check is not represented as container execution.

## Verification

| Check | Actual result |
|---|---|
| Full offline Python suite | 1,286 passed, 1 failed; 818.31 s |
| Recovered runner + durable journal regression selection | 29 passed |
| Packaging, release, disclosure and hygiene selection | 18 passed |
| Python 3.12 consolidation selection | 16 passed; 64.82 s |
| Console component suite | 60 passed across 14 files |
| TypeScript and production build | passed |
| Fixture browser suite | 38 passed, 2 intentional skips |
| Complete real API/browser suite | 42 passed |
| One-process launcher + authenticated release smoke | 9/9 passed |
| Protected artifacts | 333/333 SHA-256 matches |
| Actual Docker image build/run | NOT VERIFIED; Docker unavailable |
| GitHub Actions execution | prior run billing-blocked; final push status recorded separately |

The full suite's sole failure is the unchanged
`test_trace_rebuilds_byte_identically_and_validates`. It is the previously isolated
Mac platform-math discrepancy: five one-ULP raw forecast values; the same source
failure reproduces on untouched starting main. The strict assertion and frozen trace
remain unchanged. See `TRACE_REPRODUCIBILITY_V1.md`. Live execution, safety, API and
browser workflows pass; exact historical raw-float reproduction remains a limitation.

The packaging test was added after full-suite collection and passed in the focused
selection; overlapping counts are not added together. Test data stayed in temporary
directories and external provider requests were blocked. No models were trained,
providers evaluated, frozen experiments rerun or protected artifacts rewritten.
The earlier Desktop worktree remains on its V3 branch with its user changes preserved.

Logs: `/private/tmp/sentinel-main-consolidation/`. The standard start command is
`bash scripts/run_console.sh`; see README for the one-time setup. Use one worker;
sessions and decision receipts are in memory. Hazards and hardware are simulated,
zero document-derived T2 rules are mandatory, and this is not an operational
emergency deployment.

## Branch-by-branch disposition before final main update

| Branch | Head | Disposition |
|---|---|---|
| `lane-x/m40-full-integration-hardening` | `1d33996` | Selected integration branch |
| `main` | `d5eefe5` | Preserve as archive/main-before-consolidation-20261028; its 29 non-merge patches are already represented in remote main |
| `v2-resources` | `d998aac` | Historical resource snapshot; retain branch; older non-merge patches already represented |
| `v3-dynamic-stochastic` | `c720720` | Identical tree to rewritten origin/v3-dynamic-stochastic; retain local checkout and dirty files |
| `v3-geospatial-integration` | `5ebbef5` | Identical tree to rewritten remote V3 geospatial head; functionality already included |
| `v3-simulation-demo` | `d34bc80` | Identical tree to rewritten remote V3 simulation head; functionality already included |
| `origin/lane-x/m14b-claim-support` | `418891a` | Already included by ancestry |
| `origin/lane-x/m14b-run` | `d000ca8` | Recovered lost server-status handling and its offline regressions; retained newer journal and disabled live CLI |
| `origin/lane-x/m14c-claim-support` | `59e8969` | Only extra synchronization merge; provider byte-identical and current runner has later journal hardening |
| `origin/lane-x/m14c-results` | `ae976ef` | Already included by ancestry |
| `origin/lane-x/m14d-claim-support` | `cd22e95` | Already included by ancestry |
| `origin/lane-x/m14d-practice` | `dd91017` | Already included by ancestry |
| `origin/lane-x/m14d-results` | `f59b956` | Already included by ancestry |
| `origin/lane-x/m28-hil` | `1fc9393` | Already included by ancestry |
| `origin/lane-x/m30-api` | `4573761` | Already included by ancestry |
| `origin/lane-x/m31-web` | `1a0066c` | Already included by ancestry |
| `origin/lane-x/m32-decisions` | `90b822e` | Already included by ancestry |
| `origin/lane-x/m33-pages` | `dc7c88a` | Already included by ancestry |
| `origin/lane-x/m34a-wire` | `faa55a3` | Already included by ancestry |
| `origin/lane-x/m34c-live-session` | `e62b39c` | Already included by ancestry |
| `origin/lane-x/m35-escrow-lite` | `f1866a5` | Already included by ancestry |
| `origin/lane-x/m36-course` | `5e365a4` | Already included by ancestry |
| `origin/lane-x/m39-console-showcase` | `2b6b3f9` | Already included by ancestry |
| `origin/lane-x/m40-live-operations` | `8f8f184` | Already included by ancestry |
| `origin/m15p-constraints` | `5f2fd6d` | Already included by ancestry |
| `origin/m15t2-wiring` | `2d92284` | Already included by ancestry |
| `origin/m20-baseline` | `5bdb7e1` | Already included by ancestry |
| `origin/m21-v4-world` | `c1cb56b` | Already included by ancestry |
| `origin/m22-futures` | `f753f5b` | Already included by ancestry |
| `origin/m23-rollout` | `733d5c5` | Already included by ancestry |
| `origin/m24-certifier` | `73f8b99` | Already included by ancestry |
| `origin/m25-gate` | `a859507` | Already included by ancestry |
| `origin/m26-recertify` | `a903dba` | Already included by ancestry |
| `origin/m27-eval` | `1998eb6` | Already included by ancestry |
| `origin/m27-runs-remote` | `0eb6918` | 20 second-machine episodes match canonical episodes except wall_seconds; do not replace frozen canonical data |
| `origin/m34b-release` | `d5770a3` | Already included by ancestry |
| `origin/m34r-session-recert` | `36b398e` | Already included by ancestry |
| `origin/main` | `52f2451` | Already included by ancestry |
| `origin/v3-dynamic-stochastic` | `37591c5` | Already included by ancestry |
| `origin/v3-geospatial-integration` | `2e18a51` | Already included by ancestry |
| `origin/v3-simulation-demo` | `049d036` | Already included by ancestry |
