"""Lane S unit test: restricting futures to an edge subset is bit-identical per edge."""

import pytest

pytestmark = pytest.mark.milestone("P22")


def test_edge_subset_matches_full_graph():
    from src.certify.forecast import forecast_from_state, ledger_hash
    from src.certify.futures import FutureSet, root_key
    from src.geospatial.v4_runtime import build_v4_runtime

    scenario, sim, graph, overlay, world = build_v4_runtime("v4-medium-dt2-v1")
    sim.observe()
    state = sim.prepared_state_for_debug()
    fc = forecast_from_state(state, overlay.road_state, scenario)
    root = root_key(incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
                    graph_fingerprint=graph.graph_fingerprint, ledger_hash=ledger_hash(state),
                    params_id="v4-cert-v1")
    subset = tuple(e.edge_id for e in graph.edges[:60])
    full = FutureSet(fc, graph, world, root, horizon_steps=5)
    part = FutureSet(fc, graph, world, root, horizon_steps=5, edge_ids=subset)
    assert part.edge_set_digest() != "ALL" and full.edge_set_digest() == "ALL"
    for k in (1, 2, 3):
        a, b = full.future(k), part.future(k)
        for t in range(fc.timestep + 1, fc.timestep + 6):
            for e in subset:
                assert a.edge_open(e, t) == b.edge_open(e, t)
                assert a.edge_hazard(e, t) == b.edge_hazard(e, t)
            for s in state.shelters:
                assert a.walk_ins(s.shelter_id, t) == b.walk_ins(s.shelter_id, t)
    with pytest.raises(KeyError):
        part.future(1).edge_open(graph.edges[100].edge_id, fc.timestep + 1)
