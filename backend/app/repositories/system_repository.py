
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.system import SystemSetting


class SystemRepository:
    """Repository handling database operations for system metadata and configuration."""

    def get_by_key(self, db: Session, key: str) -> SystemSetting | None:
        query = select(SystemSetting).where(SystemSetting.key == key)
        return db.scalars(query).first()

    def list_settings(self, db: Session, limit: int = 50, offset: int = 0) -> list[SystemSetting]:
        query = select(SystemSetting).offset(offset).limit(limit)
        return list(db.scalars(query).all())

    def upsert_setting(
        self, db: Session, key: str, value: dict, description: str | None = None
    ) -> SystemSetting:
        setting = self.get_by_key(db, key)
        if setting:
            setting.value = value
            if description is not None:
                setting.description = description
        else:
            setting = SystemSetting(key=key, value=value, description=description)
            db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

    def count_settings(self, db: Session) -> int:
        query = select(func.count(SystemSetting.id))
        return db.scalar(query) or 0
