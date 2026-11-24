import json

from pydantic import Field, field_validator
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
