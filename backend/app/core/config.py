import json

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    # CORS
    CORS_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Background tasks
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

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

    # External Provider Conventions (Future Phases 7, 8, 10 - not required in Phase 0)
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    TAVILY_API_KEY: str | None = None
    OCR_ENGINE: str = "paddleocr"

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

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Ensures production configuration cannot run with insecure cookies or default dev secret keys."""
        if self.ENVIRONMENT.lower() == "production":
            if not self.COOKIE_SECURE:
                self.COOKIE_SECURE = True
            if self.SECRET_KEY == "dev-insecure-secret-key-change-in-production-123456789":
                raise ValueError(
                    "In production, SECRET_KEY must be configured with a strong secret."
                )
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
