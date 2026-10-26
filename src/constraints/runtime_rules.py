"""Load recorded, authenticated T2 rules for live sessions without calling a provider.

T1 is provenance, not semantic approval of a numeric policy. Its configured rules
remain visible but never become mandatory operational predicates here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from .claim_support import ClaimSupportResult
from .evidence import get_authenticated_evidence, operational_citation_eligible
from .ndma_rules import load_rules
from .t2_wiring import load_t2_approval
from .tiering import Tier, TieredRule, rules_digest

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "data/constraints_v4/p15t2/tier_results.json"


@dataclass(frozen=True)
class RuntimeRuleSet:
    rules: tuple[TieredRule, ...]
    metadata: dict


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate runtime rule metadata key")
            value[key] = item
        return value
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(value, dict):
        raise ValueError("runtime rule metadata must be an object")
    return value


def load_runtime_rules(*, rules_path: Path | None = None, tier_results_path: Path | None = None,
                       approval_path: Path | None = None, root: Path = ROOT) -> RuntimeRuleSet:
    root = Path(root).resolve()
    rules_path = Path(rules_path) if rules_path is not None else root / "data/constraints_v4/ndma_constraints.json"
    result_path = Path(tier_results_path) if tier_results_path is not None else root / "data/constraints_v4/p15t2/tier_results.json"
    approval_path = Path(approval_path) if approval_path is not None else root / "specs/approvals/t2_semantic_verifier.json"
    metadata = {"status": "STALE", "source": "AUTHENTICATED_RECORDED_RULES", "active_t2_count": 0,
                "enforced_count": 0, "digest": None, "rules": [],
                "rule_digest": None, "configured_rules": [], "reason": None,
                "rules_file_sha256": None, "tier_results_sha256": None, "approval_record_sha256": None}
    try:
        approval = load_t2_approval(approval_path, root=root)
        if not approval.enabled:
            raise ValueError(approval.reason)
        approval_record = _read(approval_path)
        for field in ("approved_by_user_utc", "approved_by_opus_utc"):
            if datetime.fromisoformat(approval_record[field].replace("Z", "+00:00")).tzinfo is None:
                raise ValueError("approval timestamps must include a timezone")
        result = _read(result_path)
        if result.get("schema") != "p15t2-tier-results-v1":
            raise ValueError("unexpected recorded rule schema")
        referenced = (root / result["rules_file"]).resolve()
        if not referenced.is_relative_to(root) or referenced != rules_path.resolve():
            raise ValueError("recorded rules path mismatch")
        if result.get("rules_file_sha256") != _sha(rules_path):
            raise ValueError("recorded rules hash mismatch")
        if result.get("approval_record_sha256") != approval.record_sha256:
            raise ValueError("recorded rule approval mismatch")
        if result.get("t2_enabled") is not True:
            raise ValueError("recorded semantic verification was not enabled")
        raw_rules = _read(rules_path)["rules"]
        for raw in raw_rules:
            if type(raw.get("approved")) is not bool:
                raise ValueError("rule approval must be an explicit boolean")
            for values in (raw["params"], raw["strict_fallback"]):
                if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                       for value in values.values()):
                    raise ValueError("rule parameters must be finite nonnegative numbers")
        rules = load_rules(rules_path)
        records = result["records"]
        if not isinstance(records, list) or len(records) != len(rules):
            raise ValueError("recorded approved-rule set mismatch")
        by_id = {row["rule_id"]: row for row in records}
        if len(by_id) != len(records) or set(by_id) != {rule.rule_id for rule in rules}:
            raise ValueError("recorded approved-rule IDs mismatch")
        active, configured = [], []
        identity = {"evaluation_id": approval.evaluation_id, "provider_id": approval.provider_id,
                    "model_id": approval.model_id, "prompt_version": approval.prompt_version,
                    "prompt_sha256": approval.prompt_sha256,
                    "approval_record_sha256": approval.record_sha256}
        for rule in rules:
            record = by_id[rule.rule_id]
            if any(record.get(key) != value for key, value in identity.items()):
                raise ValueError("recorded rule semantic identity mismatch")
            tier = Tier(record["tier"])
            if record.get("active_params") != dict(rule.params):
                raise ValueError("recorded rule parameters changed")
            reason = "NOT_SEMANTICALLY_SUPPORTED"
            enforced = False
            chunk = get_authenticated_evidence(rule.evidence["chunk_id"])
            expected = (rule.evidence["source_id"], rule.evidence["filename"], rule.evidence["page"],
                        rule.evidence["passage_sha256"])
            if (chunk.source_id, chunk.filename, chunk.page, chunk.passage_sha256) != expected:
                raise ValueError("rule evidence does not match canonical provenance")
            if not rule.evidence["span"] or rule.evidence["span"] not in chunk.text:
                raise ValueError("rule evidence span is not canonical")
            if tier is Tier.T2:
                from .claim_support_p14d import split_sentences
                semantic = record.get("semantic")
                if not isinstance(semantic, dict) or record.get("semantic_status") != "CALLED":
                    raise ValueError("T2 rule lacks recorded semantic verification")
                ids = semantic["supporting_sentence_ids"]
                sentences = split_sentences(chunk.text)
                if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
                        or any(type(i) is not int or not 1 <= i <= len(sentences) for i in ids)):
                    raise ValueError("T2 rule citations are invalid")
                if semantic.get("http_status") != 200 or semantic.get("response_model") != approval.model_id:
                    raise ValueError("T2 rule response identity is invalid")
                if semantic.get("finish_reason") != "stop":
                    raise ValueError("T2 rule response is incomplete")
                confidence = semantic["confidence"]
                if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
                    raise ValueError("T2 rule confidence is invalid")
                outcome = ClaimSupportResult(semantic["outcome"], confidence,
                    [sentences[i - 1] for i in ids], "Recorded rule verification",
                    semantic.get("source_integrity_pass") is True)
                if not operational_citation_eligible(outcome, chunk):
                    raise ValueError("T2 rule is not eligible for operational enforcement")
                active.append(TieredRule(rule, Tier.T2, (), dict(rule.params)))
                reason, enforced = "AUTHENTICATED_T2", True
            configured.append({"rule_id": rule.rule_id, "tier": tier.value, "enforced": enforced,
                               "reason": reason, "params": dict(rule.params)})
        metadata.update(status="CURRENT", active_t2_count=len(active), configured_rules=configured,
                        rule_digest=rules_digest(active) if active else None,
                        enforced_count=len(active), rules=configured,
                        digest=rules_digest(active) if active else None,
                        reason="AUTHENTICATED_T2" if active else "NO_APPROVED_T2_RULES",
                        rules_file_sha256=_sha(rules_path), tier_results_sha256=_sha(result_path),
                        approval_record_sha256=approval.record_sha256)
        return RuntimeRuleSet(tuple(active), metadata)
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        metadata["reason"] = str(exc)
        return RuntimeRuleSet((), metadata)
