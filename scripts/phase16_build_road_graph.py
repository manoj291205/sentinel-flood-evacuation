#!/usr/bin/env python3
"""Build the frozen Phase 16 demo graph from a local Overpass JSON response.

The input is a one-time development download. Only the compact, canonical graph and
its manifest are required at runtime; the dashboard never contacts OpenStreetMap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import networkx as nx

GRAPH_VERSION = "fort-kochi-osm-drive-v1"
BOUNDS = {"south": 9.961, "west": 76.238, "north": 9.969, "east": 76.247}
OVERPASS_QUERY = (
    "[out:json][timeout:30];way[highway](9.9610,76.2380,9.9690,76.2470);"
    "(._;>;);out body;"
)
DRIVABLE_HIGHWAYS = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "residential",
    "living_street",
    "unclassified",
    "service",
    "road",
}
ASSUMED_SPEED_KPH = {
    "motorway": 60.0,
    "motorway_link": 40.0,
    "trunk": 50.0,
    "trunk_link": 35.0,
    "primary": 40.0,
    "primary_link": 30.0,
    "secondary": 35.0,
    "secondary_link": 25.0,
    "tertiary": 30.0,
    "tertiary_link": 25.0,
    "residential": 22.0,
    "living_street": 15.0,
    "unclassified": 20.0,
    "service": 12.0,
    "road": 20.0,
}

# Fictional demo entities are snapped to deterministic positions on real topology.
ENTITY_TARGETS = {
    "zones": {
        "Z1": (0.14, 0.18),
        "Z2": (0.82, 0.18),
        "Z3": (0.18, 0.80),
        "Z4": (0.80, 0.78),
    },
    "shelters": {
        "S1": (0.50, 0.12),
        "S2": (0.12, 0.50),
        "S3": (0.52, 0.50),
        "S4": (0.87, 0.50),
        "S5": (0.50, 0.88),
    },
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _haversine_m(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, left)
    lat2, lon2 = map(math.radians, right)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6_371_000.0 * 2 * math.asin(math.sqrt(value))


def _graph_fingerprint(graph: dict[str, object]) -> str:
    static = {
        "graph_version": graph["graph_version"],
        "coordinate_reference": graph["coordinate_reference"],
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "zone_node_map": graph["zone_node_map"],
        "shelter_node_map": graph["shelter_node_map"],
    }
    return hashlib.sha256(_canonical_json(static)).hexdigest()


def _nearest_unique_nodes(
    nodes: list[dict[str, object]], targets: dict[str, tuple[float, float]]
) -> dict[str, str]:
    used: set[str] = set()
    result: dict[str, str] = {}
    lat_span = BOUNDS["north"] - BOUNDS["south"]
    lon_span = BOUNDS["east"] - BOUNDS["west"]
    for entity_id, (x_fraction, y_fraction) in targets.items():
        target_lat = BOUNDS["south"] + y_fraction * lat_span
        target_lon = BOUNDS["west"] + x_fraction * lon_span
        candidates = sorted(
            nodes,
            key=lambda node: (
                (float(node["lat"]) - target_lat) ** 2
                + (float(node["lon"]) - target_lon) ** 2,
                str(node["node_id"]),
            ),
        )
        selected = next(node for node in candidates if node["node_id"] not in used)
        node_id = str(selected["node_id"])
        result[entity_id] = node_id
        used.add(node_id)
    return result


def build(overpass: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    elements = overpass.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass response has no elements array")
    coordinates = {
        int(item["id"]): (float(item["lat"]), float(item["lon"]))
        for item in elements
        if item.get("type") == "node" and "lat" in item and "lon" in item
    }
    edge_candidates: list[dict[str, object]] = []
    for way in elements:
        if way.get("type") != "way":
            continue
        tags = way.get("tags", {})
        highway = tags.get("highway")
        if highway not in DRIVABLE_HIGHWAYS:
            continue
        way_nodes = way.get("nodes", [])
        oneway = str(tags.get("oneway", "")).lower()
        directions = ("reverse",) if oneway == "-1" else ("forward",)
        if oneway not in {"yes", "1", "true", "-1"} and tags.get("junction") != "roundabout":
            directions = ("forward", "reverse")
        for index, (raw_u, raw_v) in enumerate(zip(way_nodes, way_nodes[1:])):
            if raw_u not in coordinates or raw_v not in coordinates:
                continue
            length_m = _haversine_m(coordinates[raw_u], coordinates[raw_v])
            if length_m < 0.5:
                continue
            travel_minutes = length_m / (ASSUMED_SPEED_KPH[highway] * 1000 / 60)
            for direction in directions:
                u, v = (raw_u, raw_v) if direction == "forward" else (raw_v, raw_u)
                edge_candidates.append(
                    {
                        "edge_id": f"osm-w{way['id']}-{index}-{'f' if direction == 'forward' else 'r'}",
                        "u": f"osm-n{u}",
                        "v": f"osm-n{v}",
                        "osm_way_id": str(way["id"]),
                        "highway": highway,
                        "name": tags.get("name"),
                        "length_m": round(length_m, 3),
                        "assumed_speed_kph": ASSUMED_SPEED_KPH[highway],
                        "base_travel_time_minutes": round(travel_minutes, 6),
                    }
                )

    # Collapse parallel directed segments deterministically to the fastest edge.
    by_pair: dict[tuple[str, str], dict[str, object]] = {}
    for edge in edge_candidates:
        pair = (str(edge["u"]), str(edge["v"]))
        previous = by_pair.get(pair)
        if previous is None or (
            float(edge["base_travel_time_minutes"]), str(edge["edge_id"])
        ) < (
            float(previous["base_travel_time_minutes"]), str(previous["edge_id"])
        ):
            by_pair[pair] = edge

    directed = nx.DiGraph()
    for edge in by_pair.values():
        directed.add_edge(str(edge["u"]), str(edge["v"]))
    if not directed:
        raise ValueError("no drivable road edges found")
    component = max(nx.weakly_connected_components(directed), key=lambda item: (len(item), sorted(item)))
    edges = sorted(
        (
            edge
            for edge in by_pair.values()
            if edge["u"] in component and edge["v"] in component
        ),
        key=lambda edge: str(edge["edge_id"]),
    )
    retained_ids = sorted(
        {str(edge["u"]) for edge in edges} | {str(edge["v"]) for edge in edges}
    )
    nodes = [
        {
            "node_id": node_id,
            "lat": round(coordinates[int(node_id.removeprefix("osm-n"))][0], 7),
            "lon": round(coordinates[int(node_id.removeprefix("osm-n"))][1], 7),
        }
        for node_id in retained_ids
    ]
    graph: dict[str, object] = {
        "graph_version": GRAPH_VERSION,
        "location": "Fort Kochi, Kerala, India (compact demonstration extract)",
        "bounds_wgs84": BOUNDS,
        "coordinate_reference": "EPSG:4326 (WGS84 latitude/longitude)",
        "topology_source": "OpenStreetMap contributors via Overpass API",
        "topology_license": "Open Database License (ODbL); © OpenStreetMap contributors",
        "routing_assumption": (
            "Travel speeds are synthetic class-based demo assumptions, not observed traffic."
        ),
        "nodes": nodes,
        "edges": edges,
        "zone_node_map": _nearest_unique_nodes(nodes, ENTITY_TARGETS["zones"]),
        "shelter_node_map": _nearest_unique_nodes(nodes, ENTITY_TARGETS["shelters"]),
    }
    graph["graph_fingerprint"] = _graph_fingerprint(graph)
    osm_base = overpass.get("osm3s", {}).get("timestamp_osm_base")
    manifest = {
        "graph_version": GRAPH_VERSION,
        "location": graph["location"],
        "bounds_wgs84": BOUNDS,
        "coordinate_reference": graph["coordinate_reference"],
        "source": graph["topology_source"],
        "license": graph["topology_license"],
        "osm_snapshot_timestamp": osm_base,
        "overpass_query": OVERPASS_QUERY,
        "network_filter": sorted(DRIVABLE_HIGHWAYS),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "directed_edge_count": len(edges),
        "graph_fingerprint": graph["graph_fingerprint"],
        "canonicalization": (
            "SHA-256 of sorted-key compact JSON containing graph_version, CRS, sorted "
            "nodes, sorted directed edges, and zone/shelter node mappings; dynamic "
            "hazard and closure state excluded."
        ),
        "runtime_network_required": False,
        "disaster_overlay": "SIMULATED",
    }
    return graph, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("overpass_json", type=Path)
    parser.add_argument(
        "--graph", type=Path, default=Path("data/geospatial_v3/fort_kochi_osm_drive_v1.json")
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/geospatial_v3/fort_kochi_osm_drive_v1_manifest.json"),
    )
    args = parser.parse_args()
    graph, manifest = build(json.loads(args.overpass_json.read_text(encoding="utf-8")))
    args.graph.parent.mkdir(parents=True, exist_ok=True)
    args.graph.write_text(
        json.dumps(graph, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"{graph['graph_version']}: {manifest['node_count']} nodes, "
        f"{manifest['directed_edge_count']} directed edges, "
        f"sha256={graph['graph_fingerprint']}"
    )


if __name__ == "__main__":
    main()
