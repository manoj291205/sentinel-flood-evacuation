"""Structured Gemini provider for the frozen claim-support protocol."""

from __future__ import annotations

import json
import os
from typing import Callable

from src.constraints.claim_support import (
    ClaimSupportResult,
    EvidenceChunk,
    build_verifier_payload,
    finalize_semantic_result,
)
from src.constraints.generate import MODEL

PROVIDER_ID = "gemini-claim-support-v1"
PROMPT_VERSION = "14b-prompt-v1"
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]},
        "confidence": {"type": "number"},
        "supporting_spans": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "confidence", "supporting_spans", "reason"],
}

_INSTRUCTIONS = """Judge only whether the evidence supports the exact claim.
SUPPORTED: every material proposition is established. Paraphrasing is allowed, but do not strengthen modality, certainty, scope, actor responsibility, timing, numerical quantity, or conditions.
PARTIALLY_SUPPORTED: a meaningful component is established, but at least one material component is not, including an added actor, deadline, number, or population, or a recommendation turned into a mandate.
UNSUPPORTED: the evidence does not materially establish the core factual claim. Same-topic wrong facts, wrong actors/actions/conditions/populations, reversed advice, unsupported quantities, and contradictions belong here.
Copy supporting spans verbatim from the evidence. Give a short reason. Do not include chain-of-thought. Return only the structured JSON object.
"""


def build_prompt(payload: dict) -> str:
    return _INSTRUCTIONS + json.dumps(payload, ensure_ascii=False)


def _call_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.0,
        ),
    )
    return response.text


def verify_claim_support_gemini(
    claim: str,
    evidence: EvidenceChunk,
    *,
    client: Callable[[str], str] | None = None,
) -> ClaimSupportResult:
    prompt = build_prompt(build_verifier_payload(claim, evidence))
    invoke = client or _call_gemini
    for _ in range(2):
        raw = invoke(prompt)
        try:
            response = json.loads(raw)
            if not isinstance(response, dict):
                raise ValueError("response must be an object")
            if set(response) != set(RESPONSE_SCHEMA["required"]):
                raise ValueError("response fields do not match schema")
            if not isinstance(response["supporting_spans"], list) or not all(
                isinstance(span, str) for span in response["supporting_spans"]
            ):
                raise ValueError("supporting_spans must be strings")
            if not isinstance(response["reason"], str):
                raise ValueError("reason must be a string")
            return finalize_semantic_result(evidence=evidence, **response)
        except (ValueError, TypeError, KeyError):
            continue
    return ClaimSupportResult(
        verdict="UNSUPPORTED",
        confidence=0.0,
        supporting_spans=[],
        reason="PROVIDER_PARSE_FAILURE",
        source_integrity_pass=False,
    )
