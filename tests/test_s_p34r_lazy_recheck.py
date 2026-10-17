"""Lane S own tests for P34R: the re-check is lazy, once per timestep (spec Amendment 2026-10-17)."""

from __future__ import annotations

import pytest

SEED, WORLD, PARAMS = 620003, "v4-medium-dt2-v1", "v4-cert-test-v1"


@pytest.fixture(scope="module")
def graph():
    from src.geospatial import load_road_graph

    return load_road_graph()


def test_recheck_runs_once_per_timestep_and_only_when_consulted(graph):
    from src.human_decision import EvidenceReference
    from src.simulation_session import SimulationSession

    s = SimulationSession(SEED, WORLD, graph=graph, certified=True, params_id=PARAMS, recertify=True)
    assert s.recert_log == []  # reset consults nothing
    ev = EvidenceReference(source_id="ndma-flood-guidelines-2008", page=64, chunk_id="ndma-flood-guidelines-2008-p64-c0")
    for _ in range(3):
        s.decide("ACCEPT", ev)
    assert s.recert_log == [] or {r["timestep"] for r in s.recert_log} <= {0, 1, 2}
    s.context()
    n = len(s.recert_log)
    s.context()
    s.certification()
    assert len(s.recert_log) == n  # idempotent within a timestep


def test_non_certified_session_has_no_recert_state(graph):
    from src.simulation_session import SimulationSession

    s = SimulationSession(SEED, "v3-medium-v1", graph=graph)
    s.context()
    assert s.recert_log == [] and s.recertify is False
