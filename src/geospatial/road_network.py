"""Cached real-road topology with a reproducible simulated disaster overlay.

Only the road topology and coordinates originate from OpenStreetMap. Edge hazards,
closures, travel conditions, populations, shelters, and decisions are simulated.
Runtime code reads local JSON and performs no network requests.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import networkx as nx

from src.sim import EpisodeState, ScenarioV3, StochasticSimulator
from src.sim.configs import UncertaintyConfig, get_uncertainty_config
from src.sim.events import AuditEventType, AuditRecord, DispatchAction, SimulationAction
from src.sim.generator import generate_gate6_scenario
from src.sim.randomness import EpisodeRandomStreams, RandomStream
from src.sim.schemas import (
    NetworkConfig,
    NetworkMode,
    ProvenanceClass,
    ProvenanceComponent,
    RouteDefinition,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRAPH_PATH = (
    REPOSITORY_ROOT / "data/geospatial_v3/fort_kochi_osm_drive_v1.json"
)
DEFAULT_MANIFEST_PATH = (
    REPOSITORY_ROOT / "data/geospatial_v3/fort_kochi_osm_drive_v1_manifest.json"
)
GRAPH_SOURCE_ARTIFACT = "data/geospatial_v3/fort_kochi_osm_drive_v1.json"
GRAPH_BASE_EDGE_CLOSURE_PROBABILITY = 0.005


@dataclass(frozen=True)
class RoadNode:
    node_id: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RoadEdge:
    edge_id: str
    u: str
    v: str
    osm_way_id: str
    highway: str
    name: str | None
    length_m: float
    assumed_speed_kph: float
    base_travel_time_minutes: float


@dataclass(frozen=True)
class DynamicRoadEdge:
    edge_id: str
    hazard_severity: float
    closure_probability: float
    current_travel_time_minutes: float
    open: bool
    closed_at_timestep: int | None


@dataclass(frozen=True)
class RoadState:
    graph_version: str
    graph_fingerprint: str
    scenario_seed: int
    uncertainty_config_id: str
    timestep: int
    edges: tuple[DynamicRoadEdge, ...]

    def edge(self, edge_id: str) -> DynamicRoadEdge:
        try:
            return next(item for item in self.edges if item.edge_id == edge_id)
        except StopIteration as exc:
            raise KeyError(edge_id) from exc


@dataclass(frozen=True)
class PathResult:
    source_node: str
    destination_node: str
    reachable: bool
    node_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    distance_m: float | None = None
    travel_time_minutes: float | None = None
    hazard_exposure: float | None = None
    closure_probability: float | None = None
    path_sha256: str | None = None

    @property
    def path_id(self) -> str | None:
        return f"path-{self.path_sha256[:16]}" if self.path_sha256 else None


class RoadGraph:
    def __init__(
        self,
        *,
        graph_version: str,
        graph_fingerprint: str,
        location: str,
        coordinate_reference: str,
        topology_source: str,
        nodes: tuple[RoadNode, ...],
        edges: tuple[RoadEdge, ...],
        zone_node_map: dict[str, str],
        shelter_node_map: dict[str, str],
    ) -> None:
        self.graph_version = graph_version
        self.graph_fingerprint = graph_fingerprint
        self.location = location
        self.coordinate_reference = coordinate_reference
        self.topology_source = topology_source
        self.nodes = nodes
        self.edges = edges
        self.zone_node_map = dict(zone_node_map)
        self.shelter_node_map = dict(shelter_node_map)
        self.nodes_by_id = {item.node_id: item for item in nodes}
        self.edges_by_id = {item.edge_id: item for item in edges}
        if len(self.nodes_by_id) != len(nodes) or len(self.edges_by_id) != len(edges):
            raise ValueError("road node and edge IDs must be unique")
        known = set(self.nodes_by_id)
        if any(edge.u not in known or edge.v not in known for edge in edges):
            raise ValueError("road edge references an unknown node")
        if any(node_id not in known for node_id in self.zone_node_map.values()):
            raise ValueError("zone mapping references an unknown road node")
        if any(node_id not in known for node_id in self.shelter_node_map.values()):
            raise ValueError("shelter mapping references an unknown road node")


def _canonical_static_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "graph_version": raw["graph_version"],
        "coordinate_reference": raw["coordinate_reference"],
        "nodes": raw["nodes"],
        "edges": raw["edges"],
        "zone_node_map": raw["zone_node_map"],
        "shelter_node_map": raw["shelter_node_map"],
    }


def road_graph_fingerprint(raw: dict[str, Any]) -> str:
    """Hash canonical static topology; dynamic road state is intentionally excluded."""
    encoded = json.dumps(
        _canonical_static_payload(raw),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_road_graph(path: Path = DEFAULT_GRAPH_PATH) -> RoadGraph:
    raw = json.loads(path.read_text(encoding="utf-8"))
    fingerprint = road_graph_fingerprint(raw)
    if raw.get("graph_fingerprint") != fingerprint:
        raise ValueError("road graph fingerprint does not match canonical topology")
    nodes = tuple(RoadNode(**item) for item in raw["nodes"])
    edges = tuple(RoadEdge(**item) for item in raw["edges"])
    return RoadGraph(
        graph_version=raw["graph_version"],
        graph_fingerprint=fingerprint,
        location=raw["location"],
        coordinate_reference=raw["coordinate_reference"],
        topology_source=raw["topology_source"],
        nodes=nodes,
        edges=edges,
        zone_node_map=raw["zone_node_map"],
        shelter_node_map=raw["shelter_node_map"],
    )


def _entity_hazards(graph: RoadGraph, state: EpisodeState) -> tuple[tuple[RoadNode, float], ...]:
    anchors: list[tuple[RoadNode, float]] = []
    for zone in state.zones:
        anchors.append(
            (graph.nodes_by_id[graph.zone_node_map[zone.zone_id]], zone.flood_severity_current)
        )
    for shelter in state.shelters:
        anchors.append(
            (
                graph.nodes_by_id[graph.shelter_node_map[shelter.shelter_id]],
                shelter.flood_severity_current,
            )
        )
    return tuple(anchors)


def _spatial_hazard(node: RoadNode, anchors: tuple[tuple[RoadNode, float], ...]) -> float:
    weighted = 0.0
    total_weight = 0.0
    for anchor, severity in anchors:
        distance_sq = (node.lat - anchor.lat) ** 2 + (node.lon - anchor.lon) ** 2
        weight = 1.0 / max(distance_sq, 1e-9)
        weighted += severity * weight
        total_weight += weight
    return weighted / total_weight


def derive_road_state(
    graph: RoadGraph,
    state: EpisodeState,
    config: str | UncertaintyConfig,
    *,
    scenario_seed: int,
    previous: RoadState | None = None,
) -> tuple[RoadState, tuple[AuditRecord, ...]]:
    """Apply seeded simulated hazards and absorbing closures to real road edges."""
    selected = get_uncertainty_config(config)
    if previous is not None:
        if previous.graph_fingerprint != graph.graph_fingerprint:
            raise ValueError("previous road state belongs to a different graph")
        if previous.scenario_seed != scenario_seed:
            raise ValueError("previous road state belongs to a different scenario seed")
        if previous.uncertainty_config_id != selected.config_id:
            raise ValueError("previous road state uses a different uncertainty config")
        if previous.timestep > state.current_timestep:
            raise ValueError("previous road state is ahead of the episode")
    previous_edges = {item.edge_id: item for item in previous.edges} if previous else {}
    streams = EpisodeRandomStreams(scenario_seed, selected.config_id)
    anchors = _entity_hazards(graph, state)
    dynamic: list[DynamicRoadEdge] = []
    records: list[AuditRecord] = []
    for edge in graph.edges:
        u = graph.nodes_by_id[edge.u]
        v = graph.nodes_by_id[edge.v]
        base_hazard = (_spatial_hazard(u, anchors) + _spatial_hazard(v, anchors)) / 2
        local = 0.2 * selected.local_hazard_sigma * streams.normal(
            RandomStream.LOCAL_HAZARD,
            "geospatial-edge",
            state.current_timestep,
            edge.edge_id,
        )
        hazard = min(1.0, max(0.0, base_hazard + local))
        probability = min(
            selected.maximum_closure_probability,
            GRAPH_BASE_EDGE_CLOSURE_PROBABILITY * selected.base_closure_multiplier
            + selected.hazard_to_closure_strength * hazard,
        )
        prior = previous_edges.get(edge.edge_id)
        close_now = (
            state.current_timestep > 0
            and (prior is None or prior.open)
            and streams.uniform(
                RandomStream.ROUTE_CLOSURE,
                "geospatial-edge",
                state.current_timestep,
                edge.edge_id,
            )
            < probability
        )
        is_open = (prior is None or prior.open) and not close_now
        closed_at = (
            state.current_timestep
            if close_now
            else prior.closed_at_timestep if prior is not None else None
        )
        current_time = edge.base_travel_time_minutes * (
            1.0 + selected.route_hazard_travel_factor * hazard
        )
        dynamic.append(
            DynamicRoadEdge(
                edge_id=edge.edge_id,
                hazard_severity=round(hazard, 6),
                closure_probability=round(probability, 8),
                current_travel_time_minutes=round(current_time, 6),
                open=is_open,
                closed_at_timestep=closed_at,
            )
        )
        if close_now:
            records.append(
                AuditRecord(
                    event_type=AuditEventType.ROUTE_CLOSED,
                    timestep=state.current_timestep,
                    route_id=edge.edge_id,
                    uncertainty_config_id=selected.config_id,
                    probability=probability,
                    hazard_proxy=hazard,
                    entity_kind="road_edge",
                    reason_code="SEEDED_SIMULATED_GRAPH_EDGE_CLOSURE",
                    message="road edge closed for future graph-routed dispatches",
                )
            )
    return (
        RoadState(
            graph_version=graph.graph_version,
            graph_fingerprint=graph.graph_fingerprint,
            scenario_seed=scenario_seed,
            uncertainty_config_id=selected.config_id,
            timestep=state.current_timestep,
            edges=tuple(dynamic),
        ),
        tuple(records),
    )


def shortest_valid_path(
    graph: RoadGraph, road_state: RoadState, source_node: str, destination_node: str
) -> PathResult:
    """Return the shortest current-travel-time route, excluding every closed edge."""
    dynamic = {item.edge_id: item for item in road_state.edges}
    network = nx.DiGraph()
    selected_edges: dict[tuple[str, str], RoadEdge] = {}
    for edge in graph.edges:
        current = dynamic[edge.edge_id]
        if not current.open:
            continue
        network.add_edge(edge.u, edge.v, weight=current.current_travel_time_minutes)
        selected_edges[(edge.u, edge.v)] = edge
    try:
        node_ids = tuple(
            nx.shortest_path(
                network,
                source=source_node,
                target=destination_node,
                weight="weight",
            )
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return PathResult(source_node, destination_node, False)
    edges = tuple(selected_edges[pair] for pair in zip(node_ids, node_ids[1:]))
    edge_ids = tuple(edge.edge_id for edge in edges)
    travel = sum(dynamic[edge.edge_id].current_travel_time_minutes for edge in edges)
    distance = sum(edge.length_m for edge in edges)
    hazard = (
        sum(dynamic[edge.edge_id].hazard_severity * edge.length_m for edge in edges)
        / distance
        if distance
        else 0.0
    )
    survival = math.prod(1.0 - dynamic[edge.edge_id].closure_probability for edge in edges)
    digest = hashlib.sha256("\n".join(edge_ids).encode("utf-8")).hexdigest()
    return PathResult(
        source_node,
        destination_node,
        True,
        node_ids,
        edge_ids,
        round(distance, 3),
        round(travel, 6),
        round(hazard, 6),
        round(1.0 - survival, 8),
        digest,
    )


def path_for_action(
    graph: RoadGraph, road_state: RoadState, action: SimulationAction
) -> PathResult | None:
    if not isinstance(action, DispatchAction):
        return None
    return shortest_valid_path(
        graph,
        road_state,
        graph.zone_node_map[action.zone_id],
        graph.shelter_node_map[action.shelter_id],
    )


def _adapt_routes(
    state: EpisodeState,
    graph: RoadGraph,
    road_state: RoadState,
    config: UncertaintyConfig,
) -> EpisodeState:
    routes = []
    for route in state.routes:
        path = shortest_valid_path(
            graph,
            road_state,
            graph.zone_node_map[route.source_zone_id],
            graph.shelter_node_map[route.destination_shelter_id],
        )
        reachable = route.reachable_current and path.reachable
        routes.append(
            replace(
                route,
                reachable_current=reachable,
                travel_time_current=path.travel_time_minutes if reachable else None,
                base_travel_time_minutes=path.travel_time_minutes if reachable else None,
                expected_travel_time_minutes=path.travel_time_minutes if reachable else None,
                travel_time_uncertainty_minutes=(
                    path.travel_time_minutes * config.travel_noise_fraction
                    if reachable and path.travel_time_minutes is not None
                    else None
                ),
                estimated_closure_probability=(
                    path.closure_probability if reachable else 0.0
                ),
                route_hazard_proxy=path.hazard_exposure if reachable else None,
                closed_at_timestep=(
                    route.closed_at_timestep
                    if reachable or route.closed_at_timestep is not None
                    else state.current_timestep
                ),
            )
        )
    return replace(state, routes=tuple(routes))


class GeospatialRouteOverlay:
    """Stateful simulator intervention that projects graph paths to route abstractions."""

    def __init__(self, graph: RoadGraph, config: UncertaintyConfig, scenario_seed: int):
        self.graph = graph
        self.config = config
        self.scenario_seed = scenario_seed
        self.road_state: RoadState | None = None

    def __call__(
        self, scenario: ScenarioV3, state: EpisodeState
    ) -> tuple[EpisodeState, tuple[AuditRecord, ...]]:
        del scenario
        road_state, records = derive_road_state(
            self.graph,
            state,
            self.config,
            scenario_seed=self.scenario_seed,
            previous=self.road_state,
        )
        self.road_state = road_state
        return _adapt_routes(state, self.graph, road_state, self.config), records


def _graph_scenario(graph: RoadGraph, config: UncertaintyConfig) -> ScenarioV3:
    scenario = generate_gate6_scenario(620000, "practical")
    static_state, _ = derive_road_state(
        graph,
        StochasticSimulator(scenario, config).prepared_state_for_debug(),
        config,
        scenario_seed=scenario.seed,
    )
    routes: list[RouteDefinition] = []
    for route in scenario.network.routes:
        path = shortest_valid_path(
            graph,
            static_state,
            graph.zone_node_map[route.source_zone_id],
            graph.shelter_node_map[route.destination_shelter_id],
        )
        routes.append(
            replace(
                route,
                reachable=path.reachable,
                travel_time_mean=path.travel_time_minutes if path.reachable else None,
                travel_time_std=(
                    path.travel_time_minutes * 0.15
                    if path.reachable and path.travel_time_minutes is not None
                    else None
                ),
                base_closure_probability=(
                    GRAPH_BASE_EDGE_CLOSURE_PROBABILITY if path.reachable else None
                ),
            )
        )
    provenance = replace(
        scenario.provenance,
        network_origin=ProvenanceComponent(
            ProvenanceClass.REAL,
            "Cached OpenStreetMap road topology; routing speeds and all disaster conditions are simulated.",
            (GRAPH_SOURCE_ARTIFACT,),
        ),
    )
    return replace(
        scenario,
        network=NetworkConfig(
            network_id=graph.graph_version,
            mode=NetworkMode.GRAPH,
            routes=tuple(routes),
        ),
        provenance=provenance,
    )


def build_geospatial_demo_runtime(
    uncertainty: str | UncertaintyConfig = "v3-medium-v1",
    *,
    graph: RoadGraph | None = None,
) -> tuple[ScenarioV3, StochasticSimulator, RoadGraph, GeospatialRouteOverlay]:
    """Build the reproducible Gate 6 demo over the frozen local Fort Kochi graph."""
    loaded = graph or load_road_graph()
    selected = get_uncertainty_config(uncertainty)
    scenario = _graph_scenario(loaded, selected)
    overlay = GeospatialRouteOverlay(loaded, selected, scenario.seed)
    simulator = StochasticSimulator(scenario, selected, intervention=overlay)
    return scenario, simulator, loaded, overlay


def audit_route_metadata(
    graph: RoadGraph, road_state: RoadState, action: SimulationAction
) -> dict[str, object]:
    path = path_for_action(graph, road_state, action)
    return {
        "graph_version": graph.graph_version,
        "graph_fingerprint": graph.graph_fingerprint,
        "graph_source_artifact": GRAPH_SOURCE_ARTIFACT,
        "graph_path_id": path.path_id if path else "NONE",
        "graph_path_sha256": path.path_sha256 if path else "NONE",
        "graph_route_distance_m": path.distance_m if path else None,
        "graph_estimated_travel_minutes": path.travel_time_minutes if path else None,
        "graph_edge_count": len(path.edge_ids) if path else 0,
    }
