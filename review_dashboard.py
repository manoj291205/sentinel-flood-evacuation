"""Standalone, offline review dashboard for frozen Sentinel-Agent V3 results.

Run with: streamlit run review_dashboard.py

This UI reads committed artifacts and local corpus chunks. It does not train models,
run policy/retrieval evaluations, call Gemini, or modify scientific outputs.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.geospatial import (
    audit_route_metadata,
    build_geospatial_demo_runtime,
    path_for_action,
)
from src.human_decision import (
    DEMO_DEFAULT_UNCERTAINTY,
    DEMO_GENERATOR_SEED,
    DEMO_PLANNER_LABEL,
    DEMO_UNCERTAINTY_OPTIONS,
    EvidenceReference,
    HumanDecisionError,
    action_label,
    allowed_override_actions,
    apply_human_decision,
    current_decision_context,
    progress_snapshot,
    recommended_batch_size,
    route_for_action,
    session_summary,
    timeline_entries,
)
from src.sim import DispatchAction


ROOT = Path(__file__).resolve().parent
TRAINING_PATH = ROOT / "data" / "eval_v3" / "training" / "training_summary.json"
LEARNING_CURVES_PATH = ROOT / "data" / "eval_v3" / "training" / "learning_curves.csv"
PERMUTATION_PATH = ROOT / "data" / "eval_v3" / "training" / "permutation_diagnostic.json"
POLICY_PATH = ROOT / "data" / "eval_v3" / "phase10" / "heldout_summary.json"
PAIRWISE_PATH = ROOT / "data" / "eval_v3" / "phase10" / "pairwise_bootstrap.json"
POLICY_LATENCY_PATH = ROOT / "data" / "eval_v3" / "phase10" / "latency_results.json"
RETRIEVAL_LATENCY_PATH = ROOT / "data" / "eval_v3" / "phase12_retrieval_sanity.json"
RETRIEVAL_PATH = ROOT / "data" / "eval_v3" / "phase13" / "phase13b_retrieval_results_v2.json"
RETRIEVAL_MANIFEST_PATH = ROOT / "data" / "eval_v3" / "phase13" / "ai_assisted_label_manifest_extended.json"
CLAIM_SUPPORT_MANIFEST_PATH = ROOT / "data" / "eval_v3" / "phase14" / "claim_support_manifest.json"
GEOSPATIAL_MANIFEST_PATH = ROOT / "data" / "geospatial_v3" / "fort_kochi_osm_drive_v1_manifest.json"
PER_QUESTION_PATH = ROOT / "data" / "eval_v3" / "phase13" / "phase13b_per_question_v2.csv"
RANKINGS_PATH = ROOT / "data" / "eval_v3" / "phase13" / "phase13b_rankings_v2.csv"
LABELS_PATH = ROOT / "data" / "eval_v3" / "phase13" / "ai_assisted_passage_labels_extended.csv"
DOCUMENTATION_PATH = ROOT / "DOCUMENTATION.md"

SYSTEM_LABELS = {
    "dense-minilm-v1": "Dense",
    "bm25-okapi-v1": "BM25",
    "hybrid-rrf-v1": "Hybrid",
}
POLICY_LABELS = {
    "random_valid": "Random",
    "nearest_safe": "Nearest-safe",
    "risk_greedy": "Risk-greedy",
    "lookahead_k2": "Lookahead-2",
    "lookahead_k3": "Lookahead-3",
    "sampled_mpc": "MPC",
    "ppo_family": "PPO",
}
SOURCE_TITLES = {
    "ndma-flood-guidelines-2008": "NDMA Management of Floods",
    "ndma-national-disaster-management-plan-2019": "National Disaster Management Plan 2019",
    "ndma-temporary-shelters-2019": "National Guidelines for Temporary Shelters",
}
GRADE_LABELS = {2: "DIRECT", 1: "PARTIAL", 0: "NOT RELEVANT"}
GRADE_COLORS = {2: "#0f9d76", 1: "#d98e04", 0: "#718096"}


st.set_page_config(
    page_title="Sentinel-Agent V3 · Project Review",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root { --navy:#10243e; --cyan:#17a6b6; --ice:#eef8fa; --gold:#e0a52b; }
      .stApp { background: linear-gradient(180deg,#f7fbfc 0,#ffffff 300px); }
      .block-container { max-width: 1280px; padding-top: 1.7rem; padding-bottom: 3rem; }
      .hero { padding:1.6rem 1.8rem; border-radius:20px; color:white;
              background:linear-gradient(125deg,#10243e 0%,#153f5d 62%,#148a99 100%);
              box-shadow:0 18px 42px rgba(16,36,62,.16); margin-bottom:1rem; }
      .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-size:.72rem;
                 font-weight:700; color:#8fe2ea; }
      .hero h1 { font-size:2.45rem; line-height:1.05; margin:.35rem 0 .5rem; }
      .hero p { color:#d6edf1; max-width:850px; font-size:1.03rem; margin:0; }
      .result-good,.result-warn,.result-info { padding:1rem 1.15rem; border-radius:14px;
                 border:1px solid rgba(16,36,62,.10); height:100%; }
      .result-good { background:#eaf8f3; border-left:5px solid #0f9d76; }
      .result-warn { background:#fff7e6; border-left:5px solid #e0a52b; }
      .result-info { background:#edf7fb; border-left:5px solid #17a6b6; }
      .result-kicker { text-transform:uppercase; letter-spacing:.08em; font-size:.7rem;
                       font-weight:700; color:#526477; }
      .result-value { font-size:1.45rem; font-weight:800; color:#10243e; margin:.2rem 0; }
      .result-copy { color:#43576a; font-size:.88rem; line-height:1.45; }
      .flow { display:flex; gap:.45rem; align-items:center; flex-wrap:wrap; margin:.8rem 0 1.2rem; }
      .flow-step { background:#fff; border:1px solid #cfe3e8; color:#173853; border-radius:10px;
                   padding:.62rem .75rem; font-size:.78rem; font-weight:650;
                   box-shadow:0 4px 12px rgba(16,36,62,.05); }
      .flow-arrow { color:#17a6b6; font-weight:800; }
      .evidence { background:#fff; border:1px solid #dce9ed; border-radius:13px;
                  padding:.78rem .9rem; margin:.45rem 0; box-shadow:0 4px 13px rgba(16,36,62,.04); }
      .evidence-meta { font-size:.76rem; color:#607386; margin-bottom:.35rem; }
      .excerpt { font-size:.86rem; line-height:1.5; color:#273b4d; }
      .badge { color:white; padding:.14rem .48rem; border-radius:999px; font-size:.68rem;
               font-weight:750; letter-spacing:.04em; }
      div[data-testid="stMetric"] { background:white; border:1px solid #dce9ed;
               padding:.8rem 1rem; border-radius:13px; box-shadow:0 5px 14px rgba(16,36,62,.04); }
      div[data-testid="stTabs"] button { font-weight:650; }
      h2,h3 { color:#10243e; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text()), None
    except Exception as exc:  # surfaced visibly by each tab
        return None, f"Could not load {path.relative_to(ROOT)}: {exc}"


@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    try:
        return pd.read_csv(path), None
    except Exception as exc:
        return None, f"Could not load {path.relative_to(ROOT)}: {exc}"


@st.cache_data(show_spinner=False)
def load_test_count() -> int | None:
    try:
        matches = re.findall(r"passes all ([0-9,]+) collected tests", DOCUMENTATION_PATH.read_text())
        return int(matches[-1].replace(",", "")) if matches else None
    except Exception:
        return None


@st.cache_data(show_spinner="Reconstructing local evidence excerpts…")
def load_chunk_catalog() -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    try:
        from src.rag.ingest import prepare_corpus

        prepared = prepare_corpus()
        catalog = {
            chunk_id: {
                "text": text,
                "source_id": str(metadata["source_id"]),
                "filename": str(metadata["source_document"]),
                "page": int(metadata["page"]),
            }
            for chunk_id, text, metadata in zip(
                prepared.ids, prepared.documents, prepared.metadatas
            )
        }
        return catalog, None
    except Exception as exc:
        return None, f"Local chunk reconstruction is unavailable: {exc}"


@st.cache_data(show_spinner="Loading frozen decision evidence…")
def load_decision_evidence() -> tuple[dict[str, Any] | None, str | None]:
    """Select one direct Phase 13 route-planning passage without running retrieval."""
    try:
        rankings = pd.read_csv(RANKINGS_PATH)
        labels = pd.read_csv(LABELS_PATH)
        grade_lookup = {
            (str(row.question_id), str(row.chunk_id)): int(row.ai_relevance_grade)
            for row in labels.itertuples()
        }
        candidates = rankings[
            (rankings["question_id"] == "Q015")
            & (rankings["method_id"] == "hybrid-rrf-v1")
        ].sort_values("rank")
        selected = next(
            row
            for row in candidates.itertuples()
            if grade_lookup.get(("Q015", str(row.chunk_id))) == 2
        )
        catalog, error = load_chunk_catalog()
        if error or catalog is None:
            raise RuntimeError(error or "local chunk catalog unavailable")
        chunk = catalog[str(selected.chunk_id)]
        if (
            chunk["source_id"] != str(selected.source_id)
            or chunk["page"] != int(selected.page)
        ):
            raise RuntimeError("frozen evidence provenance mismatch")
        clean = " ".join(chunk["text"].split())
        return {
            "question_id": "Q015",
            "source_id": chunk["source_id"],
            "document": SOURCE_TITLES.get(chunk["source_id"], chunk["source_id"]),
            "filename": chunk["filename"],
            "page": chunk["page"],
            "chunk_id": str(selected.chunk_id),
            "excerpt": clean[:320] + ("…" if len(clean) > 320 else ""),
        }, None
    except Exception as exc:
        return None, f"Frozen decision evidence is unavailable: {exc}"


def show_error(error: str | None) -> bool:
    if error:
        st.warning(error, icon="⚠️")
        return True
    return False


def result_card(kicker: str, value: str, copy: str, kind: str = "info") -> None:
    st.markdown(
        f'<div class="result-{kind}"><div class="result-kicker">{html.escape(kicker)}</div>'
        f'<div class="result-value">{html.escape(value)}</div>'
        f'<div class="result-copy">{html.escape(copy)}</div></div>',
        unsafe_allow_html=True,
    )


def road_graph_chart(graph, road_state, selected_edge_ids: tuple[str, ...]):
    """Build a self-contained Altair road graph; no basemap tiles are requested."""
    selected = set(selected_edge_ids)
    edge_state = {item.edge_id: item for item in road_state.edges}
    segments = []
    for edge in graph.edges:
        current = edge_state[edge.edge_id]
        kind = (
            "RECOMMENDED PATH"
            if edge.edge_id in selected
            else "OPEN ROAD"
            if current.open
            else "CLOSED ROAD"
        )
        for order, node_id in enumerate((edge.u, edge.v)):
            node = graph.nodes_by_id[node_id]
            segments.append(
                {
                    "edge_id": edge.edge_id,
                    "order": order,
                    "longitude": node.lon,
                    "latitude": node.lat,
                    "status": kind,
                    "hazard": current.hazard_severity,
                }
            )
    line_data = pd.DataFrame(segments)
    roads = (
        alt.Chart(line_data)
        .mark_line(opacity=0.78)
        .encode(
            x=alt.X("longitude:Q", scale=alt.Scale(zero=False), title="Longitude"),
            y=alt.Y("latitude:Q", scale=alt.Scale(zero=False), title="Latitude"),
            detail="edge_id:N",
            order="order:O",
            color=alt.Color(
                "status:N",
                scale=alt.Scale(
                    domain=["OPEN ROAD", "CLOSED ROAD", "RECOMMENDED PATH"],
                    range=["#9aa9b4", "#b64c63", "#17a6b6"],
                ),
                legend=alt.Legend(title="Road state"),
            ),
            strokeWidth=alt.condition(
                alt.datum.status == "RECOMMENDED PATH", alt.value(4), alt.value(1)
            ),
            tooltip=["edge_id:N", "status:N", alt.Tooltip("hazard:Q", format=".3f")],
        )
    )
    entities = []
    for kind, mapping in (
        ("SIMULATED ZONE", graph.zone_node_map),
        ("SIMULATED SHELTER", graph.shelter_node_map),
    ):
        for entity_id, node_id in mapping.items():
            node = graph.nodes_by_id[node_id]
            entities.append(
                {
                    "entity_id": entity_id,
                    "kind": kind,
                    "longitude": node.lon,
                    "latitude": node.lat,
                }
            )
    point_data = pd.DataFrame(entities)
    points = (
        alt.Chart(point_data)
        .mark_point(filled=True, size=115, stroke="white", strokeWidth=1.5)
        .encode(
            x=alt.X("longitude:Q", scale=alt.Scale(zero=False)),
            y=alt.Y("latitude:Q", scale=alt.Scale(zero=False)),
            shape=alt.Shape(
                "kind:N",
                scale=alt.Scale(
                    domain=["SIMULATED ZONE", "SIMULATED SHELTER"],
                    range=["triangle-up", "square"],
                ),
            ),
            color=alt.Color(
                "kind:N",
                scale=alt.Scale(
                    domain=["SIMULATED ZONE", "SIMULATED SHELTER"],
                    range=["#e0a52b", "#0f9d76"],
                ),
            ),
            tooltip=["entity_id:N", "kind:N"],
        )
    )
    labels = (
        alt.Chart(point_data)
        .mark_text(dx=8, dy=-8, fontSize=11, fontWeight="bold")
        .encode(x="longitude:Q", y="latitude:Q", text="entity_id:N")
    )
    return (roads + points + labels).properties(height=500).interactive()


training, training_error = load_json(TRAINING_PATH)
policy, policy_error = load_json(POLICY_PATH)
pairwise, pairwise_error = load_json(PAIRWISE_PATH)
retrieval, retrieval_error = load_json(RETRIEVAL_PATH)
retrieval_manifest, retrieval_manifest_error = load_json(RETRIEVAL_MANIFEST_PATH)
claim_support_manifest, claim_support_manifest_error = load_json(CLAIM_SUPPORT_MANIFEST_PATH)
geospatial_manifest, geospatial_manifest_error = load_json(GEOSPATIAL_MANIFEST_PATH)
policy_latency, policy_latency_error = load_json(POLICY_LATENCY_PATH)
retrieval_latency, retrieval_latency_error = load_json(RETRIEVAL_LATENCY_PATH)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">University project review · frozen research results</div>
      <h1>Sentinel-Agent V3</h1>
      <p>Evidence-Grounded Decision Support for Dynamic Flood Evacuation Under Uncertainty</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Offline review UI · reads committed artifacts · performs no training or experiment reruns")

review_mode = st.sidebar.toggle(
    "Review Mode",
    value=True,
    help="Emphasizes the faculty-review path; all scientific values still come from frozen artifacts.",
)
with st.sidebar.expander("3-Minute Review Demo", expanded=review_mode):
    st.markdown(
        "1. **Overview:** architecture and frozen findings.\n"
        "2. **Live Evacuation:** show Fort Kochi roads; accept one action.\n"
        "3. **Policy & RL:** show 1.25M PPO steps and the retained negative result.\n"
        "4. **Evidence / RAG:** compare retrievers and open one NDMA example.\n"
        "5. **Human Override & Audit:** show operator authority and provenance.\n"
        "6. **Research Progress:** explain why Phase 14B is paused."
    )

(
    overview_tab,
    decision_tab,
    policy_tab,
    retrieval_tab,
    human_tab,
    progress_tab,
) = st.tabs(
    [
        "Overview",
        "Live Evacuation",
        "Policy & RL",
        "Evidence / RAG",
        "Human Override & Audit",
        "Research Progress",
    ]
)
training_tab = policy_tab
evidence_tab = retrieval_tab
tradeoffs_tab = policy_tab


with overview_tab:
    st.subheader("Project at a glance")
    values = [
        ("Held-out scenarios", policy["suite"]["number_of_scenarios"] if policy else "—"),
        ("PPO seeds", len(training["primary_training_seeds"]) if training else "—"),
        ("Timesteps / seed", f"{training['timesteps_per_seed']:,}" if training else "—"),
        ("Total PPO timesteps", f"{training['total_primary_timesteps']/1_000_000:.2f}M" if training else "—"),
        (
            "NDMA documents",
            len(retrieval["source_distribution_top5"]["dense"]) if retrieval else "—",
        ),
        (
            "RAG chunks",
            f"{retrieval_manifest['canonical_chunks']:,}" if retrieval_manifest else "—",
        ),
        ("Benchmark questions", retrieval["question_count"] if retrieval else "—"),
        (
            "Claim-support examples",
            claim_support_manifest["claim_pairs"] if claim_support_manifest else "—",
        ),
        ("Real road nodes", geospatial_manifest["node_count"] if geospatial_manifest else "—"),
        (
            "Directed road edges",
            f"{geospatial_manifest['directed_edge_count']:,}" if geospatial_manifest else "—",
        ),
    ]
    for start in (0, 5):
        columns = st.columns(5)
        for column, (label, value) in zip(columns, values[start : start + 5]):
            column.metric(label, value)
    for error in (
        training_error,
        policy_error,
        retrieval_error,
        retrieval_manifest_error,
        claim_support_manifest_error,
        geospatial_manifest_error,
    ):
        show_error(error)

    st.subheader("System architecture")
    st.info(
        "**REAL ROAD TOPOLOGY + SIMULATED FLOOD / POPULATION / SHELTER CONDITIONS**",
        icon="🗺️",
    )
    flow = [
        "Current state",
        "Stochastic simulator",
        "Deterministic safety layer",
        "Risk-Greedy / planning",
        "Evacuation recommendation",
        "NDMA evidence retrieval",
        "Human decision",
        "Audit trail",
    ]
    flow_html = '<div class="flow">' + '<span class="flow-arrow">→</span>'.join(
        f'<span class="flow-step">{html.escape(step)}</span>' for step in flow
    ) + "</div>"
    st.markdown(flow_html, unsafe_allow_html=True)
    left, middle, right, final = st.columns(4)
    with left:
        result_card("Decision research", "RL usefulness = NO", "PPO was tested across five seeds and 600 held-out stochastic scenarios, but was not selected as the final decision method.", "warn")
    with middle:
        result_card("Retrieval research", "HYBRID_SUPPORTED", "Hybrid met the frozen support rule against Dense; BM25 nevertheless had the highest DirectHit@5.", "good")
    with right:
        result_card("Important secondary finding", "BM25 highest DirectHit@5", "Hybrid did not beat BM25 on DirectHit@5.", "info")
    with final:
        result_card("Phase 14B", "PAUSED", "Gemini daily quota · 21/135 dispositions · no partial metrics.", "warn")


with decision_tab:
    st.subheader("Live Evacuation — Fort Kochi")
    st.warning(
        "SYNTHETIC EVACUATION SCENARIO — this is a decision-support prototype, not an operationally validated real-world recommendation.",
        icon="⚠️",
    )
    st.info(
        "**REAL ROAD TOPOLOGY + SIMULATED DISASTER CONDITIONS.** Only the cached "
        "OpenStreetMap road geometry is real. Flood hazards, edge closures, travel "
        "conditions, populations, shelter states, and decisions are simulated.",
        icon="🗺️",
    )

    integrity_columns = st.columns(4)
    with integrity_columns[0]:
        result_card("Phase 10", "RL usefulness = NO", "PPO was not selected by the frozen evaluation.", "warn")
    with integrity_columns[1]:
        result_card("Phase 13", "HYBRID_SUPPORTED", "Frozen comparison against Dense.", "good")
    with integrity_columns[2]:
        result_card("Phase 13 finding", "BM25 highest Hit@5", "BM25 had the highest frozen DirectHit@5.", "info")
    with integrity_columns[3]:
        result_card("Claim-Support Verification", "PAUSED — GEMINI DAILY QUOTA", "Benchmark: 135 · dispositions: 21/135. No partial performance is shown.", "warn")

    flow = [
        "Observed State",
        "Safety Filter",
        "Planner",
        "Recommendation",
        "Evidence",
        "Human Decision",
        "Audit Record",
    ]
    st.markdown(
        '<div class="flow">'
        + '<span class="flow-arrow">→</span>'.join(
            f'<span class="flow-step">{html.escape(step)}</span>' for step in flow
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.info(
        "**Why human-in-the-loop?** Sentinel-Agent provides decision support rather than autonomous disaster command. Deterministic checks constrain unsafe or mechanically invalid actions, while an operator retains authority to accept, reject, or override recommendations with an auditable reason.",
        icon="👤",
    )

    regime_labels = {
        "v3-low-v1": "LOW",
        "v3-medium-v1": "MEDIUM",
        "v3-high-v1": "HIGH",
    }
    selected_uncertainty = st.selectbox(
        "Synthetic uncertainty regime",
        DEMO_UNCERTAINTY_OPTIONS,
        index=DEMO_UNCERTAINTY_OPTIONS.index(DEMO_DEFAULT_UNCERTAINTY),
        format_func=lambda value: regime_labels[value],
        key="decision_demo_uncertainty_selector",
    )

    if "decision_demo_scenario" not in st.session_state:
        scenario, simulator, road_graph, road_overlay = build_geospatial_demo_runtime(
            selected_uncertainty
        )
        st.session_state.decision_demo_scenario = scenario
        st.session_state.decision_demo_simulator = simulator
        st.session_state.decision_demo_road_graph = road_graph
        st.session_state.decision_demo_road_overlay = road_overlay
        st.session_state.decision_demo_audit = []
        st.session_state.decision_demo_timeline = []
        st.session_state.decision_demo_progress = [
            progress_snapshot(simulator.prepared_state_for_debug())
        ]
    if "decision_demo_audit" not in st.session_state:
        st.session_state.decision_demo_audit = []
    if "decision_demo_timeline" not in st.session_state:
        st.session_state.decision_demo_timeline = []
    if "decision_demo_progress" not in st.session_state:
        st.session_state.decision_demo_progress = [
            progress_snapshot(
                st.session_state.decision_demo_simulator.prepared_state_for_debug()
            )
        ]

    reset_col, state_col = st.columns([1, 4])
    with reset_col:
        if st.button("Reset Scenario", key="reset_decision_demo"):
            scenario, simulator, road_graph, road_overlay = build_geospatial_demo_runtime(
                selected_uncertainty
            )
            st.session_state.decision_demo_scenario = scenario
            st.session_state.decision_demo_simulator = simulator
            st.session_state.decision_demo_road_graph = road_graph
            st.session_state.decision_demo_road_overlay = road_overlay
            st.session_state.decision_demo_audit = []
            st.session_state.decision_demo_timeline = []
            st.session_state.decision_demo_progress = [
                progress_snapshot(simulator.prepared_state_for_debug())
            ]
            st.session_state.decision_demo_last = "Synthetic scenario reset."
            st.rerun()
    with state_col:
        active_config = st.session_state.decision_demo_simulator.config
        st.caption(
            f"Fixed generator seed {DEMO_GENERATOR_SEED} · active regime {active_config.level.value} "
            f"(`{active_config.config_id}`). Choose a regime and reset to apply it. Reset clears only this browser session."
        )

    demo_simulator = st.session_state.decision_demo_simulator
    if demo_simulator.state.terminal:
        display_state = demo_simulator.state
        context = None
    else:
        demo_simulator.observe()
        display_state = demo_simulator.prepared_state_for_debug()
        try:
            context = current_decision_context(
                st.session_state.decision_demo_scenario,
                demo_simulator,
            )
        except HumanDecisionError as exc:
            st.warning(f"Synthetic incident has no remaining executable action: {exc}")
            context = None

    evidence, evidence_error = load_decision_evidence()
    road_graph = st.session_state.decision_demo_road_graph
    road_overlay = st.session_state.decision_demo_road_overlay
    road_state = road_overlay.road_state
    if road_state is None:
        raise RuntimeError("geospatial road state was not initialized")
    observation = display_state.to_policy_observation()
    timestep_col, regime_col, seed_col = st.columns(3)
    timestep_col.metric(
        "Timestep",
        f"{display_state.current_timestep} / {st.session_state.decision_demo_scenario.time.horizon_steps}",
    )
    regime_col.metric("Uncertainty regime", demo_simulator.config.level.value)
    seed_col.metric("Scenario generator seed", DEMO_GENERATOR_SEED)
    total_col, population_col, transit_col, arrived_col = st.columns(4)
    total_col.metric("Total population", display_state.initial_evacuation_population)
    population_col.metric("Population remaining", display_state.population_remaining)
    transit_col.metric("Population in transit", display_state.people_in_transit)
    arrived_col.metric("Population safe", display_state.people_safely_arrived)

    st.markdown("### Current incident state")
    if context is not None:
        zones_col, shelters_col = st.columns(2)
        with zones_col:
            st.markdown("#### Affected zones")
            zone_definitions = {
                zone.zone_id: zone
                for zone in st.session_state.decision_demo_scenario.zones
            }
            st.dataframe(
                pd.DataFrame(
                    {
                        "Zone": [row["zone_id"] for row in observation["zones"]],
                        "Population remaining": [row["population_remaining"] for row in observation["zones"]],
                        "Vulnerable population (initial)": [
                            zone_definitions[row["zone_id"]].vulnerable_population
                            for row in observation["zones"]
                        ],
                        "Flood severity": [row["flood_severity_current"] for row in observation["zones"]],
                    }
                ),
                hide_index=True,
                width="stretch",
            )
        with shelters_col:
            st.markdown("#### Shelters")
            st.dataframe(
                pd.DataFrame(
                    {
                        "Shelter": [row["shelter_id"] for row in observation["shelters"]],
                        "Status": [row["status_current"] for row in observation["shelters"]],
                        "Capacity": [row["capacity_total"] for row in observation["shelters"]],
                        "Occupancy": [row["occupancy_current"] for row in observation["shelters"]],
                        "Reserved": [row["capacity_reserved"] for row in observation["shelters"]],
                        "Available capacity": [row["capacity_available"] for row in observation["shelters"]],
                        "Flood severity": [row["flood_severity_current"] for row in observation["shelters"]],
                    }
                ),
                hide_index=True,
                width="stretch",
            )

        graph_paths = [
            path_for_action(
                road_graph,
                road_state,
                DispatchAction(row["source_zone_id"], row["destination_shelter_id"]),
            )
            for row in observation["routes"]
        ]
        with st.expander("Current routes", expanded=not review_mode):
            st.dataframe(
                pd.DataFrame(
                    {
                        "Route": [row["route_id"] for row in observation["routes"]],
                        "Source": [row["source_zone_id"] for row in observation["routes"]],
                        "Destination": [row["destination_shelter_id"] for row in observation["routes"]],
                        "Status": [
                            "OPEN"
                            if row["reachable_current"]
                            else "CLOSED"
                            if row["closed_at_timestep"] is not None
                            else "UNREACHABLE"
                            for row in observation["routes"]
                        ],
                        "Current travel (min)": [row["travel_time_current"] for row in observation["routes"]],
                        "Expected travel (min)": [row["expected_travel_time_minutes"] for row in observation["routes"]],
                        "Graph distance (m)": [
                            path.distance_m if path and path.reachable else None
                            for path in graph_paths
                        ],
                        "Route hazard": [row["route_hazard_proxy"] for row in observation["routes"]],
                        "Closure probability": [row["estimated_closure_probability"] for row in observation["routes"]],
                        "Closure timestep": [row["closed_at_timestep"] for row in observation["routes"]],
                    }
                ),
                hide_index=True,
                width="stretch",
            )

        st.markdown("#### In Transit")
        pending = display_state.pending_dispatches
        if pending:
            st.dataframe(
                pd.DataFrame(
                    {
                        "Event": [event.event_id for event in pending],
                        "Source": [event.source_zone_id for event in pending],
                        "Destination": [event.destination_shelter_id for event in pending],
                        "Population": [event.people for event in pending],
                        "Remaining timesteps": [
                            max(event.arrival_timestep - display_state.current_timestep, 0)
                            for event in pending
                        ],
                        "Arrival timestep": [event.arrival_timestep for event in pending],
                    }
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("No population is currently in transit.")

        action = context.recommendation.action
        recommendation_path = path_for_action(road_graph, road_state, action)
        selected_edge_ids = (
            recommendation_path.edge_ids if recommendation_path is not None else ()
        )
        st.markdown("### REAL ROAD TOPOLOGY — FORT KOCHI")
        st.markdown("#### Offline road-network view")
        st.altair_chart(
            road_graph_chart(road_graph, road_state, selected_edge_ids),
            width="stretch",
        )
        open_edges = sum(item.open for item in road_state.edges)
        map_metrics = st.columns(4)
        map_metrics[0].metric("Graph nodes", len(road_graph.nodes))
        map_metrics[1].metric("Open directed edges", open_edges)
        map_metrics[2].metric("Closed directed edges", len(road_state.edges) - open_edges)
        map_metrics[3].metric(
            "Recommendation path",
            "OPEN" if recommendation_path and recommendation_path.reachable else "UNREACHABLE",
        )
        st.caption(
            f"{road_graph.location} · `{road_graph.graph_version}` · fingerprint "
            f"`{road_graph.graph_fingerprint[:16]}…` · local artifact only; no basemap "
            "or runtime network access. Offline road-network view."
        )

        route = route_for_action(context, action)
        st.markdown("### RECOMMENDED EVACUATION ACTION")
        recommendation_col, checks_col = st.columns([1.15, 1])
        with recommendation_col:
            st.markdown(f"## {action_label(action)}")
            st.write(f"**Batch size:** {recommended_batch_size(context)} people")
            st.write(f"**Planner:** {DEMO_PLANNER_LABEL} (`{context.recommendation.planner_version}`)")
            if recommendation_path is not None and recommendation_path.reachable:
                st.write(
                    f"**Graph path:** {recommendation_path.distance_m:.0f} m · "
                    f"{recommendation_path.travel_time_minutes:.2f} min · "
                    f"{len(recommendation_path.edge_ids)} road edges · "
                    f"`{recommendation_path.path_id}`"
                )
            else:
                st.write("**Graph path:** UNREACHABLE")
            st.caption(context.recommendation.explanation or "")
            st.caption(
                "Recommended because the action is mechanically valid and passes the deterministic safety layer under the current observable state."
            )
        with checks_col:
            checks = st.columns(3)
            checks[0].metric("Mechanical validity", "PASS")
            checks[1].metric("Hard safety", "PASS")
            checks[2].metric("Route", "OPEN" if route and route["reachable_current"] else "N/A")
            if isinstance(action, DispatchAction):
                shelter = context.state.shelter(action.shelter_id)
                detail_checks = st.columns(3)
                detail_checks[0].metric("Source zone", action.zone_id)
                detail_checks[1].metric("Destination shelter", action.shelter_id)
                detail_checks[2].metric(
                    "Available capacity", shelter.capacity_available if shelter else "—"
                )
                st.metric(
                    "Destination hazard",
                    f"{shelter.flood_severity_current:.3f}" if shelter else "—",
                )

        st.markdown("### Offline authoritative evidence")
        if evidence_error or evidence is None:
            show_error(evidence_error)
        else:
            st.markdown(
                f'<div class="evidence"><div class="evidence-meta"><b>{html.escape(evidence["document"])}</b> · '
                f'{html.escape(evidence["filename"])} · PDF page {evidence["page"]}</div>'
                f'<div class="evidence-meta"><code>{html.escape(evidence["chunk_id"])}</code></div>'
                f'<div class="excerpt">{html.escape(evidence["excerpt"])}</div></div>',
                unsafe_allow_html=True,
            )
            st.info(
                "Retrieved authoritative context — semantic claim-support verification is currently under evaluation in Phase 14B. This contextual passage is not a dynamic semantic justification for the simulator action.",
                icon="📚",
            )

        st.markdown("### Human decision")
        accept_col, override_col, reject_col = st.columns(3)
        evidence_reference = (
            EvidenceReference(evidence["source_id"], evidence["page"], evidence["chunk_id"])
            if evidence
            else None
        )

        def submit_decision(decision: str, *, selected_action=None, reason: str = "") -> None:
            if evidence_reference is None:
                st.error("Offline evidence must load before a decision can be recorded.")
                return
            audited_action = (
                selected_action
                if decision == "OVERRIDE" and selected_action is not None
                else context.recommendation.action
            )
            try:
                record, transition = apply_human_decision(
                    context,
                    st.session_state.decision_demo_simulator,
                    decision=decision,
                    evidence=evidence_reference,
                    audit_sequence=len(st.session_state.decision_demo_audit) + 1,
                    selected_action=selected_action,
                    human_reason=reason,
                    audit_metadata=audit_route_metadata(
                        road_graph, road_state, audited_action
                    ),
                )
            except HumanDecisionError as exc:
                st.error(str(exc))
                return
            st.session_state.decision_demo_audit.append(record)
            st.session_state.decision_demo_timeline.extend(
                timeline_entries(record, transition)
            )
            if transition is not None:
                simulator = st.session_state.decision_demo_simulator
                if transition.terminal:
                    next_state = transition.state
                else:
                    simulator.observe()
                    next_state = simulator.prepared_state_for_debug()
                snapshot = progress_snapshot(next_state)
                if (
                    not st.session_state.decision_demo_progress
                    or st.session_state.decision_demo_progress[-1] != snapshot
                ):
                    st.session_state.decision_demo_progress.append(snapshot)
            st.session_state.decision_demo_last = (
                f"{record['decision']} recorded as {record['audit_id']}."
            )
            st.rerun()

        with accept_col:
            st.markdown("#### Accept")
            accept_note = st.text_input(
                "Optional operator note", key="decision_accept_note"
            )
            if st.button("ACCEPT RECOMMENDATION", key="accept_recommendation", type="primary"):
                submit_decision("ACCEPT", reason=accept_note)

        with override_col:
            st.markdown("#### Override")
            alternatives = allowed_override_actions(context)
            override_action = st.selectbox(
                "Safe alternative",
                alternatives,
                format_func=action_label,
                key="decision_override_action",
                disabled=not alternatives,
            ) if alternatives else None
            if override_action is not None:
                override_path = path_for_action(road_graph, road_state, override_action)
                if override_path is not None and override_path.reachable:
                    st.caption(
                        f"Path preview: {override_path.distance_m:.0f} m · "
                        f"{override_path.travel_time_minutes:.2f} min · "
                        f"{len(override_path.edge_ids)} edges"
                    )
            override_reason = st.text_input(
                "Override reason (required)", key="decision_override_reason"
            )
            if st.button("OVERRIDE", key="override_recommendation", disabled=not alternatives):
                submit_decision(
                    "OVERRIDE", selected_action=override_action, reason=override_reason
                )

        with reject_col:
            st.markdown("#### Reject")
            reject_reason = st.text_input(
                "Rejection reason (required)", key="decision_reject_reason"
            )
            if st.button("REJECT", key="reject_recommendation"):
                submit_decision("REJECT", reason=reject_reason)

    if st.session_state.get("decision_demo_last"):
        st.success(st.session_state.decision_demo_last)

    audit_rows = st.session_state.decision_demo_audit
    st.markdown("### Scenario Timeline")
    timeline_rows = st.session_state.decision_demo_timeline
    if timeline_rows:
        st.dataframe(pd.DataFrame(timeline_rows), hide_index=True, width="stretch")
    else:
        st.caption("No simulator or human-decision events have occurred yet.")

    st.markdown("### Population progress")
    progress_frame = pd.DataFrame(st.session_state.decision_demo_progress)
    if not progress_frame.empty:
        st.line_chart(
            progress_frame.set_index("timestep")[
                ["safe_population", "remaining_population", "in_transit_population"]
            ],
            color=["#0f9d76", "#b64c63", "#17a6b6"],
        )
        st.caption("Session playback only; this chart is not an evaluation metric.")

    current_summary = session_summary(audit_rows, display_state)
    summary_payload = {
        "scenario_id": st.session_state.decision_demo_scenario.scenario_id,
        "scenario_seed": st.session_state.decision_demo_scenario.seed,
        "uncertainty_regime": demo_simulator.config.level.value,
        "uncertainty_config_id": demo_simulator.config.config_id,
        "graph_version": road_graph.graph_version,
        "graph_fingerprint": road_graph.graph_fingerprint,
        "graph_source_artifact": "data/geospatial_v3/fort_kochi_osm_drive_v1.json",
        "current_timestep": display_state.current_timestep,
        "horizon_steps": st.session_state.decision_demo_scenario.time.horizon_steps,
        **current_summary,
    }
    if display_state.terminal:
        st.success("EVACUATION EPISODE COMPLETE")
        st.json({
            "terminal_reason": display_state.terminal_reason.value if display_state.terminal_reason else None,
            "initial_population": display_state.initial_evacuation_population,
            "safe_population": display_state.people_safely_arrived,
            "unfinished_population": display_state.population_remaining + display_state.people_in_transit,
            "dispatches": len(display_state.dispatch_events),
            "overrides": current_summary["overrides"],
            "rejects": current_summary["rejected_recommendations"],
            "unsafe_actions_executed": current_summary["unsafe_actions_executed"],
            "timesteps": display_state.current_timestep,
        })
        st.caption("This single synthetic episode is not a statistical policy comparison.")

    with st.expander("How to demonstrate this"):
        st.markdown(
            "1. Inspect the current flood, shelter, route, and in-transit state.\n"
            "2. Show the planner recommendation and deterministic safety validation.\n"
            "3. Accept or safely override the recommendation.\n"
            "4. Advance through several timesteps and inspect the timeline and audit history."
        )


with policy_tab:
    st.subheader("Frozen Phase 10 held-out evaluation")
    if show_error(policy_error) or policy is None:
        st.info("Policy charts require the committed Phase 10 held-out summary.")
    else:
        policies = policy["policies"]
        policy_rows = [
            {
                "Policy": label,
                "NSU-practical": policies[key]["nsu_practical"],
                "Safe population fraction": policies[key]["mean_safe_population_fraction"],
            }
            for key, label in POLICY_LABELS.items()
        ]
        policy_frame = pd.DataFrame(policy_rows).set_index("Policy")
        st.dataframe(
            policy_frame.reset_index(),
            hide_index=True,
            width="stretch",
            column_config={
                "NSU-practical": st.column_config.NumberColumn(format="%.4f"),
                "Safe population fraction": st.column_config.NumberColumn(format="%.4f"),
            },
        )
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.markdown("#### Normalized score (NSU-practical)")
            st.bar_chart(policy_frame[["NSU-practical"]], color="#17a6b6")
            st.caption("Frozen Phase 1 practical normalization; values are intentionally unclipped.")
        with chart_right:
            st.markdown("#### Mean safe-population fraction")
            st.bar_chart(policy_frame[["Safe population fraction"]], color="#e0a52b")
            st.caption("Synthetic held-out scenarios; this is not real emergency-response evidence.")

        result_left, comparison_col, safety_col = st.columns([1, 1.35, 1])
        with result_left:
            result_card("Frozen Phase 10 result", f"RL USEFULNESS: {policy['formal_result']}", "PPO was evaluated experimentally and was not selected as the final decision method.", "warn")
        if pairwise and not pairwise_error:
            effect = pairwise["combined"]["effects"]["nsu_difference"]
            with comparison_col:
                result_card("PPO vs Risk-greedy", f"{effect['estimate']:.4f} NSU", f"95% CI [{effect['lower']:.4f}, {effect['upper']:.4f}] · principal comparator: {policy['principal_comparator']}", "info")
        else:
            with comparison_col:
                show_error(pairwise_error)
        with safety_col:
            unsafe = int(policies["ppo_family"]["unsafe_dispatches"])
            result_card("Hard-safety outcome", f"{unsafe} unsafe dispatches", "Deterministic action masks remained the safety authority.", "good")
        st.info(
            "PPO was evaluated rather than assumed to be superior. The negative result was retained.",
            icon="ℹ️",
        )


with training_tab:
    st.subheader("Frozen Phase 9 PPO training")
    if show_error(training_error) or training is None:
        st.info("Training charts require the committed Phase 9 training summary.")
    else:
        seed_rows = pd.DataFrame(training["seed_results"])
        seed_rows["seed"] = seed_rows["seed"].astype(str)
        top = st.columns(4)
        top[0].metric("Seeds", len(training["primary_training_seeds"]))
        top[1].metric("Timesteps / seed", f"{training['timesteps_per_seed']:,}")
        top[2].metric("Total timesteps", f"{training['total_primary_timesteps']/1_000_000:.2f}M")
        top[3].metric("Representative model", f"Seed {training['representative_seed']}")

        left, right = st.columns(2)
        with left:
            st.markdown("#### Best validation return by seed")
            st.bar_chart(seed_rows.set_index("seed")[["validation_return"]], color="#17a6b6")
            st.dataframe(
                seed_rows[["seed", "best_timestep", "validation_return"]].rename(
                    columns={"seed": "Seed", "best_timestep": "Best timestep", "validation_return": "Validation return"}
                ),
                hide_index=True,
                width="stretch",
                column_config={"Validation return": st.column_config.NumberColumn(format="%.6f")},
            )
        with right:
            curves, curves_error = load_csv(LEARNING_CURVES_PATH)
            if curves is not None:
                aggregate = curves.groupby("timestep", as_index=False)["mean_validation_return"].first()
                st.markdown("#### Recorded validation trajectory")
                st.line_chart(aggregate.set_index("timestep"), color="#e0a52b")
                st.caption("Committed mean validation return across seeds; no curve was regenerated for this dashboard.")
            else:
                show_error(curves_error)

        permutation, permutation_error = load_json(PERMUTATION_PATH)
        if permutation and not permutation_error:
            result_card("Scientific limitation", permutation["alarm_label"], "The flat MLP showed sensitivity to slot permutations, which was reported rather than hidden.", "warn")
        else:
            show_error(permutation_error)


with retrieval_tab:
    st.subheader("Frozen Phase 13 retrieval benchmark")
    if show_error(retrieval_error) or retrieval is None:
        st.info("Retrieval charts require the committed Phase 13B v2 result artifact.")
    else:
        overall = retrieval["overall"]
        hit_frame = pd.DataFrame(
            {
                "Retriever": ["Dense", "BM25", "Hybrid"],
                "DirectHit@1": [overall[key]["direct_hit_at_1"] for key in ("dense", "bm25", "hybrid")],
                "DirectHit@3": [overall[key]["direct_hit_at_3"] for key in ("dense", "bm25", "hybrid")],
                "DirectHit@5": [overall[key]["direct_hit_at_5"] for key in ("dense", "bm25", "hybrid")],
            }
        ).set_index("Retriever")
        retrieval_table = pd.DataFrame(
            [
                {
                    "Retriever": name,
                    "DirectHit@1": overall[key]["direct_hit_at_1"],
                    "DirectHit@3": overall[key]["direct_hit_at_3"],
                    "DirectHit@5": overall[key]["direct_hit_at_5"],
                    "Direct hits": f"{overall[key]['direct_hit_at_5_count']} / 45",
                    "nDCG@5": overall[key]["ndcg_at_5"],
                }
                for key, name in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid"))
            ]
        )
        st.dataframe(
            retrieval_table,
            hide_index=True,
            width="stretch",
            column_config={
                metric: st.column_config.NumberColumn(format="%.4f")
                for metric in ("DirectHit@1", "DirectHit@3", "DirectHit@5", "nDCG@5")
            },
        )
        left, right = st.columns([1.55, 1])
        with left:
            st.markdown("#### Direct-evidence hit rate")
            st.bar_chart(hit_frame, color=["#8ccbd3", "#17a6b6", "#10243e"])
        with right:
            st.markdown("#### Graded ranking quality · nDCG@5")
            ndcg = pd.DataFrame(
                {
                    "Retriever": ["Dense", "BM25", "Hybrid"],
                    "nDCG@5": [overall[key]["ndcg_at_5"] for key in ("dense", "bm25", "hybrid")],
                }
            ).set_index("Retriever")
            st.bar_chart(ndcg, color="#e0a52b")

        principal = retrieval["principal_comparison"]
        a, b, c = st.columns(3)
        with a:
            result_card("Frozen verdict vs Dense", principal["final_verdict"], "All three pre-registered support conditions passed.", "good")
        with b:
            result_card("Hybrid − Dense Hit@5", f"+{principal['hybrid_minus_dense_directhit5']:.4f}", f"+{principal['equivalent_question_difference']} questions · 95% CI [{principal['ci95']['lower']:.4f}, {principal['ci95']['upper']:.4f}]", "info")
        with c:
            counts = ", ".join(
                f"{name} {overall[key]['direct_hit_at_5_count']}/45"
                for key, name in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid"))
            )
            result_card("DirectHit@5 counts", "BM25 highest", counts, "warn")
        st.warning("Unexpected finding: BM25 achieved the highest DirectHit@5 even though Hybrid was strongly supported over the pre-registered Dense baseline. Hybrid did not beat BM25 on DirectHit@5.", icon="🔎")
        st.caption("Passage relevance labels are AI-assisted rather than independently human-annotated gold labels.")


with evidence_tab:
    st.subheader("Offline evidence explorer")
    question_data, question_error = load_csv(PER_QUESTION_PATH)
    rankings, rankings_error = load_csv(RANKINGS_PATH)
    labels, labels_error = load_csv(LABELS_PATH)
    errors = [error for error in (question_error, rankings_error, labels_error) if error]
    for error in errors:
        show_error(error)
    if question_data is None or rankings is None or labels is None:
        st.info("The evidence explorer requires the committed Phase 13 question, ranking, and extended-label artifacts.")
    else:
        preferred = ["Q003", "Q008", "Q016", "Q034", "Q006", "Q012", "Q020", "Q039"]
        available = set(question_data["question_id"])
        selected_ids = [question_id for question_id in preferred if question_id in available]
        if not selected_ids:
            selected_ids = list(question_data["question_id"].head(8))
        question_lookup = question_data.set_index("question_id")["effective_question"].to_dict()
        selected = st.selectbox(
            "Select a frozen benchmark question",
            selected_ids,
            format_func=lambda question_id: f"{question_id} · {question_lookup[question_id]}",
        )
        st.markdown(f"### {selected} · {question_lookup[selected]}")
        st.caption("Ranks come from the frozen evaluation; excerpts are reconstructed at runtime from the unchanged local corpus.")

        label_lookup = {
            (str(row.question_id), str(row.chunk_id)): int(row.ai_relevance_grade)
            for row in labels.itertuples()
        }
        catalog, catalog_error = load_chunk_catalog()
        if catalog_error:
            show_error(catalog_error)
        method_columns = st.columns(3)
        for column, (method_id, system_name) in zip(method_columns, SYSTEM_LABELS.items()):
            with column:
                st.markdown(f"#### {system_name} top-5")
                method_rows = rankings[
                    (rankings["question_id"] == selected)
                    & (rankings["method_id"] == method_id)
                ].sort_values("rank")
                if method_rows.empty:
                    st.warning(f"No frozen {system_name} ranks found.")
                    continue
                for row in method_rows.itertuples():
                    grade = label_lookup.get((selected, str(row.chunk_id)))
                    grade_text = GRADE_LABELS.get(grade, "UNLABELLED")
                    grade_color = GRADE_COLORS.get(grade, "#b42318")
                    chunk = catalog.get(str(row.chunk_id)) if catalog else None
                    source_id = str(row.source_id)
                    document = SOURCE_TITLES.get(source_id, source_id)
                    filename = chunk["filename"] if chunk else document
                    excerpt = ""
                    if chunk:
                        clean = " ".join(chunk["text"].split())
                        excerpt = clean[:280] + ("…" if len(clean) > 280 else "")
                    excerpt_html = f'<div class="excerpt">{html.escape(excerpt)}</div>' if excerpt else ""
                    st.markdown(
                        f'<div class="evidence"><span class="badge" style="background:{grade_color}">{grade_text}</span>'
                        f'<div class="evidence-meta"><b>Rank {int(row.rank)}</b> · {html.escape(document)} · '
                        f'{html.escape(filename)} · PDF page {int(row.page)}</div>'
                        f'<div class="evidence-meta"><code>{html.escape(str(row.chunk_id))}</code></div>'
                        f'{excerpt_html}</div>',
                        unsafe_allow_html=True,
                    )
        st.info("Relevant evidence retrieval is separate from claim entailment. Phase 14B claim-support verification is currently paused because of the Gemini daily quota; no partial performance is shown.", icon="ℹ️")


with tradeoffs_tab:
    st.subheader("Research trade-offs: quality versus computation")
    st.caption("Both views combine already-frozen measurements; no evaluation or timing was rerun for this dashboard.")

    st.markdown("### Evacuation policy trade-off")
    if policy is None:
        show_error(policy_error)
    elif policy_latency is None:
        show_error(policy_latency_error)
        st.info("Phase 10 latency artifact unavailable; the policy latency/utility scatter cannot be displayed.")
    else:
        policy_tradeoff = pd.DataFrame(
            [
                {
                    "Method": label,
                    "Median latency (ms)": policy_latency["policies"][key]["median_ms"],
                    "NSU-practical": policy["policies"][key]["nsu_practical"],
                    "Safe fraction": policy["policies"][key]["mean_safe_population_fraction"],
                }
                for key, label in POLICY_LABELS.items()
            ]
        )
        policy_base = alt.Chart(policy_tradeoff).encode(
            x=alt.X(
                "Median latency (ms):Q",
                scale=alt.Scale(type="log"),
                axis=alt.Axis(title="Median decision latency (ms, logarithmic)", grid=True),
            ),
            y=alt.Y(
                "NSU-practical:Q",
                axis=alt.Axis(title="Normalized score / NSU-practical"),
                scale=alt.Scale(zero=False, padding=18),
            ),
            color=alt.Color(
                "Method:N",
                legend=None,
                scale=alt.Scale(
                    domain=list(POLICY_LABELS.values()),
                    range=["#8aa8b7", "#5d8799", "#0f9d76", "#27a8b7", "#123c5a", "#e0a52b", "#b64c63"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Method:N"),
                alt.Tooltip("NSU-practical:Q", format=".4f"),
                alt.Tooltip("Median latency (ms):Q", format=".4f"),
                alt.Tooltip("Safe fraction:Q", format=".4f"),
            ],
        )
        policy_plot = policy_base.mark_circle(size=175, opacity=0.92) + policy_base.mark_text(
            align="left", dx=9, dy=-9, fontSize=12, fontWeight=600
        ).encode(text="Method:N")
        st.altair_chart(policy_plot.properties(height=420), width="stretch")
        st.caption(
            f"Latency source: {POLICY_LATENCY_PATH.relative_to(ROOT)} · "
            f"utility/safety source: {POLICY_PATH.relative_to(ROOT)}"
        )
        st.info(
            "Planning quality increased substantially with lookahead depth, but latency also increased by orders of magnitude. PPO remained fast but did not achieve competitive held-out utility.",
            icon="↔️",
        )
        best, practical, rl = st.columns(3)
        with best:
            result_card("Best utility", "Lookahead-3", f"NSU {policy['policies']['lookahead_k3']['nsu_practical']:.4f}; not designated as a production method.", "good")
        with practical:
            result_card("Fast practical baseline", "Risk-Greedy", "Principal practical comparator under the frozen latency constraint.", "info")
        with rl:
            result_card("RL result", "Not useful", "PPO did not pass the frozen Phase 10 usefulness criteria.", "warn")

    st.markdown("### Retrieval quality versus latency")
    if retrieval is None:
        show_error(retrieval_error)
    elif retrieval_latency is None:
        show_error(retrieval_latency_error)
        fallback = pd.DataFrame(
            {
                "Method": ["Dense MiniLM", "BM25", "Hybrid RRF"],
                "DirectHit@5": [retrieval["overall"][key]["direct_hit_at_5"] for key in ("dense", "bm25", "hybrid")],
            }
        ).set_index("Method")
        st.info("Latency artifact unavailable; showing frozen retrieval quality only.")
        st.bar_chart(fallback, color="#17a6b6")
    else:
        retrieval_names = {"dense": "Dense MiniLM", "bm25": "BM25", "hybrid": "Hybrid RRF"}
        retrieval_tradeoff = pd.DataFrame(
            [
                {
                    "Method": label,
                    "Median latency (ms)": retrieval_latency["latency"][key]["median_ms"],
                    "DirectHit@5": retrieval["overall"][key]["direct_hit_at_5"],
                    "Hits": f"{retrieval['overall'][key]['direct_hit_at_5_count']}/45",
                    "nDCG@5": retrieval["overall"][key]["ndcg_at_5"],
                }
                for key, label in retrieval_names.items()
            ]
        )
        retrieval_base = alt.Chart(retrieval_tradeoff).encode(
            x=alt.X(
                "Median latency (ms):Q",
                scale=alt.Scale(type="log"),
                axis=alt.Axis(title="Warmed median retrieval latency (ms, logarithmic)", grid=True),
            ),
            y=alt.Y(
                "DirectHit@5:Q",
                axis=alt.Axis(title="DirectHit@5", format=".0%"),
                scale=alt.Scale(domain=[0.55, 0.92]),
            ),
            color=alt.Color(
                "Method:N",
                legend=None,
                scale=alt.Scale(
                    domain=list(retrieval_names.values()),
                    range=["#5d8799", "#e0a52b", "#17a6b6"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Method:N"),
                alt.Tooltip("DirectHit@5:Q", format=".4f"),
                alt.Tooltip("Hits:N"),
                alt.Tooltip("nDCG@5:Q", format=".4f"),
                alt.Tooltip("Median latency (ms):Q", format=".4f"),
            ],
        )
        retrieval_plot = retrieval_base.mark_circle(size=210, opacity=0.94) + retrieval_base.mark_text(
            align="left", dx=10, dy=-10, fontSize=13, fontWeight=600
        ).encode(text="Method:N")
        st.altair_chart(retrieval_plot.properties(height=380), width="stretch")
        st.caption(
            f"Latency source: {RETRIEVAL_LATENCY_PATH.relative_to(ROOT)} · "
            f"quality source: {RETRIEVAL_PATH.relative_to(ROOT)}"
        )
        retrieval_finding, hybrid_finding = st.columns(2)
        with retrieval_finding:
            result_card("BM25 highest DirectHit@5", "39/45 · 0.8667", "BM25 also had the lowest frozen warmed retrieval latency.", "good")
        with hybrid_finding:
            result_card("Hybrid supported vs Dense", "+0.2000 DirectHit@5", "Hybrid passed the pre-registered principal comparison against Dense; it did not beat BM25.", "info")
        st.success("BM25 produced the highest DirectHit@5 while also having the lowest measured warmed retrieval latency.", icon="🔎")

    st.markdown("### Why this matters")
    lesson_one, lesson_two, lesson_three = st.columns(3)
    with lesson_one:
        result_card("1 · Complexity", "Not automatically better", "Measured quality and computation—not model novelty—drive selection.", "info")
    with lesson_two:
        result_card("2 · Reinforcement learning", "Empirically rejected", "PPO was not retained despite 1.25 million training timesteps.", "warn")
    with lesson_three:
        result_card("3 · Neural retrieval", "Lexical baseline won", "BM25 outperformed the Dense baseline on direct-evidence retrieval.", "good")
    st.markdown(
        "**Sentinel-Agent therefore selects components based on measured performance rather than assuming that reinforcement learning or neural retrieval must be superior.**"
    )

    st.markdown("### Research progression")
    timeline = [
        "V1 · Static shelter recommendation",
        "V2 · Multi-resource deterministic planning",
        "V3 Simulator · Dynamic stochastic evacuation",
        "V3 Policy Study · PPO tested and rejected",
        "V3 Retrieval Study · Hybrid supported vs Dense",
    ]
    st.markdown(
        '<div class="flow">'
        + '<span class="flow-arrow">→</span>'.join(
            f'<span class="flow-step">{html.escape(step)}</span>' for step in timeline
        )
        + "</div>",
        unsafe_allow_html=True,
    )


with human_tab:
    st.subheader("Human Override & Audit")
    st.info(
        "**Sentinel-Agent is a decision-support system, not an autonomous disaster commander.** "
        "The operator remains responsible for accepting, safely overriding, or rejecting each recommendation.",
        icon="🧑‍💼",
    )

    recommendation_col, authority_col = st.columns([1.1, 1])
    with recommendation_col:
        if context is None:
            result_card(
                "Current recommendation",
                "EPISODE COMPLETE",
                "Reset the synthetic scenario in Live Evacuation to begin another review run.",
                "good",
            )
        else:
            result_card(
                "Current recommendation",
                action_label(context.recommendation.action),
                f"{DEMO_PLANNER_LABEL} · timestep {display_state.current_timestep} · deterministic safety PASS",
                "info",
            )
    with authority_col:
        st.markdown("#### Operator authority")
        st.markdown(
            "- **ACCEPT:** executes the current recommendation exactly once.\n"
            "- **OVERRIDE:** executes only a valid, safe, graph-reachable alternative and requires a reason.\n"
            "- **REJECT:** records a reason and makes no dispatch."
        )
        st.caption("Use the working decision controls in the Live Evacuation tab; this tab records their outcome.")

    st.markdown("### Live session audit trail")
    if audit_rows:
        audit_frame = pd.DataFrame(audit_rows)
        st.dataframe(audit_frame, hide_index=True, width="stretch")
        st.download_button(
            "Download session audit CSV",
            data=audit_frame.to_csv(index=False).encode("utf-8"),
            file_name="sentinel_v3_session_audit.csv",
            mime="text/csv",
            key="download_human_audit",
        )
    else:
        st.caption("No decisions recorded in this browser session. Accept, override, or reject an action in Live Evacuation.")
    st.caption(
        "Each row records scenario and seed, uncertainty regime, timestep, planner, recommendation, "
        "human decision and reason, executed action, mechanical and safety checks, graph-path provenance, "
        "and NDMA evidence provenance. No full authoritative passage text or personal data is stored."
    )

    st.markdown("### Session summary")
    first_summary = st.columns(4)
    first_summary[0].metric("Decisions", current_summary["decisions_made"])
    first_summary[1].metric("Accepts", current_summary["accepted_recommendations"])
    first_summary[2].metric("Overrides", current_summary["overrides"])
    first_summary[3].metric("Rejects", current_summary["rejected_recommendations"])
    second_summary = st.columns(4)
    second_summary[0].metric("Safe population", current_summary["population_safely_evacuated"])
    second_summary[1].metric("Remaining", current_summary["population_remaining"])
    second_summary[2].metric("In transit", current_summary["population_in_transit"])
    second_summary[3].metric("Unsafe executed actions", current_summary["unsafe_actions_executed"])
    st.download_button(
        "Download session summary JSON",
        data=(json.dumps(summary_payload, indent=2) + "\n").encode("utf-8"),
        file_name="sentinel_v3_session_summary.json",
        mime="application/json",
        key="download_human_summary",
    )

    with st.expander("Audit provenance fields", expanded=False):
        st.code(
            "audit_id · timestamp · scenario_id · generator_seed · scenario_seed · "
            "uncertainty_regime · timestep · planner · recommended_action · decision · "
            "executed_action · human_reason · mechanical_validity · safety_result · "
            "graph_version · graph_fingerprint · graph_path_id · graph_path_sha256 · "
            "graph_route_distance_m · graph_estimated_travel_minutes · graph_edge_count · "
            "evidence_source · evidence_page · evidence_chunk_id"
        )


with progress_tab:
    st.subheader("Research Progress")
    st.caption("A transparent record of completed, frozen, and paused work. No experiment is executed by this dashboard.")

    progress_rows = [
        ("V1", "Static shelter recommendation", "COMPLETE", "Foundational prototype"),
        ("V2", "Deterministic multi-resource planning", "COMPLETE", "Planning baseline"),
        ("V3 simulator", "Dynamic stochastic evacuation", "COMPLETE", "Frozen scenario protocol"),
        ("V3 safety", "Deterministic safety layer", "COMPLETE", "Hard action filtering"),
        ("V3 planning", "Planner benchmarking", "COMPLETE", "Frozen comparators"),
        ("Phase 9/10", "PPO training + held-out evaluation", "COMPLETE", "RL usefulness = NO"),
        ("Phase 11", "Authoritative NDMA RAG corpus", "COMPLETE", "3 documents · 1,797 chunks"),
        ("Phase 13", "Dense / BM25 / Hybrid benchmark", "COMPLETE", "HYBRID_SUPPORTED vs Dense"),
        ("Phase 14A", "Claim-support challenge benchmark", "COMPLETE", "135 construction-labeled examples"),
        ("Phase 14B", "Semantic claim-support evaluation", "PAUSED", "Gemini free-tier daily quota"),
        ("Phase 16/17", "Fort Kochi geospatial road network", "COMPLETE", "622 nodes · 1,358 directed edges"),
        ("Phase 19", "Human override", "COMPLETE", "Accept / override / reject"),
        ("Phase 19", "Session audit trail", "COMPLETE", "CSV + JSON export"),
    ]
    st.dataframe(
        pd.DataFrame(progress_rows, columns=["Stage", "Work", "Status", "Outcome"]),
        hide_index=True,
        width="stretch",
    )

    st.markdown("### Phase 14B — paused, incomplete evaluation")
    phase14_columns = st.columns(4)
    phase14_columns[0].metric("Official dispositions", "21 / 135")
    phase14_columns[1].metric("Successful predictions", 19)
    phase14_columns[2].metric("Invalid outputs", 2)
    phase14_columns[3].metric("Status", "PAUSED")
    st.warning(
        "PAUSED — GEMINI FREE-TIER DAILY QUOTA. The incomplete run has no official performance result; "
        "no interim performance score or class-summary table is displayed or interpreted scientifically.",
        icon="⏸️",
    )
    st.caption(
        "Phase 13 passage-relevance labels are AI-assisted. Phase 14A claim pairs are AI-assisted, "
        "construction-labeled challenge examples."
    )

    st.markdown("### Why claim-support verification exists")
    support_flow = [
        "SOURCE INTEGRITY\nDoes the citation actually exist?",
        "RETRIEVAL RELEVANCE\nIs the passage relevant?",
        "CLAIM SUPPORT\nDoes it support the exact claim?",
    ]
    st.markdown(
        '<div class="flow">'
        + '<span class="flow-arrow">→</span>'.join(
            f'<span class="flow-step">{html.escape(step).replace(chr(10), "<br>")}</span>'
            for step in support_flow
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    evidence_example, extension_example = st.columns(2)
    with evidence_example:
        result_card(
            "Illustrative evidence",
            "Shelters should be located on high ground.",
            "The citation exists and the passage is relevant.",
            "good",
        )
    with extension_example:
        result_card(
            "Unsupported generated extension",
            "…and within 2 km of residents.",
            "The added 2 km condition is not supported by the illustrative evidence.",
            "warn",
        )
    st.caption("Illustrative conceptual example—not a quoted frozen benchmark passage.")

    with st.expander("3-Minute Review Demo", expanded=True):
        st.markdown(
            "1. **OVERVIEW (20 seconds):** explain the architecture and frozen findings.\n"
            "2. **LIVE EVACUATION:** show the real Fort Kochi graph with simulated hazard; accept one action and advance until transit or arrival is visible.\n"
            "3. **POLICY & RL:** show 1.25M PPO training steps and the retained negative result.\n"
            "4. **RAG:** compare Dense, BM25, and Hybrid; open one offline NDMA evidence example.\n"
            "5. **HUMAN OVERRIDE:** show operator authority and the resulting audit provenance.\n"
            "6. **RESEARCH PROGRESS:** explain that semantic claim-support evaluation is paused and remains the next research stage."
        )

st.divider()
st.caption("Sentinel-Agent V3 · Synthetic evacuation research prototype · Not validated for operational emergency response")
