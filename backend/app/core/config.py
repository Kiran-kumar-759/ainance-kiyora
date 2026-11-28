import json
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), str(_BACKEND_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "AI Personal Finance Manager"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-production-123456789"

    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://tenderpilot:tenderpilot@localhost:5432/pfm_dev",
        description="SQLAlchemy PostgreSQL connection string",
    )
    TEST_DATABASE_URL: str = Field(
        default="postgresql+psycopg://tenderpilot:tenderpilot@localhost:5432/pfm_test",
        description="SQLAlchemy PostgreSQL test connection string",
    )

    # Database Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_PRE_PING: bool = True

    # CORS & Host Security
    CORS_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    ALLOWED_HOSTS: list[str] | str = []

    # Background tasks & shared rate limiting
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    RATE_LIMIT_USE_VALKEY: bool = True

    # Authentication & Session Settings (Phase 1)
    SESSION_COOKIE_NAME: str = "pfm_session"
    SESSION_EXPIRY_SECONDS: int = 60 * 60 * 24 * 7  # 7 days
    COOKIE_SECURE: bool = False  # Set to True in production HTTPS
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str | None = None
    CSRF_COOKIE_NAME: str = "pfm_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # Token Lifespans
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # Frontend URL & Email Delivery (Phase 1)
    FRONTEND_URL: str = "http://localhost:5173"
    EMAILS_FROM_EMAIL: str = "support@personalfinancemanager.in"
    EMAILS_FROM_NAME: str = "AI Personal Finance Manager"
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_TLS: bool = False
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    TRUSTED_PROXIES: list[str] = ["127.0.0.1", "::1"]

    # Rate Limiting
    RATE_LIMIT_LOGIN_MAX: int = 10  # Max per minute
    RATE_LIMIT_REGISTER_MAX: int = 5  # Max per minute

    # Bank Statement Imports & Private Storage (Phase 3)
    IMPORT_STORAGE_DIR: str = "uploads/statements"
    IMPORT_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    IMPORT_MAX_ROWS_PER_FILE: int = 5000
    IMPORT_FILE_RETENTION_DAYS: int = 30

    # Bills, Payments, Reminders & Private Document Storage (Phase 5)
    BILL_DUE_SOON_DAYS: int = 5
    BILL_STORAGE_DIR: str = "uploads/bills"
    BILL_MAX_DOC_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    REMINDER_SCHEDULER_ENABLED: bool = True
    REMINDER_SCHEDULER_INTERVAL_SECONDS: int = 60
    REMINDER_DEFAULT_HOUR_IST: int = 9

    # SMS Provider Adapter Settings (Phase 5 - optional external credentials)
    SMS_ENABLED: bool = False
    SMS_PROVIDER: str = "none"  # none, webhook
    SMS_API_KEY: str | None = None
    SMS_SENDER_ID: str | None = None
    SMS_WEBHOOK_URL: str | None = None

    # Document Management, OCR & Email/SMS Ingestion (Phase 7)
    DOCUMENT_STORAGE_DIR: str = "uploads/documents"
    DOCUMENT_MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    DOCUMENT_MAX_PDF_PAGES: int = 20
    OCR_ENGINE: str = "rapidocr"  # rapidocr (local CPU PaddleOCR-ONNX) or paddleocr
    OCR_USE_ANGLE_CLS: bool = True
    OCR_WORKER_ENABLED: bool = True
    OCR_WORKER_INTERVAL_SECONDS: int = 15
    OCR_WORKER_MAX_CONCURRENT: int = 2
    OCR_JOB_MAX_ATTEMPTS: int = 3
    DOCUMENT_UPLOAD_RATE_LIMIT_MAX: int = 30  # Max uploads/processes per minute

    # Gmail OAuth 2.0 & Email Ingestion (Phase 7)
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://127.0.0.1:8000/api/v1/email/gmail/callback"
    GOOGLE_ALLOWED_REDIRECT_URIS: list[str] = [
        "http://127.0.0.1:8000/api/v1/email/gmail/callback",
        "http://localhost:8000/api/v1/email/gmail/callback",
        "http://localhost:5173/email/gmail/callback",
    ]
    GMAIL_SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
    EMAIL_TOKEN_ENCRYPTION_KEY: str | None = None
    EMAIL_SYNC_DEFAULT_QUERY: str = (
        "(bill OR invoice OR receipt OR statement OR electricity OR broadband "
        "OR recharge OR premium OR emi OR payment) newer_than:90d"
    )
    EMAIL_SYNC_MAX_MESSAGES: int = 25

    # Banking / Account Aggregator Provider Settings
    ACCOUNT_AGGREGATOR_ENABLED: bool = False

    # Incoming SMS Ingestion Boundary (Phase 7 - disabled unless supported source configured)
    SMS_INGESTION_ENABLED: bool = False
    SMS_INGESTION_PROVIDER: str = "none"

    # AI Expense Intelligence & Optional Groq Integration (Phase 8)
    AI_WORKER_ENABLED: bool = True
    AI_WORKER_INTERVAL_SECONDS: int = 20
    GROQ_ENABLED: bool = False
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: float = 8.0
    GROQ_MAX_RETRIES: int = 1

    # Web Research Providers & AI Assistant (Phase 10)
    LANGSEARCH_API_KEY: str | None = None
    FIRECRAWL_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
    DEFAULT_WEB_RESEARCH_PROVIDER: str = "tavily"
    WEB_RESEARCH_TIMEOUT_SECONDS: float = 12.0
    WEB_RESEARCH_MAX_RESULTS: int = 5
    WEB_RESEARCH_MAX_SCRAPES: int = 2
    WEB_RESEARCH_MAX_CONTENT_CHARS: int = 4000
    ASSISTANT_MAX_CONTEXT_MESSAGES: int = 12

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return []
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    return [str(i).strip() for i in json.loads(raw) if str(i).strip()]
                except Exception:
                    pass
            return [i.strip() for i in raw.split(",") if i.strip()]
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return []

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Ensures production configuration enforces HTTPS cookies, strong secrets, and safe CORS."""
        if self.ENVIRONMENT.lower() == "production":
            if not self.COOKIE_SECURE:
                self.COOKIE_SECURE = True
            if (
                self.SECRET_KEY == "dev-insecure-secret-key-change-in-production-123456789"
                or len(self.SECRET_KEY.strip()) < 32
            ):
                raise ValueError(
                    "In production, SECRET_KEY must be configured with a strong secret (>= 32 chars)."
                )
            if isinstance(self.CORS_ORIGINS, list) and "*" in self.CORS_ORIGINS:
                raise ValueError("In production, wildcard '*' is forbidden in CORS_ORIGINS.")
        return self

    @property
    def safe_database_url(self) -> str:
        """Returns database URL with password masked for safe diagnostics."""
        try:
            from sqlalchemy.engine import make_url

            url = make_url(self.DATABASE_URL)
            return url.render_as_string(hide_password=True)
        except Exception:
            return "postgresql://***:***@masked/pfm_dev"


settings = Settings()
