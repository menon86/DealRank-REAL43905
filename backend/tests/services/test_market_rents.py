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


# Trimmed from the real Apartment_List_Rent_Estimates_2026_09.csv: one row per
# geography per bed size, and "Pittsburgh, PA" names both a metro and a city.
APARTMENT_LIST_REAL = (
    "location_name,location_type,location_fips_code,population,state,county,metro,"
    "bed_size,2026_07,2026_08,2026_09\n"
    '"Pittsburgh, PA",Metro,38300,2365501,,,"Pittsburgh, PA",overall,1271,1265,1256\n'
    '"Pittsburgh, PA",Metro,38300,2365501,,,"Pittsburgh, PA",1br,1058,1053,1046\n'
    '"Pittsburgh, PA",City,4261000,303843,Pennsylvania,Allegheny County,"Pittsburgh, PA",'
    "overall,1451,1440,1420\n"
    '"Pittsburgh, PA",City,4261000,303843,Pennsylvania,Allegheny County,"Pittsburgh, PA",'
    "1br,1265,1255,1238\n"
    "Texas,State,48,29243342,Texas,,,overall,1229,1230,1229\n"
)


def test_parse_apartment_list_real_format_keeps_overall_and_disambiguates_names():
    rows = parse_wide_rent_csv(APARTMENT_LIST_REAL)
    assert len(rows) == 9  # 3 geographies x 3 months, no 1br rows
    latest = {r.geography: r.median_rent for r in rows if r.period == date(2026, 9, 1)}
    assert latest == {
        "Pittsburgh, PA (Metro)": D("1256.00"),
        "Pittsburgh, PA (City)": D("1420.00"),
        "Texas": D("1229.00"),
    }


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
