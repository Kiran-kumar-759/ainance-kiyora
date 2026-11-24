from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories.system_repository import SystemRepository


def test_system_info_endpoint(client: TestClient):
    """System info endpoint returns India-first metadata and database status."""
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()
    assert data["target_market"] == "India"
    assert data["primary_currency"] == "INR"
    assert data["fiscal_year_cycle"] == "April - March"
    assert data["database_connected"] is True
    assert data["settings_count"] >= 1


def test_system_settings_persistence(client: TestClient, db_session: Session):
    """Verifies that system configuration records are read from PostgreSQL."""
    repo = SystemRepository()
    repo.upsert_setting(
        db_session,
        key="test_compliance_key",
        value={"rbi_compliant": True, "data_residency": "India"},
        description="RBI and data residency compliance config",
    )

    response = client.get("/api/v1/system/settings")
    assert response.status_code == 200
    settings_list = response.json()
    keys = [item["key"] for item in settings_list]
    assert "test_compliance_key" in keys
