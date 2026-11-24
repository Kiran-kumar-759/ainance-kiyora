from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import rate_limiter


def test_onboarding_lifecycle(client: TestClient):
    """User starts onboarding, updates preferences, and completes onboarding."""
    rate_limiter.clear()

    email = "onboarding.test@example.in"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Vikram Das", "email": email, "password": "VikramPassword123!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "VikramPassword123!"},
    )
    csrf_token = login_res.cookies.get(settings.CSRF_COOKIE_NAME)

    # 1. Initial Onboarding Status
    status_res = client.get("/api/v1/onboarding")
    assert status_res.status_code == 200
    assert status_res.json()["onboarding_completed"] is False

    # 2. Update Step Data
    step_res = client.patch(
        "/api/v1/onboarding",
        json={"preferred_currency": "INR", "timezone": "Asia/Kolkata"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert step_res.status_code == 200
    assert step_res.json()["onboarding_completed"] is False

    # 3. Complete Onboarding
    complete_res = client.post(
        "/api/v1/onboarding/complete",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["onboarding_completed"] is True


def test_onboarding_skip(client: TestClient):
    """User skips all optional onboarding steps."""
    rate_limiter.clear()

    email = "skip.test@example.in"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Tara Sen", "email": email, "password": "TaraPassword123!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TaraPassword123!"},
    )
    csrf_token = login_res.cookies.get(settings.CSRF_COOKIE_NAME)

    # Skip
    skip_res = client.post(
        "/api/v1/onboarding/skip",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert skip_res.status_code == 200
    assert skip_res.json()["onboarding_completed"] is True
