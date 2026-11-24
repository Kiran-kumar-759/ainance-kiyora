from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import rate_limiter


def test_user_profile_and_preferences_lifecycle(client: TestClient):
    """User views and updates their own profile and preferences."""
    rate_limiter.clear()

    # Register and login
    email = "profile.test@example.in"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Meera Iyer", "email": email, "password": "MeeraPassword123!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "MeeraPassword123!"},
    )
    csrf_token = login_res.cookies.get(settings.CSRF_COOKIE_NAME)

    # 1. Get Profile
    profile_res = client.get("/api/v1/users/me")
    assert profile_res.status_code == 200
    assert profile_res.json()["full_name"] == "Meera Iyer"

    # 2. Update Profile Name
    update_res = client.patch(
        "/api/v1/users/me",
        json={"full_name": "Meera Krishna Iyer"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert update_res.status_code == 200
    assert update_res.json()["full_name"] == "Meera Krishna Iyer"

    # 3. Get Default Preferences
    pref_res = client.get("/api/v1/users/me/preferences")
    assert pref_res.status_code == 200
    pref_data = pref_res.json()
    assert pref_data["preferred_currency"] == "INR"
    assert pref_data["locale"] == "en-IN"
    assert pref_data["timezone"] == "Asia/Kolkata"

    # 4. Update Preferences
    pref_update_res = client.patch(
        "/api/v1/users/me/preferences",
        json={"date_format": "YYYY-MM-DD", "notification_preferences": {"sms_alerts": False}},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert pref_update_res.status_code == 200
    assert pref_update_res.json()["date_format"] == "YYYY-MM-DD"
    assert pref_update_res.json()["notification_preferences"]["sms_alerts"] is False
