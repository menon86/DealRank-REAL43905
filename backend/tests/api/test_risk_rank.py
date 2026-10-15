"""Risk-adjusted ranking through the API, with cap_rate_spreads seeded
into the test DB and the Treasury pinned by override (no network).

Hurdles at a 4.6% Treasury:
  student_housing  4.6% + 1.30% + 2.0% = 7.90%
  suburban_garden  4.6% + 0.61% + 1.4% = 6.61%
  urban_midrise    4.6% + 0.60% + 1.4% = 6.60%
Unlevered IRRs (golden cases): 9.9086%, 10.1706%, 3.3810%.
Year-one DSCRs: 1.33x, 1.46x, 0.87x.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.cap_rate_spread import CapRateSpread
from tests.api.payloads import (
    STUDENT_HOUSING_PAYLOAD,
    SUBURBAN_GARDEN_PAYLOAD,
    URBAN_MIDRISE_PAYLOAD,
)

TREASURY = "0.046"


@pytest.fixture()
def spreads(db_session):
    for cls, bps, growth in [
        ("student_housing", 130, "0.0200"),
        ("suburban_garden", 61, "0.0140"),
        ("urban_midrise", 60, "0.0140"),
    ]:
        db_session.add(
            CapRateSpread(
                sub_asset_class=cls,
                survey_source="test survey",
                survey_quarter="2026H1",
                spread_bps=bps,
                assumed_stabilized_noi_growth=Decimal(growth),
                effective_date=date(2026, 8, 12),
            )
        )
    db_session.flush()


@pytest.fixture()
def deal_ids(client, spreads):
    return [
        client.post("/deals", json=p).json()["id"]
        for p in (STUDENT_HOUSING_PAYLOAD, SUBURBAN_GARDEN_PAYLOAD, URBAN_MIDRISE_PAYLOAD)
    ]


def _rank(client, ids, **extra):
    resp = client.post(
        "/rank/risk-adjusted", json={"deal_ids": ids, "treasury_yield": TREASURY, **extra}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_each_deal_uses_its_own_subclass_hurdle(client, deal_ids):
    body = _rank(client, deal_ids, dscr_minimum="0")  # gate off to see all three
    by_name = {r["deal"]["name"]: r for r in body["ranked"]}

    student = by_name["Campus View Student Housing"]
    assert Decimal(student["hurdle"]["total"]) == Decimal("0.0790")
    assert Decimal(student["hurdle"]["cap_rate"]) == Decimal("0.0590")
    assert student["hurdle"]["spread_bps"] == 130

    urban = by_name["Meridian Urban Mid-Rise"]
    assert Decimal(urban["hurdle"]["total"]) == Decimal("0.0660")

    # spread = unlevered IRR - that deal's hurdle
    for r in body["ranked"]:
        expected = Decimal(r["metrics"]["unlevered_irr"]) - Decimal(r["hurdle"]["total"])
        assert Decimal(r["spread"]) == expected

    assert body["treasury"]["source"] == "override"
    assert Decimal(body["treasury"]["yield"]) == Decimal(TREASURY)


def test_subclass_hurdle_can_reorder_versus_a_flat_hurdle(client, deal_ids):
    # Flat-hurdle D2 order is suburban (10.17%) > student (9.91%). Against its own
    # 7.90% hurdle student's spread is +2.01%, suburban's vs 6.61% is +3.56%.
    body = _rank(client, deal_ids, dscr_minimum="0")
    assert [r["deal"]["name"] for r in body["ranked"]] == [
        "Willowbrook Suburban Garden",
        "Campus View Student Housing",
        "Meridian Urban Mid-Rise",
    ]
    assert body["excluded"] == []


def test_dscr_gate_excludes_rather_than_ranks_last(client, deal_ids):
    body = _rank(client, deal_ids)  # default 1.25x
    assert [r["rank"] for r in body["ranked"]] == [1, 2]
    assert [e["deal"]["name"] for e in body["excluded"]] == ["Meridian Urban Mid-Rise"]
    assert "0.87x" in body["excluded"][0]["reason"]
    assert "1.25x" in body["excluded"][0]["reason"]

    stricter = _rank(client, deal_ids, dscr_minimum="1.4")
    assert [r["deal"]["name"] for r in stricter["ranked"]] == ["Willowbrook Suburban Garden"]
    assert len(stricter["excluded"]) == 2


def test_everything_gated_out_is_empty_not_an_error(client, deal_ids):
    body = _rank(client, deal_ids, dscr_minimum="3")
    assert body["ranked"] == []
    assert len(body["excluded"]) == 3


def test_default_is_return_only_weights(client, deal_ids):
    body = _rank(client, deal_ids)
    assert Decimal(body["weights"]["irr"]) == 1
    assert Decimal(body["weights"]["risk"]) == 0
    assert "never sorted on" in body["basis_note"]


def test_preference_weights_flip_the_order_on_a_real_tradeoff(client, spreads):
    # Same asset, same unlevered IRR, different leverage. With cheap (3%) debt that is
    # positive leverage, so the low-leverage twin has higher DSCR but lower cash-on-cash.
    # Return can't separate them; the other two factors pull in opposite directions.
    cheap = {**SUBURBAN_GARDEN_PAYLOAD, "interest_rate": "0.03"}
    levered = client.post("/deals", json=cheap).json()["id"]
    twin = {**cheap, "name": "Willowbrook Low-Leverage", "loan_amount": "9000000"}
    safe = client.post("/deals", json=twin).json()["id"]

    def top(weights):
        body = _rank(client, [levered, safe], weights=weights)
        return body["ranked"][0]["deal"]["name"]

    assert top({"irr": 0, "cash_flow": 1, "risk": 0}) == "Willowbrook Suburban Garden"
    assert top({"irr": 0, "cash_flow": 0, "risk": 1}) == "Willowbrook Low-Leverage"


def test_questionnaire_answers_resolve_to_weights(client, deal_ids):
    body = _rank(
        client,
        deal_ids,
        answers={"primary_goal": "preservation", "risk_tolerance": 1, "income_need": 3},
    )
    w = {k: Decimal(v) for k, v in body["weights"].items()}
    assert sum(w.values()) == pytest.approx(Decimal(1))
    assert w["risk"] > w["irr"] and w["risk"] > w["cash_flow"]


def test_explicit_weights_beat_questionnaire(client, deal_ids):
    body = _rank(
        client,
        deal_ids,
        weights={"irr": 1, "cash_flow": 0, "risk": 0},
        answers={"primary_goal": "preservation", "risk_tolerance": 1, "income_need": 5},
    )
    assert Decimal(body["weights"]["irr"]) == 1


def test_bad_inputs(client, deal_ids):
    for extra in (
        {"weights": {"irr": 0, "cash_flow": 0, "risk": 0}},
        {"weights": {"irr": -1, "cash_flow": 1, "risk": 0}},
        {"answers": {"primary_goal": "moon", "risk_tolerance": 3, "income_need": 3}},
        {"answers": {"primary_goal": "cash_flow", "risk_tolerance": 9, "income_need": 3}},
    ):
        resp = client.post(
            "/rank/risk-adjusted",
            json={"deal_ids": deal_ids, "treasury_yield": TREASURY, **extra},
        )
        assert resp.status_code == 422


def test_unknown_deal_is_404(client, spreads):
    resp = client.post(
        "/rank/risk-adjusted",
        json={"deal_ids": ["00000000-0000-0000-0000-000000000000"], "treasury_yield": TREASURY},
    )
    assert resp.status_code == 404


def test_missing_reference_data_is_a_clear_409(client):
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    resp = client.post(
        "/rank/risk-adjusted", json={"deal_ids": [deal_id], "treasury_yield": TREASURY}
    )
    assert resp.status_code == 409
    assert "seed_reference_data" in resp.json()["detail"]


def test_latest_effective_date_wins(client, deal_ids, db_session):
    db_session.add(
        CapRateSpread(
            sub_asset_class="suburban_garden",
            survey_source="newer",
            survey_quarter="2026H2",
            spread_bps=100,
            assumed_stabilized_noi_growth=Decimal("0.0100"),
            effective_date=date(2027, 1, 1),
        )
    )
    db_session.flush()
    body = _rank(client, deal_ids, dscr_minimum="0")
    suburban = next(r for r in body["ranked"] if r["deal"]["name"].startswith("Willowbrook"))
    assert suburban["hurdle"]["survey_quarter"] == "2026H2"
    assert Decimal(suburban["hurdle"]["total"]) == Decimal("0.046") + Decimal("0.01") * 2


def test_hurdle_reference_table(client, spreads, monkeypatch):
    from app.api import risk_rank
    from app.services.treasury import TreasuryQuote

    monkeypatch.setattr(
        risk_rank,
        "get_treasury_10y",
        lambda: TreasuryQuote(Decimal("0.0431"), date(2026, 10, 14), "fred"),
    )
    body = client.get("/reference/hurdles").json()
    assert body["treasury"] == {"yield": "0.0431", "as_of": "2026-10-14", "source": "fred"}
    assert [h["sub_asset_class"] for h in body["hurdles"]] == [
        "student_housing",
        "suburban_garden",
        "urban_midrise",
    ]
    assert Decimal(body["hurdles"][0]["total"]) == Decimal("0.0431") + Decimal("0.013") + Decimal(
        "0.02"
    )
