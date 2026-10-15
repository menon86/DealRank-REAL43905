"""Market-rent reference data from CSV downloads (not APIs).

Zillow's Observed Rent Index (ZORI) and Apartment List's rent estimates
are published as CSVs; Zillow's Zestimate API does not cover rents. Both
are wide files — one row per geography, one column per month — which
parse_wide_rent_csv() normalizes into rows for the market_rents table.

Neither source classifies rents by sub-asset class, so rows are stored
with sub_asset_class="all" unless the caller says otherwise.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_rent import MarketRent

SOURCES = {"zillow_zori": "Zillow ZORI", "apartment_list": "Apartment List"}
ALL_CLASSES = "all"

# Column that names the geography, by publisher, in preference order.
NAME_COLUMNS = ("RegionName", "location_name", "Metro", "metro", "name")
# Zillow adds a "United States" row; STATE rows are also named by abbreviation.
_DATE_COLUMN = re.compile(r"^(\d{4})[-_](\d{2})(?:[-_](\d{2}))?$")


@dataclass(frozen=True)
class RentRow:
    geography: str
    period: date
    median_rent: Decimal


def _parse_period(header: str) -> date | None:
    m = _DATE_COLUMN.match(header.strip())
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), 1)


def parse_wide_rent_csv(text: str, months: int = 24) -> list[RentRow]:
    """Keeps the most recent `months` monthly columns per geography.
    Blank cells (geography has no estimate that month) are skipped.
    Periods are normalized to the first of the month.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    name_col = next((c for c in NAME_COLUMNS if c in reader.fieldnames), None)
    if name_col is None:
        raise ValueError(f"no geography column found (looked for {', '.join(NAME_COLUMNS)})")
    periods = {c: p for c in reader.fieldnames if (p := _parse_period(c)) is not None}
    if not periods:
        raise ValueError("no monthly date columns found (expected e.g. 2025-06-30 or 2025_06)")
    keep = set(sorted(set(periods.values()))[-months:])

    rows: list[RentRow] = []
    for record in reader:
        geography = (record.get(name_col) or "").strip()
        if not geography:
            continue
        for column, period in periods.items():
            if period not in keep:
                continue
            raw = (record.get(column) or "").strip()
            if not raw:
                continue
            try:
                rent = Decimal(raw).quantize(Decimal("0.01"))
            except InvalidOperation:
                continue
            rows.append(RentRow(geography=geography, period=period, median_rent=rent))
    return rows


def load_rows(
    db: Session, source: str, rows: list[RentRow], sub_asset_class: str = ALL_CLASSES
) -> tuple[int, int]:
    """Upserts rows keyed on (source, geography, sub_asset_class, period)
    so re-running an ingest on a refreshed CSV is safe. Returns
    (inserted, updated).
    """
    existing = {
        (r.geography, r.period): r
        for r in db.scalars(
            select(MarketRent).where(
                MarketRent.source == source, MarketRent.sub_asset_class == sub_asset_class
            )
        )
    }
    inserted = updated = 0
    for row in rows:
        current = existing.get((row.geography, row.period))
        if current is None:
            db.add(
                MarketRent(
                    source=source,
                    geography=row.geography,
                    sub_asset_class=sub_asset_class,
                    period=row.period,
                    median_rent=row.median_rent,
                )
            )
            inserted += 1
        elif current.median_rent != row.median_rent:
            current.median_rent = row.median_rent
            updated += 1
    db.flush()
    return inserted, updated


# ------------------------------------------------------------ sanity check


@dataclass(frozen=True)
class RentCheck:
    status: str  # ok | caution | flag | not_comparable | no_data
    deal_rent: Decimal | None
    market_rent: Decimal | None
    market_period: date | None
    source: str | None
    variance: Decimal | None  # (deal - market) / market
    market_yoy_growth: Decimal | None
    note: str


CAUTION_VARIANCE = Decimal("0.10")
FLAG_VARIANCE = Decimal("0.25")


def classify_variance(variance: Decimal) -> str:
    size = abs(variance)
    if size >= FLAG_VARIANCE:
        return "flag"
    if size >= CAUTION_VARIANCE:
        return "caution"
    return "ok"


def check_rent(
    db: Session,
    geography: str,
    *,
    per_unit_rent: Decimal | None,
    source: str | None = None,
) -> RentCheck:
    """Compares a deal's per-unit rent to the latest market median for a
    geography (and, when a year-earlier point exists, reports the market's
    trailing 12-month rent growth for comparing against rent_growth_rate).
    Per-bed deals are not comparable: both indexes are whole-unit rents.
    """
    if per_unit_rent is None:
        return RentCheck(
            "not_comparable",
            None,
            None,
            None,
            None,
            None,
            None,
            "Per-bed rents can't be compared with whole-unit market indexes "
            "(Zillow ZORI and Apartment List both publish per-unit rent).",
        )

    stmt = select(MarketRent).where(MarketRent.geography == geography)
    if source:
        stmt = stmt.where(MarketRent.source == source)
    rows = list(db.scalars(stmt.order_by(MarketRent.period.desc())))
    if not rows:
        return RentCheck(
            "no_data",
            per_unit_rent,
            None,
            None,
            None,
            None,
            None,
            f"No market rent data loaded for '{geography}'. "
            "Import a Zillow or Apartment List CSV (see ingest_market_rents.py).",
        )

    latest = rows[0]
    market = Decimal(latest.median_rent)
    variance = (per_unit_rent - market) / market

    prior = next(
        (
            r
            for r in rows
            if r.source == latest.source
            and r.period.year == latest.period.year - 1
            and r.period.month == latest.period.month
        ),
        None,
    )
    yoy = (market / Decimal(prior.median_rent) - 1) if prior else None

    status = classify_variance(variance)
    direction = "above" if variance > 0 else "below"
    note = (
        f"Deal rent is {abs(variance) * 100:.1f}% {direction} the "
        f"{SOURCES.get(latest.source, latest.source)} median "
        f"for {geography} ({latest.period:%b %Y})."
    )
    return RentCheck(
        status, per_unit_rent, market, latest.period, latest.source, variance, yoy, note
    )
