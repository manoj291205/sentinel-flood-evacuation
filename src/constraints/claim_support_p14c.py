"""Second-provider claim-support verification for the pre-registered 14C protocol."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable, Mapping

import httpx

from src.constraints.claim_support import (
    ClaimSupportResult,
    EvidenceChunk,
    build_verifier_payload,
    finalize_semantic_result,
)
from src.constraints.claim_support_gemini import build_prompt as _build_14b_prompt

EVALUATION_ID = "v3-claim-support-eval-14c-v1"
PROVIDER_ID = "groq-claim-support-v1"
MODEL_ID = "openai/gpt-oss-120b"
PROMPT_VERSION = "14b-prompt-v1"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
TEMPERATURE_NOTE = "provider converts 0 to 1e-8"
REQUEST_SETTINGS = {
    "temperature": 0.0,
    "seed": 14,
    "reasoning_effort": "low",
    "include_reasoning": False,
    "max_completion_tokens": 2048,
}
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]},
        "confidence": {"type": "number"},
        "supporting_spans": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "confidence", "supporting_spans", "reason"],
}


def build_prompt(payload: dict) -> str:
    return _build_14b_prompt(payload)


def build_request(prompt: str) -> dict:
    return {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "claim_support_verdict", "strict": True, "schema": RESPONSE_SCHEMA},
        },
        **REQUEST_SETTINGS,
    }


@dataclass(frozen=True)
class ProviderResponse:
    status: int
    body: dict
    headers: Mapping[str, str]


Transport = Callable[[dict], ProviderResponse]


class ProviderStop(Exception):
    """Safe, structured stop reason without request or response text."""

    def __init__(self, reason: str, status: int | None = None, retry_after: float | None = None,
                 exception_class: str | None = None) -> None:
        self.reason = reason
        self.status = status
        self.retry_after = retry_after
        self.exception_class = exception_class
        super().__init__(reason, status, retry_after, exception_class)


@dataclass(frozen=True)
class P14cOutcome:
    result: ClaimSupportResult
    response_model: str | None
    system_fingerprint: str | None
    finish_reason: str | None
    usage: Mapping[str, int]
    attempts: int


def http_transport(body: dict, *, client: httpx.Client | None = None,
                   timeout: float = 60.0) -> ProviderResponse:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    own_client = client is None
    active = client if client is not None else httpx.Client(timeout=timeout)
    try:
        try:
            response = active.post(
                API_URL,
                json=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=timeout,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderStop("NETWORK_ERROR", exception_class=type(exc).__name__) from None
        try:
            parsed = response.json()
        except ValueError:
            parsed = {}
        return ProviderResponse(
            status=response.status_code,
            body=parsed if isinstance(parsed, dict) else {},
            headers={name.lower(): value for name, value in response.headers.items()},
        )
    finally:
        if own_client:
            active.close()


def _retry_after(headers: Mapping[str, str]) -> float | None:
    try:
        value = float(headers.get("retry-after", ""))
        return value if value >= 0 else None
    except (TypeError, ValueError):
        return None


def _usage(body: dict) -> dict[str, int]:
    raw = body.get("usage", {})
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if isinstance(value, int) and not isinstance(value, bool)}


def _parse_result(response: ProviderResponse, evidence: EvidenceChunk) -> ClaimSupportResult:
    choice = response.body["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("truncated output")
    content = choice["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or set(parsed) != set(RESPONSE_SCHEMA["required"]):
        raise ValueError("response fields do not match schema")
    if not isinstance(parsed["supporting_spans"], list) or not all(
        isinstance(span, str) for span in parsed["supporting_spans"]
    ):
        raise ValueError("supporting_spans must be strings")
    if not isinstance(parsed["reason"], str):
        raise ValueError("reason must be a string")
    return finalize_semantic_result(evidence=evidence, **parsed)


def verify_claim_support_p14c(
    claim: str,
    evidence: EvidenceChunk,
    *,
    transport: Transport,
    sleep: Callable[[float], None] = time.sleep,
) -> P14cOutcome:
    request = build_request(build_prompt(build_verifier_payload(claim, evidence)))
    attempts = 0
    parse_failures = 0
    rate_waits = 0
    while True:
        response = transport(request)
        attempts += 1
        status = response.status
        if status == 429:
            delay = _retry_after(response.headers)
            if delay is not None and delay <= 60 and rate_waits < 2:
                rate_waits += 1
                sleep(delay)
                continue
            raise ProviderStop("RATE_LIMITED", status, delay)
        if status in (500, 502, 503, 504):
            raise ProviderStop("PROVIDER_UNAVAILABLE", status)
        if status in (401, 403):
            raise ProviderStop("AUTH_ERROR", status)
        error = response.body.get("error", {})
        code = error.get("code") if isinstance(error, dict) else None
        if status == 400 and code == "json_validate_failed":
            parse_failures += 1
        elif status >= 400:
            raise ProviderStop("REQUEST_REJECTED", status)
        else:
            try:
                result = _parse_result(response, evidence)
                choice = response.body["choices"][0]
                return P14cOutcome(
                    result=result,
                    response_model=response.body.get("model"),
                    system_fingerprint=response.body.get("system_fingerprint"),
                    finish_reason=choice.get("finish_reason"),
                    usage=_usage(response.body),
                    attempts=attempts,
                )
            except (ValueError, TypeError, KeyError, IndexError):
                parse_failures += 1
        if parse_failures >= 2:
            return P14cOutcome(
                result=ClaimSupportResult(
                    verdict="UNSUPPORTED", confidence=0.0, supporting_spans=[],
                    reason="PROVIDER_PARSE_FAILURE", source_integrity_pass=False,
                ),
                response_model=response.body.get("model"),
                system_fingerprint=response.body.get("system_fingerprint"),
                finish_reason=None,
                usage=_usage(response.body),
                attempts=attempts,
            )
