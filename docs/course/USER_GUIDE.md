# Local console user guide — private draft

Disclosure level: RESTRICTED. The console shows real Fort Kochi road topology with simulated disaster conditions and is not operationally validated. Use it only as a local research demonstration. Do not post screenshots or a recording before the user approves the disclosure text.

## Start the console

From the repository root on Windows, run `scripts/dev.ps1`. The release script checks the local Python environment and Node installation, installs web packages if needed, and starts the API and browser console. It prints the local URLs. Use Ctrl+C to stop both processes. For a browser-only preview with contract mock data, run `scripts/dev.ps1 -Mock`; that mode does not start the API.

Do not enter real incident data, API keys or passwords into the course screenshots. The optional demo password is for local access control and is not an operational authentication system. The mock mode is useful for page layout and keyboard checks; it must be labeled as a scripted preview, not as a recorded engine result.

## Overview

Overview summarizes the current simulated incident and links to its latest decision record. Read the honesty banner before interpreting the map or counts. Waiting, on-road and shelter figures come from the selected simulated state. A missing or stale value is left visible as unavailable with its reason. Use this page as orientation, then open Live Operations for the step-by-step view.

## Live Operations

The **Guided demo** plays a recorded run of the real engine. **Run demo** advances through the prepared sequence; Back, Next and Reset support closer inspection. The seed note explains why that run was selected and why it is not a performance sample. The map, event feed, candidates and suggestion update with each recorded step. Accept displays the recorded certificate. Override or Reject in this mode does not change the trace; use a live session to record a new choice.

The **Live session** mode starts a new simulated run from a selected seed and world. Wait for the “Certifying…” indicator to finish, then read the suggestion, reasons and alternatives. A certified alternative can be chosen for Override with a required reason; Reject also needs a reason. An uncertified option is visibly blocked, and a refused attempt is shown without advancing the step. After a decision, follow the new certificate link to inspect its record. The In transit tab shows re-checks for groups already on the road and any re-route note. This is an interactive simulation, not a field dispatch screen.

## Decisions & Certificates

This page lists recorded decisions and their certificates. Select a row to inspect the chosen action, candidates, bounds, operator record and audit trail. The explanation lists reasons derived from the recorded certificate. **Replay certificate** checks the stored calculation. The **Tamper with forecast (demo)** control changes a request copy and should produce a mismatch naming the altered field. A matching replay confirms consistency with the stored inputs; it does not validate a real hazard forecast.

## Evidence & Results

The page shows values from an allowlisted manifest with source paths and missing-value reasons. The 14D claim-support result is the evaluation of record; 14C failed and 14B was superseded. The Document rules table reads the current rule-tier run: NDMA-R01 and NDMA-R02 remain T1, and no current rule is T2. A stale or missing tier result is not promoted. The Phase 27 section reports the failed outcome bar and its R guard beside the other bar outcomes. Read it with the report's no outcome-effect claim.

## System & Hardware

This page shows the local software and simulated hardware state, including device and topic information when available. A fixture device or publisher is not a physical bench result. The absence of a measured physical latency is displayed as unavailable. Use this page to distinguish a software demonstration from a connected device trial.

## Troubleshooting and interpretation

If a page says the API is unavailable, confirm the local development script started the API, then retry. If the recorded trace is missing or invalid, the demo and certificate endpoints report an error; the service should still answer its health request. If a displayed result is unavailable, inspect the source path and note rather than substituting a value from another run. If a rule tier is stale, rerun the approved tiering process through the project workflow before quoting it. Nothing in this guide authorizes a real evacuation decision.
