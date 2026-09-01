"""Run the constraint step standalone against the Step 1 scenario and print the result.

Run:  .venv/bin/python -m src.constraints.test_constraints            (uses cache)
      .venv/bin/python -m src.constraints.test_constraints --refresh  (forces API call)
"""

from __future__ import annotations

import json
import sys
import textwrap

from .generate import (
    ConstraintError,
    allowed_shelter_ids,
    load_or_generate,
    load_scenario,
    shelter_facts,
)


def main() -> int:
    refresh = "--refresh" in sys.argv
    scenario = load_scenario()

    try:
        payload = load_or_generate(refresh=refresh)
    except ConstraintError as exc:
        print(f"\nFAILED: {exc}")
        return 1

    facts = {f["shelter_id"]: f for f in shelter_facts(scenario)}
    constraints = {c["action_id"]: c for c in payload["constraints"]}

    print()
    print("=" * 92)
    print(f"CONSTRAINT VERDICTS   scenario_id={payload['scenario_id']}   model={payload['_meta']['model']}")
    print("=" * 92)
    header = f"{'ID':<4}{'verdict':<11}{'severity':<20}{'headroom':>9}{'travel':>8}   citation"
    print(header)
    print("-" * 92)

    for shelter_id in sorted(constraints):
        item = constraints[shelter_id]
        fact = facts[shelter_id]
        mark = "VERIFIED" if item.get("citation_verified") else "UNVERIFIED"
        print(
            f"{shelter_id:<4}{item['status'].upper():<11}"
            f"{str(fact['flood_severity']) + ' ' + fact['severity_band']:<20}"
            f"{fact['capacity_headroom']:>9}{fact['travel_cost_minutes']:>8}   "
            f"{item['source_document']} [{mark}]"
        )

    print()
    print("=" * 92)
    print("REASONS AND CITED CLAUSES")
    print("=" * 92)
    for shelter_id in sorted(constraints):
        item = constraints[shelter_id]
        mark = "VERIFIED verbatim" if item.get("citation_verified") else "UNVERIFIED - not found verbatim"
        print(f"\n{shelter_id}  [{item['status'].upper()}]  (status={facts[shelter_id]['status']})")
        print(textwrap.fill(f"reason: {item['reason']}", width=90, subsequent_indent="        "))
        print(f"cited : {item['source_document']}  ({mark})")
        print(textwrap.fill(f'quote : "{item["source_excerpt"]}"', width=90, subsequent_indent="        "))

    allowed = allowed_shelter_ids(payload)
    excluded = [c["action_id"] for c in payload["constraints"] if c["status"] == "excluded"]
    unverified = payload["_meta"].get("unverified_citations", [])

    print()
    print("=" * 92)
    print(f"ALLOWED  ({len(allowed)}): {allowed}")
    print(f"EXCLUDED ({len(excluded)}): {excluded}")
    print(f"attempts used: {payload['_meta']['attempts_used']}")
    if unverified:
        print(f"UNVERIFIED CITATIONS: {unverified}  <-- flagged, not silently trusted")
    else:
        print("All citations verified verbatim against the retrieved NDMA text.")
    print("=" * 92)

    if not allowed:
        print(
            "\nWARNING: every shelter was excluded. Step 4's action mask would be empty\n"
            "and the RL policy would have nothing to choose. Reporting rather than hiding."
        )
        return 2

    print("\nRaw validated JSON (this exact shape is what Steps 4-6 consume):")
    print(json.dumps({k: v for k, v in payload.items() if k != "_meta"}, indent=2)[:1400])
    print("...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
