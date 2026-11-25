import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid

from app.core.config import settings


def create_oauth_state(user_id: uuid.UUID, redirect_uri: str, ttl_seconds: int = 600) -> str:
    """Generates an HMAC-SHA256 signed OAuth state token bound to user_id and redirect_uri."""
    payload = {
        "uid": str(user_id),
        "ruri": redirect_uri,
        "nonce": secrets.token_urlsafe(12),
        "exp": int(time.time()) + ttl_seconds,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_oauth_state(state_token: str, expected_user_id: uuid.UUID) -> dict:
    """Validates HMAC signature, expiration, and strict user ownership of OAuth state."""
    if not state_token or "." not in state_token:
        raise ValueError("Malformed OAuth state parameter.")
    b64, sig = state_token.split(".", 1)
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not secrets.compare_digest(sig, expected_sig):
        raise ValueError("Invalid OAuth state signature.")
    try:
        payload = json.loads(base64.urlsafe_b64decode(b64.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Corrupted OAuth state payload.") from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("OAuth state expired. Please restart Gmail authorization.")
    if payload.get("uid") != str(expected_user_id):
        raise ValueError("OAuth state user binding mismatch.")
    return payload
