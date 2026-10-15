from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app.models.market_rent import MarketRent
from app.services.market_rents import load_rows, parse_wide_rent_csv

ZILLOW = """RegionID,SizeRank,RegionName,RegionType,StateName,2025-08-31,2025-09-30,2025-10-31
102001,0,United States,country,,1900.5,1910.25,1925
394535,40,"Indianapolis, IN",msa,IN,1500,,1550.126
"""

APARTMENT_LIST = """location_name,location_type,2025_09,2025_10
"Lafayette, IN",Metro,1105.5,1110
"""


def test_parse_zillow_wide_csv_keeps_recent_months_and_skips_blanks():
    rows = parse_wide_rent_csv(ZILLOW, months=2)
    got = {(r.geography, r.period): r.median_rent for r in rows}
    assert got == {
        ("United States", date(2025, 9, 1)): D("1910.25"),
        ("United States", date(2025, 10, 1)): D("1925.00"),
        # Indy's Sep cell is blank => skipped; Oct rounds to cents.
        ("Indianapolis, IN", date(2025, 10, 1)): D("1550.13"),
    }


def test_parse_apartment_list_underscore_dates():
    rows = parse_wide_rent_csv(APARTMENT_LIST)
    assert [(r.geography, r.period, r.median_rent) for r in rows] == [
        ("Lafayette, IN", date(2025, 9, 1), D("1105.50")),
        ("Lafayette, IN", date(2025, 10, 1), D("1110.00")),
    ]


@pytest.mark.parametrize(
    "text, message",
    [
        ("RegionName,foo\nx,1\n", "monthly date columns"),
        ("foo,2025-01-31\nx,1\n", "geography column"),
        ("", "no header"),
    ],
)
def test_parse_errors(text, message):
    with pytest.raises(ValueError, match=message):
        parse_wide_rent_csv(text)


def test_load_is_an_idempotent_upsert(db_session):
    rows = parse_wide_rent_csv(ZILLOW)
    assert load_rows(db_session, "zillow_zori", rows) == (5, 0)
    assert load_rows(db_session, "zillow_zori", rows) == (0, 0)

    revised = parse_wide_rent_csv(ZILLOW.replace("1925", "1930"))
    assert load_rows(db_session, "zillow_zori", revised) == (0, 1)
    stored = db_session.scalars(
        select(MarketRent).where(
            MarketRent.geography == "United States", MarketRent.period == date(2025, 10, 1)
        )
    ).one()
    assert stored.median_rent == D("1930.00")
    assert stored.source == "zillow_zori" and stored.sub_asset_class == "all"
