"""Sign-in via Google or Microsoft ID tokens.

The browser signs the user in with Google Identity Services or MSAL and
sends the resulting ID token as `Authorization: Bearer <token>`. This module
verifies the signature against the provider's published keys and turns the
token into a `User` keyed by lowercase email, so the same person gets the
same deals whichever provider they used. Username is the part of the email
before the "@".

Microsoft emails are only trusted when the token comes from the configured
tenant (MICROSOFT_TENANT_ID): in a multi-tenant app the email claim is not
verified by Microsoft, so accepting any tenant would let someone claim another
person's address.
"""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.demo import DEMO_AUDIENCE, DEMO_ISSUER, ensure_sample_deals, is_demo_email

GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
MICROSOFT_JWKS_URL = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
MICROSOFT_ISSUER = "https://login.microsoftonline.com/{tenant}/v2.0"

DEV_USER_EMAIL = "dev@localhost"


@dataclass(frozen=True)
class User:
    email: str

    @property
    def username(self) -> str:
        return self.email.split("@", 1)[0]


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    # Caches the provider's keys in-process; refetches when an unknown key id appears.
    return PyJWKClient(url, cache_keys=True)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def _decode(token: str, *, jwks_url: str, audience: str, issuer: str | list[str]) -> dict:
    try:
        key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired sign-in token.") from exc


def _verify_google(token: str, settings: Settings) -> str:
    claims = _decode(
        token,
        jwks_url=GOOGLE_JWKS_URL,
        audience=settings.GOOGLE_CLIENT_ID,
        issuer=list(GOOGLE_ISSUERS),
    )
    if claims.get("email_verified") is not True or not claims.get("email"):
        raise _unauthorized("Google account has no verified email.")
    return claims["email"]


def _verify_microsoft(token: str, settings: Settings) -> str:
    tenant = settings.MICROSOFT_TENANT_ID
    claims = _decode(
        token,
        jwks_url=MICROSOFT_JWKS_URL.format(tenant=tenant),
        audience=settings.MICROSOFT_CLIENT_ID,
        issuer=MICROSOFT_ISSUER.format(tenant=tenant),
    )
    email = claims.get("email") or claims.get("preferred_username")
    if not email or "@" not in email:
        raise _unauthorized("Microsoft account has no email address.")
    return email


def _verify_demo(token: str, settings: Settings) -> str:
    try:
        claims = jwt.decode(
            token,
            settings.DEMO_TOKEN_SECRET.get_secret_value(),
            algorithms=["HS256"],
            audience=DEMO_AUDIENCE,
            issuer=DEMO_ISSUER,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired demo token.") from exc
    email = str(claims.get("email", ""))
    if not is_demo_email(email):
        raise _unauthorized("Invalid demo token.")
    return email


def _issuer_of(token: str) -> str:
    try:
        return str(jwt.decode(token, options={"verify_signature": False}).get("iss", ""))
    except jwt.PyJWTError as exc:
        raise _unauthorized("Malformed sign-in token.") from exc


def _check_domain(email: str, settings: Settings) -> None:
    allowed = settings.allowed_email_domains_list
    if allowed and email.rsplit("@", 1)[-1] not in allowed:
        raise HTTPException(status_code=403, detail="This email domain is not allowed.")


# Emails already given their starting deals by this process, so most requests skip the check.
_seeded: set[str] = set()


def _welcome(db: Session, user: User) -> User:
    if user.email not in _seeded:
        ensure_sample_deals(db, user.email)
        _seeded.add(user.email)
    return user


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> User:
    if not settings.AUTH_REQUIRED:
        return _welcome(db, User(email=DEV_USER_EMAIL))

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("Sign in required.")
    token = token.strip()

    issuer = _issuer_of(token)
    if issuer == DEMO_ISSUER and settings.demo_configured:
        # Demo accounts are throwaway and skip the email-domain allowlist.
        return _welcome(db, User(email=_verify_demo(token, settings)))
    if issuer in GOOGLE_ISSUERS and settings.GOOGLE_CLIENT_ID:
        email = _verify_google(token, settings)
    elif (
        settings.MICROSOFT_CLIENT_ID
        and settings.MICROSOFT_TENANT_ID
        and issuer == MICROSOFT_ISSUER.format(tenant=settings.MICROSOFT_TENANT_ID)
    ):
        email = _verify_microsoft(token, settings)
    else:
        raise _unauthorized("Unsupported sign-in provider.")

    email = email.strip().lower()
    _check_domain(email, settings)
    return _welcome(db, User(email=email))


def current_owner(user: User = Depends(current_user)) -> str:
    """The key deals are stored under (lowercase email)."""
    return user.email
