"""See docs/build-plan.md Phase 4: round-trip create-then-read for both
leasing modes, 422 on a mode/branch mismatch, 404s on unknown IDs, and a
metrics response matching the Phase 2 golden fixture through the API
rather than only in-process.
"""

import uuid
from decimal import Decimal

from tests.api.payloads import STUDENT_HOUSING_PAYLOAD, SUBURBAN_GARDEN_PAYLOAD


def test_create_then_read_per_unit_deal(client):
    create_resp = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["leasing_mode"] == "per_unit"
    assert created["unit_count"] == 180
    assert created["bed_count"] is None

    get_resp = client.get(f"/deals/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Willowbrook Suburban Garden"


def test_create_then_read_per_bed_deal(client):
    create_resp = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["leasing_mode"] == "per_bed"
    assert created["bed_count"] == 240
    assert created["unit_count"] is None

    get_resp = client.get(f"/deals/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Campus View Student Housing"


def test_list_deals_includes_created(client):
    client.post("/deals", json=STUDENT_HOUSING_PAYLOAD)
    client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD)

    list_resp = client.get("/deals")
    assert list_resp.status_code == 200
    names = {deal["name"] for deal in list_resp.json()}
    assert {"Campus View Student Housing", "Willowbrook Suburban Garden"} <= names


def test_create_rejects_leasing_mode_branch_mismatch(client):
    """422 naming the offending field when leasing_mode doesn't match the
    populated branch — mirrors app/engine/types.py's DealInputs rule.
    """
    bad_payload = {
        **SUBURBAN_GARDEN_PAYLOAD,
        "leasing_mode": "per_unit",
        "bed_count": 180,  # should not be populated for per_unit
        "monthly_rent_per_bed": "1450.00",
    }
    resp = client.post("/deals", json=bad_payload)
    assert resp.status_code == 422


def test_get_unknown_deal_is_404(client):
    resp = client.get(f"/deals/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_patch_unknown_deal_is_404(client):
    resp = client.patch(f"/deals/{uuid.uuid4()}", json={"name": "New Name"})
    assert resp.status_code == 404


def test_delete_unknown_deal_is_404(client):
    resp = client.delete(f"/deals/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_metrics_unknown_deal_is_404(client):
    resp = client.get(f"/deals/{uuid.uuid4()}/metrics")
    assert resp.status_code == 404


def test_patch_updates_fields(client):
    created = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()

    patch_resp = client.patch(f"/deals/{created['id']}", json={"name": "Renamed Deal"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed Deal"

    get_resp = client.get(f"/deals/{created['id']}")
    assert get_resp.json()["name"] == "Renamed Deal"


def test_patch_rejects_result_that_would_break_leasing_mode_rule(client):
    """A PATCH that, applied on top of the existing row, would leave a
    per_unit deal carrying bed fields is rejected with 422 — same rule as
    create, just checked against the merged row.
    """
    created = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()

    patch_resp = client.patch(f"/deals/{created['id']}", json={"bed_count": 50})
    assert patch_resp.status_code == 422


def test_delete_removes_deal(client):
    created = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()

    delete_resp = client.delete(f"/deals/{created['id']}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/deals/{created['id']}")
    assert get_resp.status_code == 404


def test_metrics_matches_golden_fixture_through_the_api(client):
    """Same year-1 NOI as docs/golden-case-derivation.md's student housing
    case (Decimal('1375000.00')), computed through the full HTTP round
    trip rather than only in-process against app.engine directly (see
    tests/engine/test_golden_cases.py for the in-process version).
    """
    created = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()

    metrics_resp = client.get(f"/deals/{created['id']}/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()

    assert Decimal(metrics["year_one_noi"]) == Decimal("1375000.0000")
    assert len(metrics["annual_cash_flows"]) == 7
    assert Decimal(metrics["annual_cash_flows"][0]["noi"]) == Decimal("1375000.0000")
