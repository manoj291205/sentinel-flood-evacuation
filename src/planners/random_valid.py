"""Independent-policy-RNG random-valid baseline."""

from __future__ import annotations

import random
import time

from .base import PlannerDecision, PlannerInput, allowed_actions, timed


class RandomValidPlanner:
    name = "random_valid"
    version = "random-valid-v1"

    def __init__(self, policy_seed: int) -> None:
        self.policy_seed = policy_seed
        self._rng = random.Random(policy_seed)

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision:
        started = time.perf_counter_ns()
        candidates = allowed_actions(planner_input)
        if not candidates:
            raise ValueError("random_valid received an empty executable action set")
        action = candidates[self._rng.randrange(len(candidates))]
        return PlannerDecision(
            action=action,
            planner_name=self.name,
            planner_version=self.version,
            decision_latency_ns=timed(started),
            explanation="Uniform sample from all currently allowed actions, including WAIT.",
        )
