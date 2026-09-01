"""Reward arithmetic, including the edge case that would divide by zero."""

from __future__ import annotations

import numpy as np

from src.env.shelter_env import WEIGHT_FIT, WEIGHT_TRAVEL, compute_rewards


def fact(headroom: int, travel: float, severity: float = 0.1, status: str = "operational"):
    return {
        "shelter_id": "S", "cell_id": "C", "flood_severity": severity,
        "capacity_total": headroom, "current_occupancy": 0,
        "capacity_headroom": headroom, "status": status,
        "travel_cost_minutes": travel,
    }


def test_fit_is_capped_so_excess_capacity_earns_nothing():
    """The approved design: once a shelter fits everyone, more room adds no reward."""
    facts = [fact(700, 10), fact(7000, 10)]
    r = compute_rewards(facts, population=700)
    assert r[0] == r[1]


def test_partial_fit_scales_linearly():
    facts = [fact(350, 10), fact(700, 10)]
    r = compute_rewards(facts, population=700)
    assert np.isclose(r[0], WEIGHT_FIT * 0.5 + WEIGHT_TRAVEL, atol=1e-6)


def test_closest_shelter_gets_full_travel_score():
    facts = [fact(700, 5), fact(700, 45)]
    r = compute_rewards(facts, population=700)
    assert np.isclose(r[0], WEIGHT_FIT + WEIGHT_TRAVEL, atol=1e-6)
    assert np.isclose(r[1], WEIGHT_FIT, atol=1e-6)


def test_equal_travel_costs_do_not_divide_by_zero():
    """Guard for the degenerate case where travel carries no information."""
    facts = [fact(700, 20), fact(700, 20), fact(700, 20)]
    r = compute_rewards(facts, population=700)
    assert np.all(np.isfinite(r))
    assert np.allclose(r, WEIGHT_FIT + WEIGHT_TRAVEL)


def test_zero_headroom_scores_only_travel():
    facts = [fact(0, 5), fact(700, 45)]
    r = compute_rewards(facts, population=700)
    assert np.isclose(r[0], WEIGHT_TRAVEL, atol=1e-6)


def test_rewards_stay_in_unit_range():
    rng = np.random.default_rng(0)
    for _ in range(200):
        facts = [fact(int(rng.integers(0, 2000)), float(rng.integers(5, 46)))
                 for _ in range(7)]
        r = compute_rewards(facts, population=700)
        assert np.all(r >= -1e-6) and np.all(r <= 1 + 1e-6)
