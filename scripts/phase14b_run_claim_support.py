#!/usr/bin/env python3
"""Run the frozen claim-support challenge with a resumable disposition ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.constraints.claim_support import get_chunk_by_id, label_independent_order  # noqa: E402
from src.constraints.claim_support_gemini import (  # noqa: E402
    MODEL,
    PROMPT_VERSION,
    PROVIDER_ID,
    RESPONSE_SCHEMA,
    _call_gemini,
    verify_claim_support_gemini,
)
from src.rag.ingest import prepare_corpus  # noqa: E402
from src.constraints.provider_journal import ProviderJournal  # noqa: E402

CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
MANIFEST = ROOT / "data/eval_v3/phase14/claim_support_manifest.json"
DEFAULT_LEDGER = ROOT / "data/eval_results/phase14b/dispositions.jsonl"


def _challenge() -> tuple[list[dict], dict]:
    pairs = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fields = manifest["fingerprint_procedure"]["canonical_fields_in_order"]
    lines = [
        json.dumps([pair[field] for field in fields], ensure_ascii=False, separators=(",", ":"))
        for pair in sorted(pairs, key=lambda pair: pair["claim_pair_id"])
    ]
    fingerprint = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    if fingerprint != manifest["challenge_fingerprint"] or len(pairs) != manifest["claim_pairs"]:
        raise ValueError("claim-support challenge fingerprint or size mismatch")
    return pairs, manifest


def _rate_limited(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code == 429 or "429" in str(exc)


class _RequestBudgetStop(Exception):
    pass


def run(*, max_requests: int, client: Callable[[str], str], ledger_path: Path) -> dict:
    if max_requests < 0:
        raise ValueError("max_requests must be non-negative")
    pairs, manifest = _challenge()
    by_id = {pair["claim_pair_id"]: pair for pair in pairs}
    order = label_independent_order(list(by_id), manifest["challenge_fingerprint"])
    existing = []
    if ledger_path.exists():
        existing = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    done_ids = [row["claim_pair_id"] for row in existing]
    if done_ids != order[: len(done_ids)]:
        raise ValueError("ledger is not an ordered prefix of this challenge")
    if len(done_ids) == len(order):
        return {"done": len(done_ids), "total": len(order), "requests_made": 0, "stopped_reason": "COMPLETE"}
    if max_requests == 0:
        return {"done": len(done_ids), "total": len(order), "requests_made": 0, "stopped_reason": "MAX_REQUESTS"}

    prepared = prepare_corpus()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    requests_made = 0
    reason = "COMPLETE"
    identity = {"provider_id": PROVIDER_ID, "prompt_version": PROMPT_VERSION, "model": MODEL,
                "challenge_fingerprint": manifest["challenge_fingerprint"], "temperature": 0.0,
                "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "provider_source_sha256": hashlib.sha256((ROOT / "src/constraints/claim_support_gemini.py").read_bytes()).hexdigest(),
                "response_schema_sha256": hashlib.sha256(json.dumps(RESPONSE_SCHEMA, sort_keys=True).encode("utf-8")).hexdigest(),
                "python_version": sys.version.split()[0]}
    with ProviderJournal(ledger_path.with_name(ledger_path.name + ".attempts.json"), identity, existing,
                         request_budget=max_requests) as attempts, \
            ledger_path.open("a", encoding="utf-8") as ledger:
        for order_index in range(len(done_ids), len(order)):
            if requests_made >= max_requests:
                reason = "MAX_REQUESTS"
                break
            pair_id = order[order_index]
            pair = by_id[pair_id]
            evidence = get_chunk_by_id(
                pair["chunk_id"], prepared,
                source_id=pair["source_id"], filename=pair["filename"],
                page=pair["page"], passage_sha256=pair["passage_sha256"],
            )
            started = time.monotonic()
            request_utc = datetime.now(timezone.utc).isoformat()
            def counted(prompt):
                nonlocal requests_made
                if requests_made >= max_requests:
                    raise _RequestBudgetStop
                attempt = attempts.begin(pair_id, {"prompt": prompt})
                requests_made += 1
                try:
                    raw = client(prompt)
                except BaseException as exc:
                    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                    attempts.resolve(attempt, None, SimpleNamespace(
                        status=code if isinstance(code, int) else None,
                        reason="HTTP_ERROR" if isinstance(code, int) else "NETWORK_ERROR"))
                    raise
                attempts.resolve(attempt, SimpleNamespace(status=200, body={"choices": [
                    {"message": {"content": raw}}]}), None)
                return raw
            try:
                result = verify_claim_support_gemini(pair["claim"], evidence, client=counted)
            except _RequestBudgetStop:
                reason = "MAX_REQUESTS"
                break
            except Exception as exc:
                if _rate_limited(exc):
                    reason = "RATE_LIMITED"
                    break
                raise
            row = {
                "claim_pair_id": pair_id,
                "order_index": order_index,
                "provider_id": PROVIDER_ID,
                "prompt_version": PROMPT_VERSION,
                "model": MODEL,
                "temperature": 0.0,
                "verdict": result.verdict.value,
                "confidence": result.confidence,
                "supporting_spans": result.supporting_spans,
                "reason": result.reason,
                "source_integrity_pass": result.source_integrity_pass,
                "request_utc": request_utc,
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
            ledger.write(json.dumps(row, ensure_ascii=False) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            attempts.commit(row)
            done_ids.append(pair_id)
    if len(done_ids) == len(order):
        reason = "COMPLETE"
    return {"done": len(done_ids), "total": len(order), "requests_made": requests_made, "stopped_reason": reason}


def _fake_client(prompt: str) -> str:
    del prompt
    return json.dumps({"verdict": "UNSUPPORTED", "confidence": 0.0, "supporting_spans": [], "reason": "Fake client"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-requests", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--client", choices=("gemini", "fake"), default="gemini")
    args = parser.parse_args()
    fake = args.client == "fake" or args.dry_run
    if fake:
        with tempfile.TemporaryDirectory(prefix="phase14b-fake-") as directory:
            result = run(max_requests=args.max_requests, client=_fake_client, ledger_path=Path(directory) / "dispositions.jsonl")
    else:
        print("Phase 14B is superseded; live execution is disabled. Use --dry-run or --client fake.")
        return 2
    print(f"{result['done']}/{result['total']} done; {result['stopped_reason']}")
    if result["stopped_reason"] != "COMPLETE":
        print("Rerun: python scripts/phase14b_run_claim_support.py --max-requests 20")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
