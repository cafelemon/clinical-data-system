from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clinical-data-system"}


def test_version() -> None:
    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0.1.0"}

