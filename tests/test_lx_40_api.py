"""Phase 40 live decision subjects come from the current simulator state."""

from fastapi.testclient import TestClient

from src.api.app import create_app


def test_certified_context_adds_subject_without_changing_existing_keys():
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"seed": 620003,
                                                "regime": "v4-medium-dt2-v1",
                                                "certified": True,
                                                "params_id": "v4-cert-test-v1"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    legacy = client.get(f"/api/sessions/{session_id}/context")
    assert legacy.status_code == 200
    assert "subject" not in legacy.json()["certified"]["recommendation"]
    assert all("subject" not in row for row in legacy.json()["certified"]["alternatives"])
    response = client.get(f"/api/sessions/{session_id}/context?include_subject=true")
    assert response.status_code == 200
    certified = response.json()["certified"]
    assert {"timestep", "threshold", "futures_used", "looks", "recommendation",
            "why", "candidates", "alternatives", "rechecks", "note"} <= set(certified)
    assert {"action_key", "label", "verdict", "lower", "upper", "successes", "n",
            "outcome_counts"} <= set(certified["recommendation"])
    fields = {"action_key", "kind", "people", "zone_id", "zone_name", "zone_waiting",
              "zone_flood_severity", "shelter_id", "shelter_name",
              "shelter_seats_free_before", "shelter_seats_free_after", "route_label",
              "route_length_km", "eta_minutes", "closed_edges_on_route"}
    assert fields <= set(certified["recommendation"]["subject"])
    assert certified["recommendation"]["subject"]["kind"] == "HOLD"
    assert certified["recommendation"]["subject"]["people"] is None
    assert certified["alternatives"]
    assert all(fields <= set(item["subject"]) for item in certified["alternatives"])
    plain = response.json()
    plain["certified"]["recommendation"].pop("subject")
    for item in plain["certified"]["alternatives"]:
        item.pop("subject")
    assert plain == legacy.json()
    state = client.get(f"/api/sessions/{session_id}/state").json()
    for item in certified["alternatives"]:
        subject = item["subject"]
        zone = next(row for row in state["zones"] if row["zone_id"] == subject["zone_id"])
        shelter = next(row for row in state["shelters"] if row["shelter_id"] == subject["shelter_id"])
        assert subject["zone_waiting"] == zone["population_remaining"]
        assert subject["shelter_seats_free_before"] == shelter["capacity_available"]
        assert subject["shelter_seats_free_after"] == shelter["capacity_available"] - subject["people"]
