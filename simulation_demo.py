"""Live, offline Sentinel-Agent V3 simulation. Run: streamlit run simulation_demo.py.

The UI orchestrates existing project behavior; it runs no scientific evaluations.
"""
from __future__ import annotations

import csv
from pathlib import Path
import re

import altair as alt
import pandas as pd
import streamlit as st

from src.geospatial import load_road_graph, path_for_action
from src.human_decision import (
    EvidenceReference, HumanDecisionError, action_label, allowed_override_actions,
    recommended_batch_size,
)
from src.sim import DispatchAction
from src.sim.configs import get_uncertainty_config
from src.simulation_session import SimulationSession
from src.simulation_views import road_graph_chart

ROOT = Path(__file__).resolve().parent
PRESETS = {"Standard Medium Scenario": (620000, "MEDIUM"),
           "High-Uncertainty Scenario": (620000, "HIGH")}


@st.cache_resource(show_spinner=False)
def static_graph():
    """Only immutable topology is shared; road overlays are session-owned."""
    return load_road_graph()


@st.cache_data(show_spinner="Loading local NDMA context…")
def load_evidence():
    """Read a frozen ranking and its exact local PDF chunk; no retrieval or model call."""
    from pypdf import PdfReader
    from src.rag.corpus import validate_manifest, RAW_DOCS_DIR
    from src.rag.ingest import chunk_page

    base = ROOT / "data/eval_v3/phase13"
    with (base / "ai_assisted_passage_labels_extended.csv").open(encoding="utf-8") as handle:
        grades = {(row["question_id"], row["chunk_id"]): int(row["ai_relevance_grade"])
                  for row in csv.DictReader(handle)}
    with (base / "phase13b_rankings_v2.csv").open(encoding="utf-8") as handle:
        rows = sorted((row for row in csv.DictReader(handle)
                       if row["question_id"] == "Q015" and row["method_id"] == "hybrid-rrf-v1"),
                      key=lambda row: int(row["rank"]))
    selected = next(row for row in rows if grades.get(("Q015", row["chunk_id"])) == 2)
    source = next(item for item in validate_manifest() if item["source_id"] == selected["source_id"])
    match = re.fullmatch(re.escape(source["source_id"]) + r"-p(\d+)-c(\d+)", selected["chunk_id"])
    if not match or int(match[1]) != int(selected["page"]):
        raise ValueError("frozen evidence provenance mismatch")
    page, chunk_index = int(match[1]), int(match[2])
    text = PdfReader(str(RAW_DOCS_DIR / source["filename"])).pages[page - 1].extract_text()
    normalized = " ".join((text or "").replace("\x00", "ti").split())
    chunk = chunk_page(normalized)[chunk_index]
    return {"source_id": source["source_id"], "document": source["title"],
            "page": page, "chunk_id": selected["chunk_id"],
            "excerpt": chunk[:400] + ("…" if len(chunk) > 400 else "")}


def population_chart(history):
    frame = pd.DataFrame(history).rename(columns={
        "remaining_population": "Waiting", "in_transit_population": "In Transit",
        "safe_population": "Safe"})
    long = frame.melt(id_vars=["timestep", "sample", "phase"],
                      value_vars=["Waiting", "In Transit", "Safe"],
                      var_name="Population", value_name="People")
    return alt.Chart(long).mark_line(point=True).encode(
        x=alt.X("timestep:Q", title="Timestep", axis=alt.Axis(tickMinStep=1)),
        y=alt.Y("People:Q", scale=alt.Scale(zero=True)),
        order="sample:Q", color=alt.Color("Population:N", scale=alt.Scale(
            domain=["Waiting", "In Transit", "Safe"], range=["#d58a1b", "#1b9bc4", "#128268"])),
        tooltip=["timestep:Q", "phase:N", "Population:N", "People:Q"],
    ).properties(height=260)


def shelter_chart(state):
    rows = [{"Shelter": shelter.shelter_id, "Capacity": kind, "People": value}
            for shelter in state.shelters for kind, value in (
                ("Occupied", shelter.occupancy_current), ("Reserved", shelter.capacity_reserved),
                ("Available", shelter.capacity_available))]
    return alt.Chart(pd.DataFrame(rows)).mark_bar().encode(
        x=alt.X("Shelter:N", axis=alt.Axis(labelAngle=0)), y=alt.Y("People:Q", stack="zero"),
        color=alt.Color("Capacity:N", scale=alt.Scale(domain=["Occupied", "Reserved", "Available"],
                                                      range=["#128268", "#1b9bc4", "#dce6eb"])),
        tooltip=["Shelter:N", "Capacity:N", "People:Q"],
    ).properties(height=260)


def main():
    st.set_page_config(page_title="Sentinel-Agent V3 · Live Simulation", page_icon="◈", layout="wide")
    st.markdown("""<style>
    .block-container {max-width:1450px; padding-top:1.6rem;}
    .hero {padding:1.4rem 1.7rem; border-radius:16px; color:white;
           background:linear-gradient(110deg,#10243e,#146375); margin-bottom:1rem;}
    .hero h1 {font-size:2rem; color:white; margin:0;}
    .hero p {margin:.45rem 0 0; color:#d9f0f4;}
    @media (max-width:900px) {
      .st-key-map_panel [data-testid="stHorizontalBlock"] {flex-direction:column;}
      .st-key-map_panel [data-testid="stColumn"] {width:100% !important; flex:1 1 100% !important;}
    }
    </style>""", unsafe_allow_html=True)
    st.markdown(
        '<div class="hero"><h1>Sentinel-Agent V3<br>Live Flood Evacuation Simulation</h1>'
        '<p>Evidence-Grounded Decision Support Under Dynamic Uncertainty</p></div>',
        unsafe_allow_html=True,
    )
    st.info("REAL ROAD TOPOLOGY + SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED")
    st.caption("OpenStreetMap roads are real. Flood hazards, population, shelters, travel speeds, closures and decisions are simulated.")

    with st.sidebar:
        st.subheader("Scenario controls")
        preset = st.selectbox("Presentation preset", list(PRESETS), key="demo_preset")
        if st.button("Apply preset", key="apply_preset"):
            st.session_state.demo_seed, st.session_state.demo_regime = PRESETS[preset]
        seed = int(st.number_input("Scenario generator seed", min_value=0, max_value=2**31 - 1,
                                   value=620000, step=1, key="demo_seed"))
        regime = st.selectbox("Uncertainty regime", ["LOW", "MEDIUM", "HIGH"], index=1, key="demo_regime")
        st.write("**Planner:** Risk-Greedy")
        config = get_uncertainty_config(f"v3-{regime.lower()}-v1")
        reset = st.button("RESET", key="reset_demo", use_container_width=True)
        if reset or "live_simulation" not in st.session_state:
            st.session_state.live_simulation = SimulationSession(seed, config, graph=static_graph())
            for key in ("override_reason", "reject_reason", "accept_note", "override_action"):
                st.session_state.pop(key, None)
            st.session_state.demo_notice = "Scenario initialized."
        st.caption("Choose seed/regime and RESET to apply. Reset clears this browser session's decisions and history.")

    session = st.session_state.live_simulation
    context = session.context()
    state = session.state
    try:
        evidence = load_evidence()
        evidence_ref = EvidenceReference(evidence["source_id"], evidence["page"], evidence["chunk_id"])
        evidence_error = None
    except (OSError, ValueError, KeyError, StopIteration, IndexError) as exc:
        evidence, evidence_ref, evidence_error = None, None, str(exc)

    def submit(decision, *, alternative=None, reason=""):
        try:
            if evidence_ref is None:
                raise HumanDecisionError("Local authoritative context must load before recording a decision.")
            record, transition = session.decide(decision, evidence_ref, selected_action=alternative, reason=reason)
            st.session_state.demo_notice = (
                f"{record['audit_id']} · {decision} · executed {record['executed_action']} · "
                + (f"advanced to timestep {transition.new_timestep}" if transition else "time unchanged")
            )
        except HumanDecisionError as exc:
            st.error(str(exc))
            return
        st.rerun()

    with st.sidebar:
        st.caption(f"Active: seed {session.seed} · {session.simulator.config.level.value}")
        if st.button("STEP / ADVANCE", key="advance_demo", disabled=context is None or evidence_ref is None,
                     use_container_width=True, type="primary"):
            submit("ACCEPT", reason="Operator used STEP / ADVANCE.")
        st.caption("STEP / ADVANCE accepts the current recommendation and runs exactly one simulator transition.")

    metric_groups = [
        [("Initial population", state.initial_evacuation_population),
         ("Waiting", state.population_remaining), ("In transit", state.people_in_transit),
         ("Safely arrived", state.people_safely_arrived)],
        [("Timestep / horizon", f"{state.current_timestep} / {session.scenario.time.horizon_steps}"),
         ("Open shelters", sum(s.status_current.value == "OPEN" for s in state.shelters)),
         ("Closed roads", sum(not edge.open for edge in session.overlay.road_state.edges))],
    ]
    for group in metric_groups:
        for col, (label, value) in zip(st.columns(len(group)), group):
            col.metric(label, value)

    if state.terminal:
        st.success("EVACUATION EPISODE COMPLETE")
        st.json(session.summary())
        st.caption("One simulated episode is a demonstration, not a scientific evaluation result.")
    if st.session_state.get("demo_notice"):
        st.success(st.session_state.demo_notice)

    with st.container(key="map_panel"):
        map_col, decision_col = st.columns([1.7, 1])
        action = context.recommendation.action if context else None
        path = path_for_action(session.graph, session.overlay.road_state, action) if action else None
        with map_col:
            st.subheader("Fort Kochi · live road network")
            st.altair_chart(road_graph_chart(session.graph, session.overlay.road_state,
                                            path.edge_ids if path and path.reachable else ()), width="stretch")
            st.caption(f"{session.graph.location} · © OpenStreetMap contributors · ODbL · offline topology\n\n"
                       f"{session.graph.graph_version} · {len(session.graph.nodes)} nodes · {len(session.graph.edges)} directed edges")
        with decision_col:
            st.subheader("CURRENT RECOMMENDATION")
            if context:
                st.markdown(f"### {action_label(action)}")
                st.write(f"**Risk-Greedy** · {recommended_batch_size(context)} people")
                evaluation = context.recommendation_evaluation
                st.write(
                    f"Mechanical validity: **{'PASS' if evaluation.mechanically_valid else 'FAIL'}** · "
                    f"Hard safety: **{'PASS' if evaluation.hard_safety_allowed else 'FAIL'}**"
                )
                if isinstance(action, DispatchAction):
                    destination = state.shelter(action.shelter_id)
                    st.write(f"Graph reachability: **{'REACHABLE' if path.reachable else 'UNREACHABLE'}**")
                    st.write(f"Distance: **{path.distance_m:.0f} m** · travel: **{path.travel_time_minutes:.2f} min**")
                    st.write(f"Path: **{len(path.edge_ids)} edges** · capacity available: **{destination.capacity_available}**")
                    st.write(f"Destination hazard: **{destination.flood_severity_current:.3f}**")
                    st.caption("Current graph travel estimate; realized dispatch travel also uses seeded simulator uncertainty.")
                else:
                    st.info("WAIT: no dispatch recommended. One accepted WAIT advances the simulator; no graph path is selected.")
                note = st.text_input("Optional operator note", key="accept_note")
                if st.button("ACCEPT RECOMMENDATION", key="accept_demo", type="primary", disabled=evidence_ref is None):
                    submit("ACCEPT", reason=note)
                with st.expander("OVERRIDE · allowed alternatives"):
                    alternatives = allowed_override_actions(context)
                    selected = st.selectbox("Safe alternative", alternatives, format_func=action_label,
                                            key="override_action") if alternatives else None
                    if selected is not None:
                        preview = path_for_action(session.graph, session.overlay.road_state, selected)
                        if preview:
                            st.caption(f"Alternative path: {preview.distance_m:.0f} m · {preview.travel_time_minutes:.2f} min · {len(preview.edge_ids)} edges")
                    reason = st.text_input("Override reason (required)", key="override_reason")
                    if st.button("OVERRIDE", key="override_demo", disabled=selected is None or evidence_ref is None):
                        submit("OVERRIDE", alternative=selected, reason=reason)
                with st.expander("REJECT · record reason and hold time"):
                    reason = st.text_input("Rejection reason (required)", key="reject_reason")
                    if st.button("REJECT", key="reject_demo", disabled=evidence_ref is None):
                        submit("REJECT", reason=reason)
                    st.caption("REJECT records NONE and does not advance time. To advance without dispatch, override with allowed WAIT and a reason.")
            else:
                st.caption("Episode complete. RESET starts another scenario.")
            with st.expander("Why are some actions unavailable?"):
                if context:
                    evaluations = context.snapshot.evaluations
                    st.write(f"Theoretical actions: **{len(evaluations)}** · mechanically valid: "
                             f"**{sum(e.mechanically_valid for e in evaluations)}** · hard-safety permitted: "
                             f"**{sum(e.final_allowed for e in evaluations)}** (includes WAIT)")
                    st.dataframe(pd.DataFrame([{
                        "Action": e.action_key, "Mechanical": e.mechanically_valid,
                        "Hard safety": e.hard_safety_allowed, "Allowed": e.final_allowed,
                        "Exclusion": "; ".join(v.reason for v in e.exclusions),
                    } for e in evaluations]), hide_index=True, width="stretch")
                st.caption("Empty source, full/unavailable shelter, closed/unreachable route and destination hazard at or above 0.70 exclude dispatches. The hazard limit is a synthetic project rule. This is the same safety/action-mask concept used by MaskablePPO.")

    st.subheader("Waiting → In Transit → Safe")
    st.altair_chart(population_chart(session.population_history), width="stretch")
    st.caption("Actual session snapshots. Dispatch and next observation may share a timestep; short trips can arrive at that next observation. Hover to distinguish the two stages.")
    st.subheader("Live zones and shelters")
    zone_col, shelter_col = st.columns([1, 1.4])
    with zone_col:
        definitions = {z.zone_id: z for z in session.scenario.zones}
        st.dataframe(pd.DataFrame([{
            "Zone": z.zone_id, "Initial": definitions[z.zone_id].population_initial_remaining,
            "Waiting": z.population_remaining, "Vulnerable (initial)": definitions[z.zone_id].vulnerable_population,
            "Medical priority (initial)": definitions[z.zone_id].medical_priority_population,
            "Hazard": z.flood_severity_current,
        } for z in state.zones]), hide_index=True, width="stretch")
    with shelter_col:
        st.dataframe(pd.DataFrame([{
            "Shelter": s.shelter_id, "Status": s.status_current.value, "Capacity": s.capacity_total,
            "Occupancy": s.occupancy_current, "Reserved": s.capacity_reserved,
            "Available": s.capacity_available, "Hazard": s.flood_severity_current,
        } for s in state.shelters]), hide_index=True, width="stretch")
    transit_col, utilization_col = st.columns([1, 1.4])
    with transit_col:
        st.subheader("In-transit groups")
        def transit_rows(snapshot):
            return [{"Source": e.source_zone_id, "Destination": e.destination_shelter_id,
                     "People": e.people, "Dispatch timestep": e.departure_timestep,
                     "ETA timestep": e.arrival_timestep,
                     "Remaining steps": max(0, e.arrival_timestep - snapshot.current_timestep)}
                    for e in snapshot.pending_dispatches]
        rows = transit_rows(state)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.caption("No groups currently in transit.")
        if session.last_transition and session.last_transition.events_created:
            st.write(f"**Latest dispatch:** {session.last_transition.people_dispatched} people entered transit.")
            with st.expander("Actual snapshot after dispatch, before current arrivals", expanded=not rows):
                st.dataframe(pd.DataFrame(transit_rows(session.last_transition.state)), hide_index=True, width="stretch")
                st.caption("Committed transition snapshot; current population metrics above include arrivals processed by the next observation.")
    with utilization_col:
        st.subheader("Shelter utilization")
        st.altair_chart(shelter_chart(state), width="stretch")
        st.caption("Occupancy includes the scenario's initial shelter residents; safe population counts this episode's arrivals only.")

    st.subheader("Live events and session timeline")
    if session.timeline:
        timeline = pd.DataFrame(session.timeline)
        display_columns = ["timestep", "category", "event_type", "description", "people", "zone_id", "shelter_id", "route_id"]
        st.write("**Latest events**")
        st.dataframe(timeline.reindex(columns=display_columns).tail(10), hide_index=True, width="stretch")
        with st.expander("Complete event timeline"):
            st.dataframe(timeline.reindex(columns=display_columns), hide_index=True, width="stretch")
    else:
        st.caption("No human decisions or simulator transitions yet.")
    with st.expander("Current routing state"):
        st.dataframe(pd.DataFrame(session.route_rows()), hide_index=True, width="stretch")
        st.caption("UNREACHABLE has no fallback path. Closed graph edges are removed; absorbing simulator route closures also prevent dispatch. Later closures do not reroute groups already in transit.")
    with st.expander("Zone hazard evolution"):
        st.altair_chart(alt.Chart(pd.DataFrame(session.hazard_history)).mark_line(point=True).encode(
            x=alt.X("timestep:Q", axis=alt.Axis(tickMinStep=1)), y=alt.Y("hazard:Q", scale=alt.Scale(domain=[0, 1])),
            color="zone:N", tooltip=["zone:N", "timestep:Q", "hazard:Q"]
        ).properties(height=230), width="stretch")

    with st.expander("AUTHORITATIVE CONTEXT · offline NDMA", expanded=True):
        if evidence:
            st.write(f"**{evidence['document']}** · PDF page {evidence['page']} · `{evidence['chunk_id']}`")
            st.write(evidence["excerpt"])
        else:
            st.error(f"Local evidence unavailable: {evidence_error}")
        st.caption("Authoritative context does not automatically support every claim. Claim-support verification is still undergoing the paused Phase 14B evaluation.")

    st.subheader("Session summary and audit")
    st.json(session.summary(), expanded=False)
    with st.expander("Human-decision audit records"):
        st.dataframe(pd.DataFrame(session.audit), hide_index=True, width="stretch")
        st.caption("UTC timestamps, both recommendation and executed-path provenance, and evidence references. No full PDF passages are stored.")
    csv_col, json_col = st.columns(2)
    csv_col.download_button("Download CSV audit", session.export_csv(), "sentinel_simulation_audit.csv", "text/csv")
    json_col.download_button("Download JSON session", session.export_json(), "sentinel_simulation_session.json", "application/json")
    with st.expander("Reproducibility and technical details"):
        st.write(f"Generator seed: `{session.seed}` · simulator root seed: `{session.scenario.seed}`")
        st.write(f"Uncertainty: `{session.simulator.config.config_id}` · simulator: `StochasticSimulator`, V3 Phase 3/4 · scenario schema: `{session.scenario.schema_version}`")
        st.write(f"Graph: `{session.graph.graph_version}` · SHA-256: `{session.graph.graph_fingerprint}`")
        st.caption("Same generator seed + same uncertainty config/version + same graph + same actions = same stochastic evolution. Human timestamps differ. All runtime assets are local; dynamic state stays in this browser session.")
    with st.expander("How does the simulation work?"):
        st.markdown("""1. The simulator maintains zones, shelters, routes and in-transit groups.
2. Seeded flood, travel, closure and shelter conditions evolve.
3. Mechanical validity removes impossible actions.
4. Hard safety removes unsafe actions.
5. Risk-Greedy recommends an allowed evacuation or WAIT.
6. A human accepts, overrides or rejects; accepted actions advance the simulator.""")
    with st.expander("Compact research status"):
        st.markdown("""- Phase 10: **RL usefulness = NO**. PPO: experimentally evaluated — not selected after held-out evaluation.
- Phase 13: **HYBRID_SUPPORTED vs Dense**. **BM25 highest DirectHit@5**; labels are AI-assisted.
- Phase 14A: claim-support benchmark complete.
- Phase 14B: **PAUSED / incomplete — 21 / 135 official dispositions**. No partial performance metrics.""")


if __name__ == "__main__":
    main()
