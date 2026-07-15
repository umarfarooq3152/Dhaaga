"""Password hashing and JWT helpers for user authentication."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from app.config import get_settings

JWT_ALGORITHM = "HS256"

# bcrypt enforces a 72-*byte* limit and raises ValueError beyond it, but the
# schema's `max_length=72` is measured in *characters* — a password with
# multi-byte UTF-8 (accents, emoji, non-Latin scripts) can be under 72 chars
# and still exceed 72 bytes. Truncate on the encoded bytes, not the string,
# so such passwords hash/verify instead of raising.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage. Never store plaintext."""
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(_to_bcrypt_bytes(password), password_hash.encode("utf-8"))


def create_access_token(user_id: UUID) -> str:
    """Issue a signed JWT identifying this user, valid for jwt_expiry_days."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_expiry_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> UUID | None:
    """Return the user_id encoded in a token, or None if invalid/expired.

    Never raises — callers treat an invalid token exactly like "not logged
    in" rather than a hard error, since an expired/tampered token on an
    otherwise-anonymous request shouldn't break the request.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
