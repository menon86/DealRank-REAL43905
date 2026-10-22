"""Shared number formatting for the PDF and PPTX exports, so the two
report formats can't silently disagree on how a figure is displayed."""

from decimal import Decimal


def money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    # Sign before the symbol ("-$1,000"), not "$-1,000".
    return f"-${-value:,.0f}" if value < 0 else f"${value:,.0f}"


def percent(value: Decimal | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def multiple(value: Decimal | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}x"


def number(value: Decimal | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def short_name(name: str, limit: int = 34) -> str:
    """A deal name trimmed for a narrow column header; the full name is
    always shown elsewhere in the report."""
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "…"
