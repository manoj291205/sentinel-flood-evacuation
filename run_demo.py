#!/usr/bin/env python
"""Run the whole Sentinel-Agent pipeline end to end, with no manual steps in between.

    .venv/bin/python run_demo.py

Each stage skips work whose artifact already exists, so a rerun is fast, but the script
can rebuild the entire pipeline from nothing but the committed PDF.

Flags:
    --rebuild-index        re-chunk and re-embed the corpus
    --refresh-constraints  force a new Gemini call instead of using the cache
    --retrain              retrain the policy from scratch
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RAW_DOCS = PROJECT_ROOT / "data" / "raw_docs"
CHROMA_DIR = PROJECT_ROOT / "src" / "rag" / "chroma_db"
MODEL_PATH = PROJECT_ROOT / "models" / "maskable_ppo_shelter.zip"

WIDTH = 84


def banner(number: int, title: str) -> None:
    print()
    print("=" * WIDTH)
    print(f"STAGE {number} — {title}")
    print("=" * WIDTH)


def fail(message: str) -> int:
    print(f"\nFAILED: {message}")
    return 1


# ---------------------------------------------------------------------------------------


def stage_preflight(needs_api: bool) -> bool:
    banner(1, "Preflight")
    print(f"Python {sys.version.split()[0]}  ({sys.executable})")

    missing = []
    for module in ("pypdf", "sentence_transformers", "chromadb", "google.genai",
                   "gymnasium", "stable_baselines3", "sb3_contrib", "streamlit"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        print(f"  MISSING packages: {missing}")
        print("  Install them with:  .venv/bin/python -m pip install -r requirements.txt")
        return False
    print("  all required packages import OK")

    import os

    if os.environ.get("GEMINI_API_KEY"):
        print("  GEMINI_API_KEY: set")
    elif needs_api:
        print("  GEMINI_API_KEY: NOT SET — required, because constraints must be generated.")
        print("  Get one free from Google AI Studio (no credit card needed).")
        return False
    else:
        print("  GEMINI_API_KEY: not set — not needed, cached constraints will be used.")
    return True


def stage_scenario():
    from src.constraints.generate import load_scenario, shelter_facts

    banner(2, "Scenario  (fictional — inspired by the 2018 Kerala floods)")
    scenario = load_scenario()
    source = scenario["source"]
    print(f"scenario_id : {scenario['scenario_id']}")
    print(f"grid        : {scenario['grid']['rows']}x{scenario['grid']['cols']} "
          f"= {len(scenario['grid']['cells'])} cells")
    print(f"source cell : {source['cell_id']} — {source['population_to_evacuate']:,} "
          f"people to evacuate")
    print()
    print(f"  {'ID':<4}{'cell':<6}{'severity':<10}{'band':<10}{'spare':>7}{'travel':>8}   status")
    print("  " + "-" * (WIDTH - 4))
    for fact in shelter_facts(scenario):
        print(f"  {fact['shelter_id']:<4}{fact['cell_id']:<6}{fact['flood_severity']:<10}"
              f"{fact['severity_band']:<10}{fact['capacity_headroom']:>7}"
              f"{fact['travel_cost_minutes']:>8}   {fact['status']}")
    return scenario


def stage_corpus(rebuild: bool) -> bool:
    banner(3, "RAG corpus  (real NDMA guidelines, embedded locally)")

    if not list(RAW_DOCS.glob("*.pdf")):
        print("No PDF in data/raw_docs/ — fetching (needs network)...")
        from src.rag.fetch_docs import fetch_all

        if fetch_all() != 0:
            return False
    else:
        print("Source document already present (committed to the repo).")

    import json

    manifest_path = RAW_DOCS / "MANIFEST.json"
    if manifest_path.exists():
        for doc in json.loads(manifest_path.read_text())["documents"]:
            print(f"  {doc['filename']} — {doc['pages']} pages, {doc['bytes']:,} bytes")
            print(f"    {doc['title']}")
            print(f"    {doc['publisher']}, {doc['dated']}")
            if doc.get("mirror_urls"):
                print(f"    NOTE: {len(doc['mirror_urls'])} other URL(s) serve this exact "
                      f"file (identical sha256) — this is ONE document, not several.")

    if rebuild and CHROMA_DIR.exists():
        print("\n--rebuild-index: removing the existing vector store.")
        shutil.rmtree(CHROMA_DIR)

    if not CHROMA_DIR.exists():
        print("\nNo vector store — chunking and embedding locally (no API call)...")
        from src.rag.ingest import build_index

        if build_index() != 0:
            return False
    else:
        print("\nVector store already built.")

    # Prove retrieval works rather than assuming it.
    from src.rag.retrieve import retrieve

    top = retrieve("flood evacuation shelter capacity", k=1)[0]
    print(f"\nLive retrieval check — query 'flood evacuation shelter capacity':")
    print(f"  top hit: {top.citation()}  (cosine distance {top.score:.4f})")
    print(f"  \"{top.text[:150].strip()}...\"")
    return True


def stage_constraints(refresh: bool):
    banner(4, "Constraints  (one structured Gemini call, grounded in the real text)")
    from src.constraints.generate import ConstraintError, load_or_generate

    try:
        payload = load_or_generate(refresh=refresh, verbose=True)
    except ConstraintError as exc:
        print(f"  {exc}")
        return None

    meta = payload["_meta"]
    print(f"\nmodel: {meta['model']}   attempts used: {meta['attempts_used']}")
    print()
    print(f"  {'ID':<5}{'verdict':<11}{'citation verified':<20}reason")
    print("  " + "-" * (WIDTH - 4))
    for item in sorted(payload["constraints"], key=lambda c: c["action_id"]):
        mark = "yes (verbatim)" if item.get("citation_verified") else "NO — UNVERIFIED"
        reason = item["reason"]
        print(f"  {item['action_id']:<5}{item['status'].upper():<11}{mark:<20}"
              f"{reason[:40]}{'...' if len(reason) > 40 else ''}")

    unverified = meta.get("unverified_citations", [])
    print()
    if unverified:
        print(f"  {len(unverified)} citation(s) could NOT be verified verbatim: {unverified}")
    else:
        print("  every citation was found verbatim in the retrieved NDMA text")
    return payload


def stage_policy(retrain: bool) -> bool:
    banner(5, "Policy  (MaskablePPO — excluded shelters are structurally unselectable)")

    if retrain and MODEL_PATH.exists():
        print("--retrain: discarding the existing checkpoint.")
        MODEL_PATH.unlink()

    if not MODEL_PATH.exists():
        print("No checkpoint — training now (about a minute on CPU)...\n")
        from src.env.train import main as train_main

        if train_main() != 0:
            return False
    else:
        print(f"Using existing checkpoint: {MODEL_PATH.relative_to(PROJECT_ROOT)}")
        print("  (pass --retrain to rebuild it)")
    return True


def stage_decision(payload) -> bool:
    banner(6, "Decision")
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.maskable.utils import get_action_masks

    from src.env.shelter_env import ShelterChoiceEnv

    model = MaskablePPO.load(MODEL_PATH, device="cpu")

    def run(env):
        obs, _ = env.reset()
        action, _ = model.predict(obs, action_masks=get_action_masks(env), deterministic=True)
        _, reward, _, _, info = env.step(int(action))
        return env.shelter_ids[int(action)], float(reward), info

    env = ShelterChoiceEnv(randomise=False, constraint_payload=payload)
    chosen, reward, info = run(env)

    # The same policy, with every shelter selectable. Computed, never hardcoded.
    env_open = ShelterChoiceEnv(randomise=False, constraint_payload=payload)
    env_open.fixed_mask = np.ones(env_open.n, dtype=bool)
    chosen_open, reward_open, _ = run(env_open)

    facts = {f["shelter_id"]: f for f in env.base_facts}
    cells = {c["cell_id"]: c for c in env.scenario["grid"]["cells"]}

    fact = facts[chosen]
    print(f"RECOMMENDED SHELTER : {chosen}")
    print(f"  cell {fact['cell_id']}, flood severity {fact['flood_severity']} "
          f"({cells[fact['cell_id']]['severity_band']})")
    print(f"  {fact['capacity_headroom']:,} spare places for "
          f"{env.population:,} evacuees, {fact['travel_cost_minutes']:g} min away")
    print(f"  policy score {reward:.4f}, regret {info['regret']:.4f}")

    print()
    print("-" * WIDTH)
    print("WHAT THE CONSTRAINT STEP IS ACTUALLY DOING")
    print("-" * WIDTH)
    open_fact = facts[chosen_open]
    open_band = cells[open_fact["cell_id"]]["severity_band"]
    print(f"  with the RAG-grounded constraints : {chosen}  "
          f"(severity {fact['flood_severity']}, score {reward:.4f})")
    print(f"  with NO constraints at all        : {chosen_open}  "
          f"(severity {open_fact['flood_severity']}, score {reward_open:.4f})")
    if chosen_open != chosen:
        print()
        print(f"  Unconstrained, the policy picks {chosen_open}: closest at "
              f"{open_fact['travel_cost_minutes']:g} min with room for all "
              f"{env.population:,}, so it scores highest on capacity and travel alone —")
        print(f"  but it sits in a {open_band.upper()} flood cell "
              f"(severity {open_fact['flood_severity']}). The constraint step is what "
              f"removes it.")
    else:
        print("\n  On this scenario the constraints do not change the choice.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Sentinel-Agent pipeline end to end.")
    parser.add_argument("--rebuild-index", action="store_true")
    parser.add_argument("--refresh-constraints", action="store_true")
    parser.add_argument("--retrain", action="store_true")
    args = parser.parse_args()

    print("=" * WIDTH)
    print("SENTINEL-AGENT SPRINT — end-to-end demo")
    print("Fictional scenario inspired by the 2018 Kerala floods; the guideline")
    print("document and every quoted clause are real. See README.md.")
    print("=" * WIDTH)

    from src.constraints.generate import CACHE_PATH

    needs_api = args.refresh_constraints or not CACHE_PATH.exists()

    if not stage_preflight(needs_api):
        return fail("preflight")
    stage_scenario()
    if not stage_corpus(args.rebuild_index):
        return fail("could not build the RAG corpus")
    payload = stage_constraints(args.refresh_constraints)
    if payload is None:
        return fail("constraint generation")
    if not stage_policy(args.retrain):
        return fail("policy training")
    if not stage_decision(payload):
        return fail("decision")

    print()
    print("=" * WIDTH)
    print("PIPELINE COMPLETE")
    print("=" * WIDTH)
    print("Launch the dashboard with:")
    print("    .venv/bin/streamlit run src/dashboard/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
