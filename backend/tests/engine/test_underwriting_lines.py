"""Optional underwriting lines (other-income growth, credit loss, management
fee, replacement reserves), preferred-return accrual, and the Monte Carlo
correlation. Every line defaults to zero, which must reproduce the original
model exactly.
"""

from dataclasses import replace
from decimal import Decimal as D

from app.engine import sensitivity as s
from app.engine.metrics import compute
from app.engine.types import FinancingLayer, LayerType
from tests.engine.test_edge_cases import BASE_DEAL


def _flows(deal):
    return compute(deal).annual_cash_flows


def test_defaults_change_nothing():
    explicit = replace(
        BASE_DEAL,
        other_income_growth_rate=D(0),
        credit_loss_rate=D(0),
        management_fee_rate=D(0),
        replacement_reserve_per_unit_or_bed=D(0),
    )
    assert compute(explicit) == compute(BASE_DEAL)


def test_other_income_grows_when_asked():
    flows = _flows(replace(BASE_DEAL, other_income_growth_rate=D("0.03")))
    assert flows[0].other_income == D("10000")
    assert flows[4].other_income == D("10000") * D("1.03") ** 4
    assert flows[4].egi > _flows(BASE_DEAL)[4].egi


def test_credit_loss_reduces_egi_by_share_of_gpr():
    base, lossy = _flows(BASE_DEAL)[0], _flows(replace(BASE_DEAL, credit_loss_rate=D("0.01")))[0]
    assert lossy.credit_loss == base.gpr * D("0.01")
    assert lossy.egi == base.egi - lossy.credit_loss


def test_management_fee_is_a_share_of_egi_and_comes_out_of_noi():
    row = _flows(replace(BASE_DEAL, management_fee_rate=D("0.03")))[0]
    base = _flows(BASE_DEAL)[0]
    assert row.management_fee == row.egi * D("0.03")
    assert row.noi == base.noi - row.management_fee


def test_reserves_are_below_noi_but_cut_cash_flow_and_irr():
    reserved = replace(BASE_DEAL, replacement_reserve_per_unit_or_bed=D("300"))
    row, base = _flows(reserved)[0], _flows(BASE_DEAL)[0]
    assert row.replacement_reserves == D("300") * 100
    assert row.noi == base.noi  # NOI, cap rate and DSCR are before reserves
    assert row.levered_cash_flow == base.levered_cash_flow - row.replacement_reserves
    assert row.unlevered_cash_flow == base.noi - row.replacement_reserves
    assert compute(reserved).exit_value == compute(BASE_DEAL).exit_value
    assert compute(reserved).unlevered_irr < compute(BASE_DEAL).unlevered_irr
    assert _flows(reserved)[1].replacement_reserves == D("300") * 100 * D("1.03")


def _pref_deal(pref_return):
    stack = (
        FinancingLayer(
            layer_type=LayerType.AGENCY_FANNIE_MAE,
            amount=D("6500000"),
            interest_rate=D("0.06"),
            amortization_years=30,
        ),
        FinancingLayer(
            layer_type=LayerType.PREFERRED_EQUITY, amount=D("1500000"), preferred_return=pref_return
        ),
        FinancingLayer(layer_type=LayerType.SPONSOR_GP, amount=D("1")),
    )
    return replace(BASE_DEAL, capital_stack=stack)


def test_preferred_return_is_paid_in_full_when_cash_flow_covers_it():
    metrics = compute(_pref_deal(D("0.08")))
    assert all(cf.preferred_shortfall == 0 for cf in metrics.annual_cash_flows)
    assert metrics.annual_cash_flows[0].preferred_distribution == D("120000")
    assert metrics.preferred_equity_repayment == D("1500000")


def test_unpaid_preferred_return_accrues_and_is_repaid_at_exit():
    # A 40% preferred return can't be paid from this deal's cash flow.
    metrics = compute(_pref_deal(D("0.40")))
    flows = metrics.annual_cash_flows
    short = [cf for cf in flows if cf.preferred_shortfall > 0]
    assert short, "expected a shortfall"
    # Cash flow never goes below zero just because of the preferred return.
    first = flows[0]
    assert first.preferred_distribution + first.preferred_shortfall == D("600000")
    assert first.levered_cash_flow >= 0
    total_accrued = flows[-1].preferred_accrued
    assert total_accrued == sum((cf.preferred_shortfall for cf in flows), D(0))
    assert metrics.preferred_equity_repayment == D("1500000") + total_accrued


def test_monte_carlo_correlation_links_exit_cap_and_rent_growth():
    def stdev(rho):
        spec = s.MonteCarloSpec(simulations=400, seed=5, exit_cap_rent_growth_correlation=D(rho))
        return s.monte_carlo(BASE_DEAL, spec).unlevered_irr.stdev

    # Perfectly negative correlation: a high exit cap always pairs with low rent growth,
    # which makes bad outcomes worse than the independent case.
    assert stdev("-1") > stdev("0")


def test_non_converged_runs_count_as_below_the_hurdle():
    # Rent growth -50% makes NOI collapse: no IRR for any run.
    doomed = replace(BASE_DEAL, opex_annual=D("5000000"))
    result = s.monte_carlo(doomed, s.MonteCarloSpec(simulations=20, seed=1), hurdle=D("0.05"))
    assert result.converged == 0
    assert result.prob_below_hurdle == 1


def test_hurdle_can_be_compared_on_the_gross_irr():
    spec = s.MonteCarloSpec(
        simulations=50, seed=3, exit_cap_sd=D(0), rent_growth_sd=D(0), vacancy_sd=D(0)
    )
    base = compute(BASE_DEAL)
    between = (base.unlevered_irr + base.unlevered_irr_before_costs) / 2
    net = s.monte_carlo(BASE_DEAL, spec, hurdle=between)
    gross = s.monte_carlo(BASE_DEAL, spec, hurdle=between, hurdle_on_gross_irr=True)
    assert net.prob_below_hurdle == 1  # net IRR sits under the hurdle
    assert gross.prob_below_hurdle == 0  # gross IRR sits above it
