import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.email_ingestion import (
    EmailAttachmentRecord,
    EmailConnection,
    EmailDocumentCandidate,
    EmailMessageRecord,
    EmailSyncHistory,
)


class EmailIngestionRepository:
    def get_connection(
        self, db: Session, user_id: uuid.UUID, provider: str = "gmail"
    ) -> EmailConnection | None:
        return db.execute(
            select(EmailConnection).where(
                EmailConnection.user_id == user_id,
                EmailConnection.provider == provider,
            )
        ).scalar_one_or_none()

    def get_or_create_connection(
        self, db: Session, user_id: uuid.UUID, provider: str = "gmail"
    ) -> EmailConnection:
        conn = self.get_connection(db, user_id, provider)
        if not conn:
            conn = EmailConnection(user_id=user_id, provider=provider, status="disconnected")
            db.add(conn)
            db.flush()
        return conn

    def get_message_by_provider_id(
        self, db: Session, user_id: uuid.UUID, provider_message_id: str
    ) -> EmailMessageRecord | None:
        return db.execute(
            select(EmailMessageRecord).where(
                EmailMessageRecord.user_id == user_id,
                EmailMessageRecord.provider_message_id == provider_message_id,
            )
        ).scalar_one_or_none()

    def get_attachment_by_hash(
        self, db: Session, user_id: uuid.UUID, file_hash: str
    ) -> EmailAttachmentRecord | None:
        return db.execute(
            select(EmailAttachmentRecord)
            .where(
                EmailAttachmentRecord.user_id == user_id,
                EmailAttachmentRecord.file_hash == file_hash,
            )
            .limit(1)
        ).scalar_one_or_none()

    def find_candidate_duplicate(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        invoice_number: str | None = None,
        merchant_name: str | None = None,
        invoice_date=None,
        amount=None,
    ) -> EmailDocumentCandidate | None:
        if invoice_number and merchant_name:
            found = db.execute(
                select(EmailDocumentCandidate)
                .where(
                    EmailDocumentCandidate.user_id == user_id,
                    EmailDocumentCandidate.invoice_number == invoice_number,
                    EmailDocumentCandidate.merchant_name == merchant_name,
                )
                .limit(1)
            ).scalar_one_or_none()
            if found:
                return found
        if merchant_name and invoice_date is not None and amount is not None:
            found = db.execute(
                select(EmailDocumentCandidate)
                .where(
                    EmailDocumentCandidate.user_id == user_id,
                    EmailDocumentCandidate.merchant_name == merchant_name,
                    EmailDocumentCandidate.invoice_date == invoice_date,
                    EmailDocumentCandidate.amount == amount,
                )
                .limit(1)
            ).scalar_one_or_none()
            if found:
                return found
        return None

    def list_sync_history(
        self, db: Session, user_id: uuid.UUID, limit: int = 20
    ) -> list[EmailSyncHistory]:
        stmt = (
            select(EmailSyncHistory)
            .where(EmailSyncHistory.user_id == user_id)
            .order_by(EmailSyncHistory.started_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def list_candidates(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        status_filter: str | None = None,
        limit: int = 50,
    ) -> list[EmailDocumentCandidate]:
        filters = [EmailDocumentCandidate.user_id == user_id]
        if status_filter:
            filters.append(EmailDocumentCandidate.status == status_filter)
        stmt = (
            select(EmailDocumentCandidate)
            .where(*filters)
            .options(
                selectinload(EmailDocumentCandidate.message).selectinload(
                    EmailMessageRecord.attachments
                ),
            )
            .order_by(EmailDocumentCandidate.created_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_candidate(
        self, db: Session, candidate_id: uuid.UUID, user_id: uuid.UUID
    ) -> EmailDocumentCandidate | None:
        stmt = (
            select(EmailDocumentCandidate)
            .where(
                EmailDocumentCandidate.id == candidate_id,
                EmailDocumentCandidate.user_id == user_id,
            )
            .options(
                selectinload(EmailDocumentCandidate.message).selectinload(
                    EmailMessageRecord.attachments
                ),
                selectinload(EmailDocumentCandidate.document),
                selectinload(EmailDocumentCandidate.attachment),
            )
        )
        return db.execute(stmt).scalar_one_or_none()
