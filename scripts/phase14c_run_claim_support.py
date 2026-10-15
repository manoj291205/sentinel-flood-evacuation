#!/usr/bin/env python3
"""Run the separately registered Phase 14C claim-support challenge."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.constraints.claim_support import get_chunk_by_id, label_independent_order  # noqa: E402
from src.constraints.claim_support_p14c import (  # noqa: E402
    EVALUATION_ID,
    MODEL_ID,
    PROMPT_VERSION,
    PROVIDER_ID,
    REQUEST_SETTINGS,
    TEMPERATURE_NOTE,
    ProviderResponse,
    ProviderStop,
    Transport,
    http_transport,
    verify_claim_support_p14c,
)
from src.rag.ingest import prepare_corpus  # noqa: E402

CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
MANIFEST = ROOT / "data/eval_v3/phase14/claim_support_manifest.json"
PROTOCOL = ROOT / "specs/V4_CLAIM_SUPPORT_14C_SPEC.md"
DEFAULT_OUT_DIR = ROOT / "data/eval_results/phase14c"
PHASE14B_DIR = ROOT / "data/eval_results/phase14b"
RATE_HEADERS = (
    "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests",
    "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens",
)


@dataclass(frozen=True)
class Budget:
    requests_per_minute: int = 20
    tokens_per_minute: int = 6000
    requests_per_day: int = 800
    tokens_per_day: int = 150_000


class _BudgetStop(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


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


@functools.lru_cache(maxsize=1)
def _prepared_corpus():
    return prepare_corpus()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _forbid_14b(path: Path) -> None:
    resolved = path.resolve()
    if resolved == PHASE14B_DIR.resolve() or resolved.is_relative_to(PHASE14B_DIR.resolve()):
        raise ValueError("Phase 14C output must not use the phase14b path")


def _validate_ledger(rows: list[dict], order: list[str], fingerprint: str, protocol_hash: str) -> None:
    if [row.get("claim_pair_id") for row in rows] != order[:len(rows)]:
        raise ValueError("ledger is not an ordered prefix of the challenge")
    expected = {
        "evaluation_id": EVALUATION_ID, "provider_id": PROVIDER_ID, "model_id": MODEL_ID,
        "prompt_version": PROMPT_VERSION, "request_settings": REQUEST_SETTINGS,
        "challenge_fingerprint": fingerprint, "protocol_sha256": protocol_hash,
    }
    for index, row in enumerate(rows):
        if row.get("order_index") != index or any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("mixed ledger or mismatched protocol")


def _usage(body: dict) -> dict[str, int]:
    raw = body.get("usage", {})
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if isinstance(value, int) and not isinstance(value, bool)}


def _remaining_exhausted(headers: dict[str, str]) -> bool:
    try:
        return int(headers.get("x-ratelimit-remaining-requests", "999999")) <= 1
    except ValueError:
        return False


def run(
    *,
    transport: Transport,
    out_dir: Path,
    max_requests: int,
    budget: Budget = Budget(),
    zdr_attested: bool,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    if not zdr_attested:
        raise ValueError("ZDR attestation is required")
    if max_requests < 0:
        raise ValueError("max_requests must be non-negative")
    _forbid_14b(out_dir)
    pairs, manifest = _challenge()
    by_id = {pair["claim_pair_id"]: pair for pair in pairs}
    order = label_independent_order(list(by_id), manifest["challenge_fingerprint"])
    protocol_hash = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    ledger_path, calls_path = out_dir / "dispositions.jsonl", out_dir / "calls.jsonl"
    rows = _read_jsonl(ledger_path)
    calls = _read_jsonl(calls_path)
    _validate_ledger(rows, order, manifest["challenge_fingerprint"], protocol_hash)
    if len(rows) == len(order):
        return {"done": len(rows), "total": len(order), "requests_made": 0,
                "tokens_counted": 0, "stopped_reason": "COMPLETE"}
    if max_requests == 0:
        return {"done": len(rows), "total": len(order), "requests_made": 0,
                "tokens_counted": 0, "stopped_reason": "MAX_REQUESTS"}

    prepared = _prepared_corpus()
    out_dir.mkdir(parents=True, exist_ok=True)
    requests_made = 0
    tokens_in_run = 0
    stop_reason = "COMPLETE"
    header_stop = False
    with ledger_path.open("a", encoding="utf-8") as ledger, calls_path.open("a", encoding="utf-8") as call_log:
        for order_index in range(len(rows), len(order)):
            if requests_made >= max_requests:
                stop_reason = "MAX_REQUESTS"
                break
            pair_id = order[order_index]
            pair = by_id[pair_id]
            evidence = get_chunk_by_id(
                pair["chunk_id"], prepared,
                source_id=pair["source_id"], filename=pair["filename"],
                page=pair["page"], passage_sha256=pair["passage_sha256"],
            )
            started = time.monotonic()
            request_utc = _utc(clock())
            pair_attempt = 0

            def counted(body: dict) -> ProviderResponse:
                nonlocal requests_made, tokens_in_run, header_stop, pair_attempt
                if requests_made >= max_requests:
                    raise _BudgetStop("MAX_REQUESTS")
                prompt = body["messages"][0]["content"]
                estimate = math.ceil(len(prompt.encode("utf-8")) / 3) + REQUEST_SETTINGS["max_completion_tokens"]
                while True:
                    now = clock()
                    today = _utc(now)[:10]
                    daily = [call for call in calls if call["utc"][:10] == today]
                    if len(daily) >= budget.requests_per_day:
                        raise _BudgetStop("DAILY_REQUEST_BUDGET")
                    if sum(call["tokens_counted"] for call in daily) + estimate > budget.tokens_per_day:
                        raise _BudgetStop("DAILY_TOKEN_BUDGET")
                    recent = [call for call in calls if now - 60 < datetime.fromisoformat(call["utc"]).timestamp() <= now]
                    recent_tokens = sum(call["tokens_counted"] for call in recent)
                    token_wait = recent and recent_tokens + estimate > budget.tokens_per_minute
                    request_wait = len(recent) >= budget.requests_per_minute
                    if not request_wait and not token_wait:
                        break
                    oldest = min(datetime.fromisoformat(call["utc"]).timestamp() for call in recent)
                    sleep(max(0.001, oldest + 60 - now))

                pair_attempt += 1
                call_started = time.monotonic()
                response = None
                failure = None
                try:
                    response = transport(body)
                    return response
                except ProviderStop as exc:
                    failure = exc
                    raise
                finally:
                    requests_made += 1
                    usage = _usage(response.body) if response is not None else {}
                    counted_tokens = usage.get("total_tokens", estimate)
                    tokens_in_run += counted_tokens
                    headers = {name.lower(): value for name, value in response.headers.items()} if response else {}
                    header_stop = header_stop or _remaining_exhausted(headers)
                    record = {
                        "call_index": len(calls), "utc": _utc(now), "kind": "inference",
                        "claim_pair_id": pair_id, "attempt": pair_attempt,
                        "http_status": response.status if response else failure.status if failure else None,
                        "outcome": "RESPONSE" if response else failure.reason if failure else "NETWORK_ERROR",
                        "retry_after": headers.get("retry-after"), "usage": usage,
                        "tokens_counted": counted_tokens,
                        "latency_ms": round((time.monotonic() - call_started) * 1000),
                        "ratelimit": {name: headers[name] for name in RATE_HEADERS if name in headers},
                        "response_model": response.body.get("model") if response else None,
                        "system_fingerprint": response.body.get("system_fingerprint") if response else None,
                    }
                    call_log.write(json.dumps(record, ensure_ascii=False) + "\n")
                    call_log.flush()
                    calls.append(record)

            try:
                outcome = verify_claim_support_p14c(pair["claim"], evidence, transport=counted, sleep=sleep)
            except _BudgetStop as exc:
                stop_reason = exc.reason
                break
            except ProviderStop as exc:
                stop_reason = exc.reason
                break
            result = outcome.result
            row = {
                "evaluation_id": EVALUATION_ID, "provider_id": PROVIDER_ID,
                "model_id": MODEL_ID, "prompt_version": PROMPT_VERSION,
                "temperature_requested": REQUEST_SETTINGS["temperature"],
                "temperature_note": TEMPERATURE_NOTE, "request_settings": REQUEST_SETTINGS,
                "challenge_fingerprint": manifest["challenge_fingerprint"],
                "protocol_sha256": protocol_hash, "zdr_attested": True,
                "claim_pair_id": pair_id, "order_index": order_index,
                "verdict": result.verdict.value, "confidence": result.confidence,
                "supporting_spans": result.supporting_spans, "reason": result.reason,
                "source_integrity_pass": result.source_integrity_pass,
                "response_model": outcome.response_model,
                "system_fingerprint": outcome.system_fingerprint,
                "finish_reason": outcome.finish_reason,
                "usage": dict(outcome.usage), "attempts": outcome.attempts,
                "request_utc": request_utc,
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
            ledger.write(json.dumps(row, ensure_ascii=False) + "\n")
            ledger.flush()
            rows.append(row)
            if header_stop:
                stop_reason = "DAILY_REQUEST_BUDGET"
                break
    if len(rows) == len(order):
        stop_reason = "COMPLETE"
    return {"done": len(rows), "total": len(order), "requests_made": requests_made,
            "tokens_counted": tokens_in_run, "stopped_reason": stop_reason}


def _protocol_committed() -> bool:
    relative = "specs/V4_CLAIM_SUPPORT_14C_SPEC.md"
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", relative],
                             cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return tracked.returncode == 0 and clean.returncode == 0


def _fake_transport(body: dict) -> ProviderResponse:
    del body
    verdict = {"verdict": "UNSUPPORTED", "confidence": 0.0, "supporting_spans": [], "reason": "Fake transport"}
    return ProviderResponse(200, {"model": MODEL_ID, "choices": [{"message": {"content": json.dumps(verdict)},
                            "finish_reason": "stop"}], "usage": {"total_tokens": 100}}, {})


def _preflight() -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    url = f"https://api.groq.com/openai/v1/models/{MODEL_ID}"
    started = time.monotonic()
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderStop("NETWORK_ERROR", exception_class=type(exc).__name__) from None
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    calls_path = DEFAULT_OUT_DIR / "calls.jsonl"
    prior = _read_jsonl(calls_path)
    headers = {name.lower(): value for name, value in response.headers.items()}
    record = {
        "call_index": len(prior), "utc": _utc(time.time()), "kind": "preflight",
        "claim_pair_id": None, "attempt": 1, "http_status": response.status_code,
        "outcome": "RESPONSE", "retry_after": headers.get("retry-after"),
        "usage": {}, "tokens_counted": 0,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "ratelimit": {name: headers[name] for name in RATE_HEADERS if name in headers},
        "response_model": None, "system_fingerprint": None,
    }
    with calls_path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record) + "\n")
    if response.status_code >= 400:
        reason = "AUTH_ERROR" if response.status_code in (401, 403) else "REQUEST_REJECTED"
        raise ProviderStop(reason, response.status_code)


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-env", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument("--attest-zdr", action="store_true")
    parser.add_argument("--max-requests", type=int, default=120)
    args = parser.parse_args()
    if args.check_env:
        calls = _read_jsonl(DEFAULT_OUT_DIR / "calls.jsonl")
        day = _utc(time.time())[:10]
        today = [call for call in calls if call["utc"][:10] == day]
        done = len(_read_jsonl(DEFAULT_OUT_DIR / "dispositions.jsonl"))
        print(f"key {'present' if os.environ.get('GROQ_API_KEY') else 'missing'}")
        print(f"Python {sys.version_info.major}.{sys.version_info.minor}; httpx {httpx.__version__}")
        print(f"protocol committed {'yes' if _protocol_committed() else 'no'}")
        print(f"ledger {done}/135; calls today {len(today)}; tokens today {sum(c['tokens_counted'] for c in today)}")
        return 0
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="phase14c-fake-") as directory:
            result = run(transport=_fake_transport, out_dir=Path(directory),
                         max_requests=min(args.max_requests, 2), zdr_attested=True)
    else:
        if not _protocol_committed():
            raise RuntimeError("Phase 14C protocol must be committed and unmodified")
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is not set")
        if args.preflight:
            _preflight()
            print("preflight complete")
            return 0
        if not args.attest_zdr:
            raise RuntimeError("ZDR attestation is required")
        result = run(transport=http_transport, out_dir=DEFAULT_OUT_DIR,
                     max_requests=args.max_requests, zdr_attested=True)
    print(f"{result['done']}/{result['total']} done; {result['stopped_reason']}; "
          f"calls {result['requests_made']}; tokens {result['tokens_counted']}")
    if result["stopped_reason"] != "COMPLETE":
        print("Rerun: python scripts/phase14c_run_claim_support.py --live --attest-zdr --max-requests 120")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
