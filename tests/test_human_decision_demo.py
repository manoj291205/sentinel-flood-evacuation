"""Focused smoke tests for the offline human override and audit demo."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.human_decision import (
    EvidenceReference,
    HumanDecisionError,
    allowed_override_actions,
    apply_human_decision,
    build_demo_runtime,
    current_decision_context,
)

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
        "timestep": 0,
        "planner": "Risk-Greedy",
        "recommended_action": "Z4->S3",
        "decision": "ACCEPT",
        "executed_action": "Z4->S3",
        "mechanical_validity": "PASS",
        "safety_result": "PASS",
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
    assert "SYNTHETIC DEMONSTRATION" in rendered
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
    assert audit_tables[0].iloc[0]["decision"] == "ACCEPT"


def test_dashboard_reject_without_reason_reports_validation_error():
    app = AppTest.from_file(str(ROOT / "review_dashboard.py")).run(timeout=120)
    app.button(key="reject_recommendation").click().run(timeout=120)
    assert not app.exception
    assert any("REJECT requires a short human reason" in item.value for item in app.error)


def test_feature_has_no_gemini_or_network_integration():
    source = (ROOT / "src/human_decision.py").read_text() + (ROOT / "review_dashboard.py").read_text()
    for forbidden in (
        "google.genai",
        "call_gemini",
        "generate_content(",
        "GEMINI_API_KEY",
        "requests.get(",
        "httpx.",
    ):
        assert forbidden not in source
