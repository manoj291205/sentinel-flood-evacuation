"""Phase 2 tests for the immutable Sentinel-Agent V3 scenario contract."""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.constraints.generate import load_scenario as load_v1_scenario
from src.sim.schemas import (
    ProvenanceClass,
    ScenarioV3,
    ScenarioValidationError,
    dump_v3_scenario,
    load_v3_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "scenarios_v3" / "example_v3_scenario.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(EXAMPLE.read_text())


def test_minimal_example_loads():
    scenario = load_v3_scenario(EXAMPLE)
    assert scenario.schema_version == "3.0"
    assert len(scenario.zones) == 2
    assert len(scenario.shelters) == 2
    assert len(scenario.network.routes) == 4


def test_json_round_trip_preserves_semantics(tmp_path):
    scenario = load_v3_scenario(EXAMPLE)
    output = tmp_path / "roundtrip.json"
    dump_v3_scenario(scenario, output)
    assert load_v3_scenario(output) == scenario


@pytest.mark.parametrize(
    ("collection", "id_field"),
    [("zones", "zone_id"), ("shelters", "shelter_id")],
)
def test_duplicate_entity_id_rejected(raw, collection, id_field):
    raw[collection][1][id_field] = raw[collection][0][id_field]
    with pytest.raises(ScenarioValidationError, match="duplicate"):
        ScenarioV3.from_dict(raw)


def test_duplicate_route_id_rejected(raw):
    raw["network"]["routes"][1]["route_id"] = raw["network"]["routes"][0]["route_id"]
    with pytest.raises(ScenarioValidationError, match="duplicate"):
        ScenarioV3.from_dict(raw)


def test_bad_zone_reference_rejected(raw):
    raw["network"]["routes"][0]["source_zone_id"] = "Z-UNKNOWN"
    with pytest.raises(ScenarioValidationError, match="unknown zone"):
        ScenarioV3.from_dict(raw)


def test_bad_shelter_reference_rejected(raw):
    raw["network"]["routes"][0]["destination_shelter_id"] = "S-UNKNOWN"
    with pytest.raises(ScenarioValidationError, match="unknown shelter"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("field", ["population_total", "population_initial_remaining"])
def test_negative_population_rejected(raw, field):
    raw["zones"][0][field] = -1
    with pytest.raises(ScenarioValidationError, match=field):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("field", ["vulnerable_population", "medical_priority_population"])
def test_subgroup_larger_than_total_rejected(raw, field):
    raw["zones"][0][field] = raw["zones"][0]["population_total"] + 1
    with pytest.raises(ScenarioValidationError, match=field):
        ScenarioV3.from_dict(raw)


def test_vulnerability_and_medical_groups_may_overlap(raw):
    total = raw["zones"][0]["population_total"]
    raw["zones"][0]["vulnerable_population"] = total
    raw["zones"][0]["medical_priority_population"] = total
    scenario = ScenarioV3.from_dict(raw)
    assert scenario.zones[0].vulnerable_population + scenario.zones[0].medical_priority_population > total


def test_initial_population_remaining_may_not_exceed_total(raw):
    raw["zones"][0]["population_initial_remaining"] += 1
    with pytest.raises(ScenarioValidationError, match="population_initial_remaining"):
        ScenarioV3.from_dict(raw)


def test_occupancy_over_capacity_rejected(raw):
    raw["shelters"][0]["occupancy_initial"] = raw["shelters"][0]["capacity_total"] + 1
    with pytest.raises(ScenarioValidationError, match="occupancy_initial"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize(
    ("collection", "value"),
    [("zones", -0.01), ("zones", 1.01), ("shelters", -0.01), ("shelters", 1.01)],
)
def test_entity_severity_outside_unit_interval_rejected(raw, collection, value):
    raw[collection][0]["initial_flood_severity"] = value
    with pytest.raises(ScenarioValidationError, match="initial_flood_severity"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_invalid_closure_probability_rejected(raw, value):
    route = next(route for route in raw["network"]["routes"] if route["reachable"])
    route["base_closure_probability"] = value
    with pytest.raises(ScenarioValidationError, match="base_closure_probability"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("value", [0, -1])
def test_reachable_route_requires_positive_travel_mean(raw, value):
    route = next(route for route in raw["network"]["routes"] if route["reachable"])
    route["travel_time_mean"] = value
    with pytest.raises(ScenarioValidationError, match="travel_time_mean"):
        ScenarioV3.from_dict(raw)


def test_route_travel_standard_deviation_cannot_be_negative(raw):
    route = next(route for route in raw["network"]["routes"] if route["reachable"])
    route["travel_time_std"] = -0.1
    with pytest.raises(ScenarioValidationError, match="travel_time_std"):
        ScenarioV3.from_dict(raw)


def test_valid_unreachable_route_uses_null_metrics(raw):
    scenario = ScenarioV3.from_dict(raw)
    route = next(route for route in scenario.network.routes if not route.reachable)
    assert route.travel_time_mean is None
    assert route.travel_time_std is None
    assert route.base_closure_probability is None


def test_unreachable_route_rejects_fake_sentinel_metrics(raw):
    route = next(route for route in raw["network"]["routes"] if not route["reachable"])
    route["travel_time_mean"] = 999999
    with pytest.raises(ScenarioValidationError, match="must use null"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("value", [1, 0])
def test_invalid_horizon_rejected(raw, value):
    raw["time"]["horizon_steps"] = value
    with pytest.raises(ScenarioValidationError, match="horizon_steps"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("value", [0, -10])
def test_invalid_timestep_rejected(raw, value):
    raw["time"]["timestep_minutes"] = value
    with pytest.raises(ScenarioValidationError, match="timestep_minutes"):
        ScenarioV3.from_dict(raw)


def test_unsupported_schema_version_rejected(raw):
    raw["schema_version"] = "4.0"
    with pytest.raises(ScenarioValidationError, match="unsupported version"):
        ScenarioV3.from_dict(raw)


def test_negative_root_seed_rejected(raw):
    raw["seed"] = -1
    with pytest.raises(ScenarioValidationError, match="seed"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize("collection", ["zones", "shelters"])
def test_scenario_requires_zone_and_shelter(raw, collection):
    raw[collection] = []
    with pytest.raises(ScenarioValidationError, match=collection):
        ScenarioV3.from_dict(raw)


def test_v1_json_is_not_silently_interpreted_as_v3():
    with pytest.raises(ScenarioValidationError, match="unsupported version"):
        load_v3_scenario(ROOT / "data" / "scenario.json")


def test_canonical_ordering_is_deterministic_and_non_mutating(raw):
    original = copy.deepcopy(raw)
    scenario = ScenarioV3.from_dict(raw)
    assert [zone.zone_id for zone in scenario.canonical_zones] == ["Z1", "Z2"]
    assert [shelter.shelter_id for shelter in scenario.canonical_shelters] == ["S1", "S2"]
    assert [
        (route.source_zone_id, route.destination_shelter_id)
        for route in scenario.canonical_routes
    ] == [("Z1", "S1"), ("Z1", "S2"), ("Z2", "S1"), ("Z2", "S2")]
    assert raw == original


def test_capacity_available_is_derived_not_serialized():
    scenario = load_v3_scenario(EXAMPLE)
    shelter = scenario.canonical_shelters[0]
    assert shelter.capacity_initial_available == shelter.capacity_total - shelter.occupancy_initial
    assert "capacity_remaining" not in scenario.to_dict()["shelters"][0]


def test_scenario_definition_is_frozen():
    scenario = load_v3_scenario(EXAMPLE)
    with pytest.raises(FrozenInstanceError):
        scenario.seed = 7  # type: ignore[misc]
    assert isinstance(scenario.zones, tuple)
    assert isinstance(scenario.network.routes, tuple)


def test_serialized_contract_has_no_mutable_runtime_state():
    data = load_v3_scenario(EXAMPLE).to_dict()
    encoded = json.dumps(data)
    for field in (
        "people_in_transit",
        "capacity_reserved",
        "current_road_closures",
        "current_timestep",
        "pending_arrivals",
    ):
        assert field not in encoded


def test_fixture_is_prominently_labeled_synthetic(raw):
    label = raw["provenance"]["scenario_origin"]
    assert label["classification"] == ProvenanceClass.SIMULATED.value
    assert "NOT REAL FLOOD OR SHELTER DATA" in label["description"]


def test_all_provenance_classes_are_supported(raw):
    component = raw["provenance"]["scenario_origin"]
    for classification in ProvenanceClass:
        component["classification"] = classification.value
        assert ScenarioV3.from_dict(copy.deepcopy(raw)).provenance.scenario_origin.classification is classification


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_accessibility_score_must_be_normalized(raw, value):
    raw["shelters"][0]["accessibility_score"] = value
    with pytest.raises(ScenarioValidationError, match="accessibility_score"):
        ScenarioV3.from_dict(raw)


def test_invalid_shelter_status_rejected(raw):
    raw["shelters"][0]["status"] = "operational"
    with pytest.raises(ScenarioValidationError, match="status"):
        ScenarioV3.from_dict(raw)


def test_graph_node_location_is_supported(raw):
    location = raw["zones"][0]["location"]
    location["kind"] = "GRAPH_NODE"
    location["node_id"] = "123456789"
    assert ScenarioV3.from_dict(raw).zones[0].location.node_id == "123456789"


def test_coordinate_location_is_supported_without_inventing_fixture_coordinates(raw):
    location = raw["zones"][0]["location"]
    location.update({"kind": "COORDINATES", "node_id": None, "latitude": 10.0, "longitude": 76.0})
    parsed = ScenarioV3.from_dict(raw).zones[0].location
    assert (parsed.latitude, parsed.longitude) == (10.0, 76.0)


def test_partial_coordinate_location_rejected(raw):
    location = raw["zones"][0]["location"]
    location.update({"kind": "COORDINATES", "node_id": None, "latitude": 10.0, "longitude": None})
    with pytest.raises(ScenarioValidationError, match="require latitude and longitude"):
        ScenarioV3.from_dict(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [("vehicle_count", -1), ("vehicle_capacity", 0), ("dispatches_per_timestep", 0)],
)
def test_enabled_fleet_requires_meaningful_values(raw, field, value):
    raw["fleet"][field] = value
    with pytest.raises(ScenarioValidationError, match=field):
        ScenarioV3.from_dict(raw)


def test_deferred_stochastic_parameters_must_remain_null(raw):
    raw["stochastic_model"]["regional_shock_std"] = 0.2
    with pytest.raises(ScenarioValidationError, match="must remain null"):
        ScenarioV3.from_dict(raw)


def test_configured_stochastic_interface_accepts_valid_typed_values(raw):
    raw["stochastic_model"].update(
        {
            "parameter_status": "CONFIGURED",
            "regional_shock_std": 0.1,
            "local_noise_std": 0.05,
            "shock_persistence": 0.5,
            "travel_noise_std": 2.0,
            "closure_hazard_coefficient": 0.3,
            "shelter_degradation_probability": 0.02,
        }
    )
    config = ScenarioV3.from_dict(raw).stochastic_model
    assert config.regional_shock_std == 0.1


def test_v1_loader_and_contract_remain_unchanged():
    scenario = load_v1_scenario()
    assert scenario["schema_version"] == 1
    assert scenario["scenario_id"] == "flood-evac-demo-01"
