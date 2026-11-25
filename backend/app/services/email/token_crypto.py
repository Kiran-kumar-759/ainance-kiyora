import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    raw_key = settings.EMAIL_TOKEN_ENCRYPTION_KEY
    if raw_key:
        try:
            return Fernet(raw_key.encode("utf-8"))
        except Exception:
            digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
            return Fernet(base64.urlsafe_b64encode(digest))

    digest = hashlib.sha256(f"email-oauth:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_oauth_token(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_oauth_token(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored OAuth credential.") from exc
