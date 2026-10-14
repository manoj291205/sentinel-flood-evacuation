"""The evaluation suite must stay reproducible and must not be rigged."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.constraints.generate import shelter_facts

SUITE = Path(__file__).resolve().parents[1] / "data" / "eval_scenarios.json"


@pytest.fixture(scope="module")
def suite():
    if not SUITE.exists():
        pytest.skip("eval suite not generated")
    return json.loads(SUITE.read_text(encoding="utf-8"))


def test_suite_declares_its_generation_distribution(suite):
    """A reader must be able to judge whether the suite is fair."""
    assert suite["_distribution"]
    assert suite["_seed"]


def test_suite_covers_regimes_where_the_constraint_layer_cannot_help(suite):
    """If only favourable cases were included the measurements would be worthless."""
    counts = suite["_regime_counts"]
    assert counts["all_safe"] >= 1
    assert counts["no_safe_shelter"] >= 1
    assert counts["mixed"] >= 1


def test_scenarios_are_structurally_valid(suite):
    for scenario in suite["scenarios"]:
        cells = {c["cell_id"] for c in scenario["grid"]["cells"]}
        assert scenario["source"]["cell_id"] in cells
        assert scenario["source"]["population_to_evacuate"] > 0
        ids = [s["shelter_id"] for s in scenario["shelters"]]
        assert len(ids) == len(set(ids))
        for shelter in scenario["shelters"]:
            assert shelter["cell_id"] in cells
            assert 0 <= shelter["current_occupancy"] <= shelter["capacity_total"]


def test_headroom_is_never_negative(suite):
    for scenario in suite["scenarios"]:
        for fact in shelter_facts(scenario):
            assert fact["capacity_headroom"] >= 0


def test_no_scenario_reuses_the_demo_scenario_id(suite):
    """The eval set must be disjoint from the demo scenario."""
    ids = {s["scenario_id"] for s in suite["scenarios"]}
    assert "flood-evac-demo-01" not in ids
