"""Phase 27 acceptance tests (Lead) — pre-registration integrity and evaluation building blocks.

Do not edit; escalate instead. The pre-registration hash below may only change through a dated Lead
amendment to specs/V4_EVALUATION_PREREG.md.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P27")

PREREG = Path(__file__).resolve().parents[1] / "specs" / "V4_EVALUATION_PREREG.md"
PREREG_SHA256 = "bdfe8caf4ad63a37f7df47f98d3678751528c289e12c9beb804f81f74157ace9"


def test_preregistration_is_frozen():
    assert hashlib.sha256(PREREG.read_bytes()).hexdigest() == PREREG_SHA256


def test_stress_world_registered_as_preregistered():
    from src.sim.world import get_world_config

    stress, high = asdict(get_world_config("v4-stress-dt2-v1")), asdict(get_world_config("v4-high-dt2-v1"))
    assert stress["base_uncertainty_id"] == "v3-high-v1" and stress["walk_in_rate"] == 2.0
    for key in set(stress) - {"world_id", "walk_in_rate"}:
        assert stress[key] == high[key], key


def test_eval_params_are_deterministic():
    from src.certify.params import get_cert_params

    p = get_cert_params("v4-cert-eval-v1")
    assert (p.k0, p.max_looks, p.eps_dispatch, p.delta) == (256, 3, 0.05, 0.01)
    assert math.isinf(p.deadline_ms)


def test_baseline_b_uses_one_independent_root_per_candidate():
    from src.certify.baselines import baseline_b_root
    from src.certify.futures import root_key

    common = dict(incident_id="KOCHI-SIM-1050000", forecast_hash="a" * 64, graph_fingerprint="b" * 64,
                  ledger_hash="c" * 64)
    r1 = baseline_b_root(**common, action_key="Z1->S1")
    r2 = baseline_b_root(**common, action_key="Z1->S2")
    assert r1 != r2
    assert r1 == root_key(**common, params_id="baseline-b-v1:Z1->S1")


def test_statistics_helpers():
    from src.evaluation_v4.stats import mcnemar_exact, paired_bootstrap_ci

    assert mcnemar_exact(10, 0) == pytest.approx(2 * 0.5**10)
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 0) == 1.0
    assert paired_bootstrap_ci([-1.0] * 20, resamples=1000, seed=27_001) == (-1.0, -1.0)
    lo, hi = paired_bootstrap_ci([0.0, 1.0] * 50, resamples=2000, seed=27_001)
    assert 0.3 < lo < 0.5 < hi < 0.7
    assert paired_bootstrap_ci([0.0, 1.0] * 50, resamples=2000, seed=27_001) == (lo, hi)
