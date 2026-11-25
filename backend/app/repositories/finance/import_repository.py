import math
import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.imports import ImportBatch, ImportMappingProfile, ImportRow


class ImportRepository:
    """Repository for statement import batches, parsed rows, and user mapping profiles."""

    def create_batch(self, db: Session, batch: ImportBatch) -> ImportBatch:
        db.add(batch)
        db.flush()
        return batch

    def get_batch(self, db: Session, batch_id: uuid.UUID, user_id: uuid.UUID) -> ImportBatch | None:
        stmt = (
            select(ImportBatch)
            .options(joinedload(ImportBatch.account))
            .where(ImportBatch.id == batch_id, ImportBatch.user_id == user_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_batch_for_update(
        self, db: Session, batch_id: uuid.UUID, user_id: uuid.UUID
    ) -> ImportBatch | None:
        stmt = (
            select(ImportBatch)
            .where(ImportBatch.id == batch_id, ImportBatch.user_id == user_id)
            .with_for_update()
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_batches(self, db: Session, user_id: uuid.UUID, limit: int = 100) -> list[ImportBatch]:
        stmt = (
            select(ImportBatch)
            .options(joinedload(ImportBatch.account))
            .where(ImportBatch.user_id == user_id)
            .order_by(ImportBatch.created_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def update_batch(self, db: Session, batch: ImportBatch) -> ImportBatch:
        db.add(batch)
        db.flush()
        return batch

    def delete_batch(self, db: Session, batch: ImportBatch) -> None:
        db.delete(batch)
        db.flush()

    def replace_rows_for_batch(
        self, db: Session, batch_id: uuid.UUID, rows: list[ImportRow]
    ) -> list[ImportRow]:
        db.execute(delete(ImportRow).where(ImportRow.import_batch_id == batch_id))
        db.flush()
        if rows:
            db.add_all(rows)
            db.flush()
        return rows

    def list_all_rows(self, db: Session, batch_id: uuid.UUID) -> list[ImportRow]:
        stmt = (
            select(ImportRow)
            .options(joinedload(ImportRow.category))
            .where(ImportRow.import_batch_id == batch_id)
            .order_by(ImportRow.source_row_number.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def get_row(
        self, db: Session, batch_id: uuid.UUID, row_id: uuid.UUID, user_id: uuid.UUID
    ) -> ImportRow | None:
        stmt = (
            select(ImportRow)
            .join(ImportBatch, ImportRow.import_batch_id == ImportBatch.id)
            .options(joinedload(ImportRow.category))
            .where(
                ImportRow.id == row_id,
                ImportRow.import_batch_id == batch_id,
                ImportBatch.user_id == user_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_rows(
        self,
        db: Session,
        batch_id: uuid.UUID,
        status_filter: str | None = None,
        duplicate_only: bool = False,
        search: str | None = None,
        sort_by: str = "row_asc",
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[ImportRow], int, int]:
        base = select(ImportRow).where(ImportRow.import_batch_id == batch_id)

        if status_filter:
            base = base.where(ImportRow.validation_status == status_filter)
        if duplicate_only:
            base = base.where(
                ImportRow.validation_status.in_(["duplicate", "potential_duplicate"])
            )
        if search and search.strip():
            pat = f"%{search.strip()}%"
            base = base.where(
                or_(
                    ImportRow.normalized_description.ilike(pat),
                    ImportRow.normalized_merchant.ilike(pat),
                    ImportRow.transaction_reference.ilike(pat),
                )
            )

        total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        if sort_by == "date_desc":
            order_clause = [ImportRow.normalized_date.desc().nullslast(), ImportRow.source_row_number.asc()]
        elif sort_by == "date_asc":
            order_clause = [ImportRow.normalized_date.asc().nullslast(), ImportRow.source_row_number.asc()]
        elif sort_by == "amount_desc":
            order_clause = [ImportRow.normalized_amount.desc().nullslast(), ImportRow.source_row_number.asc()]
        elif sort_by == "amount_asc":
            order_clause = [ImportRow.normalized_amount.asc().nullslast(), ImportRow.source_row_number.asc()]
        else:
            order_clause = [ImportRow.source_row_number.asc()]

        offset = max(0, (page - 1) * page_size)
        query = (
            base.options(joinedload(ImportRow.category))
            .order_by(*order_clause)
            .offset(offset)
            .limit(page_size)
        )
        items = list(db.execute(query).scalars().all())
        return items, total, total_pages

    def list_mapping_profiles(
        self, db: Session, user_id: uuid.UUID, file_format: str | None = None
    ) -> list[ImportMappingProfile]:
        stmt = select(ImportMappingProfile).where(ImportMappingProfile.user_id == user_id)
        if file_format:
            stmt = stmt.where(ImportMappingProfile.file_format == file_format)
        stmt = stmt.order_by(ImportMappingProfile.updated_at.desc())
        return list(db.execute(stmt).scalars().all())

    def upsert_mapping_profile(
        self,
        db: Session,
        user_id: uuid.UUID,
        profile_name: str,
        file_format: str,
        mapping_configuration: dict,
    ) -> ImportMappingProfile:
        stmt = select(ImportMappingProfile).where(
            ImportMappingProfile.user_id == user_id,
            func.lower(ImportMappingProfile.profile_name) == profile_name.strip().lower(),
            ImportMappingProfile.file_format == file_format,
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            existing.mapping_configuration = mapping_configuration
            db.add(existing)
            db.flush()
            return existing
        prof = ImportMappingProfile(
            user_id=user_id,
            profile_name=profile_name.strip(),
            file_format=file_format,
            mapping_configuration=mapping_configuration,
        )
        db.add(prof)
        db.flush()
        return prof
