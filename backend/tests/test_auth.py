from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.services.email_service import email_service


def test_register_success(client: TestClient):
    """User registration succeeds, persists user and preferences, and sends verification email."""
    rate_limiter.clear()
    email_service.clear_mailbox()

    payload = {
        "full_name": "Aarav Sharma",
        "email": "aarav.sharma@example.in",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Registration successful. Please verify your email."
    assert data["user"]["email"] == "aarav.sharma@example.in"
    assert data["user"]["full_name"] == "Aarav Sharma"
    assert data["user"]["is_email_verified"] is False
    assert data["user"]["onboarding_completed"] is False
    assert data["email_delivery_status"] == "sent"

    # Verify email was captured in email service
    assert len(email_service.get_sent_messages()) == 1
    assert email_service.get_sent_messages()[0].to_email == "aarav.sharma@example.in"


def test_register_duplicate_email_rejected(client: TestClient):
    """Registering an existing email address (even with different casing) returns 409 Conflict."""
    rate_limiter.clear()

    payload1 = {
        "full_name": "Rohan Patel",
        "email": "rohan.patel@example.in",
        "password": "Password123!",
    }
    res1 = client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "full_name": "Rohan Patel",
        "email": "ROHAN.PATEL@example.in",
        "password": "AnotherPassword456!",
    }
    res2 = client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_login_success_and_cookie_generation(client: TestClient):
    """Login succeeds with valid credentials, sets HttpOnly session and CSRF cookies."""
    rate_limiter.clear()

    # Register user
    reg_payload = {
        "full_name": "Priya Nair",
        "email": "priya.nair@example.in",
        "password": "PriyaPassword789!",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # Login
    login_payload = {
        "email": "priya.nair@example.in",
        "password": "PriyaPassword789!",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful."
    assert response.json()["user"]["email"] == "priya.nair@example.in"

    # Check cookies
    cookies = response.cookies
    assert settings.SESSION_COOKIE_NAME in cookies
    assert settings.CSRF_COOKIE_NAME in cookies


def test_login_invalid_credentials(client: TestClient):
    """Login fails with 401 when given invalid password or unknown email."""
    rate_limiter.clear()

    # Unknown email
    res1 = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.in", "password": "WrongPassword!"},
    )
    assert res1.status_code == 401
    assert "Invalid email or password" in res1.json()["detail"]


def test_session_restoration_and_logout(client: TestClient):
    """Tests GET /me session restoration and subsequent POST /logout revocation."""
    rate_limiter.clear()

    # Register and login
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ananya Roy",
            "email": "ananya.roy@example.in",
            "password": "AnanyaPassword123!",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "ananya.roy@example.in", "password": "AnanyaPassword123!"},
    )
    csrf_token = login_res.cookies.get(settings.CSRF_COOKIE_NAME)

    # GET /auth/me with session cookie
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "ananya.roy@example.in"

    # Logout
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == 200

    # Next GET /auth/me should fail with 401
    me_after = client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


def test_csrf_protection_on_mutating_requests(client: TestClient):
    """Mutating state requests require matching CSRF header and cookie."""
    rate_limiter.clear()

    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dev Sharma",
            "email": "dev.sharma@example.in",
            "password": "DevPassword123!",
        },
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "dev.sharma@example.in", "password": "DevPassword123!"},
    )

    # Attempt logout without X-CSRF-Token header -> 403 Forbidden
    res_no_header = client.post("/api/v1/auth/logout")
    assert res_no_header.status_code == 403

    # Attempt with wrong X-CSRF-Token header -> 403 Forbidden
    res_bad_header = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "invalid_csrf_token_value"},
    )
    assert res_bad_header.status_code == 403


def test_email_verification_flow(client: TestClient):
    """User verifies email using valid token, and token cannot be reused."""
    rate_limiter.clear()
    email_service.clear_mailbox()

    email = "verification.test@example.in"
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Kavita Rao",
            "email": email,
            "password": "KavitaPassword123!",
        },
    )

    raw_token = email_service.get_latest_token_for(email)
    assert raw_token is not None

    # Verify email
    verify_res = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert verify_res.status_code == 200
    assert verify_res.json()["user"]["is_email_verified"] is True

    # Token reuse attempt should fail with 400
    reuse_res = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert reuse_res.status_code == 400
    assert "Invalid or already used" in reuse_res.json()["detail"]


def test_password_reset_flow(client: TestClient):
    """User requests password reset, updates password, and previous sessions are revoked."""
    rate_limiter.clear()
    email_service.clear_mailbox()

    email = "reset.test@example.in"
    old_pwd = "OldPassword123!"
    new_pwd = "NewSecurePassword456!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Siddharth Sen", "email": email, "password": old_pwd},
    )
    # Login to create an active session
    client.post("/api/v1/auth/login", json={"email": email, "password": old_pwd})

    # Request password reset
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200

    raw_token = email_service.get_latest_token_for(email)
    assert raw_token is not None

    # Reset password
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": new_pwd},
    )
    assert reset_res.status_code == 200

    # Old password no longer works
    fail_login = client.post("/api/v1/auth/login", json={"email": email, "password": old_pwd})
    assert fail_login.status_code == 401

    # New password works
    success_login = client.post("/api/v1/auth/login", json={"email": email, "password": new_pwd})
    assert success_login.status_code == 200
