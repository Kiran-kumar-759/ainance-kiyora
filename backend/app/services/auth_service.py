import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.core.security import (
    generate_csrf_token,
    generate_secure_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)
from app.models.user import User
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.preference_repository import PreferenceRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
)
from app.services.email_service import email_service

# Dummy hash for constant-time comparison against nonexistent accounts
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$dummyhashdummysalt12$dummyhashdummysalt1234567890123456789012"
)


class AuthService:
    """Service handling core authentication, session lifecycles, and credential management."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        session_repo: SessionRepository | None = None,
        token_repo: TokenRepository | None = None,
        pref_repo: PreferenceRepository | None = None,
        onboarding_repo: OnboardingRepository | None = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.session_repo = session_repo or SessionRepository()
        self.token_repo = token_repo or TokenRepository()
        self.pref_repo = pref_repo or PreferenceRepository()
        self.onboarding_repo = onboarding_repo or OnboardingRepository()

    def register(
        self,
        db: Session,
        req: RegisterRequest,
        client_ip: str | None = None,
    ) -> tuple[User, str]:
        """Registers a new user account, creates default preferences, and sends verification email."""
        # 1. Rate Limiting
        rate_key = f"register:{client_ip or 'global'}"
        if not rate_limiter.is_allowed(
            rate_key,
            max_requests=settings.RATE_LIMIT_REGISTER_MAX,
            window_seconds=60,
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts. Please try again in a few minutes.",
            )

        clean_email = normalize_email(req.email)

        # 2. Duplicate Account Check
        existing_user = self.user_repo.get_by_email(db, clean_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # 3. Hash Password with Argon2id
        pwd_hash = hash_password(req.password)

        # 4. Create User Record
        user = self.user_repo.create(
            db=db,
            email=clean_email,
            password_hash=pwd_hash,
            full_name=req.full_name,
            is_email_verified=False,
        )

        # 5. Create Default User Preferences (India standards) & Initial Onboarding State
        self.pref_repo.create_defaults(
            db=db,
            user_id=user.id,
            preferred_currency="INR",
            locale="en-IN",
            timezone_str="Asia/Kolkata",
            date_format="DD/MM/YYYY",
        )
        self.onboarding_repo.get_or_create(db, user.id, already_completed=False)

        # 6. Generate Verification Token
        raw_token = generate_secure_token()
        token_hash_val = hash_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(
            hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )
        self.token_repo.create_verification_token(
            db=db,
            user_id=user.id,
            token_hash=token_hash_val,
            expires_at=expires_at,
        )

        # 7. Dispatch Email
        email_sent = email_service.send_verification_email(
            to_email=user.email,
            full_name=user.full_name,
            raw_token=raw_token,
        )
        delivery_status = "sent" if email_sent else "failed"

        return user, delivery_status

    def login(
        self,
        db: Session,
        req: LoginRequest,
        user_agent: str | None = None,
        client_ip: str | None = None,
    ) -> tuple[User, str, str]:
        """
        Validates credentials and provisions a secure server-managed session.
        Returns: (user, raw_session_token, csrf_token)
        """
        # 1. Rate Limiting
        rate_key = f"login:{client_ip or req.email}"
        if not rate_limiter.is_allowed(
            rate_key,
            max_requests=settings.RATE_LIMIT_LOGIN_MAX,
            window_seconds=60,
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again shortly.",
            )

        clean_email = normalize_email(req.email)
        user = self.user_repo.get_by_email(db, clean_email)

        # 2. Timing attack mitigation: verify dummy hash if user doesn't exist
        target_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        is_valid_pwd = verify_password(req.password, target_hash)

        if not user or not is_valid_pwd:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # 3. Account Status Check
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact support.",
            )

        # 4. Update last login timestamp
        self.user_repo.update_last_login(db, user)

        # 5. Provision Cryptographically Random Session
        raw_session_token = generate_secure_token()
        session_token_hash = hash_token(raw_session_token)
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.SESSION_EXPIRY_SECONDS)

        self.session_repo.create(
            db=db,
            user_id=user.id,
            token_hash=session_token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=client_ip,
        )

        # 6. Generate CSRF Token
        csrf_token = generate_csrf_token()

        return user, raw_session_token, csrf_token

    def logout(self, db: Session, raw_token: str) -> None:
        """Revokes the current session."""
        token_hash_val = hash_token(raw_token)
        session = self.session_repo.get_by_token_hash(db, token_hash_val)
        if session and session.revoked_at is None:
            self.session_repo.revoke(db, session_id=session.id, user_id=session.user_id)

    def logout_all(self, db: Session, user_id: uuid.UUID) -> int:
        """Revokes all active sessions for the authenticated user."""
        return self.session_repo.revoke_all_for_user(db, user_id)

    def list_sessions(
        self,
        db: Session,
        user_id: uuid.UUID,
        current_token: str | None = None,
    ) -> list[SessionResponse]:
        """Lists active sessions for the authenticated user, tagging current session."""
        current_hash = hash_token(current_token) if current_token else None
        active_sessions = self.session_repo.list_active_by_user(db, user_id)

        responses: list[SessionResponse] = []
        for s in active_sessions:
            responses.append(
                SessionResponse(
                    id=s.id,
                    created_at=s.created_at,
                    expires_at=s.expires_at,
                    last_used_at=s.last_used_at,
                    user_agent=s.user_agent,
                    ip_address=s.ip_address,
                    is_current=(s.token_hash == current_hash),
                )
            )
        return responses

    def revoke_session(
        self,
        db: Session,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Revokes a specific session, strictly enforcing user ownership."""
        revoked = self.session_repo.revoke(db, session_id=session_id, user_id=user_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or already revoked.",
            )

    def verify_email(self, db: Session, raw_token: str) -> User:
        """Validates one-time email verification token and marks user verified."""
        token_hash_val = hash_token(raw_token)
        token_record = self.token_repo.get_verification_token(db, token_hash_val)

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used verification token.",
            )

        now = datetime.now(UTC)
        if token_record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new one.",
            )

        # Atomically mark token as used; fails if concurrent request already claimed it
        claimed = self.token_repo.mark_verification_used(db, token_hash_val)
        if not claimed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used verification token.",
            )

        user = self.user_repo.get_by_id(db, token_record.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        user.is_email_verified = True
        db.commit()
        db.refresh(user)
        return user

    def resend_verification(
        self,
        db: Session,
        email: str,
        client_ip: str | None = None,
    ) -> None:
        """Generates and sends a new verification token, invalidating prior tokens."""
        rate_key = f"resend_verify:{client_ip or email}"
        if not rate_limiter.is_allowed(rate_key, max_requests=3, window_seconds=60):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification requests. Please wait a moment.",
            )

        clean_email = normalize_email(email)
        user = self.user_repo.get_by_email(db, clean_email)

        # Do not leak whether user exists or is already verified
        if not user or user.is_email_verified:
            return

        self.token_repo.invalidate_pending_verification_tokens(db, user.id)

        raw_token = generate_secure_token()
        token_hash_val = hash_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(
            hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )
        self.token_repo.create_verification_token(
            db=db,
            user_id=user.id,
            token_hash=token_hash_val,
            expires_at=expires_at,
        )

        email_service.send_verification_email(
            to_email=user.email,
            full_name=user.full_name,
            raw_token=raw_token,
        )

    def forgot_password(
        self,
        db: Session,
        email: str,
        client_ip: str | None = None,
    ) -> None:
        """Creates a one-time password reset token and emails it without exposing account existence."""
        rate_key = f"forgot_pwd:{client_ip or email}"
        if not rate_limiter.is_allowed(rate_key, max_requests=4, window_seconds=60):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset requests. Please wait a moment.",
            )

        clean_email = normalize_email(email)
        user = self.user_repo.get_by_email(db, clean_email)

        # If user does not exist or is inactive, return silently to prevent enumeration
        if not user or not user.is_active:
            return

        self.token_repo.invalidate_pending_reset_tokens(db, user.id)

        raw_token = generate_secure_token()
        token_hash_val = hash_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        self.token_repo.create_reset_token(
            db=db,
            user_id=user.id,
            token_hash=token_hash_val,
            expires_at=expires_at,
        )

        email_service.send_password_reset_email(
            to_email=user.email,
            full_name=user.full_name,
            raw_token=raw_token,
        )

    def reset_password(self, db: Session, req: ResetPasswordRequest) -> None:
        """Validates reset token, updates password hash with Argon2id, and revokes all active sessions."""
        token_hash_val = hash_token(req.token)
        token_record = self.token_repo.get_reset_token(db, token_hash_val)

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used password reset token.",
            )

        now = datetime.now(UTC)
        if token_record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token has expired. Please request a new one.",
            )

        # Atomically mark token as used; fails if concurrent request already claimed it
        claimed = self.token_repo.mark_reset_used(db, token_hash_val)
        if not claimed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used password reset token.",
            )

        user = self.user_repo.get_by_id(db, token_record.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is invalid or deactivated.",
            )

        # Hash new password
        user.password_hash = hash_password(req.new_password)

        # Revoke ALL existing active sessions
        self.session_repo.revoke_all_for_user(db, user.id)

        db.commit()

    def change_password(
        self,
        db: Session,
        user: User,
        req: ChangePasswordRequest,
        current_token: str | None = None,
    ) -> int:
        """
        Verifies current password with Argon2id, updates password hash, and
        optionally revokes all other active sessions cleanly.
        """
        rate_key = f"change_pwd:{user.id}"
        if not rate_limiter.is_allowed(rate_key, max_requests=5, window_seconds=60):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password change attempts. Please wait a minute and retry.",
            )

        if not verify_password(req.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        if req.current_password == req.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from your current password.",
            )

        user.password_hash = hash_password(req.new_password)
        user.updated_at = datetime.now(UTC)

        revoked_count = 0
        if req.revoke_other_sessions:
            except_session_id = None
            if current_token:
                current_session = self.session_repo.get_by_token_hash(db, hash_token(current_token))
                if current_session and current_session.user_id == user.id:
                    except_session_id = current_session.id
            revoked_count = self.session_repo.revoke_all_for_user(
                db, user.id, except_session_id=except_session_id
            )
        else:
            db.commit()

        return revoked_count
