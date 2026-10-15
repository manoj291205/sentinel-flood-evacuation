"""P24 latency: certify-only and end-to-end (future generation included) at n = 256, seed 620000."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import replace
from pathlib import Path

from src.certify.certifier import certify
from src.certify.forecast import forecast_from_state, ledger_hash
from src.certify.futures import FutureSet, root_key
from src.certify.ledger_view import ledger_view_from_state
from src.certify.params import CertParams
from src.certify.rollout import Candidate
from src.geospatial import load_road_graph, shortest_valid_path
from src.geospatial.v4_runtime import build_v4_runtime
from src.safety import evaluate_actions
from src.sim import DispatchAction

OUT = Path(__file__).resolve().parents[1] / "data/eval_results/phase24/latency.json"


def p(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def main(repeats: int = 5) -> None:
    graph = load_road_graph()
    params = replace(CertParams(), max_looks=1)  # n = 256 exactly
    certify_only, end_to_end = [], []
    for _ in range(repeats):
        scenario, sim, _, overlay, world = build_v4_runtime("v4-medium-dt2-v1", generator_seed=620000, graph=graph)
        sim.observe()
        state = sim.prepared_state_for_debug()
        snapshot = evaluate_actions(scenario, state)
        paths = {}
        for zone in scenario.zones:
            for shelter in scenario.shelters:
                path = shortest_valid_path(graph, overlay.road_state, graph.zone_node_map[zone.zone_id],
                                           graph.shelter_node_map[shelter.shelter_id])
                if path.reachable:
                    paths[(zone.zone_id, shelter.shelter_id)] = path.edge_ids
        candidates = []
        for a in snapshot.allowed_actions:
            if isinstance(a, DispatchAction) and (a.zone_id, a.shelter_id) in paths:
                people = min(scenario.fleet.vehicle_capacity, state.zone(a.zone_id).population_remaining,
                             state.shelter(a.shelter_id).capacity_available)
                candidates.append(Candidate(a.zone_id, a.shelter_id, people, paths[(a.zone_id, a.shelter_id)], 0))
        started = time.perf_counter()
        forecast = forecast_from_state(state, overlay.road_state, scenario)
        root = root_key(incident_id=forecast.incident_id, forecast_hash=forecast.forecast_hash(),
                        graph_fingerprint=graph.graph_fingerprint, ledger_hash=ledger_hash(state),
                        params_id=params.params_id)
        futures = FutureSet(forecast, graph, world, root, horizon_steps=10,
                            edge_ids=tuple(sorted({e for pth in paths.values() for e in pth})))
        for k in range(1, params.k0 + 1):
            futures.future(k)
        built = time.perf_counter()
        certify(candidates, futures, ledger_view_from_state(state, {}), world, params, graph)
        done = time.perf_counter()
        certify_only.append((done - built) * 1000.0)
        end_to_end.append((done - started) * 1000.0)
    result = {
        "n": params.k0, "candidates": len(candidates), "repeats": repeats,
        "certify_only_ms": {"p50": p(certify_only, 0.5), "p95": p(certify_only, 0.95)},
        "end_to_end_ms": {"p50": p(end_to_end, 0.5), "p95": p(end_to_end, 0.95)},
        "targets": {"certify_only_p95_ms": 100.0, "end_to_end_p95_ms": 10000.0},
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
