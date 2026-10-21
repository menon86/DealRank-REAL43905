"""Negative and otherwise impossible values are rejected everywhere a deal
or analysis request is accepted: rents, rates, costs, counts and the layers
of a capital stack.
"""

import pytest

from tests.api.payloads import STUDENT_HOUSING_PAYLOAD as BED_PAYLOAD
from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD as P

BAD_DEAL_VALUES = [
    ("monthly_rent_per_unit", "-1"),
    ("monthly_rent_per_unit", "0"),
    ("unit_count", -5),
    ("unit_count", 0),
    ("vacancy_rate", "-0.01"),
    ("vacancy_rate", "1.01"),
    ("other_income_annual", "-1"),
    ("opex_annual", "-1"),
    ("expense_growth_rate", "-0.01"),
    ("rent_growth_rate", "-1"),
    ("turnover_cost_per_unit_or_bed", "-1"),
    ("annual_turnover_rate", "-0.1"),
    ("annual_turnover_rate", "1.5"),
    ("purchase_price", "-100"),
    ("purchase_price", "0"),
    ("closing_costs", "-1"),
    ("loan_amount", "-1"),
    ("interest_rate", "-0.01"),
    ("amortization_years", 0),
    ("amortization_years", -30),
    ("hold_period_years", 0),
    ("hold_period_years", -3),
    ("exit_cap_rate", "0"),
    ("exit_cap_rate", "-0.05"),
    ("selling_costs_rate", "-0.01"),
    ("selling_costs_rate", "1"),
    ("credit_loss_rate", "-0.01"),
    ("management_fee_rate", "1.2"),
    ("replacement_reserve_per_unit_or_bed", "-5"),
    ("lease_expiration_month", 0),
    ("lease_expiration_month", 13),
    ("vacancy_rate", "NaN"),
    ("opex_annual", "Infinity"),
]


@pytest.mark.parametrize(("field", "value"), BAD_DEAL_VALUES)
def test_create_rejects_illogical_values(client, field, value):
    assert client.post("/deals", json={**P, field: value}).status_code == 422


@pytest.mark.parametrize(("field", "value"), BAD_DEAL_VALUES)
def test_patch_rejects_illogical_values(client, field, value):
    deal = client.post("/deals", json=P).json()
    assert client.patch(f"/deals/{deal['id']}", json={field: value}).status_code == 422


@pytest.mark.parametrize(
    ("field", "value"), [("monthly_rent_per_bed", "-10"), ("bed_count", -4), ("bed_count", 0)]
)
def test_per_bed_fields_reject_illogical_values(client, field, value):
    assert client.post("/deals", json={**BED_PAYLOAD, field: value}).status_code == 422


def test_negative_rent_growth_above_minus_100_percent_is_allowed(client):
    # A declining market is a legitimate stress case; only <= -100% is impossible.
    assert client.post("/deals", json={**P, "rent_growth_rate": "-0.03"}).status_code == 201


@pytest.mark.parametrize(
    "layer_change",
    [
        {"amount": "-1"},
        {"interest_rate": "-0.01"},
        {"io_months": -6},
        {"amortization_years": -30},
        {"term_years": 0},
        {"rate_cap_cost": "-1"},
        {"origination_fee_rate": "-0.01"},
    ],
)
def test_capital_stack_layers_reject_illogical_values(client, layer_change):
    senior = {
        "type": "agency_fannie_mae",
        "amount": "18700000",
        "interest_rate": "0.06",
        "amortization_years": 30,
        **layer_change,
    }
    stack = [senior, {"type": "sponsor_gp", "amount": "1"}]
    assert client.post("/deals", json={**P, "capital_stack": stack}).status_code == 422


def test_unit_mix_rejects_negative_values(client):
    tier = {
        "id": "a",
        "name": "Studio",
        "units": 10,
        "beds_per_unit": 1,
        "avg_sqft": 500,
        "rent": "1000",
    }
    for change in ({"units": -1}, {"rent": "-5"}, {"avg_sqft": -1}, {"beds_per_unit": 0}):
        resp = client.post("/deals", json={**P, "unit_mix": [{**tier, **change}]})
        assert resp.status_code == 422


def test_analysis_requests_reject_illogical_values(client):
    deal = client.post("/deals", json=P).json()
    for body in ({"simulations": 0}, {"exit_cap_sd": "-0.01"}, {"vacancy_sd": "-1"}):
        assert client.post(f"/deals/{deal['id']}/monte-carlo", json=body).status_code == 422
    assert (
        client.post("/rank", json={"deal_ids": [deal["id"]], "hurdle_rate": "-2"}).status_code
        == 422
    )
    for body in (
        {"dscr_minimum": "-1"},
        {"treasury_yield": "-0.01"},
        {"debt_yield_minimum": "-0.1"},
        {"weights": {"irr": -1, "cash_flow": 1, "risk": 1}},
    ):
        resp = client.post("/rank/risk-adjusted", json={"deal_ids": [deal["id"]], **body})
        assert resp.status_code == 422
