"""Bounded synthetic flood evolution and observable one-step forecasts."""

from __future__ import annotations

from dataclasses import replace

from .configs import UncertaintyConfig
from .events import AuditEventType, AuditRecord
from .randomness import EpisodeRandomStreams, RandomStream
from .schemas import ScenarioV3, Trend
from .state import EpisodeState, ShelterState, ZoneState


def clip_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def trend_drift(trend: Trend, config: UncertaintyConfig) -> float:
    """Phase 4 interpretation: trend supplies direction, config supplies magnitude."""
    if trend is Trend.RISING:
        return config.hazard_drift_scale
    if trend is Trend.FALLING:
        return -config.hazard_drift_scale
    return 0.0


def evolve_flood_state(
    scenario: ScenarioV3,
    state: EpisodeState,
    config: UncertaintyConfig,
    streams: EpisodeRandomStreams,
    previous_regional_shock: float,
) -> tuple[EpisodeState, float, tuple[AuditRecord, ...]]:
    """Apply the timestep's regional AR(1) innovation plus entity-local noise."""
    timestep = state.current_timestep
    innovation = config.regional_hazard_sigma * streams.normal(
        RandomStream.REGIONAL_HAZARD, timestep
    )
    regional_shock = (
        config.regional_hazard_persistence * previous_regional_shock + innovation
    )
    definitions = {zone.zone_id: zone for zone in scenario.zones}
    records: list[AuditRecord] = []
    zones: list[ZoneState] = []
    for zone in state.zones:
        local_noise = config.local_hazard_sigma * streams.normal(
            RandomStream.LOCAL_HAZARD, timestep, "zone", zone.zone_id
        )
        updated = clip_unit(
            zone.flood_severity_current
            + trend_drift(definitions[zone.zone_id].initial_severity_trend, config)
            + regional_shock
            + local_noise
        )
        zones.append(
            replace(
                zone,
                flood_severity_previous=zone.flood_severity_current,
                flood_severity_current=updated,
                observed_severity_change=updated - zone.flood_severity_current,
            )
        )
        records.append(
            AuditRecord(
                event_type=AuditEventType.FLOOD_STATE_UPDATED,
                timestep=timestep,
                zone_id=zone.zone_id,
                entity_kind="ZONE",
                uncertainty_config_id=config.config_id,
                value_before=zone.flood_severity_current,
                value_after=updated,
                uncertainty=config.forecast_std_next,
                reason_code="SYNTHETIC_HAZARD_UPDATE",
                message="bounded regional-plus-local synthetic severity update",
            )
        )

    shelters: list[ShelterState] = []
    for shelter in state.shelters:
        local_noise = config.local_hazard_sigma * streams.normal(
            RandomStream.LOCAL_HAZARD, timestep, "shelter", shelter.shelter_id
        )
        updated = clip_unit(
            shelter.flood_severity_current + regional_shock + local_noise
        )
        shelters.append(
            replace(
                shelter,
                flood_severity_previous=shelter.flood_severity_current,
                flood_severity_current=updated,
                observed_severity_change=updated - shelter.flood_severity_current,
            )
        )
        records.append(
            AuditRecord(
                event_type=AuditEventType.FLOOD_STATE_UPDATED,
                timestep=timestep,
                shelter_id=shelter.shelter_id,
                entity_kind="SHELTER",
                uncertainty_config_id=config.config_id,
                value_before=shelter.flood_severity_current,
                value_after=updated,
                uncertainty=config.forecast_std_next,
                reason_code="SYNTHETIC_HAZARD_UPDATE",
                message="bounded regional-plus-local synthetic severity update",
            )
        )
    return (
        replace(state, zones=tuple(zones), shelters=tuple(shelters)),
        regional_shock,
        tuple(records),
    )


def update_observable_forecasts(
    scenario: ScenarioV3,
    state: EpisodeState,
    config: UncertaintyConfig,
) -> EpisodeState:
    """Compute imperfect t+1 forecasts from observable current/past values only."""
    definitions = {zone.zone_id: zone for zone in scenario.zones}
    zones = tuple(
        replace(
            zone,
            forecast_mean_next=clip_unit(
                zone.flood_severity_current
                + (
                    zone.observed_severity_change
                    if zone.flood_severity_previous is not None
                    else trend_drift(
                        definitions[zone.zone_id].initial_severity_trend, config
                    )
                )
            ),
            forecast_std_next=config.forecast_std_next,
        )
        for zone in state.zones
    )
    shelters = tuple(
        replace(
            shelter,
            forecast_mean_next=clip_unit(
                shelter.flood_severity_current
                + (
                    shelter.observed_severity_change
                    if shelter.flood_severity_previous is not None
                    else 0.0
                )
            ),
            forecast_std_next=config.forecast_std_next,
        )
        for shelter in state.shelters
    )
    return replace(
        state,
        zones=zones,
        shelters=shelters,
        forecast_for_timestep=state.current_timestep + 1,
    )
