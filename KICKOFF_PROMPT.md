# Kickoff prompt — paste this as your first message to Builder S Code

I'm building a fast, zero-budget prototype for a college capstone project demo — not production, not the patent-grade version. Read DEVELOPMENT.md in this directory first; it has the ground rules and tech stack, including that everything must run free. I have roughly one day. Work through the steps below **in order**, using plan mode before each one, and stop for my confirmation after each step runs successfully. Commit to git after each step.

## Step 0 — Setup
- Initialize a git repo if one doesn't exist.
- Create the project structure from DEVELOPMENT.md.
- Create a Python virtual environment and start `requirements.txt` (add to it as you go).
- Confirm `GEMINI_API_KEY` is available in the environment before writing any code that calls the Gemini API — if it isn't set, tell me and wait. (I'll get this free from Google AI Studio myself — no credit card needed.)

## Step 1 — The scenario
Build `data/scenario.json`: a fictional but plausible ward-level flood scenario **inspired by** the August 2018 Kerala floods (peaked mid-August 2018; severely affected districts included Idukki, Ernakulam, Alappuzha, Thrissur, and Wayanad; worsened by controlled dam releases including from the Idukki reservoir — treat these as real background facts you can use). Invent a small fictional grid (8-10 cells) with:
- One flooded source cell with a population needing evacuation
- 5-8 candidate shelter cells, each with a location, a capacity, and a travel cost from the source
- Enough spread that some shelters are clearly better choices than others once constraints are applied

Only two kinds of data matter here: flood/hazard severity and shelter status. Don't add sensor feeds, satellite imagery, or traffic data to the scenario — out of scope.

Do **not** present this fictional grid as real GPS or administrative data — label it clearly, in comments and later in the README, as "inspired by the 2018 Kerala floods, using a simplified fictional grid for demo purposes."

## Step 2 — Real RAG corpus
Try to fetch these real NDMA/NIDM flood management guideline documents and save them into `data/raw_docs/`:
- https://ndma.gov.in/sites/default/files/PDF/Guidelines/flood.pdf
- https://nidm.gov.in/pdf/guidelines/floods.pdf

If fetching fails because this environment has no network access, tell me exactly that and pause — I'll download them myself and place them there, then you can continue.

Once at least one real document is in `data/raw_docs/`, chunk it and embed it **locally with `sentence-transformers`** (no API call for this step) into a local Chroma collection under `src/rag/`. Write a small test that retrieves the top 3 chunks for a query like "flood evacuation shelter capacity" and prints them, so we can both confirm it's retrieving real text before moving on.

## Step 3 — The constraint step
In `src/constraints/`, write a function that:
1. Takes the scenario state (which cells are flooded, shelter capacities/status) and the top retrieved RAG chunks as input.
2. Calls the **Gemini API free tier** (`gemini-2.5-flash`) with a prompt asking it to return JSON matching the schema in DEVELOPMENT.md exactly — mark each candidate shelter `allowed` or `excluded`, with a one-sentence reason and which source document/excerpt it's based on.
3. Validates the returned JSON against the schema, and retries once if it doesn't parse.

Test it standalone against the Step 1 scenario and print the result before moving on.

## Step 4 — The RL environment
In `src/env/`, build a Gymnasium environment that frames this as a **single-decision task**: given the scenario state and the constraint mask from Step 3, the agent picks one shelter (discrete action space, one action per candidate shelter) in a single step per episode. Reward: highest for picking the best *allowed* shelter (weight capacity headroom and lower travel cost), lower for a worse allowed choice. Excluded shelters should be structurally unselectable — use `MaskablePPO` from `sb3-contrib` rather than relying on a penalty.

Randomize the scenario slightly across episodes (which shelters are excluded, capacities, distances) so the policy has something real to learn, but keep it small enough that training converges in a couple of minutes on CPU. Train a short run, save the checkpoint to `models/`, and show me a handful of example decisions with their rewards before moving on.

## Step 5 — Dashboard
In `src/dashboard/`, build a single-page Streamlit app that shows the scenario (a simple grid or table is fine), runs the trained policy on it, and displays the recommended shelter plus, for every excluded shelter, its reason and source citation from Step 3. This is the part I'll actually be showing live, so it should look clean even though the logic behind it is simple.

## Step 6 — Tie it together
Write one script, `run_demo.py`, that runs the whole pipeline end to end on the Step 1 scenario with no manual steps in between. Write `README.md` explaining: what's real (the NDMA/NIDM documents, the 2018 Kerala floods background) vs. simplified/fictional (the grid, the specific numbers), which free-tier services this depends on (Gemini API, local sentence-transformers), how to run everything, and what would need to change to make this the full, rigorous version (I can paste in the fuller architecture doc if you want it for that section — ask me).

## When every step is done
Give me a short summary of what got built, what's real vs. simulated, and anything you had to cut or simplify beyond what's specified above, so I know exactly what I'm actually presenting tomorrow.
