from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.engine.metrics import compute
from app.engine.sensitivity import MonteCarloSpec, monte_carlo, sweep
from tests.engine.fixtures import STUDENT_HOUSING, SUBURBAN_GARDEN


def test_sweep_matches_a_direct_engine_run_at_each_point():
    points = sweep(SUBURBAN_GARDEN, "exit_cap_rate", D("0.045"), D("0.065"), 5)
    assert [p.value for p in points] == [D("0.045"), D("0.050"), D("0.055"), D("0.060"), D("0.065")]
    for p in points:
        direct = compute(replace(SUBURBAN_GARDEN, exit_cap_rate=p.value))
        assert p.unlevered_irr == direct.unlevered_irr
        assert p.exit_value == direct.exit_value
    # The base exit cap (5.5%) reproduces the headline number exactly.
    assert points[2].unlevered_irr == compute(SUBURBAN_GARDEN).unlevered_irr


def test_higher_exit_cap_lowers_irr_and_higher_rent_growth_raises_it():
    caps = sweep(SUBURBAN_GARDEN, "exit_cap_rate", D("0.045"), D("0.065"), 5)
    irrs = [p.unlevered_irr for p in caps]
    assert irrs == sorted(irrs, reverse=True)

    growth = sweep(SUBURBAN_GARDEN, "rent_growth_rate", D("0"), D("0.05"), 6)
    irrs = [p.unlevered_irr for p in growth]
    assert irrs == sorted(irrs)


def test_sweep_min_dscr_is_lowest_over_hold():
    point = sweep(STUDENT_HOUSING, "rent_growth_rate", D("0.03"), D("0.04"), 2)[0]
    flows = compute(STUDENT_HOUSING).annual_cash_flows
    assert point.min_dscr == min(cf.noi / cf.debt_service for cf in flows)


@pytest.mark.parametrize(
    "args",
    [
        ("vacancy_rate", D("0.01"), D("0.1"), 5),
        ("exit_cap_rate", D("0.06"), D("0.05"), 5),
        ("exit_cap_rate", D("0.05"), D("0.06"), 1),
        ("exit_cap_rate", D("0"), D("0.06"), 5),
    ],
)
def test_sweep_rejects_bad_arguments(args):
    with pytest.raises(ValueError):
        sweep(SUBURBAN_GARDEN, *args)


def test_monte_carlo_is_reproducible_with_a_seed():
    spec = MonteCarloSpec(simulations=200, seed=42)
    a = monte_carlo(SUBURBAN_GARDEN, spec, hurdle=D("0.08"))
    b = monte_carlo(SUBURBAN_GARDEN, spec, hurdle=D("0.08"))
    assert a == b
    c = monte_carlo(SUBURBAN_GARDEN, replace(spec, seed=43), hurdle=D("0.08"))
    assert c.unlevered_irr != a.unlevered_irr


def test_zero_volatility_collapses_to_the_base_case():
    spec = MonteCarloSpec(
        exit_cap_sd=D(0), rent_growth_sd=D(0), vacancy_sd=D(0), simulations=20, seed=1
    )
    result = monte_carlo(SUBURBAN_GARDEN, spec, hurdle=D("0.08"), dscr_minimum=D("1.25"))
    base = compute(SUBURBAN_GARDEN).unlevered_irr
    assert result.unlevered_irr.mean == base
    assert result.unlevered_irr.stdev == 0
    assert result.prob_below_hurdle == 0  # base IRR ~10.2% > 8%
    assert result.prob_dscr_below_minimum == 0  # base min DSCR > 1.25


def test_distribution_is_ordered_and_histogram_accounts_for_every_run():
    result = monte_carlo(SUBURBAN_GARDEN, MonteCarloSpec(simulations=300, seed=7), hurdle=D("0.10"))
    d = result.unlevered_irr
    assert d.p5 <= d.p25 <= d.p50 <= d.p75 <= d.p95
    assert sum(b.count for b in result.unlevered_histogram) == result.converged == 300
    # Hurdle near the median: a meaningful share of runs land on each side.
    assert D("0.2") < result.prob_below_hurdle < D("0.8")


def test_high_hurdle_means_certain_shortfall_and_dscr_probability_rises_with_stress():
    assert (
        monte_carlo(
            SUBURBAN_GARDEN, MonteCarloSpec(simulations=50, seed=3), hurdle=D("0.5")
        ).prob_below_hurdle
        == 1
    )
    tight = replace(STUDENT_HOUSING, vacancy_rate=D("0.12"))
    stressed = monte_carlo(tight, MonteCarloSpec(simulations=200, seed=5), dscr_minimum=D("1.25"))
    assert stressed.prob_dscr_below_minimum > 0


def test_all_cash_deal_has_no_dscr_probability():
    cash = replace(SUBURBAN_GARDEN, loan_amount=D(0))
    result = monte_carlo(cash, MonteCarloSpec(simulations=10, seed=1), dscr_minimum=D("1.25"))
    assert result.prob_dscr_below_minimum is None


def test_simulations_must_be_positive():
    with pytest.raises(ValueError):
        monte_carlo(SUBURBAN_GARDEN, MonteCarloSpec(simulations=0))
