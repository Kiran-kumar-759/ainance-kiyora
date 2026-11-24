from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_liveness_endpoint(client: TestClient):
    """Liveness probe must return 200 OK and report application metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data


def test_health_readiness_endpoint_real_postgres(client: TestClient):
    """Readiness probe must execute a real query on PostgreSQL and report 200 OK."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["ready"] is True
    assert data["database"]["status"] == "connected"
    assert data["database"]["database_name"] in ["pfm_test", "pfm_dev"]
    assert isinstance(data["database"]["latency_ms"], (int, float))
    assert data["database"]["latency_ms"] >= 0
    assert data["database"]["error"] is None


def test_health_readiness_database_failure_handling(client: TestClient):
    """
    Readiness probe must return 503 Service Unavailable when the database is unreachable,
    without leaking sensitive connection information.
    """
    with patch("app.api.routes.health.check_db_readiness") as mock_check:
        mock_check.return_value = {
            "ready": False,
            "status": "disconnected",
            "database_name": None,
            "latency_ms": 15.4,
            "error": "Database service is unavailable or unreachable",
        }
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"]["ready"] is False
        assert data["database"]["status"] == "disconnected"
        assert data["database"]["error"] == "Database service is unavailable or unreachable"
        # Verify no credentials leaked
        assert "password" not in response.text.lower()
        assert "tenderpilot" not in response.text.lower()
