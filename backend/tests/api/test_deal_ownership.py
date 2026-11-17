"""Each user sees only their own deals (app/api/ownership.py)."""

import uuid

import pytest

from app.demo_deals import DEMO_DEALS
from app.models.deal import Deal
from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD

DEMO_NAMES = sorted(d["name"] for d in DEMO_DEALS)


def _names(client, headers):
    return sorted(d["name"] for d in client.get("/deals", headers=headers).json())


def _sign_up(client, username):
    res = client.post("/auth/register", json={"username": username, "password": "password123"})
    assert res.status_code == 201
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture()
def two_users(anon_client, spreads):
    alice = _sign_up(anon_client, "alice")
    bob = _sign_up(anon_client, "bob")
    res = anon_client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD, headers=alice)
    assert res.status_code == 201
    return anon_client, alice, bob, res.json()["id"]


def test_every_account_starts_with_its_own_demo_deals(anon_client, spreads):
    alice = _sign_up(anon_client, "alice")
    bob = _sign_up(anon_client, "bob")
    assert len(DEMO_NAMES) == 18
    assert _names(anon_client, alice) == _names(anon_client, bob) == DEMO_NAMES
    in_order = [d["name"] for d in anon_client.get("/deals", headers=alice).json()]
    assert in_order == [d["name"] for d in DEMO_DEALS]

    # Separate copies: deleting one of alice's leaves bob's set whole.
    first = anon_client.get("/deals", headers=alice).json()[0]
    assert anon_client.delete(f"/deals/{first['id']}", headers=alice).status_code == 204
    assert len(_names(anon_client, alice)) == 17
    assert _names(anon_client, bob) == DEMO_NAMES
    # Real deals the engine can compute.
    assert anon_client.get(f"/deals/{first['id']}/metrics", headers=bob).status_code == 404
    other = anon_client.get("/deals", headers=bob).json()[0]
    assert anon_client.get(f"/deals/{other['id']}/metrics", headers=bob).status_code == 200


def test_new_deal_belongs_to_its_creator(two_users, db_session):
    client, alice, bob, deal_id = two_users
    assert deal_id in {d["id"] for d in client.get("/deals", headers=alice).json()}
    assert deal_id not in {d["id"] for d in client.get("/deals", headers=bob).json()}
    deal = db_session.get(Deal, uuid.UUID(deal_id))
    assert deal.owner_id is not None


def test_other_users_cannot_touch_the_deal(two_users):
    client, alice, bob, deal_id = two_users
    attempts = [
        client.get(f"/deals/{deal_id}", headers=bob),
        client.get(f"/deals/{deal_id}/metrics", headers=bob),
        client.patch(f"/deals/{deal_id}", json={"name": "mine now"}, headers=bob),
        client.delete(f"/deals/{deal_id}", headers=bob),
        client.post("/rank", json={"deal_ids": [deal_id], "hurdle_rate": "0.08"}, headers=bob),
        client.post(
            f"/deals/{deal_id}/sensitivity", json={"variable": "exit_cap_rate"}, headers=bob
        ),
        client.get(f"/deals/{deal_id}/rent-check?geography=x", headers=bob),
        client.get(f"/reports/pdf?deal_ids={deal_id}&hurdle_rate=0.08", headers=bob),
    ]
    # Same 404 as a deal that doesn't exist, so ids of other users' deals aren't confirmed.
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    # And it's untouched for its owner.
    mine = client.get(f"/deals/{deal_id}", headers=alice)
    assert mine.status_code == 200 and mine.json()["name"] == SUBURBAN_GARDEN_PAYLOAD["name"]


def test_chat_presets_only_see_own_deals(two_users):
    client, alice, bob, deal_id = two_users
    body = {"preset_id": "top_deal", "context": {"ranking": {"hurdle_rate": "0.08"}}}
    bob_answer = client.post("/chat/preset", json=body, headers=bob).json()["answer"]
    alice_answer = client.post("/chat/preset", json=body, headers=alice).json()["answer"]
    assert SUBURBAN_GARDEN_PAYLOAD["name"] not in bob_answer
    assert SUBURBAN_GARDEN_PAYLOAD["name"] in alice_answer


def test_claim_deals_assigns_unowned_rows(two_users, db_session, monkeypatch):
    import claim_deals

    client, alice, bob, _ = two_users
    legacy = Deal(**{**SUBURBAN_GARDEN_PAYLOAD, "name": "Legacy deal"})
    db_session.add(legacy)
    db_session.flush()
    assert "Legacy deal" not in _names(client, bob)

    monkeypatch.setattr(claim_deals, "SessionLocal", lambda: _NoClose(db_session))
    assert claim_deals.claim("BOB") == 1
    assert "Legacy deal" in _names(client, bob)
    assert "Legacy deal" not in _names(client, alice)


class _NoClose:
    """Hands the test's session to claim_deals without letting it close or commit for real."""

    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *exc):
        return False
