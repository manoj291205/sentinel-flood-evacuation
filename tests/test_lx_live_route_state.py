"""Reproduce the audited Fort Kochi mismatch and verify current-state route DTOs."""
from src.api.app import _state_dto
from src.api.live_session import current_route_geometry
from src.api.sessions import SessionEntry
from src.geospatial import path_for_action
from src.human_decision import EvidenceReference
from src.presentation.map_geometry import edge_path_svg, project_graph
from src.sim import DispatchAction
from src.simulation_session import SimulationSession


def test_previous_fort_kochi_mismatch_uses_engine_path_and_current_transit():
    session = SimulationSession(620003, "v4-medium-dt2-v1", certified=True,
                                params_id="v4-cert-test-v1", recertify=True)
    road = path_for_action(session.graph, session.overlay.road_state, DispatchAction("Z1", "S1"))
    shown = current_route_geometry(session, state_version=0)["routes"]["Z1->S1"]
    static_svg, static_distance = project_graph(session.graph)["route_Z1_S1"]
    assert shown["edge_ids"] == list(road.edge_ids)
    assert shown["svg_path"] != static_svg  # The audited shortest-distance shortcut is different.
    assert shown["distance_m"] != static_distance
    evidence = EvidenceReference("ndma-flood-guidelines-2008", 64, "ndma-flood-guidelines-2008-p64-c0")
    for _ in range(2):
        session.decide("ACCEPT", evidence)
    dto = _state_dto(SessionEntry(session, state_version=2))
    assert dto["state_version"] == 2 and dto["current_timestep"] == 2
    assert dto["closed_edge_svg_path"] == edge_path_svg(session.graph,
        [edge.edge_id for edge in session.overlay.road_state.edges if not edge.open])
    assert {"people_stranded", "people_unsafe_arrival", "people_overflow"} <= dto.keys()
    assert dto["transit_positions"]  # A real dispatch, not a route-only mock.
    for group in dto["transit_positions"]:
        plan = session.simulator.transit_plans()[group["group_id"]]
        assert group["edge_ids"] == list(plan.edge_ids)
        assert group["svg_path"] == edge_path_svg(session.graph, plan.edge_ids)
        assert group["graph_fingerprint"] == session.graph.graph_fingerprint
        assert group["state_version"] == 2
