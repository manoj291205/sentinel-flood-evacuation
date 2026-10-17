"""Phase 15T2: tier the approved NDMA rules, with T2 from the 14D approval record.

    python scripts/phase15t2_tier_rules.py                      # offline dry run: no network, T2 disabled
    python scripts/phase15t2_tier_rules.py --preflight          # one GET on the model endpoint (status only)
    python scripts/phase15t2_tier_rules.py --live --attest-zdr  # one 14D call per eligible rule; writes results

GROQ_API_KEY comes from the environment only and is never written anywhere.
Spec: specs/V4_CONSTRAINT_TIERS_SPEC.md, Amendment 2026-10-17.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.constraints import claim_support_p14d as p14d  # noqa: E402
from src.constraints.ndma_rules import DEFAULT_RULES_PATH, corpus_chunk_lookup  # noqa: E402
from src.constraints.t2_wiring import load_tiered_rules  # noqa: E402

OUT = ROOT / "data" / "constraints_v4" / "p15t2" / "tier_results.json"
SCHEMA = "p15t2-tier-results-v1"


def _lookup():
    from src.rag.ingest import prepare_corpus

    return corpus_chunk_lookup(prepare_corpus())


def _summary(load) -> str:
    lines = [f"T2 {'enabled' if load.t2_enabled else 'disabled'} ({load.t2_reason}); approval {load.approval.reason}"]
    for record in load.records:
        sem = record["semantic"] or {}
        lines.append(f"{record['rule_id']}: {record['tier']} {record['semantic_status']}"
                     f" {sem.get('outcome', '')} integrity={sem.get('source_integrity_pass', '')}".rstrip())
    return "\n".join(lines)


def preflight() -> int:
    import httpx

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY is not set")
        return 2
    with httpx.Client(timeout=60.0) as client:
        response = client.get(f"https://api.groq.com/openai/v1/models/{p14d.MODEL_ID}",
                              headers={"Authorization": f"Bearer {api_key}"})
    print(f"preflight HTTP {response.status_code}")
    return 0 if response.status_code == 200 else 1


def live(rules_path: Path, out: Path) -> int:
    if out.exists():
        print(f"{out} exists; refusing to overwrite a recorded run")
        return 2
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set")
        return 2
    started = time.time()
    load = load_tiered_rules(rules_path, _lookup(), attest_zdr=True)
    result = {
        "schema": SCHEMA,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "rules_file": rules_path.relative_to(ROOT).as_posix(),
        "rules_file_sha256": hashlib.sha256(rules_path.read_bytes()).hexdigest(),
        "approval_record_sha256": load.approval.record_sha256,
        "approval_reason": load.approval.reason,
        "t2_enabled": load.t2_enabled,
        "t2_reason": load.t2_reason,
        "calls_total": sum(1 for r in load.records if r["semantic"] is not None),
        "records": list(load.records),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(_summary(load))
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--attest-zdr", action="store_true",
                        help="the user confirmed Zero Data Retention for the Groq organisation that owns the key")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.preflight:
        return preflight()
    if args.live:
        if not args.attest_zdr:
            print("--live requires --attest-zdr")
            return 2
        return live(args.rules.resolve(), args.out.resolve())
    print(_summary(load_tiered_rules(args.rules, _lookup(), attest_zdr=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
