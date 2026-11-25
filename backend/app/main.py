import logging
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.api import api_router
from app.api.routes import health
from app.core.config import Settings, settings
from app.core.logging import setup_logging
from app.db.session import check_db_readiness, engine
from app.services.ai.worker import ai_intelligence_worker
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
    ai_intelligence_worker.start()
    yield
    await ai_intelligence_worker.stop()
    await document_ocr_worker.stop()
    await reminder_scheduler.stop()
    logger.info("Shutting down %s...", settings.APP_NAME)
    engine.dispose()
    logger.info("Database engine connections closed.")


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def create_application(runtime_settings: Settings | None = None) -> FastAPI:
    """Application factory configuring security middleware, exception handlers, and routing."""
    cfg = runtime_settings or settings
    is_prod = cfg.ENVIRONMENT.lower() == "production"

    app = FastAPI(
        title=cfg.APP_NAME,
        version="1.0.0",
        description="AI Personal Finance Manager — India-first multi-user SaaS",
        openapi_url=None if is_prod else "/api/openapi.json",
        docs_url=None if is_prod else "/api/docs",
        redoc_url=None if is_prod else "/api/redoc",
        lifespan=lifespan,
    )

    if cfg.ALLOWED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(cfg.ALLOWED_HOSTS))

    # Configure CORS with explicit allowlists instead of wildcards
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def security_headers_and_request_id(request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID", "")
        request_id = incoming_id if _REQUEST_ID_RE.match(incoming_id) else uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(self), geolocation=()",
        )
        response.headers.setdefault("X-XSS-Protection", "0")
        if cfg.COOKIE_SECURE:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # Safe error handling (never leak stack traces or internal credentials)
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", None)
        logger.error(
            "Unhandled server exception [request_id=%s] at %s: %s",
            req_id or "-",
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
                "path": request.url.path,
                "request_id": req_id,
            },
        )

    # Health probes at root level
    app.include_router(health.router)

    # Versioned API routes
    app.include_router(api_router, prefix=cfg.API_V1_PREFIX)

    return app


app = create_application()
