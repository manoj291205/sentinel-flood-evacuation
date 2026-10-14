"""Runtime builder for Phase 21 v4 worlds (finer time step, multi-step trips, edge closures)."""

from __future__ import annotations

from dataclasses import replace

from src.sim import ScenarioV3, StochasticSimulator
from src.sim.randomness import EpisodeRandomStreams
from src.sim.schemas import TimeConfig
from src.sim.world import V4WorldConfig, get_world_config, scaled_uncertainty

from .road_network import (
    GeospatialRouteOverlay,
    RoadGraph,
    _graph_scenario,
    load_road_graph,
)



def build_v4_runtime(
    world_id: str = "v4-medium-dt2-v1",
    *,
    generator_seed: int = 620000,
    graph: RoadGraph | None = None,
    replication_id: int = 0,
) -> tuple[ScenarioV3, StochasticSimulator, RoadGraph, GeospatialRouteOverlay, V4WorldConfig]:
    world = get_world_config(world_id)
    config = scaled_uncertainty(world)
    loaded = graph or load_road_graph()
    scenario = _graph_scenario(loaded, config, generator_seed)
    scenario = replace(
        scenario,
        time=TimeConfig(world.timestep_minutes, world.horizon_steps),
    )
    streams = EpisodeRandomStreams(scenario.seed, config.config_id, replication_id)
    overlay = GeospatialRouteOverlay(loaded, config, scenario.seed, streams=streams)
    simulator = StochasticSimulator(
        scenario, config, replication_id=replication_id, intervention=overlay, world=world
    )
    return scenario, simulator, loaded, overlay, world
