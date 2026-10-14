#!/usr/bin/env python3
"""Score a complete Phase 14B ledger against the frozen construction labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.constraints.claim_support import (  # noqa: E402
    ClaimSupportResult,
    classification_metrics,
    label_independent_order,
    span_integrity_failure_rate,
    usefulness_gate,
)

CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
MANIFEST = ROOT / "data/eval_v3/phase14/claim_support_manifest.json"
DEFAULT_LEDGER = ROOT / "data/eval_results/phase14b/dispositions.jsonl"
DEFAULT_SCORE = ROOT / "data/eval_results/phase14b/score.json"


def score(ledger_path: Path, out_path: Path) -> dict:
    pairs = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw = ledger_path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    by_id = {pair["claim_pair_id"]: pair for pair in pairs}
    order = label_independent_order(list(by_id), manifest["challenge_fingerprint"])
    if len(rows) != len(order) or [row["claim_pair_id"] for row in rows] != order:
        raise ValueError("cannot score a partial or unordered claim-support ledger")
    if any(row["order_index"] != index for index, row in enumerate(rows)):
        raise ValueError("ledger order indices do not match challenge order")
    if any(row["provider_id"] != rows[0]["provider_id"] or row["prompt_version"] != rows[0]["prompt_version"] for row in rows):
        raise ValueError("ledger mixes provider or prompt versions")
    results = [
        ClaimSupportResult(
            verdict=row["verdict"], confidence=row["confidence"],
            supporting_spans=row["supporting_spans"], reason=row["reason"],
            source_integrity_pass=row["source_integrity_pass"],
        ) for row in rows
    ]
    metrics = classification_metrics(
        [by_id[row["claim_pair_id"]]["construction_label"] for row in rows],
        [result.verdict for result in results],
    )
    metrics["supported_precision"] = metrics["per_class"]["SUPPORTED"]["precision"]
    metrics["span_integrity_failure_rate"] = span_integrity_failure_rate(results)
    gate_values = {
        "macro_f1": metrics["macro_f1"],
        "supported_precision": metrics["supported_precision"],
        "unsafe_acceptance": metrics["unsafe_citation_acceptance_rate"],
        "span_integrity_failure": metrics["span_integrity_failure_rate"],
    }
    verdict, conditions = usefulness_gate(gate_values)
    output = {
        "verdict": verdict,
        "conditions": conditions,
        "metrics": metrics,
        "ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "challenge_fingerprint": manifest["challenge_fingerprint"],
        "provider_id": rows[0]["provider_id"],
        "prompt_version": rows[0]["prompt_version"],
        "claim_pairs": len(rows),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--out", type=Path, default=DEFAULT_SCORE)
    args = parser.parse_args()
    result = score(args.ledger, args.out)
    print(result["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
