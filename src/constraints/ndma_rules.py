"""NDMA document rules for the joint indicator (Phase 15', confidential, dependent claim 13)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA = "ndma-constraints-v1"
# Closed predicate set: name -> the single parameter it takes. All four are upper limits, so a
# strict fallback is stricter exactly when it is <= the normal value.
PREDICATES: dict[str, str] = {
    "MAX_TRAVEL_MINUTES": "minutes",
    "MAX_ROUTE_HAZARD": "hazard",
    "MAX_DESTINATION_SEVERITY": "severity",
    "MAX_OCCUPANCY_FRACTION": "fraction",
}
DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "constraints_v4" / "ndma_constraints.json"


@dataclass(frozen=True)
class NdmaRule:
    rule_id: str
    text: str
    predicate: str
    params: Mapping[str, float]
    strict_fallback: Mapping[str, float]
    evidence: Mapping[str, Any]
    approved: bool = False
    approved_by: str | None = None
    approved_utc: str | None = None

    def __post_init__(self) -> None:
        if self.predicate not in PREDICATES:
            raise ValueError(f"{self.rule_id}: unknown predicate {self.predicate!r}")
        name = PREDICATES[self.predicate]
        for label, values in (("params", self.params), ("strict_fallback", self.strict_fallback)):
            if set(values) != {name}:
                raise ValueError(f"{self.rule_id}: {label} must be exactly {{{name!r}}}")
        if float(self.strict_fallback[name]) > float(self.params[name]):
            raise ValueError(f"{self.rule_id}: strict_fallback is looser than params")
        for key in ("source_id", "filename", "page", "chunk_id", "passage_sha256", "span"):
            if key not in self.evidence:
                raise ValueError(f"{self.rule_id}: evidence is missing {key!r}")


def _rule(raw: Mapping[str, Any]) -> NdmaRule:
    return NdmaRule(
        rule_id=raw["rule_id"], text=raw["text"], predicate=raw["predicate"],
        params=dict(raw["params"]), strict_fallback=dict(raw["strict_fallback"]),
        evidence=dict(raw["evidence"]), approved=bool(raw.get("approved", False)),
        approved_by=raw.get("approved_by"), approved_utc=raw.get("approved_utc"),
    )


def load_rules(path: str | Path = DEFAULT_RULES_PATH) -> tuple[NdmaRule, ...]:
    """Approved rules only; any validation error in any listed rule raises."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"unexpected rule file schema {data.get('schema')!r}")
    rules = [_rule(raw) for raw in data["rules"]]  # validate every rule, approved or not
    ids = [r.rule_id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ids")
    return tuple(r for r in rules if r.approved)


def corpus_chunk_lookup(prepared) -> Callable[[NdmaRule], Any]:
    """Chunk lookup over a ``PreparedCorpus``; returns None when the chunk no longer resolves."""
    from .claim_support import get_chunk_by_id

    def lookup(rule: NdmaRule):
        try:
            return get_chunk_by_id(rule.evidence["chunk_id"], prepared)
        except ValueError:
            return None

    return lookup
