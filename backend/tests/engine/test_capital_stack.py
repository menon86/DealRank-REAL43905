"""Capital stack: multiple financing layers per deal. See
app/engine/financing.py. Every case is built on a golden-case fixture and
checked against that fixture's own (already hand-verified) numbers, so a
layer's effect is isolated: same deal, one financing change.
"""

from dataclasses import replace
from decimal import Decimal

import pytest

from app.engine.debt import layer_schedule, monthly_payment
from app.engine.financing import validate_capital_stack
from app.engine.metrics import compute
from app.engine.types import FinancingLayer, LayerType, RateType
from tests.engine.fixtures import STUDENT_HOUSING, SUBURBAN_GARDEN, URBAN_MIDRISE

CENT = Decimal("0.01")
SPONSOR = FinancingLayer(layer_type=LayerType.SPONSOR_GP, amount=Decimal("0"))


def _agency(deal, **overrides) -> FinancingLayer:
    """The fixture's own loan, typed as a Fannie Mae loan."""
    return FinancingLayer(
        layer_type=LayerType.AGENCY_FANNIE_MAE,
        amount=deal.loan_amount,
        interest_rate=deal.interest_rate,
        amortization_years=deal.amortization_years,
        **overrides,
    )


def _with_stack(deal, *layers):
    return replace(deal, capital_stack=tuple(layers))


# --------------------------------------------------------------- golden cases


@pytest.mark.parametrize("deal", [STUDENT_HOUSING, SUBURBAN_GARDEN, URBAN_MIDRISE])
def test_single_agency_loan_matches_the_original_single_loan(deal):
    """A stack holding just the fixture's loan (typed, plus an equity
    layer) must reproduce every golden-case figure exactly."""
    assert compute(_with_stack(deal, _agency(deal), SPONSOR)) == compute(deal)


def test_agency_plus_mezzanine():
    deal = SUBURBAN_GARDEN
    mezz_amount = Decimal("2000000")
    mezz = FinancingLayer(
        layer_type=LayerType.MEZZANINE, amount=mezz_amount, interest_rate=Decimal("0.11")
    )
    base = compute(deal)
    stacked = compute(_with_stack(deal, _agency(deal), mezz, SPONSOR))

    y1_base, y1 = base.annual_cash_flows[0], stacked.annual_cash_flows[0]
    mezz_interest = mezz_amount * Decimal("0.11")  # interest-only all term
    assert abs(y1.debt_service - (y1_base.debt_service + mezz_interest)) < CENT
    assert y1.senior_debt_service == y1_base.debt_service

    # Senior DSCR is unchanged; combined DSCR picks up the mezz payment.
    assert stacked.year_one_senior_dscr == base.year_one_dscr
    assert stacked.year_one_dscr < stacked.year_one_senior_dscr

    assert stacked.total_debt == deal.loan_amount + mezz_amount
    assert stacked.equity_invested == base.equity_invested - mezz_amount
    # Interest-only mezz is still fully outstanding at exit.
    assert abs(stacked.net_sale_proceeds - (base.net_sale_proceeds - mezz_amount)) < CENT
    assert stacked.unlevered_irr == base.unlevered_irr


def test_bridge_loan_floating_with_interest_only_and_balloon():
    deal = URBAN_MIDRISE  # 10-year hold
    amount = Decimal("20000000")
    bridge = FinancingLayer(
        layer_type=LayerType.BRIDGE_DEBT_FUND,
        amount=amount,
        rate_type=RateType.FLOATING,
        index_name="SOFR",
        index_rate=Decimal("0.043"),
        spread=Decimal("0.0325"),
        io_months=24,
        amortization_years=30,
        term_years=3,
        rate_cap_cost=Decimal("150000"),
        origination_fee_rate=Decimal("0.01"),
    )
    base = compute(deal)
    metrics = compute(_with_stack(deal, bridge, SPONSOR))
    flows = metrics.annual_cash_flows

    # Years 1-2: interest only at index + spread.
    for year in flows[:2]:
        assert year.principal_paid == 0
        assert abs(year.debt_service - amount * Decimal("0.0755")) < CENT
    # Year 3 amortizes, then the remaining balance balloons at maturity.
    assert flows[2].principal_paid > 0
    assert flows[2].balloon_payment == amount - flows[2].principal_paid
    assert flows[2].ending_loan_balance == 0
    assert flows[2].levered_cash_flow == (
        flows[2].noi - flows[2].debt_service - flows[2].balloon_payment
    )
    # Nothing owed after maturity, so nothing to repay at exit.
    for year in flows[3:]:
        assert year.debt_service == 0
    assert metrics.loan_balance_at_exit == 0

    # Rate cap + 1% fee are paid at closing, out of equity.
    upfront = Decimal("150000") + amount * Decimal("0.01")
    assert metrics.upfront_financing_costs == upfront
    assert metrics.equity_invested == deal.purchase_price + deal.closing_costs + upfront - amount
    assert metrics.unlevered_irr == base.unlevered_irr


def test_amortization_after_interest_only_uses_the_remaining_period():
    """TASK.md section 4: after I/O, level amortization over
    amortization_years minus the I/O period."""
    amount, rate = Decimal("10000000"), Decimal("0.06")
    layer = FinancingLayer(
        layer_type=LayerType.AGENCY_FREDDIE_MAC,
        amount=amount,
        interest_rate=rate,
        io_months=24,
        amortization_years=30,
    )
    schedule = layer_schedule(layer, hold_period_years=5)
    level = monthly_payment(amount, rate, 28)  # 30 years less 2 of I/O
    assert schedule[0].ending_balance == amount
    assert schedule[1].ending_balance == amount
    assert abs(schedule[2].debt_service - level * 12) < CENT


def test_preferred_equity_is_paid_before_common_but_is_not_debt():
    deal = STUDENT_HOUSING
    pref_amount = Decimal("2000000")
    pref = FinancingLayer(
        layer_type=LayerType.PREFERRED_EQUITY,
        amount=pref_amount,
        preferred_return=Decimal("0.09"),
    )
    base = compute(deal)
    metrics = compute(_with_stack(deal, _agency(deal), pref, SPONSOR))

    for base_year, year in zip(base.annual_cash_flows, metrics.annual_cash_flows, strict=True):
        assert year.preferred_distribution == Decimal("180000.00")
        assert year.debt_service == base_year.debt_service
        assert year.levered_cash_flow == base_year.levered_cash_flow - Decimal("180000.00")

    # Not in either DSCR.
    assert metrics.year_one_dscr == base.year_one_dscr
    assert metrics.year_one_senior_dscr == base.year_one_dscr

    assert metrics.preferred_equity == pref_amount
    assert metrics.equity_invested == base.equity_invested - pref_amount
    assert metrics.preferred_equity_repayment == pref_amount
    assert metrics.net_sale_proceeds == base.net_sale_proceeds - pref_amount
    assert metrics.unlevered_irr == base.unlevered_irr


def test_all_cash_deal():
    deal = SUBURBAN_GARDEN
    cash = FinancingLayer(
        layer_type=LayerType.ALL_CASH, amount=deal.purchase_price + deal.closing_costs
    )
    metrics = compute(_with_stack(deal, cash))

    assert all(year.debt_service == 0 for year in metrics.annual_cash_flows)
    assert metrics.year_one_dscr is None
    assert metrics.year_one_senior_dscr is None
    assert metrics.total_debt == 0
    assert metrics.equity_invested == deal.purchase_price + deal.closing_costs
    # No debt: the levered and unlevered streams are the same stream.
    assert metrics.levered_irr == metrics.unlevered_irr


def test_loan_assumption_maturing_mid_hold_balloons_and_stops():
    deal = SUBURBAN_GARDEN  # 10-year hold
    assumed = _agency(deal, term_years=5)
    assumed = replace(assumed, layer_type=LayerType.LOAN_ASSUMPTION)
    base = compute(deal)
    metrics = compute(_with_stack(deal, assumed, SPONSOR))
    flows = metrics.annual_cash_flows

    # Identical to the original loan until maturity...
    for base_year, year in zip(base.annual_cash_flows[:4], flows[:4], strict=True):
        assert year.debt_service == base_year.debt_service
    # ...then the year-5 balance is repaid as a balloon.
    assert flows[4].balloon_payment == base.annual_cash_flows[4].ending_loan_balance
    assert flows[4].ending_loan_balance == 0
    assert all(year.debt_service == 0 for year in flows[5:])
    assert metrics.loan_balance_at_exit == 0
    assert metrics.unlevered_irr == base.unlevered_irr


def test_loan_maturing_at_exit_is_repaid_from_the_sale_not_as_a_balloon():
    deal = SUBURBAN_GARDEN  # 10-year hold
    metrics = compute(_with_stack(deal, _agency(deal, term_years=10), SPONSOR))
    assert metrics == compute(deal)
    assert all(year.balloon_payment == 0 for year in metrics.annual_cash_flows)


def test_other_layers_keep_the_users_label_and_count_as_their_group():
    deal = SUBURBAN_GARDEN
    other_sub = FinancingLayer(
        layer_type=LayerType.OTHER_SUBORDINATE,
        label="Seller earn-out note",
        amount=Decimal("1000000"),
        interest_rate=Decimal("0.08"),
    )
    metrics = compute(_with_stack(deal, _agency(deal), other_sub, SPONSOR))
    # "Other subordinate" is a loan: in combined DSCR, not senior.
    assert metrics.year_one_dscr < metrics.year_one_senior_dscr


# ----------------------------------------------------------------- validation


def _senior(**overrides) -> FinancingLayer:
    fields = dict(
        layer_type=LayerType.AGENCY_FANNIE_MAE,
        amount=Decimal("1000000"),
        interest_rate=Decimal("0.06"),
        amortization_years=30,
    )
    fields.update(overrides)
    return FinancingLayer(**fields)


def test_valid_stack_has_no_errors():
    assert validate_capital_stack([_senior(), SPONSOR]) == []


@pytest.mark.parametrize(
    "layers, message",
    [
        ([SPONSOR], "exactly one senior debt layer"),
        ([_senior(), _senior(layer_type=LayerType.CMBS), SPONSOR], "Only one senior"),
        ([_senior()], "at least one equity layer"),
        (
            [FinancingLayer(layer_type=LayerType.ALL_CASH, amount=Decimal("1")), _senior()],
            "all-cash deal can't also have debt",
        ),
        (
            [_senior(rate_type=RateType.FLOATING, index_rate=Decimal("0.04")), SPONSOR],
            "need an index rate and a spread",
        ),
        ([_senior(io_months=72, term_years=5), SPONSOR], "can't exceed the term"),
        ([_senior(interest_rate=None), SPONSOR], "need an interest rate"),
        ([_senior(layer_type=LayerType.OTHER_SENIOR), SPONSOR], "needs a name"),
        (
            [
                _senior(),
                FinancingLayer(layer_type=LayerType.PREFERRED_EQUITY, amount=Decimal("5")),
                SPONSOR,
            ],
            "needs a preferred return",
        ),
        ([_senior(io_months=360), SPONSOR], "longer than the interest-only period"),
        ([_senior(amount=Decimal("0")), SPONSOR], "amount above zero"),
    ],
)
def test_invalid_stacks_are_rejected(layers, message):
    errors = validate_capital_stack(layers)
    assert any(message in error for error in errors), errors


def test_deal_inputs_rejects_an_invalid_stack():
    with pytest.raises(ValueError, match="equity layer"):
        _with_stack(SUBURBAN_GARDEN, _senior())
