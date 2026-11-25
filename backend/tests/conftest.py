import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set environment before loading application
os.environ["ENVIRONMENT"] = "test"
os.environ["GROQ_ENABLED"] = "false"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://tenderpilot:tenderpilot@localhost:5432/pfm_test",
)

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_application

# Use the real PostgreSQL test database
test_engine = create_engine(
    settings.TEST_DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database():
    """Ensure all tables exist on the real PostgreSQL test database."""
    Base.metadata.create_all(bind=test_engine)
    yield
    # Cleanup after test session
    # Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a transactional database session for each test that rolls back."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient that uses the real PostgreSQL test database session."""
    app = create_application()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
