"""Accounts and access: password hashing, signed tokens, and who may read or change which profile.

- An account owns profiles. The shared demo profile has no owner: everyone signed in may read and analyse it,
  nobody may change it.
- Someone else's profile answers 404, so its existence isn't revealed.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from .config import settings
from .db import SessionLocal
from .models import Profile, User

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
FILE_LINK_MINUTES = 5            # how long an "open the original report" link works
MIN_SECRET_CHARS = 32
WEAK_SECRETS = {"change-this-secret-in-env", "changeme", "secret"}
SECRET_HELP = ('Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))" '
               "and add HORMONY_AUTH_SECRET=<value> to backend/.env")

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


class AuthConfigError(RuntimeError):
    pass


def check_secret(secret: Optional[str] = None) -> str:
    """Tokens signed with a missing, default or short secret can be forged, so the server won't run with one."""
    s = settings.auth_secret if secret is None else secret
    if not s or s in WEAK_SECRETS or len(s) < MIN_SECRET_CHARS:
        raise AuthConfigError(f"HORMONY_AUTH_SECRET must be a random value of at least {MIN_SECRET_CHARS} characters. "
                              + SECRET_HELP)
    return s


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def _encode(claims: dict, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({**claims, "iat": now, "exp": now + ttl}, check_secret(), algorithm=ALGORITHM)


def decode(token: str, typ: str) -> dict:
    """Verify a token and that it is the expected kind (a sign-in, or a link to one file)."""
    claims = jwt.decode(token, check_secret(), algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    if claims.get("typ") != typ:
        raise jwt.InvalidTokenError("wrong token type")
    return claims


def create_access_token(user_id: str) -> str:
    return _encode({"sub": user_id, "typ": "access"}, timedelta(hours=TOKEN_EXPIRE_HOURS))


def create_file_token(user_id: str, pid: str, report_id: str) -> str:
    return _encode({"sub": user_id, "typ": "file", "pid": pid, "rid": report_id}, timedelta(minutes=FILE_LINK_MINUTES))


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def user_by_id(user_id: str) -> Optional[User]:
    db = SessionLocal()
    try:
        return db.get(User, user_id)
    finally:
        db.close()


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> User:
    if credentials is None:
        raise _unauthorized("Sign in to continue")
    try:
        claims = decode(credentials.credentials, "access")
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Your session has expired. Sign in again.")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid authentication token")
    user = user_by_id(claims["sub"])
    if user is None:
        raise _unauthorized("Account not found")
    return user


def readable_profile(pid: str, user: User) -> Profile:
    """Your own profiles and the shared demo. Anything else doesn't exist as far as you can tell."""
    db = SessionLocal()
    try:
        p = db.get(Profile, pid)
    finally:
        db.close()
    if p is None or not (p.kind == "demo" or p.owner_id == user.id):
        raise HTTPException(404, "unknown profile")
    return p


def writable_profile(pid: str, user: User) -> Profile:
    p = readable_profile(pid, user)
    if p.owner_id != user.id:
        raise HTTPException(403, "The demo is read-only. Start your own record to add data.")
    return p


class FailedLogins:
    """Wrong passwords per (email, client): after `limit` failures in `window` seconds, sign-in pauses."""

    def __init__(self, limit: int = 5, window: float = 15 * 60):
        self.limit, self.window = limit, window
        self.hits: dict = defaultdict(deque)

    def _recent(self, key) -> deque:
        q, now = self.hits[key], time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            self.hits.pop(key, None)
        return q

    def retry_after(self, key) -> int:
        q = self._recent(key)
        return int(self.window - (time.monotonic() - q[0])) + 1 if len(q) >= self.limit else 0

    def fail(self, key) -> None:
        self.hits[key].append(time.monotonic())

    def clear(self, key) -> None:
        self.hits.pop(key, None)


FAILED_LOGINS = FailedLogins()
