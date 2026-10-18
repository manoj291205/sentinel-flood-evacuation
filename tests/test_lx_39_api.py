"""Phase 39 read-only artifact views and route projection."""

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.library import library_index, library_trace
from src.geospatial import load_road_graph


def test_library_index_is_deduplicated_and_source_labelled():
    index = library_index()
    keys = {(row["system"], row["regime"], row["seed"]) for row in index["runs"]}
    assert len(keys) == len(index["runs"]) == 1260
    assert sum(row["has_trace"] for row in index["runs"]) == 180
    assert all(row["source_path"].startswith("data/eval_results/phase27/runs/") for row in index["runs"])
    assert index["analysis"]["bars"]["bar1"]["pass"] is False
    assert TestClient(create_app()).get("/api/library/index").status_code == 200


def test_trace_routes_follow_graph_edges_and_reject_unknown_paths():
    graph = load_road_graph()
    trace = library_trace("v4-medium-dt2-v1", 1_050_000, graph)
    assert trace["steps"]
    assert trace["source_path"].endswith("v4-medium-dt2-v1_1050000.jsonl.gz")
    step = trace["steps"][0]
    assert step["candidates"][0]["svg_path"].startswith("M")
    assert len(step["candidates"]) == 16
    assert step["shelters"][0]["capacity"] >= step["shelters"][0]["occupied"]
    client = TestClient(create_app())
    assert client.get("/api/library/trace/../../etc/0").status_code != 200
    assert client.get("/api/library/trace/v4-medium-dt2-v1/0").status_code == 404


def test_facts_and_v3_views_have_sources():
    client = TestClient(create_app())
    facts = client.get("/api/project/facts").json()["facts"]
    assert facts["tests"]["value"] is not None
    assert facts["recorded_runs"]["value"] == 1260
    assert facts["corpus_chunks"]["source_path"] == "data/eval_v3/phase11_corpus_summary.json"
    v3 = client.get("/api/library/v3").json()
    assert v3["items"]["heldout"]["source_path"].startswith("data/eval_v3/")
    assert v3["curves"]["rows"]
    comparison = client.get("/api/escrow/comparison").json()
    assert comparison["totals"]["overbooked_seats_escrow"] == 0
    assert comparison["source_path"] == "data/eval_results/phase35lite/outages.json"


def test_live_stranded_is_additive_to_the_original_kpi_shape():
    client = TestClient(create_app())
    created = client.post("/api/sessions", json={"seed": 620003, "regime": "v4-medium-dt2-v1",
                                                 "certified": True, "params_id": "v4-cert-test-v1"})
    assert created.status_code == 200
    state = client.get(f"/api/sessions/{created.json()['session_id']}/state").json()
    assert state["people_stranded"] >= 0
    assert set(state["kpis"]) == {"waiting", "in_transit", "safe", "certificates_issued"}
