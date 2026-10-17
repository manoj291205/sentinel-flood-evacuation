Confidential until P0 is filed — do not show outside the project.

# Sentinel V4 — five-minute walkthrough

For judges. Open the console (hosted behind the password, or `scripts/dev.ps1`) on **Overview**. Click what is in
**bold**; say what is in the quoted lines.

**Say this first, in your own words:** "Everything on screen is simulated: real Fort Kochi roads, simulated flood hazards. The guided demo is a recorded run of the real engine, using the fast parameter set, which is not the evaluated configuration. The pre-registered evaluation makes no outcome-effect claim."

## 0:00–0:30 Overview
Show the banner and the status tiles. "Sentinel is a decision-support gate: it only suggests a dispatch when it can
certify it is safe across many sampled hazard futures. Otherwise it holds, and says why."

## 0:30–1:45 Live Operations — Run demo
Click **Run demo**, then **Next** through the six steps. At each step read the caption aloud and point at the
suggestion, the gate result and the map.
- Step 0: a new dispatch is certified. "Each suggestion carries a certificate."
- Step 1: a shelter closes while a group is on the road; the gate re-checks it and acts automatically.
- Step 3: an option stays blocked because the evidence is too thin. "Undecided means blocked."
- Step 4: no option clears the bar, so the suggestion is HOLD and escalate. "It does not guess."
- Step 5: monitoring. Every decision so far has a certificate that can be replayed.

## 1:45–2:45 Live session
Switch to the live session. Start seed 620003 on `v4-medium-dt2-v1`. The first step is a HOLD: show the alternatives
marked uncertified and the three reasons. **Accept**. **Step on** to the next step; if a group on the road is
re-checked, point at the re-check row. Then **Override**: pick a certified alternative and type a reason, and show
the new certificate and the new audit row. "An override to an uncertified action is refused, flagged and recorded; nothing is committed."

## 2:45–3:45 Decisions & Certificates
Open a certificate. Show its kind, the verdict bounds and the stored inputs. Click **Replay**: the result is MATCH.
Click **Replay with tampered input**: the result is MISMATCH on the forecast hash. "Any certificate can be
re-derived from its stored inputs; changing an input is detected."

## 3:45–4:30 Evidence & Results
Read only what the page shows. "Replay match rate: 100.0 % over 1,274 certified decisions." Then the honest part:
"The pre-registered evaluation has a guard, R, the delivered-people ratio of the gated system against the baseline.
R is 21.4 %, so the guard failed. There is no outcome-effect claim. Any failure rate quoted from that evaluation must
be quoted together with R = 21.4 %. What the evidence does support is decision-level: certified decisions replay, and no
unsafe dispatch was accepted in the checked states." Mention that the claim-support check of rule texts is on record,
the earlier attempt failed, and no document rule reached the top tier.

## 4:30–5:00 System & Hardware
Show the hardware page. "The hardware loop is simulated; there are no bench numbers until the parts arrive."
Close: "Sentinel certifies before it dispatches, holds when it cannot, and every decision can be replayed. We make no
outcome-effect claim, and we say exactly which parts are simulated."
