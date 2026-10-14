"""Phase 24 acceptance tests (Lead) — sequential fail-closed certifier. Do not edit; escalate instead."""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest
from scipy.stats import beta

pytestmark = pytest.mark.milestone("P24")


@dataclass(frozen=True)
class FakeCandidate:
    zone_id: str
    shelter_id: str
    people: int = 20
    edge_ids: tuple = ()
    departure_timestep: int = 0

    @property
    def action_key(self):
        return f"{self.zone_id}->{self.shelter_id}"


class FakeFutures:
    """Each candidate succeeds in future k with a fixed probability, keyed by (seed, key, k)."""

    def __init__(self, probabilities, seed=0, a_max=21):
        self.p = probabilities
        self.seed = seed
        self.A_MAX = a_max

    def future(self, k):
        if k < 1:
            raise ValueError("k must be >= 1")
        return k


def _fake_rollout(futures):
    from src.certify.rollout import Outcome, RolloutResult

    def rollout(candidate, k, *args, **kwargs):
        u = random.Random(f"{futures.seed}|{candidate.action_key}|{k}").random()
        ok = u < futures.p[candidate.action_key]
        return RolloutResult(
            z=ok, outcome=Outcome.OK if ok else Outcome.STRANDED, arrival_timestep=3,
            utility=float(candidate.people if ok else -candidate.people),
            path_ok=ok, shelter_ok=True, capacity_ok=True,
        )

    return rollout


def _certify(probabilities, *, seed=0, params=None, clock=None, order=None):
    from src.certify.certifier import certify
    from src.certify.params import CertParams

    futures = FakeFutures(probabilities, seed)
    keys = order or list(probabilities)
    candidates = [FakeCandidate(*key.split("->")) for key in keys]
    kwargs = {"rollout": _fake_rollout(futures)}
    if clock is not None:
        kwargs["clock"] = clock
    return certify(candidates, futures, None, None, params or CertParams(), None, **kwargs)


def test_clopper_pearson_matches_scipy():
    from src.certify.certifier import clopper_pearson

    for s, n, alpha in [(252, 256, 0.01), (503, 512, 0.0001), (0, 50, 0.05), (50, 50, 0.05), (10, 20, 0.025)]:
        lo, hi = clopper_pearson(s, n, alpha)
        expect_lo = 0.0 if s == 0 else beta.ppf(alpha, s, n - s + 1)
        expect_hi = 1.0 if s == n else beta.ppf(1 - alpha, s + 1, n - s)
        assert lo == pytest.approx(expect_lo, abs=1e-12)
        assert hi == pytest.approx(expect_hi, abs=1e-12)
        assert 0.0 <= lo <= s / n <= hi <= 1.0


def test_params_defaults():
    from src.certify.params import CertParams, get_cert_params

    p = get_cert_params("v4-cert-v1")
    assert p == CertParams()
    assert (p.eps_dispatch, p.eps_keep, p.delta, p.k0, p.max_looks) == (0.05, 0.10, 0.01, 256, 4)
    assert p.eps_keep > p.eps_dispatch


def test_verdicts_and_fail_closed():
    from src.certify.certifier import Verdict

    result = _certify({"Z-01->S-02": 0.999, "Z-03->S-04": 0.70, "Z-02->S-05": 0.955})
    verdicts = {c.action_key: c.verdict for c in result.candidates}
    assert verdicts["Z-01->S-02"] is Verdict.FEASIBLE
    assert verdicts["Z-03->S-04"] is Verdict.INFEASIBLE
    allowed = result.allowed_keys()
    assert "WAIT" in allowed and "Z-01->S-02" in allowed and "Z-03->S-04" not in allowed
    for c in result.candidates:
        if c.verdict is Verdict.UNDECIDED:
            assert c.action_key not in allowed
    assert result.chosen_key in allowed


def test_empty_certified_set_chooses_hold():
    result = _certify({"Z-04->S-01": 0.6})
    assert result.chosen_key == "WAIT"
    assert result.allowed_keys() == frozenset({"WAIT"})


def test_false_accept_rate_is_bounded_by_delta():
    from src.certify.certifier import Verdict

    accepts = 0
    reps = 1000
    for rep in range(reps):
        result = _certify({"Z-01->S-02": 0.94}, seed=rep)
        accepts += result.candidates[0].verdict is Verdict.FEASIBLE
    assert accepts / reps <= 0.01


def test_deadline_leaves_undecided_blocked():
    from src.certify.certifier import Verdict

    ticks = iter(range(0, 10_000_000, 60))  # every clock read advances 60 ms
    result = _certify({"Z-02->S-05": 0.952}, clock=lambda: next(ticks) / 1000.0)
    assert result.deadline_hit
    candidate = result.candidates[0]
    assert candidate.verdict is Verdict.UNDECIDED
    assert candidate.action_key not in result.allowed_keys()


def test_certification_is_order_invariant():
    probabilities = {"Z-01->S-02": 0.99, "Z-03->S-04": 0.97, "Z-02->S-05": 0.955, "Z-04->S-01": 0.8}
    forward = _certify(probabilities)
    backward = _certify(probabilities, order=list(reversed(list(probabilities))))
    as_map = lambda r: {c.action_key: (c.verdict, c.successes, c.n, c.lower, c.upper) for c in r.candidates}
    assert as_map(forward) == as_map(backward)
    assert forward.chosen_key == backward.chosen_key


def test_paired_argmax_uses_common_futures():
    from src.certify.certifier import paired_argmax

    utilities = {"A": [10, 10, 10, -10], "B": [9, 9, 9, 9]}
    assert paired_argmax(["A", "B"], utilities) == "B"
    assert paired_argmax(["A", "B"], {"A": [5, 5], "B": [5, 5]}) == "A"  # tie -> canonical order given


def test_evaluate_actions_legacy_and_certified():
    from src.certify.certifier import CandidateCertificate, Verdict
    from src.geospatial import build_geospatial_demo_runtime
    from src.safety import evaluate_actions
    from src.safety.models import RuleProvenance
    from src.sim import DispatchAction

    scenario, simulator, _, _ = build_geospatial_demo_runtime("v3-medium-v1")
    simulator.observe()
    state = simulator.prepared_state_for_debug()
    legacy = evaluate_actions(scenario, state)
    assert evaluate_actions(scenario, state, certifier=None).to_dict() == legacy.to_dict()

    allowed = [a for a in legacy.allowed_actions if isinstance(a, DispatchAction)]
    keep = f"{allowed[0].zone_id}->{allowed[0].shelter_id}"

    def certifier(_scenario, _state, actions):
        out = {}
        for action in actions:
            key = f"{action.zone_id}->{action.shelter_id}"
            verdict = Verdict.FEASIBLE if key == keep else Verdict.UNDECIDED
            out[key] = CandidateCertificate(key, verdict, 250, 256, 0.96 if key == keep else 0.93, 0.99, 1.0, {})
        return out

    gated = evaluate_actions(scenario, state, certifier=certifier)
    gated_dispatches = [a for a in gated.allowed_actions if isinstance(a, DispatchAction)]
    assert [f"{a.zone_id}->{a.shelter_id}" for a in gated_dispatches] == [keep]
    evaluation = next(e for e in gated.evaluations if e.action_key == keep)
    assert any(v.provenance is RuleProvenance.CERTIFIED_CHANCE for v in evaluation.rule_verdicts)
