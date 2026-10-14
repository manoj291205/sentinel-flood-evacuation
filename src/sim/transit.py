"""Multi-step transit plans, failures and walk-ins for v4 worlds (Phase 21).

Everything here is a SIMULATION MODELING ASSUMPTION. Randomness is keyed by
(departure step, zone, shelter, edge) -- never by an event sequence number or a candidate
index -- so Phase 22/23 can reproduce the same draw for a hypothetical dispatch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Any

from .configs import UncertaintyConfig
from .events import AuditEventType, AuditRecord, DispatchEvent, DispatchStatus
from .randomness import EpisodeRandomStreams, RandomStream
from .state import EpisodeState
from .schemas import ShelterStatus

if TYPE_CHECKING:  # pragma: no cover
    from .world import V4WorldConfig


class TransitOutcome(str, Enum):
    ARRIVED = "ARRIVED"
    STRANDED = "STRANDED"
    ARRIVAL_UNSAFE = "ARRIVAL_UNSAFE"
    ARRIVAL_OVERFLOW = "ARRIVAL_OVERFLOW"


@dataclass(frozen=True)
class TransitPlan:
    event_id: str
    zone_id: str
    shelter_id: str
    people: int
    departure_timestep: int
    edge_ids: tuple[str, ...]
    edge_entry_minutes: tuple[float, ...]  # absolute simulated minutes
    arrival_minutes: float
    timestep_minutes: float = 2.0

    @property
    def arrival_timestep(self) -> int:
        duration = self.arrival_minutes - self.departure_timestep * self.timestep_minutes
        return self.departure_timestep + max(1, math.ceil(duration / self.timestep_minutes))


@dataclass(frozen=True)
class TransitRealization:
    plan: TransitPlan
    base_minutes: float  # boarding + noise-free movement
    realized_minutes: float  # boarding + realized movement
    multiplier: float


def edge_travel_minutes(
    length_m: float,
    assumed_speed_kph: float,
    hazard: float,
    world: "V4WorldConfig",
) -> float:
    speed = min(assumed_speed_kph, world.evacuation_speed_cap_kph) * (
        1.0 - world.flood_speed_reduction * hazard
    )
    speed = max(speed, 0.5)
    return (length_m / 1000.0) / speed * 60.0


def build_transit_plan(
    *,
    graph: Any,
    road_state: Any,
    path_edge_ids: tuple[str, ...],
    event_id: str,
    zone_id: str,
    shelter_id: str,
    people: int,
    departure_timestep: int,
    world: "V4WorldConfig",
    config: UncertaintyConfig,
    streams: EpisodeRandomStreams,
) -> TransitRealization:
    """Plan a trip along ``path_edge_ids`` using the road state at dispatch time."""
    start = departure_timestep * world.timestep_minutes + world.boarding_minutes
    clock = start
    base_clock = start
    entries: list[float] = []
    for edge_id in path_edge_ids:
        edge = graph.edges_by_id[edge_id]
        hazard = road_state.edge(edge_id).hazard_severity
        minutes = edge_travel_minutes(edge.length_m, edge.assumed_speed_kph, hazard, world)
        raw = 1.0 + config.travel_noise_fraction * streams.normal(
            RandomStream.TRAVEL, departure_timestep, zone_id, shelter_id, edge_id
        )
        multiplier = min(
            config.maximum_travel_multiplier, max(config.minimum_travel_multiplier, raw)
        )
        entries.append(clock)
        clock += minutes * multiplier
        base_clock += minutes
    plan = TransitPlan(
        event_id=event_id,
        zone_id=zone_id,
        shelter_id=shelter_id,
        people=people,
        departure_timestep=departure_timestep,
        edge_ids=tuple(path_edge_ids),
        edge_entry_minutes=tuple(entries),
        arrival_minutes=clock,
        timestep_minutes=world.timestep_minutes,
    )
    moving_base = base_clock - start
    moving_real = clock - start
    return TransitRealization(
        plan=plan,
        base_minutes=world.boarding_minutes + moving_base,
        realized_minutes=world.boarding_minutes + moving_real,
        multiplier=(moving_real / moving_base) if moving_base > 0 else 1.0,
    )


def _release(state: EpisodeState, shelter_id: str, people: int) -> tuple:
    return tuple(
        replace(s, capacity_reserved=s.capacity_reserved - people)
        if s.shelter_id == shelter_id
        else s
        for s in state.shelters
    )


def process_v4_transit(
    state: EpisodeState,
    plans: tuple[TransitPlan, ...],
    road_state: Any,
    config: UncertaintyConfig,
    world: "V4WorldConfig",
) -> tuple[EpisodeState, tuple[DispatchEvent, ...], tuple[AuditRecord, ...]]:
    """Strand, then arrive/refuse/overflow every in-transit group for ``state.current_timestep``."""
    t = state.current_timestep
    dt = world.timestep_minutes
    by_id = {plan.event_id: plan for plan in plans}
    events = list(state.dispatch_events)
    stranded = state.people_stranded
    unsafe = state.people_unsafe_arrival
    overflow = state.people_overflow
    safe = state.people_safely_arrived
    records: list[AuditRecord] = []
    changed: list[DispatchEvent] = []
    working = state
    closed = (
        {e.edge_id for e in road_state.edges if not e.open} if road_state is not None else set()
    )
    for index, event in enumerate(events):
        if event.status is not DispatchStatus.IN_TRANSIT:
            continue
        plan = by_id.get(event.event_id)
        if plan is None:
            continue
        hit = next(
            (
                edge_id
                for edge_id, entry in zip(plan.edge_ids, plan.edge_entry_minutes)
                if (t - 1) * dt < entry <= t * dt and edge_id in closed
            ),
            None,
        )
        if hit is not None:
            updated = replace(event, status=DispatchStatus.STRANDED)
            events[index] = updated
            changed.append(updated)
            working = replace(
                working, shelters=_release(working, event.destination_shelter_id, event.people)
            )
            stranded += event.people
            records.append(
                AuditRecord(
                    event_type=AuditEventType.GROUP_STRANDED,
                    timestep=t,
                    event_id=event.event_id,
                    zone_id=event.source_zone_id,
                    shelter_id=event.destination_shelter_id,
                    route_id=hit,
                    people=event.people,
                    reason_code="EDGE_CLOSED_ON_ROUTE",
                    message="an edge on the dispatched path closed before the group entered it",
                )
            )
            continue
        if event.arrival_timestep != t:
            continue
        working = replace(
            working, shelters=_release(working, event.destination_shelter_id, event.people)
        )
        shelter = working.shelter(event.destination_shelter_id)
        assert shelter is not None
        if (
            shelter.status_current is ShelterStatus.CLOSED
            or shelter.flood_severity_current >= config.closed_threshold
        ):
            updated = replace(event, status=DispatchStatus.ARRIVAL_UNSAFE)
            unsafe += event.people
            records.append(
                AuditRecord(
                    event_type=AuditEventType.ARRIVAL_UNSAFE,
                    timestep=t,
                    event_id=event.event_id,
                    zone_id=event.source_zone_id,
                    shelter_id=event.destination_shelter_id,
                    people=event.people,
                    value_after=shelter.flood_severity_current,
                    reason_code="SHELTER_UNSAFE_AT_ARRIVAL",
                    message="shelter was closed or too flooded when the group arrived",
                )
            )
        else:
            room = max(0, shelter.capacity_total - shelter.occupancy_current)
            admitted = min(event.people, room)
            working = replace(
                working,
                shelters=tuple(
                    replace(s, occupancy_current=s.occupancy_current + admitted)
                    if s.shelter_id == shelter.shelter_id
                    else s
                    for s in working.shelters
                ),
            )
            safe += admitted
            if admitted == event.people:
                updated = replace(event, status=DispatchStatus.ARRIVED)
                records.append(
                    AuditRecord(
                        event_type=AuditEventType.ARRIVAL_PROCESSED,
                        timestep=t,
                        event_id=event.event_id,
                        zone_id=event.source_zone_id,
                        shelter_id=event.destination_shelter_id,
                        people=admitted,
                        reason_code="SCHEDULED_ARRIVAL_DUE",
                        message="evacuees arrived and were admitted",
                    )
                )
            else:
                updated = replace(event, status=DispatchStatus.ARRIVAL_OVERFLOW)
                overflow += event.people - admitted
                records.append(
                    AuditRecord(
                        event_type=AuditEventType.ARRIVAL_OVERFLOW,
                        timestep=t,
                        event_id=event.event_id,
                        zone_id=event.source_zone_id,
                        shelter_id=event.destination_shelter_id,
                        people=event.people - admitted,
                        value_after=float(admitted),
                        reason_code="RESERVED_SEATS_TAKEN_BY_WALK_INS",
                        message="shelter filled before the group arrived; excess not admitted",
                    )
                )
        events[index] = updated
        changed.append(updated)
    if not changed:
        return state, (), ()
    result = replace(
        working,
        dispatch_events=tuple(events),
        people_safely_arrived=safe,
        people_stranded=stranded,
        people_unsafe_arrival=unsafe,
        people_overflow=overflow,
        audit_log=working.audit_log + tuple(records),
    )
    arrived = tuple(e for e in changed if e.status is not DispatchStatus.STRANDED)
    return result, arrived, tuple(records)


def walk_in_demand(
    streams: Any, world: "V4WorldConfig", t: int, shelter_id: str, mean_hazard: float
) -> int:
    """Unconstrained keyed walk-in count for one shelter and step."""
    u = streams.uniform(RandomStream.WALK_IN, t, shelter_id)
    return math.floor(world.walk_in_rate * mean_hazard * 2.0 * u)


def apply_walk_ins(
    state: EpisodeState,
    streams: EpisodeRandomStreams,
    world: "V4WorldConfig",
) -> tuple[EpisodeState, tuple[AuditRecord, ...]]:
    """Keyed walk-ins raise occupancy but not reservations (so reserved seats can be lost)."""
    t = state.current_timestep
    if not state.zones:
        return state, ()
    mean_hazard = sum(z.flood_severity_current for z in state.zones) / len(state.zones)
    shelters = []
    records: list[AuditRecord] = []
    for shelter in state.shelters:
        if shelter.status_current is ShelterStatus.CLOSED:
            shelters.append(shelter)
            continue
        want = walk_in_demand(streams, world, t, shelter.shelter_id, mean_hazard)
        count = max(0, min(want, shelter.capacity_total - shelter.occupancy_current))
        if count > 0:
            records.append(
                AuditRecord(
                    event_type=AuditEventType.WALK_IN,
                    timestep=t,
                    shelter_id=shelter.shelter_id,
                    people=count,
                    reason_code="KEYED_SYNTHETIC_WALK_IN",
                    message="unplanned evacuees walked into the shelter",
                )
            )
            shelter = replace(shelter, occupancy_current=shelter.occupancy_current + count)
        shelters.append(shelter)
    if not records:
        return state, ()
    return (
        replace(state, shelters=tuple(shelters), audit_log=state.audit_log + tuple(records)),
        tuple(records),
    )
