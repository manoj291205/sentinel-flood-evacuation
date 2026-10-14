"""Focused smoke tests for the offline human override and audit demo."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.human_decision import (
    DEMO_DEFAULT_UNCERTAINTY,
    DEMO_GENERATOR_SEED,
    DEMO_UNCERTAINTY_OPTIONS,
    EvidenceReference,
    HumanDecisionError,
    allowed_override_actions,
    apply_human_decision,
    build_demo_runtime,
    current_decision_context,
    progress_snapshot,
    session_summary,
    timeline_entries,
)
from src.sim import assert_episode_invariants

EVIDENCE = EvidenceReference(
    source_id="ndma-national-disaster-management-plan-2019",
    page=306,
    chunk_id="ndma-national-disaster-management-plan-2019-p306-c1",
)
NOW = lambda: datetime(2026, 9, 9, 7, 30, tzinfo=timezone.utc)


def prepared():
    scenario, simulator = build_demo_runtime()
    return simulator, current_decision_context(scenario, simulator)


def test_accept_executes_recommendation_and_creates_complete_audit_record():
    simulator, context = prepared()
    record, transition = apply_human_decision(
        context,
        simulator,
        decision="ACCEPT",
        evidence=EVIDENCE,
        audit_sequence=1,
        now=NOW,
    )
    assert transition is not None and transition.accepted
    assert record == {
        "audit_id": "AUDIT-0001",
        "timestamp": "2026-09-09T07:30:00+00:00",
        "scenario_id": "gate6-practical-620000",
        "generator_seed": DEMO_GENERATOR_SEED,
        "scenario_seed": 3208501935049057720,
        "uncertainty_regime": "MEDIUM",
        "uncertainty_config_id": DEMO_DEFAULT_UNCERTAINTY,
        "timestep": 0,
        "planner": "Risk-Greedy",
        "recommended_action": "Z4->S3",
        "decision": "ACCEPT",
        "executed_action": "Z4->S3",
        "mechanical_validity": "PASS",
        "safety_result": "PASS",
        "source_zone_state": (
            '{"flood_severity_current":0.768476,'
            '"population_remaining":59,"zone_id":"Z4"}'
        ),
        "destination_shelter_state": (
            '{"capacity_available":153,"capacity_reserved":0,'
            '"capacity_total":217,"flood_severity_current":0.299122,'
            '"occupancy_current":64,"shelter_id":"S3",'
            '"status_current":"OPEN"}'
        ),
        "human_reason": "",
        "evidence_source": EVIDENCE.source_id,
        "evidence_page": EVIDENCE.page,
        "evidence_chunk_id": EVIDENCE.chunk_id,
    }


def test_reject_requires_reason_records_none_and_does_not_advance():
    simulator, context = prepared()
    with pytest.raises(HumanDecisionError, match="requires a short human reason"):
        apply_human_decision(
            context,
            simulator,
            decision="REJECT",
            evidence=EVIDENCE,
            audit_sequence=1,
            human_reason="  ",
            now=NOW,
        )
    before = simulator.state.current_timestep
    record, transition = apply_human_decision(
        context,
        simulator,
        decision="REJECT",
        evidence=EVIDENCE,
        audit_sequence=1,
        human_reason="Awaiting updated route confirmation.",
        now=NOW,
    )
    assert transition is None and simulator.state.current_timestep == before
    assert record["decision"] == "REJECT"
    assert record["executed_action"] == "NONE"
    assert record["human_reason"] == "Awaiting updated route confirmation."


def test_override_offers_only_allowed_alternatives_and_rechecks_safety():
    simulator, context = prepared()
    alternatives = allowed_override_actions(context)
    assert alternatives
    assert context.recommendation.action not in alternatives
    assert all(
        context.snapshot.allowed_mask[context.snapshot.canonical_actions.index(action)]
        for action in alternatives
    )
    selected = alternatives[0]
    record, transition = apply_human_decision(
        context,
        simulator,
        decision="OVERRIDE",
        evidence=EVIDENCE,
        audit_sequence=1,
        selected_action=selected,
        human_reason="Use the alternate safe route for the exercise.",
        now=NOW,
    )
    assert transition is not None and transition.accepted
    assert record["decision"] == "OVERRIDE"
    assert record["executed_action"] != record["recommended_action"]
    assert record["mechanical_validity"] == record["safety_result"] == "PASS"


def test_invalid_or_unsafe_action_cannot_execute():
    simulator, context = prepared()
    invalid = next(
        evaluation.action
        for evaluation in context.snapshot.evaluations
        if not evaluation.final_allowed
    )
    before = simulator.state.to_dict()
    with pytest.raises(HumanDecisionError, match="not in the current allowed action mask"):
        apply_human_decision(
            context,
            simulator,
            decision="OVERRIDE",
            evidence=EVIDENCE,
            audit_sequence=1,
            selected_action=invalid,
            human_reason="Attempt an excluded action.",
            now=NOW,
        )
    assert simulator.state.to_dict() == before


def test_audit_rows_form_session_table_and_csv_without_evidence_text():
    simulator, context = prepared()
    record, _ = apply_human_decision(
        context,
        simulator,
        decision="REJECT",
        evidence=EVIDENCE,
        audit_sequence=1,
        human_reason="Operator rejects for the demonstration.",
        now=NOW,
    )
    frame = pd.DataFrame([record])
    csv_text = frame.to_csv(index=False)
    assert len(frame) == 1
    assert "audit_id" in frame and "human_reason" in frame
    assert EVIDENCE.chunk_id in csv_text
    assert "passage_text" not in csv_text and "authoritative evidence" not in csv_text


def test_dashboard_compiles_and_human_override_tab_renders():
    app = AppTest.from_file(str(ROOT / "review_dashboard.py")).run(timeout=120)
    assert not app.exception
    assert "Human Override & Audit" in [tab.label for tab in app.tabs]
    rendered = "\n".join(
        item.value for group in (app.markdown, app.warning, app.info) for item in group
    )
    assert "SYNTHETIC EVACUATION SCENARIO" in rendered
    assert "Why human-in-the-loop?" in rendered
    assert "Phase 14B" in rendered and "PAUSED" in rendered
    assert app.button(key="accept_recommendation")
    assert app.button(key="override_recommendation")
    assert app.button(key="reject_recommendation")


def test_dashboard_accept_updates_session_audit_table():
    app = AppTest.from_file(str(ROOT / "review_dashboard.py")).run(timeout=120)
    assert not app.exception
    app.button(key="accept_recommendation").click().run(timeout=120)
    assert not app.exception
    audit_tables = [
        frame.value
        for frame in app.dataframe
        if hasattr(frame.value, "columns") and "audit_id" in frame.value.columns
    ]
    assert len(audit_tables) == 1
    assert len(audit_tables[0]) == 1
    assert audit_tables[0].iloc[0]["decision"] == "ACCEPT"
    assert len(app.session_state["decision_demo_timeline"]) > 1
    assert [row["timestep"] for row in app.session_state["decision_demo_progress"]] == [0, 1]


def test_dashboard_reset_restores_initial_state_and_clears_playback():
    app = AppTest.from_file(str(ROOT / "review_dashboard.py")).run(timeout=120)
    initial = app.session_state["decision_demo_simulator"].state.to_dict()
    app.button(key="accept_recommendation").click().run(timeout=120)
    assert app.session_state["decision_demo_simulator"].state.current_timestep == 1
    app.button(key="reset_decision_demo").click().run(timeout=120)
    assert not app.exception
    assert app.session_state["decision_demo_simulator"].state.to_dict() == initial
    assert app.session_state["decision_demo_audit"] == []
    assert app.session_state["decision_demo_timeline"] == []
    assert len(app.session_state["decision_demo_progress"]) == 1


def test_dashboard_reject_without_reason_reports_validation_error():
    app = AppTest.from_file(str(ROOT / "review_dashboard.py")).run(timeout=120)
    app.button(key="reject_recommendation").click().run(timeout=120)
    assert not app.exception
    assert any("REJECT requires a short human reason" in item.value for item in app.error)


def test_feature_has_no_gemini_or_network_integration():
    source = (ROOT / "src/human_decision.py").read_text(encoding="utf-8") + (ROOT / "review_dashboard.py").read_text(encoding="utf-8")
    for forbidden in (
        "google.genai",
        "call_gemini",
        "generate_content(",
        "GEMINI_API_KEY",
        "requests.get(",
        "httpx.",
    ):
        assert forbidden not in source


def test_scenario_initialization_and_default_reset_are_deterministic():
    left_scenario, left = build_demo_runtime()
    right_scenario, right = build_demo_runtime()
    assert DEMO_GENERATOR_SEED == 620000
    assert left_scenario.to_dict() == right_scenario.to_dict()
    assert left.prepared_state_for_debug().to_dict() == right.prepared_state_for_debug().to_dict()
    assert left.config.config_id == right.config.config_id == DEMO_DEFAULT_UNCERTAINTY


@pytest.mark.parametrize("config_id", DEMO_UNCERTAINTY_OPTIONS)
def test_supported_uncertainty_regimes_initialize(config_id):
    scenario, simulator = build_demo_runtime(config_id)
    assert scenario.scenario_id == "gate6-practical-620000"
    assert simulator.config.config_id == config_id


def test_planner_recommendation_is_in_the_allowed_safety_mask():
    _simulator, context = prepared()
    recommendation = context.recommendation.action
    index = context.snapshot.canonical_actions.index(recommendation)
    assert context.snapshot.allowed_mask[index]
    assert context.recommendation_evaluation.mechanically_valid
    assert context.recommendation_evaluation.final_allowed


def test_accept_advances_exactly_one_step_and_preserves_population_ledgers():
    simulator, context = prepared()
    before = context.state
    record, transition = apply_human_decision(
        context,
        simulator,
        decision="ACCEPT",
        evidence=EVIDENCE,
        audit_sequence=1,
        now=NOW,
    )
    assert transition is not None
    assert transition.new_timestep == transition.previous_timestep + 1
    assert simulator.state.current_timestep == before.current_timestep + 1
    assert_episode_invariants(context.scenario, simulator.state)
    assert (
        simulator.state.initial_evacuation_population
        == simulator.state.population_remaining
        + simulator.state.people_in_transit
        + simulator.state.people_safely_arrived
    )
    assert record["mechanical_validity"] == record["safety_result"] == "PASS"
    for shelter in simulator.state.shelters:
        pending = sum(
            event.people
            for event in simulator.state.pending_dispatches
            if event.destination_shelter_id == shelter.shelter_id
        )
        assert shelter.capacity_reserved == pending
        assert shelter.occupancy_current + shelter.capacity_reserved <= shelter.capacity_total


def test_actual_timeline_and_progress_update_across_complete_episode():
    scenario, simulator = build_demo_runtime()
    progress = [progress_snapshot(simulator.prepared_state_for_debug())]
    timeline = []
    audit = []
    while not simulator.state.terminal:
        context = current_decision_context(scenario, simulator)
        record, transition = apply_human_decision(
            context,
            simulator,
            decision="ACCEPT",
            evidence=EVIDENCE,
            audit_sequence=len(audit) + 1,
            now=NOW,
        )
        audit.append(record)
        timeline.extend(timeline_entries(record, transition))
        progress.append(progress_snapshot(simulator.state))

    assert len(audit) == scenario.time.horizon_steps
    assert [row["timestep"] for row in progress] == list(
        range(scenario.time.horizon_steps + 1)
    )
    event_types = {row["event_type"] for row in timeline}
    assert {
        "HUMAN_ACCEPT",
        "DISPATCH_CREATED",
        "ARRIVAL_PROCESSED",
        "FLOOD_STATE_UPDATED",
        "ROUTE_CLOSED",
        "SHELTER_RESTRICTED",
        "EPISODE_TERMINATED",
    } <= event_types
    assert simulator.state.people_safely_arrived > 0
    assert_episode_invariants(scenario, simulator.state)


def test_audit_csv_and_session_summary_json_are_serializable():
    simulator, context = prepared()
    record, _transition = apply_human_decision(
        context,
        simulator,
        decision="ACCEPT",
        evidence=EVIDENCE,
        audit_sequence=1,
        now=NOW,
    )
    csv_text = pd.DataFrame([record]).to_csv(index=False)
    payload = json.loads(json.dumps(session_summary([record], simulator.state)))
    assert "AUDIT-0001" in csv_text
    assert "passage_text" not in csv_text
    assert payload["decisions_made"] == 1
    assert payload["unsafe_actions_executed"] == 0


def test_episode_demo_does_not_modify_phase14b_cache():
    cache_path = ROOT / "data/eval_v3/phase14/phase14b_run_cache.json"
    before = hashlib.sha256(cache_path.read_bytes()).hexdigest() if cache_path.exists() else None
    simulator, context = prepared()
    apply_human_decision(
        context,
        simulator,
        decision="ACCEPT",
        evidence=EVIDENCE,
        audit_sequence=1,
        now=NOW,
    )
    after = hashlib.sha256(cache_path.read_bytes()).hexdigest() if cache_path.exists() else None
    assert after == before
