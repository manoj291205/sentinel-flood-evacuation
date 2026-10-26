"""Presentation-path checks for the six-tab Sentinel-Agent V3 review dashboard."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "review_dashboard.py"


def render() -> AppTest:
    app = AppTest.from_file(str(DASHBOARD)).run(timeout=120)
    assert not app.exception
    return app


def rendered_text(app: AppTest) -> str:
    return "\n".join(
        str(item.value)
        for group in (app.markdown, app.warning, app.info, app.caption)
        for item in group
    )


def test_six_review_tabs_and_frozen_kpis_render_from_local_artifacts():
    app = render()
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Live Evacuation",
        "Policy & RL",
        "Evidence / RAG",
        "Human Override & Audit",
        "Research Progress",
    ]
    metrics = {(item.label, str(item.value)) for item in app.metric}
    assert {
        ("Held-out scenarios", "600"),
        ("PPO seeds", "5"),
        ("Timesteps / seed", "250,000"),
        ("Total PPO timesteps", "1.25M"),
        ("NDMA documents", "3"),
        ("RAG chunks", "1,797"),
        ("Benchmark questions", "45"),
        ("Claim-support examples", "135"),
        ("Real road nodes", "622"),
        ("Directed road edges", "1,358"),
    } <= metrics
    text = rendered_text(app)
    for expected in (
        "REAL ROAD TOPOLOGY — FORT KOCHI",
        "RECOMMENDED EVACUATION ACTION",
        "RL USEFULNESS: NO",
        "HYBRID_SUPPORTED",
        "BM25 achieved the highest DirectHit@5",
        "Sentinel-Agent is a decision-support system",
        "Why claim-support verification exists",
    ):
        assert expected in text
    assert "3-Minute Review Demo" in [item.label for item in app.expander]


def test_evidence_demo_is_frozen_offline_and_includes_requested_questions():
    app = render()
    evidence_selector = next(
        item for item in app.selectbox if item.label == "Select a frozen benchmark question"
    )
    choices = "\n".join(evidence_selector.options)
    for question_id in ("Q003", "Q008", "Q016", "Q034", "Q039"):
        assert question_id in choices
    text = rendered_text(app)
    assert "reconstructed at runtime from the unchanged local corpus" in text
    assert "runtime network access" in text


def test_dashboard_override_executes_safe_graph_reachable_alternative_and_audits():
    app = render()
    app.text_input(key="decision_override_reason").set_value(
        "University review: choose the alternate safe graph route."
    )
    app.button(key="override_recommendation").click().run(timeout=120)
    assert not app.exception
    assert len(app.session_state["decision_demo_audit"]) == 1
    record = app.session_state["decision_demo_audit"][0]
    assert record["decision"] == "OVERRIDE"
    assert record["executed_action"] != record["recommended_action"]
    assert record["mechanical_validity"] == "PASS"
    assert record["safety_result"] == "PASS"
    assert record["graph_path_sha256"]
    assert record["graph_route_distance_m"] > 0
    assert record["graph_edge_count"] > 0


def test_phase14b_is_presented_as_superseded_without_partial_performance():
    app = render()
    metrics = {(item.label, str(item.value)) for item in app.metric}
    assert ("Phase 14B status", "SUPERSEDED") in metrics
    assert not {"Official dispositions", "Successful predictions", "Invalid outputs"} & {label for label, _ in metrics}
    text = rendered_text(app)
    assert "no official performance result" in text
    assert "Phase 14C and 14D are separate" in text
    assert "not independent annotation agreement" in text
    source = DASHBOARD.read_text(encoding="utf-8")
    for forbidden in ("google.genai", "generate_content(", "GEMINI_API_KEY", "requests.get("):
        assert forbidden not in source
