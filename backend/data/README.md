# Reference data

`zillow_zori_metro_all_homes_plus_multifamily.csv` — Zillow Observed Rent Index (ZORI),
smoothed, all homes plus multifamily, metro level, most recent 24 months (Oct 2024 – Sep 2026).
Downloaded from <https://www.zillow.com/research/data/>. Source: Zillow Observed Rent Index
(ZORI), Zillow Research.

Loaded into `market_rents` by `seed_market_rents.py` (skipped once Zillow rows exist).
To refresh, upload a newer CSV in the app's Market check tab, or run
`python ingest_market_rents.py zillow_zori <file.csv>`.
