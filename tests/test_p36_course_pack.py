"""Phase 36 acceptance tests (Lead) — course submission pack drafts. Do not edit; escalate instead.

Spec: specs/V4_COURSE_PACK_SPEC.md. Checks structure, the disclosure rule (P0 not filed), D-27 honesty, the
14D/14C/14B and rule-tier wording, and that every number in the outward-facing text traces to a frozen file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P36")

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "docs" / "course"
FILES = ("README.md", "DISCLOSURE.md", "REPORT.md", "POSTER.md", "VIDEO_SHOT_LIST.md", "VIVA_QA.md", "USER_GUIDE.md",
         "CONTRIBUTION_LOG.md", "REFERENCES.md", "NUMBERS.md")
OUTWARD = ("REPORT.md", "POSTER.md", "VIDEO_SHOT_LIST.md", "VIVA_QA.md", "USER_GUIDE.md")
REPORT_HEADINGS = ("Problem", "Literature", "Method", "Experiments", "Results", "Limitations", "Ethics and safety",
                   "Future work")
TOPICS = {"problem", "data", "road-graph", "hazard-model", "planners", "reinforcement-learning", "retrieval",
          "claim-support", "rule-tiers", "gate", "evaluation", "limitations", "ethics", "reproducibility", "hardware",
          "future-work"}
DATA_ROOTS = ("data/eval_results/", "data/eval_v3/", "data/constraints_v4/", "data/demo_v4/")
NUMBER = re.compile(r"\d+(?:\.\d+)? %|\d+\.\d+")


def _read(name):
    path = COURSE / name
    assert path.is_file(), f"docs/course/{name} is missing"
    return path.read_text(encoding="utf-8")


def _policy():
    return json.loads((ROOT / "specs" / "contracts" / "claims_policy.json").read_text(encoding="utf-8"))


def _pointer(document, pointer):
    for part in pointer.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def _format(value, fmt):
    return {
        "percent1": lambda v: f"{float(v) * 100:.1f} %",
        "percent2": lambda v: f"{float(v) * 100:.2f} %",
        "fixed3": lambda v: f"{float(v):.3f}",
        "fixed2": lambda v: f"{float(v):.2f}",
        "integer": lambda v: str(int(v)),
        "ms0": lambda v: f"{float(v):.0f} ms",
        "text": str,
    }[fmt](value)


def _ledger():
    rows = []
    for line in _read("NUMBERS.md").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in ("Written", "") or set(cells[0]) <= set("-: "):
            continue
        rows.append(dict(zip(("written", "file", "pointer", "format"), (c.strip("`") for c in cells))))
    return rows


def test_every_file_exists_and_the_report_has_its_sections():
    for name in FILES:
        _read(name)
    report = _read("REPORT.md")
    headings = re.findall(r"^## (.+?)\s*$", report, re.M)
    for heading in REPORT_HEADINGS:
        assert heading in headings, heading
    assert "no outcome-effect claim" in report
    assert "14D" in report and "evaluation of record" in report


def test_viva_bank_has_thirty_questions_covering_every_topic():
    text = _read("VIVA_QA.md")
    entries = re.findall(r"^### Q(\d+)\. .+ \[topic: ([a-z-]+)\]\s*$", text, re.M)
    assert [int(n) for n, _ in entries] == list(range(1, 31))
    assert TOPICS <= {topic for _, topic in entries}
    assert text.count("**Answer:**") == 30


def test_video_is_at_most_three_minutes_and_poster_is_a1():
    text = _read("VIDEO_SHOT_LIST.md")
    spans = [(int(a) * 60 + int(b), int(c) * 60 + int(d))
             for a, b, c, d in re.findall(r"^\|\s*(\d+):(\d\d)–(\d+):(\d\d)\s*\|", text, re.M)]
    assert spans and spans[0][0] == 0 and spans[-1][1] <= 180
    assert all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))
    assert "Run demo" in text and "Live session" in text
    outage = sum(int(c) * 60 + int(d) - int(a) * 60 - int(b)
                 for a, b, c, d in re.findall(r"^\|\s*(\d+):(\d\d)–(\d+):(\d\d)\s*\|[^|\n]*Network outage", text, re.M))
    assert outage == 90, f"Network outage rows cover {outage} s, not 90 s"
    poster = _read("POSTER.md")
    assert "A1" in poster and "594" in poster and "841" in poster


def test_contribution_log_is_a_template_for_the_student():
    text = _read("CONTRIBUTION_LOG.md")
    assert "To be completed by the student." in text
    assert "## Use of AI assistance" in text


def test_disclosure_level_and_restricted_terms():
    first = _read("DISCLOSURE.md").splitlines()[0].strip()
    assert first in ("Disclosure level: RESTRICTED", "Disclosure level: FULL")
    if first.endswith("FULL"):
        status = (ROOT / "docs" / "patent-roadmap" / "STATUS.md").read_text(encoding="utf-8")
        assert "Disclosure level FULL approved by the user" in status
        return
    terms = _policy()["restricted_terms_until_disclosure"]
    for name in FILES:
        if name in ("DISCLOSURE.md", "NUMBERS.md"):
            continue
        text = _read(name)
        for term in terms:
            flags = 0 if term.isupper() else re.I
            assert not re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, flags), (name, term)


def test_no_outcome_effect_claim_anywhere():
    policy = _policy()
    banned = [re.compile(p, re.I) for p in policy["banned_outcome_patterns"]]
    exempt = [re.compile(re.escape(p), re.I) for p in policy["negation_exemptions"]]
    for name in FILES:
        for line in _read(name).splitlines():
            if any(e.search(line) for e in exempt):
                continue
            assert not any(b.search(line) for b in banned), (name, line)


def test_claim_support_and_tier_wording():
    for name in FILES:
        text = _read(name)
        if "14C" in text:
            assert "failed" in text, name
        if "14B" in text:
            assert "superseded" in text, name
        for line in text.splitlines():
            if re.search(r"NDMA-R0\d", line) and re.search(r"\bT2\b", line):
                assert re.search(r"\bT1\b", line), (name, line)


def test_numbers_ledger_resolves_and_covers_every_number():
    rows = _ledger()
    assert rows, "NUMBERS.md has no rows"
    written = set()
    for row in rows:
        written.add(row["written"])
        if row["format"] == "literal":
            assert row["file"] == "-" and row["pointer"] not in ("", "-"), row
            continue
        assert row["file"].startswith(DATA_ROOTS), row
        path = ROOT / row["file"]
        assert path.is_file(), row
        value = _pointer(json.loads(path.read_text(encoding="utf-8")), row["pointer"])
        assert _format(value, row["format"]) == row["written"], (row, value)
    for name in OUTWARD:
        for line in _read(name).splitlines():
            if line.lstrip().startswith("#"):
                continue
            for token in NUMBER.findall(line):
                assert token in written, f"{name}: '{token}' is not in NUMBERS.md ({line.strip()[:80]})"


def test_phase27_failure_rates_travel_with_r():
    rows = _ledger()
    r_rows = [row["written"] for row in rows if row["pointer"].endswith("/R_P_over_A2")]
    rate_rows = [row["written"] for row in rows
                 if row["file"].startswith("data/eval_results/phase27/")
                 and ("/E1/" in row["pointer"] or "failure" in row["pointer"] or "rate" in row["pointer"])]
    for name in OUTWARD:
        text = _read(name)
        if any(rate in text for rate in rate_rows):
            assert r_rows and any(r in text for r in r_rows), f"{name} quotes a Phase 27 failure rate without R"
