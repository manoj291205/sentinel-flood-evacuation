"""Read the recorded P15T2 tier result without recomputing its decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.constraints.ndma_rules import load_rules
from src.constraints.t2_wiring import APPROVAL_PATH, load_t2_approval

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "data/constraints_v4/p15t2/tier_results.json"
HONESTY = "REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED"


def rule_tiers(results_path: Path = RESULTS, approval_path: Path = APPROVAL_PATH) -> dict:
    path = Path(results_path)
    base = {
        "simulated": True, "honesty": HONESTY, "source": "ARTIFACT",
        "results_path": "data/constraints_v4/p15t2/tier_results.json",
        "results_sha256": None, "run_utc": None, "t2_enabled": None,
        "t2_reason": None, "approval_record_sha256": None,
        "evaluation_id": None, "rules": [], "status": "MISSING",
        "status_reason": "P15T2 tier result is missing",
    }
    if not path.is_file():
        return base
    raw = path.read_bytes()
    base["results_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        result = json.loads(raw.decode("utf-8"))
        base.update(run_utc=result["utc"], t2_enabled=result["t2_enabled"],
                    t2_reason=result["t2_reason"], approval_record_sha256=result["approval_record_sha256"])
        approval = load_t2_approval(approval_path)
        checks = [
            (result.get("schema") == "p15t2-tier-results-v1", "unexpected tier result schema"),
            (result.get("approval_record_sha256") == approval.record_sha256, "approval record changed"),
            (result.get("t2_enabled") == approval.enabled, "approval status changed"),
        ]
        rules_file = (ROOT / result["rules_file"]).resolve()
        checks.append((rules_file.is_relative_to(ROOT) and rules_file.is_file() and
                       hashlib.sha256(rules_file.read_bytes()).hexdigest() == result["rules_file_sha256"],
                       "rules file changed"))
        stale_reason = next((message for ok, message in checks if not ok), None)
        base["status"] = "STALE" if stale_reason else "CURRENT"
        base["status_reason"] = stale_reason
        predicates = {r.rule_id: r.predicate for r in load_rules(rules_file)} if rules_file.is_file() else {}
        base["rules"] = [
            {"rule_id": record["rule_id"], "predicate": predicates.get(record["rule_id"]),
             "tier": None if stale_reason else record["tier"], "active_params": record["active_params"],
             "semantic_outcome": (record.get("semantic") or {}).get("outcome"),
             "source_integrity_pass": (record.get("semantic") or {}).get("source_integrity_pass"),
             "note": "tier result is stale; re-run P15T2" if stale_reason else None}
            for record in result["records"]
        ]
        base["evaluation_id"] = result["records"][0].get("evaluation_id") if result["records"] else None
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        base["status"] = "STALE"
        base["status_reason"] = "tier result unreadable"
        base["rules"] = []
    return base
