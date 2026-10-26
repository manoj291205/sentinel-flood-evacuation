"""Depth-2/3 exhaustive expected-model lookahead planners."""

from __future__ import annotations

import time

from .base import CandidateScore, PlannerDecision, PlannerInput, timed
from .model import ModelState, terminal_action_estimates, terminal_estimate


class LookaheadPlanner:
    def __init__(self, depth: int) -> None:
        if depth not in (2, 3):
            raise ValueError("Gate 6 lookahead depth must be 2 or 3")
        self.depth = depth
        self.name = f"lookahead_k{depth}"
        self.version = f"lookahead-k{depth}-v2"

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision:
        started = time.perf_counter_ns()
        root = ModelState.from_input(planner_input)
        nodes = 0
        transitions = 0

        def search(state, remaining, exposure, transit):
            nonlocal nodes, transitions
            nodes += 1
            if remaining == 0 or state.timestep >= state.horizon:
                return terminal_estimate(state, exposure, transit)
            exposure += state.exposure()
            transit += state.transit
            actions = state.allowed_actions()
            if remaining == 1:
                values = terminal_action_estimates(
                    state, actions, exposure, transit
                )
                nodes += len(actions)
                transitions += len(actions)
                return max(values)
            best = float("-inf")
            for action in actions:
                transitions += 1
                child = state.advance(action)
                value = search(child, remaining - 1, exposure, transit)
                best = max(best, value)
            return best

        scores = []
        root_exposure = root.exposure()
        root_transit = root.transit
        for action in root.allowed_actions():
            transitions += 1
            child = root.advance(action)
            value = search(child, self.depth - 1, root_exposure, root_transit)
            scores.append(CandidateScore(action, value))
        best = max(item.total for item in scores)
        action = next(item.action for item in scores if item.total == best)
        return PlannerDecision(
            action=action,
            planner_name=self.name,
            planner_version=self.version,
            decision_latency_ns=timed(started),
            candidate_scores=tuple(scores),
            nodes_evaluated=nodes,
            model_transitions=transitions,
            explanation=f"Exhaustive observable expected-model depth {self.depth}.",
        )


class LookaheadK2Planner(LookaheadPlanner):
    def __init__(self) -> None:
        super().__init__(2)


class LookaheadK3Planner(LookaheadPlanner):
    def __init__(self) -> None:
        super().__init__(3)
