"""Schema validation — the first defence against a fabricated constraint payload."""

from __future__ import annotations

import pytest

from src.constraints.generate import load_scenario, validate


@pytest.fixture(scope="module")
def scenario():
    return load_scenario()


def good_payload(scenario):
    return {
        "scenario_id": scenario["scenario_id"],
        "constraints": [
            {
                "action_id": s["shelter_id"],
                "status": "allowed",
                "reason": "Fine.",
                "source_document": "ndma_flood_guidelines.pdf",
                "source_excerpt": "some clause",
            }
            for s in scenario["shelters"]
        ],
    }


def test_a_wellformed_payload_passes(scenario):
    assert validate(good_payload(scenario), scenario) == []


def test_wrong_scenario_id_is_rejected(scenario):
    payload = good_payload(scenario)
    payload["scenario_id"] = "not-the-right-one"
    assert any("scenario_id" in e for e in validate(payload, scenario))


def test_missing_shelter_is_rejected(scenario):
    payload = good_payload(scenario)
    dropped = payload["constraints"].pop()["action_id"]
    errors = validate(payload, scenario)
    assert any(dropped in e for e in errors)


def test_invented_shelter_is_rejected(scenario):
    payload = good_payload(scenario)
    payload["constraints"][0]["action_id"] = "S99"
    assert any("S99" in e for e in validate(payload, scenario))


def test_duplicate_shelter_is_rejected(scenario):
    payload = good_payload(scenario)
    payload["constraints"][1]["action_id"] = payload["constraints"][0]["action_id"]
    assert any("duplicate" in e for e in validate(payload, scenario))


@pytest.mark.parametrize("status", ["maybe", "ALLOWED", "", None])
def test_bad_status_is_rejected(scenario, status):
    payload = good_payload(scenario)
    payload["constraints"][0]["status"] = status
    assert any("status" in e for e in validate(payload, scenario))


def test_unknown_source_document_is_rejected(scenario):
    """A citation naming a document we do not have is the key hallucination vector."""
    payload = good_payload(scenario)
    payload["constraints"][0]["source_document"] = "totally_made_up_guidelines.pdf"
    assert any("totally_made_up_guidelines.pdf" in e for e in validate(payload, scenario))


def test_filename_with_page_appended_is_rejected(scenario):
    """The exact failure the model produced on the first real run."""
    payload = good_payload(scenario)
    payload["constraints"][0]["source_document"] = "ndma_flood_guidelines.pdf (page 89)"
    assert validate(payload, scenario) != []


@pytest.mark.parametrize("field", ["reason", "source_excerpt"])
def test_empty_required_text_is_rejected(scenario, field):
    payload = good_payload(scenario)
    payload["constraints"][0][field] = "   "
    assert any(field in e for e in validate(payload, scenario))


def test_missing_required_field_is_reported(scenario):
    payload = good_payload(scenario)
    del payload["constraints"][0]["reason"]
    assert any("reason" in e for e in validate(payload, scenario))


@pytest.mark.parametrize("payload", [[], "a string", 42, None])
def test_non_object_payload_is_rejected(scenario, payload):
    assert validate(payload, scenario) != []


def test_constraints_must_be_a_list(scenario):
    assert validate({"scenario_id": scenario["scenario_id"], "constraints": {}}, scenario) != []
