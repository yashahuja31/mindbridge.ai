"""Auth primitives: password hashing (bcrypt) + JWT access tokens (HS256), plus the FastAPI
dependencies that turn a bearer token back into a `User`.

bcrypt is used directly (no passlib). JWTs are signed with `settings.secret_key` — override it in
production via `MINDBRIDGE_SECRET_KEY`; the default is intentionally an obvious placeholder.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from mindbridge.config import settings
from mindbridge.web.db import get_db
from mindbridge.web.models import User

_ALGORITHM = "HS256"
# auto_error=False so the *optional* dependency can run for anonymous callers; the required
# dependency raises 401 itself.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# bcrypt hashes at most the first 72 bytes of a password; longer inputs must be pre-truncated or
# bcrypt raises. We truncate the encoded bytes so hashing and verifying agree on the same prefix.
_BCRYPT_MAX_BYTES = 72


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """Mint a signed JWT whose `sub` is the user id (as a string)."""
    minutes = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {"sub": str(subject), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def _decode_user_id(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Optional[str] = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Required auth: resolve the bearer token to a User or raise 401."""
    if not token:
        raise _CREDENTIALS_EXC
    user_id = _decode_user_id(token)
    if user_id is None:
        raise _CREDENTIALS_EXC
    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    return user


def get_optional_user(
    token: Optional[str] = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> Optional[User]:
    """Optional auth: return the User if a valid token is present, else None (never raises).
    Lets endpoints serve anonymous callers while still personalizing/persisting for signed-in ones."""
    if not token:
        return None
    user_id = _decode_user_id(token)
    if user_id is None:
        return None
    return db.get(User, user_id)
