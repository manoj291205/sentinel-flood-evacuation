"""Lead check (Wave C review, 2026-10-18): while docs/course/DISCLOSURE.md says RESTRICTED, the text the console renders
uses none of the restricted mechanism terms of specs/contracts/claims_policy.json, and does not mention the patent.
Scans the console components and the API modules and contract fixtures whose strings reach the screen."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "specs/contracts/claims_policy.json").read_text(encoding="utf-8"))
SHOWN = [
    *sorted(p for p in (ROOT / "web/src").rglob("*.tsx") if ".test." not in p.name),
    ROOT / "src/api/why.py", ROOT / "src/api/live_session.py", ROOT / "src/api/demo_live.py",
    ROOT / "src/escrow/session.py", ROOT / "src/presentation/rule_tiers.py",
    ROOT / "specs/contracts/demo_steps.json", ROOT / "specs/contracts/decision_why_fixture.json",
    ROOT / "specs/contracts/evidence_manifest.json", ROOT / "specs/contracts/system_status_fixture.json",
]


def _restricted() -> bool:
    first = (ROOT / "docs/course/DISCLOSURE.md").read_text(encoding="utf-8").splitlines()[0]
    return first.strip() == "Disclosure level: RESTRICTED"


def test_console_text_has_no_restricted_mechanism_terms():
    if not _restricted():
        return
    terms = [*POLICY["restricted_terms_until_disclosure"], "patent"]
    hits = []
    for path in SHOWN:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for term in terms:
                flags = 0 if term == "CRN" else re.IGNORECASE
                if re.search(rf"(?<![A-Za-z_]){re.escape(term)}(?![A-Za-z])", line, flags):
                    hits.append(f"{path.relative_to(ROOT)}:{number}: {term}")
    assert hits == []
