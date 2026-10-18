# Console showcase · 12-minute judge walkthrough

**Disclosure:** RESTRICTED. Run locally in the private repository. Real Fort Kochi road topology; disaster conditions, populations, shelters and decisions are simulated. This is not an operationally validated system. The live session uses `v4-cert-test-v1` demo parameters, not the evaluated configuration.

## 0:00–3:00 · Recorded simulation library

1. Open **Simulations**. Point to the source labels: `data/eval_results/phase27/runs/*.jsonl` for final results and `states/*.jsonl.gz` for the certified gate's per-step decisions. The library has 1,260 unique run summaries and 180 per-step gate traces, counted by `/api/library/index`.
2. Set 5× speed and choose **Run-all showcase**. Let medium, high and stress worlds play. Pause at a HOLD and a route choice. Show flood rings, simulated closures, shelter fill and route details on the real road graph. These are recorded certifier inputs, not an animation of unrecorded arrivals.
3. Choose the same world and seed for **P versus A2**. The A2 side shows a final summary because no A2 per-step trace exists. Point out the D-27 decision: Bars 2 and 4 pass; Bars 1 and 3 fail. The recorded group failure rates are shown only beside throughput guard R. **No outcome-effect claim.** Source: `data/eval_results/phase27/analysis.json` and `specs/V4_D27_DECISION.md`.

## 3:00–7:00 · Live certified command centre

1. Open **Live Operations**. **LIVE ENGINE** is the default. Choose the medium world and seed 620003, then **Start**. The header identifies the live session and pending decision; the large sticky **OPERATOR DECIDES** bar stays in view while scrolling. This uses `v4-cert-test-v1` demo parameters, not the Phase 27 evaluated configuration.
2. At step 0, read the HOLD rationale and safety bound. Click **Accept**. Show the result strip, certificate, new decision card, feed line, KPI change, map mark and toast. Choose **Step on**.
3. At the next certified suggestion, click **Override**. Choose a certified alternative, select **Road report**, enter a field reason, and confirm. Show the amber route, the actual chosen subject and the certificate link. Choose **Step on**.
4. Click **Override** again and select an option marked **the gate will refuse this**. Supply a reason code and text, then confirm. Show the red refusal banner, refused log card and unchanged dispatch state. The modal remains open because the server rejected the action.
5. Choose **Decline**, provide a reason code and text, and confirm. Show the grey declined route and HOLD certificate. Open **Overview**: the live KPIs and last decisions follow the session. Open **Decisions & Certificates**, select **Show this live session**, and show the new certificates. Return to **Live Operations** and show that the session and log remain. Auto-run advances after each human decision; **Demo fast-forward · 3 accepts** is a separate labelled action.

## 7:00–9:00 · Exploratory network outage

1. Select **Two-team network demo**. Start with escrow mode, then use **Cut network**, **Step on**, and **Restore network**. Point to the ONLINE/OFFLINE indicator, the team seat bars, blocked dispatches and returned capacity.
2. Switch to last-known mode. The comparison panel reads `data/eval_results/phase35lite/outages.json`: 40 paired simulated outages, zero overbooked seats with escrow and 80 with last-known across five outages. This is exploratory and was not pre-registered; it supports no outcome-effect claim.

## 9:00–12:00 · Journey and evidence

1. Open **How it was built**. Follow the architecture from scenario and simulator through safety, planner, certifier, operator, certificate and HIL rig. Click boxes to reveal their role.
2. Walk the phase timeline and source-labelled counts. The reviewed test count comes from the dated README milestone table, and corpus size from `data/eval_v3/phase11_corpus_summary.json`.
3. Open **Evidence & Results**. Show Phase 10 planners, Phase 13 retrieval and the claim-support history: 14B superseded without a score, 14C failed, 14D is the evaluation of record. Return to the four D-27 bars and the absence of an outcome-effect claim. Hardware bench latency remains unavailable until measured.
