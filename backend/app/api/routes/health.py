from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import check_db_readiness
from app.schemas.health import DatabaseReadiness, HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", response_model=HealthResponse, summary="Application Liveness Probe")
def get_liveness():
    """
    Liveness probe: reports whether the application process is running.
    Does not require external infrastructure to be ready.
    """
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        version="0.1.0",
    )


@router.get("/health/ready", response_model=ReadinessResponse, summary="Database Readiness Probe")
def get_readiness(response: Response):
    """
    Readiness probe: performs an active lightweight query to PostgreSQL.
    Returns 200 OK if PostgreSQL is connected, or 503 Service Unavailable if unreachable.
    Does not expose sensitive credentials in responses.
    """
    db_check = check_db_readiness()

    db_readiness = DatabaseReadiness(
        ready=db_check["ready"],
        status=db_check["status"],
        database_name=db_check.get("database_name"),
        latency_ms=db_check["latency_ms"],
        error=db_check.get("error"),
    )

    if not db_check["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "degraded"
    else:
        overall_status = "ready"

    return ReadinessResponse(
        status=overall_status,
        database=db_readiness,
        environment=settings.ENVIRONMENT,
    )
