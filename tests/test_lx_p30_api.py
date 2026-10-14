"""Additional Lane X checks for map provenance and response boundaries."""

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.geospatial import load_road_graph


def test_map_geometry_uses_loaded_graph():
    graph = load_road_graph()
    with TestClient(create_app()) as client:
        response = client.get("/api/map/geometry")
    geometry = response.json()
    assert geometry["graph_fingerprint"] == graph.graph_fingerprint
    assert geometry["zones"] and geometry["shelters"]
    assert geometry["major"] and geometry["minor"]
    assert geometry["source"] == "LIVE"


def test_fixture_certificate_provenance_and_cors():
    with TestClient(create_app()) as client:
        certificate = client.get("/api/certificates/CERT-000127")
        allowed = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        denied = client.options(
            "/api/health",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
        )
    assert certificate.headers["X-Sentinel-Source"] == "FIXTURE"
    assert certificate.headers["X-Sentinel-Simulated"] == "true"
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert denied.headers.get("Access-Control-Allow-Origin") is None
