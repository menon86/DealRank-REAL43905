"""Username/password sign-in (app/auth.py)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth import hash_password, verify_password
from app.models.user import User, UserSession


def _register(client, username="alice", password="correct horse"):
    return client.post("/auth/register", json={"username": username, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_round_trip():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("scrypt$") and "s3cret-pass" not in stored
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret-pass", "garbage")


def test_api_requires_sign_in(anon_client):
    assert anon_client.get("/deals").status_code == 401
    assert anon_client.get("/deals", headers=_auth("not-a-token")).status_code == 401
    assert anon_client.get("/health").status_code == 200


def test_register_then_use_api(anon_client, db_session):
    res = _register(anon_client, username="  Alice ")
    assert res.status_code == 201
    body = res.json()
    assert body["user"] == {"username": "alice"}
    token = body["token"]
    assert anon_client.get("/deals", headers=_auth(token)).status_code == 200
    assert anon_client.get("/auth/me", headers=_auth(token)).json() == {"username": "alice"}
    # Stored hashed, never in plain text.
    user = db_session.scalar(select(User).where(User.username == "alice"))
    assert "correct horse" not in user.password_hash
    assert db_session.scalar(select(UserSession.token_hash)) != token


def test_login_and_logout(anon_client):
    _register(anon_client)
    res = anon_client.post("/auth/login", json={"username": "ALICE", "password": "correct horse"})
    assert res.status_code == 200
    token = res.json()["token"]
    assert anon_client.get("/auth/me", headers=_auth(token)).status_code == 200

    assert anon_client.post("/auth/logout", headers=_auth(token)).status_code == 204
    assert anon_client.get("/auth/me", headers=_auth(token)).status_code == 401


def test_login_rejects_bad_credentials(anon_client):
    _register(anon_client)
    wrong_pw = anon_client.post("/auth/login", json={"username": "alice", "password": "nope"})
    no_user = anon_client.post("/auth/login", json={"username": "bob", "password": "nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    # Same message either way, so it doesn't reveal which usernames exist.
    assert wrong_pw.json() == no_user.json()


def test_register_validation(anon_client):
    assert _register(anon_client, username="ab").status_code == 422
    assert _register(anon_client, username="has space").status_code == 422
    assert _register(anon_client, password="short").status_code == 422
    assert _register(anon_client).status_code == 201
    assert _register(anon_client, username="ALICE").status_code == 409


def test_expired_session_is_rejected(anon_client, db_session):
    token = _register(anon_client).json()["token"]
    session = db_session.scalar(select(UserSession))
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()
    assert anon_client.get("/auth/me", headers=_auth(token)).status_code == 401


def test_registration_can_be_turned_off(anon_client):
    from app.config import get_settings
    from app.main import app

    settings = get_settings().model_copy(update={"ALLOW_REGISTRATION": False})
    app.dependency_overrides[get_settings] = lambda: settings
    assert _register(anon_client).status_code == 403


def test_sign_in_is_rate_limited(anon_client):
    from app.config import get_settings

    limit = get_settings().AUTH_RATE_LIMIT_PER_MIN
    codes = [
        anon_client.post("/auth/login", json={"username": "x", "password": "y"}).status_code
        for _ in range(limit + 1)
    ]
    assert codes[:limit] == [401] * limit
    assert codes[-1] == 429
