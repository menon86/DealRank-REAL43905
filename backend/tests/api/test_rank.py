"""See docs/build-plan.md Phase 4: a rank response whose order is verified
against hand-computed IRRs, including one deal below the hurdle to
confirm negative spreads still rank rather than disappear (the DSCR gate
that excludes deals is Deliverable 3, not D2).
"""

import uuid
from decimal import Decimal

from tests.api.payloads import (
    STUDENT_HOUSING_PAYLOAD,
    SUBURBAN_GARDEN_PAYLOAD,
    URBAN_MIDRISE_PAYLOAD,
)

# Hand-computed in docs/golden-case-derivation.md / verified in
# tests/engine/test_golden_cases.py: student housing and suburban garden
# are positively levered (unlevered IRR ~9.9% / ~10.2%), Meridian Urban
# Mid-Rise is negatively levered by construction (unlevered IRR ~3.4%).
HURDLE_RATE = "0.08"


def test_rank_orders_by_unlevered_irr_minus_hurdle(client):
    student = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()
    suburban = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()
    urban = client.post("/deals", json=URBAN_MIDRISE_PAYLOAD).json()

    resp = client.post(
        "/rank",
        json={
            "deal_ids": [student["id"], suburban["id"], urban["id"]],
            "hurdle_rate": HURDLE_RATE,
        },
    )
    assert resp.status_code == 200
    ranked = resp.json()

    assert [entry["rank"] for entry in ranked] == [1, 2, 3]

    names_in_order = [entry["deal"]["name"] for entry in ranked]
    # Suburban garden's unlevered IRR (~10.2%) beats student housing's
    # (~9.9%); Meridian Urban Mid-Rise (~3.4%, below the 8% hurdle) is
    # last, not absent.
    assert names_in_order == [
        "Willowbrook Suburban Garden",
        "Campus View Student Housing",
        "Meridian Urban Mid-Rise",
    ]

    last_place = ranked[-1]
    assert Decimal(last_place["spread"]) < 0
    assert last_place["deal"]["name"] == "Meridian Urban Mid-Rise"


def test_rank_response_carries_basis_note(client):
    """3.4 accept criterion: the response carries an explicit basis note,
    so an exported report can't be read as ranking on levered returns.
    """
    student = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()

    resp = client.post("/rank", json={"deal_ids": [student["id"]], "hurdle_rate": HURDLE_RATE})
    assert resp.status_code == 200
    ranked = resp.json()
    assert len(ranked) == 1
    assert "unlevered" in ranked[0]["basis_note"].lower()
    assert "never sorted on" in ranked[0]["basis_note"].lower()


def test_rank_unknown_deal_id_is_404(client):
    resp = client.post("/rank", json={"deal_ids": [str(uuid.uuid4())], "hurdle_rate": HURDLE_RATE})
    assert resp.status_code == 404
