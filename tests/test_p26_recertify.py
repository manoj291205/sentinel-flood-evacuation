"""Phase 26 acceptance tests (Lead) — in-transit re-certification and migration. Do not edit; escalate instead."""

from __future__ import annotations

import hashlib
import threading
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.milestone("P26")


def _plan():
    from src.sim.transit import TransitPlan

    return TransitPlan(
        event_id="E-1", zone_id="Z1", shelter_id="S1", people=30, departure_timestep=0,
        edge_ids=("e1", "e2", "e3"), edge_entry_minutes=(4.0, 7.0, 11.0), arrival_minutes=15.0,
        timestep_minutes=2.0,
    )


STUB_GRAPH = SimpleNamespace(
    edges_by_id={
        "e1": SimpleNamespace(edge_id="e1", u="n0", v="n1"),
        "e2": SimpleNamespace(edge_id="e2", u="n1", v="n2"),
        "e3": SimpleNamespace(edge_id="e3", u="n2", v="n3"),
    },
    zone_node_map={"Z1": "n0"},
    shelter_node_map={"S1": "n3", "S2": "n9", "S3": "n8"},
)


@pytest.mark.parametrize(
    "now, node, at, remaining",
    [(2.0, "n0", 4.0, ("e1", "e2", "e3")), (8.0, "n2", 11.0, ("e3",)), (12.0, "n3", 15.0, ())],
)
def test_group_position(now, node, at, remaining):
    from src.sim.transit import group_position

    pos = group_position(_plan(), STUB_GRAPH, now)
    assert (pos.event_id, pos.node_id, pos.at_minutes, pos.remaining_edge_ids) == ("E-1", node, at, remaining)


class FakeFutures:
    A_MAX = 21
    root = "f" * 64

    def future(self, k):
        if k < 1:
            raise ValueError
        return k


def _rollout(p_by_shelter):
    from src.certify.rollout import Outcome, RolloutResult

    def rollout(c, k, *args, **kwargs):
        u = int(hashlib.sha256(f"{c.shelter_id}|{k}".encode()).hexdigest()[:8], 16) / 2**32
        ok = u < p_by_shelter[c.shelter_id]
        return RolloutResult(z=ok, outcome=Outcome.OK if ok else Outcome.STRANDED, arrival_timestep=5,
                             utility=float(c.people if ok else -c.people), path_ok=ok,
                             shelter_ok=True if ok else None, capacity_ok=True if ok else None)

    return rollout


def _cand(shelter, start=11.0):
    from src.certify.rollout import Candidate

    return Candidate(zone_id="Z1", shelter_id=shelter, people=30, edge_ids=("e9",),
                     departure_timestep=4, start_minutes=start)


def _recert(p, alts=("S2",), history=None, timestep=4, policy=None):
    from src.certify.ledger_view import LedgerView
    from src.certify.params import CertParams
    from src.certify.recertify import GroupHistory, RecertPolicy, recertify_group

    view = LedgerView(timestep=timestep, capacity_total={}, occupancy={}, reserved={}, pending=(),
                      occupancy_sigma={}, occupancy_age_s={})
    return recertify_group(
        "E-1", _cand("S1"), tuple(_cand(s) for s in alts), FakeFutures(), view, None, CertParams(), None,
        timestep=timestep, history=history or GroupHistory(), policy=policy or RecertPolicy(),
        rollout=_rollout(p),
    )


def test_hysteresis_keeps_a_group_that_would_not_be_dispatched():
    from src.certify.certifier import Verdict, certify
    from src.certify.params import CertParams

    decision = _recert({"S1": 0.92, "S2": 0.999})
    assert decision.action == "KEEP" and decision.keep_verdict is not Verdict.INFEASIBLE
    fresh = certify([_cand("S1")], FakeFutures(), None, None, CertParams(), None, rollout=_rollout({"S1": 0.92}))
    assert "Z1->S1" not in fresh.allowed_keys()


def test_certified_failure_migrates_to_certified_alternative():
    from src.certify.certifier import Verdict

    decision = _recert({"S1": 0.50, "S2": 0.999})
    assert decision.keep_verdict is Verdict.INFEASIBLE
    assert decision.action == "MIGRATE" and decision.new_shelter_id == "S2"


def test_no_certified_alternative_keeps_and_escalates():
    decision = _recert({"S1": 0.50, "S2": 0.50})
    assert decision.action == "KEEP_ESCALATE" and decision.new_shelter_id is None


def test_never_returns_to_a_shelter_it_left():
    from src.certify.recertify import GroupHistory

    history = GroupHistory(migrations=1, last_migration_step=0, left_shelters=frozenset({"S2"}))
    decision = _recert({"S1": 0.50, "S2": 0.999, "S3": 0.50}, alts=("S2", "S3"), history=history, timestep=10)
    assert decision.action == "KEEP_ESCALATE"


def test_cooldown_and_max_migrations():
    from src.certify.recertify import GroupHistory

    recent = GroupHistory(migrations=1, last_migration_step=3, left_shelters=frozenset({"S0"}))
    assert _recert({"S1": 0.50, "S2": 0.999}, history=recent, timestep=4).action == "COOLDOWN"
    capped = GroupHistory(migrations=2, last_migration_step=0, left_shelters=frozenset({"S0", "S4"}))
    assert _recert({"S1": 0.50, "S2": 0.999}, history=capped, timestep=20).action == "COOLDOWN"


def test_migration_transaction_is_atomic():
    from src.certify.ledger import SqliteLedger

    def hook(stage):
        if stage == "after_reserve" and armed:
            raise RuntimeError("injected crash")

    armed = False
    ledger = SqliteLedger(shelters={"S1": (100, 0), "S2": (100, 0)}, fail_hook=hook)
    with ledger.transaction() as tx:
        tx.reserve("S1", 40, "CERT-000001")
    armed = True
    with pytest.raises(RuntimeError):
        with ledger.transaction() as tx:
            tx.release("S1", 40, "CERT-000002")
            tx.reserve("S2", 40, "CERT-000002")
    view = ledger.view()
    assert (view.reserved["S1"], view.reserved["S2"]) == (40, 0)


def test_burst_concurrency_never_overbooks():
    from src.certify.ledger import LedgerConflict, SqliteLedger

    ledger = SqliteLedger(shelters={"S9": (100, 10)})
    outcomes = []
    barrier = threading.Barrier(8)

    def worker(i):
        barrier.wait()
        try:
            with ledger.transaction() as tx:
                tx.reserve("S9", 30, f"CERT-{i:06d}")
            outcomes.append(True)
        except LedgerConflict:
            outcomes.append(False)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count(True) == 3
    assert ledger.view().reserved["S9"] == 90


def test_mask_delta_round_trip_and_size():
    from src.certify.mask_delta import decode_mask_delta, encode_mask_delta

    prev = {"WAIT": True, "Z1->S1": True, "Z1->S2": False, "Z2->S1": True}
    same = encode_mask_delta(prev, prev, epoch=7)
    assert len(same) == 10 and same[:4] == b"SMD1"
    assert decode_mask_delta(prev, same) == prev
    new = {"WAIT": True, "Z1->S1": False, "Z1->S2": True, "Z2->S1": True}
    payload = encode_mask_delta(prev, new, epoch=8)
    assert len(payload) == 10 + 3 * 2
    assert decode_mask_delta(prev, payload) == new
    with pytest.raises(ValueError):
        decode_mask_delta(prev, payload[:-1])
