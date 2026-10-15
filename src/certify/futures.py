"""Keyed future generator (Phase 22, confidential core element B).

Futures are generated from a forecast snapshot only. Every draw is keyed by
(root, k, stream, absolute timestep, entity): never by draw order, candidate index or the
number of candidates evaluated. The unchanged live dynamics run as the future dynamics by
passing a duck-typed stream object.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import Any

from src.geospatial.road_network import DynamicRoadEdge, RoadGraph, RoadState, derive_road_state
from src.sim.configs import get_uncertainty_config
from src.sim.hazard import evolve_flood_state
from src.sim.randomness import RandomStream
from src.sim.schemas import ShelterStatus, Trend
from src.sim.state import EpisodeState, ShelterState, ZoneState
from src.sim.stochastic import degrade_shelter_status
from src.sim.transit import walk_in_demand
from src.sim.world import V4WorldConfig

from .forecast import ForecastSnapshot

CERT_KEY_VERSION = "sentinel-cert-v1"
FUTURE_DIGEST_TAG = "sentinel-cert-future-v1"
BACKENDS = ("sha256", "philox")


def root_key(
    *,
    incident_id: str,
    forecast_hash: str,
    graph_fingerprint: str,
    ledger_hash: str,
    params_id: str,
    backend: str = "sha256",
) -> str:
    payload = [
        CERT_KEY_VERSION,
        incident_id,
        forecast_hash,
        graph_fingerprint,
        ledger_hash,
        params_id,
        backend,
    ]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FutureStreams:
    """Duck-types ``EpisodeRandomStreams`` for future ``k`` under certificate root ``root``."""

    def __init__(self, root: str, k: int, config_id: str) -> None:
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("future index k must be an integer >= 1")
        self.root = root
        self.k = k
        self.root_seed = int(root[:15], 16)  # read-only convenience; never used for draws
        self.config_id = config_id
        self.replication_id = k

    def _digest(self, stream: RandomStream, key: tuple[Any, ...], lane: int) -> bytes:
        payload = json.dumps(
            [FUTURE_DIGEST_TAG, self.root, self.k, stream.value, list(key), lane],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).digest()

    def uniform(self, stream: RandomStream, *key: Any) -> float:
        return int.from_bytes(self._digest(stream, key, 0)[:8], "big") / 2**64

    def normal(self, stream: RandomStream, *key: Any) -> float:
        import math

        first = int.from_bytes(self._digest(stream, key, 0)[:8], "big")
        second = int.from_bytes(self._digest(stream, key, 1)[:8], "big")
        u1 = (first + 1) / (2**64 + 1)
        u2 = (second + 1) / (2**64 + 1)
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


@dataclass(frozen=True)
class _TrajectoryData:
    edge_index: dict[str, int]
    open_by_t: dict[int, tuple[bool, ...]]
    hazard_by_t: dict[int, tuple[float, ...]]
    shelter_severity_by_t: dict[int, dict[str, float]]
    shelter_status_by_t: dict[int, dict[str, str]]
    walk_ins_by_t: dict[int, dict[str, int]]


@dataclass(frozen=True)
class FutureTrajectory:
    """Exogenous world for one future; no candidate dispatch enters it."""

    k: int
    start_timestep: int
    steps: int
    streams: FutureStreams = field(repr=False, compare=False)
    data: _TrajectoryData = field(repr=False, compare=False)

    def _check(self, t: int) -> None:
        if not self.start_timestep <= t <= self.start_timestep + self.steps:
            raise ValueError(f"timestep {t} outside future [{self.start_timestep}, "
                             f"{self.start_timestep + self.steps}]")

    def edge_open(self, edge_id: str, t: int) -> bool:
        self._check(t)
        return self.data.open_by_t[t][self.data.edge_index[edge_id]]

    def edge_hazard(self, edge_id: str, t: int) -> float:
        self._check(t)
        if t == self.start_timestep:  # the snapshot carries no hazards: use the first future step
            if self.steps == 0:
                raise ValueError("edge hazard is not part of the forecast snapshot")
            t = t + 1
        return self.data.hazard_by_t[t][self.data.edge_index[edge_id]]

    def shelter_severity(self, shelter_id: str, t: int) -> float:
        self._check(t)
        return self.data.shelter_severity_by_t[t][shelter_id]

    def shelter_status(self, shelter_id: str, t: int) -> str:
        self._check(t)
        return self.data.shelter_status_by_t[t][shelter_id]

    def walk_ins(self, shelter_id: str, t: int) -> int:
        """Unconstrained walk-in demand; the rollout caps it by the candidate's occupancy."""
        self._check(t)
        return self.data.walk_ins_by_t.get(t, {}).get(shelter_id, 0)

    def travel_normal(self, *key: Any) -> float:
        return self.streams.normal(RandomStream.TRAVEL, *key)


class FutureSet:
    def __init__(
        self,
        forecast: ForecastSnapshot,
        graph: RoadGraph,
        world: V4WorldConfig,
        root: str,
        horizon_steps: int,
        backend: str = "sha256",
        edge_ids: tuple[str, ...] | None = None,
    ) -> None:
        if backend != "sha256":
            raise ValueError("only the sha256 backend is implemented")
        if forecast.graph_fingerprint and forecast.graph_fingerprint != graph.graph_fingerprint:
            raise ValueError("forecast was taken on a different road graph")
        if horizon_steps < 0:
            raise ValueError("horizon_steps must be nonnegative")
        self.forecast = forecast
        self.graph = graph
        # Optional restriction to the union of canonical-dispatch path edges (V4_FUTURES_SPEC
        # amendment 2026-10-14): per-edge values are bit-identical to the full graph.
        self.edge_ids = None if edge_ids is None else tuple(sorted(set(edge_ids)))
        self._graph_view = graph
        if self.edge_ids is not None:
            keep = set(self.edge_ids)
            self._graph_view = RoadGraph(
                graph_version=graph.graph_version,
                graph_fingerprint=graph.graph_fingerprint,
                location=graph.location,
                coordinate_reference=graph.coordinate_reference,
                topology_source=graph.topology_source,
                nodes=graph.nodes,
                edges=tuple(e for e in graph.edges if e.edge_id in keep),
                zone_node_map=graph.zone_node_map,
                shelter_node_map=graph.shelter_node_map,
            )
        self.world = world
        self.root = root
        self.backend = backend
        self.config = get_uncertainty_config(forecast.uncertainty_config_id)
        self.steps = max(0, min(horizon_steps, world.horizon_steps - forecast.timestep))
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1
        self._cache: dict[int, FutureTrajectory] = {}
        self._seed = int(root[:15], 16)
        self._scenario_stub = SimpleNamespace(
            zones=tuple(
                SimpleNamespace(zone_id=zone_id, initial_severity_trend=Trend(trend))
                for zone_id, trend in forecast.zone_trend
            )
        )

    def edge_set_digest(self) -> str:
        """Audit digest of the restricted edge set ("ALL" when unrestricted)."""
        if self.edge_ids is None:
            return "ALL"
        return hashlib.sha256("\n".join(self.edge_ids).encode("utf-8")).hexdigest()

    def future(self, k: int) -> FutureTrajectory:
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("future index k must be an integer >= 1")
        trajectory = self._cache.get(k)
        if trajectory is None:
            trajectory = self._build(k)
            self._cache[k] = trajectory
        return trajectory

    def _initial_state(self) -> EpisodeState:
        f = self.forecast
        return EpisodeState(
            scenario_id=f.incident_id,
            current_timestep=f.timestep,
            zones=tuple(ZoneState(zid, 0, sev) for zid, sev in f.zone_severity),
            shelters=tuple(
                ShelterState(sid, 0, 0, 0, ShelterStatus(status), sev)
                for (sid, sev), (_, status) in zip(f.shelter_severity, f.shelter_status)
            ),
            routes=(),
            dispatch_events=(),
            people_safely_arrived=0,
            initial_evacuation_population=0,
            dispatch_limit_per_timestep=0,
            dispatches_used_this_timestep=0,
            next_dispatch_sequence=1,
            terminal=False,
            terminal_reason=None,
            audit_log=(),
            uncertainty_config_id=self.config.config_id,
        )

    def _initial_road(self) -> RoadState:
        f = self.forecast
        base = {e.edge_id: e for e in self._graph_view.edges}
        edges = tuple(
            DynamicRoadEdge(
                edge_id=edge_id,
                hazard_severity=0.0,
                closure_probability=0.0,
                current_travel_time_minutes=base[edge_id].base_travel_time_minutes,
                open=is_open,
                closed_at_timestep=None if is_open else f.timestep,
            )
            for edge_id, is_open in f.edge_open
            if edge_id in base
        )
        return RoadState(
            graph_version=self.graph.graph_version,
            graph_fingerprint=self.graph.graph_fingerprint,
            scenario_seed=self._seed,
            uncertainty_config_id=self.config.config_id,
            timestep=f.timestep,
            edges=edges,
        )

    def _build(self, k: int) -> FutureTrajectory:
        f = self.forecast
        config = self.config
        streams = FutureStreams(self.root, k, config.config_id)
        state = self._initial_state()
        road = self._initial_road()
        road_ids = {e.edge_id for e in road.edges}
        edge_order = [edge_id for edge_id, _ in f.edge_open if edge_id in road_ids]
        edge_index = {edge_id: i for i, edge_id in enumerate(edge_order)}
        data = _TrajectoryData(edge_index, {}, {}, {}, {}, {})
        data.open_by_t[f.timestep] = tuple(
            is_open for edge_id, is_open in f.edge_open if edge_id in road_ids
        )
        data.shelter_severity_by_t[f.timestep] = dict(f.shelter_severity)
        data.shelter_status_by_t[f.timestep] = dict(f.shelter_status)
        shock = f.regional_shock_estimate
        for t in range(f.timestep + 1, f.timestep + self.steps + 1):
            state = replace(state, current_timestep=t)
            state, shock, _ = evolve_flood_state(
                self._scenario_stub, state, config, streams, shock
            )
            shelters = []
            for shelter in state.shelters:
                status, _, _ = degrade_shelter_status(
                    shelter.status_current,
                    shelter.flood_severity_current,
                    config,
                    streams,
                    t,
                    shelter.shelter_id,
                )
                shelters.append(replace(shelter, status_current=status))
            state = replace(state, shelters=tuple(shelters))
            road, _ = derive_road_state(
                self._graph_view, state, config, scenario_seed=self._seed, previous=road, streams=streams
            )
            by_edge = {e.edge_id: e for e in road.edges}
            data.open_by_t[t] = tuple(by_edge[e].open for e in edge_order)
            data.hazard_by_t[t] = tuple(by_edge[e].hazard_severity for e in edge_order)
            data.shelter_severity_by_t[t] = {
                s.shelter_id: s.flood_severity_current for s in state.shelters
            }
            data.shelter_status_by_t[t] = {
                s.shelter_id: s.status_current.value for s in state.shelters
            }
            mean_hazard = sum(z.flood_severity_current for z in state.zones) / len(state.zones)
            data.walk_ins_by_t[t] = {
                s.shelter_id: (
                    0
                    if s.status_current is ShelterStatus.CLOSED
                    else walk_in_demand(streams, self.world, t, s.shelter_id, mean_hazard)
                )
                for s in state.shelters
            }
        return FutureTrajectory(k, f.timestep, self.steps, streams, data)
