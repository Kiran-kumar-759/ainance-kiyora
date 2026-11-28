import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.finance import BankingConnection, BankingSyncRun
from app.models.user import User
from app.providers.banking.demo_provider import (
    get_all_demo_providers,
    get_demo_provider,
)
from app.providers.banking.institution_catalog import (
    BankInstitutionEntry,
    get_bank_institution,
    list_bank_institutions,
)
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.banking_repository import BankingRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.schemas.finance.account import AccountCreateRequest, AccountResponse
from app.schemas.finance.banking import (
    BankingAccountImportRequest,
    BankingConnectionResponse,
    BankingConsentDecisionRequest,
    BankingConsentRequest,
    BankingInitiateRequest,
    BankingProviderInfo,
    BankingSyncResponse,
    BankingSyncRunResponse,
    BankInstitutionCatalogResponse,
    BankInstitutionResponse,
    DiscoveredAccountInfo,
)
from app.services.finance.account_service import AccountService
from app.services.finance.category_service import CategoryService
from app.services.finance.transaction_service import TransactionService


def _institution_to_response(entry: BankInstitutionEntry) -> BankInstitutionResponse:
    return BankInstitutionResponse(
        bank_id=entry.bank_id,
        bank_name=entry.bank_name,
        short_name=entry.short_name,
        bank_code=entry.bank_code,
        category=entry.category,
        logo_key=entry.logo_key,
        logo_url=entry.logo_url,
        supported_connection_methods=list(entry.supported_connection_methods),
        provider_id=entry.provider_id,
        provider_available=entry.provider_available,
        live_supported=entry.live_supported,
        is_demo=entry.is_demo,
        connection_availability_status=entry.connection_availability_status,
        description=entry.description,
        unavailable_reason=entry.unavailable_reason,
    )


class BankingService:
    """Service managing Indian bank catalog, consent lifecycle, account discovery, and idempotent sync."""

    def __init__(self):
        self.banking_repo = BankingRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.transaction_repo = TransactionRepository()
        self.account_service = AccountService()
        self.category_service = CategoryService()
        self.transaction_service = TransactionService()

    def list_providers(self) -> list[BankingProviderInfo]:
        return get_all_demo_providers()

    def list_institutions(
        self,
        *,
        search: str | None = None,
        method: str | None = None,
        category: str | None = None,
        include_demo: bool = True,
    ) -> BankInstitutionCatalogResponse:
        entries = list_bank_institutions(
            search=search,
            method=method,
            category=category,
            include_demo=include_demo,
        )
        return BankInstitutionCatalogResponse(
            institutions=[_institution_to_response(item) for item in entries],
            total=len(entries),
            live_aa_configured=bool(settings.ACCOUNT_AGGREGATOR_ENABLED),
            demo_available=True,
        )

    def _count_connected_accounts(
        self, db: Session, user: User, institution_name: str
    ) -> int:
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
        return sum(
            1
            for a in accounts
            if a.source == "demo_bank" and a.institution_name == institution_name
        )

    def _to_connection_response(
        self, db: Session, user: User, conn: BankingConnection
    ) -> BankingConnectionResponse:
        resp = BankingConnectionResponse.model_validate(conn)
        resp.connected_accounts_count = self._count_connected_accounts(
            db, user, conn.institution_name
        )
        return resp

    def initiate_connection(
        self, db: Session, user: User, req: BankingInitiateRequest
    ) -> BankingConnectionResponse:
        """
        Initiates or resumes a bank connection attempt after validating bank support
        and live provider availability. Never fabricates live bank connections.
        """
        institution = get_bank_institution(req.bank_id)
        if not institution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown bank institution: {req.bank_id}",
            )

        if not institution.is_demo:
            if not institution.live_supported or not settings.ACCOUNT_AGGREGATOR_ENABLED:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"Live Account Aggregator connection for {institution.bank_name} is not configured in this release. "
                        "Use CSV/XLSX bank statement import, manual account creation, or connect a labeled Demo Bank institution."
                    ),
                )

        if req.connection_method != "demo" and institution.is_demo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{institution.bank_name} only supports the 'demo' simulated connection method.",
            )

        provider = get_demo_provider(institution.provider_id)
        provider_info = provider.get_info()
        now = dt.datetime.now(dt.UTC)
        target_status = "connected" if req.consent_given else "pending"
        target_state = "accounts_discovered" if req.consent_given else "awaiting_consent"

        try:
            existing = self.banking_repo.get_connection_by_provider(
                db, user.id, institution.provider_id
            )
            if existing:
                existing.bank_id = institution.bank_id
                existing.connection_method = req.connection_method
                existing.status = target_status
                existing.lifecycle_state = target_state
                existing.last_error = None
                existing.revoked_at = None
                if req.consent_given:
                    existing.consent_granted_at = now
                self.banking_repo.update_connection(db, existing)
                db.commit()
                db.refresh(existing)
                return self._to_connection_response(db, user, existing)

            conn = BankingConnection(
                user_id=user.id,
                provider_id=institution.provider_id,
                bank_id=institution.bank_id,
                connection_method=req.connection_method,
                institution_name=provider_info.name,
                status=target_status,
                lifecycle_state=target_state,
                consent_granted_at=now,
                consent_scope="accounts,transactions",
                is_simulated=True,
            )
            self.banking_repo.create_connection(db, conn)
            db.commit()
            db.refresh(conn)
            return self._to_connection_response(db, user, conn)
        except Exception:
            db.rollback()
            raise

    def submit_consent(
        self,
        db: Session,
        user: User,
        connection_id: uuid.UUID,
        req: BankingConsentDecisionRequest,
    ) -> BankingConnectionResponse:
        """Persists user consent decision for a initiated banking connection."""
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        if conn.status == "revoked" or conn.lifecycle_state == "revoked":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Revoked banking connections must be re-initiated before granting consent.",
            )

        now = dt.datetime.now(dt.UTC)
        try:
            if req.consent_given:
                conn.status = "connected"
                conn.lifecycle_state = "accounts_discovered"
                conn.consent_granted_at = now
                conn.consent_scope = req.consent_scope
                conn.last_error = None
            else:
                conn.status = "disconnected"
                conn.lifecycle_state = "failed"
                conn.last_error = "User declined data access consent."
            self.banking_repo.update_connection(db, conn)
            db.commit()
            db.refresh(conn)
            return self._to_connection_response(db, user, conn)
        except Exception:
            db.rollback()
            raise

    def create_demo_connection(
        self, db: Session, user: User, req: BankingConsentRequest
    ) -> BankingConnectionResponse:
        if not req.consent_given:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit consent is required to initialize a simulated banking connection.",
            )

        try:
            provider = get_demo_provider(req.provider_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown banking provider: {req.provider_id}",
            )

        provider_info = provider.get_info()
        now = dt.datetime.now(dt.UTC)

        try:
            existing = self.banking_repo.get_connection_by_provider(db, user.id, req.provider_id)
            if existing:
                existing.bank_id = req.provider_id
                existing.connection_method = "demo"
                existing.status = "connected"
                existing.lifecycle_state = "connected"
                existing.last_error = None
                existing.revoked_at = None
                existing.consent_granted_at = now
                self.banking_repo.update_connection(db, existing)
                db.commit()
                db.refresh(existing)
                return self._to_connection_response(db, user, existing)

            conn = BankingConnection(
                user_id=user.id,
                provider_id=req.provider_id,
                bank_id=req.provider_id,
                connection_method="demo",
                institution_name=provider_info.name,
                status="connected",
                lifecycle_state="connected",
                consent_granted_at=now,
                consent_scope="accounts,transactions",
                is_simulated=True,
            )
            self.banking_repo.create_connection(db, conn)
            db.commit()
            db.refresh(conn)
            return self._to_connection_response(db, user, conn)
        except Exception:
            db.rollback()
            raise

    def list_user_connections(self, db: Session, user: User) -> list[BankingConnectionResponse]:
        conns = self.banking_repo.list_connections(db, user.id)
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
        res = []
        for c in conns:
            matched_count = sum(
                1
                for a in accounts
                if a.source == "demo_bank" and a.institution_name == c.institution_name
            )
            resp = BankingConnectionResponse.model_validate(c)
            resp.connected_accounts_count = matched_count
            res.append(resp)
        return res

    def get_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> BankingConnectionResponse:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        return self._to_connection_response(db, user, conn)

    def discover_accounts(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> list[DiscoveredAccountInfo]:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        if conn.status != "connected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot discover accounts until banking connection is consented and active.",
            )

        provider = get_demo_provider(conn.provider_id)
        discovered = provider.discover_accounts(str(conn.id), str(user.id))

        existing_accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
        existing_identifiers = {
            a.account_identifier
            for a in existing_accounts
            if a.source == "demo_bank" and a.institution_name == conn.institution_name
        }

        for acc in discovered:
            if acc.masked_account_number in existing_identifiers:
                acc.already_imported = True

        if conn.lifecycle_state in {"initiated", "awaiting_consent", "accounts_discovered"}:
            conn.lifecycle_state = "awaiting_account_selection"
            self.banking_repo.update_connection(db, conn)
            db.commit()

        return discovered

    def import_accounts(
        self,
        db: Session,
        user: User,
        connection_id: uuid.UUID,
        req: BankingAccountImportRequest,
    ) -> list[AccountResponse]:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        if conn.status != "connected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot import accounts from an inactive banking connection.",
            )

        provider = get_demo_provider(conn.provider_id)
        discovered = provider.discover_accounts(str(conn.id), str(user.id))
        discovered_map = {acc.external_account_id: acc for acc in discovered}

        unique_ids = list(dict.fromkeys(req.account_ids))
        for ext_id in unique_ids:
            if ext_id not in discovered_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown provider account identifier: {ext_id}",
                )

        all_institution_accounts = self.account_repo.list_demo_accounts_by_institution(
            db, user.id, conn.institution_name
        )
        accounts_by_identifier = {
            a.account_identifier: a for a in all_institution_accounts if a.account_identifier
        }

        imported: list[AccountResponse] = []
        try:
            for ext_id in unique_ids:
                acc_info = discovered_map[ext_id]
                existing_acc = accounts_by_identifier.get(acc_info.masked_account_number)
                if existing_acc:
                    if existing_acc.status != "disconnected":
                        continue
                    existing_acc.status = "active"
                    self.account_repo.update(db, existing_acc)
                    imported.append(AccountResponse.model_validate(existing_acc))
                    continue

                create_req = AccountCreateRequest(
                    name=acc_info.name,
                    account_type=acc_info.account_type,  # type: ignore[arg-type]
                    institution_name=acc_info.institution_name,
                    account_identifier=acc_info.masked_account_number,
                    currency=acc_info.currency,
                    opening_balance=acc_info.balance,
                )
                new_acc = self.account_service.create_account(
                    db=db, user=user, req=create_req, source="demo_bank", commit=False
                )
                imported.append(new_acc)

            conn.lifecycle_state = "connected"
            conn.last_error = None
            self.banking_repo.update_connection(db, conn)
            db.commit()
        except Exception:
            db.rollback()
            raise

        if req.trigger_initial_sync:
            self.sync_connection(db, user, connection_id)

        return imported

    def sync_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> BankingSyncResponse:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        if conn.status != "connected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot synchronize an inactive or disconnected banking connection.",
            )

        provider = get_demo_provider(conn.provider_id)
        conn.lifecycle_state = "synchronizing"
        self.banking_repo.update_connection(db, conn)

        sync_run = BankingSyncRun(
            connection_id=conn.id,
            user_id=user.id,
            status="success",
        )
        self.banking_repo.create_sync_run(db, sync_run)

        try:
            self.category_service.seed_default_categories(db, commit=False)

            user_accounts = self.account_repo.list_by_user(db, user.id, include_archived=False)
            target_accounts = [
                a
                for a in user_accounts
                if a.source == "demo_bank" and a.institution_name == conn.institution_name
            ]

            discovered = provider.discover_accounts(str(conn.id), str(user.id))
            discovered_by_mask = {
                acc.masked_account_number: acc.external_account_id for acc in discovered
            }

            total_tx_synced = 0
            total_accounts_synced = 0

            for acc in target_accounts:
                if not acc.account_identifier:
                    continue
                ext_account_id = discovered_by_mask.get(acc.account_identifier)
                if not ext_account_id:
                    continue

                total_accounts_synced += 1
                raw_txs = provider.fetch_transactions(str(conn.id), ext_account_id)

                for tx_data in raw_txs:
                    ext_ref = tx_data["external_reference"]
                    existing_tx = self.transaction_repo.get_by_external_reference(
                        db=db,
                        user_id=user.id,
                        account_id=acc.id,
                        external_reference=ext_ref,
                    )
                    if existing_tx:
                        continue

                    category = self.category_repo.get_system_category_by_name(
                        db=db,
                        name=tx_data["category_name"],
                        category_type=tx_data["transaction_type"],
                    )
                    cat_id = category.id if category else None

                    from app.schemas.finance.transaction import TransactionCreateRequest

                    create_req = TransactionCreateRequest(
                        account_id=acc.id,
                        transaction_type=tx_data["transaction_type"],
                        amount=tx_data["amount"],
                        currency=acc.currency,
                        category_id=cat_id,
                        description=tx_data["description"],
                        merchant_payee=tx_data.get("merchant_payee"),
                        transaction_date=tx_data["transaction_date"],
                        notes=tx_data.get("notes"),
                    )
                    self.transaction_service.create_transaction(
                        db=db,
                        user=user,
                        req=create_req,
                        source="demo_bank",
                        external_reference=ext_ref,
                        commit=False,
                    )
                    total_tx_synced += 1

            now = dt.datetime.now(dt.UTC)
            conn.last_sync_at = now
            conn.lifecycle_state = "connected"
            conn.last_error = None
            self.banking_repo.update_connection(db, conn)

            sync_run.accounts_synced = total_accounts_synced
            sync_run.transactions_synced = total_tx_synced
            sync_run.completed_at = now
            self.banking_repo.update_sync_run(db, sync_run)

            db.commit()

            message = (
                f"Synchronized {total_accounts_synced} account(s) and {total_tx_synced} new transaction(s)."
                if total_accounts_synced > 0
                else "No active imported accounts found for this bank. Use 'Discover Accounts' to import accounts first."
            )

            return BankingSyncResponse(
                connection_id=conn.id,
                status="success",
                lifecycle_state="connected",
                accounts_synced=total_accounts_synced,
                transactions_synced=total_tx_synced,
                synced_at=now,
                message=message,
            )
        except Exception as exc:
            db.rollback()
            now = dt.datetime.now(dt.UTC)
            err_conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
            if err_conn:
                err_conn.status = "error"
                err_conn.lifecycle_state = "failed"
                err_conn.last_error = str(exc)[:500]
                self.banking_repo.update_connection(db, err_conn)
                failed_run = BankingSyncRun(
                    connection_id=err_conn.id,
                    user_id=user.id,
                    status="failed",
                    accounts_synced=0,
                    transactions_synced=0,
                    error_message=str(exc)[:500],
                    completed_at=now,
                )
                self.banking_repo.create_sync_run(db, failed_run)
                db.commit()
            raise

    def list_sync_runs(
        self, db: Session, user: User, connection_id: uuid.UUID, limit: int = 10
    ) -> list[BankingSyncRunResponse]:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        runs = self.banking_repo.list_sync_runs(db, conn.id, user.id, limit=limit)
        return [BankingSyncRunResponse.model_validate(r) for r in runs]

    def _deactivate_connection_with_state(
        self, db: Session, user: User, connection_id: uuid.UUID, *, revoke: bool
    ) -> BankingConnectionResponse:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        now = dt.datetime.now(dt.UTC)
        try:
            conn.status = "revoked" if revoke else "disconnected"
            conn.lifecycle_state = "revoked" if revoke else "disconnected"
            if revoke:
                conn.revoked_at = now
            self.banking_repo.update_connection(db, conn)

            demo_accounts = self.account_repo.list_demo_accounts_by_institution(
                db, user.id, conn.institution_name
            )
            for acc in demo_accounts:
                if acc.status != "disconnected":
                    acc.status = "disconnected"
                    self.account_repo.update(db, acc)

            db.commit()
            db.refresh(conn)
            return self._to_connection_response(db, user, conn)
        except Exception:
            db.rollback()
            raise

    def disconnect_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> BankingConnectionResponse:
        return self._deactivate_connection_with_state(db, user, connection_id, revoke=False)

    def revoke_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> BankingConnectionResponse:
        return self._deactivate_connection_with_state(db, user, connection_id, revoke=True)
