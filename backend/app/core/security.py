import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# Configure Argon2id with OWASP recommended parameters
# memory_cost=65536 (64 MB), time_cost=3, parallelism=4
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id hash in constant time.
    Returns False if hash is invalid or does not match.
    """
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_secure_token() -> str:
    """Generates a cryptographically secure 256-bit URL-safe random string."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """
    Computes SHA-256 hash of an opaque token for database storage.
    Raw tokens are never persisted to the database.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_token(secret_key: str | None = None) -> str:
    """
    Generates a cryptographically secure HMAC-SHA256 signed CSRF token.
    Format: <raw_hex>.<signature>
    Prevents cookie injection and subdomain-based forged cookie attacks.
    """
    key = (secret_key or settings.SECRET_KEY).encode("utf-8")
    raw = secrets.token_hex(32)
    sig = hmac.new(key, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_csrf_token_signature(token: str, secret_key: str | None = None) -> bool:
    """Verifies that a CSRF token was cryptographically signed by the server's secret key."""
    if not token or "." not in token:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    raw, sig = parts
    key = (secret_key or settings.SECRET_KEY).encode("utf-8")
    expected_sig = hmac.new(key, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return secrets.compare_digest(sig, expected_sig)


def normalize_email(email: str) -> str:
    """Normalizes an email address to lowercase and strips whitespace."""
    return email.strip().lower()
