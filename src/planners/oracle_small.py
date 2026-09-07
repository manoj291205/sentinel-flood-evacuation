"""Exhaustive clairvoyant upper bound for frozen small Gate 6 instances."""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any

from src.safety import evaluate_actions
from src.sim.events import SimulationAction
from src.sim.stochastic import StochasticSimulator

from .objective import EXPOSURE_WEIGHT, SAFE_WEIGHT, TRAVEL_WEIGHT, state_exposure

ORACLE_LABEL = "CLAIRVOYANT UPPER BOUND — NOT A PRACTICAL POLICY"
ORACLE_VERSION = "clairvoyant-oracle-small-v1"
ORACLE_TIMEOUT_SECONDS = 5.0


class OracleTimeout(RuntimeError):
    pass


@dataclass(frozen=True)
class OracleResult:
    label: str
    version: str
    utility: float
    actions: tuple[SimulationAction, ...]
    states_expanded: int
    branches_evaluated: int
    elapsed_ns: int
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "version": self.version,
            "utility": self.utility,
            "actions": [action.to_dict() for action in self.actions],
            "states_expanded": self.states_expanded,
            "branches_evaluated": self.branches_evaluated,
            "elapsed_ns": self.elapsed_ns,
            "timed_out": self.timed_out,
        }


def _utility(simulator, exposure: float, transit: float) -> float:
    state = simulator.state
    population = state.initial_evacuation_population
    denominator = population * simulator._scenario.time.horizon_steps
    return (
        SAFE_WEIGHT * (state.people_safely_arrived / population)
        - EXPOSURE_WEIGHT * (exposure / denominator)
        - TRAVEL_WEIGHT * (transit / denominator)
    )


def solve_clairvoyant(
    simulator: StochasticSimulator,
    *,
    timeout_seconds: float = ORACLE_TIMEOUT_SECONDS,
) -> OracleResult:
    """Search every realized safe sequence; private simulator access is oracle-only."""
    started = time.perf_counter_ns()
    deadline = started + int(timeout_seconds * 1_000_000_000)
    states_expanded = 0
    branches_evaluated = 0

    def search(sim, exposure, transit):
        nonlocal states_expanded, branches_evaluated
        if time.perf_counter_ns() > deadline:
            raise OracleTimeout("exact oracle exceeded its frozen deadline")
        if sim.state.terminal:
            return _utility(sim, exposure, transit), ()
        sim.observe()
        state = sim.prepared_state_for_debug()
        states_expanded += 1
        next_exposure = exposure + state_exposure(state)
        next_transit = transit + state.people_in_transit
        snapshot = evaluate_actions(sim._scenario, state)
        best_value = float("-inf")
        best_actions: tuple[SimulationAction, ...] = ()
        for evaluation in snapshot.evaluations:
            if not evaluation.final_allowed:
                continue
            branches_evaluated += 1
            child = copy.deepcopy(sim)
            result = child.step(evaluation.action)
            if not result.accepted:
                raise AssertionError("oracle safety snapshot disagrees with simulator")
            value, suffix = search(child, next_exposure, next_transit)
            if value > best_value + 1e-12:
                best_value = value
                best_actions = (evaluation.action,) + suffix
        return best_value, best_actions

    value, actions = search(copy.deepcopy(simulator), 0.0, 0.0)
    return OracleResult(
        label=ORACLE_LABEL,
        version=ORACLE_VERSION,
        utility=value,
        actions=actions,
        states_expanded=states_expanded,
        branches_evaluated=branches_evaluated,
        elapsed_ns=time.perf_counter_ns() - started,
    )
