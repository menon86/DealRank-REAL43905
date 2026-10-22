"""The deal inputs shown in each report, grouped the way an underwriter
reads them. Shared by the PDF and PPTX exports so the two list the same
fields under the same labels.
"""

import enum

from app.reports.formatting import money, percent

ASSUMPTION_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Property & revenue",
        [
            ("sub_asset_class", "Sub-asset class"),
            ("leasing_mode", "Leasing mode"),
            ("unit_count", "Unit count"),
            ("monthly_rent_per_unit", "Monthly rent / unit"),
            ("bed_count", "Bed count"),
            ("monthly_rent_per_bed", "Monthly rent / bed"),
            ("vacancy_rate", "Vacancy rate"),
            ("credit_loss_rate", "Bad debt & concessions"),
            ("other_income_annual", "Other income, annual"),
            ("other_income_growth_rate", "Other income growth"),
            ("rent_growth_rate", "Rent growth rate"),
            ("lease_expiration_month", "Lease expiration month"),
        ],
    ),
    (
        "Operating expenses",
        [
            ("opex_annual", "OpEx, annual"),
            ("expense_growth_rate", "Expense growth rate"),
            ("management_fee_rate", "Management fee (of EGI)"),
            ("replacement_reserve_per_unit_or_bed", "Replacement reserve / unit or bed"),
            ("turnover_cost_per_unit_or_bed", "Turnover cost / unit or bed"),
            ("annual_turnover_rate", "Annual turnover rate"),
        ],
    ),
    (
        "Acquisition & financing",
        [
            ("purchase_price", "Purchase price"),
            ("closing_costs", "Closing costs"),
            ("loan_amount", "Loan amount"),
            ("interest_rate", "Interest rate"),
            ("amortization_years", "Amortization (years)"),
        ],
    ),
    (
        "Hold & exit",
        [
            ("hold_period_years", "Hold period (years)"),
            ("exit_cap_rate", "Exit cap rate"),
            ("selling_costs_rate", "Selling costs rate"),
        ],
    ),
]

RATE_FIELDS = {
    "other_income_growth_rate",
    "credit_loss_rate",
    "management_fee_rate",
    "vacancy_rate",
    "expense_growth_rate",
    "rent_growth_rate",
    "annual_turnover_rate",
    "interest_rate",
    "exit_cap_rate",
    "selling_costs_rate",
}

MONEY_FIELDS = {
    "replacement_reserve_per_unit_or_bed",
    "monthly_rent_per_unit",
    "monthly_rent_per_bed",
    "other_income_annual",
    "opex_annual",
    "turnover_cost_per_unit_or_bed",
    "purchase_price",
    "closing_costs",
    "loan_amount",
}


def format_assumption_value(field: str, value: object) -> str:
    if value is None:
        return "—"
    if field in RATE_FIELDS:
        return percent(value)  # type: ignore[arg-type]
    if field in MONEY_FIELDS:
        return money(value)  # type: ignore[arg-type]
    if isinstance(value, enum.Enum):
        # str(SubAssetClass.SUBURBAN_GARDEN) is "SubAssetClass.SUBURBAN_GARDEN"
        # (the str+Enum mixin doesn't get StrEnum's plain __str__) — .value
        # is the "suburban_garden" a reader actually wants.
        return str(value.value).replace("_", " ")
    return str(value)


def present_rows(deal, groups):
    """(group title, [(label, formatted value)]) for each group, leaving out
    inputs the deal doesn't have (e.g. bed count on a per-unit deal) and
    groups left empty."""
    result = []
    for title, fields in groups:
        rows = [
            (label, format_assumption_value(field, getattr(deal, field)))
            for field, label in fields
            if getattr(deal, field) is not None
        ]
        if rows:
            result.append((title, rows))
    return result
