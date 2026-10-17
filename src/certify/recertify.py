"""In-transit re-certification with hysteresis and migration (Phase 26, dependent claims 8, 9, 16).

A group is moved only on a *certified failure*: its remaining trip fails the looser keep test
(``1 - eps_keep``) with verdict INFEASIBLE, and at least one alternative is certified FEASIBLE at the
dispatch threshold. UNDECIDED keeps the group (fail-keep), never moves it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.geospatial import shortest_valid_path
from src.sim.transit import GroupPosition, TransitPlan

from .certifier import CertificationResult, Verdict, certify, paired_argmax
from .ledger_view import LedgerView
from .params import CertParams
from .rollout import Candidate, rollout_joint


@dataclass(frozen=True)
class RecertPolicy:
    cooldown_steps: int = 3
    max_migrations: int = 2


@dataclass(frozen=True)
class GroupHistory:
    migrations: int = 0
    last_migration_step: int | None = None
    left_shelters: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RecertDecision:
    event_id: str
    keep_verdict: Verdict
    keep_lower: float
    keep_upper: float
    action: str  # "KEEP" | "MIGRATE" | "KEEP_ESCALATE" | "COOLDOWN"
    new_shelter_id: str | None
    certificate: dict | None
    # Extras for the gate (not part of the pure contract; default None).
    alt_result: CertificationResult | None = None
    alternatives: tuple[Candidate, ...] = ()
    chosen_key: str | None = None


def keep_candidate(plan: TransitPlan, position: GroupPosition, graph: Any, *, timestep: int | None = None) -> Candidate:
    """The group's remaining trip to its current shelter, starting where it will next enter an edge."""
    return Candidate(
        zone_id=plan.zone_id, shelter_id=plan.shelter_id, people=plan.people,
        edge_ids=tuple(position.remaining_edge_ids),
        departure_timestep=plan.departure_timestep if timestep is None else timestep,
        start_minutes=position.at_minutes,
    )


def migration_candidates(
    plan: TransitPlan, position: GroupPosition, graph: Any, road_state: Any, scenario: Any,
    *, timestep: int, left_shelters: frozenset[str] = frozenset(),
) -> tuple[Candidate, ...]:
    """Shortest valid path from the group's next node to every shelter it has not left or occupies."""
    out = []
    for shelter in scenario.shelters:
        sid = shelter.shelter_id
        if sid == plan.shelter_id or sid in left_shelters:
            continue
        path = shortest_valid_path(graph, road_state, position.node_id, graph.shelter_node_map[sid])
        if not path.reachable:
            continue
        out.append(Candidate(plan.zone_id, sid, plan.people, tuple(path.edge_ids), timestep,
                             position.at_minutes))
    return tuple(out)


def recertify_group(
    event_id: str, keep: Candidate, alternatives: Sequence[Candidate], futures: Any, ledger: LedgerView,
    world: Any, params: CertParams, graph: Any, *, timestep: int, history: GroupHistory,
    policy: RecertPolicy = RecertPolicy(), rollout=rollout_joint,
) -> RecertDecision:
    """Pure core: no ledger writes. ``certificate`` is None (the gate builds it on commit)."""
    if history.migrations >= policy.max_migrations or (
        history.last_migration_step is not None
        and timestep - history.last_migration_step < policy.cooldown_steps
    ):
        return RecertDecision(event_id, Verdict.UNDECIDED, 0.0, 1.0, "COOLDOWN", None, None)
    keep_params = dataclasses.replace(params, eps_dispatch=params.eps_keep)
    kept = certify([keep], futures, ledger, world, keep_params, graph, rollout=rollout)
    cc = kept.candidates[0]
    if cc.verdict is not Verdict.INFEASIBLE:
        return RecertDecision(event_id, cc.verdict, cc.lower, cc.upper, "KEEP", None, None)
    allowed = tuple(
        a for a in alternatives
        if a.shelter_id != keep.shelter_id and a.shelter_id not in history.left_shelters
    )
    result = certify(allowed, futures, ledger, world, params, graph, rollout=rollout)
    feasible = [c.action_key for c in result.candidates if c.verdict is Verdict.FEASIBLE]
    if not feasible:
        return RecertDecision(event_id, cc.verdict, cc.lower, cc.upper, "KEEP_ESCALATE", None, None,
                              alt_result=result, alternatives=allowed)
    best = result.chosen_key
    shelter = next(a.shelter_id for a in allowed if a.action_key == best)
    return RecertDecision(event_id, cc.verdict, cc.lower, cc.upper, "MIGRATE", shelter, None,
                          alt_result=result, alternatives=allowed, chosen_key=best)


def recertify_in_transit(gate, state, road_state, plans: Mapping[str, TransitPlan],
                         histories: dict[str, GroupHistory], policy: RecertPolicy = RecertPolicy()):
    """Re-certify every in-transit group once, in event-id order; migrations commit through the gate."""
    from src.sim.events import DispatchStatus

    decisions = []
    for event in sorted(state.dispatch_events, key=lambda e: e.event_id):
        if event.status is not DispatchStatus.IN_TRANSIT or event.event_id not in plans:
            continue
        if event.arrival_timestep <= state.current_timestep:  # arrives this step: not re-certified
            continue
        history = histories.get(event.event_id, GroupHistory())
        decision = gate.recertify(state, road_state, plans[event.event_id], history, policy)
        if decision.action == "MIGRATE":
            histories[event.event_id] = GroupHistory(
                history.migrations + 1, state.current_timestep,
                history.left_shelters | {plans[event.event_id].shelter_id},
            )
        decisions.append(decision)
    return tuple(decisions)
