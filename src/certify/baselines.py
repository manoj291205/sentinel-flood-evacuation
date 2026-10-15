"""Baseline B (Phase 27): the industry / academic combination the certified gate is compared against.

(i) deterministic hazard filter (edges with current hazard >= 0.70 are treated as closed),
(ii) drop shelters that cannot hold the group now, (iii) independent Monte Carlo per candidate
(128 futures from a per-candidate root, mean joint success >= 0.95, no bound, no CRN).
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Callable

from src.geospatial import shortest_valid_path
from src.sim.events import WAIT, DispatchAction
from src.sim.transition import validate_action

from .certifier import CandidateCertificate, CertificationResult, Verdict
from .forecast import forecast_from_state
from .futures import FutureSet, root_key
from .gate import _horizon, canonical_paths, ledger_view_hash
from .ledger_view import ledger_view_from_state
from .rollout import HOLD_KEY, Candidate, rollout_joint

B_FUTURES = 128
B_THRESHOLD = 0.95
B_HAZARD_LIMIT = 0.70


def baseline_b_root(*, incident_id: str, forecast_hash: str, graph_fingerprint: str, ledger_hash: str,
                    action_key: str) -> str:
    """One independent root per candidate (no common random numbers)."""
    return root_key(incident_id=incident_id, forecast_hash=forecast_hash,
                    graph_fingerprint=graph_fingerprint, ledger_hash=ledger_hash,
                    params_id="baseline-b-v1:" + action_key)


class BaselineBPlanner:
    """Chooses a dispatch for one decision state; ``choose(state, road_state, snapshot, plans)``."""

    name = "baseline_b"

    def __init__(self, scenario, graph, world, params, *, rollout: Callable = rollout_joint,
                 futures_factory: Callable[..., Any] | None = None) -> None:
        self.scenario, self.graph, self.world, self.params = scenario, graph, world, params
        self.rollout = rollout
        self.futures_factory = futures_factory or FutureSet
        self.last_futures = 0

    def _safe_road_state(self, road_state):
        edges = tuple(
            dataclasses.replace(e, open=False) if e.hazard_severity >= B_HAZARD_LIMIT else e
            for e in road_state.edges
        )
        return dataclasses.replace(road_state, edges=edges)

    def choose(self, state, road_state, snapshot, plans=None):
        self.last_futures = 0
        t = state.current_timestep
        safe_state = self._safe_road_state(road_state)
        view = ledger_view_from_state(state, plans or {})
        fc = forecast_from_state(state, road_state, self.scenario)
        paths = canonical_paths(self.graph, road_state, self.scenario)
        edges = tuple(sorted({e for p in paths.values() for e in p}))
        horizon = _horizon(paths, self.graph, self.world, self.world.horizon_steps - t)
        ledger_hash = ledger_view_hash(view)
        cands = []
        for action in snapshot.allowed_actions:
            if not isinstance(action, DispatchAction):
                continue
            people = validate_action(self.scenario, state, action).people
            shelter = state.shelter(action.shelter_id)
            if people <= 0 or shelter.occupancy_current + shelter.capacity_reserved + people > shelter.capacity_total:
                continue  # (ii)
            path = shortest_valid_path(self.graph, safe_state, self.graph.zone_node_map[action.zone_id],
                                       self.graph.shelter_node_map[action.shelter_id])
            if not path.reachable:  # (i)
                continue
            cands.append((action, Candidate(action.zone_id, action.shelter_id, people, tuple(path.edge_ids), t)))
        edges = tuple(sorted(set(edges) | {e for _, c in cands for e in c.edge_ids}))
        best, best_utility = None, -math.inf
        for action, cand in cands:
            root = baseline_b_root(incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
                                   graph_fingerprint=self.graph.graph_fingerprint,
                                   ledger_hash=ledger_hash, action_key=cand.action_key)
            fs = self.futures_factory(fc, self.graph, self.world, root, horizon, edge_ids=edges)
            ok = total = 0
            for k in range(1, B_FUTURES + 1):
                r = self.rollout(cand, fs.future(k), view, self.world, self.params, self.graph)
                ok += bool(r.z)
                total += r.utility
            self.last_futures += B_FUTURES
            if ok / B_FUTURES >= B_THRESHOLD and total / B_FUTURES > best_utility:
                best, best_utility = action, total / B_FUTURES
        return best if best is not None else WAIT


def relax_fail_closed(result: CertificationResult) -> CertificationResult:
    """P-noFC: UNDECIDED candidates with point estimate >= 0.95 are treated as FEASIBLE."""
    cands = []
    for c in result.candidates:
        if c.verdict is Verdict.UNDECIDED and c.n > 0 and c.successes / c.n >= B_THRESHOLD:
            c = dataclasses.replace(c, verdict=Verdict.FEASIBLE)
        cands.append(c)
    feasible = [c for c in cands if c.verdict is Verdict.FEASIBLE]
    chosen = HOLD_KEY
    best = -math.inf
    for c in feasible:  # candidates are in sorted-key order: ties go to the earliest key
        if c.mean_utility > best:
            chosen, best = c.action_key, c.mean_utility
    return dataclasses.replace(result, candidates=tuple(cands), chosen_key=chosen)
