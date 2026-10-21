"""See docs/build-plan.md Phase 4: round-trip create-then-read for both
leasing modes, 422 on a mode/branch mismatch, 404s on unknown IDs, and a
metrics response matching the Phase 2 golden fixture through the API
rather than only in-process.
"""

import uuid
from decimal import Decimal

import pytest

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
    # Equity invested and the exit breakdown travel with the headline
    # metrics so the comparison view can show each formula's inputs.
    for field in (
        "equity_invested",
        "total_distributions",
        "forward_noi",
        "selling_costs",
        "loan_balance_at_exit",
    ):
        assert field in metrics, field
    assert Decimal(metrics["equity_invested"]) == Decimal(
        STUDENT_HOUSING_PAYLOAD["purchase_price"]
    ) + Decimal(STUDENT_HOUSING_PAYLOAD["closing_costs"]) - Decimal(
        STUDENT_HOUSING_PAYLOAD["loan_amount"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("exit_cap_rate", "0"),
        ("purchase_price", "0"),
        ("amortization_years", 0),
        ("hold_period_years", 0),
        ("vacancy_rate", "1.5"),
        ("monthly_rent_per_bed", "-1"),
        ("loan_amount", "999999999.00"),
    ],
)
def test_create_rejects_out_of_range_values(client, field, value):
    """Values that would otherwise divide by zero or produce nonsense are
    rejected with a 422 instead of surfacing as a 500 from the engine.
    """
    payload = {**STUDENT_HOUSING_PAYLOAD, field: value}
    assert client.post("/deals", json=payload).status_code == 422


def test_patch_rejects_out_of_range_value(client):
    created = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()
    resp = client.patch(f"/deals/{created['id']}", json={"exit_cap_rate": "0"})
    assert resp.status_code == 422


def test_create_rejects_blank_and_overlong_names(client):
    from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD as payload

    assert client.post("/deals", json={**payload, "name": ""}).status_code == 422
    assert client.post("/deals", json={**payload, "name": "   "}).status_code == 422
    assert client.post("/deals", json={**payload, "name": "x" * 256}).status_code == 422
    ok = client.post("/deals", json={**payload, "name": "  Padded  "})
    assert ok.status_code == 201
    assert ok.json()["name"] == "Padded"


# ------------------------------------------------- optional lines, unit mix, paging


def test_optional_lines_and_unit_mix_round_trip_and_feed_the_engine(client):
    from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD as P

    mix = [
        {
            "id": "studio",
            "name": "Studio",
            "units": 60,
            "beds_per_unit": 1,
            "avg_sqft": 500,
            "rent": "1200",
        },
        {
            "id": "2bed",
            "name": "2 Bed",
            "units": 120,
            "beds_per_unit": 2,
            "avg_sqft": 900,
            "rent": "1550",
        },
    ]
    payload = {
        **P,
        "unit_mix": mix,
        "management_fee_rate": "0.03",
        "credit_loss_rate": "0.01",
        "other_income_growth_rate": "0.025",
        "replacement_reserve_per_unit_or_bed": "300",
    }
    created = client.post("/deals", json=payload)
    assert created.status_code == 201, created.text
    body = client.get(f"/deals/{created.json()['id']}").json()
    assert [t["name"] for t in body["unit_mix"]] == ["Studio", "2 Bed"]
    assert body["management_fee_rate"] == "0.030000"

    plain = client.post("/deals", json=P).json()
    with_lines = client.get(f"/deals/{body['id']}/metrics").json()
    without = client.get(f"/deals/{plain['id']}/metrics").json()
    assert Decimal(with_lines["year_one_noi"]) < Decimal(without["year_one_noi"])
    first = with_lines["annual_cash_flows"][0]
    assert Decimal(first["management_fee"]) > 0
    assert Decimal(first["replacement_reserves"]) == Decimal("300") * P["unit_count"]


def test_new_lines_default_to_zero(client):
    from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD as P

    deal = client.post("/deals", json=P).json()
    assert Decimal(deal["management_fee_rate"]) == 0
    assert deal["unit_mix"] is None


def test_deal_list_is_paged(client):
    from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD as P

    for index in range(3):
        client.post("/deals", json={**P, "name": f"Deal {index}"})
    assert len(client.get("/deals?limit=2").json()) == 2
    assert len(client.get("/deals?limit=2&offset=2").json()) >= 1
    assert client.get("/deals?limit=0").status_code == 422
