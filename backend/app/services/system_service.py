from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import check_db_readiness
from app.repositories.system_repository import SystemRepository
from app.schemas.system import PlatformInfoResponse


class SystemService:
    """Service handling platform foundation and system settings logic."""

    def __init__(self, repository: SystemRepository | None = None):
        self.repository = repository or SystemRepository()

    def get_platform_info(self, db: Session) -> PlatformInfoResponse:
        """Returns verified system status and platform metadata."""
        db_status = check_db_readiness()
        settings_count = self.repository.count_settings(db) if db_status["ready"] else 0

        # Ensure baseline foundation metadata record exists in DB if DB is ready
        if db_status["ready"] and settings_count == 0:
            self.repository.upsert_setting(
                db,
                key="platform_baseline",
                value={
                    "phase": "Phase 0 - Product Foundation",
                    "currency": "INR",
                    "region": "India",
                    "fiscal_year": "April 1 - March 31",
                    "status": "initialized",
                },
                description="Core application foundation configuration",
            )
            settings_count = 1

        return PlatformInfoResponse(
            app_name=settings.APP_NAME,
            version="0.1.0",
            phase="Phase 0: Product Foundation + Functional Demo UI",
            target_market="India",
            primary_currency="INR",
            fiscal_year_cycle="April - March",
            environment=settings.ENVIRONMENT,
            database_connected=db_status["ready"],
            database_name=db_status.get("database_name"),
            settings_count=settings_count,
            timestamp=datetime.now(UTC),
        )
