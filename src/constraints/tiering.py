"""Trust tiers for document rules and their arrival predicates (Phase 15')."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence

from src.sim.events import AuditEventType, AuditRecord

from .claim_support import ClaimSupportResult, EvidenceChunk, verify_evidence_integrity
from .ndma_rules import PREDICATES, NdmaRule

USEFUL = "CLAIM_SUPPORT_VERIFIER_USEFUL"


class Tier(str, Enum):
    T0 = "T0"  # provenance does not verify: strict fallback parameters
    T1 = "T1"  # chunk hash and verbatim span verify
    T2 = "T2"  # T1 and the semantic verifier (proven useful by 14B) agrees


@dataclass(frozen=True)
class TieredRule:
    rule: NdmaRule
    tier: Tier
    reasons: tuple[str, ...]
    active_params: Mapping[str, float]


def assign_tier(
    rule: NdmaRule,
    chunk_lookup: Callable[[NdmaRule], EvidenceChunk | None],
    *,
    semantic: Callable[[str, EvidenceChunk], ClaimSupportResult] | None = None,
    semantic_verdict: str | None = None,
) -> TieredRule:
    chunk = chunk_lookup(rule)
    reasons: list[str] = []
    if chunk is None:
        reasons.append("CHUNK_MISSING")
    else:
        if not verify_evidence_integrity(chunk) or chunk.passage_sha256 != rule.evidence["passage_sha256"]:
            reasons.append("CHUNK_HASH_MISMATCH")
        if rule.evidence["span"] not in chunk.text:
            reasons.append("SPAN_NOT_VERBATIM")
    if reasons:
        return TieredRule(rule, Tier.T0, tuple(reasons), dict(rule.strict_fallback))
    tier = Tier.T1
    if semantic_verdict == USEFUL and semantic is not None:
        result = semantic(rule.text, chunk)
        if result.verdict.value == "SUPPORTED" and result.source_integrity_pass:
            tier = Tier.T2
    return TieredRule(rule, tier, (), dict(rule.params))


@dataclass(frozen=True)
class ArrivalPredicate:
    """One document rule evaluated at a rollout's arrival; ``tier`` is recorded for the audit only."""

    rule_id: str
    tier: Tier
    predicate: str = ""
    limit: float = math.inf

    def __call__(self, c, f, arrival: int, arrival_minutes: float, path_hazards: Sequence[float], ledger) -> bool:
        """``arrival_minutes`` is the elapsed time from dispatch (boarding included) to arrival."""
        from src.certify.rollout import _at, _end

        if self.predicate == "MAX_TRAVEL_MINUTES":
            return arrival_minutes <= self.limit
        if self.predicate == "MAX_ROUTE_HAZARD":
            return max(path_hazards, default=0.0) <= self.limit
        s = c.shelter_id
        t = _at(f, arrival)
        if self.predicate == "MAX_DESTINATION_SEVERITY":
            return f.shelter_severity(s, t) <= self.limit
        if self.predicate == "MAX_OCCUPANCY_FRACTION":
            reserved = sum(p for (_, sh, p, _) in ledger.pending if sh == s)
            walk = sum(
                f.walk_ins(s, step)
                for step in range(ledger.timestep + 1, t + 1)
                if f.start_timestep < step <= _end(f)
            )
            total = (ledger.occupancy[s] + reserved + walk + c.people) / ledger.capacity_total[s]
            return total <= self.limit
        raise ValueError(f"unknown predicate {self.predicate!r}")


def predicates_for(tiered: Sequence[TieredRule]) -> tuple[ArrivalPredicate, ...]:
    return tuple(
        ArrivalPredicate(t.rule.rule_id, t.tier, t.rule.predicate,
                         float(t.active_params[PREDICATES[t.rule.predicate]]))
        for t in tiered
    )


def tier_audit_records(tiered: Sequence[TieredRule], timestep: int) -> tuple[AuditRecord, ...]:
    return tuple(
        AuditRecord(
            event_type=AuditEventType.RULE_STRICT_FALLBACK, timestep=timestep, route_id=t.rule.rule_id,
            reason_code=",".join(t.reasons),
            message=f"rule {t.rule.rule_id} failed provenance verification; strict fallback applied",
        )
        for t in tiered if t.tier is Tier.T0
    )


def rules_digest(tiered: Sequence[TieredRule]) -> str:
    """First 8 hex digits of the digest over (rule id, tier, active params) of the active rule set."""
    rows = sorted([t.rule.rule_id, t.tier.value, sorted(dict(t.active_params).items())] for t in tiered)
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("utf-8")).hexdigest()[:8]
