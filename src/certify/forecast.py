"""What keyed futures may condition on: an observation-only forecast snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from src.sim.schemas import ScenarioV3
from src.sim.state import EpisodeState


def _canonical(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


@dataclass(frozen=True)
class ForecastSnapshot:
    incident_id: str
    timestep: int
    timestep_minutes: float
    uncertainty_config_id: str
    zone_severity: tuple[tuple[str, float], ...]
    zone_trend: tuple[tuple[str, str], ...]
    shelter_severity: tuple[tuple[str, float], ...]
    shelter_status: tuple[tuple[str, str], ...]
    edge_open: tuple[tuple[str, bool], ...]
    regional_shock_estimate: float = 0.0  # v1: the latent regional state is NOT read
    graph_fingerprint: str = ""

    def forecast_hash(self) -> str:
        payload = _canonical(
            [
                self.incident_id,
                self.timestep,
                self.timestep_minutes,
                self.uncertainty_config_id,
                self.zone_severity,
                self.zone_trend,
                self.shelter_severity,
                self.shelter_status,
                self.edge_open,
                self.regional_shock_estimate,
                self.graph_fingerprint,
            ]
        )
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def forecast_from_state(
    state: EpisodeState, road_state: Any, scenario: ScenarioV3
) -> ForecastSnapshot:
    trends = {zone.zone_id: zone.initial_severity_trend.value for zone in scenario.zones}
    return ForecastSnapshot(
        incident_id=f"KOCHI-SIM-{scenario.seed}",
        timestep=state.current_timestep,
        timestep_minutes=scenario.time.timestep_minutes,
        uncertainty_config_id=state.uncertainty_config_id or "",
        zone_severity=tuple((z.zone_id, z.flood_severity_current) for z in state.zones),
        zone_trend=tuple((z.zone_id, trends[z.zone_id]) for z in state.zones),
        shelter_severity=tuple((s.shelter_id, s.flood_severity_current) for s in state.shelters),
        shelter_status=tuple((s.shelter_id, s.status_current.value) for s in state.shelters),
        edge_open=tuple((e.edge_id, bool(e.open)) for e in road_state.edges),
        regional_shock_estimate=0.0,
        graph_fingerprint=road_state.graph_fingerprint,
    )


def ledger_hash(state: EpisodeState) -> str:
    """Hash of the commitments a certificate depends on: occupancy, reservations, pending groups."""
    payload = [
        [[s.shelter_id, s.occupancy_current, s.capacity_reserved] for s in state.shelters],
        [
            [e.event_id, e.people, e.destination_shelter_id, e.arrival_timestep]
            for e in state.pending_dispatches
        ],
    ]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
