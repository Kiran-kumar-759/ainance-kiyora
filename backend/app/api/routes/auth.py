import uuid

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_db,
    get_session_token_from_cookie_or_header,
    verify_csrf,
)
from app.core.config import settings
from app.core.security import generate_csrf_token
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    CsrfResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SessionResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Sessions"])
auth_service = AuthService()


def _set_auth_cookies(response: Response, raw_session_token: str, csrf_token: str) -> None:
    """Sets secure HttpOnly session cookie and readable CSRF token cookie."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_session_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRY_SECONDS,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # Accessible to frontend client for double-submit header
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRY_SECONDS,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clears authentication and CSRF cookies."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


@router.get("/csrf", response_model=CsrfResponse, summary="Obtain or refresh CSRF token")
def get_csrf(
    response: Response, csrf_cookie: str | None = Cookie(None, alias=settings.CSRF_COOKIE_NAME)
):
    """Provides a fresh CSRF token and sets the corresponding cookie."""
    token = csrf_cookie or generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRY_SECONDS,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    return CsrfResponse(csrf_token=token)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Creates a new user with Argon2id password hash, assigns default Indian preferences,
    and sends a verification email.
    """
    user, delivery_status = auth_service.register(
        db=db,
        req=req,
        client_ip=request.client.host if request.client else None,
    )
    # Ensure CSRF cookie is initialized on registration
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRY_SECONDS,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )

    return AuthResponse(
        message="Registration successful. Please verify your email.",
        user=UserResponse.model_validate(user),
        email_delivery_status=delivery_status,
    )


@router.post("/login", response_model=AuthResponse, summary="Log in and provision session")
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates user, creates cryptographically random opaque session,
    and sets HttpOnly cookie.
    """
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    user, raw_session_token, csrf_token = auth_service.login(
        db=db,
        req=req,
        user_agent=user_agent,
        client_ip=client_ip,
    )

    _set_auth_cookies(response, raw_session_token, csrf_token)

    return AuthResponse(
        message="Login successful.",
        user=UserResponse.model_validate(user),
        email_delivery_status="skipped",
    )


@router.get("/me", response_model=UserResponse, summary="Get currently authenticated user")
def get_me(current_user: User = Depends(get_current_user)):
    """Restores session and returns the current user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse, summary="Log out of current session")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    raw_token: str | None = Depends(get_session_token_from_cookie_or_header),
    _: None = Depends(verify_csrf),
):
    """Revokes the current session and clears browser cookies."""
    if raw_token:
        auth_service.logout(db, raw_token)
    _clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Log out of all devices/sessions",
)
def logout_all(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Revokes all active sessions for the authenticated user and clears cookies."""
    count = auth_service.logout_all(db, current_user.id)
    _clear_auth_cookies(response)
    return MessageResponse(message=f"Logged out from {count} active device(s).")


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    summary="List active sessions for current user",
)
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    raw_token: str | None = Depends(get_session_token_from_cookie_or_header),
):
    """Lists all active sessions belonging to the authenticated user."""
    return auth_service.list_sessions(db, current_user.id, raw_token)


@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
    summary="Revoke an individual session",
)
def revoke_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Revokes a specific session, enforcing strict user ownership."""
    auth_service.revoke_session(db, session_id, current_user.id)
    return MessageResponse(message="Session successfully revoked.")


@router.post(
    "/verify-email",
    response_model=AuthResponse,
    summary="Verify email with one-time token",
)
def verify_email(
    req: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """Marks user email verified after validating token."""
    user = auth_service.verify_email(db, req.token)
    return AuthResponse(
        message="Email verified successfully.",
        user=UserResponse.model_validate(user),
        email_delivery_status="verified",
    )


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend verification email",
)
def resend_verification(
    req: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Dispatches a new email verification token (enumeration-safe)."""
    auth_service.resend_verification(
        db=db,
        email=req.email,
        client_ip=request.client.host if request.client else None,
    )
    return MessageResponse(
        message="If an unverified account exists with that email, a verification link has been sent."
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset email",
)
def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Sends password reset token (enumeration-safe generic response)."""
    auth_service.forgot_password(
        db=db,
        email=req.email,
        client_ip=request.client.host if request.client else None,
    )
    return MessageResponse(
        message="If an account exists with that email, password reset instructions have been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using one-time token",
)
def reset_password(
    req: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Resets user password with Argon2id and revokes all existing sessions."""
    auth_service.reset_password(db, req)
    return MessageResponse(
        message="Password has been reset successfully. Please log in with your new password."
    )
