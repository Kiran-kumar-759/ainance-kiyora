import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.api import api_router
from app.api.routes import health
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import check_db_readiness, engine
from app.services.bills.scheduler import reminder_scheduler
from app.services.documents.worker import document_ocr_worker

# Initialize logging
setup_logging(debug=settings.DEBUG)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown hooks."""
    logger.info("Starting %s in %s mode...", settings.APP_NAME, settings.ENVIRONMENT)
    # Check database readiness on startup
    db_check = check_db_readiness()
    if db_check["ready"]:
        logger.info(
            "PostgreSQL connected successfully. Catalog: %s (latency: %sms)",
            db_check["database_name"],
            db_check["latency_ms"],
        )
    else:
        logger.warning(
            "Initial PostgreSQL readiness check failed: %s (will retry on readiness probes)",
            db_check.get("error"),
        )
    reminder_scheduler.start()
    document_ocr_worker.start()
    yield
    await document_ocr_worker.stop()
    await reminder_scheduler.stop()
    logger.info("Shutting down %s...", settings.APP_NAME)
    engine.dispose()
    logger.info("Database engine connections closed.")


def create_application() -> FastAPI:
    """Application factory configuring middleware, exception handlers, and routing."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Phase 0: Product Foundation + Functional Demo UI (India-first SaaS)",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Safe error handling
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled server exception at %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
                "path": request.url.path,
            },
        )

    # Health probes at root level
    app.include_router(health.router)

    # Versioned API routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
