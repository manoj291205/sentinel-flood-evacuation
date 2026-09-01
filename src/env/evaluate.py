"""Show example decisions from the trained policy, including on the REAL scenario.

The real-scenario run uses the action mask from the actual Step 3 Gemini output
(data/constraints_output.json), not the training-time proxy rule.

Run:  .venv/bin/python -m src.env.evaluate
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks

from ..constraints.generate import load_or_generate
from .shelter_env import ShelterChoiceEnv

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "maskable_ppo_shelter.zip"


def decide(model, env, seed: int | None = None):
    obs, _ = env.reset(seed=seed)
    masks = get_action_masks(env)
    action, _ = model.predict(obs, action_masks=masks, deterministic=True)
    _, reward, _, _, info = env.step(action)
    return int(action), reward, info, env


def main() -> int:
    if not MODEL_PATH.exists():
        print(f"No checkpoint at {MODEL_PATH}. Run:  .venv/bin/python -m src.env.train")
        return 1

    model = MaskablePPO.load(MODEL_PATH, device="cpu")

    # ---------------------------------------------------------------- the real scenario
    payload = load_or_generate(verbose=True)
    env = ShelterChoiceEnv(randomise=False, constraint_payload=payload)
    action, reward, info, env = decide(model, env)

    reasons = {c["action_id"]: c for c in payload["constraints"]}

    print()
    print("=" * 88)
    print("DECISION ON THE REAL SCENARIO  (mask from the actual Gemini constraint step)")
    print("=" * 88)
    header = f"{'ID':<5}{'mask':<12}{'severity':>9}{'headroom':>10}{'travel':>8}{'reward':>9}   note"
    print(header)
    print("-" * 88)
    for index, fact in enumerate(env.facts):
        allowed = env.mask[index]
        mark = "SELECTABLE" if allowed else "masked out"
        note = "<-- CHOSEN" if index == action else ""
        if not allowed:
            note = f"excluded: {reasons[fact['shelter_id']]['reason'][:34]}..."
        print(
            f"{fact['shelter_id']:<5}{mark:<12}{fact['flood_severity']:>9}"
            f"{fact['capacity_headroom']:>10}{fact['travel_cost_minutes']:>8}"
            f"{env.rewards[index]:>9.4f}   {note}"
        )

    chosen = env.shelter_ids[action]
    print()
    print(f"  RECOMMENDED SHELTER : {chosen}")
    print(f"  reward              : {reward:.4f}")
    print(f"  oracle best allowed : {info['optimal_shelter_id']} "
          f"(reward {info['optimal_reward']:.4f}), regret {info['regret']:.4f}")
    print(f"  chose an allowed shelter: {info['allowed']}")

    # ------------------------------------------------------------- randomised examples
    print()
    print("=" * 88)
    print("EXAMPLE DECISIONS ON RANDOMISED SCENARIOS  (mask from the training proxy rule)")
    print("=" * 88)
    print(f"{'#':<3}{'allowed set':<26}{'chose':<7}{'reward':>8}{'oracle':>9}{'regret':>8}   optimal?")
    print("-" * 88)

    rnd = ShelterChoiceEnv(randomise=True, seed=99)
    violations = 0
    for episode in range(8):
        action, reward, info, rnd = decide(model, rnd, seed=500 + episode)
        allowed_ids = [sid for sid, ok in zip(rnd.shelter_ids, rnd.mask) if ok]
        if not info["allowed"]:
            violations += 1
        print(
            f"{episode+1:<3}{','.join(allowed_ids):<26}{info['shelter_id']:<7}"
            f"{reward:>8.4f}{info['optimal_reward']:>9.4f}{info['regret']:>8.4f}"
            f"   {'yes' if info['regret'] < 1e-9 else 'no'}"
        )

    # ------------------------------------------------------------------ masking assertion
    print()
    print("Masking check over 1,000 random episodes...")
    check = ShelterChoiceEnv(randomise=True, seed=2024)
    picked_excluded = 0
    for episode in range(1000):
        obs, _ = check.reset(seed=10_000 + episode)
        masks = get_action_masks(check)
        act, _ = model.predict(obs, action_masks=masks, deterministic=True)
        if not check.mask[int(act)]:
            picked_excluded += 1
    print(f"  episodes where an EXCLUDED shelter was chosen: {picked_excluded}  (must be 0)")

    if picked_excluded or violations:
        print("\nFAIL: masking did not hold.")
        return 1
    print("  masking held: excluded shelters were structurally unselectable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
