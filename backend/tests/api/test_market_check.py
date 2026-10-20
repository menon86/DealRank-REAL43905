from datetime import date
from decimal import Decimal as D

from app.models.market_rent import MarketRent
from tests.api.payloads import STUDENT_HOUSING_PAYLOAD, SUBURBAN_GARDEN_PAYLOAD


def _seed(db, rent_now="1500.00", rent_year_ago="1400.00", source="zillow_zori"):
    for period, rent in ((date(2026, 9, 1), rent_now), (date(2025, 9, 1), rent_year_ago)):
        db.add(
            MarketRent(
                source=source,
                geography="West Lafayette, IN",
                sub_asset_class="all",
                period=period,
                median_rent=D(rent),
            )
        )
    db.flush()


def _check(client, deal_id, geography="West Lafayette, IN", **params):
    return client.get(f"/deals/{deal_id}/rent-check", params={"geography": geography, **params})


def test_deal_rent_within_ten_percent_is_ok(client, db_session):
    _seed(db_session)
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]  # $1,450
    body = _check(client, deal_id).json()
    assert body["status"] == "ok"
    assert D(body["market_rent"]) == D("1500.00")
    assert D(body["variance"]) == (D("1450") - D("1500")) / D("1500")
    assert D(body["market_yoy_growth"]) == D("1500") / D("1400") - 1
    assert D(body["deal_rent_growth"]) == D("0.025")
    assert body["market_period"] == "2026-09-01"
    assert "below" in body["note"] and "Zillow ZORI" in body["note"]


def test_variance_bands(client, db_session):
    _seed(db_session, rent_now="1200.00")  # 1450 vs 1200 = +20.8% => caution
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    assert _check(client, deal_id).json()["status"] == "caution"


def test_large_variance_is_flagged(client, db_session):
    _seed(db_session, rent_now="1000.00")  # +45%
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    assert _check(client, deal_id).json()["status"] == "flag"


def test_no_data_for_geography(client, db_session):
    _seed(db_session)
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    body = _check(client, deal_id, geography="Nowhere, ZZ").json()
    assert body["status"] == "no_data" and body["variance"] is None
    assert "ingest_market_rents.py" in body["note"]


def test_per_bed_deals_are_not_comparable(client, db_session):
    _seed(db_session)
    deal_id = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()["id"]
    body = _check(client, deal_id).json()
    assert body["status"] == "not_comparable"
    assert body["variance"] is None


def test_source_filter_and_geography_list(client, db_session):
    _seed(db_session, source="zillow_zori")
    _seed(db_session, rent_now="1480.00", source="apartment_list")
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    body = _check(client, deal_id, source="apartment_list").json()
    assert D(body["market_rent"]) == D("1480.00") and body["source"] == "apartment_list"

    geos = client.get("/market-rents/geographies").json()
    assert {(g["geography"], g["source"]) for g in geos} == {
        ("West Lafayette, IN", "zillow_zori"),
        ("West Lafayette, IN", "apartment_list"),
    }
    assert all(g["latest_period"] == "2026-09-01" for g in geos)


def test_geography_is_required_and_unknown_deal_404s(client):
    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    assert client.get(f"/deals/{deal_id}/rent-check").status_code == 422
    assert _check(client, "00000000-0000-0000-0000-000000000000").status_code == 404


ZORI_CSV = (
    "RegionID,SizeRank,RegionName,RegionType,StateName,2025-08-31,2025-09-30\n"
    '394463,1,"Indianapolis, IN",msa,IN,1300,1320\n'
    '394463,2,"Columbus, OH",msa,OH,,1400\n'
)


def _upload(client, body, **params):
    params = {"source": "zillow_zori", **params}
    return client.post(
        "/market-rents/upload", params=params, content=body, headers={"content-type": "text/csv"}
    )


def test_upload_loads_rows_and_is_idempotent(client):
    first = _upload(client, ZORI_CSV)
    assert first.status_code == 200
    assert first.json() == {
        "source": "zillow_zori",
        "inserted": 3,
        "updated": 0,
        "geographies": 2,
    }
    again = _upload(client, ZORI_CSV).json()
    assert again["inserted"] == 0 and again["updated"] == 0

    geos = {g["geography"] for g in client.get("/market-rents/geographies").json()}
    assert geos == {"Indianapolis, IN", "Columbus, OH"}

    deal_id = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]
    check = _check(client, deal_id, geography="Indianapolis, IN").json()
    assert D(check["market_rent"]) == D("1320.00")


def test_upload_collapses_repeated_geography_period_rows(client):
    doubled = ZORI_CSV + '394463,3,"Indianapolis, IN",msa,IN,1301,1321\n'
    body = _upload(client, doubled).json()
    assert body["inserted"] == 3 and body["updated"] == 2


def test_upload_rejects_bad_files(client):
    assert _upload(client, "").status_code == 422
    assert _upload(client, "a,b\n1,2\n").status_code == 422
    assert _upload(client, b"\xff\xfe\x00bad").status_code == 422
    assert _upload(client, ZORI_CSV, source="costar").status_code == 422
