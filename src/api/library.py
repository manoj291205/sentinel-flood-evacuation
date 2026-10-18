"""Read-only views of the frozen Phase 27 and V3 evaluation artifacts."""

from __future__ import annotations

import csv
import gzip
import json
import math
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from src.geospatial.road_network import RoadGraph

ROOT = Path(__file__).resolve().parents[2]
P27 = ROOT / "data/eval_results/phase27"
REGIMES = {"v4-medium-dt2-v1", "v4-high-dt2-v1", "v4-stress-dt2-v1"}


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@lru_cache(maxsize=1)
def library_index() -> dict:
    runs: dict[tuple[str, str, int], dict] = {}
    for path in sorted((P27 / "runs").glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                key = (row["system"], row["regime"], row["seed"])
                runs.setdefault(key, {
                    **_json_safe(row),
                    "has_trace": row["system"] == "P" and
                    (P27 / "states" / f"{row['regime']}_{row['seed']}.jsonl.gz").is_file(),
                    "source_path": path.relative_to(ROOT).as_posix(),
                })
    return {
        "runs": list(runs.values()),
        "analysis": _json_safe(_read_json(P27 / "analysis.json")),
        "analysis_source": "data/eval_results/phase27/analysis.json",
        "source": "RECORDED SIMULATION",
    }


def _project_nodes(graph: RoadGraph, width: int = 880, height: int = 789) -> dict:
    lat0 = sum(node.lat for node in graph.nodes) / len(graph.nodes)
    cosine = math.cos(math.radians(lat0))
    raw = {node.node_id: (node.lon * cosine, -node.lat) for node in graph.nodes}
    xs = [xy[0] for xy in raw.values()]
    ys = [xy[1] for xy in raw.values()]
    minimum_x, minimum_y = min(xs), min(ys)
    scale = min((width - 40) / (max(xs) - minimum_x), (height - 40) / (max(ys) - minimum_y))
    return {key: (round(20 + (x - minimum_x) * scale, 1),
                  round(20 + (y - minimum_y) * scale, 1)) for key, (x, y) in raw.items()}


def _path(edge_ids: list[str], edges: dict, points: dict) -> str:
    parts = []
    for edge_id in edge_ids:
        edge = edges.get(edge_id)
        if edge is None:
            continue
        a, b = points[edge.u], points[edge.v]
        parts.append(f"M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}")
    return "".join(parts)


@lru_cache(maxsize=8)
def _trace(regime: str, seed: int, graph: RoadGraph) -> dict:
    if regime not in REGIMES or not 1_050_000 <= seed <= 1_050_059:
        raise HTTPException(404, "recorded trace not found")
    path = P27 / "states" / f"{regime}_{seed}.jsonl.gz"
    if not path.is_file():
        raise HTTPException(404, "recorded trace not found")
    edges = {edge.edge_id: edge for edge in graph.edges}
    points = _project_nodes(graph)
    steps = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            inputs = row["inputs"]
            forecast = inputs["forecast"]
            candidates = []
            for candidate in inputs["candidates"]:
                key = f"{candidate['zone_id']}->{candidate['shelter_id']}"
                candidates.append({
                    "action_key": key,
                    "people": candidate["people"],
                    "verdict": row["verdicts"].get(key, "UNAVAILABLE"),
                    "svg_path": _path(candidate["edge_ids"], edges, points),
                })
            steps.append({
                "timestep": row["timestep"], "chosen_key": row["chosen_key"],
                "looks": row["looks"], "futures_used": row["n_final"],
                "candidates": candidates,
                "zone_severity": dict(forecast["zone_severity"]),
                "shelter_severity": dict(forecast["shelter_severity"]),
                "edge_closed_path": _path([key for key, opened in forecast["edge_open"] if not opened], edges, points),
                "shelters": [{"id": shelter, "capacity": capacity,
                              "occupied": inputs["ledger"]["occupancy"][shelter],
                              "reserved": inputs["ledger"]["reserved"][shelter]}
                             for shelter, capacity in inputs["ledger"]["capacity_total"].items()],
            })
    return {"regime": regime, "seed": seed, "steps": steps,
            "source": "RECORDED SIMULATION", "source_path": path.relative_to(ROOT).as_posix(),
            "note": "Phase 27 state traces contain certifier inputs and choices, not per-step arrival or transit counters. Those counters are unavailable in replay."}


def library_trace(regime: str, seed: int, graph: RoadGraph) -> dict:
    return _trace(regime, seed, graph)


@lru_cache(maxsize=1)
def library_v3() -> dict:
    paths = {
        "heldout": "data/eval_v3/phase10/heldout_summary.json",
        "planner": "data/eval_v3/phase10/planner_summary.json",
        "ppo": "data/eval_v3/phase10/ppo_seed_summary.json",
        "gate6": "data/eval_v3/gate6_summary.json",
        "training": "data/eval_v3/training/training_summary.json",
    }
    curves = []
    curve_path = ROOT / "data/eval_v3/training/learning_curves.csv"
    with curve_path.open("r", encoding="utf-8", newline="") as stream:
        curves = list(csv.DictReader(stream))
    return {"source": "RECORDED SIMULATION", "items": {name: {"source_path": path, "data": _read_json(ROOT / path)}
                                                        for name, path in paths.items()},
            "curves": {"source_path": "data/eval_v3/training/learning_curves.csv", "rows": curves}}
