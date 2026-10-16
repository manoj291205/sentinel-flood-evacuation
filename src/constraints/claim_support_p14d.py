"""Sentence-citation claim support for the registered Phase 14D protocol."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from src.constraints.claim_support import (
    ClaimSupportResult,
    ClaimSupportVerdict,
    EvidenceChunk,
    build_verifier_payload,
    finalize_semantic_result,
)
from src.constraints.claim_support_p14c import (
    ProviderResponse,
    ProviderStop,
    Transport,
    http_transport,
)

EVALUATION_ID = "v4-claim-support-eval-14d-v1"
PROVIDER_ID = "groq-claim-support-14d-v1"
MODEL_ID = "openai/gpt-oss-120b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_SETTINGS = {
    "temperature": 0.0,
    "seed": 14,
    "reasoning_effort": "medium",
    "include_reasoning": False,
    "max_completion_tokens": 4096,
}
TEMPERATURE_NOTE = "provider converts 0 to 1e-8"
PROMPT_VERSIONS = ("14d-prompt-r0", "14d-prompt-r1")
PROMPT_DIR = Path(__file__).resolve().parent / "p14d_prompts"
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]},
        "confidence": {"type": "number"},
        "supporting_sentence_ids": {"type": "array", "items": {"type": "integer"}},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "confidence", "supporting_sentence_ids", "reason"],
}


def load_prompt(prompt_version: str) -> str:
    if prompt_version not in PROMPT_VERSIONS:
        raise ValueError("unknown Phase 14D prompt version")
    path = PROMPT_DIR / f"{prompt_version}.txt"
    if not path.is_file():
        raise ValueError("Phase 14D prompt file is missing")
    return path.read_text(encoding="utf-8")


def prompt_sha256(prompt_version: str) -> str:
    load_prompt(prompt_version)
    return hashlib.sha256((PROMPT_DIR / f"{prompt_version}.txt").read_bytes()).hexdigest()


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SPLIT.split(text) if part.strip()]


def build_payload(claim: str, evidence: EvidenceChunk) -> dict:
    base = build_verifier_payload(claim, evidence)
    return {
        "claim": base["claim"],
        "evidence_sentences": [
            {"id": index, "text": sentence}
            for index, sentence in enumerate(split_sentences(evidence.text), 1)
        ],
        "source_provenance": base["source_provenance"],
    }


def build_prompt(payload: dict, prompt_version: str) -> str:
    return load_prompt(prompt_version) + json.dumps(payload, ensure_ascii=False)


def build_request(prompt: str) -> dict:
    return {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "claim_support_verdict_14d", "strict": True, "schema": RESPONSE_SCHEMA},
        },
        **REQUEST_SETTINGS,
    }


@dataclass(frozen=True)
class P14dOutcome:
    result: ClaimSupportResult
    supporting_sentence_ids: tuple[int, ...]
    response_model: str | None
    system_fingerprint: str | None
    finish_reason: str | None
    usage: Mapping[str, int]
    attempts: int


@dataclass(frozen=True)
class _EmptyCitationResult(ClaimSupportResult):
    """Preserve a semantic verdict when a missing citation fails integrity."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdict", ClaimSupportVerdict(self.verdict))
        if not 0.0 <= self.confidence <= 1.0 or not self.reason.strip():
            raise ValueError("invalid result")


def _retry_after(headers: Mapping[str, str]) -> float | None:
    try:
        value = float(headers.get("retry-after", ""))
        return value if 0 <= value <= 60 else None
    except (TypeError, ValueError):
        return None


def _usage(body: dict) -> dict[str, int]:
    raw = body.get("usage", {})
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if type(value) is int}


def _parse_result(response: ProviderResponse, evidence: EvidenceChunk) -> tuple[ClaimSupportResult, tuple[int, ...]]:
    choice = response.body["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("truncated output")
    parsed = json.loads(choice["message"]["content"])
    if not isinstance(parsed, dict) or set(parsed) != set(RESPONSE_SCHEMA["required"]):
        raise ValueError("response fields do not match schema")
    if parsed["verdict"] not in RESPONSE_SCHEMA["properties"]["verdict"]["enum"]:
        raise ValueError("invalid verdict")
    confidence = parsed["confidence"]
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
        raise ValueError("invalid confidence")
    ids = parsed["supporting_sentence_ids"]
    sentences = split_sentences(evidence.text)
    if not isinstance(ids, list) or any(type(i) is not int or i < 1 or i > len(sentences) for i in ids):
        raise ValueError("invalid sentence IDs")
    if len(ids) != len(set(ids)) or not isinstance(parsed["reason"], str):
        raise ValueError("invalid sentence IDs or reason")
    spans = [sentences[index - 1] for index in ids]
    if parsed["verdict"] != "UNSUPPORTED" and not spans:
        result = _EmptyCitationResult(
            verdict=parsed["verdict"], confidence=confidence, supporting_spans=[],
            reason=parsed["reason"], source_integrity_pass=False,
        )
    else:
        result = finalize_semantic_result(
            evidence=evidence, verdict=parsed["verdict"], confidence=confidence,
            supporting_spans=spans, reason=parsed["reason"],
        )
    return result, tuple(ids)


def verify_claim_support_p14d(
    claim: str,
    evidence: EvidenceChunk,
    *,
    prompt_version: str,
    transport: Transport,
    sleep: Callable[[float], None] = time.sleep,
) -> P14dOutcome:
    request = build_request(build_prompt(build_payload(claim, evidence), prompt_version))
    attempts = 0
    parse_failures = 0
    rate_waits = 0
    while True:
        response = transport(request)
        attempts += 1
        status = response.status
        if status == 429:
            try:
                raw_delay = float(response.headers.get("retry-after", ""))
            except (TypeError, ValueError):
                raw_delay = None
            delay = _retry_after(response.headers)
            if delay is not None and rate_waits < 2:
                rate_waits += 1
                sleep(delay)
                continue
            raise ProviderStop("RATE_LIMITED", status, raw_delay)
        if status >= 500:
            raise ProviderStop("PROVIDER_UNAVAILABLE", status)
        if status in (401, 403):
            raise ProviderStop("AUTH_ERROR", status)
        error = response.body.get("error", {})
        code = error.get("code") if isinstance(error, dict) else None
        if status == 400 and code == "json_validate_failed":
            parse_failures += 1
        elif status != 200:
            raise ProviderStop("REQUEST_REJECTED", status)
        else:
            try:
                result, ids = _parse_result(response, evidence)
                choice = response.body["choices"][0]
                return P14dOutcome(
                    result=result, supporting_sentence_ids=ids,
                    response_model=response.body.get("model"),
                    system_fingerprint=response.body.get("system_fingerprint"),
                    finish_reason=choice.get("finish_reason"), usage=_usage(response.body),
                    attempts=attempts,
                )
            except (ValueError, TypeError, KeyError, IndexError):
                parse_failures += 1
        if parse_failures >= 2:
            return P14dOutcome(
                result=ClaimSupportResult(
                    verdict="UNSUPPORTED", confidence=0.0, supporting_spans=[],
                    reason="PROVIDER_PARSE_FAILURE", source_integrity_pass=False,
                ),
                supporting_sentence_ids=(), response_model=response.body.get("model"),
                system_fingerprint=response.body.get("system_fingerprint"),
                finish_reason=None, usage=_usage(response.body), attempts=attempts,
            )
