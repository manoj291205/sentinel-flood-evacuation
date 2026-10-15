"""Project the loaded Fort Kochi road graph to a compact SVG map."""

from __future__ import annotations

import heapq
import math

from src.geospatial.road_network import RoadGraph


def project_graph(graph: RoadGraph, width: int = 880, height: int = 789) -> dict:
    lat0 = sum(node.lat for node in graph.nodes) / len(graph.nodes)
    cos_lat = math.cos(math.radians(lat0))
    raw = {node.node_id: (node.lon * cos_lat, -node.lat) for node in graph.nodes}
    xs = [point[0] for point in raw.values()]
    ys = [point[1] for point in raw.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad = 20.0
    scale = min((width - 2 * pad) / (max_x - min_x), (height - 2 * pad) / (max_y - min_y))
    points = {
        node_id: (round(pad + (x - min_x) * scale, 1), round(pad + (y - min_y) * scale, 1))
        for node_id, (x, y) in raw.items()
    }

    def segment(u: str, v: str) -> str:
        x1, y1 = points[u]
        x2, y2 = points[v]
        return f"M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}"

    major_types = {"primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}
    major = []
    minor = []
    for edge in graph.edges:
        (major if edge.highway in major_types else minor).append(segment(edge.u, edge.v))

    adjacency: dict[str, list[tuple[float, str]]] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.u, []).append((edge.length_m, edge.v))

    def route(source: str, destination: str) -> tuple[str, float] | None:
        start = graph.zone_node_map[source]
        goal = graph.shelter_node_map[destination]
        queue = [(0.0, start)]
        best = {start: 0.0}
        previous: dict[str, str] = {}
        while queue:
            distance, node = heapq.heappop(queue)
            if node == goal:
                break
            if distance > best[node]:
                continue
            for length, neighbor in adjacency.get(node, ()):
                next_distance = distance + length
                if next_distance < best.get(neighbor, math.inf):
                    best[neighbor] = next_distance
                    previous[neighbor] = node
                    heapq.heappush(queue, (next_distance, neighbor))
        if goal not in best:
            return None
        path = [goal]
        while path[-1] != start:
            path.append(previous[path[-1]])
        path.reverse()
        return "".join(segment(a, b) for a, b in zip(path, path[1:])), round(best[goal], 3)

    output = {
        "W": width, "H": height,
        "px_per_m": scale / 111_320,
        "major": "".join(major), "minor": "".join(minor),
        "zones": {zone: points[node] for zone, node in graph.zone_node_map.items()},
        "shelters": {shelter: points[node] for shelter, node in graph.shelter_node_map.items()},
        "closed": "",
        "graph_version": graph.graph_version,
        "graph_fingerprint": graph.graph_fingerprint,
    }
    for zone, shelter in (("Z3", "S4"), ("Z1", "S2"), ("Z2", "S5"), ("Z4", "S1")):
        if zone in graph.zone_node_map and shelter in graph.shelter_node_map:
            value = route(zone, shelter)
            if value is not None:
                output[f"route_{zone}_{shelter}"] = value
    return output
