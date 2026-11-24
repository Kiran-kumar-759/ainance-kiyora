import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import BankingConnection, BankingSyncRun


class BankingRepository:
    """Repository for simulated banking connections and synchronization audit runs."""

    def create_connection(self, db: Session, conn: BankingConnection) -> BankingConnection:
        db.add(conn)
        db.flush()
        return conn

    def get_connection_by_id(
        self, db: Session, connection_id: uuid.UUID, user_id: uuid.UUID
    ) -> BankingConnection | None:
        stmt = select(BankingConnection).where(
            BankingConnection.id == connection_id,
            BankingConnection.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_connection_by_provider(
        self, db: Session, user_id: uuid.UUID, provider_id: str
    ) -> BankingConnection | None:
        stmt = select(BankingConnection).where(
            BankingConnection.user_id == user_id,
            BankingConnection.provider_id == provider_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_connections(self, db: Session, user_id: uuid.UUID) -> list[BankingConnection]:
        stmt = (
            select(BankingConnection)
            .where(BankingConnection.user_id == user_id)
            .order_by(BankingConnection.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    def update_connection(self, db: Session, conn: BankingConnection) -> BankingConnection:
        db.add(conn)
        db.flush()
        return conn

    def create_sync_run(self, db: Session, run: BankingSyncRun) -> BankingSyncRun:
        db.add(run)
        db.flush()
        return run

    def update_sync_run(self, db: Session, run: BankingSyncRun) -> BankingSyncRun:
        db.add(run)
        db.flush()
        return run

    def list_sync_runs(
        self, db: Session, connection_id: uuid.UUID, user_id: uuid.UUID, limit: int = 10
    ) -> list[BankingSyncRun]:
        stmt = (
            select(BankingSyncRun)
            .where(
                BankingSyncRun.connection_id == connection_id,
                BankingSyncRun.user_id == user_id,
            )
            .order_by(BankingSyncRun.started_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())
