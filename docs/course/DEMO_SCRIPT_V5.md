# Console showcase · 12-minute judge walkthrough

**Disclosure:** RESTRICTED. Run locally in the private repository. Real Fort Kochi road topology; disaster conditions, populations, shelters and decisions are simulated. This is not an operationally validated system. The live session uses `v4-cert-test-v1` demo parameters, not the evaluated configuration.

## 0:00–3:00 · Recorded simulation library

1. Open **Simulations**. Point to the source labels: `data/eval_results/phase27/runs/*.jsonl` for final results and `states/*.jsonl.gz` for the certified gate's per-step decisions. The library has 1,260 unique run summaries and 180 per-step gate traces, counted by `/api/library/index`.
2. Set 5× speed and choose **Run-all showcase**. Let medium, high and stress worlds play. Pause at a HOLD and a route choice. Show flood rings, simulated closures, shelter fill and route details on the real road graph. These are recorded certifier inputs, not an animation of unrecorded arrivals.
3. Choose the same world and seed for **P versus A2**. The A2 side shows a final summary because no A2 per-step trace exists. Point out the D-27 decision: Bars 2 and 4 pass; Bars 1 and 3 fail. The recorded group failure rates are shown only beside throughput guard R. **No outcome-effect claim.** Source: `data/eval_results/phase27/analysis.json` and `specs/V4_D27_DECISION.md`.

## 3:00–7:00 · Live certified command view

1. On **Live Operations**, switch to **Live session**. Choose medium world and seed 620003. Explain that the modal pauses the operator flow at each new certified suggestion. The seeded demo configuration is `v4-cert-test-v1`, not the Phase 27 evaluated configuration.
2. At step 0, read the reasons, safety bound, alternatives and source reference. Click **Accept** for the HOLD. Show the certificate link on the result screen, then **Step on**.
3. At the next certified suggestion, choose **Override**, select a certified alternative or HOLD, choose a code, enter a reason, and submit. Show the audit and certificate. For a refusal, click **Test gate refusal (demo)** on an uncertified alternative; its **Choose** control remains disabled. The red `UNCERTIFIED_OVERRIDE_REFUSED` banner remains until another decision is made, and no dispatch is committed.
4. Choose **Decline**, select a reason code, enter a reason, and submit. Demonstrate the audit CSV/JSON download at episode end. Auto-run advances after each human decision; it never accepts by itself. **Demo fast-forward with accepts** is a separate labelled control.

## 7:00–9:00 · Exploratory network outage

1. Select **Two-team network demo**. Start with escrow mode, then use **Cut network**, **Step on**, and **Restore network**. Point to the ONLINE/OFFLINE indicator, the team seat bars, blocked dispatches and returned capacity.
2. Switch to last-known mode. The comparison panel reads `data/eval_results/phase35lite/outages.json`: 40 paired simulated outages, zero overbooked seats with escrow and 80 with last-known across five outages. This is exploratory and was not pre-registered; it supports no outcome-effect claim.

## 9:00–12:00 · Journey and evidence

1. Open **How it was built**. Follow the architecture from scenario and simulator through safety, planner, certifier, operator, certificate and HIL rig. Click boxes to reveal their role.
2. Walk the phase timeline and source-labelled counts. The reviewed test count comes from the dated README milestone table, and corpus size from `data/eval_v3/phase11_corpus_summary.json`.
3. Open **Evidence & Results**. Show Phase 10 planners, Phase 13 retrieval and the claim-support history: 14B superseded without a score, 14C failed, 14D is the evaluation of record. Return to the four D-27 bars and the absence of an outcome-effect claim. Hardware bench latency remains unavailable until measured.
