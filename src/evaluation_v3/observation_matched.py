"""A one-step heuristic restricted to the exact 384-value PPO observation."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from src.env_v3 import FixedActionMap


OBSERVATION_MATCHED_WEIGHTS = {
    "source_urgency": 0.30,
    "destination_safety": 0.20,
    "capacity_fraction": 0.25,
    "travel": 0.10,
    "closure_safety": 0.10,
    "travel_certainty": 0.05,
}


@dataclass(frozen=True)
class ObservationMatchedDecision:
    action_index: int
    decision_latency_ns: int


class ObservationMatchedGreedy:
    """Stateless scoring from flat observation, fixed mapping, and mask only."""

    name = "observation_matched_greedy"
    version = "observation-matched-greedy-v1"

    def choose_action(
        self,
        observation: np.ndarray,
        action_mask: np.ndarray,
        action_mapping: FixedActionMap,
    ) -> ObservationMatchedDecision:
        started = time.perf_counter_ns()
        values = np.asarray(observation, dtype=float)
        mask = np.asarray(action_mask, dtype=bool)
        if values.shape != (384,) or mask.shape != (55,):
            raise ValueError("observation-matched planner requires shapes (384,) and (55,)")
        best_index = action_mapping.config.wait_index
        best_score = -float("inf")
        for index in range(action_mapping.config.dispatch_slots):
            if not mask[index]:
                continue
            zone_slot, shelter_slot = divmod(index, action_mapping.config.max_shelters)
            zone_base = zone_slot * 6
            shelter_base = 36 + shelter_slot * 8
            route_base = 108 + index * 5
            components = {
                "source_urgency": values[zone_base + 2],
                "destination_safety": 1.0 - values[shelter_base + 4],
                "capacity_fraction": values[shelter_base + 1],
                "travel": 1.0 - values[route_base + 2],
                "closure_safety": 1.0 - values[route_base + 4],
                "travel_certainty": 1.0 - values[route_base + 3],
            }
            score = sum(
                OBSERVATION_MATCHED_WEIGHTS[name] * component
                for name, component in components.items()
            )
            if score > best_score:
                best_score = score
                best_index = index
        return ObservationMatchedDecision(best_index, time.perf_counter_ns() - started)
