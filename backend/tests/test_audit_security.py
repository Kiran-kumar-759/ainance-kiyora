import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.rate_limit import rate_limiter
from app.core.security import generate_csrf_token
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import RegisterRequest, ResetPasswordRequest
from app.services.auth_service import AuthService
from app.services.email_service import EmailMessage, email_service


def test_csrf_cookie_injection_protection(client: TestClient):
    """
    Verifies that unsigned/injected CSRF cookies (e.g. from compromised subdomains or MitM)
    are strictly rejected with HTTP 403 Forbidden.
    """
    # 1. Attacker injects arbitrary matching cookie and header
    injected_token = "attacker_forged_cookie_1234567890abcdef"
    res1 = client.post(
        "/api/v1/auth/logout",
        cookies={settings.CSRF_COOKIE_NAME: injected_token},
        headers={settings.CSRF_HEADER_NAME: injected_token},
    )
    assert res1.status_code == 403
    assert "signature is invalid or forged" in res1.json()["detail"]

    # 2. Attacker modifies a legitimately issued token's signature
    valid_token = generate_csrf_token()
    tampered_token = valid_token[:-4] + "dead"
    res2 = client.post(
        "/api/v1/auth/logout",
        cookies={settings.CSRF_COOKIE_NAME: tampered_token},
        headers={settings.CSRF_HEADER_NAME: tampered_token},
    )
    assert res2.status_code == 403
    assert "signature is invalid or forged" in res2.json()["detail"]

    # 3. Legitimate server-signed CSRF token succeeds
    res3 = client.post(
        "/api/v1/auth/logout",
        cookies={settings.CSRF_COOKIE_NAME: valid_token},
        headers={settings.CSRF_HEADER_NAME: valid_token},
    )
    assert res3.status_code == 200


def test_concurrent_verification_token_consumption():
    """
    Verifies that concurrent requests attempting to consume the same email verification token
    are safely serialized by PostgreSQL atomic conditional updates. Exactly one must succeed.
    """
    rate_limiter.clear()
    email_service.clear_mailbox()
    email = f"audit.concurrent.verify.{uuid.uuid4().hex[:8]}@example.in"

    setup_db = SessionLocal()
    auth_service = AuthService()
    auth_service.register(
        setup_db,
        RegisterRequest(full_name="Concurrent User", email=email, password="Password123!"),
    )
    setup_db.close()

    token = email_service.get_latest_token_for(email)
    assert token is not None

    results = []

    def verify_attempt():
        thread_db = SessionLocal()
        try:
            auth_service.verify_email(thread_db, token)
            results.append("success")
        except Exception as e:
            results.append(f"error: {e}")
        finally:
            thread_db.close()

    t1 = threading.Thread(target=verify_attempt)
    t2 = threading.Thread(target=verify_attempt)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one thread succeeded; the other failed with HTTP 400
    assert results.count("success") == 1
    assert any("400" in r for r in results if r != "success")


def test_concurrent_password_reset_token_consumption():
    """
    Verifies that concurrent requests attempting to consume the same password reset token
    are safely serialized. Exactly one must succeed.
    """
    rate_limiter.clear()
    email_service.clear_mailbox()
    email = f"audit.concurrent.reset.{uuid.uuid4().hex[:8]}@example.in"

    setup_db = SessionLocal()
    auth_service = AuthService()
    auth_service.register(
        setup_db,
        RegisterRequest(full_name="Concurrent Reset", email=email, password="Password123!"),
    )
    auth_service.forgot_password(setup_db, email=email)
    setup_db.close()

    token = email_service.get_latest_token_for(email)
    assert token is not None

    results = []

    def reset_attempt(new_pwd: str):
        thread_db = SessionLocal()
        try:
            auth_service.reset_password(
                thread_db, ResetPasswordRequest(token=token, new_password=new_pwd)
            )
            results.append("success")
        except Exception as e:
            results.append(f"error: {e}")
        finally:
            thread_db.close()

    t1 = threading.Thread(target=reset_attempt, args=("NewPass1!",))
    t2 = threading.Thread(target=reset_attempt, args=("NewPass2!",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one thread succeeded
    assert results.count("success") == 1
    assert any("400" in r for r in results if r != "success")


def test_onboarding_step_persistence_and_session_restore(client: TestClient, db_session: Session):
    """
    Verifies that onboarding progress (step position, name, regional preferences)
    persists across session restoration and allows resuming from the saved step.
    """
    rate_limiter.clear()
    email = "audit.onboarding.resume@example.in"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Onboard User", "email": email, "password": "Password123!"},
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    session_cookie = login_res.cookies[settings.SESSION_COOKIE_NAME]
    csrf_cookie = login_res.cookies[settings.CSRF_COOKIE_NAME]

    auth_cookies = {
        settings.SESSION_COOKIE_NAME: session_cookie,
        settings.CSRF_COOKIE_NAME: csrf_cookie,
    }
    auth_headers = {settings.CSRF_HEADER_NAME: csrf_cookie}

    # Step 1 -> Advance to Step 2
    res_step2 = client.patch(
        "/api/v1/onboarding",
        cookies=auth_cookies,
        headers=auth_headers,
        json={"full_name": "Onboard User Updated", "current_step": 2},
    )
    assert res_step2.status_code == 200
    assert res_step2.json()["current_step"] == 2
    assert res_step2.json()["full_name"] == "Onboard User Updated"

    # Step 2 -> Advance to Step 3 with regional preferences
    res_step3 = client.patch(
        "/api/v1/onboarding",
        cookies=auth_cookies,
        headers=auth_headers,
        json={
            "current_step": 3,
            "preferred_currency": "INR",
            "timezone": "Asia/Kolkata",
            "date_format": "DD/MM/YYYY",
        },
    )
    assert res_step3.status_code == 200
    assert res_step3.json()["current_step"] == 3
    assert res_step3.json()["preferences"]["timezone"] == "Asia/Kolkata"

    # Simulate closing/refreshing browser: Fetch GET /onboarding with restored session
    restore_res = client.get("/api/v1/onboarding", cookies=auth_cookies)
    assert restore_res.status_code == 200
    data = restore_res.json()
    assert data["current_step"] == 3
    assert data["preferences"]["preferred_currency"] == "INR"
    assert data["preferences"]["timezone"] == "Asia/Kolkata"
    assert data["onboarding_completed"] is False

    # Complete onboarding
    comp_res = client.post(
        "/api/v1/onboarding/complete",
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["onboarding_completed"] is True

    # Verify directly in PostgreSQL using the test transaction session
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.onboarding_completed is True
    assert user.full_name == "Onboard User Updated"


def test_production_security_guards():
    """
    Verifies that Settings model validators strictly prevent running in production
    with insecure cookies or default development secret keys.
    """
    # 1. In production, COOKIE_SECURE is automatically enforced to True
    prod_settings = Settings(
        ENVIRONMENT="production",
        COOKIE_SECURE=False,
        SECRET_KEY="a-very-strong-unique-production-secret-key-987654321",
    )
    assert prod_settings.COOKIE_SECURE is True

    # 2. In production, default dev secret key raises ValueError
    with pytest.raises(ValueError, match="SECRET_KEY must be configured"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev-insecure-secret-key-change-in-production-123456789",
        )


def test_smtp_delivery_and_graceful_failure():
    """
    Verifies email service delivery behavior:
    - Captures messages in in-memory mailbox when SMTP_ENABLED=False.
    - Gracefully catches and logs errors when SMTP is enabled but unreachable.
    """
    email_service.clear_mailbox()
    msg = EmailMessage(
        to_email="test.smtp@example.com",
        subject="Test SMTP",
        html_content="<p>Test</p>",
        plain_content="Test",
        token="tok123",
    )

    # In dev mode (SMTP_ENABLED=False)
    delivered = email_service._deliver(msg)
    assert delivered is True
    assert len(email_service.get_sent_messages()) == 1

    # In SMTP mode with unreachable port
    orig_smtp_enabled = settings.SMTP_ENABLED
    orig_smtp_port = settings.SMTP_PORT
    try:
        settings.SMTP_ENABLED = True
        settings.SMTP_PORT = 65534  # Unreachable port
        delivered_failed = email_service._deliver(msg)
        assert delivered_failed is False  # Graceful failure handling
    finally:
        settings.SMTP_ENABLED = orig_smtp_enabled
        settings.SMTP_PORT = orig_smtp_port
