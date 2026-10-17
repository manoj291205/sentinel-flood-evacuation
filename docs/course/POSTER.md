# Poster draft — user export after approval

Format: **A1 portrait, 594 × 841 mm**. Keep all images and screenshots inside the private project until the disclosure level changes. Use the console's flat day-theme colors, IBM Plex Sans for prose, IBM Plex Mono for figures, clear rules between panels, and a visible honesty line. No screenshot is selected or attached here.

## Layout grid

| Region | Position and size | Content |
|---|---|---|
| Title | x 24, y 22, width 546, height 92 mm | Project title, student-supplied authorship, honesty statement |
| Problem | x 24, y 128, width 262, height 153 mm | Setting, question, limits |
| Method | x 308, y 128, width 262, height 153 mm | Approved mechanism paragraph, interface flow |
| Evidence | x 24, y 299, width 262, height 225 mm | Planner and retrieval chart from frozen artifacts |
| Demonstration | x 308, y 299, width 262, height 225 mm | User-selected console image of recorded run |
| Evaluation | x 24, y 542, width 262, height 213 mm | Claim support and Phase 27 verdict table |
| Limits and next steps | x 308, y 542, width 262, height 213 mm | Simulated setting, failed bar, research needs |
| Footer | x 24, y 777, width 546, height 42 mm | References, disclosure line, student-supplied contact |

## Title text

**Sentinel-Agent: evidence-grounded flood-evacuation decision support on Fort Kochi roads**

REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED

The author line and institution are intentionally blank for the student to complete after review.

## Problem panel

An evacuation operator needs to see waiting groups, active routes, shelter capacity, changing simulated hazards and the evidence behind each suggestion. The project uses real Fort Kochi road geometry with a simulated incident. It asks whether a recommendation and its audit trail can be presented clearly enough for a human to inspect. The console is a research prototype, not an operational dispatch tool. A map that looks familiar does not validate the forecast or the policy.

## Method panel

Before any dispatch is executed, Sentinel checks it against many sampled hazard futures and allows it only when a statistical lower bound on its success clears a fixed threshold; otherwise it holds and escalates to a human (fail-closed). Every decision gets a hash-chained certificate that anyone can replay bit-for-bit.

The browser separates a recorded teaching run from a live simulated session. Each page states the status of its data and retains an audit path.

## Evidence panel

The frozen V3 planner table reports practical normalized safety utility of **1.531** for lookahead, **1.000** for the named risk-greedy comparator and **0.209** for the evaluated learned-policy mean. The retrieval benchmark reports direct hit of **86.7 %** for BM25, **82.2 %** for hybrid and **62.2 %** for dense retrieval. These are separate synthetic benchmarks. The retrieval labels were AI assisted. **Place:** a chart built from the cited frozen rows, with both metric definitions and a visible synthetic-data caption. [3][4][5]

## Demonstration panel

**Place:** a user-approved local screenshot of Live Operations during the recorded run. It should show the honesty banner, simulated map, suggestion, alternatives and certificate link. Add a small inset from Decisions & Certificates showing a matching replay. The run's seed was chosen to show a hold, dispatches and a re-route. It is a demonstration, not a representative performance sample. Do not use a screenshot until the student has approved the text and disclosure scope.

## Evaluation panel

**14D is the claim-support evaluation of record**; its frozen T2-use verdict passed. **14C failed** its macro-score and span-integrity conditions (**58.5 %**, **10.4 %**). **14B superseded** was not scored. NDMA-R01 and NDMA-R02 remain T1 after partially supported answers; no recorded rule is T2. Phase 27 was preregistered: the safety bar passed, the outcome bar failed with R = **21.4 %** below **95 %**, the decision-level comparison passed with details withheld, and the variance bar failed. There is **no outcome-effect claim**. [6][7][8]

## Limits and next steps panel

The roads are real; flood conditions, groups and shelter states are simulated. The planner, retrieval and claim-support benchmarks use project-specific test settings and labels. Replay checks consistency with stored inputs, not the correctness of real-world inputs. A new preregistered outcome study would be needed before any stronger system-level statement. Real deployment would also need current data, human-factors work and independent operational review. The course draft remains RESTRICTED and requires user approval before outside use.

## Footer

Source details: [3]–[8] in `REFERENCES.md`; every printed measurement is linked to a frozen artifact in `NUMBERS.md`. Disclosure level: RESTRICTED. Student contact and acknowledgements: to be completed by the student.
