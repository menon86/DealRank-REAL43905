"""Username/password sign-in.

Passwords are hashed with scrypt (stdlib, no extra dependency). Signing in
returns an opaque bearer token; the browser sends it as
`Authorization: Bearer <token>` and every API route except /health and
/auth/* requires it (see app/main.py). Only a SHA-256 of each token is kept
in user_sessions, and signing out deletes that row.
"""

import base64
import hashlib
import hmac
import math
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.demo_deals import add_demo_deals
from app.models.user import User, UserSession
from app.services.rate_limit import auth_limiter, client_key

# scrypt cost: ~16 MiB and a few tens of ms per hash.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    b64 = base64.b64encode
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Checked against when the username doesn't exist, so a login for an unknown
# user takes as long as one with a wrong password.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: the signed-in user, or 401."""
    token = _bearer_token(request)
    if token is not None:
        session = db.get(UserSession, _hash_token(token))
        if session is not None and session.expires_at > datetime.now(UTC):
            user = db.get(User, session.user_id)
            if user is not None:
                return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_owner(user: User = Depends(require_user)) -> str:
    """FastAPI dependency: the value stored in deals.owner_id for the signed-in user."""
    return str(user.id)


# ---- API ----

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserOut(BaseModel):
    username: str


class SessionOut(BaseModel):
    token: str
    user: UserOut


def _rate_limit(request: Request, settings: Settings) -> None:
    retry_after = auth_limiter.check(client_key(request), settings.AUTH_RATE_LIMIT_PER_MIN)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Wait a minute and try again.",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )


def _start_session(db: Session, user: User, settings: Settings) -> SessionOut:
    now = datetime.now(UTC)
    # Clear this user's expired sessions while we're here, so the table doesn't grow forever.
    db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at <= now)
    )
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            expires_at=now + timedelta(days=settings.SESSION_TTL_DAYS),
        )
    )
    db.commit()
    return SessionOut(token=token, user=UserOut(username=user.username))


@router.post("/register", response_model=SessionOut, status_code=201)
def register(
    payload: Credentials,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionOut:
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="New accounts are turned off.")
    _rate_limit(request, settings)
    username = payload.username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=422,
            detail="Usernames are 3-32 characters: letters, numbers, dots, dashes, underscores.",
        )
    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Passwords need at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise HTTPException(status_code=409, detail="That username is taken.")
    user = User(username=username, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    # Every account starts with its own copy of the demo deals.
    add_demo_deals(db, str(user.id))
    return _start_session(db, user, settings)


@router.post("/login", response_model=SessionOut)
def login(
    payload: Credentials,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionOut:
    _rate_limit(request, settings)
    username = payload.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    valid = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    return _start_session(db, user, settings)


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> None:
    token = _bearer_token(request)
    if token is not None:
        db.execute(delete(UserSession).where(UserSession.token_hash == _hash_token(token)))
        db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)) -> UserOut:
    return UserOut(username=user.username)
