"""Committed-seat view the rollout reads (never other candidates)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.sim.events import DispatchStatus
from src.sim.state import EpisodeState


@dataclass(frozen=True)
class LedgerView:
    timestep: int
    capacity_total: Mapping[str, int]
    occupancy: Mapping[str, int]
    reserved: Mapping[str, int]
    pending: tuple[tuple[str, str, int, int], ...]  # (event_id, shelter_id, people, arrival_timestep)
    occupancy_sigma: Mapping[str, float]  # 0.0 in simulation; HIL sensors fill it (Phase 28)
    occupancy_age_s: Mapping[str, float]


def ledger_view_from_state(state: EpisodeState, plans: Mapping[str, object] | None = None) -> LedgerView:
    """``plans`` is accepted for interface symmetry; arrival steps come from the event ledger."""
    pending = tuple(
        (e.event_id, e.destination_shelter_id, e.people, e.arrival_timestep)
        for e in state.dispatch_events
        if e.status is DispatchStatus.IN_TRANSIT
    )
    return LedgerView(
        timestep=state.current_timestep,
        capacity_total={s.shelter_id: s.capacity_total for s in state.shelters},
        occupancy={s.shelter_id: s.occupancy_current for s in state.shelters},
        reserved={s.shelter_id: s.capacity_reserved for s in state.shelters},
        pending=pending,
        occupancy_sigma={s.shelter_id: 0.0 for s in state.shelters},
        occupancy_age_s={s.shelter_id: 0.0 for s in state.shelters},
    )
