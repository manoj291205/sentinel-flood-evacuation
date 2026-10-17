"""Phase 35-lite acceptance tests (Lead) — seat escrow during a simulated network outage. Do not edit; escalate instead.

Spec: specs/V4_ESCROW_LITE_SPEC.md. Exploratory, not pre-registered. The safety property: with escrow, the offline
reservations of the two teams never exceed the seats that were free at the cut, at any shelter, in any seeded outage.
Property tests use fast fake futures (every rollout OK), which makes both teams want the same seats — the hard case.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.milestone("P35L")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "contracts"
RESULT = ROOT / "data" / "eval_results" / "phase35lite" / "outages.json"
WORLD = "v4-medium-dt2-v1"
SEEDS = range(1_080_000, 1_080_060)  # property seeds (not the study seeds)


def _schema(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


class _Futures:
    def __init__(self, forecast, graph, world, root, horizon_steps, edge_ids=None, **kwargs):
        self.root = root
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        return k


def _ok(c, k, ledger, world, params, graph, extra_terms=()):
    from src.certify.rollout import Outcome, RolloutResult

    return RolloutResult(True, Outcome.OK, 3, float(c.people), True, True, True, None)


@pytest.fixture(scope="module")
def graph():
    from src.geospatial import load_road_graph

    return load_road_graph()


@pytest.fixture(scope="module")
def reports(graph):
    from src.escrow.outage import simulate_outage

    out = {}
    for seed in SEEDS:
        for mode in ("escrow", "last_known"):
            out[seed, mode] = simulate_outage(seed, WORLD, 1 + seed % 3, 2, mode, futures_factory=_Futures,
                                              rollout=_ok, graph=graph)
    return out


def test_shares_never_exceed_free_seats():
    from src.escrow.shares import split_shares

    rng = random.Random(35)
    for _ in range(500):
        free = {f"S{i}": rng.randint(0, 120) for i in range(1, rng.randint(2, 7))}
        weights = {"TEAM-A": rng.choice([0.0, rng.random() * 500]), "TEAM-B": rng.choice([0.0, rng.random() * 500])}
        shares = split_shares(free, weights)
        assert set(shares) == {"TEAM-A", "TEAM-B"}
        for s, seats in free.items():
            parts = [shares[t][s] for t in shares]
            assert all(isinstance(p, int) and p >= 0 for p in parts)
            assert sum(parts) <= seats


def test_adapter_shows_only_the_team_seats_and_refuses_more(graph):
    from src.certify.ledger import LedgerConflict, SimLedgerAdapter
    from src.escrow.ledger import EscrowLedgerAdapter
    from src.geospatial.v4_runtime import build_v4_runtime

    _, sim, _, _, _ = build_v4_runtime(WORLD, generator_seed=620003, graph=graph)
    sim.observe()
    base = SimLedgerAdapter(sim)
    cut = base.view()
    seats = {s: 5 for s in cut.capacity_total}
    adapter = EscrowLedgerAdapter(base, "TEAM-A", cut_view=cut, seats=seats)
    view = adapter.view()
    for s in cut.capacity_total:
        assert view.capacity_total[s] - view.occupancy[s] - view.reserved[s] == 5
    shelter = next(iter(seats))
    with pytest.raises(LedgerConflict):
        with adapter.transaction() as tx:
            tx.reserve(shelter, 6, "CERT-000001")
    assert sim.prepared_state_for_debug().current_timestep == cut.timestep  # nothing executed offline


def test_with_escrow_no_outage_ever_overbooks(reports):
    for (seed, mode), r in reports.items():
        if mode != "escrow":
            continue
        assert r.overbooked_seats == 0 and r.overbooked is False, seed
        for s, free in r.free_at_cut.items():
            assert r.reserved_offline.get(s, 0) <= free, (seed, s)
            for team, by_shelter in r.reserved_by_team.items():
                assert by_shelter.get(s, 0) <= r.seats[team].get(s, 0), (seed, team, s)
            assert sum(r.seats[t].get(s, 0) for t in r.seats) <= free, (seed, s)


def test_without_escrow_the_last_known_count_can_overbook(reports):
    overbooked = [seed for (seed, mode), r in reports.items() if mode == "last_known" and r.overbooked]
    assert overbooked, "the comparison mode never overbooked in 60 outages"
    for (seed, mode), r in reports.items():
        if mode == "last_known":
            expected = sum(max(0, r.reserved_offline.get(s, 0) - f) for s, f in r.free_at_cut.items())
            assert r.overbooked_seats == expected and r.overbooked == (expected > 0)


def test_rebalance_returns_every_unused_seat(reports):
    for (seed, mode), r in reports.items():
        if mode != "escrow":
            continue
        shared = sum(sum(by_shelter.values()) for by_shelter in r.seats.values())
        used = sum(r.reserved_offline.values())
        assert r.returned_to_pool == shared - used, seed
        assert shared <= sum(r.free_at_cut.values())


def test_held_dispatches_carry_a_reason_and_a_suggestion(reports):
    blocked = [b for (seed, mode), r in reports.items() if mode == "escrow" for b in r.blocked]
    assert blocked, "no dispatch was ever held for exceeding a share"
    for b in blocked:
        assert b["people"] > b["seats_left"]
        assert "seats" in b["reason"] and b["suggested"]
    assert all(not r.blocked for (seed, mode), r in reports.items() if mode == "last_known")


def test_offline_certificates_validate_and_replay(reports, graph):
    from src.certify.certificate import CertificateInputs, validate_certificate
    from src.certify.replay import replay_certificate

    checked = 0
    for (seed, mode), r in list(reports.items())[:8]:
        for item in r.certificates:
            cert = item["certificate"]
            validate_certificate(cert)
            report = replay_certificate(cert, CertificateInputs.from_dict(item["inputs"]), graph=graph,
                                        futures_factory=_Futures, rollout=_ok)
            assert report.result == "MATCH", (seed, mode, cert["cert_id"], report.mismatched_fields)
            checked += 1
    assert checked


def test_escrow_api_flow(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.app import create_app

    monkeypatch.setenv("SENTINEL_DEMO_SOURCE", "FIXTURE")
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    schema = _schema("escrow_status.schema.json")
    with TestClient(create_app()) as client:
        assert client.post("/api/escrow/sessions", json={"seed": 620003, "regime": "v3-medium-v1",
                                                         "mode": "escrow"}).status_code == 422
        status = client.post("/api/escrow/sessions", json={"seed": 620003, "regime": WORLD, "mode": "escrow"}).json()
        jsonschema.validate(status, schema)
        sid = status["session_id"]
        assert status["network"] == "ONLINE" and status["label"] is None and status["teams"] == []
        assert client.post(f"/api/escrow/sessions/{sid}/restore").status_code == 409
        cut = client.post(f"/api/escrow/sessions/{sid}/cut").json()
        jsonschema.validate(cut, schema)
        assert cut["network"] == "OFFLINE" and cut["label"] == "Simulated network outage"
        assert [t["team"] for t in cut["teams"]] == ["TEAM-A", "TEAM-B"]
        assert all(t["seats_left"] == t["seats_total"] for t in cut["teams"])
        assert client.post(f"/api/escrow/sessions/{sid}/cut").status_code == 409
        offline = client.post(f"/api/escrow/sessions/{sid}/step").json()
        jsonschema.validate(offline, schema)
        assert all(t["seats_left"] <= t["seats_total"] for t in offline["teams"])
        restored = client.post(f"/api/escrow/sessions/{sid}/restore").json()
        jsonschema.validate(restored, schema)
        assert restored["network"] == "ONLINE" and restored["last_reconciliation"]["overbooked_seats"] == 0
        assert client.get(f"/api/escrow/sessions/{sid}").json()["network"] == "ONLINE"


def test_result_file_is_valid_consistent_and_in_the_manifest():
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    jsonschema.validate(data, _schema("phase35lite_result.schema.json"))
    rows, totals = data["rows"], data["totals"]
    assert totals["outages"] == len({r["seed"] for r in rows}) == 40
    for mode, key in (("escrow", "overbooked_outages_escrow"), ("last_known", "overbooked_outages_last_known")):
        assert totals[key] == sum(r["overbooked"] for r in rows if r["mode"] == mode)
    assert totals["overbooked_seats_escrow"] == sum(r["overbooked_seats"] for r in rows if r["mode"] == "escrow") == 0
    assert totals["overbooked_seats_last_known"] == sum(r["overbooked_seats"] for r in rows if r["mode"] == "last_known")
    assert totals["blocked_escrow"] == sum(r["blocked"] for r in rows if r["mode"] == "escrow")
    for r in rows:
        assert r["cut_step"] == 2 + r["seed"] % 5
        assert r["overbooked"] == (r["overbooked_seats"] > 0)
    manifest = {i["id"]: i for i in _schema("evidence_manifest.json")["items"]}
    for item_id, key in (("p35lite-outages", "outages"), ("p35lite-overbooked-escrow", "overbooked_outages_escrow"),
                         ("p35lite-overbooked-last-known", "overbooked_outages_last_known")):
        assert manifest[item_id]["path"] == "data/eval_results/phase35lite/outages.json"
        assert manifest[item_id]["json_pointer"] == f"/totals/{key}"


def test_texts_are_honest(reports):
    policy = _schema("claims_policy.json")
    banned = [re.compile(p, re.I) for p in policy["banned_outcome_patterns"]]
    texts = [b["reason"] for r in reports.values() for b in r.blocked]
    texts.append(_schema("escrow_status.schema.json")["properties"]["note"]["const"])
    for text in texts:
        assert not any(b.search(text) for b in banned), text
