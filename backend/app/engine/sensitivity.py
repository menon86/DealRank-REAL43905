"""Sensitivity analysis on top of the core waterfall: single-variable
sweeps (exit cap rate, rent growth) and a Monte Carlo over exit cap rate,
rent growth and vacancy. Every run goes through metrics.compute(), so a
sensitivity case can never disagree with the headline numbers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from decimal import Decimal

from app.engine.metrics import compute
from app.engine.types import DealInputs

SWEEP_VARIABLES = ("exit_cap_rate", "rent_growth_rate")

MIN_EXIT_CAP = Decimal("0.01")
RATE_QUANTUM = Decimal("0.00001")


@dataclass(frozen=True)
class SensitivityPoint:
    value: Decimal
    unlevered_irr: Decimal | None
    levered_irr: Decimal | None
    cash_on_cash: Decimal | None
    equity_multiple: Decimal | None
    min_dscr: Decimal | None  # lowest DSCR over the hold; None if all-cash
    exit_value: Decimal


def _point(deal: DealInputs, value: Decimal) -> SensitivityPoint:
    metrics = compute(deal)
    ratios = [cf.noi / cf.debt_service for cf in metrics.annual_cash_flows if cf.debt_service != 0]
    return SensitivityPoint(
        value=value,
        unlevered_irr=metrics.unlevered_irr,
        levered_irr=metrics.levered_irr,
        cash_on_cash=metrics.cash_on_cash,
        equity_multiple=metrics.equity_multiple,
        min_dscr=min(ratios) if ratios else None,
        exit_value=metrics.exit_value,
    )


def sweep(
    deal: DealInputs, variable: str, low: Decimal, high: Decimal, steps: int
) -> list[SensitivityPoint]:
    """Re-runs the deal at `steps` evenly spaced values of one variable,
    every other input held at its base value. `steps` >= 2 includes both
    endpoints.
    """
    if variable not in SWEEP_VARIABLES:
        raise ValueError(f"variable must be one of {SWEEP_VARIABLES}")
    if steps < 2:
        raise ValueError("steps must be at least 2")
    if high <= low:
        raise ValueError("high must be greater than low")
    if variable == "exit_cap_rate" and low <= 0:
        raise ValueError("exit_cap_rate must stay positive")
    increment = (high - low) / (steps - 1)
    points = []
    for i in range(steps):
        value = low + increment * i
        points.append(_point(replace(deal, **{variable: value}), value))
    return points


# ---------------------------------------------------------------- Monte Carlo


@dataclass(frozen=True)
class MonteCarloSpec:
    """Standard deviations of independent normal draws centred on the
    deal's own inputs. Draws are clamped to sane ranges (exit cap >= 1%,
    rent growth within +/-20%, vacancy within 0-50%).
    """

    exit_cap_sd: Decimal = Decimal("0.0050")
    rent_growth_sd: Decimal = Decimal("0.0100")
    vacancy_sd: Decimal = Decimal("0.0200")
    simulations: int = 1000
    seed: int | None = None


@dataclass(frozen=True)
class Distribution:
    mean: Decimal
    stdev: Decimal
    p5: Decimal
    p25: Decimal
    p50: Decimal
    p75: Decimal
    p95: Decimal


@dataclass(frozen=True)
class HistogramBin:
    low: Decimal
    high: Decimal
    count: int


@dataclass(frozen=True)
class MonteCarloResult:
    simulations: int
    converged: int
    unlevered_irr: Distribution | None
    levered_irr: Distribution | None
    unlevered_histogram: list[HistogramBin]
    prob_below_hurdle: Decimal | None
    prob_dscr_below_minimum: Decimal | None


def _clamp(x: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, x))


def _draw(rng: random.Random, centre: Decimal, sd: Decimal) -> Decimal:
    if sd == 0:
        return centre
    return centre + Decimal(rng.gauss(0.0, float(sd))).quantize(RATE_QUANTUM)


def _percentile(sorted_values: list[Decimal], q: Decimal) -> Decimal:
    """Linear-interpolated percentile, q in 0..1."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _distribution(values: list[Decimal]) -> Distribution | None:
    if not values:
        return None
    ordered = sorted(values)
    n = Decimal(len(ordered))
    mean = sum(ordered, Decimal(0)) / n
    variance = sum(((v - mean) ** 2 for v in ordered), Decimal(0)) / n
    return Distribution(
        mean=mean,
        stdev=variance.sqrt(),
        p5=_percentile(ordered, Decimal("0.05")),
        p25=_percentile(ordered, Decimal("0.25")),
        p50=_percentile(ordered, Decimal("0.50")),
        p75=_percentile(ordered, Decimal("0.75")),
        p95=_percentile(ordered, Decimal("0.95")),
    )


def _histogram(values: list[Decimal], bins: int = 20) -> list[HistogramBin]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [HistogramBin(low=low, high=high, count=len(values))]
    width = (high - low) / bins
    counts = [0] * bins
    for v in values:
        counts[min(int((v - low) / width), bins - 1)] += 1
    return [
        HistogramBin(low=low + width * i, high=low + width * (i + 1), count=counts[i])
        for i in range(bins)
    ]


def monte_carlo(
    deal: DealInputs,
    spec: MonteCarloSpec,
    hurdle: Decimal | None = None,
    dscr_minimum: Decimal | None = None,
) -> MonteCarloResult:
    """Draws exit cap rate, rent growth and vacancy independently, re-runs
    the full waterfall each time, and summarizes unlevered/levered IRR.
    Pass `hurdle` for P(unlevered IRR < hurdle) and `dscr_minimum` for
    P(lowest hold-period DSCR < minimum). A fixed seed is reproducible.
    """
    if spec.simulations < 1:
        raise ValueError("simulations must be at least 1")
    rng = random.Random(spec.seed)

    unlevered: list[Decimal] = []
    levered: list[Decimal] = []
    below_hurdle = 0
    dscr_breaches = 0
    has_debt = deal.loan_amount > 0

    for _ in range(spec.simulations):
        trial = replace(
            deal,
            exit_cap_rate=_clamp(_draw(rng, deal.exit_cap_rate, spec.exit_cap_sd), MIN_EXIT_CAP, 1),
            rent_growth_rate=_clamp(
                _draw(rng, deal.rent_growth_rate, spec.rent_growth_sd),
                Decimal("-0.2"),
                Decimal("0.2"),
            ),
            vacancy_rate=_clamp(
                _draw(rng, deal.vacancy_rate, spec.vacancy_sd), Decimal(0), Decimal("0.5")
            ),
        )
        metrics = compute(trial)
        if metrics.unlevered_irr is not None:
            unlevered.append(metrics.unlevered_irr)
            if hurdle is not None and metrics.unlevered_irr < hurdle:
                below_hurdle += 1
        if metrics.levered_irr is not None:
            levered.append(metrics.levered_irr)
        if dscr_minimum is not None and has_debt:
            ratios = [
                cf.noi / cf.debt_service for cf in metrics.annual_cash_flows if cf.debt_service != 0
            ]
            if ratios and min(ratios) < dscr_minimum:
                dscr_breaches += 1

    n = Decimal(spec.simulations)
    return MonteCarloResult(
        simulations=spec.simulations,
        converged=len(unlevered),
        unlevered_irr=_distribution(unlevered),
        levered_irr=_distribution(levered),
        unlevered_histogram=_histogram(unlevered),
        prob_below_hurdle=(Decimal(below_hurdle) / n) if hurdle is not None else None,
        prob_dscr_below_minimum=(
            (Decimal(dscr_breaches) / n) if dscr_minimum is not None and has_debt else None
        ),
    )
