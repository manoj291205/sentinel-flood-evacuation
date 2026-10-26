"""Sampled observable-model MPC with planner-owned keyed randomness."""

from __future__ import annotations

import hashlib
import math
import time

from src.sim.events import WAIT, DispatchAction

from .base import CandidateScore, PlannerDecision, PlannerInput, timed
from .model import ModelState, terminal_estimate

MPC_SAMPLES = 16
MPC_HORIZON = 3
MPC_MASTER_SEED = 76001
MPC_RNG_VERSION = "v3-mpc-keyed-rng-v1"


def _uniform(*parts: object) -> float:
    payload = "\x1f".join(map(str, (MPC_RNG_VERSION, MPC_MASTER_SEED, *parts))).encode()
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return (value + 0.5) / 2**64


def _normal(*parts: object) -> float:
    u1 = max(_uniform(*parts, "a"), 1e-15)
    u2 = _uniform(*parts, "b")
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _risk_score(state: ModelState, action: DispatchAction) -> float:
    zone = state.zone(action.zone_id)
    shelter = state.shelter(action.shelter_id)
    route = state.route(action)
    assert zone is not None and shelter is not None and route is not None
    expected = float(route.expected_travel)
    uncertainty = float(route.uncertainty or 0.0)
    useful = min(state.vehicle_capacity, zone.population, shelter.available)
    return (
        0.30 * zone.severity
        + 0.20 * (1.0 - shelter.severity)
        + 0.25 * (useful / state.vehicle_capacity)
        + 0.10 * (1.0 - min(expected / (state.horizon * state.timestep_minutes), 1.0))
        + 0.10 * (1.0 - route.closure_probability)
        + 0.05 * (1.0 - min(uncertainty / expected, 1.0))
    )


def _continuation_action(state: ModelState):
    dispatches = [item for item in state.allowed_actions() if isinstance(item, DispatchAction)]
    if not dispatches:
        return WAIT
    scores = [(_risk_score(state, action), action) for action in dispatches]
    best = max(score for score, _ in scores)
    return next(action for score, action in scores if score == best)


class SampledMPCPlanner:
    name = "sampled_mpc"
    version = "sampled-mpc-n16-h3-v2"

    def __init__(self, planner_seed: int = MPC_MASTER_SEED) -> None:
        self.planner_seed = planner_seed

    def _sample_advance(
        self,
        state: ModelState,
        action,
        planner_input: PlannerInput,
        action_key: str,
        sample: int,
        modeled_step: int,
    ) -> ModelState:
        prefix = (
            self.planner_seed,
            planner_input.scenario_id,
            planner_input.current_timestep,
            action_key,
            sample,
            modeled_step,
        )
        config = planner_input.uncertainty_config
        zone_shocks = {
            item.zone_id: config.forecast_std_next * _normal(*prefix, "zone", item.zone_id)
            for item in state.zones
        }
        shelter_shocks = {
            item.shelter_id: config.forecast_std_next
            * _normal(*prefix, "shelter", item.shelter_id)
            for item in state.shelters
        }
        closed = frozenset(
            route.route_id
            for route in state.routes
            if route.reachable
            and _uniform(*prefix, "closure", route.route_id) < route.closure_probability
        )
        status_updates: dict[str, str] = {}
        for shelter in state.shelters:
            if shelter.status == "CLOSED":
                continue
            next_severity = min(
                1.0,
                max(
                    0.0,
                    (shelter.forecast if shelter.forecast is not None else shelter.severity)
                    + shelter_shocks[shelter.shelter_id],
                ),
            )
            if next_severity >= config.closed_threshold:
                status_updates[shelter.shelter_id] = "CLOSED"
            elif next_severity >= config.restricted_threshold and shelter.status == "OPEN":
                status_updates[shelter.shelter_id] = "RESTRICTED"
            elif _uniform(*prefix, "degrade", shelter.shelter_id) < min(
                1.0, config.shelter_degradation_probability * next_severity
            ):
                status_updates[shelter.shelter_id] = (
                    "RESTRICTED" if shelter.status == "OPEN" else "CLOSED"
                )
        multiplier = 1.0
        if isinstance(action, DispatchAction):
            route = state.route(action)
            assert route is not None and route.expected_travel is not None
            static_fraction = float(route.uncertainty or 0.0) / route.expected_travel
            multiplier = min(
                config.maximum_travel_multiplier,
                max(
                    config.minimum_travel_multiplier,
                    1.0 + static_fraction * _normal(*prefix, "travel", route.route_id),
                ),
            )
        return state.advance(
            action,
            travel_multiplier=multiplier,
            closed_route_ids=closed,
            zone_shocks=zone_shocks,
            shelter_shocks=shelter_shocks,
            shelter_status_updates=status_updates,
        )

    def choose_action(self, planner_input: PlannerInput) -> PlannerDecision:
        started = time.perf_counter_ns()
        root = ModelState.from_input(planner_input)
        scores: list[CandidateScore] = []
        transitions = 0
        nodes = 0
        for candidate in root.allowed_actions():
            key = "WAIT" if candidate == WAIT else f"{candidate.zone_id}->{candidate.shelter_id}"
            sample_values = []
            for sample in range(MPC_SAMPLES):
                state = root
                exposure = 0.0
                transit = 0.0
                action = candidate
                for modeled_step in range(MPC_HORIZON):
                    if state.timestep >= state.horizon:
                        break
                    nodes += 1
                    exposure += state.exposure()
                    transit += state.transit
                    state = self._sample_advance(
                        state,
                        action,
                        planner_input,
                        key,
                        sample,
                        modeled_step,
                    )
                    transitions += 1
                    action = _continuation_action(state)
                sample_values.append(terminal_estimate(state, exposure, transit))
            scores.append(CandidateScore(candidate, sum(sample_values) / len(sample_values)))
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
            explanation="Mean of 16 planner-owned sampled three-step futures.",
        )
