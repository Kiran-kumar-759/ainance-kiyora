import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.config import settings
from app.models.user import User
from app.schemas.email_ingestion import (
    EmailCandidateConfirmRequest,
    EmailCandidateRejectRequest,
    EmailCandidateResponse,
    EmailConnectionResponse,
    EmailSyncHistoryResponse,
    EmailSyncRequest,
    GmailConnectUrlResponse,
    SmsIngestionStatusResponse,
)
from app.services.email.email_ingestion_service import EmailIngestionService
from app.services.sms.sms_ingestion_boundary import get_sms_ingestion_provider

router = APIRouter(prefix="/email", tags=["Email & SMS Ingestion"])
email_service = EmailIngestionService()


@router.get("/connections", response_model=list[EmailConnectionResponse])
def list_email_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_service.get_connections(db, current_user)


@router.get("/gmail/connect", response_model=GmailConnectUrlResponse)
def get_gmail_connect_url(
    redirect_uri: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_service.start_gmail_connect(db, current_user, redirect_uri=redirect_uri)


@router.get("/gmail/callback")
def handle_gmail_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_to_frontend: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = email_service.handle_gmail_callback(db, current_user, code=code, state=state)
    if redirect_to_frontend:
        target = f"{settings.FRONTEND_URL}?view=documents&tab=email&gmail=connected"
        return HTMLResponse(
            f'<html><head><meta http-equiv="refresh" content="0;url={target}" /></head>'
            f'<body>Gmail connected cleanly. Redirecting...</body></html>'
        )
    return conn


@router.post("/gmail/disconnect", response_model=EmailConnectionResponse)
def disconnect_gmail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return email_service.disconnect_gmail(db, current_user)


@router.post("/gmail/sync", response_model=EmailSyncHistoryResponse)
def sync_gmail_messages(
    req: EmailSyncRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return email_service.sync_gmail(db, current_user, req or EmailSyncRequest())


@router.get("/sync-history", response_model=list[EmailSyncHistoryResponse])
def list_email_sync_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_service.list_sync_history(db, current_user)


@router.get("/candidates", response_model=list[EmailCandidateResponse])
def list_email_candidates(
    status_filter: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_service.list_candidates(db, current_user, status_filter=status_filter)


@router.get("/candidates/{candidate_id}", response_model=EmailCandidateResponse)
def get_email_candidate(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_service.get_candidate(db, current_user, candidate_id)


@router.post("/candidates/{candidate_id}/confirm", response_model=EmailCandidateResponse)
def confirm_email_candidate(
    candidate_id: uuid.UUID,
    req: EmailCandidateConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return email_service.confirm_candidate(db, current_user, candidate_id, req)


@router.post("/candidates/{candidate_id}/reject", response_model=EmailCandidateResponse)
def reject_email_candidate(
    candidate_id: uuid.UUID,
    req: EmailCandidateRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return email_service.reject_candidate(db, current_user, candidate_id, req)


@router.get("/sms/status", response_model=SmsIngestionStatusResponse)
def get_sms_ingestion_status(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return get_sms_ingestion_provider().get_status()
