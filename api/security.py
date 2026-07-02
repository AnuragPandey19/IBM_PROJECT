"""Password hashing + JWT create/verify.

Uses bcrypt directly (not via passlib) because passlib 1.7.4 is broken with
modern bcrypt on Windows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from api.config import get_settings

settings = get_settings()

_BCRYPT_MAX_BYTES = 72


def _prepare(plaintext: str) -> bytes:
    b = plaintext.encode("utf-8")
    if len(b) > _BCRYPT_MAX_BYTES:
        b = b[:_BCRYPT_MAX_BYTES]
    return b


def hash_password(plaintext: str) -> str:
    hashed = bcrypt.hashpw(_prepare(plaintext), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plaintext), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject, extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
