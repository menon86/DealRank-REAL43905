"""Load the 18 demo deals (app/demo_deals.py) into an existing account through the API.

New accounts already get them when they sign up; this is for an account
that deleted them or predates that. Goes through the public REST API
rather than the database, so no DB credentials are needed. The deals are
created under the account given by DEALRANK_USERNAME / DEALRANK_PASSWORD.
Skips any deal whose name that user already has, so it is safe to re-run.

Usage:
    DEALRANK_USERNAME=me DEALRANK_PASSWORD=... python seed_demo_deals.py http://localhost:8000
"""

import json
import os
import sys
import urllib.request

from app.demo_deals import DEMO_DEALS


def _request(url: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def main(base_url: str) -> None:
    base_url = base_url.rstrip("/")
    username = os.environ.get("DEALRANK_USERNAME")
    password = os.environ.get("DEALRANK_PASSWORD")
    if not username or not password:
        sys.exit("Set DEALRANK_USERNAME and DEALRANK_PASSWORD to the account to load deals into.")
    login = {"username": username, "password": password}
    token = _request(f"{base_url}/auth/login", login)["token"]
    existing = {d["name"] for d in _request(f"{base_url}/deals", token=token)}
    created = 0
    for deal in DEMO_DEALS:
        if deal["name"] in existing:
            print(f"skip    {deal['name']}")
            continue
        _request(f"{base_url}/deals", deal, token=token)
        created += 1
        print(f"created {deal['name']}")
    print(f"done: {created} created, {len(DEMO_DEALS) - created} skipped")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
