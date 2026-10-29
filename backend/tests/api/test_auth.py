"""Sign-in: token verification (app/auth.py) and per-user deal isolation.

Tokens are signed with a throwaway RSA key and the JWKS lookup is patched, so
no test touches Google or Microsoft.
"""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import auth
from app.auth import User, current_user
from app.config import Settings, get_settings
from app.db import get_db
from tests.api.conftest import OTHER_OWNER, TEST_OWNER
from tests.api.payloads import STUDENT_HOUSING_PAYLOAD

GOOGLE_ID = "google-client"
MS_ID = "ms-client"
MS_TENANT = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def settings():
    return Settings(
        DATABASE_URL="postgresql://x/y",
        AUTH_REQUIRED=True,
        GOOGLE_CLIENT_ID=GOOGLE_ID,
        MICROSOFT_CLIENT_ID=MS_ID,
        MICROSOFT_TENANT_ID=MS_TENANT,
    )


@pytest.fixture()
def raw_client(db_session, key, settings, monkeypatch):
    """The app with real token verification (no current_user override)."""
    from app.main import app

    monkeypatch.setattr(
        auth,
        "_jwks_client",
        lambda url: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
        ),
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def token(key, **claims):
    body = {"exp": int(time.time()) + 600, **claims}
    return jwt.encode(body, key, algorithm="RS256")


def google_token(key, **over):
    claims = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_ID,
        "email": "Rohan.Menon@Gmail.com",
        "email_verified": True,
    }
    return token(key, **{**claims, **over})


def ms_token(key, tenant=MS_TENANT, **over):
    claims = {
        "iss": f"https://login.microsoftonline.com/{tenant}/v2.0",
        "aud": MS_ID,
        "email": "rmenon@purdue.edu",
    }
    return token(key, **{**claims, **over})


def bearer(t):
    return {"Authorization": f"Bearer {t}"}


# ----------------------------------------------------------- token checks


def test_missing_token_is_401(raw_client):
    assert raw_client.get("/deals").status_code == 401
    assert raw_client.get("/me").status_code == 401


def test_health_stays_open(raw_client):
    assert raw_client.get("/health").status_code == 200


def test_google_token_signs_in_and_username_is_email_prefix(raw_client, key):
    res = raw_client.get("/me", headers=bearer(google_token(key)))
    assert res.status_code == 200
    assert res.json() == {"email": "rohan.menon@gmail.com", "username": "rohan.menon"}


def test_microsoft_token_signs_in(raw_client, key):
    res = raw_client.get("/me", headers=bearer(ms_token(key)))
    assert res.json() == {"email": "rmenon@purdue.edu", "username": "rmenon"}


def test_microsoft_falls_back_to_preferred_username(raw_client, key):
    t = ms_token(key, email=None, preferred_username="x@purdue.edu")
    assert raw_client.get("/me", headers=bearer(t)).json()["email"] == "x@purdue.edu"


@pytest.mark.parametrize(
    "bad",
    [
        lambda k: google_token(k, aud="someone-elses-client"),
        lambda k: google_token(k, exp=int(time.time()) - 10),
        lambda k: google_token(k, email_verified=False),
        lambda k: google_token(k, email=None),
        lambda k: ms_token(k, tenant="99999999-0000-0000-0000-000000000000"),
        lambda k: token(k, iss="https://evil.example", aud=GOOGLE_ID, email="a@b.c"),
        lambda k: "not-a-jwt",
    ],
)
def test_bad_tokens_are_rejected(raw_client, key, bad):
    assert raw_client.get("/me", headers=bearer(bad(key))).status_code == 401


def test_token_signed_with_another_key_is_rejected(raw_client):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert raw_client.get("/me", headers=bearer(google_token(other))).status_code == 401


def test_microsoft_disabled_without_tenant(raw_client, key, settings):
    settings.MICROSOFT_TENANT_ID = ""
    assert raw_client.get("/me", headers=bearer(ms_token(key))).status_code == 401


def test_domain_allowlist(raw_client, key, settings):
    settings.ALLOWED_EMAIL_DOMAINS = "purdue.edu"
    assert raw_client.get("/me", headers=bearer(ms_token(key))).status_code == 200
    assert raw_client.get("/me", headers=bearer(google_token(key))).status_code == 403


def test_auth_disabled_uses_dev_user(raw_client, settings):
    settings.AUTH_REQUIRED = False
    assert raw_client.get("/me").json()["email"] == auth.DEV_USER_EMAIL


def test_same_email_from_either_provider_is_one_user(raw_client, key):
    g = raw_client.get("/me", headers=bearer(google_token(key, email="rmenon@purdue.edu")))
    m = raw_client.get("/me", headers=bearer(ms_token(key)))
    assert g.json()["email"] == m.json()["email"]


# ------------------------------------------------------ deal isolation


@pytest.fixture()
def as_user(client):
    from app.main import app

    def switch(email: str) -> TestClient:
        app.dependency_overrides[current_user] = lambda: User(email=email)
        return client

    return switch


@pytest.fixture()
def my_deal(as_user):
    c = as_user(TEST_OWNER)
    res = c.post("/deals", json=STUDENT_HOUSING_PAYLOAD)
    assert res.status_code == 201
    return res.json()["id"]


def test_new_deal_is_stored_under_the_caller(as_user, db_session, my_deal):
    from app.models.deal import Deal

    assert db_session.get(Deal, my_deal).owner_id == TEST_OWNER


def test_other_user_cannot_list_see_or_change_my_deal(as_user, my_deal):
    c = as_user(OTHER_OWNER)
    assert c.get("/deals").json() == []
    assert c.get(f"/deals/{my_deal}").status_code == 404
    assert c.patch(f"/deals/{my_deal}", json={"name": "hijack"}).status_code == 404
    assert c.get(f"/deals/{my_deal}/metrics").status_code == 404
    assert c.delete(f"/deals/{my_deal}").status_code == 404
    # ...and the owner's deal is untouched.
    c = as_user(TEST_OWNER)
    assert c.get(f"/deals/{my_deal}").json()["name"] == STUDENT_HOUSING_PAYLOAD["name"]


def test_other_user_cannot_analyze_my_deal(as_user, my_deal, spreads):
    c = as_user(OTHER_OWNER)
    ids = [my_deal]
    assert c.post("/rank", json={"deal_ids": ids, "hurdle_rate": "0.08"}).status_code == 404
    assert c.post("/rank/risk-adjusted", json={"deal_ids": ids}).status_code == 404
    assert (
        c.post(f"/deals/{my_deal}/sensitivity", json={"variable": "exit_cap_rate"}).status_code
        == 404
    )
    assert c.post(f"/deals/{my_deal}/monte-carlo", json={}).status_code == 404
    assert c.get(f"/deals/{my_deal}/rent-check", params={"geography": "x"}).status_code == 404
    for kind in ("pdf", "pptx"):
        res = c.get(f"/reports/{kind}", params={"deal_ids": ids, "hurdle_rate": "0.08"})
        assert res.status_code == 404
        assert c.get(f"/reports/{kind}", params={"deal_ids": ids}).status_code == 404


def test_one_foreign_id_fails_a_mixed_rank(as_user, my_deal):
    mine = as_user(OTHER_OWNER).post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()["id"]
    res = as_user(OTHER_OWNER).post(
        "/rank", json={"deal_ids": [mine, my_deal], "hurdle_rate": "0.08"}
    )
    assert res.status_code == 404


def test_chat_tools_only_see_the_callers_deals(db_session, my_deal):
    import json

    from app.api.chat_tools import ToolContext, run_tool

    def names(owner):
        text, ok = run_tool(ToolContext(db=db_session, owner=owner), "list_deals", "{}")
        assert ok
        return [d["name"] for d in json.loads(text)["deals"]]

    assert names(TEST_OWNER) == [STUDENT_HOUSING_PAYLOAD["name"]]
    assert names(OTHER_OWNER) == []
    text, ok = run_tool(
        ToolContext(db=db_session, owner=OTHER_OWNER),
        "get_metrics",
        json.dumps({"deal": my_deal}),
    )
    assert not ok


# ------------------------------------------------------------ demo profile

DEMO_SECRET = "x" * 40


@pytest.fixture()
def demo_on(settings):
    settings.DEMO_ENABLED = True
    settings.DEMO_TOKEN_SECRET = SecretStr(DEMO_SECRET)
    return settings


@pytest.fixture()
def template(db_session):
    from app.demo import DEMO_TEMPLATE_OWNER, clone_deal
    from app.models.deal import Deal

    db_session.add(clone_deal(Deal(**STUDENT_HOUSING_PAYLOAD), DEMO_TEMPLATE_OWNER))
    db_session.flush()


@pytest.fixture(autouse=True)
def _reset_demo_limiter():
    from app.services.rate_limit import demo_limiter

    demo_limiter.reset()


def test_demo_is_404_when_disabled(raw_client):
    assert raw_client.post("/auth/demo").status_code == 404


def test_demo_needs_a_long_secret(raw_client, settings):
    settings.DEMO_ENABLED = True
    settings.DEMO_TOKEN_SECRET = SecretStr("short")
    assert raw_client.post("/auth/demo").status_code == 404


def test_demo_gives_a_private_copy_of_the_template(raw_client, demo_on, template):
    first = raw_client.post("/auth/demo").json()
    second = raw_client.post("/auth/demo").json()
    assert first["email"].endswith("@demo.local") and first["email"] != second["email"]

    deals = raw_client.get("/deals", headers=bearer(first["token"])).json()
    assert [d["name"] for d in deals] == [STUDENT_HOUSING_PAYLOAD["name"]]

    # Editing one visitor's copy leaves the other's (and the template) alone.
    edited = raw_client.patch(
        f"/deals/{deals[0]['id']}", json={"name": "mine"}, headers=bearer(first["token"])
    )
    assert edited.status_code == 200
    other = raw_client.get("/deals", headers=bearer(second["token"])).json()
    assert [d["name"] for d in other] == [STUDENT_HOUSING_PAYLOAD["name"]]
    assert (
        raw_client.get(f"/deals/{deals[0]['id']}", headers=bearer(second["token"])).status_code
        == 404
    )


def test_demo_token_must_be_signed_with_the_secret(raw_client, demo_on, template):
    forged = jwt.encode(
        {
            "iss": "dealrank-demo",
            "aud": "dealrank-api",
            "email": "template@demo.local",
            "exp": int(time.time()) + 600,
        },
        "y" * 40,
        algorithm="HS256",
    )
    assert raw_client.get("/me", headers=bearer(forged)).status_code == 401


def test_demo_token_is_rejected_when_demo_is_off(raw_client, demo_on, template):
    t = raw_client.post("/auth/demo").json()["token"]
    demo_on.DEMO_ENABLED = False
    assert raw_client.get("/me", headers=bearer(t)).status_code == 401


def test_demo_is_rate_limited(raw_client, demo_on, template):
    demo_on.DEMO_RATE_LIMIT_PER_MIN = 2
    codes = [raw_client.post("/auth/demo").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_old_demo_accounts_are_purged(raw_client, demo_on, template, db_session):
    from sqlalchemy import text

    from app.models.deal import Deal

    old = raw_client.post("/auth/demo").json()["email"]
    db_session.execute(
        text("UPDATE deals SET created_at = now() - interval '2 days' WHERE owner_id = :o"),
        {"o": old},
    )
    raw_client.post("/auth/demo")
    assert db_session.query(Deal).filter(Deal.owner_id == old).count() == 0
    assert db_session.query(Deal).filter(Deal.owner_id == "template@demo.local").count() == 1


# ------------------------------------------------- starting deals for new accounts


@pytest.fixture(autouse=True)
def _forget_seeded_users():
    auth._seeded.clear()


@pytest.fixture()
def sample_template(db_session):
    from app.demo import DEMO_TEMPLATE_OWNER
    from app.models.deal import Deal
    from app.sample_deals import SAMPLE_DEALS

    db_session.add_all(Deal(**d, owner_id=DEMO_TEMPLATE_OWNER) for d in SAMPLE_DEALS)
    db_session.flush()


def test_new_account_starts_with_the_sample_deals(raw_client, key, sample_template):
    mine = raw_client.get("/deals", headers=bearer(google_token(key))).json()
    assert len(mine) == 12


def test_another_account_gets_its_own_copies(raw_client, key, sample_template):
    a = raw_client.get("/deals", headers=bearer(google_token(key))).json()
    b = raw_client.get("/deals", headers=bearer(ms_token(key))).json()
    assert len(a) == len(b) == 12
    assert not {d["id"] for d in a} & {d["id"] for d in b}


def test_deleted_sample_deals_do_not_come_back(raw_client, key, sample_template):
    h = bearer(google_token(key))
    deals = raw_client.get("/deals", headers=h).json()
    for d in deals:
        assert raw_client.delete(f"/deals/{d['id']}", headers=h).status_code == 204
    auth._seeded.clear()  # as after a server restart
    assert raw_client.get("/deals", headers=h).json() == []


def test_existing_owner_is_not_given_duplicates(raw_client, key, sample_template, db_session):
    from app.models.deal import Deal
    from tests.api.payloads import STUDENT_HOUSING_PAYLOAD

    db_session.add(Deal(**STUDENT_HOUSING_PAYLOAD, owner_id="rohan.menon@gmail.com"))
    db_session.flush()
    mine = raw_client.get("/deals", headers=bearer(google_token(key))).json()
    assert [d["name"] for d in mine] == [STUDENT_HOUSING_PAYLOAD["name"]]
