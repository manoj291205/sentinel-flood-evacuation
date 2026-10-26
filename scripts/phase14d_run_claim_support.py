#!/usr/bin/env python3
"""Run the registered Phase 14D practice or test challenge."""

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
from src.constraints.claim_support_p14d import (  # noqa: E402
    EVALUATION_ID,
    MODEL_ID,
    PROVIDER_ID,
    REQUEST_SETTINGS,
    RESPONSE_SCHEMA,
    TEMPERATURE_NOTE,
    PROMPT_DIR,
    ProviderResponse,
    ProviderStop,
    Transport,
    http_transport,
    load_prompt,
    prompt_sha256,
    verify_claim_support_p14d,
)
from src.rag.ingest import prepare_corpus  # noqa: E402
from src.constraints.provider_journal import ProviderJournal  # noqa: E402

CHALLENGE_DIR = ROOT / "data/eval_v4/phase14d"
MANIFEST = CHALLENGE_DIR / "manifest.json"
PROTOCOL = ROOT / "specs/V4_CLAIM_SUPPORT_14D_SPEC.md"
DEFAULT_OUT_DIR = ROOT / "data/eval_results/phase14d"
FREEZE = ROOT / "specs/approvals/p14d_prompt_freeze.json"
OLD_DIRS = (ROOT / "data/eval_results/phase14b", ROOT / "data/eval_results/phase14c")
EXPECTED_COMPLETION_TOKENS = 1500
RATE_HEADERS = (
    "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests",
    "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens",
)


@dataclass(frozen=True)
class Budget:
    requests_per_minute: int = 20
    tokens_per_minute: int = 7000
    requests_per_day: int = 800
    tokens_per_day: int = 185_000


class _BudgetStop(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _challenge(challenge_set: str) -> tuple[list[dict], dict]:
    pairs = json.loads((CHALLENGE_DIR / f"challenge_{challenge_set}.json").read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fields = manifest["canonical_fields_in_order"]
    lines = [
        json.dumps([pair[field] for field in fields], ensure_ascii=False, separators=(",", ":"))
        for pair in sorted(pairs, key=lambda pair: pair["claim_pair_id"])
    ]
    fingerprint = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    selected = manifest["sets"][challenge_set]
    if fingerprint != selected["challenge_fingerprint"] or len(pairs) != selected["claim_pairs"]:
        raise ValueError("claim-support challenge fingerprint or size mismatch")
    return pairs, selected


@functools.lru_cache(maxsize=1)
def _prepared_corpus():
    return prepare_corpus()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _forbid_old_results(path: Path) -> None:
    resolved = path.resolve()
    if any(resolved == old.resolve() or resolved.is_relative_to(old.resolve()) for old in OLD_DIRS):
        raise ValueError("Phase 14D output must not use an earlier evaluation path")


def _validate_ledger(rows: list[dict], order: list[str], fingerprint: str, protocol_hash: str,
                     challenge_set: str, prompt_version: str, prompt_hash: str) -> None:
    if [row.get("claim_pair_id") for row in rows] != order[:len(rows)]:
        raise ValueError("ledger is not an ordered prefix of the challenge")
    expected = {
        "evaluation_id": EVALUATION_ID, "provider_id": PROVIDER_ID, "model_id": MODEL_ID,
        "prompt_version": prompt_version, "prompt_sha256": prompt_hash,
        "request_settings": REQUEST_SETTINGS,
        "challenge_id": "v4-claim-support-challenge-14d-v1", "challenge_set": challenge_set,
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
    challenge_set: str,
    out_dir: Path,
    max_requests: int,
    prompt_version: str,
    freeze_path: Path | None = None,
    budget_root: Path | None = None,
    budget: Budget = Budget(),
    zdr_attested: bool,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    if not zdr_attested:
        raise ValueError("ZDR attestation is required")
    if max_requests < 0:
        raise ValueError("max_requests must be non-negative")
    if challenge_set not in ("test", "practice"):
        raise ValueError("unknown challenge set")
    _forbid_old_results(out_dir)
    prompt_hash = prompt_sha256(prompt_version)
    if challenge_set == "test":
        if freeze_path is None or not freeze_path.is_file():
            raise ValueError("a prompt freeze record is required")
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        if (freeze.get("evaluation_id") != EVALUATION_ID or
                freeze.get("prompt_version") != prompt_version or
                freeze.get("prompt_sha256") != prompt_hash):
            raise ValueError("prompt freeze record does not match")
    pairs, manifest = _challenge(challenge_set)
    by_id = {pair["claim_pair_id"]: pair for pair in pairs}
    order = label_independent_order(list(by_id), manifest["challenge_fingerprint"])
    protocol_hash = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    ledger_path, calls_path = out_dir / "dispositions.jsonl", out_dir / "calls.jsonl"
    rows = _read_jsonl(ledger_path)
    calls = _read_jsonl(calls_path)
    _validate_ledger(rows, order, manifest["challenge_fingerprint"], protocol_hash,
                     challenge_set, prompt_version, prompt_hash)
    if len(rows) == len(order):
        return {"done": len(rows), "total": len(order), "requests_made": 0,
                "tokens_counted": 0, "stopped_reason": "COMPLETE"}
    if max_requests == 0:
        return {"done": len(rows), "total": len(order), "requests_made": 0,
                "tokens_counted": 0, "stopped_reason": "MAX_REQUESTS"}

    prepared = _prepared_corpus()
    out_dir.mkdir(parents=True, exist_ok=True)
    budget_root = budget_root or out_dir
    all_calls = []
    for path in budget_root.rglob("calls.jsonl"):
        all_calls.extend(_read_jsonl(path))
    if not (budget_root / "calls.jsonl").exists() and out_dir == budget_root:
        all_calls = calls.copy()
    requests_made = 0
    tokens_in_run = 0
    stop_reason = "COMPLETE"
    header_stop = False
    identity = {"evaluation_id": EVALUATION_ID, "model_id": MODEL_ID, "protocol_sha256": protocol_hash,
                "challenge_fingerprint": manifest["challenge_fingerprint"], "challenge_set": challenge_set,
                "prompt_sha256": prompt_hash, "request_settings": REQUEST_SETTINGS,
                "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "provider_source_sha256": hashlib.sha256((ROOT / "src/constraints/claim_support_p14d.py").read_bytes()).hexdigest(),
                "response_schema_sha256": hashlib.sha256(json.dumps(RESPONSE_SCHEMA, sort_keys=True).encode("utf-8")).hexdigest(),
                "python_version": sys.version.split()[0], "httpx_version": httpx.__version__}
    with ProviderJournal(out_dir / "attempt_journal.json", identity, rows, request_budget=max_requests,
                         lock_path=budget_root / ".provider-budget.lock") as attempts, \
            ledger_path.open("a", encoding="utf-8") as ledger, calls_path.open("a", encoding="utf-8") as call_log:
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
                estimate = math.ceil(len(prompt.encode("utf-8")) / 3) + EXPECTED_COMPLETION_TOKENS
                while True:
                    now = clock()
                    today = _utc(now)[:10]
                    daily = [call for call in all_calls if call["utc"][:10] == today]
                    if len(daily) >= budget.requests_per_day:
                        raise _BudgetStop("DAILY_REQUEST_BUDGET")
                    if sum(call["tokens_counted"] for call in daily) + estimate > budget.tokens_per_day:
                        raise _BudgetStop("DAILY_TOKEN_BUDGET")
                    recent = [call for call in all_calls if now - 60 < datetime.fromisoformat(call["utc"]).timestamp() <= now]
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
                attempt = attempts.begin(pair_id, body)
                try:
                    response = transport(body)
                    return response
                except ProviderStop as exc:
                    failure = exc
                    raise
                finally:
                    attempts.resolve(attempt, response, failure)
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
                    all_calls.append(record)

            try:
                outcome = verify_claim_support_p14d(
                    pair["claim"], evidence, prompt_version=prompt_version,
                    transport=counted, sleep=sleep,
                )
            except _BudgetStop as exc:
                stop_reason = exc.reason
                break
            except ProviderStop as exc:
                stop_reason = exc.reason
                break
            result = outcome.result
            row = {
                "evaluation_id": EVALUATION_ID, "provider_id": PROVIDER_ID,
                "model_id": MODEL_ID, "prompt_version": prompt_version,
                "prompt_sha256": prompt_hash,
                "temperature_requested": REQUEST_SETTINGS["temperature"],
                "temperature_note": TEMPERATURE_NOTE, "request_settings": REQUEST_SETTINGS,
                "challenge_id": "v4-claim-support-challenge-14d-v1",
                "challenge_set": challenge_set,
                "challenge_fingerprint": manifest["challenge_fingerprint"],
                "protocol_sha256": protocol_hash, "zdr_attested": True,
                "claim_pair_id": pair_id, "order_index": order_index,
                "verdict": result.verdict.value, "confidence": result.confidence,
                "supporting_sentence_ids": list(outcome.supporting_sentence_ids),
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
            os.fsync(ledger.fileno())
            attempts.commit(row)
            rows.append(row)
            if header_stop:
                stop_reason = "DAILY_REQUEST_BUDGET"
                break
    if len(rows) == len(order):
        stop_reason = "COMPLETE"
    return {"done": len(rows), "total": len(order), "requests_made": requests_made,
            "tokens_counted": tokens_in_run, "stopped_reason": stop_reason}


def _tracked_and_clean(paths: list[Path]) -> bool:
    for path in paths:
        relative = str(path.relative_to(ROOT))
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", relative],
                                 cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative],
                               cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if tracked.returncode or clean.returncode:
            return False
    return True


def _protocol_committed(prompt_version: str, challenge_set: str, *, test: bool = False) -> bool:
    files = [PROTOCOL, MANIFEST, CHALLENGE_DIR / f"challenge_{challenge_set}.json",
             PROMPT_DIR / f"{prompt_version}.txt"]
    if test:
        files.append(FREEZE)
    return _tracked_and_clean(files)


def _fake_transport(body: dict) -> ProviderResponse:
    del body
    verdict = {"verdict": "UNSUPPORTED", "confidence": 0.0,
               "supporting_sentence_ids": [], "reason": "Fake transport"}
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
    parser.add_argument("--set", dest="challenge_set", choices=("practice", "test"))
    parser.add_argument("--round", type=int, choices=(1, 2))
    parser.add_argument("--prompt")
    args = parser.parse_args()
    if args.check_env:
        calls = [call for path in DEFAULT_OUT_DIR.rglob("calls.jsonl") for call in _read_jsonl(path)]
        day = _utc(time.time())[:10]
        today = [call for call in calls if call["utc"][:10] == day]
        print(f"key {'present' if os.environ.get('GROQ_API_KEY') else 'missing'}")
        print(f"Python {sys.version_info.major}.{sys.version_info.minor}; httpx {httpx.__version__}")
        print(f"protocol committed {'yes' if _tracked_and_clean([PROTOCOL, MANIFEST]) else 'no'}")
        print(f"calls today {len(today)}; tokens today {sum(c['tokens_counted'] for c in today)}")
        return 0
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="phase14d-fake-") as directory:
            result = run(transport=_fake_transport, challenge_set="practice", out_dir=Path(directory),
                         prompt_version="14d-prompt-r0", max_requests=min(args.max_requests, 2),
                         zdr_attested=True)
    else:
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is not set")
        if args.preflight:
            if not _tracked_and_clean([PROTOCOL, MANIFEST]):
                raise RuntimeError("Phase 14D protocol must be committed and unmodified")
            _preflight()
            print("preflight complete")
            return 0
        if not args.attest_zdr:
            raise RuntimeError("ZDR attestation is required")
        if args.challenge_set == "practice":
            if args.round is None or args.prompt != f"14d-prompt-r{args.round - 1}":
                raise ValueError("practice requires the matching round and prompt")
            prompt_version = args.prompt
            out_dir = DEFAULT_OUT_DIR / "practice" / f"round{args.round}"
            if args.round == 2 and len(_read_jsonl(DEFAULT_OUT_DIR / "practice/round1/dispositions.jsonl")) != 30:
                raise ValueError("practice round 1 is not complete")
            freeze_path = None
        elif args.challenge_set == "test":
            if args.round is not None or args.prompt is not None or not FREEZE.is_file():
                raise ValueError("test requires the frozen prompt")
            freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
            prompt_version = freeze["prompt_version"]
            out_dir = DEFAULT_OUT_DIR / "test"
            freeze_path = FREEZE
        else:
            raise ValueError("--live requires --set practice or test")
        if not _protocol_committed(prompt_version, args.challenge_set, test=args.challenge_set == "test"):
            raise RuntimeError("Phase 14D inputs must be committed and unmodified")
        result = run(transport=http_transport, challenge_set=args.challenge_set, out_dir=out_dir,
                     max_requests=args.max_requests, prompt_version=prompt_version,
                     freeze_path=freeze_path, budget_root=DEFAULT_OUT_DIR, zdr_attested=True)
    print(f"{result['done']}/{result['total']} done; {result['stopped_reason']}; "
          f"calls {result['requests_made']}; tokens {result['tokens_counted']}")
    if result["stopped_reason"] != "COMPLETE":
        if args.dry_run:
            print("Dry run can be repeated")
        elif args.challenge_set == "practice":
            print(f"Rerun: python scripts/phase14d_run_claim_support.py --live --attest-zdr --set practice --round {args.round} --prompt {prompt_version} --max-requests 120")
        else:
            print("Rerun: python scripts/phase14d_run_claim_support.py --live --attest-zdr --set test --max-requests 120")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
