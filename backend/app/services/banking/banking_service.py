import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.finance import BankingConnection, BankingSyncRun
from app.models.user import User
from app.providers.banking.demo_provider import (
    get_all_demo_providers,
    get_demo_provider,
)
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.banking_repository import BankingRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.schemas.finance.account import AccountCreateRequest, AccountResponse
from app.schemas.finance.banking import (
    BankingAccountImportRequest,
    BankingConnectionResponse,
    BankingConsentRequest,
    BankingProviderInfo,
    BankingSyncResponse,
    DiscoveredAccountInfo,
)
from app.services.finance.account_service import AccountService
from app.services.finance.category_service import CategoryService
from app.services.finance.transaction_service import TransactionService


class BankingService:
    """Service managing simulated banking connections, account discovery, and idempotent sync."""

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

        existing = self.banking_repo.get_connection_by_provider(db, user.id, req.provider_id)
        if existing:
            existing.status = "connected"
            existing.consent_granted_at = dt.datetime.now(dt.UTC)
            self.banking_repo.update_connection(db, existing)
            return BankingConnectionResponse.model_validate(existing)

        conn = BankingConnection(
            user_id=user.id,
            provider_id=req.provider_id,
            institution_name=provider_info.name,
            status="connected",
            consent_granted_at=dt.datetime.now(dt.UTC),
            consent_scope="accounts,transactions",
            is_simulated=True,
        )
        self.banking_repo.create_connection(db, conn)
        return BankingConnectionResponse.model_validate(conn)

    def list_user_connections(self, db: Session, user: User) -> list[BankingConnectionResponse]:
        conns = self.banking_repo.list_connections(db, user.id)
        res = []
        for c in conns:
            # Count connected accounts
            accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
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
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
        matched_count = sum(
            1
            for a in accounts
            if a.source == "demo_bank" and a.institution_name == conn.institution_name
        )
        resp = BankingConnectionResponse.model_validate(conn)
        resp.connected_accounts_count = matched_count
        return resp

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
                detail="Cannot discover accounts on a disconnected banking connection.",
            )

        provider = get_demo_provider(conn.provider_id)
        discovered = provider.discover_accounts(str(conn.id), str(user.id))

        # Check existing imported accounts
        existing_accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
        existing_identifiers = {
            a.account_identifier
            for a in existing_accounts
            if a.source == "demo_bank" and a.institution_name == conn.institution_name
        }

        for acc in discovered:
            if acc.masked_account_number in existing_identifiers:
                acc.already_imported = True

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
                detail="Cannot import accounts from a disconnected banking connection.",
            )

        provider = get_demo_provider(conn.provider_id)
        discovered = provider.discover_accounts(str(conn.id), str(user.id))
        discovered_map = {acc.external_account_id: acc for acc in discovered}

        imported = []
        for ext_id in req.account_ids:
            if ext_id not in discovered_map:
                continue
            acc_info = discovered_map[ext_id]

            # Check if already imported
            existing_accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
            already_imported = any(
                a.source == "demo_bank"
                and a.institution_name == conn.institution_name
                and a.account_identifier == acc_info.masked_account_number
                for a in existing_accounts
            )
            if already_imported:
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
                db=db, user=user, req=create_req, source="demo_bank"
            )
            imported.append(new_acc)

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
                detail="Cannot synchronize a disconnected banking connection.",
            )

        provider = get_demo_provider(conn.provider_id)
        sync_run = BankingSyncRun(
            connection_id=conn.id,
            user_id=user.id,
            status="success",
        )
        self.banking_repo.create_sync_run(db, sync_run)

        # Ensure system categories are seeded
        self.category_service.seed_default_categories(db)

        # Find user's imported accounts for this provider
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
                # Idempotency check: verify if external_reference already exists for this account
                existing_tx = self.transaction_repo.get_by_external_reference(
                    db=db,
                    user_id=user.id,
                    account_id=acc.id,
                    external_reference=ext_ref,
                )
                if existing_tx:
                    # Already synchronized - skip to prevent duplicate!
                    continue

                # Find or assign category
                category = self.category_repo.get_system_category_by_name(
                    db=db,
                    name=tx_data["category_name"],
                    category_type=tx_data["transaction_type"],
                )
                cat_id = category.id if category else None

                # Create transaction
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
                )
                total_tx_synced += 1

        now = dt.datetime.now(dt.UTC)
        conn.last_sync_at = now
        self.banking_repo.update_connection(db, conn)

        sync_run.accounts_synced = total_accounts_synced
        sync_run.transactions_synced = total_tx_synced
        sync_run.completed_at = now
        self.banking_repo.update_sync_run(db, sync_run)

        return BankingSyncResponse(
            connection_id=conn.id,
            status="success",
            accounts_synced=total_accounts_synced,
            transactions_synced=total_tx_synced,
            synced_at=now,
            message=f"Synchronized {total_accounts_synced} account(s) and {total_tx_synced} new transaction(s).",
        )

    def disconnect_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> BankingConnectionResponse:
        conn = self.banking_repo.get_connection_by_id(db, connection_id, user.id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Banking connection not found.",
            )
        conn.status = "disconnected"
        self.banking_repo.update_connection(db, conn)
        return BankingConnectionResponse.model_validate(conn)
