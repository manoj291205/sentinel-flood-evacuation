"""The ablation study: does the constraint layer actually change anything?

Replaces the project's single tuned anecdote ("without constraints it picks S1") with a
rate measured over the whole held-out suite.

MASK SOURCE: this study uses the DETERMINISTIC safety rule as the constraint mask for all
60 scenarios, because calling Gemini 60 times is slow and rate-limited on the free tier.
Numbers produced here are therefore about the *architecture* (does a constraint mask
change the outcome?), NOT about the LLM's accuracy. The LLM is scored separately, against
this same rule, in constraint_agreement.py. Never present these numbers as LLM numbers.

Run:  .venv/bin/python -m src.eval.run_study
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from ..constraints.generate import shelter_facts
from ..env.shelter_env import ShelterChoiceEnv, compute_rewards
from .baselines import CONSTRAINED, UNCONSTRAINED, is_unsafe, violation_kinds

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = PROJECT_ROOT / "data" / "eval_scenarios.json"
RESULTS_DIR = PROJECT_ROOT / "data" / "eval_results"
MODEL_PATH = PROJECT_ROOT / "models" / "maskable_ppo_shelter.zip"

WIDTH = 92


def load_suite() -> dict:
    if not SUITE_PATH.exists():
        raise FileNotFoundError(
            f"{SUITE_PATH} missing. Run: .venv/bin/python -m src.eval.generate_scenarios"
        )
    return json.loads(SUITE_PATH.read_text())


def rl_choice(model, scenario, mask) -> int:
    """The trained policy's pick under a given mask."""
    from sb3_contrib.common.maskable.utils import get_action_masks

    env = ShelterChoiceEnv(randomise=False, scenario=scenario)
    env.fixed_mask = mask.copy()
    obs, _ = env.reset()
    action, _ = model.predict(obs, action_masks=get_action_masks(env), deterministic=True)
    return int(action)


def main() -> int:
    suite = load_suite()
    scenarios = suite["scenarios"]
    rng = np.random.default_rng(4242)

    if not MODEL_PATH.exists():
        print(f"No checkpoint at {MODEL_PATH}. Run: .venv/bin/python -m src.env.train")
        return 1
    from sb3_contrib import MaskablePPO

    model = MaskablePPO.load(MODEL_PATH, device="cpu")

    strategies = dict(CONSTRAINED)
    strategies["rl_policy_allowed"] = None  # handled specially
    strategies.update(UNCONSTRAINED)
    strategies["rl_policy_unconstrained"] = None

    stats = {
        name: {"reward": [], "unsafe": 0, "optimal": 0, "kinds": {}}
        for name in strategies
    }
    per_scenario = []

    for scenario in scenarios:
        facts = shelter_facts(scenario)
        population = scenario["source"]["population_to_evacuate"]
        rewards = compute_rewards(facts, population)
        mask = np.array([not is_unsafe(f) for f in facts], dtype=bool)
        open_mask = np.ones(len(facts), dtype=bool)

        # The oracle: best reward among genuinely safe shelters (if any exist).
        if mask.any():
            best = float(np.max(np.where(mask, rewards, -np.inf)))
        else:
            best = float(np.max(rewards))

        row = {"scenario_id": scenario["scenario_id"], "regime": scenario["_regime"]}

        for name in strategies:
            if name == "rl_policy_allowed":
                choice = rl_choice(model, scenario, mask)
            elif name == "rl_policy_unconstrained":
                choice = rl_choice(model, scenario, open_mask)
            elif name in UNCONSTRAINED:
                choice = strategies[name](facts, rewards, open_mask, rng)
            else:
                choice = strategies[name](facts, rewards, mask, rng)

            fact = facts[choice]
            unsafe = is_unsafe(fact)
            stats[name]["reward"].append(float(rewards[choice]))
            stats[name]["unsafe"] += int(unsafe)
            if abs(float(rewards[choice]) - best) < 1e-6 and not unsafe:
                stats[name]["optimal"] += 1
            for kind in violation_kinds(fact):
                stats[name]["kinds"][kind] = stats[name]["kinds"].get(kind, 0) + 1
            row[name] = {"shelter": fact["shelter_id"], "unsafe": bool(unsafe)}

        per_scenario.append(row)

    n = len(scenarios)

    # ---------------------------------------------------------------- headline
    changed = sum(
        1 for r in per_scenario
        if r["rl_policy_allowed"]["shelter"] != r["rl_policy_unconstrained"]["shelter"]
    )
    unsafe_without = sum(1 for r in per_scenario if r["rl_policy_unconstrained"]["unsafe"])
    unsafe_with = sum(1 for r in per_scenario if r["rl_policy_allowed"]["unsafe"])

    print("=" * WIDTH)
    print(f"ABLATION STUDY — {n} held-out scenarios")
    print("Mask source: DETERMINISTIC safety rule (not the LLM). See module docstring.")
    print("=" * WIDTH)
    print()
    print("THE HEADLINE — what the constraint layer actually buys:")
    print(f"  scenarios where it changed the chosen shelter : {changed}/{n} "
          f"({changed / n * 100:.0f}%)")
    print(f"  UNSAFE pick WITHOUT the constraint layer      : {unsafe_without}/{n} "
          f"({unsafe_without / n * 100:.0f}%)")
    print(f"  UNSAFE pick WITH the constraint layer         : {unsafe_with}/{n} "
          f"({unsafe_with / n * 100:.0f}%)")

    regimes: dict[str, int] = {}
    for r in per_scenario:
        regimes[r["regime"]] = regimes.get(r["regime"], 0) + 1
    unsafe_with_by_regime: dict[str, int] = {}
    for r in per_scenario:
        if r["rl_policy_allowed"]["unsafe"]:
            unsafe_with_by_regime[r["regime"]] = unsafe_with_by_regime.get(r["regime"], 0) + 1
    if unsafe_with:
        print()
        print("  The residual unsafe picks WITH constraints, by regime:")
        for regime, count in sorted(unsafe_with_by_regime.items()):
            print(f"    {regime:<18} {count}/{regimes[regime]}")
        print("    (in 'no_safe_shelter' scenarios every option is unsafe, so the mask")
        print("     cannot help -- this is why those cases were included.)")

    # ---------------------------------------------------------------- table
    print()
    print("=" * WIDTH)
    print("STRATEGY COMPARISON")
    print("=" * WIDTH)
    header = (f"{'strategy':<34}{'mean reward':>13}{'optimal':>11}"
              f"{'UNSAFE picks':>15}{'  top violation'}")
    print(header)
    print("-" * WIDTH)
    for name in strategies:
        s = stats[name]
        mean = float(np.mean(s["reward"]))
        top = max(s["kinds"].items(), key=lambda kv: kv[1])[0] if s["kinds"] else "-"
        marker = "  <-- no safety layer" if name in UNCONSTRAINED or name.endswith("unconstrained") else ""
        print(f"{name:<34}{mean:>13.4f}{s['optimal'] / n * 100:>10.0f}%"
              f"{s['unsafe']:>10}/{n}  {top}{marker}")

    print()
    print("READING THIS TABLE")
    print("  * 'greedy_reward_allowed' IS the oracle -- the reward is fully computable,")
    print("    so it cannot be beaten and the RL policy can at best tie it. On this")
    print("    single-decision task RL is NOT justified on performance grounds; the")
    print("    framing is scaffolding for the multi-step problem where greedy fails.")
    print("  * 'nearest_unconstrained' is the naive baseline a system without this")
    print("    project would use. Its UNSAFE count is the case for the constraint layer.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "ablation_study.json"
    out.write_text(json.dumps(
        {
            "_note": (
                "Mask source is the DETERMINISTIC safety rule, not the LLM. These "
                "measure the architecture, not the LLM's accuracy."
            ),
            "n_scenarios": n,
            "suite_seed": suite["_seed"],
            "headline": {
                "changed_choice": changed,
                "unsafe_without_constraints": unsafe_without,
                "unsafe_with_constraints": unsafe_with,
            },
            "strategies": {
                name: {
                    "mean_reward": float(np.mean(s["reward"])),
                    "optimal_rate": s["optimal"] / n,
                    "unsafe_picks": s["unsafe"],
                    "violation_kinds": s["kinds"],
                }
                for name, s in stats.items()
            },
            "per_scenario": per_scenario,
        },
        indent=2,
    ) + "\n")
    print(f"\nWrote {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
