"""Source-labelled project counts for the local story page."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from src.api.library import ROOT, library_index
from src.api.library import _read_json


@lru_cache(maxsize=1)
def project_facts() -> dict:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    milestone = readme.split("<!-- MILESTONE-TABLE:START", 1)[1].split("<!-- MILESTONE-TABLE:END", 1)[0]
    match = re.search(r"Last refreshed:\s*(\d{4}-\d{2}-\d{2}).*?·\s*(\d+) tests pass", milestone)
    summary = _read_json(ROOT / "data/eval_v3/phase11_corpus_summary.json")
    runs = library_index()["runs"]
    return {"facts": {
        "tests": {"value": int(match.group(2)) if match else None,
                  "as_of": match.group(1) if match else None,
                  "source_path": "README.md (reviewed milestone table)",
                  "reason": None if match else "Reviewed test count unavailable"},
        "recorded_runs": {"value": len(runs), "source_path": "data/eval_results/phase27/runs/*.jsonl"},
        "traces": {"value": sum(row["has_trace"] for row in runs),
                   "source_path": "data/eval_results/phase27/states/*.jsonl.gz"},
        "corpus_chunks": {"value": summary["chunk_count"],
                          "source_path": "data/eval_v3/phase11_corpus_summary.json"},
        "phases": {"value": len(re.findall(r"^\|\s*(?:\d|P0,)", milestone, re.MULTILINE)),
                   "source_path": "README.md (reviewed milestone table)",
                   "reason": "Milestone rows; ranges count as one row and planned phases are included"},
    }, "source": "LOCAL ARTIFACTS"}
