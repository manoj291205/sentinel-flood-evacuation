#!/usr/bin/env python3
"""Score a complete Phase 14D practice or test ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.constraints.claim_support import (  # noqa: E402
    ClaimSupportResult, classification_metrics, label_independent_order,
    span_integrity_failure_rate, usefulness_gate,
)
from src.constraints.claim_support_p14d import (  # noqa: E402
    EVALUATION_ID, MODEL_ID, PROVIDER_ID, REQUEST_SETTINGS, TEMPERATURE_NOTE, prompt_sha256,
)

CHALLENGE_DIR = ROOT / "data/eval_v4/phase14d"
MANIFEST = CHALLENGE_DIR / "manifest.json"
PROTOCOL = ROOT / "specs/V4_CLAIM_SUPPORT_14D_SPEC.md"
DEFAULT_DIR = ROOT / "data/eval_results/phase14d"
OLD_DIRS = (ROOT / "data/eval_results/phase14b", ROOT / "data/eval_results/phase14c")


def _forbid_old(path: Path) -> None:
    resolved = path.resolve()
    if any(resolved == old.resolve() or resolved.is_relative_to(old.resolve()) for old in OLD_DIRS):
        raise ValueError("Phase 14D scoring must not use an earlier evaluation path")


def t2_gate(expected: Sequence[str], predicted: Sequence[str],
            integrity: Sequence[bool]) -> tuple[dict, str, dict]:
    if len(expected) != len(predicted) or len(expected) != len(integrity):
        raise ValueError("metric inputs must align")
    positives = [i for i, (verdict, valid) in enumerate(zip(predicted, integrity))
                 if verdict == "SUPPORTED" and valid]
    supported = sum(label == "SUPPORTED" for label in expected)
    unsafe = sum(label != "SUPPORTED" for label in expected)
    predicted_supported = sum(verdict == "SUPPORTED" for verdict in predicted)
    true_positives = sum(expected[i] == "SUPPORTED" for i in positives)
    metrics = {
        "t2_positive_count": len(positives),
        "t2_precision": true_positives / len(positives) if positives else 0.0,
        "t2_unsafe_acceptance": (len(positives) - true_positives) / unsafe if unsafe else 0.0,
        "t2_recall": true_positives / supported if supported else 0.0,
        "supported_integrity_failure": (
            (predicted_supported - len(positives)) / predicted_supported if predicted_supported else 0.0
        ),
    }
    conditions = {
        "t2_precision": metrics["t2_precision"] >= 0.95,
        "t2_unsafe_acceptance": metrics["t2_unsafe_acceptance"] <= 0.05,
        "t2_recall": metrics["t2_recall"] >= 0.70,
        "supported_integrity_failure": metrics["supported_integrity_failure"] <= 0.02,
    }
    verdict = "T2_VERIFIER_USEFUL" if all(conditions.values()) else "T2_VERIFIER_NOT_YET_RELIABLE"
    return metrics, verdict, conditions


def score(ledger_path: Path, out_path: Path, calls_path: Path | None = None,
          *, challenge_set: str = "test") -> dict:
    if challenge_set not in ("test", "practice"):
        raise ValueError("unknown challenge set")
    for path in (ledger_path, out_path, calls_path):
        if path is not None:
            _forbid_old(path)
    pairs = json.loads((CHALLENGE_DIR / f"challenge_{challenge_set}.json").read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {pair["claim_pair_id"]: pair for pair in pairs}
    fingerprint = manifest["sets"][challenge_set]["challenge_fingerprint"]
    order = label_independent_order(list(by_id), fingerprint)
    raw = ledger_path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(rows) != len(order) or [row.get("claim_pair_id") for row in rows] != order:
        raise ValueError("cannot score a partial or unordered ledger")
    prompt_version = rows[0]["prompt_version"]
    identity = {
        "evaluation_id": EVALUATION_ID, "provider_id": PROVIDER_ID, "model_id": MODEL_ID,
        "prompt_version": prompt_version, "prompt_sha256": prompt_sha256(prompt_version),
        "request_settings": REQUEST_SETTINGS, "challenge_id": manifest["challenge_id"],
        "challenge_set": challenge_set, "challenge_fingerprint": fingerprint,
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
    }
    for index, row in enumerate(rows):
        if row.get("order_index") != index or any(row.get(key) != value for key, value in identity.items()):
            raise ValueError("mixed ledger or mismatched protocol")
    expected = [by_id[row["claim_pair_id"]]["construction_label"] for row in rows]
    predicted = [row["verdict"] for row in rows]
    integrity = [row["source_integrity_pass"] for row in rows]
    t2_metrics, t2_verdict, t2_conditions = t2_gate(expected, predicted, integrity)
    results = [ClaimSupportResult(
        verdict=row["verdict"] if row["supporting_spans"] else "UNSUPPORTED",
        confidence=row["confidence"], supporting_spans=row["supporting_spans"],
        reason=row["reason"], source_integrity_pass=row["source_integrity_pass"],
    ) for row in rows]
    metrics = classification_metrics(expected, predicted)
    metrics["supported_precision"] = metrics["per_class"]["SUPPORTED"]["precision"]
    metrics["span_integrity_failure_rate"] = span_integrity_failure_rate(results)
    v3_verdict, v3_conditions = usefulness_gate({
        "macro_f1": metrics["macro_f1"], "supported_precision": metrics["supported_precision"],
        "unsafe_acceptance": metrics["unsafe_citation_acceptance_rate"],
        "span_integrity_failure": metrics["span_integrity_failure_rate"],
    })
    calls = []
    if calls_path is not None and calls_path.exists():
        calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    output = {
        **identity, "temperature_requested": REQUEST_SETTINGS["temperature"],
        "temperature_note": TEMPERATURE_NOTE, "ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "claim_pairs": len(rows), "verdict": t2_verdict, "t2_verdict": t2_verdict,
        "t2_conditions": t2_conditions, "t2_metrics": t2_metrics, "v3_verdict": v3_verdict,
        "v3_conditions": v3_conditions, "metrics": metrics,
        "supported_precision": metrics["supported_precision"], "macro_f1": metrics["macro_f1"],
        "calls_total": len(calls),
        "system_fingerprints": sorted({row["system_fingerprint"] for row in rows if row.get("system_fingerprint")}),
        "label": ("PRACTICE — not an evaluation result" if challenge_set == "practice"
                  else "Phase 14D (replaces 14C as the claim-support evaluation of record)"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="challenge_set", choices=("test", "practice"), default="test")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--calls", type=Path)
    args = parser.parse_args()
    default = DEFAULT_DIR / ("test" if args.challenge_set == "test" else "practice/round1")
    result = score(args.ledger or default / "dispositions.jsonl",
                   args.out or default / "score.json", args.calls or default / "calls.jsonl",
                   challenge_set=args.challenge_set)
    print(result["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
