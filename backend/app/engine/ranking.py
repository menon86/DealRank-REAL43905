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

The spread is measured on the unlevered IRR *before* closing and selling
costs, because the hurdle is a gross market return with no transaction
costs (comparing it with a net IRR would penalize short holds).

The DSCR gate (lowest DSCR over the hold, so an interest-only start can't
hide a later breach) and the optional debt-yield gate exclude deals from
ranking entirely rather than blending them into the score. Among the deals
that pass, an optional preference layer blends three factors (return,
cash flow, safety) with user weights. Each factor is scaled against fixed
anchors, not against the other candidates, so a deal's score does not
change when another deal is added to or removed from the comparison.
Pure functions on Decimals — no DB, no HTTP.

Levered IRR never appears here, and the return and cash-flow factors are
unlevered. The safety factor is deliberately leverage-aware (DSCR and
leverage are what it measures), so a non-zero risk weight lets financing
choices move the order; with risk weight 0 it cannot.
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


def passes_dscr_gate(min_dscr: Decimal | None, minimum: Decimal) -> bool:
    """`min_dscr` is the lowest DSCR over the hold. None means no debt
    service (all-cash), which has nothing to fail."""
    return min_dscr is None or min_dscr >= minimum


def passes_debt_yield_gate(debt_yield: Decimal | None, minimum: Decimal | None) -> bool:
    """Year-one NOI over total debt. None means no debt; a None minimum
    means the gate is off."""
    return minimum is None or debt_yield is None or debt_yield >= minimum


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
    spread: Decimal  # unlevered IRR before costs - risk-adjusted hurdle
    cash_yield: Decimal  # year-one NOI / (price + closing costs)
    min_dscr: Decimal | None  # lowest DSCR over the hold; None = no debt
    leverage: Decimal  # (all debt + preferred equity) / purchase price


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


# (floor, ceiling): a value at or below the floor scores 0, at or above the
# ceiling scores 1, linear between.
SPREAD_ANCHORS = (Decimal("-0.03"), Decimal("0.05"))
CASH_YIELD_ANCHORS = (Decimal("0.03"), Decimal("0.08"))
DSCR_ANCHORS = (Decimal("1.0"), Decimal("2.0"))
EQUITY_SHARE_ANCHORS = (Decimal("0.2"), Decimal("0.6"))  # 1 - leverage


def _scale(value: Decimal, anchors: tuple[Decimal, Decimal]) -> Decimal:
    low, high = anchors
    return max(Decimal(0), min(Decimal(1), (value - low) / (high - low)))


def score_candidates(candidates: list[Candidate], weights: Weights) -> list[ScoredCandidate]:
    """Blends the three factors against fixed anchors: return = spread vs
    hurdle; cash flow = unlevered year-one cash yield; risk = the mean of
    scaled DSCR and scaled (1 - leverage), so more coverage and less
    leverage both score as safer. All-cash counts as maximum coverage.
    Output is in input order; callers sort.
    """
    w = weights.normalized()
    scored = []
    for c in candidates:
        dscr = ALL_CASH_DSCR_CAP if c.min_dscr is None else c.min_dscr
        factors = FactorScores(
            irr=_scale(c.spread, SPREAD_ANCHORS),
            cash_flow=_scale(c.cash_yield, CASH_YIELD_ANCHORS),
            risk=(_scale(dscr, DSCR_ANCHORS) + _scale(1 - c.leverage, EQUITY_SHARE_ANCHORS)) / 2,
        )
        score = w.irr * factors.irr + w.cash_flow * factors.cash_flow + w.risk * factors.risk
        scored.append(ScoredCandidate(key=c.key, factors=factors, score=score))
    return scored
