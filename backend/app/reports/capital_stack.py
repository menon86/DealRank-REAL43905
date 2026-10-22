"""Capital stack table rows shared by the PDF and PPTX exports, so both
formats describe a deal's financing the same way. "Other" layers appear
under the name the user typed for them.
"""

from decimal import Decimal

from app.api.converters import engine_layer
from app.engine.types import (
    DealMetrics,
    FinancingLayer,
    LayerGroup,
    LayerType,
    PrepaymentType,
    RateType,
)
from app.models.deal import Deal
from app.reports.formatting import money, percent

LAYER_TYPE_LABELS: dict[LayerType, str] = {
    LayerType.AGENCY_FANNIE_MAE: "Agency – Fannie Mae",
    LayerType.AGENCY_FREDDIE_MAC: "Agency – Freddie Mac",
    LayerType.HUD_223F: "HUD/FHA 223(f)",
    LayerType.HUD_221D4: "HUD/FHA 221(d)(4)",
    LayerType.BANK_CREDIT_UNION: "Bank / credit union",
    LayerType.LIFE_COMPANY: "Life insurance company",
    LayerType.CMBS: "CMBS / conduit",
    LayerType.BRIDGE_DEBT_FUND: "Bridge / debt fund",
    LayerType.CONSTRUCTION: "Construction loan",
    LayerType.LOAN_ASSUMPTION: "Loan assumption",
    LayerType.SELLER_FINANCING: "Seller financing",
    LayerType.OTHER_SENIOR: "Other senior debt",
    LayerType.MEZZANINE: "Mezzanine debt",
    LayerType.PREFERRED_EQUITY: "Preferred equity",
    LayerType.SUPPLEMENTAL_LOAN: "Supplemental loan",
    LayerType.SELLER_CARRYBACK_SECOND: "Seller carryback second",
    LayerType.OTHER_SUBORDINATE: "Other subordinate",
    LayerType.SPONSOR_GP: "Sponsor / GP equity",
    LayerType.LP_SYNDICATION: "LP syndication",
    LayerType.JV_PARTNER: "JV partner",
    LayerType.EXCHANGE_1031: "1031 exchange proceeds",
    LayerType.DST_TIC: "DST / TIC",
    LayerType.OPPORTUNITY_ZONE: "Opportunity Zone fund",
    LayerType.ALL_CASH: "All cash",
    LayerType.OTHER_EQUITY: "Other equity",
}

GROUP_LABELS: dict[LayerGroup, str] = {
    LayerGroup.SENIOR: "Senior debt",
    LayerGroup.SUBORDINATE: "Subordinate",
    LayerGroup.EQUITY: "Equity",
}

CAPITAL_STACK_HEADERS = ["Layer", "Group", "Amount", "% of cost", "Rate", "Terms"]


def layer_name(layer: FinancingLayer) -> str:
    label = (layer.label or "").strip()
    if layer.layer_type.is_other:
        return label or LAYER_TYPE_LABELS[layer.layer_type]
    base = LAYER_TYPE_LABELS[layer.layer_type]
    return f"{base} ({label})" if label else base


def _rate(layer: FinancingLayer) -> str:
    if layer.is_preferred_equity:
        return f"{percent(layer.preferred_return)} pref"
    if not layer.is_debt:
        return "—"
    if layer.rate_type is RateType.FLOATING:
        index = layer.index_name or "Index"
        return f"{index} {percent(layer.index_rate)} + {percent(layer.spread)}"
    return f"{percent(layer.interest_rate)} fixed"


def _terms(layer: FinancingLayer) -> str:
    parts: list[str] = []
    if layer.is_debt:
        if layer.io_months:
            parts.append(f"{layer.io_months}-mo I/O")
        if layer.amortization_years is None:
            parts.append("interest-only")
        else:
            parts.append(f"{layer.amortization_years}-yr amort.")
        if layer.term_years is not None:
            parts.append(f"{layer.term_years}-yr term")
        if layer.recourse is not None:
            parts.append("recourse" if layer.recourse else "non-recourse")
        if layer.rate_cap_cost:
            parts.append(f"rate cap {money(layer.rate_cap_cost)}")
        if layer.mip_annual_rate or layer.mip_upfront_rate:
            annual, upfront = percent(layer.mip_annual_rate), percent(layer.mip_upfront_rate)
            parts.append(f"MIP {annual}/yr + {upfront} upfront")
        prepayment = _prepayment(layer)
        if prepayment:
            parts.append(prepayment)
    if layer.origination_fee_rate:
        parts.append(f"{percent(layer.origination_fee_rate)} fee")
    return ", ".join(parts) if parts else "—"


def _prepayment(layer: FinancingLayer) -> str | None:
    if layer.prepayment_type is PrepaymentType.STEP_DOWN:
        steps = "-".join(f"{rate * 100:g}" for rate in layer.prepayment_schedule)
        return f"prepay step-down {steps}%"
    if layer.prepayment_type is PrepaymentType.YIELD_MAINTENANCE:
        return f"yield maintenance (UST {percent(layer.prepayment_treasury_rate)})"
    if layer.prepayment_type is PrepaymentType.DEFEASANCE:
        return f"defeasance (UST {percent(layer.prepayment_treasury_rate)})"
    return None


def capital_stack_rows(deal: Deal, metrics: DealMetrics) -> list[list[str]]:
    """One row per layer (in the order entered), then the common equity
    the deal actually needs — the residual after debt and preferred
    equity, which is what levered returns are measured on.
    """
    total_cost = deal.purchase_price + deal.closing_costs + metrics.upfront_financing_costs

    def share(amount: Decimal) -> str:
        return percent(amount / total_cost, digits=1) if total_cost else "—"

    if deal.capital_stack:
        layers = [engine_layer(layer) for layer in deal.capital_stack]
        rows = [
            [
                layer_name(layer),
                GROUP_LABELS[layer.group],
                money(layer.amount),
                share(layer.amount),
                _rate(layer),
                _terms(layer),
            ]
            for layer in layers
        ]
    else:
        rows = []
        if deal.loan_amount > 0:
            rows.append(
                [
                    "Senior loan (type not specified)",
                    GROUP_LABELS[LayerGroup.SENIOR],
                    money(deal.loan_amount),
                    share(deal.loan_amount),
                    f"{percent(deal.interest_rate)} fixed",
                    f"{deal.amortization_years}-yr amort.",
                ]
            )

    rows.append(
        [
            "Common equity required",
            GROUP_LABELS[LayerGroup.EQUITY],
            money(metrics.equity_invested),
            share(metrics.equity_invested),
            "—",
            "residual after debt and preferred equity",
        ]
    )
    return rows
