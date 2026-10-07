"""Focused offline integration tests for the live simulation, not new experiments."""
from dataclasses import replace
import csv
import hashlib
import importlib
from io import StringIO
import json
from pathlib import Path
import socket

import pytest
from streamlit.testing.v1 import AppTest

from src.geospatial import path_for_action
from src.human_decision import EvidenceReference, HumanDecisionError, allowed_override_actions
from src.sim import DispatchAction, WAIT, StochasticSimulator
from src.simulation_session import SimulationSession

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = EvidenceReference("ndma-national-disaster-management-plan-2019", 306,
                             "ndma-national-disaster-management-plan-2019-p306-c1")


def conserved(state):
    assert state.initial_evacuation_population == (
        state.population_remaining + state.people_in_transit + state.people_safely_arrived)
    for shelter in state.shelters:
        assert shelter.occupancy_current + shelter.capacity_reserved <= shelter.capacity_total
        assert shelter.capacity_available >= 0


def app():
    result = AppTest.from_file(str(ROOT / "simulation_demo.py"), default_timeout=30).run()
    assert not result.exception
    return result


def test_import_and_actual_offline_graph():
    module = importlib.import_module("simulation_demo")
    session = SimulationSession(graph=module.static_graph())
    assert isinstance(session.simulator, StochasticSimulator)
    assert session.seed == 620000
    assert session.simulator.config.level.value == "MEDIUM"
    assert len(session.graph.nodes) == 622
    assert len(session.graph.edges) == 1358
    assert session.graph.graph_fingerprint == "dff7f2065ab5be8685ffd1195cdab1eaf8ce0b28716f5553f146c7565906a6e3"
    assert len(session.state.zones) == 4 and len(session.state.shelters) == 5
    assert len(session.route_rows()) == 20
    conserved(session.state)


@pytest.mark.parametrize("regime", ["v3-low-v1", "v3-medium-v1", "v3-high-v1"])
@pytest.mark.parametrize("seed", [620000, 620001])
def test_seeded_full_episode_replay_population_capacity_and_mask(seed, regime):
    left, right = SimulationSession(seed, regime), SimulationSession(seed, regime)
    while not left.state.terminal:
        assert left.state == right.state
        assert left.overlay.road_state == right.overlay.road_state
        lc, rc = left.context(), right.context()
        assert lc.recommendation.action == rc.recommendation.action
        assert lc.recommendation_evaluation.mechanically_valid
        assert lc.recommendation_evaluation.final_allowed
        if isinstance(lc.recommendation.action, DispatchAction):
            path = path_for_action(left.graph, left.overlay.road_state, lc.recommendation.action)
            assert path.reachable
            assert all(next(edge for edge in left.overlay.road_state.edges
                            if edge.edge_id == edge_id).open for edge_id in path.edge_ids)
        for session in (left, right):
            before = session.state.current_timestep
            _, transition = session.decide("ACCEPT", EVIDENCE)
            assert transition.accepted and transition.new_timestep == before + 1
            conserved(transition.state)
            conserved(session.state)
    assert left.state == right.state
    assert left.timeline == right.timeline
    assert left.population_history == right.population_history
    assert left.hazard_history == right.hazard_history
    assert left.summary()["unsafe_actions_executed"] == 0
    assert len(left.audit) == left.state.current_timestep
    with pytest.raises(HumanDecisionError, match="complete"):
        left.decide("ACCEPT", EVIDENCE)


def test_accept_has_actual_transit_arrival_and_immediate_event_history():
    session = SimulationSession()
    before = session.state
    record, result = session.decide("ACCEPT", EVIDENCE)
    assert result.people_dispatched > 0
    assert result.state.pending_dispatches
    event = result.events_created[0]
    assert event.departure_timestep == before.current_timestep
    assert event.arrival_timestep == event.departure_timestep + event.travel_lag_steps
    assert event.arrival_timestep >= 1
    assert any(row["in_transit_population"] > 0 for row in session.population_history)
    while session.state.current_timestep < event.arrival_timestep:
        session.decide("ACCEPT", EVIDENCE)
    arrived = next(e for e in session.state.dispatch_events if e.event_id == event.event_id)
    assert arrived.status.value == "ARRIVED"
    assert session.state.people_safely_arrived >= event.people
    assert any(row["event_type"] == "ARRIVAL_PROCESSED" and row["event_id"] == event.event_id
               for row in session.timeline)
    assert any(row["category"] == "HAZARD" for row in session.timeline)
    assert any(row["category"] == "ROUTE" for row in session.timeline)
    assert record["graph_edge_count"] > 0
    assert record["evidence_chunk_id"] == EVIDENCE.chunk_id
    event_count = len(session.timeline)
    history_count = len(session.population_history)
    session.context(); session.context()
    assert len(session.timeline) == event_count
    assert len(session.population_history) == history_count


def test_override_only_allowed_alternative_and_wait_semantics():
    session = SimulationSession()
    choices = allowed_override_actions(session.context())
    for action in choices:
        evaluation = next(e for e in session.context().snapshot.evaluations if e.action == action)
        assert evaluation.mechanically_valid and evaluation.final_allowed
        if isinstance(action, DispatchAction):
            assert path_for_action(session.graph, session.overlay.road_state, action).reachable
    assert WAIT in choices
    record, transition = session.decide("OVERRIDE", EVIDENCE, selected_action=WAIT, reason="Hold dispatch; advance conditions.")
    assert record["executed_action"] == "WAIT"
    assert transition.people_dispatched == 0
    assert session.state.current_timestep == 1
    assert record["graph_path_id"] == "NONE"


@pytest.mark.parametrize("decision", ["OVERRIDE", "REJECT"])
def test_required_reason_fails_atomically(decision):
    session = SimulationSession()
    before = session.export_json()
    with pytest.raises(HumanDecisionError, match="requires"):
        session.decide(decision, EVIDENCE, selected_action=WAIT if decision == "OVERRIDE" else None)
    assert session.export_json() == before


def test_reject_audits_without_transition_or_executed_path():
    session = SimulationSession()
    before, history = session.state, list(session.population_history)
    record, transition = session.decide("REJECT", EVIDENCE, reason="Reassess the situation.")
    assert transition is None and session.state == before
    assert session.population_history == history
    assert record["executed_action"] == "NONE" and record["graph_path_id"] == "NONE"
    assert record["recommended_graph_edge_count"] > 0
    assert session.timeline[-1]["category"] == "HUMAN"
    assert session.summary()["rejected_recommendations"] == 1


def test_reset_restores_seed_state_and_clears_session_only():
    session = SimulationSession(620001, "v3-high-v1")
    initial, road = session.state, session.overlay.road_state
    session.decide("ACCEPT", EVIDENCE)
    session.reset(620001, "v3-high-v1")
    assert session.state == initial and session.overlay.road_state == road
    assert session.audit == [] and session.timeline == []
    assert len(session.population_history) == 1
    assert len(session.hazard_history) == 4
    assert session.last_transition is None


def test_custom_seed_record_and_exports_contain_provenance_not_passages():
    session = SimulationSession(620001)
    session.decide("ACCEPT", EVIDENCE)
    rows = list(csv.DictReader(StringIO(session.export_csv())))
    assert rows[0]["generator_seed"] == "620001"
    assert rows[0]["scenario_seed"] == str(session.scenario.seed)
    assert rows[0]["graph_fingerprint"] == session.graph.graph_fingerprint
    assert "excerpt" not in rows[0] and "text" not in rows[0]
    exported = json.loads(session.export_json())
    assert exported["summary"] == session.summary()
    assert exported["audit"] == session.audit
    assert exported["timeline"] == session.timeline
    assert exported["population_history"] == session.population_history


def set_prepared(session, state):
    prepared = session.simulator._prepared
    session.simulator._prepared = (state, *prepared[1:])
    session.simulator.state = state


def test_all_edges_closed_unreachable_dispatch_is_rejected():
    session = SimulationSession()
    forbidden = session.context().recommendation.action
    closed = replace(session.overlay.road_state, edges=tuple(
        replace(edge, open=False, closed_at_timestep=0) for edge in session.overlay.road_state.edges))
    session.overlay.road_state = closed
    adapted, _ = session.overlay(session.scenario, session.state)
    set_prepared(session, adapted)
    assert not path_for_action(session.graph, session.overlay.road_state, forbidden).reachable
    assert session.context().recommendation.action == WAIT
    assert all(row["Status"] == "UNREACHABLE" and row["Distance (m)"] is None for row in session.route_rows())
    with pytest.raises(HumanDecisionError, match="allowed action mask"):
        session.decide("OVERRIDE", EVIDENCE, selected_action=forbidden, reason="Attempt closed route.")
    assert not session.audit


def test_destination_hazard_hard_safety_cannot_be_overridden():
    session = SimulationSession()
    forbidden = session.context().recommendation.action
    state = replace(session.state, shelters=tuple(
        replace(s, flood_severity_current=1.0) if s.shelter_id == forbidden.shelter_id else s
        for s in session.state.shelters))
    set_prepared(session, state)
    evaluation = next(e for e in session.context().snapshot.evaluations if e.action == forbidden)
    assert evaluation.mechanically_valid and not evaluation.final_allowed
    with pytest.raises(HumanDecisionError, match="allowed action mask"):
        session.decide("OVERRIDE", EVIDENCE, selected_action=forbidden, reason="Attempt unsafe destination.")
    assert not session.audit


def test_graph_recommendation_and_charts_render_without_external_urls():
    from simulation_demo import population_chart, shelter_chart
    from src.simulation_views import road_graph_chart
    session = SimulationSession()
    path = path_for_action(session.graph, session.overlay.road_state, session.context().recommendation.action)
    chart = road_graph_chart(session.graph, session.overlay.road_state, path.edge_ids).to_dict()
    datasets = chart["datasets"].values()
    assert any(row.get("status") == "RECOMMENDED PATH" for data in datasets for row in data)
    assert any(row.get("kind") == "SIMULATED ZONE" for data in datasets for row in data)
    assert any(row.get("kind") == "SIMULATED SHELTER" for data in datasets for row in data)
    assert all("url" not in layer["data"] for layer in chart["layer"])
    assert population_chart(session.population_history).to_dict()
    assert shelter_chart(session.state).to_dict()


def test_runtime_is_offline_and_phase14_artifacts_untouched(monkeypatch):
    import simulation_demo
    def denied(*args, **kwargs):
        raise AssertionError("Network access attempted")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    phase14 = ROOT / "data/eval_v3/phase14"
    def snapshot():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in phase14.iterdir() if p.is_file()}
    before = snapshot()
    evidence = simulation_demo.load_evidence.__wrapped__()
    assert evidence["page"] == EVIDENCE.page and evidence["chunk_id"] == EVIDENCE.chunk_id
    session = SimulationSession()
    for _ in range(3):
        session.decide("ACCEPT", EVIDENCE)
    session.export_csv(); session.export_json()
    assert snapshot() == before
    for relative in ("simulation_demo.py", "src/simulation_session.py", "src/simulation_views.py"):
        source = (ROOT / relative).read_text()
        assert "google.genai" not in source and "from google import genai" not in source
        assert "requests." not in source and "httpx." not in source


def test_apptest_initial_panels_and_advance_reset():
    at = app()
    assert at.session_state.live_simulation.state.current_timestep == 0
    assert len(at.get("vega_lite_chart")) >= 4
    assert any("REAL ROAD TOPOLOGY" in item.value for item in at.info)
    at.button(key="advance_demo").click().run()
    assert not at.exception
    assert at.session_state.live_simulation.state.current_timestep == 1
    assert len(at.session_state.live_simulation.audit) == 1
    at.button(key="reset_demo").click().run()
    assert not at.exception
    assert at.session_state.live_simulation.state.current_timestep == 0
    assert not at.session_state.live_simulation.audit


def test_apptest_accept_override_reject_reasons_and_terminal_render():
    at = app()
    at.button(key="reject_demo").click().run()
    assert any("requires" in item.value for item in at.error)
    at.text_input(key="reject_reason").set_value("Review hazards").run()
    at.button(key="reject_demo").click().run()
    assert not at.exception
    assert at.session_state.live_simulation.state.current_timestep == 0
    assert at.session_state.live_simulation.audit[-1]["decision"] == "REJECT"
    at.text_input(key="override_reason").set_value("Use another safe destination").run()
    at.button(key="override_demo").click().run()
    assert not at.exception
    assert at.session_state.live_simulation.audit[-1]["decision"] == "OVERRIDE"
    while not at.session_state.live_simulation.state.terminal:
        at.button(key="accept_demo").click().run()
        assert not at.exception
    assert any(item.value == "EVACUATION EPISODE COMPLETE" for item in at.success)
    assert at.button(key="advance_demo").disabled
    assert len(at.get("vega_lite_chart")) >= 4
    assert len(at.dataframe) >= 3


def test_apptest_preset_custom_seed_and_session_independence():
    left, right = app(), app()
    left.selectbox(key="demo_preset").set_value("High-Uncertainty Scenario").run()
    left.button(key="apply_preset").click().run()
    left.number_input(key="demo_seed").set_value(620001).run()
    left.button(key="reset_demo").click().run()
    assert not left.exception
    assert left.session_state.live_simulation.seed == 620001
    assert left.session_state.live_simulation.simulator.config.level.value == "HIGH"
    assert right.session_state.live_simulation.seed == 620000
    assert right.session_state.live_simulation.simulator.config.level.value == "MEDIUM"
