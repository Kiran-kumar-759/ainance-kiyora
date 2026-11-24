from sqlalchemy import create_engine

from app.core.config import settings
from app.db.session import check_db_readiness


def test_real_postgres_connection_success():
    """Directly tests check_db_readiness with the real PostgreSQL test database."""
    test_engine = create_engine(settings.TEST_DATABASE_URL)
    result = check_db_readiness(custom_engine=test_engine)

    assert result["ready"] is True
    assert result["status"] == "connected"
    assert result["database_name"] in ["pfm_test", "pfm_dev"]
    assert result["latency_ms"] >= 0
    assert result["error"] is None
    test_engine.dispose()


def test_postgres_connection_failure_handling():
    """Directly tests check_db_readiness when connecting to an unreachable port."""
    bad_engine = create_engine(
        "postgresql+psycopg://user:pass@127.0.0.1:54339/nonexistent",
        connect_args={"connect_timeout": 1},
    )
    result = check_db_readiness(custom_engine=bad_engine)

    assert result["ready"] is False
    assert result["status"] in ["disconnected", "error"]
    assert result["database_name"] is None
    assert result["error"] is not None
    bad_engine.dispose()
