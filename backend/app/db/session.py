import logging
import time
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# Engine configuration with connection pooling and pre-ping
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency injection providing a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_readiness(custom_engine=None) -> dict[str, Any]:
    """
    Executes a real lightweight PostgreSQL query to verify database readiness.
    Calculates query round-trip latency and returns sanitized status information.
    """
    target_engine = custom_engine or engine
    start_time = time.perf_counter()
    try:
        with target_engine.connect() as connection:
            result = connection.execute(text("SELECT 1 AS ready, current_database() AS db_name;"))
            row = result.fetchone()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            db_name = row[1] if row and len(row) > 1 else "unknown"

            return {
                "ready": True,
                "status": "connected",
                "database_name": db_name,
                "latency_ms": latency_ms,
                "error": None,
            }
    except SQLAlchemyError as err:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("PostgreSQL readiness check failed: %s", str(err))
        return {
            "ready": False,
            "status": "disconnected",
            "database_name": None,
            "latency_ms": latency_ms,
            "error": "Database service is unavailable or unreachable",
        }
    except Exception as err:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Unexpected error during database readiness check: %s", str(err))
        return {
            "ready": False,
            "status": "error",
            "database_name": None,
            "latency_ms": latency_ms,
            "error": "Unexpected database connection error",
        }
