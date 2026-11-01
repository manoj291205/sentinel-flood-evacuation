# Development milestones

The phase-by-phase build record. The console's "How it was built" page reads this table.

<!-- MILESTONE-TABLE:START — refreshed by the reviewer at every merge into main -->
Last refreshed: 2026-10-19 (Phase 40 merged) · base branch `main` · 1118 tests pass on `main`

V3 (phases 0–19) is complete. V4 extends it with a certified dispatch layer. Work was built on milestone branches and appeared here only after
it had been reviewed and merged into `main`.

### V3 — complete

| Phase | Component                                              | Status        |
| ----- | ------------------------------------------------------ | ------------- |
| 0     | V1 baseline freeze and repository audit                | ✅ Complete   |
| 1     | Pre-registered evaluation framework                    | ✅ Complete   |
| 2     | Versioned V3 scenario/data contract                    | ✅ Complete   |
| 3     | Deterministic multi-timestep evacuation simulator      | ✅ Complete   |
| 4     | Stochastic flood, travel, closure and shelter dynamics | ✅ Complete   |
| 5     | Deterministic hard-safety engine and action masks      | ✅ Complete   |
| 6     | Strong planning baselines and pre-PPO headroom gate    | ✅ Complete   |
| 7     | Fixed-dimension Gymnasium environment                  | ✅ Complete   |
| 8     | Pre-registered RL reward and integration               | ✅ Complete   |
| 9     | Five-seed MaskablePPO training                         | ✅ Complete   |
| 10    | Frozen held-out planner-vs-PPO evaluation              | ✅ Complete   |
| 11    | Authoritative RAG corpus expansion                     | ✅ Complete   |
| 12    | Dense + BM25 + hybrid retrieval                        | ✅ Complete   |
| 13    | AI-assisted retrieval benchmark                        | ✅ Complete   |
| 14A   | Construction-labeled claim-support challenge           | ✅ Complete   |
| 16    | Cached geospatial road graph and routing engine        | ✅ Complete   |
| 17    | Dynamic hazard-aware graph routing integration         | ✅ Complete   |
| 18    | Human-in-the-loop override and session audit trail     | ✅ Complete   |
| 19    | Streamlit review dashboard (legacy)                    | ✅ Complete   |

### V4 — Wave C complete (`v4.0`), console showcase and Live Operations rebuild merged

| Phase  | Component                                                   | Status                                   |
| ------ | ----------------------------------------------------------- | ---------------------------------------- |
| 20     | Verified baseline (frozen-artifact guard, UTF-8, CI)        | ✅ Complete                              |
| 14B    | Semantic claim-support evaluation (first provider)          | ⛔ Superseded (provider unusable; not scored) |
| 14C    | Semantic claim-support evaluation (second provider)         | ✅ Complete — verdict NOT_YET_RELIABLE   |
| 14D    | Semantic claim-support evaluation (evaluation of record)    | ✅ Complete — verdict USEFUL             |
| 15′    | Tier-verified NDMA constraints (incl. T2 wiring)            | ✅ Complete — rules R01, R02 at T1       |
| 21     | V4 simulated world (multi-step transit, failures)           | ✅ Complete                              |
| 22–24  | Certification engine                                        | ✅ Complete                              |
| 25–26  | Dispatch gate, certificates, replay, re-routing              | ✅ Complete                           |
| 27     | Pre-registered evaluation and decision D-27                 | ✅ Complete — no outcome-effect claim    |
| 28     | Hardware-in-the-loop rig (simulated publisher until parts)  | ✅ Complete                              |
| 30–31  | FastAPI service and React console with guided demo          | ✅ Complete                              |
| 32–33  | Decisions & Certificates, Overview, Evidence, System pages  | ✅ Complete                              |
| 34A    | Console wired to the real engine (recorded run)             | ✅ Complete                              |
| 34C    | Live session: accept / override while the simulation runs   | ✅ Complete                              |
| 34B    | Release: dev scripts, CI web jobs, demo script, Docker      | ✅ Complete                              |
| 36     | Course submission pack                                      | ✅ Drafts complete — awaiting user approval |
| 35-lite| Network-outage capacity shares (exploratory)                | ✅ Complete — exploratory, no outcome claim |
| 37     | Conference paper                                            | 📝 Draft complete — not submitted        |
| 38     | Journal extension                                           | ⏳ Optional                              |
| 39     | Console showcase: simulation library, replay, live decision pop-up | ✅ Complete                     |
| 40     | Live Operations rebuild: every operator action shown everywhere | ✅ Complete (small follow-up open) |
| P0, 29 | Patent filing                                               | ✖ Dropped (conference paper only)        |
| 35     | Full escrow embodiment                                      | ✖ Dropped (D-27)                         |
<!-- MILESTONE-TABLE:END -->
