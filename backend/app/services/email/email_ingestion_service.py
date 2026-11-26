import datetime as dt
import inspect
import secrets
import uuid
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.models.documents import (
    DocumentExtraction,
    DocumentReviewEvent,
    FinancialDocument,
)
from app.models.email_ingestion import (
    EmailAttachmentRecord,
    EmailDocumentCandidate,
    EmailMessageRecord,
    EmailSyncHistory,
)
from app.models.user import User
from app.repositories.email.email_repository import EmailIngestionRepository
from app.schemas.documents import DocumentConfirmRequest
from app.schemas.email_ingestion import (
    EmailAttachmentSummaryResponse,
    EmailCandidateConfirmRequest,
    EmailCandidateRejectRequest,
    EmailCandidateResponse,
    EmailConnectionResponse,
    EmailMessageSummaryResponse,
    EmailSyncHistoryResponse,
    EmailSyncRequest,
    GmailConnectUrlResponse,
)
from app.services.documents.doc_storage import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    PrivateDocumentStorage,
    sanitize_filename,
    validate_uploaded_document,
)
from app.services.documents.document_service import DocumentService
from app.services.documents.invoice_parser import parse_ocr_output
from app.services.documents.ocr_engine import (
    OcrDocumentOutput,
    OcrLineItem,
    OcrPageOutput,
    OcrProvider,
    extract_document_text,
)
from app.services.email.gmail_adapter import EmailProviderAdapter, GmailApiAdapter
from app.services.email.oauth_state import create_oauth_state, verify_oauth_state
from app.services.email.token_crypto import decrypt_oauth_token, encrypt_oauth_token

RELEVANCE_KEYWORDS = (
    ("electricity", "electricity_bill"),
    ("power", "electricity_bill"),
    ("broadband", "internet_bill"),
    ("fiber", "internet_bill"),
    ("wifi", "internet_bill"),
    ("internet", "internet_bill"),
    ("credit card", "credit_card_statement"),
    ("statement", "bank_statement"),
    ("insurance", "insurance"),
    ("premium", "insurance"),
    ("loan", "loan"),
    ("emi", "loan"),
    ("recharge", "mobile_bill"),
    ("mobile", "mobile_bill"),
    ("subscription", "subscription_invoice"),
    ("renewal", "subscription_invoice"),
    ("invoice", "other"),
    ("receipt", "shopping_receipt"),
    ("bill", "other"),
)


def _classify_relevance(subject: str | None, body: str | None) -> str | None:
    hay = f"{subject or ''} {body or ''}".lower()
    for kw, cat in RELEVANCE_KEYWORDS:
        if kw in hay:
            return cat
    return None


class EmailIngestionService:
    """
    Gmail OAuth 2.0 integration, incremental sync, duplicate detection, and
    human-confirmed document/candidate ingestion service.
    """

    def __init__(self, adapter: EmailProviderAdapter | None = None):
        self.repo = EmailIngestionRepository()
        self.adapter: EmailProviderAdapter = adapter or GmailApiAdapter()
        self.storage = PrivateDocumentStorage()
        self.doc_service = DocumentService()

    def _to_connection_response(self, conn) -> EmailConnectionResponse:
        return EmailConnectionResponse(
            id=conn.id if conn else None,
            provider=conn.provider if conn else "gmail",
            email_address=conn.email_address if conn else None,
            status=conn.status if conn else "disconnected",
            oauth_configured=self.adapter.is_configured(),
            scopes=list(conn.scopes or []) if conn else [],
            last_history_id=conn.last_history_id if conn else None,
            last_sync_at=conn.last_sync_at if conn else None,
            last_error=conn.last_error if conn else None,
        )

    def _to_candidate_response(self, cand: EmailDocumentCandidate) -> EmailCandidateResponse:
        msg_resp = None
        if cand.message:
            msg_resp = EmailMessageSummaryResponse(
                id=cand.message.id,
                provider_message_id=cand.message.provider_message_id,
                sender=cand.message.sender,
                subject=cand.message.subject,
                received_at=cand.message.received_at,
                snippet_text=cand.message.snippet_text,
                body_text=cand.message.body_text,
                relevance_category=cand.message.relevance_category,
                attachments=[
                    EmailAttachmentSummaryResponse.model_validate(a)
                    for a in (cand.message.attachments or [])
                ],
            )
        return EmailCandidateResponse(
            id=cand.id,
            connection_id=cand.connection_id,
            message_id=cand.message_id,
            attachment_id=cand.attachment_id,
            document_id=cand.document_id,
            status=cand.status,
            duplicate_status=cand.duplicate_status,
            duplicate_reason=cand.duplicate_reason,
            merchant_name=cand.merchant_name,
            invoice_number=cand.invoice_number,
            invoice_date=cand.invoice_date,
            due_date=cand.due_date,
            amount=cand.amount,
            currency=cand.currency,
            extracted_summary=dict(cand.extracted_summary or {}),
            created_at=cand.created_at,
            reviewed_at=cand.reviewed_at,
            message=msg_resp,
        )

    def get_connections(self, db: Session, user: User) -> list[EmailConnectionResponse]:
        conn = self.repo.get_connection(db, user.id, "gmail")
        return [self._to_connection_response(conn)]

    def start_gmail_connect(
        self,
        db: Session,
        user: User,
        *,
        redirect_uri: str | None = None,
        adapter: EmailProviderAdapter | None = None,
    ) -> GmailConnectUrlResponse:
        adp = adapter or self.adapter
        if not adp.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Gmail OAuth is not configured on this server. Set GOOGLE_OAUTH_CLIENT_ID "
                    "and GOOGLE_OAUTH_CLIENT_SECRET environment variables to enable Gmail sync."
                ),
            )
        target_uri = (redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI).strip()
        if target_uri not in settings.GOOGLE_ALLOWED_REDIRECT_URIS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Untrusted OAuth redirect_uri rejected.",
            )
        code_verifier = secrets.token_urlsafe(48)
        state = create_oauth_state(user.id, target_uri, code_verifier=code_verifier)
        if "code_verifier" in inspect.signature(adp.build_authorization_url).parameters:
            auth_url = adp.build_authorization_url(
                state=state, redirect_uri=target_uri, code_verifier=code_verifier
            )
        else:
            auth_url = adp.build_authorization_url(state=state, redirect_uri=target_uri)
        return GmailConnectUrlResponse(
            authorization_url=auth_url,
            state=state,
            scopes=list(settings.GMAIL_SCOPES),
        )

    def handle_gmail_callback(
        self,
        db: Session,
        user: User,
        *,
        code: str,
        state: str,
        adapter: EmailProviderAdapter | None = None,
    ) -> EmailConnectionResponse:
        adp = adapter or self.adapter
        if not adp.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gmail OAuth is not configured on this server.",
            )
        try:
            state_payload = verify_oauth_state(state, user.id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        redirect_uri = state_payload.get("ruri") or settings.GOOGLE_OAUTH_REDIRECT_URI
        if redirect_uri not in settings.GOOGLE_ALLOWED_REDIRECT_URIS:
            raise HTTPException(status_code=400, detail="Invalid redirect_uri in state.")

        code_verifier = state_payload.get("cv")
        try:
            if "code_verifier" in inspect.signature(adp.exchange_code).parameters:
                tokens = adp.exchange_code(
                    code=code, redirect_uri=redirect_uri, code_verifier=code_verifier
                )
            else:
                tokens = adp.exchange_code(code=code, redirect_uri=redirect_uri)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gmail OAuth token exchange failed: {exc}",
            ) from exc

        conn = self.repo.get_or_create_connection(db, user.id, "gmail")
        conn.status = "connected"
        conn.email_address = tokens.email_address
        conn.scopes = tokens.scopes or list(settings.GMAIL_SCOPES)
        conn.encrypted_access_token = encrypt_oauth_token(tokens.access_token)
        if tokens.refresh_token:
            conn.encrypted_refresh_token = encrypt_oauth_token(tokens.refresh_token)
        conn.token_expires_at = tokens.expires_at
        conn.last_error = None
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return self._to_connection_response(conn)

    def disconnect_gmail(
        self,
        db: Session,
        user: User,
        *,
        adapter: EmailProviderAdapter | None = None,
    ) -> EmailConnectionResponse:
        adp = adapter or self.adapter
        conn = self.repo.get_or_create_connection(db, user.id, "gmail")
        token_to_revoke = None
        try:
            token_to_revoke = decrypt_oauth_token(
                conn.encrypted_refresh_token or conn.encrypted_access_token
            )
        except ValueError:
            token_to_revoke = None

        if token_to_revoke:
            adp.revoke_token(token_to_revoke)

        conn.status = "disconnected"
        conn.encrypted_access_token = None
        conn.encrypted_refresh_token = None
        conn.token_expires_at = None
        conn.last_history_id = None
        conn.last_error = None
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return self._to_connection_response(conn)

    def _ensure_valid_access_token(
        self, db: Session, conn, adp: EmailProviderAdapter
    ) -> tuple[str, str | None]:
        access_tok = decrypt_oauth_token(conn.encrypted_access_token)
        refresh_tok = decrypt_oauth_token(conn.encrypted_refresh_token)
        if not access_tok and not refresh_tok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gmail OAuth credentials are missing; reconnect Gmail.",
            )

        now = dt.datetime.now(dt.UTC)
        needs_refresh = not access_tok or (
            conn.token_expires_at is not None
            and conn.token_expires_at <= (now + dt.timedelta(minutes=5))
        )
        if needs_refresh and refresh_tok:
            refreshed = adp.refresh_tokens(access_token=access_tok, refresh_token=refresh_tok)
            conn.encrypted_access_token = encrypt_oauth_token(refreshed.access_token)
            if refreshed.refresh_token:
                conn.encrypted_refresh_token = encrypt_oauth_token(refreshed.refresh_token)
            conn.token_expires_at = refreshed.expires_at
            db.add(conn)
            db.flush()
            return refreshed.access_token, refreshed.refresh_token

        assert access_tok is not None
        return access_tok, refresh_tok

    def sync_gmail(
        self,
        db: Session,
        user: User,
        req: EmailSyncRequest,
        *,
        adapter: EmailProviderAdapter | None = None,
        ocr_provider: OcrProvider | None = None,
    ) -> EmailSyncHistoryResponse:
        allowed = rate_limiter.is_allowed(
            f"gmail:sync:{user.id}",
            max_requests=12,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Gmail sync rate limit reached. Please try again in a minute.",
            )

        adp = adapter or self.adapter
        conn = self.repo.get_connection(db, user.id, "gmail")
        if not conn or conn.status != "connected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gmail account is not connected.",
            )

        sync_run = EmailSyncHistory(
            user_id=user.id,
            connection_id=conn.id,
            sync_mode=(
                "incremental_history"
                if conn.last_history_id and not req.force_full_query
                else "full_query"
            ),
            status="running",
            start_history_id=conn.last_history_id,
        )
        db.add(sync_run)
        db.flush()

        try:
            access_tok, refresh_tok = self._ensure_valid_access_token(db, conn, adp)
            query = (req.search_query or settings.EMAIL_SYNC_DEFAULT_QUERY).strip()
            max_msgs = req.max_messages or settings.EMAIL_SYNC_MAX_MESSAGES

            fetch_res = adp.list_relevant_messages(
                access_token=access_tok,
                refresh_token=refresh_tok,
                query=query,
                max_results=max_msgs,
                last_history_id=None if req.force_full_query else conn.last_history_id,
            )
            sync_run.sync_mode = (
                "incremental_history" if fetch_res.used_incremental_history else "full_query"
            )
            sync_run.messages_scanned = len(fetch_res.message_ids)

            for msg_id in fetch_res.message_ids:
                existing_msg = self.repo.get_message_by_provider_id(db, user.id, msg_id)
                if existing_msg:
                    sync_run.duplicate_candidates += 1
                    continue

                fetched = adp.fetch_message(
                    access_token=access_tok, refresh_token=refresh_tok, message_id=msg_id
                )
                rel_cat = _classify_relevance(fetched.subject, fetched.body_text)
                if not rel_cat and not fetched.attachments:
                    continue

                sync_run.relevant_messages += 1
                msg_rec = EmailMessageRecord(
                    user_id=user.id,
                    connection_id=conn.id,
                    provider_message_id=fetched.provider_message_id,
                    thread_id=fetched.thread_id,
                    sender=fetched.sender[:250] if fetched.sender else None,
                    subject=fetched.subject[:490] if fetched.subject else None,
                    received_at=fetched.received_at,
                    snippet_text=fetched.snippet_text,
                    body_text=fetched.body_text,
                    relevance_category=rel_cat or "other",
                )
                db.add(msg_rec)
                db.flush()

                processed_any_attachment = False
                for att in fetched.attachments:
                    safe_fname = sanitize_filename(att.filename)
                    ext = Path(safe_fname).suffix.lower()
                    supported = ext in ALLOWED_DOCUMENT_EXTENSIONS
                    att_rec = EmailAttachmentRecord(
                        user_id=user.id,
                        message_id=msg_rec.id,
                        provider_attachment_id=att.attachment_id,
                        filename=safe_fname,
                        content_type=att.content_type[:95],
                        file_size=att.size,
                        is_supported=supported,
                        processing_status="pending" if supported else "skipped",
                    )
                    db.add(att_rec)
                    db.flush()

                    if not supported:
                        continue

                    try:
                        att_bytes = att.data or adp.fetch_attachment(
                            access_token=access_tok,
                            refresh_token=refresh_tok,
                            message_id=fetched.provider_message_id,
                            attachment_id=att.attachment_id,
                        )
                        val = validate_uploaded_document(safe_fname, att_bytes)
                        att_rec.file_size = val.file_size
                        att_rec.file_hash = val.file_hash
                        att_rec.content_type = val.content_type

                        prior_doc = self.doc_service.repo.get_by_hash(db, user.id, val.file_hash)
                        storage_key = self.storage.save(user.id, val.file_type, att_bytes)
                        doc = FinancialDocument(
                            user_id=user.id,
                            original_filename=val.safe_filename,
                            file_type=val.file_type,
                            content_type=val.content_type,
                            file_size=val.file_size,
                            file_hash=val.file_hash,
                            storage_key=storage_key,
                            document_category=rel_cat or "other",
                            source="gmail_attachment",
                            is_duplicate_of_id=prior_doc.id if prior_doc else None,
                            duplicate_flag=prior_doc is not None,
                            processing_status="processing",
                            ocr_status="processing",
                            page_count=val.page_count,
                        )
                        db.add(doc)
                        db.flush()

                        ocr_out = extract_document_text(
                            att_bytes, val.file_type, provider=ocr_provider
                        )
                        parsed = parse_ocr_output(ocr_out)
                        ext_rec = DocumentExtraction(
                            user_id=user.id,
                            document_id=doc.id,
                            ocr_engine=ocr_out.engine_name,
                            ocr_engine_version=ocr_out.engine_version,
                            raw_text=ocr_out.full_text,
                            raw_structured_data=parsed.to_snapshot_dict(),
                            merchant_name=parsed.merchant_name,
                            merchant_address=parsed.merchant_address,
                            merchant_phone=parsed.merchant_phone,
                            invoice_number=parsed.invoice_number,
                            invoice_date=parsed.invoice_date,
                            due_date=parsed.due_date,
                            payment_date=parsed.payment_date,
                            bill_period=parsed.bill_period,
                            detected_document_type=parsed.detected_document_type,
                            currency=parsed.currency,
                            subtotal=parsed.subtotal,
                            taxable_amount=parsed.taxable_amount,
                            total_tax=parsed.total_tax,
                            grand_total=parsed.grand_total,
                            amount_paid=parsed.amount_paid,
                            outstanding_amount=parsed.outstanding_amount,
                            gstin=parsed.gstin,
                            cgst=parsed.cgst,
                            sgst=parsed.sgst,
                            igst=parsed.igst,
                            tax_percentage=parsed.tax_percentage,
                            line_items=parsed.line_items,
                            field_confidence=parsed.field_confidence,
                            validation_errors=parsed.validation_errors,
                            validation_warnings=list(
                                dict.fromkeys([*ocr_out.warnings, *parsed.validation_warnings])
                            ),
                            overall_confidence=parsed.overall_confidence,
                        )
                        db.add(ext_rec)
                        doc.ocr_status = "completed"
                        doc.processing_status = "needs_review"
                        doc.processed_at = dt.datetime.now(dt.UTC)
                        db.add(doc)

                        att_rec.document_id = doc.id
                        att_rec.processing_status = "stored"
                        db.add(att_rec)

                        dup_status = "exact_duplicate" if prior_doc else "unique"
                        dup_reason = (
                            "Attachment file hash matches an existing uploaded document."
                            if prior_doc
                            else None
                        )
                        if not prior_doc:
                            uncertain = self.repo.find_candidate_duplicate(
                                db,
                                user.id,
                                invoice_number=parsed.invoice_number,
                                merchant_name=parsed.merchant_name,
                                invoice_date=parsed.invoice_date,
                                amount=parsed.grand_total,
                            )
                            if uncertain:
                                dup_status = "uncertain_duplicate"
                                dup_reason = (
                                    "Similar merchant/invoice/amount matches an earlier candidate. "
                                    "Kept for user review (may be recurring invoice)."
                                )

                        cand_status = "duplicate_warning" if dup_status != "unique" else "needs_review"
                        if dup_status != "unique":
                            sync_run.duplicate_candidates += 1
                        sync_run.candidates_needing_review += 1
                        sync_run.attachments_processed += 1
                        processed_any_attachment = True

                        cand = EmailDocumentCandidate(
                            user_id=user.id,
                            connection_id=conn.id,
                            message_id=msg_rec.id,
                            attachment_id=att_rec.id,
                            document_id=doc.id,
                            status=cand_status,
                            duplicate_status=dup_status,
                            duplicate_reason=dup_reason,
                            merchant_name=parsed.merchant_name,
                            invoice_number=parsed.invoice_number,
                            invoice_date=parsed.invoice_date,
                            due_date=parsed.due_date,
                            amount=parsed.grand_total,
                            currency=parsed.currency,
                            extracted_summary=parsed.to_snapshot_dict(),
                        )
                        db.add(cand)
                    except Exception as att_exc:
                        att_rec.processing_status = "failed"
                        db.add(att_rec)
                        sync_run.failed_jobs += 1
                        db.flush()
                        # Keep going cleanly for other attachments/messages
                        _ = att_exc

                if not processed_any_attachment and (fetched.body_text or fetched.subject):
                    # Deterministic parse from plain email text when no supported attachment was present
                    text_block = "\n".join(
                        p for p in [fetched.subject or "", fetched.body_text or ""] if p
                    )
                    lines = [
                        OcrLineItem(text=ln.strip(), confidence=0.95)
                        for ln in text_block.splitlines()
                        if ln.strip()
                    ]
                    syn_ocr = OcrDocumentOutput(
                        engine_name="email_text_parser",
                        engine_version="1.0",
                        full_text=text_block,
                        pages=[
                            OcrPageOutput(
                                page_number=1,
                                text=text_block,
                                lines=lines,
                                used_ocr=False,
                                average_confidence=0.95,
                            )
                        ],
                        total_pages=1,
                        processed_pages=1,
                        warnings=[],
                        average_confidence=0.95,
                    )
                    parsed = parse_ocr_output(syn_ocr)
                    uncertain = self.repo.find_candidate_duplicate(
                        db,
                        user.id,
                        invoice_number=parsed.invoice_number,
                        merchant_name=parsed.merchant_name,
                        invoice_date=parsed.invoice_date,
                        amount=parsed.grand_total,
                    )
                    dup_status = "uncertain_duplicate" if uncertain else "unique"
                    dup_reason = (
                        "Similar merchant/invoice/amount found in prior candidate. Review before confirming."
                        if uncertain
                        else None
                    )
                    if uncertain:
                        sync_run.duplicate_candidates += 1
                    sync_run.candidates_needing_review += 1
                    db.add(
                        EmailDocumentCandidate(
                            user_id=user.id,
                            connection_id=conn.id,
                            message_id=msg_rec.id,
                            attachment_id=None,
                            document_id=None,
                            status="duplicate_warning" if uncertain else "needs_review",
                            duplicate_status=dup_status,
                            duplicate_reason=dup_reason,
                            merchant_name=parsed.merchant_name,
                            invoice_number=parsed.invoice_number,
                            invoice_date=parsed.invoice_date,
                            due_date=parsed.due_date,
                            amount=parsed.grand_total,
                            currency=parsed.currency,
                            extracted_summary=parsed.to_snapshot_dict(),
                        )
                    )

            conn.last_history_id = fetch_res.latest_history_id or conn.last_history_id
            conn.last_sync_at = dt.datetime.now(dt.UTC)
            conn.last_error = None
            db.add(conn)

            sync_run.end_history_id = conn.last_history_id
            sync_run.status = "partial" if sync_run.failed_jobs > 0 else "completed"
            sync_run.completed_at = dt.datetime.now(dt.UTC)
            db.add(sync_run)
            db.commit()
            db.refresh(sync_run)
            return EmailSyncHistoryResponse.model_validate(sync_run)

        except HttpError as g_exc:
            status_code = getattr(g_exc.resp, "status", 500)
            msg = (
                "Gmail API quota or rate limit exceeded. Try again later."
                if status_code in {403, 429}
                else f"Gmail API error ({status_code}): {g_exc}"
            )
            sync_run.status = "failed"
            sync_run.error_message = msg[:500]
            sync_run.completed_at = dt.datetime.now(dt.UTC)
            conn.last_error = msg[:500]
            db.add(sync_run)
            db.add(conn)
            db.commit()
            raise HTTPException(
                status_code=(
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if status_code == 429
                    else status.HTTP_502_BAD_GATEWAY
                ),
                detail=msg,
            ) from g_exc
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            sync_run.status = "failed"
            sync_run.error_message = str(exc)[:500]
            sync_run.completed_at = dt.datetime.now(dt.UTC)
            conn.last_error = str(exc)[:500]
            db.add(sync_run)
            db.add(conn)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gmail synchronization failed: {exc}",
            ) from exc

    def list_sync_history(self, db: Session, user: User) -> list[EmailSyncHistoryResponse]:
        rows = self.repo.list_sync_history(db, user.id, limit=25)
        return [EmailSyncHistoryResponse.model_validate(r) for r in rows]

    def list_candidates(
        self, db: Session, user: User, status_filter: str | None = None
    ) -> list[EmailCandidateResponse]:
        rows = self.repo.list_candidates(db, user.id, status_filter=status_filter)
        return [self._to_candidate_response(c) for c in rows]

    def get_candidate(
        self, db: Session, user: User, candidate_id: uuid.UUID
    ) -> EmailCandidateResponse:
        cand = self.repo.get_candidate(db, candidate_id, user.id)
        if not cand:
            raise HTTPException(status_code=404, detail="Email candidate not found.")
        return self._to_candidate_response(cand)

    def reject_candidate(
        self,
        db: Session,
        user: User,
        candidate_id: uuid.UUID,
        req: EmailCandidateRejectRequest,
    ) -> EmailCandidateResponse:
        cand = self.repo.get_candidate(db, candidate_id, user.id)
        if not cand:
            raise HTTPException(status_code=404, detail="Email candidate not found.")
        cand.status = "rejected"
        cand.reviewed_at = dt.datetime.now(dt.UTC)
        db.add(cand)
        if cand.document:
            cand.document.processing_status = "rejected"
            cand.document.rejected_at = dt.datetime.now(dt.UTC)
            cand.document.rejection_reason = req.reason.strip()
            db.add(cand.document)
            self.doc_service.repo.add_review_event(
                db,
                DocumentReviewEvent(
                    user_id=user.id,
                    document_id=cand.document.id,
                    action="rejected",
                    changes={"reason": req.reason.strip(), "source": "email_candidate"},
                ),
            )
        db.commit()
        refreshed = self.repo.get_candidate(db, candidate_id, user.id)
        assert refreshed is not None
        return self._to_candidate_response(refreshed)

    def confirm_candidate(
        self,
        db: Session,
        user: User,
        candidate_id: uuid.UUID,
        req: EmailCandidateConfirmRequest,
    ) -> EmailCandidateResponse:
        cand = self.repo.get_candidate(db, candidate_id, user.id)
        if not cand:
            raise HTTPException(status_code=404, detail="Email candidate not found.")
        if cand.status == "confirmed":
            raise HTTPException(status_code=400, detail="Candidate has already been confirmed.")
        if cand.status == "rejected":
            raise HTTPException(status_code=400, detail="Cannot confirm a rejected candidate.")

        if req.merchant_name is not None:
            cand.merchant_name = req.merchant_name
        if req.invoice_number is not None:
            cand.invoice_number = req.invoice_number
        if req.invoice_date is not None:
            cand.invoice_date = req.invoice_date
        if req.due_date is not None:
            cand.due_date = req.due_date
        if req.amount is not None:
            cand.amount = req.amount

        if cand.document_id:
            confirm_req = DocumentConfirmRequest(
                action=req.action,
                target_id=req.target_id,
                bill_name=req.bill_name or cand.merchant_name,
                bill_category=req.bill_category,
                due_date=req.due_date or cand.due_date,
                amount=req.amount or cand.amount,
                financial_account_id=req.financial_account_id,
                financial_category_id=req.financial_category_id,
                transaction_date=req.invoice_date or cand.invoice_date,
                description=cand.merchant_name,
                notes=req.notes or f"Confirmed from email candidate {cand.id}",
            )
            self.doc_service.confirm_document(db, user, cand.document_id, confirm_req)
        elif req.action == "create_bill":
            amt = req.amount or cand.amount
            from app.schemas.bills import BillCreateRequest

            bill_req = BillCreateRequest(
                bill_name=(req.bill_name or cand.merchant_name or "Email Bill")[:150],
                bill_category=(req.bill_category or "other"),  # type: ignore[arg-type]
                provider_name=cand.merchant_name,
                account_reference=cand.invoice_number,
                bill_type="one_time",
                is_variable_amount=amt is None,
                expected_amount=amt,
                current_amount=amt,
                currency="INR",
                due_date=req.due_date or cand.due_date or cand.invoice_date or dt.date.today(),
                financial_category_id=req.financial_category_id,
                linked_account_id=req.financial_account_id,
            )
            self.doc_service.bill_service.create_bill(db, user, bill_req)
        elif req.action == "create_transaction":
            if not req.financial_account_id:
                raise HTTPException(
                    status_code=400, detail="financial_account_id is required to create transaction."
                )
            amt = req.amount or cand.amount
            if amt is None or amt <= Decimal("0.00"):
                raise HTTPException(status_code=400, detail="Positive amount is required.")
            from app.schemas.finance.transaction import TransactionCreateRequest

            self.doc_service.transaction_service.create_transaction(
                db=db,
                user=user,
                req=TransactionCreateRequest(
                    account_id=req.financial_account_id,
                    transaction_type="expense",
                    amount=amt,
                    currency="INR",
                    category_id=req.financial_category_id,
                    description=(cand.merchant_name or "Email Invoice")[:250],
                    merchant_payee=cand.merchant_name,
                    transaction_date=req.invoice_date or cand.invoice_date or dt.date.today(),
                    notes=req.notes,
                ),
                source="manual",
                commit=False,
            )

        cand.status = "confirmed"
        cand.reviewed_at = dt.datetime.now(dt.UTC)
        db.add(cand)
        db.commit()
        refreshed = self.repo.get_candidate(db, candidate_id, user.id)
        assert refreshed is not None
        return self._to_candidate_response(refreshed)
