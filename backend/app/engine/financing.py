"""Capital stack helpers: which layers are debt / preferred equity, the
totals the waterfall and metrics need, and the stack validation rules.

A deal with no capital stack keeps the original single fixed-rate loan
(loan_amount / interest_rate / amortization_years). It's modeled here as
one implicit senior layer with no interest-only period and no maturity,
which reproduces the original amortization exactly — every pre-existing
golden case is unchanged.

Common equity is always the residual: price + closing costs + upfront
financing costs − all debt − preferred equity. Equity layer amounts
describe where that equity came from; they don't change the math.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.types import DealInputs, FinancingLayer, LayerGroup, LayerType, RateType

MONTHS_PER_YEAR = 12


def debt_layers(deal: DealInputs) -> list[FinancingLayer]:
    """Every layer that's a loan, senior first. For a deal without a
    capital stack, the implicit senior loan (or nothing for loan_amount 0).
    """
    if deal.capital_stack:
        layers = [layer for layer in deal.capital_stack if layer.is_debt]
        return sorted(layers, key=lambda layer: layer.group is not LayerGroup.SENIOR)
    if deal.loan_amount == 0:
        return []
    return [
        FinancingLayer(
            layer_type=LayerType.OTHER_SENIOR,
            amount=deal.loan_amount,
            interest_rate=deal.interest_rate,
            amortization_years=deal.amortization_years,
        )
    ]


def preferred_equity_layers(deal: DealInputs) -> list[FinancingLayer]:
    return [layer for layer in deal.capital_stack if layer.is_preferred_equity]


def total_debt(deal: DealInputs) -> Decimal:
    return sum((layer.amount for layer in debt_layers(deal)), Decimal("0"))


def total_preferred_equity(deal: DealInputs) -> Decimal:
    return sum((layer.amount for layer in preferred_equity_layers(deal)), Decimal("0"))


def upfront_financing_costs(deal: DealInputs) -> Decimal:
    """Origination fees and rate caps across every layer, paid at closing."""
    return sum((layer.upfront_cost for layer in deal.capital_stack), Decimal("0"))


def annual_preferred_distribution(deal: DealInputs) -> Decimal:
    """Preferred return paid current each year, ahead of common equity."""
    return sum(
        (
            layer.amount * (layer.preferred_return or Decimal("0"))
            for layer in preferred_equity_layers(deal)
        ),
        Decimal("0"),
    )


# A deal whose debt and preferred equity cover (nearly) the whole cost has no
# real common equity: cash-on-cash, the multiple and levered IRR stop meaning
# anything, so the API rejects it.
MIN_COMMON_EQUITY_SHARE = Decimal("0.05")


def common_equity_errors(
    purchase_price: Decimal,
    closing_costs: Decimal,
    layers: tuple[FinancingLayer, ...] | list[FinancingLayer],
) -> list[str]:
    """Rule: common equity (price + closing + upfront financing costs - all
    debt - preferred equity) must be at least MIN_COMMON_EQUITY_SHARE of
    that total cost.
    """
    debt = sum((layer.amount for layer in layers if layer.is_debt), Decimal("0"))
    preferred = sum((layer.amount for layer in layers if layer.is_preferred_equity), Decimal("0"))
    upfront = sum((layer.upfront_cost for layer in layers), Decimal("0"))
    total_cost = purchase_price + closing_costs + upfront
    equity = total_cost - debt - preferred
    if equity < total_cost * MIN_COMMON_EQUITY_SHARE:
        return [
            f"Debt and preferred equity total {debt + preferred:,.0f} against a total cost of "
            f"{total_cost:,.0f}; common equity must be at least "
            f"{MIN_COMMON_EQUITY_SHARE:.0%} of total cost."
        ]
    return []


def validate_capital_stack(layers: tuple[FinancingLayer, ...] | list[FinancingLayer]) -> list[str]:
    """Returns every rule the stack breaks (empty list = valid). Shared by
    DealInputs and the API schema so both reject the same stacks.
    """
    errors: list[str] = []

    seniors = [layer for layer in layers if layer.group is LayerGroup.SENIOR]
    equity = [layer for layer in layers if layer.group is LayerGroup.EQUITY]
    all_cash = any(layer.layer_type is LayerType.ALL_CASH for layer in layers)

    if all_cash:
        if any(layer.is_debt for layer in layers):
            errors.append("An all-cash deal can't also have debt layers.")
    elif len(seniors) == 0:
        errors.append(
            "Add exactly one senior debt layer, or an All cash equity layer if the deal has "
            "no debt."
        )
    elif len(seniors) > 1:
        errors.append("Only one senior debt layer is allowed.")

    if not equity:
        errors.append("Add at least one equity layer.")

    for index, layer in enumerate(layers, start=1):
        prefix = f"Layer {index}"
        if layer.layer_type.is_other and not (layer.label or "").strip():
            errors.append(f"{prefix}: an Other layer needs a name.")
        if layer.amount < 0:
            errors.append(f"{prefix}: amount can't be negative.")

        if layer.is_preferred_equity:
            if layer.amount <= 0:
                errors.append(f"{prefix}: preferred equity needs an amount above zero.")
            if layer.preferred_return is None:
                errors.append(f"{prefix}: preferred equity needs a preferred return.")

        if not layer.is_debt:
            continue

        if layer.amount <= 0:
            errors.append(f"{prefix}: a debt layer needs an amount above zero.")
        if layer.rate_type is RateType.FLOATING:
            if layer.index_rate is None or layer.spread is None:
                errors.append(f"{prefix}: floating-rate layers need an index rate and a spread.")
        elif layer.interest_rate is None:
            errors.append(f"{prefix}: fixed-rate layers need an interest rate.")
        if layer.io_months < 0:
            errors.append(f"{prefix}: interest-only months can't be negative.")
        if layer.term_years is not None and layer.io_months > layer.term_years * MONTHS_PER_YEAR:
            errors.append(f"{prefix}: interest-only months can't exceed the term.")
        if (
            layer.amortization_years is not None
            and layer.io_months >= layer.amortization_years * MONTHS_PER_YEAR
        ):
            errors.append(
                f"{prefix}: the amortization period must be longer than the interest-only period."
            )

    return errors
