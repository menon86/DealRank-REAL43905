# TASK: Cap rate & market data setup

## Why
The charter's Tech Plan lists the cap rate spread lookup table and market rent
reference table as two of the three DB surfaces for this app. Neither is
*consumed* by the ranking engine in Deliverable 2 (that's D3's
Treasury+spread hurdle — see `app/engine/ranking.py`'s docstring and
`docs/build-plan.md` section 1), but the tables should be seeded with real
data now so D3 isn't blocked on data-gathering later, and so deployment ships
with the DB layer the charter describes as complete.

**Do not wire this into the D2 ranking logic.** `POST /rank` stays on the
single user-entered hurdle rate. This task is data-only.

## What to do

1. **Get the source reports** (gated behind download forms, not freely
   fetchable — you'll need to actually download them):
   - CBRE U.S. Cap Rate Survey, H1 2026 — https://www.cbre.com/insights/reports/us-cap-rate-survey-h1-2026
   - Berkadia 2026 U.S. Student Housing Market Report — https://www.berkadia.com/lp/2026-us-student-housing-market-report/
   - (JLL multifamily cap rate survey as a cross-check if available)

2. **Transcribe cap-rate-to-Treasury spreads** for the three sub-asset
   classes used in this app (`student_housing`, `suburban_garden`,
   `urban_midrise` — see `backend/app/models/deal.py`'s `SubAssetClass`
   enum) into `backend/app/models/cap_rate_spread.py`'s schema:
   - `sub_asset_class`, `survey_source`, `survey_quarter` (e.g. `"2026H1"`),
     `spread_bps`, `assumed_stabilized_noi_growth`, `effective_date`.
   - Note which published figure each row came from — this becomes the D3
     provenance memo's source list, so don't discard the citation.

3. **Write a seed script or migration** that inserts these rows into
   `cap_rate_spreads`. Follow the existing pattern in `backend/seed.py`
   (currently seeds `deals` only) — either extend that script or add a
   sibling `seed_reference_data.py`, whichever reads cleaner.

4. **Optional, same pattern:** seed `market_rents`
   (`backend/app/models/market_rent.py`) from Zillow Research / Apartment
   List CSVs if time allows. Not required for D2 submission.

## Acceptance
- `cap_rate_spreads` has one row per sub-asset class, each traceable to a
  named, dated published source — no fabricated numbers.
- Seeding is scripted and repeatable (re-running it against a fresh DB
  reproduces the same rows), not a one-off manual `INSERT`.
- Nothing in `app/engine/` or `app/api/rank.py` changes.
