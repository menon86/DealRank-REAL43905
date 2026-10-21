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

    # spread = unlevered IRR before closing/selling costs - that deal's hurdle
    for r in body["ranked"]:
        expected = Decimal(r["metrics"]["unlevered_irr_before_costs"]) - Decimal(
            r["hurdle"]["total"]
        )
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
    # Same asset, same unlevered IRR, different leverage. The return and cash-flow
    # factors are unlevered, so financing can only move the order through the risk
    # factor: with a risk weight the low-leverage twin wins, without one they tie.
    cheap = {**SUBURBAN_GARDEN_PAYLOAD, "interest_rate": "0.03"}
    levered = client.post("/deals", json=cheap).json()["id"]
    twin = {**cheap, "name": "Willowbrook Low-Leverage", "loan_amount": "9000000"}
    safe = client.post("/deals", json=twin).json()["id"]

    def top(weights):
        body = _rank(client, [levered, safe], weights=weights)
        return body["ranked"][0]["deal"]["name"]

    flat = _rank(client, [levered, safe], weights={"irr": 0, "cash_flow": 1, "risk": 0})
    assert flat["ranked"][0]["score"] == flat["ranked"][1]["score"]
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


# ------------------------------------------------- audit fixes


def test_duplicate_deal_ids_are_ranked_once(client, deal_ids):
    body = _rank(client, [deal_ids[1], deal_ids[1], deal_ids[0]], dscr_minimum="0")
    assert len(body["ranked"]) == 2
    flat = client.post("/rank", json={"deal_ids": [deal_ids[1]] * 2, "hurdle_rate": "0.08"})
    assert len(flat.json()) == 1


def test_leverage_counts_every_debt_layer(client, spreads):
    stack = [
        {
            "type": "agency_fannie_mae",
            "amount": "14400000",
            "interest_rate": "0.06",
            "amortization_years": 30,
        },
        {"type": "mezzanine", "amount": "7200000", "interest_rate": "0.11"},
        {"type": "sponsor_gp", "amount": "1"},
    ]
    stacked = client.post("/deals", json={**SUBURBAN_GARDEN_PAYLOAD, "capital_stack": stack}).json()
    body = _rank(client, [stacked["id"]], dscr_minimum="0")
    ltv = Decimal(body["ranked"][0]["ltv"])
    assert ltv == Decimal("21600000") / Decimal(SUBURBAN_GARDEN_PAYLOAD["purchase_price"])


def test_gate_uses_lowest_dscr_over_the_hold(client, spreads):
    # Interest-only for 3 years: year-one DSCR looks fine, but it drops once the loan amortizes.
    stack = [
        {
            "type": "agency_fannie_mae",
            "amount": "18700000",
            "interest_rate": "0.06",
            "amortization_years": 25,
            "io_months": 36,
        },
        {"type": "sponsor_gp", "amount": "1"},
    ]
    deal = client.post("/deals", json={**SUBURBAN_GARDEN_PAYLOAD, "capital_stack": stack}).json()
    metrics = client.get(f"/deals/{deal['id']}/metrics").json()
    year_one = Decimal(metrics["year_one_dscr"])
    lowest = Decimal(metrics["min_dscr"])
    assert lowest < year_one
    minimum = str((year_one + lowest) / 2)  # passes year one, fails later
    body = _rank(client, [deal["id"]], dscr_minimum=minimum)
    assert body["ranked"] == []
    assert "over the hold" in body["excluded"][0]["reason"]


def test_debt_yield_gate_is_optional_and_excludes(client, deal_ids):
    off = _rank(client, deal_ids, dscr_minimum="0")
    assert len(off["ranked"]) == 3
    strict = _rank(client, deal_ids, dscr_minimum="0", debt_yield_minimum="0.5")
    assert strict["ranked"] == []
    assert all("Debt yield" in e["reason"] for e in strict["excluded"])


def test_exit_cap_below_going_in_cap_is_flagged(client, spreads):
    aggressive = {**SUBURBAN_GARDEN_PAYLOAD, "exit_cap_rate": "0.04"}
    sane = {**SUBURBAN_GARDEN_PAYLOAD, "name": "Sane exit", "exit_cap_rate": "0.09"}
    ids = [client.post("/deals", json=p).json()["id"] for p in (aggressive, sane)]
    body = _rank(client, ids, dscr_minimum="0")
    by_name = {r["deal"]["name"]: r for r in body["ranked"]}
    assert any("compression" in w for w in by_name["Willowbrook Suburban Garden"]["warnings"])
    assert not any("compression" in w for w in by_name["Sane exit"]["warnings"])


def test_rent_growth_far_above_the_hurdle_growth_is_flagged(client, spreads):
    hot = client.post("/deals", json={**SUBURBAN_GARDEN_PAYLOAD, "rent_growth_rate": "0.06"}).json()
    body = _rank(client, [hot["id"]], dscr_minimum="0")
    assert any("Rent growth" in w for w in body["ranked"][0]["warnings"])


def test_adding_a_deal_does_not_change_existing_scores(client, deal_ids):
    weights = {"irr": 1, "cash_flow": 1, "risk": 1}
    pair = _rank(client, deal_ids[:2], dscr_minimum="0", weights=weights)
    trio = _rank(client, deal_ids, dscr_minimum="0", weights=weights)
    pair_scores = {r["deal"]["name"]: Decimal(r["score"]) for r in pair["ranked"]}
    trio_scores = {r["deal"]["name"]: Decimal(r["score"]) for r in trio["ranked"]}
    for name, score in pair_scores.items():
        assert trio_scores[name] == score
