"""Risk-adjusted ranking layer (Deliverable 3).

    Risk-Adjusted Hurdle(sub_class) =
        10-Year Treasury
        + cap_rate_spreads[sub_class]        (static, versioned survey lookup)
        + assumed_stabilized_noi_growth[sub_class]

    Spread-vs-hurdle = Unlevered IRR - Risk-Adjusted Hurdle(sub_class)

Treasury + cap-rate spread is the market cap rate; adding stabilized NOI
growth turns it into an expected unlevered total return, which is the
quantity an unlevered IRR is comparable to. Using each deal's own
sub-class hurdle is what makes student housing, garden and mid-rise deals
comparable on one scale.

The DSCR gate excludes under-covered deals from ranking entirely rather
than blending DSCR into the score. Among the deals that pass, an optional
preference layer blends three normalized factors (return, cash flow,
safety) with user weights. Pure functions on Decimals — no DB, no HTTP.

Levered IRR never appears here: leverage choice must not decide a ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

BPS = Decimal("10000")
DEFAULT_DSCR_MINIMUM = Decimal("1.25")

# An all-cash deal has no DSCR; for scoring it is treated as this very
# comfortable coverage rather than as zero or infinity.
ALL_CASH_DSCR_CAP = Decimal("3")


@dataclass(frozen=True)
class RiskAdjustedHurdle:
    treasury_yield: Decimal
    spread_bps: int
    noi_growth: Decimal

    @property
    def cap_rate(self) -> Decimal:
        return self.treasury_yield + Decimal(self.spread_bps) / BPS

    @property
    def total(self) -> Decimal:
        return self.cap_rate + self.noi_growth


def passes_dscr_gate(year_one_dscr: Decimal | None, minimum: Decimal) -> bool:
    """None means no debt service (all-cash), which has nothing to fail."""
    return year_one_dscr is None or year_one_dscr >= minimum


# ---------------------------------------------------------------- preferences


@dataclass(frozen=True)
class Weights:
    irr: Decimal
    cash_flow: Decimal
    risk: Decimal

    def normalized(self) -> Weights:
        total = self.irr + self.cash_flow + self.risk
        if total <= 0:
            raise ValueError("at least one preference weight must be positive")
        return Weights(self.irr / total, self.cash_flow / total, self.risk / total)


RETURN_ONLY = Weights(Decimal(1), Decimal(0), Decimal(0))

GOAL_BASE_WEIGHTS = {
    "total_return": Weights(Decimal("0.6"), Decimal("0.2"), Decimal("0.2")),
    "cash_flow": Weights(Decimal("0.2"), Decimal("0.6"), Decimal("0.2")),
    "preservation": Weights(Decimal("0.2"), Decimal("0.2"), Decimal("0.6")),
}

# risk_tolerance 1 (capital preservation) .. 5 (aggressive): scales the
# safety weight up or down before renormalizing.
RISK_TOLERANCE_FACTOR = {
    1: Decimal("1.5"),
    2: Decimal("1.25"),
    3: Decimal("1"),
    4: Decimal("0.75"),
    5: Decimal("0.5"),
}

# income_need 1 (irrelevant) .. 5 (essential): scales the cash-flow weight.
INCOME_NEED_FACTOR = {
    1: Decimal("0.5"),
    2: Decimal("0.75"),
    3: Decimal("1"),
    4: Decimal("1.25"),
    5: Decimal("1.5"),
}


def questionnaire_to_weights(primary_goal: str, risk_tolerance: int, income_need: int) -> Weights:
    """Turns three questionnaire answers into normalized factor weights:
    the primary goal picks a base mix, then risk tolerance scales the
    safety weight and income need scales the cash-flow weight.
    """
    if primary_goal not in GOAL_BASE_WEIGHTS:
        raise ValueError(f"primary_goal must be one of {sorted(GOAL_BASE_WEIGHTS)}")
    if risk_tolerance not in RISK_TOLERANCE_FACTOR:
        raise ValueError("risk_tolerance must be an integer 1-5")
    if income_need not in INCOME_NEED_FACTOR:
        raise ValueError("income_need must be an integer 1-5")
    base = GOAL_BASE_WEIGHTS[primary_goal]
    return Weights(
        irr=base.irr,
        cash_flow=base.cash_flow * INCOME_NEED_FACTOR[income_need],
        risk=base.risk * RISK_TOLERANCE_FACTOR[risk_tolerance],
    ).normalized()


@dataclass(frozen=True)
class Candidate:
    """One gate-passing deal's inputs to the preference score."""

    key: str
    spread: Decimal  # unlevered IRR - risk-adjusted hurdle
    cash_on_cash: Decimal | None
    year_one_dscr: Decimal | None
    ltv: Decimal  # loan / purchase price


@dataclass(frozen=True)
class FactorScores:
    irr: Decimal
    cash_flow: Decimal
    risk: Decimal


@dataclass(frozen=True)
class ScoredCandidate:
    key: str
    factors: FactorScores
    score: Decimal


def _min_max(values: list[Decimal]) -> list[Decimal]:
    """Scales to 0..1 across the candidate set. When every deal ties, no
    deal is advantaged, so all get the neutral 0.5.
    """
    low, high = min(values), max(values)
    if high == low:
        return [Decimal("0.5")] * len(values)
    return [(v - low) / (high - low) for v in values]


def _safety_raw(c: Candidate) -> tuple[Decimal, Decimal]:
    dscr = ALL_CASH_DSCR_CAP if c.year_one_dscr is None else min(c.year_one_dscr, ALL_CASH_DSCR_CAP)
    return dscr, 1 - c.ltv


def score_candidates(candidates: list[Candidate], weights: Weights) -> list[ScoredCandidate]:
    """Blends the three factors, each min-max normalized across the
    candidates: return = spread vs hurdle; cash flow = year-one
    cash-on-cash; risk = the mean of normalized DSCR and normalized
    (1 - LTV), so more coverage and less leverage both score as safer.
    Output is in input order; callers sort.
    """
    if not candidates:
        return []
    w = weights.normalized()
    irr_n = _min_max([c.spread for c in candidates])
    coc_n = _min_max([c.cash_on_cash or Decimal(0) for c in candidates])
    dscr_n = _min_max([_safety_raw(c)[0] for c in candidates])
    ltv_n = _min_max([_safety_raw(c)[1] for c in candidates])

    scored = []
    for i, c in enumerate(candidates):
        risk_n = (dscr_n[i] + ltv_n[i]) / 2
        factors = FactorScores(irr=irr_n[i], cash_flow=coc_n[i], risk=risk_n)
        score = w.irr * factors.irr + w.cash_flow * factors.cash_flow + w.risk * factors.risk
        scored.append(ScoredCandidate(key=c.key, factors=factors, score=score))
    return scored
