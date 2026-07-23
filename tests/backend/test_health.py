"""Backend foundation smoke tests."""

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_endpoint_reports_foundation_readiness() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "standalone-production-inspection-backend",
        "version": "0.1.0",
    }
