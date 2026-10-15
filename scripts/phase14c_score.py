#!/usr/bin/env python3
"""Score a complete Phase 14C ledger without changing the frozen challenge."""

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
from src.constraints.claim_support_p14c import (  # noqa: E402
    EVALUATION_ID,
    MODEL_ID,
    PROMPT_VERSION,
    PROVIDER_ID,
    REQUEST_SETTINGS,
    TEMPERATURE_NOTE,
)

CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
MANIFEST = ROOT / "data/eval_v3/phase14/claim_support_manifest.json"
PROTOCOL = ROOT / "specs/V4_CLAIM_SUPPORT_14C_SPEC.md"
DEFAULT_DIR = ROOT / "data/eval_results/phase14c"
PHASE14B_DIR = ROOT / "data/eval_results/phase14b"


def _forbid_14b(path: Path) -> None:
    resolved = path.resolve()
    if resolved == PHASE14B_DIR.resolve() or resolved.is_relative_to(PHASE14B_DIR.resolve()):
        raise ValueError("Phase 14C scoring must not use the phase14b path")


def score(ledger_path: Path, out_path: Path, calls_path: Path | None = None) -> dict:
    _forbid_14b(ledger_path)
    _forbid_14b(out_path)
    if calls_path is not None:
        _forbid_14b(calls_path)
    pairs = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {pair["claim_pair_id"]: pair for pair in pairs}
    order = label_independent_order(list(by_id), manifest["challenge_fingerprint"])
    raw = ledger_path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(rows) != len(order) or [row.get("claim_pair_id") for row in rows] != order:
        raise ValueError("cannot score a partial or unordered ledger")
    expected = {
        "evaluation_id": EVALUATION_ID, "provider_id": PROVIDER_ID, "model_id": MODEL_ID,
        "prompt_version": PROMPT_VERSION, "request_settings": REQUEST_SETTINGS,
        "challenge_fingerprint": manifest["challenge_fingerprint"],
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
    }
    for index, row in enumerate(rows):
        if row.get("order_index") != index or any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("mixed ledger or mismatched protocol")
    results = [
        ClaimSupportResult(
            verdict=row["verdict"], confidence=row["confidence"],
            supporting_spans=row["supporting_spans"], reason=row["reason"],
            source_integrity_pass=row["source_integrity_pass"],
        )
        for row in rows
    ]
    metrics = classification_metrics(
        [by_id[row["claim_pair_id"]]["construction_label"] for row in rows],
        [result.verdict for result in results],
    )
    metrics["supported_precision"] = metrics["per_class"]["SUPPORTED"]["precision"]
    metrics["span_integrity_failure_rate"] = span_integrity_failure_rate(results)
    verdict, conditions = usefulness_gate({
        "macro_f1": metrics["macro_f1"],
        "supported_precision": metrics["supported_precision"],
        "unsafe_acceptance": metrics["unsafe_citation_acceptance_rate"],
        "span_integrity_failure": metrics["span_integrity_failure_rate"],
    })
    calls = []
    if calls_path is not None and calls_path.exists():
        calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    output = {
        **expected,
        "temperature_requested": REQUEST_SETTINGS["temperature"],
        "temperature_note": TEMPERATURE_NOTE,
        "ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "claim_pairs": len(rows), "verdict": verdict, "conditions": conditions, "metrics": metrics,
        "supported_precision": metrics["supported_precision"], "macro_f1": metrics["macro_f1"],
        "calls_total": len(calls),
        "system_fingerprints": sorted({row["system_fingerprint"] for row in rows if row.get("system_fingerprint")}),
        "label": "Phase 14C (second provider); not a Phase 14B / Gemini result",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_DIR / "dispositions.jsonl")
    parser.add_argument("--out", type=Path, default=DEFAULT_DIR / "score.json")
    parser.add_argument("--calls", type=Path, default=DEFAULT_DIR / "calls.jsonl")
    args = parser.parse_args()
    result = score(args.ledger, args.out, args.calls)
    print(result["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
