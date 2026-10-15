"""Planner that executes the certifier's chosen action (Phase 24, confidential)."""

from __future__ import annotations

import time
from typing import Callable

from src.certify.certifier import CertificationResult
from src.sim.events import WAIT, DispatchAction

from .base import CandidateScore, PlannerDecision, PlannerInput, allowed_dispatches, timed


class CertifiedPlanner:
    name = "certified_v4"
    version = "certified-v4"

    def __init__(self, certify_fn: Callable[[PlannerInput], CertificationResult]) -> None:
        self._certify = certify_fn

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision:
        started = time.perf_counter_ns()
        result = self._certify(planner_input)
        by_key = {f"{a.zone_id}->{a.shelter_id}": a for a in allowed_dispatches(planner_input)}
        action = by_key.get(result.chosen_key, WAIT)
        if not isinstance(action, DispatchAction):
            action = WAIT
        scores = tuple(
            CandidateScore(by_key[c.action_key], c.mean_utility, (("lower_bound", c.lower),))
            for c in result.candidates
            if c.action_key in by_key
        )
        return PlannerDecision(
            action=action,
            planner_name=self.name,
            planner_version=self.version,
            decision_latency_ns=timed(started),
            candidate_scores=scores,
            explanation=(
                f"certified {result.chosen_key} (n={result.n_final}, looks={result.looks})"
                if action is not WAIT
                else "no candidate certified feasible; HOLD"
            ),
        )
