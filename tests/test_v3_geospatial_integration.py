"""Focused Phase 16/17 cached-road integration tests (no live network)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.geospatial import (
    DEFAULT_GRAPH_PATH,
    DEFAULT_MANIFEST_PATH,
    RoadState,
    audit_route_metadata,
    build_geospatial_demo_runtime,
    derive_road_state,
    load_road_graph,
    path_for_action,
    road_graph_fingerprint,
    shortest_valid_path,
)
from src.human_decision import (
    EvidenceReference,
    allowed_override_actions,
    apply_human_decision,
    current_decision_context,
)
from src.planners import RiskGreedyPlanner, build_planner_input
from src.safety import evaluate_actions
from src.sim import DispatchAction, WAIT

EVIDENCE = EvidenceReference(
    source_id="ndma-national-disaster-management-plan-2019",
    page=306,
    chunk_id="ndma-national-disaster-management-plan-2019-p306-c1",
)
NOW = lambda: datetime(2026, 9, 9, 8, 30, tzinfo=timezone.utc)


def _closed_state(road_state, edge_ids):
    closed = set(edge_ids)
    return replace(
        road_state,
        edges=tuple(
            replace(
                edge,
                open=False,
                closed_at_timestep=road_state.timestep,
            )
            if edge.edge_id in closed
            else edge
            for edge in road_state.edges
        ),
    )


def test_graph_load_and_fingerprint_are_deterministic():
    first = load_road_graph()
    second = load_road_graph()
    raw = json.loads(DEFAULT_GRAPH_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert first.graph_fingerprint == second.graph_fingerprint
    assert first.graph_fingerprint == road_graph_fingerprint(raw)
    assert first.graph_fingerprint == manifest["graph_fingerprint"]
    assert len(first.nodes) == manifest["node_count"] == 622
    assert len(first.edges) == manifest["directed_edge_count"] == 1358


def test_every_zone_and_shelter_resolves_to_a_graph_node():
    scenario, _simulator, graph, _overlay = build_geospatial_demo_runtime()
    assert set(graph.zone_node_map) == {zone.zone_id for zone in scenario.zones}
    assert set(graph.shelter_node_map) == {
        shelter.shelter_id for shelter in scenario.shelters
    }
    assert set(graph.zone_node_map.values()) <= set(graph.nodes_by_id)
    assert set(graph.shelter_node_map.values()) <= set(graph.nodes_by_id)


def test_shortest_valid_path_and_travel_cost_use_open_edges():
    _scenario, _simulator, graph, overlay = build_geospatial_demo_runtime()
    road_state = overlay.road_state
    assert road_state is not None
    path = shortest_valid_path(
        graph, road_state, graph.zone_node_map["Z1"], graph.shelter_node_map["S1"]
    )
    assert path.reachable and path.edge_ids and path.distance_m > 0
    expected = sum(
        road_state.edge(edge_id).current_travel_time_minutes
        for edge_id in path.edge_ids
    )
    assert path.travel_time_minutes == pytest.approx(expected, abs=1e-6)
    assert path.path_sha256 and path.path_id.startswith("path-")


def test_closed_edge_is_excluded_and_path_is_recomputed():
    _scenario, _simulator, graph, overlay = build_geospatial_demo_runtime()
    road_state = overlay.road_state
    assert road_state is not None
    original = shortest_valid_path(
        graph, road_state, graph.zone_node_map["Z1"], graph.shelter_node_map["S3"]
    )
    assert original.reachable
    blocked_edge = original.edge_ids[len(original.edge_ids) // 2]
    rerouted = shortest_valid_path(
        graph,
        _closed_state(road_state, [blocked_edge]),
        graph.zone_node_map["Z1"],
        graph.shelter_node_map["S3"],
    )
    assert not rerouted.reachable or blocked_edge not in rerouted.edge_ids


def test_unreachable_destination_has_no_euclidean_fallback():
    _scenario, _simulator, graph, overlay = build_geospatial_demo_runtime()
    road_state = overlay.road_state
    assert road_state is not None
    source = graph.zone_node_map["Z2"]
    outgoing = [edge.edge_id for edge in graph.edges if edge.u == source]
    assert outgoing
    result = shortest_valid_path(
        graph,
        _closed_state(road_state, outgoing),
        source,
        graph.shelter_node_map["S4"],
    )
    assert not result.reachable
    assert result.edge_ids == () and result.travel_time_minutes is None


def test_route_adapter_feeds_graph_metrics_to_unchanged_risk_greedy():
    scenario, simulator, graph, overlay = build_geospatial_demo_runtime()
    context = current_decision_context(scenario, simulator)
    road_state = overlay.road_state
    assert road_state is not None
    assert isinstance(context.recommendation.action, DispatchAction)
    action = context.recommendation.action
    path = path_for_action(graph, road_state, action)
    route = next(
        item
        for item in context.state.routes
        if item.source_zone_id == action.zone_id
        and item.destination_shelter_id == action.shelter_id
    )
    assert path is not None and path.reachable
    assert route.expected_travel_time_minutes == path.travel_time_minutes
    assert context.recommendation.planner_version == "risk-greedy-v1"


def test_all_graph_paths_closed_are_mechanically_filtered_before_planning():
    scenario, simulator, _graph, overlay = build_geospatial_demo_runtime()
    state = simulator.prepared_state_for_debug()
    road_state = overlay.road_state
    assert road_state is not None
    overlay.road_state = _closed_state(
        road_state, [edge.edge_id for edge in road_state.edges]
    )
    adapted, _records = overlay(scenario, state)
    snapshot = evaluate_actions(scenario, adapted)
    assert all(
        not allowed
        for action, allowed in zip(snapshot.canonical_actions, snapshot.allowed_mask)
        if isinstance(action, DispatchAction)
    )
    planner_input = build_planner_input(scenario, adapted, snapshot, simulator.config)
    assert RiskGreedyPlanner().choose_action(planner_input).action == WAIT


def test_same_seed_and_action_sequence_reproduce_dynamic_road_state():
    left_scenario, left, _left_graph, left_overlay = build_geospatial_demo_runtime()
    right_scenario, right, _right_graph, right_overlay = build_geospatial_demo_runtime()
    for _ in range(3):
        left_context = current_decision_context(left_scenario, left)
        right_context = current_decision_context(right_scenario, right)
        assert left_context.recommendation.action == right_context.recommendation.action
        left.step(left_context.recommendation.action)
        right.step(right_context.recommendation.action)
        left.observe()
        right.observe()
        assert left_overlay.road_state == right_overlay.road_state


def test_different_stochastic_seeds_can_change_road_state():
    scenario, simulator, graph, overlay = build_geospatial_demo_runtime()
    state = simulator.prepared_state_for_debug()
    first, _ = derive_road_state(
        graph, state, simulator.config, scenario_seed=scenario.seed
    )
    second, _ = derive_road_state(
        graph, state, simulator.config, scenario_seed=scenario.seed + 1
    )
    assert first != second
    assert any(
        left.hazard_severity != right.hazard_severity
        for left, right in zip(first.edges, second.edges)
    )


def test_in_transit_dispatch_is_not_deleted_or_rerouted_by_later_closure():
    scenario, simulator, _graph, overlay = build_geospatial_demo_runtime()
    context = current_decision_context(scenario, simulator)
    result = simulator.step(context.recommendation.action)
    assert result.events_created
    dispatched = result.events_created[0]
    road_state = overlay.road_state
    assert road_state is not None
    overlay.road_state = _closed_state(
        road_state, [edge.edge_id for edge in road_state.edges]
    )
    simulator.observe()
    preserved = next(
        event for event in simulator.prepared_state_for_debug().dispatch_events
        if event.event_id == dispatched.event_id
    )
    assert preserved.source_zone_id == dispatched.source_zone_id
    assert preserved.destination_shelter_id == dispatched.destination_shelter_id
    assert preserved.people == dispatched.people


def test_human_override_options_are_graph_reachable_and_safe():
    scenario, simulator, graph, overlay = build_geospatial_demo_runtime()
    context = current_decision_context(scenario, simulator)
    road_state = overlay.road_state
    assert road_state is not None
    alternatives = allowed_override_actions(context)
    assert alternatives
    for action in alternatives:
        if isinstance(action, DispatchAction):
            assert path_for_action(graph, road_state, action).reachable
            index = context.snapshot.canonical_actions.index(action)
            assert context.snapshot.evaluations[index].final_allowed


def test_audit_records_compact_graph_provenance_without_path_arrays():
    scenario, simulator, graph, overlay = build_geospatial_demo_runtime()
    context = current_decision_context(scenario, simulator)
    road_state = overlay.road_state
    assert road_state is not None
    metadata = audit_route_metadata(graph, road_state, context.recommendation.action)
    record, transition = apply_human_decision(
        context,
        simulator,
        decision="ACCEPT",
        evidence=EVIDENCE,
        audit_sequence=1,
        audit_metadata=metadata,
        now=NOW,
    )
    assert transition is not None and transition.accepted
    assert record["graph_version"] == graph.graph_version
    assert record["graph_fingerprint"] == graph.graph_fingerprint
    assert record["graph_path_sha256"]
    assert record["graph_route_distance_m"] > 0
    assert record["graph_edge_count"] > 0
    assert "graph_edge_ids" not in record and "graph_node_ids" not in record


def test_dashboard_renders_offline_graph_and_provenance_banner():
    app = AppTest.from_file(str(ROOT / "review_dashboard.py")).run(timeout=120)
    assert not app.exception
    rendered = "\n".join(
        item.value for group in (app.markdown, app.warning, app.info) for item in group
    )
    assert "REAL ROAD TOPOLOGY + SIMULATED DISASTER CONDITIONS" in rendered
    assert "Offline road-network view" in rendered
    assert "st.altair_chart(" in (ROOT / "review_dashboard.py").read_text(encoding="utf-8")


def test_runtime_geospatial_code_has_no_network_client_or_live_map_dependency():
    source = (ROOT / "src/geospatial/road_network.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "review_dashboard.py").read_text(encoding="utf-8")
    for forbidden in (
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "urllib.request",
        "osmnx.graph_from",
        "overpass-api.de",
        "maps.googleapis.com",
        "st.pydeck_chart",
    ):
        assert forbidden not in source + dashboard


def test_manifest_declares_local_runtime_and_simulated_overlay():
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["runtime_network_required"] is False
    assert manifest["disaster_overlay"] == "SIMULATED"
    assert "OpenStreetMap" in manifest["source"]
