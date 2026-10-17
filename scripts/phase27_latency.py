"""Phase 27 latency (Q5, 27C): certify-only and end-to-end latency at n = 256 on 20 sampled states.

    python scripts/phase27_latency.py [--label laptop]

Uses the stored P decision states (data/eval_results/phase27/states). Run on a quiet machine. Writes
data/eval_results/phase27/latency.json (appends one entry per label). Targets p95 <= 100 ms certify-only
and <= 10 s end-to-end; no bar for the lead claim. Raspberry Pi runs reuse this script once Phase 28
hardware exists.
"""

from __future__ import annotations

import argparse
import dataclasses
import gzip
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data/eval_results/phase27"
N_STATES = 20


def pick_states():
    rows = []
    for path in sorted((OUT / "states").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            rows += [json.loads(line) for line in handle if line.strip()]
    step = max(1, len(rows) // N_STATES)
    return rows[::step][:N_STATES]


def pct(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="laptop")
    args = parser.parse_args()
    from src.certify.certificate import CertificateInputs
    from src.certify.certifier import certify
    from src.certify.futures import FutureSet, root_key
    from src.certify.gate import ledger_view_hash
    from src.certify.params import get_cert_params
    from src.geospatial import load_road_graph
    from src.sim.world import get_world_config

    graph = load_road_graph()
    only, end_to_end = [], []
    for row in pick_states():
        inputs = CertificateInputs.from_dict(row["inputs"])
        world = get_world_config(inputs.world_id)
        # n = 256: a single look of the evaluation parameters
        params = dataclasses.replace(get_cert_params(inputs.params_id), max_looks=1)
        fc = inputs.forecast
        root = root_key(incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
                        graph_fingerprint=graph.graph_fingerprint, ledger_hash=ledger_view_hash(inputs.ledger),
                        params_id=params.params_id, backend=params.backend)
        t0 = time.perf_counter()
        fs = FutureSet(fc, graph, world, root, inputs.horizon_steps, edge_ids=inputs.edge_ids)
        for k in range(1, params.k0 + 1):
            fs.future(k)  # generation counts toward end-to-end, not certify-only
        generated = time.perf_counter()
        certify(list(inputs.candidates), fs, inputs.ledger, world, params, graph)
        done = time.perf_counter()
        only.append((done - generated) * 1000.0)
        end_to_end.append((done - t0) * 1000.0)
    entry = {
        "label": args.label, "machine": platform.platform(), "processor": platform.processor(),
        "states": len(only), "n": 256,
        "certify_only_ms": {"p50": statistics.median(only), "p95": pct(only, 0.95)},
        "end_to_end_ms": {"p50": statistics.median(end_to_end), "p95": pct(end_to_end, 0.95)},
        "targets_ms": {"certify_only_p95": 100, "end_to_end_p95": 10_000},
        "energy": "not measured (no USB power meter)",
    }
    path = OUT / "latency.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    path.write_text(json.dumps(existing + [entry], indent=2), encoding="utf-8")
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
