"""Offline rendering of the existing geospatial road network."""

import altair as alt
import pandas as pd

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
                legend=alt.Legend(title="Road state", orient="bottom", columns=3),
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
                "kind:N", legend=alt.Legend(title="Entities", orient="bottom"),
                scale=alt.Scale(
                    domain=["SIMULATED ZONE", "SIMULATED SHELTER"],
                    range=["triangle-up", "square"],
                ),
            ),
            color=alt.Color(
                "kind:N", legend=None,
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
    return (roads + points + labels).resolve_scale(color="independent").properties(height=500).interactive()

