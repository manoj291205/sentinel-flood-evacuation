"""Live and replay geometry must use the engine's ordered edges, not a static shortcut."""
from dataclasses import replace
import hashlib
from types import SimpleNamespace

import pytest

from src.api.live_session import certificate_route_geometry, current_route_geometry
from src.geospatial import load_road_graph, path_for_action
from src.presentation.map_geometry import edge_path_svg
from src.sim import DispatchAction
from src.simulation_session import SimulationSession


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("route fidelity tests must remain offline")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def session():
    return SimulationSession(620000, graph=load_road_graph())


def test_current_route_uses_exact_engine_edges_and_state_identity(session):
    route = path_for_action(session.graph, session.overlay.road_state, DispatchAction("Z1", "S1"))
    dto = current_route_geometry(session, state_version=7)
    shown = dto["routes"]["Z1->S1"]
    assert dto["state_version"] == 7 and dto["timestep"] == session.state.current_timestep
    assert dto["graph_fingerprint"] == session.graph.graph_fingerprint
    assert shown["edge_ids"] == list(route.edge_ids)
    assert shown["path_id"] == route.path_id
    assert shown["svg_path"] == edge_path_svg(session.graph, route.edge_ids)
    assert shown["distance_m"] == route.distance_m


def test_closed_edges_never_fall_back_to_static_geometry(session):
    session.overlay.road_state = replace(session.overlay.road_state, edges=tuple(
        replace(edge, open=False, closed_at_timestep=0) for edge in session.overlay.road_state.edges))
    dto = current_route_geometry(session)
    assert dto["closed_edge_svg_path"]
    assert all(not route["reachable"] and route["edge_ids"] == [] and route["svg_path"] == ""
               for route in dto["routes"].values())


def test_certificate_geometry_stays_bound_to_committed_inputs(session):
    original = path_for_action(session.graph, session.overlay.road_state, DispatchAction("Z1", "S1"))
    candidate = SimpleNamespace(action_key="Z1->S1", edge_ids=original.edge_ids)
    session.ledger = SimpleNamespace(inputs=lambda _: SimpleNamespace(candidates=(candidate,)))
    certificate = {"cert_id": "CERT-TEST", "timestep": 0,
                   "graph_fingerprint": session.graph.graph_fingerprint,
                   "chosen": {"action_key": "Z1->S1"}}
    session.overlay.road_state = replace(session.overlay.road_state, edges=tuple(
        replace(edge, open=False, closed_at_timestep=1) for edge in session.overlay.road_state.edges))
    shown = certificate_route_geometry(session, [certificate])["CERT-TEST"]
    assert shown["edge_ids"] == list(original.edge_ids)
    assert shown["svg_path"] == edge_path_svg(session.graph, original.edge_ids)
    assert shown["path_sha256"] == hashlib.sha256("\n".join(original.edge_ids).encode()).hexdigest()
    assert shown["timestep"] == 0


def test_projection_rejects_unknown_edges(session):
    with pytest.raises((ValueError, KeyError)):
        edge_path_svg(session.graph, ("not-an-edge",))
