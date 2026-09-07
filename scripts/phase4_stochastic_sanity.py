"""Generate the Phase 4 stochastic-process sanity artifact (no policy benchmark)."""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import replace
from pathlib import Path

from src.sim.configs import HIGH, LOW, MEDIUM, MODELING_ASSUMPTION_DISCLAIMER
from src.sim.events import WAIT, AuditEventType
from src.sim.randomness import EpisodeRandomStreams
from src.sim.routes import realize_dispatch_travel
from src.sim.schemas import ShelterStatus, load_v3_scenario
from src.sim.stochastic import StochasticSimulator

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "data" / "scenarios_v3" / "example_v3_scenario.json"
OUTPUT_PATH = ROOT / "data" / "eval_v3" / "phase4_stochastic_sanity.json"
SEEDS = tuple(range(41000, 41200))


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _has_mechanical_option(state) -> bool:
    for route in state.routes:
        zone = state.zone(route.source_zone_id)
        shelter = state.shelter(route.destination_shelter_id)
        if (
            route.reachable_current
            and zone is not None
            and zone.population_remaining > 0
            and shelter is not None
            and shelter.status_current is not ShelterStatus.CLOSED
            and shelter.capacity_available > 0
        ):
            return True
    return False


def summarize(config) -> dict:
    template = load_v3_scenario(SCENARIO_PATH)
    absolute_changes: list[float] = []
    travel_ratios: list[float] = []
    clipped = 0
    hazard_updates = 0
    routes_closed = 0
    shelters_restricted = 0
    shelters_closed = 0
    episodes_with_option = 0
    actionable_timesteps = 0
    observed_timesteps = 0
    reachable_per_episode = sum(route.reachable for route in template.network.routes)
    shelters_per_episode = len(template.shelters)

    for seed in SEEDS:
        scenario = replace(template, seed=seed)
        simulator = StochasticSimulator(scenario, config)
        streams = EpisodeRandomStreams(seed, config.config_id)
        episode_had_option = False
        while not simulator.state.terminal:
            simulator.observe()
            state = simulator.prepared_state_for_debug()
            observed_timesteps += 1
            if _has_mechanical_option(state):
                actionable_timesteps += 1
                episode_had_option = True
            definitions = {
                route.route_id: route for route in scenario.network.routes
            }
            for route in state.routes:
                if route.base_travel_time_minutes is None:
                    continue
                realization = realize_dispatch_travel(
                    definitions[route.route_id],
                    route,
                    config,
                    streams,
                    departure_timestep=state.current_timestep,
                    event_id=f"sanity-{state.current_timestep:02d}-{route.route_id}",
                )
                travel_ratios.append(
                    realization.realized_minutes / realization.base_minutes
                )
            result = simulator.step(WAIT)
            for record in result.audit_records:
                if record.event_type is AuditEventType.FLOOD_STATE_UPDATED:
                    assert record.value_before is not None and record.value_after is not None
                    absolute_changes.append(abs(record.value_after - record.value_before))
                    hazard_updates += 1
                    clipped += int(record.value_after in (0.0, 1.0))
                elif record.event_type is AuditEventType.ROUTE_CLOSED:
                    routes_closed += 1
                elif record.event_type is AuditEventType.SHELTER_RESTRICTED:
                    shelters_restricted += 1
                elif record.event_type is AuditEventType.SHELTER_CLOSED:
                    shelters_closed += 1
        episodes_with_option += int(episode_had_option)

    return {
        "config_id": config.config_id,
        "uncertainty_config": config.to_dict(),
        "number_of_episodes": len(SEEDS),
        "mean_absolute_severity_change": statistics.fmean(absolute_changes),
        "severity_clipping_frequency": clipped / hazard_updates,
        "fraction_reachable_routes_ever_closed": routes_closed
        / (len(SEEDS) * reachable_per_episode),
        "shelter_restriction_transitions_per_shelter_episode": shelters_restricted
        / (len(SEEDS) * shelters_per_episode),
        "shelter_closure_transitions_per_shelter_episode": shelters_closed
        / (len(SEEDS) * shelters_per_episode),
        "mean_realized_to_base_travel_ratio": statistics.fmean(travel_ratios),
        "travel_ratio_standard_deviation": statistics.stdev(travel_ratios),
        "travel_ratio_p10": _quantile(travel_ratios, 0.10),
        "travel_ratio_p50": _quantile(travel_ratios, 0.50),
        "travel_ratio_p90": _quantile(travel_ratios, 0.90),
        "episodes_with_at_least_one_mechanical_option": episodes_with_option
        / len(SEEDS),
        "mechanically_actionable_timestep_fraction": actionable_timesteps
        / observed_timesteps,
    }


def main() -> None:
    payload = {
        "artifact_type": "PHASE_4_STOCHASTIC_PROCESS_SANITY_NOT_POLICY_EVALUATION",
        "generated_date": "2026-09-07",
        "scenario": str(SCENARIO_PATH.relative_to(ROOT)),
        "seed_generation": "consecutive integers 41000 through 41199 inclusive",
        "seeds": list(SEEDS),
        "actions": (
            "WAIT at every timestep; potential keyed travel sampled for process "
            "diagnostics only"
        ),
        "disclaimer": MODELING_ASSUMPTION_DISCLAIMER,
        "configs": [summarize(config) for config in (LOW, MEDIUM, HIGH)],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
