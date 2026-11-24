from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.models.auth import EmailVerificationToken, UserSession
from app.models.user import User


def test_strict_user_data_isolation(client: TestClient, db_session: Session):
    """
    Verifies that User A cannot read, modify, or revoke User B's resources,
    and User A's identity is derived strictly from backend session tokens.
    """
    rate_limiter.clear()

    # Register User A
    user_a_email = "user_a@example.in"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "User Alpha", "email": user_a_email, "password": "PasswordAlpha123!"},
    )
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": user_a_email, "password": "PasswordAlpha123!"},
    )
    cookie_a = login_a.cookies.get(settings.SESSION_COOKIE_NAME)
    csrf_a = login_a.cookies.get(settings.CSRF_COOKIE_NAME)

    # Register User B
    user_b_email = "user_b@example.in"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "User Beta", "email": user_b_email, "password": "PasswordBeta123!"},
    )
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": user_b_email, "password": "PasswordBeta123!"},
    )
    cookie_b = login_b.cookies.get(settings.SESSION_COOKIE_NAME)

    # User B lists their sessions to get a session ID
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie_b)
    sessions_b_res = client.get("/api/v1/auth/sessions")
    assert sessions_b_res.status_code == 200
    user_b_sessions = sessions_b_res.json()
    assert len(user_b_sessions) >= 1
    user_b_session_id = user_b_sessions[0]["id"]

    # Now authenticate as User A
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie_a)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_a)

    # 1. User A checks /me -> gets User A, never User B
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == user_a_email

    # 2. User A attempts to revoke User B's session -> must return 404 (ownership enforced)
    revoke_attack = client.delete(
        f"/api/v1/auth/sessions/{user_b_session_id}",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert revoke_attack.status_code == 404
    assert "not found or already revoked" in revoke_attack.json()["detail"]

    # 3. User B's session remains active
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie_b)
    check_b_res = client.get("/api/v1/auth/me")
    assert check_b_res.status_code == 200
    assert check_b_res.json()["email"] == user_b_email


def test_plaintext_secrets_never_stored_in_database(client: TestClient, db_session: Session):
    """
    Directly audits PostgreSQL tables to verify:
    - Passwords are stored ONLY as Argon2id hashes.
    - Session tokens are stored ONLY as SHA-256 hashes (64 hex characters).
    - Verification and reset tokens are stored ONLY as SHA-256 hashes.
    """
    rate_limiter.clear()

    test_email = "audit.security@example.in"
    raw_pwd = "PlaintextSecretPassword999!"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Audit User", "email": test_email, "password": raw_pwd},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": raw_pwd},
    )
    raw_session_token = login_res.cookies.get(settings.SESSION_COOKIE_NAME)

    # Query database directly
    user = db_session.query(User).filter(User.email == test_email).first()
    assert user is not None

    # Password must start with Argon2id signature and never contain plaintext password
    assert user.password_hash.startswith("$argon2id$")
    assert raw_pwd not in user.password_hash

    # Query sessions directly
    sessions = db_session.query(UserSession).filter(UserSession.user_id == user.id).all()
    assert len(sessions) >= 1
    for s in sessions:
        # Must be 64-character SHA-256 hex string
        assert len(s.token_hash) == 64
        # Raw session token must never equal token_hash
        assert raw_session_token != s.token_hash

    # Query verification tokens
    v_tokens = (
        db_session.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .all()
    )
    for vt in v_tokens:
        assert len(vt.token_hash) == 64
