"""Joint first-hitting rollout (Phase 23, confidential core element C).

One candidate, one future: follow the group to its own arrival and report whether every edge
was open when entered, the shelter was safe at arrival and enough seats were free -- all in
the SAME future. Nothing here reads other candidates.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from src.geospatial.road_network import RoadGraph
from src.sim.configs import UncertaintyConfig
from src.sim.transit import edge_travel_minutes
from src.sim.world import V4WorldConfig, scaled_uncertainty

from .ledger_view import LedgerView
from .params import CertParams

HOLD_KEY = "WAIT"


@dataclass(frozen=True)
class Candidate:
    zone_id: str
    shelter_id: str
    people: int
    edge_ids: tuple[str, ...]
    departure_timestep: int
    start_minutes: float | None = None  # Phase 26 (in-transit groups); None = departure time

    @property
    def action_key(self) -> str:
        return f"{self.zone_id}->{self.shelter_id}"


class Outcome(str, Enum):
    OK = "OK"
    STRANDED = "STRANDED"
    UNSAFE = "UNSAFE"
    OVERFLOW = "OVERFLOW"


@dataclass(frozen=True)
class RolloutResult:
    z: bool
    outcome: Outcome
    arrival_timestep: int | None
    utility: float
    path_ok: bool
    shelter_ok: bool | None
    capacity_ok: bool | None


@lru_cache(maxsize=16)
def _config(world: V4WorldConfig) -> UncertaintyConfig:
    return scaled_uncertainty(world)


def _end(f) -> int:
    return f.start_timestep + f.steps


def _at(f, t: int) -> int:
    """Clamp a lookup step into the generated future (last known state persists)."""
    return min(t, _end(f))


def _utility(outcome: Outcome, people: int, params: CertParams) -> float:
    return {
        Outcome.OK: float(people),
        Outcome.STRANDED: -params.w_strand * people,
        Outcome.UNSAFE: -params.w_unsafe * people,
        Outcome.OVERFLOW: -params.w_overflow * people,
    }[outcome]


def _walk_path(c: Candidate, f, world: V4WorldConfig, graph: RoadGraph):
    """Return (path_ok, arrival_timestep or None)."""
    dt = world.timestep_minutes
    config = _config(world)
    t_min = c.departure_timestep * dt + world.boarding_minutes
    for edge_id in c.edge_ids:
        step = _at(f, math.ceil(t_min / dt))
        if not f.edge_open(edge_id, step):
            return False, None
        edge = graph.edges_by_id[edge_id]
        hazard = f.edge_hazard(edge_id, step)
        minutes = edge_travel_minutes(edge.length_m, edge.assumed_speed_kph, hazard, world)
        raw = 1.0 + config.travel_noise_fraction * f.travel_normal(
            c.departure_timestep, c.zone_id, c.shelter_id, edge_id
        )
        t_min += minutes * min(
            config.maximum_travel_multiplier, max(config.minimum_travel_multiplier, raw)
        )
    return True, max(c.departure_timestep + 1, math.ceil(t_min / dt))


def _shelter_safe(c: Candidate, f, arrival: int, params: CertParams) -> bool:
    t = _at(f, arrival)
    return not (
        f.shelter_status(c.shelter_id, t) == "CLOSED"
        or f.shelter_severity(c.shelter_id, t) >= params.theta_unsafe
    )


def _capacity_ok(c: Candidate, f, arrival: int, ledger: LedgerView, params: CertParams) -> bool:
    s = c.shelter_id
    reserved = sum(p for (_, sh, p, _) in ledger.pending if sh == s)
    walk = sum(
        f.walk_ins(s, t)
        for t in range(ledger.timestep + 1, _at(f, arrival) + 1)
        if f.start_timestep < t <= _end(f)
    )
    free = ledger.capacity_total[s] - ledger.occupancy[s] - reserved - walk
    margin = (
        params.k_sigma
        * ledger.occupancy_sigma.get(s, 0.0)
        * (1.0 + ledger.occupancy_age_s.get(s, 0.0) / params.age_scale_s)
    )
    return free >= c.people + margin


def _result(c: Candidate, params: CertParams, path_ok, arrival, shelter_ok, capacity_ok) -> RolloutResult:
    if not path_ok:
        outcome = Outcome.STRANDED
    elif not shelter_ok:
        outcome = Outcome.UNSAFE
    elif not capacity_ok:
        outcome = Outcome.OVERFLOW
    else:
        outcome = Outcome.OK
    return RolloutResult(
        z=outcome is Outcome.OK,
        outcome=outcome,
        arrival_timestep=arrival,
        utility=_utility(outcome, c.people, params),
        path_ok=path_ok,
        shelter_ok=shelter_ok,
        capacity_ok=capacity_ok,
    )


def rollout_joint(
    c: Candidate,
    f,
    ledger: LedgerView,
    world: V4WorldConfig,
    params: CertParams,
    graph: RoadGraph,
) -> RolloutResult:
    path_ok, arrival = _walk_path(c, f, world, graph)
    if not path_ok:
        return _result(c, params, False, None, None, None)
    shelter_ok = _shelter_safe(c, f, arrival, params)
    if not shelter_ok:
        return _result(c, params, True, arrival, False, None)
    return _result(c, params, True, arrival, True, _capacity_ok(c, f, arrival, ledger, params))


def rollout_components(
    c: Candidate,
    f_path,
    f_shelter,
    f_capacity,
    ledger: LedgerView,
    world: V4WorldConfig,
    params: CertParams,
    graph: RoadGraph,
) -> RolloutResult:
    """Ablation "marginal": the three conditions read from three different futures."""
    path_ok, arrival = _walk_path(c, f_path, world, graph)
    if not path_ok:
        return _result(c, params, False, None, None, None)
    shelter_ok = _shelter_safe(c, f_shelter, arrival, params)
    capacity_ok = _capacity_ok(c, f_capacity, arrival, ledger, params)
    return _result(c, params, True, arrival, shelter_ok, capacity_ok)


def candidate_key_for_no_crn(c: Candidate) -> str:
    """Ablation "no CRN": a per-candidate key that callers hash into a future-index offset."""
    raw = f"{c.action_key}|{c.departure_timestep}|{c.people}|{','.join(c.edge_ids)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
