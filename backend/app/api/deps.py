import secrets
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token, verify_csrf_token_signature
from app.db.session import get_db
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository

session_repo = SessionRepository()
user_repo = UserRepository()


def get_session_token_from_cookie_or_header(
    request: Request,
    pfm_session: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    authorization: str | None = Header(None),
) -> str | None:
    """Extracts session token from HttpOnly cookie (primary) or Bearer header (fallback)."""
    if pfm_session:
        return pfm_session
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ")[1].strip()
    return None


def get_current_user(
    db: Session = Depends(get_db),
    raw_token: str | None = Depends(get_session_token_from_cookie_or_header),
) -> User:
    """
    Validates server-managed session from HttpOnly cookie and returns the authenticated User.
    Enforces strict user ownership and automatic session expiry verification.
    """
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    token_hash_val = hash_token(raw_token)
    session = session_repo.get_by_token_hash(db, token_hash_val)

    if not session or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked or is invalid.",
        )

    now = datetime.now(UTC)
    if session.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
        )

    user = user_repo.get_by_id(db, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
        )

    # Throttled update of last_used_at (update if older than 60s)
    if (now - session.last_used_at).total_seconds() > 60:
        session_repo.update_last_used(db, session)

    return user


def require_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Restricts sensitive operations to users with verified email addresses."""
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address must be verified before performing this action.",
        )
    return current_user


def verify_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(None, alias=settings.CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(None, alias="x-csrf-token"),
) -> None:
    """
    Double-submit CSRF verification for state-changing HTTP requests.
    Exempts safe methods (GET, HEAD, OPTIONS).
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Public unauthenticated endpoints that do not require an existing session
    public_endpoints = {
        f"{settings.API_V1_PREFIX}/auth/register",
        f"{settings.API_V1_PREFIX}/auth/login",
        f"{settings.API_V1_PREFIX}/auth/forgot-password",
        f"{settings.API_V1_PREFIX}/auth/reset-password",
        f"{settings.API_V1_PREFIX}/auth/verify-email",
        f"{settings.API_V1_PREFIX}/auth/resend-verification",
    }
    if request.url.path in public_endpoints:
        return

    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing CSRF token in request cookie or header.",
        )

    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed.",
        )

    if not verify_csrf_token_signature(csrf_cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token signature is invalid or forged.",
        )
