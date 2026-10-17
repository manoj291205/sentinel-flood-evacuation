"""T2 wiring from the 14D approval record (P15T2; V4_CONSTRAINT_TIERS_SPEC Amendment 2026-10-17).

T2 is enabled only by ``specs/approvals/t2_semantic_verifier.json`` for the exact Phase 14D configuration.
The 14D provider module (Lane X) is imported read-only. Semantic calls run once per rule when rules are
loaded, never per dispatch decision, and only with an explicit ZDR attestation and a key in the environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.constraints import claim_support_p14d as p14d
from src.constraints.claim_support import ClaimSupportResult, EvidenceChunk
from src.constraints.claim_support_p14c import ProviderStop, Transport

from .ndma_rules import NdmaRule, load_rules
from .tiering import USEFUL, TieredRule, assign_tier

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVAL_PATH = REPO_ROOT / "specs" / "approvals" / "t2_semantic_verifier.json"
T2_PROMPT_VERSION = "14d-prompt-r0"
T2_VERDICT = "T2_VERIFIER_USEFUL"
RECORD_FIELDS = (
    "evaluation_id", "provider_id", "model_id", "prompt_version", "prompt_sha256", "request_settings",
    "score_path", "score_sha256", "verdict", "approved_by_user_utc", "approved_by_opus_utc",
)


@dataclass(frozen=True)
class T2Approval:
    enabled: bool
    reason: str
    record_sha256: str | None = None
    evaluation_id: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    prompt_sha256: str | None = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_t2_approval(path: str | Path = APPROVAL_PATH, *, root: str | Path = REPO_ROOT) -> T2Approval:
    """Verify the approval record; any failure disables T2 with the first failing reason (never raises)."""
    path, root = Path(path), Path(root).resolve()
    if not path.is_file():
        return T2Approval(False, "APPROVAL_MISSING")
    raw = path.read_bytes()
    record_sha = hashlib.sha256(raw).hexdigest()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return T2Approval(False, "APPROVAL_UNREADABLE", record_sha)
    if not isinstance(record, dict):
        return T2Approval(False, "APPROVAL_UNREADABLE", record_sha)

    def done(enabled: bool, reason: str) -> T2Approval:
        return T2Approval(enabled, reason, record_sha, *(
            record.get(k) if isinstance(record.get(k), str) else None
            for k in ("evaluation_id", "provider_id", "model_id", "prompt_version", "prompt_sha256")))

    if any(field not in record for field in RECORD_FIELDS):
        return done(False, "APPROVAL_FIELDS")
    if record["verdict"] != T2_VERDICT:
        return done(False, "VERDICT_NOT_T2_USEFUL")
    for field, expected, reason in (
        ("evaluation_id", p14d.EVALUATION_ID, "EVALUATION_MISMATCH"),
        ("provider_id", p14d.PROVIDER_ID, "PROVIDER_MISMATCH"),
        ("model_id", p14d.MODEL_ID, "MODEL_MISMATCH"),
        ("prompt_version", T2_PROMPT_VERSION, "PROMPT_VERSION_MISMATCH"),
    ):
        if record[field] != expected:
            return done(False, reason)
    try:
        prompt_hash = p14d.prompt_sha256(T2_PROMPT_VERSION)
    except ValueError:
        return done(False, "PROMPT_HASH_MISMATCH")
    if record["prompt_sha256"] != prompt_hash:
        return done(False, "PROMPT_HASH_MISMATCH")
    settings = record["request_settings"]
    if not isinstance(settings, dict) or set(settings) != set(p14d.REQUEST_SETTINGS) or any(
        type(settings[k]) is not type(v) or settings[k] != v for k, v in p14d.REQUEST_SETTINGS.items()
    ):
        return done(False, "SETTINGS_MISMATCH")
    score_rel = record["score_path"]
    if not isinstance(score_rel, str) or Path(score_rel).is_absolute():
        return done(False, "SCORE_PATH_INVALID")
    score = (root / score_rel).resolve()
    if not score.is_relative_to(root):
        return done(False, "SCORE_PATH_INVALID")
    if not score.is_file():
        return done(False, "SCORE_MISSING")
    if _sha256(score) != record["score_sha256"]:
        return done(False, "SCORE_HASH_MISMATCH")
    try:
        scored = json.loads(score.read_text(encoding="utf-8"))
    except ValueError:
        return done(False, "SCORE_VERDICT_MISMATCH")
    if scored.get("t2_verdict") != T2_VERDICT or scored.get("evaluation_id") != record["evaluation_id"]:
        return done(False, "SCORE_VERDICT_MISMATCH")
    return done(True, "ACCEPTED")


def _utc(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


class P14dSemantic:
    """The 14D semantic callable for ``assign_tier``; keeps call metadata only (no prompt, payload or text)."""

    def __init__(self, transport: Transport, *, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.time) -> None:
        self.transport, self.sleep, self.clock = transport, sleep, clock
        self.calls: list[dict[str, Any]] = []

    def __call__(self, claim: str, chunk: EvidenceChunk) -> ClaimSupportResult:
        started = self.clock()
        tick = time.monotonic()
        meta: dict[str, Any] = {"utc": _utc(started)}
        try:
            outcome = p14d.verify_claim_support_p14d(
                claim, chunk, prompt_version=T2_PROMPT_VERSION, transport=self.transport, sleep=self.sleep)
        except ProviderStop as stop:
            meta.update(latency_ms=round((time.monotonic() - tick) * 1000), outcome="PROVIDER_STOP",
                        stop_reason=stop.reason, http_status=stop.status)
            self.calls.append(meta)
            raise
        result = outcome.result
        parse_failure = outcome.finish_reason is None and result.reason == "PROVIDER_PARSE_FAILURE"
        meta.update(
            latency_ms=round((time.monotonic() - tick) * 1000),
            outcome="PARSE_FAILURE" if parse_failure else result.verdict.value,
            source_integrity_pass=bool(result.source_integrity_pass),
            confidence=float(result.confidence),
            supporting_sentence_ids=list(outcome.supporting_sentence_ids),
            attempts=outcome.attempts, response_model=outcome.response_model,
            system_fingerprint=outcome.system_fingerprint, finish_reason=outcome.finish_reason,
            usage=dict(outcome.usage), stop_reason=None, http_status=200,
        )
        self.calls.append(meta)
        return result


@dataclass(frozen=True)
class TierLoad:
    tiered: tuple[TieredRule, ...]
    approval: T2Approval
    t2_enabled: bool
    t2_reason: str
    records: tuple[dict, ...]


def load_tiered_rules(
    rules_path: str | Path,
    chunk_lookup: Callable[[NdmaRule], EvidenceChunk | None],
    *,
    approval_path: str | Path = APPROVAL_PATH,
    attest_zdr: bool = False,
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> TierLoad:
    """Load approved rules and tier them; T2 only from an accepted 14D record, with ZDR attested and a key."""
    env = os.environ if env is None else env
    rules = load_rules(rules_path)
    approval = load_t2_approval(approval_path)
    if not approval.enabled:
        t2_reason = approval.reason
    elif attest_zdr is not True:
        t2_reason = "ZDR_NOT_ATTESTED"
    elif not env.get("GROQ_API_KEY"):
        t2_reason = "API_KEY_MISSING"
    else:
        t2_reason = "ENABLED"
    enabled = t2_reason == "ENABLED"
    semantic = None
    if enabled:
        if transport is None:
            from src.constraints.claim_support_p14c import http_transport as transport
        semantic = P14dSemantic(transport, sleep=sleep, clock=clock)

    tiered, records = [], []
    for rule in rules:
        call_meta, status = None, "NOT_CALLED_T2_DISABLED"
        if semantic is None:
            result = assign_tier(rule, chunk_lookup)
        else:
            before = len(semantic.calls)
            try:
                result = assign_tier(rule, chunk_lookup, semantic=semantic, semantic_verdict=USEFUL)
                status = "CALLED" if len(semantic.calls) > before else "NOT_CALLED_T0"
            except ProviderStop:
                result = assign_tier(rule, chunk_lookup)  # stays T1 when provenance verifies; never T2
                status = "PROVIDER_STOP"
            if len(semantic.calls) > before:
                call_meta = semantic.calls[-1]
        tiered.append(result)
        records.append({
            "rule_id": rule.rule_id, "tier": result.tier.value, "reasons": list(result.reasons),
            "active_params": dict(result.active_params), "t2_enabled": enabled, "t2_reason": t2_reason,
            "approval_record_sha256": approval.record_sha256, "evaluation_id": approval.evaluation_id,
            "provider_id": approval.provider_id, "model_id": approval.model_id,
            "prompt_version": approval.prompt_version, "prompt_sha256": approval.prompt_sha256,
            "semantic_status": status, "semantic": call_meta,
        })
    return TierLoad(tuple(tiered), approval, enabled, t2_reason, tuple(records))
