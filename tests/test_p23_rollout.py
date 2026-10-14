"""Phase 23 acceptance tests (Lead) — joint first-hitting rollout. Do not edit; escalate instead.

Timeline used by every case (world dt = 2 min, boarding 4 min, speed cap 15 km/h, hazard 0,
two 500 m edges at 30 km/h assumed speed -> capped to 15 km/h -> 2 min each):
departure t=0 -> enter e1 at minute 4 (step 2) -> enter e2 at minute 6 (step 3)
-> arrive minute 8 (step 4).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.milestone("P23")


class StubFuture:
    def __init__(self, *, closed=(), severity=None, status=None, walk_ins=None):
        self.k = 1
        self.start_timestep = 0
        self.steps = 20
        self._closed = set(closed)          # {(edge_id, step)} closed at that step and after
        self._severity = severity or {}     # {(shelter_id, step): value}
        self._status = status or {}
        self._walk = walk_ins or {}

    def edge_open(self, edge_id, t):
        return not any(e == edge_id and t >= s for e, s in self._closed)

    def edge_hazard(self, edge_id, t):
        return 0.0

    def shelter_severity(self, shelter_id, t):
        return self._severity.get((shelter_id, t), 0.1)

    def shelter_status(self, shelter_id, t):
        return self._status.get((shelter_id, t), "OPEN")

    def walk_ins(self, shelter_id, t):
        return self._walk.get((shelter_id, t), 0)

    def travel_normal(self, *key):
        return 0.0


@pytest.fixture(scope="module")
def setup():
    from src.certify.params import CertParams
    from src.certify.rollout import Candidate
    from src.geospatial.road_network import RoadEdge, RoadGraph, RoadNode
    from src.sim.world import get_world_config

    nodes = (RoadNode("n0", 9.96, 76.24), RoadNode("n1", 9.961, 76.24), RoadNode("n2", 9.962, 76.24))
    edges = (
        RoadEdge("e1", "n0", "n1", "w1", "residential", None, 500.0, 30.0, 1.0),
        RoadEdge("e2", "n1", "n2", "w1", "residential", None, 500.0, 30.0, 1.0),
    )
    graph = RoadGraph(
        graph_version="stub", graph_fingerprint="f" * 64, location="stub", coordinate_reference="EPSG:4326",
        topology_source="stub", nodes=nodes, edges=edges,
        zone_node_map={"Z-01": "n0"}, shelter_node_map={"S-01": "n2"},
    )
    world = get_world_config("v4-medium-dt2-v1")
    params = CertParams()
    candidate = Candidate("Z-01", "S-01", 20, ("e1", "e2"), 0)
    return graph, world, params, candidate


def _ledger(capacity=100, occupancy=50, pending=()):
    from src.certify.ledger_view import LedgerView

    return LedgerView(
        timestep=0, capacity_total={"S-01": capacity}, occupancy={"S-01": occupancy},
        reserved={"S-01": sum(p for _, s, p, _ in pending if s == "S-01")},
        pending=tuple(pending), occupancy_sigma={"S-01": 0.0}, occupancy_age_s={"S-01": 0.0},
    )


def _run(setup, future, ledger=None, candidate=None):
    from src.certify.rollout import rollout_joint

    graph, world, params, default = setup
    return rollout_joint(candidate or default, future, ledger or _ledger(), world, params, graph)


def test_all_conditions_hold(setup):
    from src.certify.rollout import Outcome

    result = _run(setup, StubFuture())
    assert result.z is True and result.outcome is Outcome.OK
    assert result.arrival_timestep == 4
    assert result.utility == pytest.approx(20.0)


def test_edge_closed_before_entry_strands(setup):
    from src.certify.rollout import Outcome

    result = _run(setup, StubFuture(closed=[("e2", 3)]))
    assert result.z is False and result.outcome is Outcome.STRANDED and result.path_ok is False
    assert result.utility == pytest.approx(-20.0)


def test_edge_closing_after_the_group_passed_is_harmless(setup):
    assert _run(setup, StubFuture(closed=[("e1", 3), ("e2", 4)])).z is True


def test_shelter_unsafe_exactly_at_arrival(setup):
    from src.certify.rollout import Outcome

    unsafe = _run(setup, StubFuture(severity={("S-01", 4): 0.75}))
    assert unsafe.outcome is Outcome.UNSAFE and unsafe.utility == pytest.approx(-30.0)
    later = _run(setup, StubFuture(severity={("S-01", 6): 0.95}))
    assert later.z is True
    closed = _run(setup, StubFuture(status={("S-01", 4): "CLOSED"}))
    assert closed.outcome is Outcome.UNSAFE


def test_capacity_with_walk_ins_and_pending(setup):
    from src.certify.rollout import Outcome

    assert _run(setup, StubFuture(), _ledger(capacity=100, occupancy=90)).outcome is Outcome.OVERFLOW
    assert _run(setup, StubFuture(), _ledger(capacity=120, occupancy=90)).z is True
    walk = StubFuture(walk_ins={("S-01", 2): 8, ("S-01", 4): 7})
    overflow = _run(setup, walk, _ledger(capacity=120, occupancy=90))
    assert overflow.outcome is Outcome.OVERFLOW and overflow.utility == pytest.approx(-10.0)
    # Seats committed to other groups count regardless of when those groups arrive.
    for arrival in (3, 9):
        tight = _ledger(capacity=120, occupancy=90, pending=[("G-1", "S-01", 15, arrival)])
        roomy = _ledger(capacity=120, occupancy=80, pending=[("G-1", "S-01", 15, arrival)])
        assert _run(setup, StubFuture(), tight).outcome is Outcome.OVERFLOW
        assert _run(setup, StubFuture(), roomy).z is True


def test_rollouts_do_not_interact(setup):
    from src.certify.rollout import Candidate

    future = StubFuture(walk_ins={("S-01", 3): 5})
    other = Candidate("Z-01", "S-01", 15, ("e1", "e2"), 0)
    alone = _run(setup, future)
    _run(setup, future, candidate=other)
    assert _run(setup, future) == alone


def test_components_read_three_different_futures(setup):
    from src.certify.rollout import Outcome, rollout_components

    graph, world, params, candidate = setup
    good, bad_shelter = StubFuture(), StubFuture(severity={("S-01", 4): 0.9})
    mixed = rollout_components(candidate, good, bad_shelter, good, _ledger(), world, params, graph)
    assert mixed.outcome is Outcome.UNSAFE
    clean = rollout_components(candidate, good, good, good, _ledger(), world, params, graph)
    assert clean.z is True


def test_joint_sees_coupled_failure_that_marginals_miss(setup):
    """Futures where path failure and shelter failure never coincide with full capacity.

    Each marginal is 0.96, the product is ~0.885 — but here failures are disjoint, so the
    joint is 0.92. A product-of-marginals rule and the joint rule disagree; rollout_joint
    must report the joint frequency exactly.
    """
    futures = (
        [StubFuture(closed=[("e2", 3)]) for _ in range(4)]
        + [StubFuture(severity={("S-01", 4): 0.9}) for _ in range(4)]
        + [StubFuture() for _ in range(92)]
    )
    joint = sum(_run(setup, f).z for f in futures) / len(futures)
    assert joint == pytest.approx(0.92)
