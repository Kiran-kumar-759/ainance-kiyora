import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import FinancialTransaction
from app.models.imports import ImportBatch, ImportRow
from app.services.imports.normalizer import canonicalize_description


def detect_duplicates_for_batch(
    db: Session,
    batch: ImportBatch,
    rows: list[ImportRow],
) -> None:
    """
    Runs 3 deterministic layers of duplicate detection across parsed ImportRow objects:
      Layer A: Within-file duplicate transaction_reference or identical record.
      Layer B: Existing DB duplicates (external_reference match, or identical record from a
               previously completed batch with the same file_hash).
      Layer C: Potential duplicates (same date + exact Decimal amount + type + canonical desc,
               or same date + exact amount on non-referenced records) flagged for user review.
    Mutates row.validation_status, row.duplicate_status, duplicate match pointers, and is_selected.
    """
    # Check if this exact file hash was already committed on this account previously
    prior_same_file = db.execute(
        select(ImportBatch.id).where(
            ImportBatch.user_id == batch.user_id,
            ImportBatch.account_id == batch.account_id,
            ImportBatch.file_hash == batch.file_hash,
            ImportBatch.id != batch.id,
            ImportBatch.status.in_(["completed", "completed_with_errors"]),
        )
    ).first()
    is_reupload_of_same_file = prior_same_file is not None

    # Fetch existing transactions for this (user_id, account_id) for Layer B & C matching
    existing_txs = list(
        db.execute(
            select(FinancialTransaction).where(
                FinancialTransaction.user_id == batch.user_id,
                FinancialTransaction.account_id == batch.account_id,
            )
        ).scalars()
    )

    tx_by_ext_ref: dict[str, FinancialTransaction] = {
        tx.external_reference: tx for tx in existing_txs if tx.external_reference
    }
    tx_by_signature: dict[tuple[dt.date, str, str, str], list[FinancialTransaction]] = {}
    tx_by_date_amount: dict[tuple[dt.date, str, str], list[FinancialTransaction]] = {}

    for tx in existing_txs:
        sig = (
            tx.transaction_date,
            f"{tx.amount:.2f}",
            tx.transaction_type,
            canonicalize_description(tx.description),
        )
        tx_by_signature.setdefault(sig, []).append(tx)

        da_key = (tx.transaction_date, f"{tx.amount:.2f}", tx.transaction_type)
        tx_by_date_amount.setdefault(da_key, []).append(tx)

    seen_refs_in_file: dict[str, uuid.UUID] = {}
    seen_sigs_in_file: dict[tuple[dt.date, str, str, str], uuid.UUID] = {}

    for row in rows:
        # Preserve already-imported / excluded / invalid / needs_review statuses
        if row.validation_status in {"invalid", "needs_review", "excluded", "imported"}:
            row.is_selected = False
            continue

        row.duplicate_status = "none"
        row.duplicate_match_row_id = None
        row.duplicate_match_transaction_id = None

        # Layer A1: Repeated non-empty transaction reference within the uploaded file
        if row.transaction_reference:
            if row.transaction_reference in seen_refs_in_file:
                row.validation_status = "duplicate"
                row.duplicate_status = "within_file_duplicate"
                row.duplicate_match_row_id = seen_refs_in_file[row.transaction_reference]
                row.is_selected = False
                if "Duplicate transaction reference within uploaded file." not in row.validation_errors:
                    row.validation_errors = [
                        *row.validation_errors,
                        "Duplicate transaction reference within uploaded file.",
                    ]
                continue
            seen_refs_in_file[row.transaction_reference] = row.id

        # Layer B1: Existing DB transaction with matching external_reference
        if row.transaction_reference and row.transaction_reference in tx_by_ext_ref:
            matched_tx = tx_by_ext_ref[row.transaction_reference]
            row.validation_status = "duplicate"
            row.duplicate_status = "existing_reference_duplicate"
            row.duplicate_match_transaction_id = matched_tx.id
            row.is_selected = False
            msg = f"Transaction reference '{row.transaction_reference}' already exists in account."
            if msg not in row.validation_errors:
                row.validation_errors = [*row.validation_errors, msg]
            continue

        assert row.normalized_date is not None and row.normalized_amount is not None
        assert row.normalized_type is not None

        sig = (
            row.normalized_date,
            f"{row.normalized_amount:.2f}",
            row.normalized_type,
            canonicalize_description(row.normalized_description),
        )

        # Layer B2: Exact match when re-uploading the same file (even if no external reference exists)
        if sig in tx_by_signature:
            matched_tx = tx_by_signature[sig][0]
            if is_reupload_of_same_file:
                row.validation_status = "duplicate"
                row.duplicate_status = "exact_match_duplicate"
                row.duplicate_match_transaction_id = matched_tx.id
                row.is_selected = False
                msg = "Exact match already imported from an identical statement file."
                if msg not in row.validation_errors:
                    row.validation_errors = [*row.validation_errors, msg]
                continue
            else:
                # Different upload or manual entry: treat as potential duplicate for user decision!
                row.validation_status = "potential_duplicate"
                row.duplicate_status = "potential_duplicate"
                row.duplicate_match_transaction_id = matched_tx.id
                row.is_selected = False
                msg = "Possible duplicate of an existing transaction (same date, amount, and description). Review before importing."
                if msg not in row.validation_errors:
                    row.validation_errors = [*row.validation_errors, msg]
                continue

        # Layer A2: Identical record within the same file (without distinct reference) -> potential duplicate
        if sig in seen_sigs_in_file:
            row.validation_status = "potential_duplicate"
            row.duplicate_status = "potential_duplicate"
            row.duplicate_match_row_id = seen_sigs_in_file[sig]
            row.is_selected = False
            msg = "Identical date, amount, and description appears earlier in this file. Confirm if this is a second legitimate purchase."
            if msg not in row.validation_errors:
                row.validation_errors = [*row.validation_errors, msg]
            continue
        seen_sigs_in_file[sig] = row.id

        # Layer C: Same date + exact Decimal amount + same type (different description) -> potential duplicate
        da_key = (row.normalized_date, f"{row.normalized_amount:.2f}", row.normalized_type)
        if da_key in tx_by_date_amount:
            matched_tx = tx_by_date_amount[da_key][0]
            row.validation_status = "potential_duplicate"
            row.duplicate_status = "potential_duplicate"
            row.duplicate_match_transaction_id = matched_tx.id
            row.is_selected = False
            msg = "Possible duplicate: an existing transaction has the same date, type, and amount."
            if msg not in row.validation_errors:
                row.validation_errors = [*row.validation_errors, msg]
            continue

        # Clean valid row
        row.validation_status = "valid"
        row.is_selected = True
