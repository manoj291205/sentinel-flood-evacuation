"""Phase 22 acceptance tests (Lead) — keyed future generator. Do not edit; escalate instead."""

from __future__ import annotations

import inspect
import math
from dataclasses import replace

import pytest
from hypothesis import given, settings, strategies as st

pytestmark = pytest.mark.milestone("P22")

ROOT_ARGS = dict(
    incident_id="KOCHI-SIM-620000",
    forecast_hash="a" * 64,
    graph_fingerprint="b" * 64,
    ledger_hash="c" * 64,
    params_id="v4-cert-v1",
)


@pytest.fixture(scope="module")
def runtime():
    from src.geospatial.road_network import load_road_graph
    from src.geospatial.v4_runtime import build_v4_runtime

    graph = load_road_graph()
    scenario, simulator, graph, overlay, world = build_v4_runtime("v4-medium-dt2-v1", graph=graph)
    simulator.observe()
    return scenario, simulator, graph, overlay, world


def _future_set(runtime, horizon=8):
    from src.certify.forecast import forecast_from_state, ledger_hash
    from src.certify.futures import FutureSet, root_key

    scenario, simulator, graph, overlay, world = runtime
    state = simulator.prepared_state_for_debug()
    forecast = forecast_from_state(state, overlay.road_state, scenario)
    root = root_key(
        incident_id=forecast.incident_id,
        forecast_hash=forecast.forecast_hash(),
        graph_fingerprint=graph.graph_fingerprint,
        ledger_hash=ledger_hash(state),
        params_id="v4-cert-v1",
    )
    return FutureSet(forecast, graph, world, root, horizon_steps=horizon), forecast, state


def _signature(traj, graph, state, steps):
    edges = [edge.edge_id for edge in graph.edges[:40]]
    rows = []
    for t in range(traj.start_timestep + 1, traj.start_timestep + steps + 1):
        rows.append(tuple(traj.edge_open(e, t) for e in edges))
        rows.append(tuple(round(traj.edge_hazard(e, t), 12) for e in edges))
        for shelter in state.shelters:
            rows.append((
                round(traj.shelter_severity(shelter.shelter_id, t), 12),
                traj.shelter_status(shelter.shelter_id, t),
                traj.walk_ins(shelter.shelter_id, t),
            ))
    return tuple(rows)


def test_root_key_is_deterministic_and_sensitive():
    from src.certify.futures import root_key

    base = root_key(**ROOT_ARGS)
    assert base == root_key(**ROOT_ARGS)
    assert len(base) == 64 and int(base, 16) >= 0
    for field in ROOT_ARGS:
        changed = dict(ROOT_ARGS, **{field: ROOT_ARGS[field] + "x"})
        assert root_key(**changed) != base, field
    assert root_key(**ROOT_ARGS, backend="philox") != base


@settings(max_examples=60, deadline=None)
@given(
    keys=st.lists(
        st.tuples(st.integers(0, 60), st.sampled_from(["Z-01", "S-04", "e-17", "e-903"])),
        min_size=1, max_size=12,
    ),
    k=st.integers(1, 4096),
)
def test_future_streams_are_order_invariant(keys, k):
    from src.certify.futures import FutureStreams
    from src.sim.randomness import RandomStream

    forward = FutureStreams("d" * 64, k, "v4-medium-dt2-v1-unc")
    backward = FutureStreams("d" * 64, k, "v4-medium-dt2-v1-unc")
    a = {key: forward.uniform(RandomStream.ROUTE_CLOSURE, *key) for key in keys}
    b = {key: backward.uniform(RandomStream.ROUTE_CLOSURE, *key) for key in reversed(keys)}
    assert a == b
    assert all(0.0 <= value < 1.0 for value in a.values())
    assert all(math.isfinite(forward.normal(RandomStream.TRAVEL, *key)) for key in keys)


def test_future_streams_differ_by_index_and_duck_type():
    from src.certify.futures import FutureStreams
    from src.sim.randomness import RandomStream

    one = FutureStreams("d" * 64, 1, "cfg")
    two = FutureStreams("d" * 64, 2, "cfg")
    assert one.uniform(RandomStream.LOCAL_HAZARD, 5, "Z-01") != two.uniform(RandomStream.LOCAL_HAZARD, 5, "Z-01")
    for attribute in ("root_seed", "config_id", "replication_id", "uniform", "normal"):
        assert hasattr(one, attribute)
    with pytest.raises(ValueError):
        FutureStreams("d" * 64, 0, "cfg")


def test_existing_dynamics_accept_future_streams(runtime):
    from src.certify.futures import FutureStreams
    from src.geospatial.road_network import derive_road_state
    from src.sim.hazard import evolve_flood_state

    scenario, simulator, graph, _, _ = runtime
    state = simulator.prepared_state_for_debug()
    streams = FutureStreams("e" * 64, 7, simulator.config.config_id)
    advanced = replace(state, current_timestep=state.current_timestep + 1)
    evolved, shock, _ = evolve_flood_state(scenario, advanced, simulator.config, streams, 0.0)
    assert math.isfinite(shock) and len(evolved.zones) == len(state.zones)
    road, _ = derive_road_state(graph, evolved, simulator.config, scenario_seed=scenario.seed, streams=streams)
    assert len(road.edges) == len(graph.edges)


def test_future_set_replays_bit_exactly(runtime):
    scenario, _, graph, _, _ = runtime
    first, _, state = _future_set(runtime)
    second, _, _ = _future_set(runtime)
    for k in (1, 2, 17, 64):
        assert _signature(first.future(k), graph, state, 8) == _signature(second.future(k), graph, state, 8)
    assert _signature(first.future(1), graph, state, 8) != _signature(first.future(2), graph, state, 8)
    assert first.A_MAX == len(scenario.zones) * len(scenario.shelters) + 1
    with pytest.raises(ValueError):
        first.future(0)


def test_future_values_do_not_depend_on_access_order(runtime):
    _, _, graph, _, _ = runtime
    warm, _, state = _future_set(runtime)
    for k in range(1, 6):
        warm.future(k)
    cold, _, _ = _future_set(runtime)
    assert _signature(warm.future(5), graph, state, 6) == _signature(cold.future(5), graph, state, 6)


def test_no_simulator_internals_reach_the_future_set():
    from src.certify.futures import FutureSet

    names = set(inspect.signature(FutureSet.__init__).parameters)
    assert not names & {"simulator", "streams", "context", "scenario_seed", "replication_id"}


def test_forecast_hash_tracks_observations(runtime):
    _, forecast, _ = _future_set(runtime)
    same = replace(forecast)
    assert same.forecast_hash() == forecast.forecast_hash()
    zone_id, severity = forecast.zone_severity[0]
    bumped = replace(forecast, zone_severity=((zone_id, severity + 0.01),) + forecast.zone_severity[1:])
    assert bumped.forecast_hash() != forecast.forecast_hash()
