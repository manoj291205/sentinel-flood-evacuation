"""Acceptance-test gating for V4 milestones.

Lead writes failing acceptance tests before a milestone is built. Tests marked
``@pytest.mark.milestone("P21")`` whose milestone is listed in ``acceptance_pending.json``
are collected as non-strict xfail, so the full suite stays green for both build lanes.
Builders run the real thing with ``--runxfail``. Lead removes a milestone from the
pending list when it merges that milestone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_PENDING_FILE = Path(__file__).with_name("acceptance_pending.json")


def _pending() -> set[str]:
    try:
        data = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    return set(data.get("pending", []))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "milestone(id): V4 acceptance test belonging to a milestone such as P21"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    pending = _pending()
    for item in items:
        marker = item.get_closest_marker("milestone")
        if marker and marker.args and marker.args[0] in pending:
            item.add_marker(
                pytest.mark.xfail(
                    reason=f"{marker.args[0]} not merged yet (run with --runxfail to see real failures)",
                    strict=False,
                )
            )
