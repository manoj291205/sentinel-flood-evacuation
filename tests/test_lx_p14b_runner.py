"""Lane X runner checks for Phase 14B: strict call cap and clean 503 stop. No network."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = ROOT / "scripts" / "phase14b_run_claim_support.py"
    spec = importlib.util.spec_from_file_location("phase14b_run_claim_support", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(ledger: Path) -> list[dict]:
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()] if ledger.exists() else []


def test_parse_retries_count_against_cap(tmp_path):
    calls = []

    def broken(prompt):
        calls.append(prompt)
        return "not json"

    ledger = tmp_path / "d.jsonl"
    result = _runner().run(max_requests=3, client=broken, ledger_path=ledger)
    # Pair 1 uses 2 calls; pair 2 gets 1 call, then the cap stops it and it is not written.
    assert len(calls) == 3 and result["requests_made"] == 3
    assert (result["done"], result["stopped_reason"]) == (1, "MAX_REQUESTS")
    assert len(_rows(ledger)) == 1


class _ServerError(Exception):
    code = 503


def test_503_stops_cleanly_and_resumes(tmp_path):
    runner = _runner()
    ledger = tmp_path / "d.jsonl"
    state = {"n": 0}

    def flaky(prompt):
        state["n"] += 1
        if state["n"] > 2:
            raise _ServerError("503 UNAVAILABLE")
        return json.dumps({"verdict": "UNSUPPORTED", "confidence": 0.0, "supporting_spans": [], "reason": "x"})

    first = runner.run(max_requests=20, client=flaky, ledger_path=ledger)
    assert (first["done"], first["stopped_reason"]) == (2, "PROVIDER_UNAVAILABLE")
    assert len(_rows(ledger)) == 2
    state["n"] = -1000
    second = runner.run(max_requests=3, client=flaky, ledger_path=ledger)
    assert (second["done"], second["stopped_reason"]) == (5, "MAX_REQUESTS")


class _ClientError(Exception):
    code = 400


def test_non_transient_error_with_503_in_text_still_raises(tmp_path):
    import pytest

    def bad(prompt):
        raise _ClientError("400 INVALID_ARGUMENT request id 1503 UNAVAILABLE")

    with pytest.raises(_ClientError):
        _runner().run(max_requests=5, client=bad, ledger_path=tmp_path / "d.jsonl")


@pytest.mark.parametrize('status,message,limited,unavailable', [
    (400, '400 bad request, id 429 and 503 UNAVAILABLE', False, False),
    (401, 'RESOURCE_EXHAUSTED', False, False),
    (429, '503 UNAVAILABLE', True, False),
    (500, '429 in request identifier', False, True),
    (501, 'server error', False, True),
    (503, '429 in request identifier', False, True),
    (599, 'server error', False, True),
    (None, '429 RESOURCE_EXHAUSTED', True, False),
    (None, '503 UNAVAILABLE', False, True),
    (None, 'request identifier 1503 UNAVAILABLE', False, False),
])
def test_integer_status_precedes_text_fallback(status, message, limited, unavailable):
    error = RuntimeError(message)
    if status is not None:
        error.status_code = status
    runner = _runner()
    assert runner._rate_limited(error) is limited
    assert runner._unavailable(error) is unavailable
