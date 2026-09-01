"""Decision strategies to measure the trained policy against.

A number like "91.5% optimal" means nothing without something to compare it to. These are
the comparisons.

A NOTE YOU SHOULD READ BEFORE INTERPRETING THE RESULTS
======================================================
In this environment the reward is FULLY COMPUTABLE from the observation:

    reward_i = 0.65 * min(headroom_i / population, 1) + 0.35 * (1 - travel_norm_i)

so `greedy_reward` -- argmax of that over the allowed set -- IS the oracle, by
construction. It cannot be beaten, and the trained RL policy cannot do better than tie
it.

That is not a flaw in the measurement; it is a true property of the problem as framed. On
a single-decision task with a known reward function, reinforcement learning is not
justified on performance grounds -- a two-line greedy rule is optimal and free. The
contextual-bandit framing is scaffolding for the multi-step, multi-shelter problem where
greedy stops being optimal. Report it that way.
"""

from __future__ import annotations

import numpy as np

from ..env.shelter_env import proxy_exclusion_rule


def _candidates(mask: np.ndarray) -> np.ndarray:
    """Indices selectable under the mask; falls back to all if the mask is empty."""
    idx = np.flatnonzero(mask)
    return idx if idx.size else np.arange(mask.size)


def random_allowed(facts, rewards, mask, rng) -> int:
    return int(rng.choice(_candidates(mask)))


def nearest_allowed(facts, rewards, mask, rng) -> int:
    idx = _candidates(mask)
    return int(idx[np.argmin([facts[i]["travel_cost_minutes"] for i in idx])])


def max_capacity_allowed(facts, rewards, mask, rng) -> int:
    idx = _candidates(mask)
    return int(idx[np.argmax([facts[i]["capacity_headroom"] for i in idx])])


def greedy_reward_allowed(facts, rewards, mask, rng) -> int:
    """Argmax of the computable reward over the allowed set. This IS the oracle."""
    idx = _candidates(mask)
    return int(idx[np.argmax([rewards[i] for i in idx])])


def nearest_unconstrained(facts, rewards, mask, rng) -> int:
    """Ignores the mask entirely -- the naive 'send them to the closest shelter' rule."""
    return int(np.argmin([f["travel_cost_minutes"] for f in facts]))


def greedy_unconstrained(facts, rewards, mask, rng) -> int:
    """Argmax reward with every shelter selectable -- no safety layer at all."""
    return int(np.argmax(rewards))


# Strategies that respect the constraint mask.
CONSTRAINED = {
    "random_allowed": random_allowed,
    "nearest_allowed": nearest_allowed,
    "max_capacity_allowed": max_capacity_allowed,
    "greedy_reward_allowed (= oracle)": greedy_reward_allowed,
}

# Strategies with NO safety layer -- these are what the constraint step is compared against.
UNCONSTRAINED = {
    "nearest_unconstrained": nearest_unconstrained,
    "greedy_unconstrained": greedy_unconstrained,
}


def is_unsafe(fact: dict) -> bool:
    """Deterministic safety condition: severe flooding, no headroom, or not operational.

    This is the same rule as the training-time proxy. It is NOT the LLM and NOT derived
    from the NDMA text -- it is the objective yardstick the LLM's verdicts get scored
    against in constraint_agreement.py.
    """
    return proxy_exclusion_rule(fact)


def violation_kinds(fact: dict) -> list[str]:
    kinds = []
    if fact["status"] != "operational":
        kinds.append("not_operational")
    if fact["flood_severity"] >= 0.70:
        kinds.append("severe_flood_cell")
    if fact["capacity_headroom"] < 1:
        kinds.append("no_headroom")
    return kinds
