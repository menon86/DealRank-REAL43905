"""Plain input/output types for the calculation engine.

Nothing here imports SQLAlchemy, FastAPI, or anything from app.models or
app.api — see the package docstring in app/engine/__init__.py. All money
and rate fields are Decimal; the engine never touches float except at the
IRR boundary (see metrics.py), where numpy-financial requires it.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal


class SubAssetClass(str, enum.Enum):
    STUDENT_HOUSING = "student_housing"
    SUBURBAN_GARDEN = "suburban_garden"
    URBAN_MIDRISE = "urban_midrise"


class LeasingMode(str, enum.Enum):
    PER_UNIT = "per_unit"
    PER_BED = "per_bed"


class LayerGroup(str, enum.Enum):
    SENIOR = "senior"
    SUBORDINATE = "subordinate"
    EQUITY = "equity"


class LayerType(str, enum.Enum):
    """Every financing source a capital stack layer can be. The group
    (senior debt / subordinate / equity) is fixed per type — see
    LAYER_GROUPS below.
    """

    # --- Senior debt ---
    AGENCY_FANNIE_MAE = "agency_fannie_mae"
    AGENCY_FREDDIE_MAC = "agency_freddie_mac"
    HUD_223F = "hud_223f"
    HUD_221D4 = "hud_221d4"
    BANK_CREDIT_UNION = "bank_credit_union"
    LIFE_COMPANY = "life_company"
    CMBS = "cmbs"
    BRIDGE_DEBT_FUND = "bridge_debt_fund"
    CONSTRUCTION = "construction"
    LOAN_ASSUMPTION = "loan_assumption"
    SELLER_FINANCING = "seller_financing"
    OTHER_SENIOR = "other_senior"

    # --- Subordinate / gap ---
    MEZZANINE = "mezzanine"
    PREFERRED_EQUITY = "preferred_equity"
    SUPPLEMENTAL_LOAN = "supplemental_loan"
    SELLER_CARRYBACK_SECOND = "seller_carryback_second"
    OTHER_SUBORDINATE = "other_subordinate"

    # --- Equity ---
    SPONSOR_GP = "sponsor_gp"
    LP_SYNDICATION = "lp_syndication"
    JV_PARTNER = "jv_partner"
    EXCHANGE_1031 = "exchange_1031"
    DST_TIC = "dst_tic"
    OPPORTUNITY_ZONE = "opportunity_zone"
    ALL_CASH = "all_cash"
    OTHER_EQUITY = "other_equity"

    @property
    def group(self) -> LayerGroup:
        return LAYER_GROUPS[self]

    @property
    def is_debt(self) -> bool:
        """Senior debt and every subordinate type except preferred equity
        (which is equity, not a loan: it earns a preferred return, isn't
        in debt service, and isn't in either DSCR).
        """
        return self.group is LayerGroup.SENIOR or (
            self.group is LayerGroup.SUBORDINATE and self is not LayerType.PREFERRED_EQUITY
        )

    @property
    def is_other(self) -> bool:
        return self in (LayerType.OTHER_SENIOR, LayerType.OTHER_SUBORDINATE, LayerType.OTHER_EQUITY)


LAYER_GROUPS: dict[LayerType, LayerGroup] = {
    **{
        t: LayerGroup.SENIOR
        for t in (
            LayerType.AGENCY_FANNIE_MAE,
            LayerType.AGENCY_FREDDIE_MAC,
            LayerType.HUD_223F,
            LayerType.HUD_221D4,
            LayerType.BANK_CREDIT_UNION,
            LayerType.LIFE_COMPANY,
            LayerType.CMBS,
            LayerType.BRIDGE_DEBT_FUND,
            LayerType.CONSTRUCTION,
            LayerType.LOAN_ASSUMPTION,
            LayerType.SELLER_FINANCING,
            LayerType.OTHER_SENIOR,
        )
    },
    **{
        t: LayerGroup.SUBORDINATE
        for t in (
            LayerType.MEZZANINE,
            LayerType.PREFERRED_EQUITY,
            LayerType.SUPPLEMENTAL_LOAN,
            LayerType.SELLER_CARRYBACK_SECOND,
            LayerType.OTHER_SUBORDINATE,
        )
    },
    **{
        t: LayerGroup.EQUITY
        for t in (
            LayerType.SPONSOR_GP,
            LayerType.LP_SYNDICATION,
            LayerType.JV_PARTNER,
            LayerType.EXCHANGE_1031,
            LayerType.DST_TIC,
            LayerType.OPPORTUNITY_ZONE,
            LayerType.ALL_CASH,
            LayerType.OTHER_EQUITY,
        )
    },
}


class RateType(str, enum.Enum):
    FIXED = "fixed"
    FLOATING = "floating"


@dataclass(frozen=True)
class FinancingLayer:
    """One layer of a deal's capital stack. Debt and preferred equity
    layers use the term fields; equity layers carry only an amount and an
    optional label (common equity in the math is always the residual —
    see app/engine/financing.py — so equity layer amounts describe who
    put the equity in, they don't change it).
    """

    layer_type: LayerType
    amount: Decimal
    label: str | None = None

    # --- Debt terms ---
    rate_type: RateType = RateType.FIXED
    interest_rate: Decimal | None = None  # fixed all-in rate
    index_name: str | None = None  # floating: e.g. "SOFR"
    index_rate: Decimal | None = None
    spread: Decimal | None = None
    io_months: int = 0
    # None = interest-only for the whole term (common for mezzanine).
    amortization_years: int | None = None
    # None = no maturity before the exit. A maturity inside the hold is
    # repaid as a balloon out of that year's levered cash flow (no
    # refinancing is modeled).
    term_years: int | None = None
    recourse: bool | None = None  # descriptive only, no effect on the math

    # --- Upfront costs, paid at closing out of equity ---
    rate_cap_cost: Decimal = Decimal("0")
    origination_fee_rate: Decimal = Decimal("0")

    # --- Preferred equity only ---
    preferred_return: Decimal | None = None

    @property
    def group(self) -> LayerGroup:
        return self.layer_type.group

    @property
    def is_debt(self) -> bool:
        return self.layer_type.is_debt

    @property
    def is_preferred_equity(self) -> bool:
        return self.layer_type is LayerType.PREFERRED_EQUITY

    @property
    def all_in_rate(self) -> Decimal:
        """Fixed: the interest rate. Floating: index + spread."""
        if self.rate_type is RateType.FLOATING:
            return (self.index_rate or Decimal("0")) + (self.spread or Decimal("0"))
        return self.interest_rate or Decimal("0")

    @property
    def upfront_cost(self) -> Decimal:
        """Origination fee plus rate cap — paid at closing, so it adds to
        the equity check (levered returns only; unlevered ignores
        financing entirely).
        """
        return self.amount * self.origination_fee_rate + self.rate_cap_cost


@dataclass(frozen=True)
class DealInputs:
    """Mirrors the nullable column pairs in app/models/deal.py: exactly one
    of the per-unit / per-bed branches is populated, matching leasing_mode.
    """

    name: str
    sub_asset_class: SubAssetClass
    leasing_mode: LeasingMode

    # --- GPR inputs (exactly one branch populated per leasing_mode) ---
    unit_count: int | None
    monthly_rent_per_unit: Decimal | None
    bed_count: int | None
    monthly_rent_per_bed: Decimal | None

    vacancy_rate: Decimal
    other_income_annual: Decimal

    # --- OpEx ---
    opex_annual: Decimal
    expense_growth_rate: Decimal
    rent_growth_rate: Decimal

    # --- Turnover / make-ready ---
    lease_expiration_month: int
    turnover_cost_per_unit_or_bed: Decimal
    annual_turnover_rate: Decimal

    # --- Acquisition / financing ---
    purchase_price: Decimal
    closing_costs: Decimal
    loan_amount: Decimal
    interest_rate: Decimal
    amortization_years: int

    # --- Hold / exit ---
    hold_period_years: int
    exit_cap_rate: Decimal
    selling_costs_rate: Decimal

    # --- Capital stack ---
    # Empty = the original single fixed-rate loan built from loan_amount /
    # interest_rate / amortization_years above. Non-empty = these layers
    # replace those three fields entirely (see app/engine/financing.py).
    capital_stack: tuple[FinancingLayer, ...] = ()

    # --- Optional lines (all default to 0, which reproduces the original model) ---
    # Other income grows at this rate (0 = flat, the original behaviour).
    other_income_growth_rate: Decimal = Decimal("0")
    # Share of GPR lost to bad debt and concessions, on top of vacancy.
    credit_loss_rate: Decimal = Decimal("0")
    # Share of EGI paid as a management fee; part of NOI.
    management_fee_rate: Decimal = Decimal("0")
    # Annual replacement reserve per unit or bed, grown at expense growth.
    # Paid below NOI (NOI, cap rate, DSCR and exit value are before reserves),
    # so it reduces cash flow and IRR but not the exit value.
    replacement_reserve_per_unit_or_bed: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.leasing_mode is LeasingMode.PER_UNIT:
            if self.unit_count is None or self.monthly_rent_per_unit is None:
                raise ValueError(
                    "per_unit leasing mode requires unit_count and monthly_rent_per_unit"
                )
            if self.bed_count is not None or self.monthly_rent_per_bed is not None:
                raise ValueError("per_unit leasing mode must not carry bed fields")
        elif self.leasing_mode is LeasingMode.PER_BED:
            if self.bed_count is None or self.monthly_rent_per_bed is None:
                raise ValueError("per_bed leasing mode requires bed_count and monthly_rent_per_bed")
            if self.unit_count is not None or self.monthly_rent_per_unit is not None:
                raise ValueError("per_bed leasing mode must not carry unit fields")
        else:  # pragma: no cover - exhaustive enum guard
            raise ValueError(f"unknown leasing_mode: {self.leasing_mode}")

        self._validate_ranges()

        if self.capital_stack:
            # Imported here: financing.py imports this module.
            from app.engine.financing import validate_capital_stack

            errors = validate_capital_stack(self.capital_stack)
            if errors:
                raise ValueError("; ".join(errors))

    def _validate_ranges(self) -> None:
        """Defense in depth behind the API's field constraints: a row edited
        directly in the DB, or a bad programmatic input, must not produce
        numbers from a negative rent or a vacancy rate above 100%.
        """
        non_negative = {
            "other_income_annual": self.other_income_annual,
            "opex_annual": self.opex_annual,
            "expense_growth_rate": self.expense_growth_rate,
            "turnover_cost_per_unit_or_bed": self.turnover_cost_per_unit_or_bed,
            "closing_costs": self.closing_costs,
            "loan_amount": self.loan_amount,
            "interest_rate": self.interest_rate,
            "selling_costs_rate": self.selling_costs_rate,
            "credit_loss_rate": self.credit_loss_rate,
            "management_fee_rate": self.management_fee_rate,
            "replacement_reserve_per_unit_or_bed": self.replacement_reserve_per_unit_or_bed,
        }
        for name, value in non_negative.items():
            if value < 0:
                raise ValueError(f"{name} can't be negative")
        shares = {
            "vacancy_rate": self.vacancy_rate,
            "annual_turnover_rate": self.annual_turnover_rate,
            "credit_loss_rate": self.credit_loss_rate,
            "management_fee_rate": self.management_fee_rate,
        }
        for name, value in shares.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 100%")
        positive = {
            "purchase_price": self.purchase_price,
            "exit_cap_rate": self.exit_cap_rate,
            "hold_period_years": self.hold_period_years,
            "monthly_rent_per_unit": self.monthly_rent_per_unit,
            "monthly_rent_per_bed": self.monthly_rent_per_bed,
            "unit_count": self.unit_count,
            "bed_count": self.bed_count,
        }
        for name, value in positive.items():
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be above zero")
        if self.selling_costs_rate >= 1:
            raise ValueError("selling_costs_rate must be below 100%")
        for name, value in (
            ("rent_growth_rate", self.rent_growth_rate),
            ("other_income_growth_rate", self.other_income_growth_rate),
        ):
            if value <= -1:
                raise ValueError(f"{name} must be above -100%")

    @property
    def unit_or_bed_count(self) -> int:
        """The count driving GPR and turnover, regardless of leasing mode."""
        return self.unit_count if self.leasing_mode is LeasingMode.PER_UNIT else self.bed_count


@dataclass(frozen=True)
class AnnualCashFlow:
    """One year's row in the waterfall. Every line a grader could want to
    trace independently is its own field — nothing is only available
    pre-summed.
    """

    year: int
    gpr: Decimal
    vacancy_loss: Decimal
    other_income: Decimal
    egi: Decimal
    opex: Decimal
    turnover_expense: Decimal
    noi: Decimal
    debt_service: Decimal
    interest_paid: Decimal
    principal_paid: Decimal
    ending_loan_balance: Decimal
    levered_cash_flow: Decimal
    unlevered_cash_flow: Decimal
    # Capital stack lines. debt_service above is every debt layer
    # (combined); the senior share is split out for senior DSCR. A balloon
    # is a loan maturing inside the hold, repaid out of that year's levered
    # cash flow — it isn't debt service, so it's in neither DSCR.
    senior_debt_service: Decimal = Decimal("0")
    balloon_payment: Decimal = Decimal("0")
    preferred_distribution: Decimal = Decimal("0")
    # Preferred return that couldn't be paid from cash flow this year, and
    # the running unpaid total (settled at exit).
    preferred_shortfall: Decimal = Decimal("0")
    preferred_accrued: Decimal = Decimal("0")
    # Optional lines.
    credit_loss: Decimal = Decimal("0")
    management_fee: Decimal = Decimal("0")
    replacement_reserves: Decimal = Decimal("0")


@dataclass(frozen=True)
class DealMetrics:
    """Everything the API's MetricsOut schema (section 5 of the build plan)
    needs, plus the full annual table for the comparison view.
    """

    annual_cash_flows: list[AnnualCashFlow] = field(default_factory=list)
    year_one_noi: Decimal = Decimal("0")
    going_in_cap_rate: Decimal = Decimal("0")
    year_one_dscr: Decimal | None = None
    cash_on_cash: Decimal | None = None
    unlevered_irr: Decimal | None = None
    levered_irr: Decimal | None = None
    equity_multiple: Decimal | None = None
    exit_value: Decimal = Decimal("0")
    net_sale_proceeds: Decimal = Decimal("0")
    # Inputs to the headline figures above, exposed so each formula can be
    # traced on screen: equity behind cash-on-cash and the equity
    # multiple, the multiple's numerator, and the exit arithmetic.
    equity_invested: Decimal = Decimal("0")
    total_distributions: Decimal = Decimal("0")
    forward_noi: Decimal = Decimal("0")
    selling_costs: Decimal = Decimal("0")
    loan_balance_at_exit: Decimal = Decimal("0")
    # Capital stack figures. year_one_dscr above is the combined DSCR
    # (NOI over every debt layer's service); senior DSCR counts only the
    # senior loan. Preferred equity is in neither.
    year_one_senior_dscr: Decimal | None = None
    total_debt: Decimal = Decimal("0")
    preferred_equity: Decimal = Decimal("0")
    upfront_financing_costs: Decimal = Decimal("0")
    preferred_equity_repayment: Decimal = Decimal("0")
    # Ranking inputs. Gross IRR is before closing and selling costs (the
    # basis the risk-adjusted hurdle is quoted on); min DSCR is the lowest
    # combined DSCR over the hold; debt yield is year-one NOI over all debt;
    # unlevered cash yield is year-one NOI over price + closing costs.
    unlevered_irr_before_costs: Decimal | None = None
    min_dscr: Decimal | None = None
    debt_yield: Decimal | None = None
    unlevered_cash_yield: Decimal = Decimal("0")
