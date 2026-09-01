"""Train the action-masked policy for shelter choice.

Uses MaskablePPO from sb3-contrib so excluded shelters are structurally unselectable
rather than merely penalised.

NOTE: during training the action mask comes from the deterministic proxy rule in
shelter_env.py, NOT from the Gemini constraint step -- see that module's docstring.

Run:  .venv/bin/python -m src.env.train
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.env_checker import check_env

from .shelter_env import ShelterChoiceEnv

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "maskable_ppo_shelter.zip"
# 40k. A 200k run was measured and gave 72% held-out optimal versus 40k's 73% --
# no gain for 5x the compute, so the policy has plateaued well below the oracle's
# 93%. See EVALUATION.md; this is evidence about the method, not a budget problem.
TOTAL_TIMESTEPS = 40_000
SEED = 7


def evaluate(model, episodes: int = 400, seed: int = 1234) -> dict:
    """Compare the policy against the oracle best-allowed choice."""
    env = ShelterChoiceEnv(randomise=True, seed=seed)
    optimal_hits = 0
    mask_violations = 0
    rewards, oracle_rewards = [], []

    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        masks = get_action_masks(env)
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        _, reward, _, _, info = env.step(action)

        rewards.append(reward)
        oracle_rewards.append(info["optimal_reward"])
        if not info["allowed"]:
            mask_violations += 1
        if int(action) == info["optimal_index"]:
            optimal_hits += 1

    return {
        "episodes": episodes,
        "optimal_rate": optimal_hits / episodes,
        "mean_reward": float(np.mean(rewards)),
        "oracle_mean_reward": float(np.mean(oracle_rewards)),
        "mean_regret": float(np.mean(np.array(oracle_rewards) - np.array(rewards))),
        "mask_violations": mask_violations,
    }


def main() -> int:
    env = ShelterChoiceEnv(randomise=True, seed=SEED)

    print("Checking the environment against the Gymnasium API...")
    check_env(env, warn=True, skip_render_check=True)
    print("  environment OK\n")

    print(f"Training MaskablePPO for {TOTAL_TIMESTEPS:,} timesteps (CPU)...")
    model = MaskablePPO("MlpPolicy", env, seed=SEED, verbose=0, device="cpu")
    model.learn(total_timesteps=TOTAL_TIMESTEPS, progress_bar=False)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    print(f"Saved checkpoint: {MODEL_PATH}\n")

    print("Evaluating against the oracle (best ALLOWED shelter) on fresh episodes...")
    stats = evaluate(model)
    print(f"  episodes evaluated : {stats['episodes']}")
    print(f"  picked the optimal allowed shelter : {stats['optimal_rate']*100:.1f}%")
    print(f"  mean reward        : {stats['mean_reward']:.4f}")
    print(f"  oracle mean reward : {stats['oracle_mean_reward']:.4f}")
    print(f"  mean regret        : {stats['mean_regret']:.4f}")
    print(f"  masked-action violations : {stats['mask_violations']}  (must be 0)")

    if stats["mask_violations"]:
        print("\nFAIL: the policy selected an excluded shelter. Masking is broken.")
        return 1

    print("\nNOTE: with only a handful of allowed actions per episode this is an easy")
    print("problem. A high optimal rate shows the wiring works; it is not evidence of")
    print("a sophisticated policy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
