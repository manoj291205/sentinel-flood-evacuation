"""Frozen paired dynamic interventions for Phase 10 stress-only evaluation."""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace

from src.sim import AuditEventType, AuditRecord, EpisodeState, ScenarioV3, ShelterStatus


def _rank(scenario: ScenarioV3, route_id: str) -> bytes:
    return hashlib.sha256(f"phase10-cascade-v1|{scenario.seed}|{route_id}".encode()).digest()


def apply_stress_intervention(
    scenario: ScenarioV3,
    state: EpisodeState,
    stress_type: str,
) -> tuple[EpisodeState, tuple[AuditRecord, ...]]:
    if state.current_timestep != 3 or stress_type in {"demand_shift", "longer_travel_lags"}:
        return state, ()
    records: list[AuditRecord] = []
    if stress_type == "sudden_flood_surge":
        zones = tuple(replace(item, flood_severity_current=min(1.0, item.flood_severity_current + 0.18)) for item in state.zones)
        shelters = tuple(replace(item, flood_severity_current=min(1.0, item.flood_severity_current + 0.10)) for item in state.shelters)
        records.append(AuditRecord(AuditEventType.FLOOD_STATE_UPDATED, 3, reason_code="PHASE10_SUDDEN_FLOOD_SURGE", message="paired stress-only hazard shock"))
        return replace(state, zones=zones, shelters=shelters), tuple(records)
    if stress_type == "route_closure_cascade":
        initially_reachable = [item.route_id for item in scenario.network.routes if item.reachable]
        count = max(1, math.ceil(0.35 * len(initially_reachable)))
        selected = set(sorted(initially_reachable, key=lambda item: _rank(scenario, item))[:count])
        routes = []
        for route in state.routes:
            close = route.route_id in selected and route.reachable_current
            routes.append(replace(route, reachable_current=False, closed_at_timestep=3) if close else route)
            if close:
                records.append(AuditRecord(AuditEventType.ROUTE_CLOSED, 3, route_id=route.route_id, reason_code="PHASE10_CORRELATED_CLOSURE_CASCADE", message="paired stress-only route closure"))
        return replace(state, routes=tuple(routes)), tuple(records)
    if stress_type == "shelter_failure":
        target = min(scenario.shelters, key=lambda item: (-item.capacity_total, item.shelter_id)).shelter_id
        shelters = tuple(replace(item, status_current=ShelterStatus.CLOSED) if item.shelter_id == target else item for item in state.shelters)
        records.append(AuditRecord(AuditEventType.SHELTER_CLOSED, 3, shelter_id=target, reason_code="PHASE10_HIGH_CAPACITY_SHELTER_FAILURE", message="paired stress-only forced closure"))
        return replace(state, shelters=shelters), tuple(records)
    raise ValueError(f"unknown stress type {stress_type!r}")
