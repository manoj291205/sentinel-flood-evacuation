Confidential until P0 is filed — do not show outside the project.

# Sentinel V4 — five-minute walkthrough

For judges. Open the console (hosted behind the password, or `scripts/dev.ps1`) on **Overview**. Click what is in
**bold**; say what is in the quoted lines.

**Say this first, in your own words:** "Everything on screen is simulated: real Fort Kochi roads, simulated flood hazards. The guided demo is a recorded run of the real engine, using the fast parameter set, which is not the evaluated configuration. The pre-registered evaluation makes no outcome-effect claim."

## 0:00–0:20 Overview
Show the banner and the status tiles. "Sentinel is a decision-support gate: it only suggests a dispatch when it can
certify it is safe across many sampled hazard futures. Otherwise it holds, and says why."

## 0:20–1:20 Live Operations — Run demo
Click **Run demo**, then **Next** through the six steps. At each step read the caption aloud and point at the
suggestion, the gate result and the map.
- Step 0: no option clears the bar, so the suggestion is HOLD and the gate escalates. "It does not guess: undecided means blocked."
- Steps 1–3: new dispatches, each with a certificate. The caption says how many options cleared the bar and how many
  stayed undecided. From step 2 the groups already on the road are re-checked and kept.
- Step 4: a group on the road loses its certificate and is re-routed automatically; the note names the re-route
  certificate. "The operator is notified; the re-route is certified like any dispatch."
- Step 5: another dispatch, with the re-checks still running. Every decision so far has a certificate that can be replayed.

## 1:20–2:10 Live session
Switch to the live session. Start seed 620003 on `v4-medium-dt2-v1`. The first step is a HOLD: show the alternatives
marked uncertified and the three reasons. **Accept**. **Step on** to the next step; if a group on the road is
re-checked, point at the re-check row. Then **Override**: pick a certified alternative and type a reason, and show
the new certificate and the new audit row. "An override to an uncertified action is refused, flagged and recorded; nothing is committed."

## 2:10–3:40 Network outage (exploratory)
Say first: "This part is exploratory. It was added after the pre-registered evaluation and is not part of it."
In Live Operations tick **Two-team network demo**, choose **With escrow** and **Start** (seed 620003). Step on once while
ONLINE: both field teams share one certified decision. Then **Cut network**: the banner reads `Simulated network
outage`. Point at the per-team lines: each team can now only use its own share of each shelter's free seats, and the
shares never add up to more than the seats free at the cut. Step on offline: each team's gate certifies against its
share only. Show a dispatch that needs more than the team's share: it is held, with the reason and a suggestion.
Then **Restore network**: unused shares go back to the pool and the rebalance shows the conserved seat totals.
Switch to **Without escrow** and repeat: both teams believe all the free seats are theirs, and the overbooked-seats
counter shows the collision. "This phase counts conflicts and held dispatches. It makes no outcome-effect claim." The
counts of outages, conflicts and held dispatches are on Evidence & Results under the exploratory group; read them
there and quote nothing from memory.

## 3:40–4:10 Decisions & Certificates
Open a certificate. Show its kind, the verdict bounds and the stored inputs. Click **Replay certificate**: the result is MATCH.
Tick **Tamper with forecast (demo)** and click **Replay certificate** again: the result is MISMATCH on the forecast hash. "Any certificate can be
re-derived from its stored inputs; changing an input is detected."

## 4:10–4:40 Evidence & Results
Read only what the page shows. "Replay match rate: 100.0 % over 1,274 certified decisions." Then the honest part:
"The pre-registered evaluation has a guard, R, the delivered-people ratio of the gated system against the baseline.
R is 21.4 %, so the guard failed. There is no outcome-effect claim. Any failure rate quoted from that evaluation must
be quoted together with R = 21.4 %. What the evidence does support is decision-level: certified decisions replay, and no
unsafe dispatch was accepted in the checked states." Mention that the claim-support check of rule texts is on record,
the earlier attempt failed, and no document rule reached the top tier.

## 4:40–5:00 System & Hardware
Show the hardware page. "The hardware loop is simulated; there are no bench numbers until the parts arrive."
Close: "Sentinel certifies before it dispatches, holds when it cannot, and every decision can be replayed. We make no
outcome-effect claim, and we say exactly which parts are simulated."
