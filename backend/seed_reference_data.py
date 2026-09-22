"""Seed cap_rate_spreads with cap-rate-to-Treasury spreads transcribed from
published broker/lender surveys, one row per sub-asset class (see
app/models/deal.py's SubAssetClass). Data-only: nothing here is consumed by
the D2 ranking engine (see TASK.md).

Sources (each row's provenance, see comments below):
  - CBRE U.S. Cap Rate Survey, H1 2026 (August 2026)
    https://www.cbre.com/insights/reports/us-cap-rate-survey-h1-2026
  - Berkadia 2026 U.S. Student Housing Market Report
    https://www.berkadia.com/lp/2026-us-student-housing-market-report/
  - Yardi Matrix, "Yardi Matrix projects modest national multifamily rent
    growth for 2026" (press release, Aug 5, 2026)
    https://www.yardi.com/news/press-releases/yardi-matrix-projects-modest-national-multifamily-rent-growth-for-2026/
  - Yardi Matrix, National Student Housing Market Report (September 2026)
    https://www.yardimatrix.com/blog/student-housing-market-report/

Usage (with DATABASE_URL set, e.g. via docker-compose up + .env):
    python seed_reference_data.py
"""

import os
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import CapRateSpread

# CBRE's H1 2026 survey publishes per-metro Class A Stabilized cap rate
# *ranges* for "Multifamily Infill" and "Multifamily Suburban" (its closest
# analogues to this app's urban_midrise / suburban_garden), not a single
# national figure. spread_bps below = the unweighted mean of each metro
# range's midpoint (47 metros for Infill, 45 for Suburban) minus the
# 10-year Treasury yield the same report cites as "hovering near 4.6% as of
# mid-July" H1 2026 — i.e. a same-report, same-period comparison.
#
# Berkadia's report gives a single national average cap rate (5.9%, based
# on 2025 transactions through Feb 6, 2026) rather than a metro table, so
# its spread uses the same 4.6% Treasury reference for consistency across
# all three rows.
#
# assumed_stabilized_noi_growth is not published by either cap-rate survey
# (it's an appraisal-model input, not something these market surveys
# report) — sourced instead from Yardi Matrix rent-growth forecasts as the
# closest public proxy. Yardi's Aug 2026 multifamily press release gives
# only a single blended national multifamily figure (1.4%), not a
# garden-style vs. mid/high-rise breakdown, so the same figure is used for
# both suburban_garden and urban_midrise below.

SEED_CAP_RATE_SPREADS = [
    CapRateSpread(
        sub_asset_class="urban_midrise",
        survey_source="CBRE U.S. Cap Rate Survey H1 2026 (Multifamily Infill, Class A Stabilized)",
        survey_quarter="2026H1",
        spread_bps=60,  # mean metro midpoint 5.20% - 10yr Treasury 4.60%
        assumed_stabilized_noi_growth=Decimal("0.0140"),  # Yardi Matrix, Aug 5 2026 press release
        effective_date=date(2026, 8, 12),  # CBRE report publication date
    ),
    CapRateSpread(
        sub_asset_class="suburban_garden",
        survey_source="CBRE U.S. Cap Rate Survey H1 2026 (Multifamily Suburban, Class A Stabilized)",
        survey_quarter="2026H1",
        spread_bps=61,  # mean metro midpoint 5.21% - 10yr Treasury 4.60%
        assumed_stabilized_noi_growth=Decimal("0.0140"),  # Yardi Matrix, Aug 5 2026 press release
        effective_date=date(2026, 8, 12),  # CBRE report publication date
    ),
    CapRateSpread(
        sub_asset_class="student_housing",
        survey_source="Berkadia 2026 U.S. Student Housing Market Report (national avg. cap rate, 2025 sales)",
        survey_quarter="2025",
        spread_bps=130,  # national avg cap rate 5.90% - 10yr Treasury 4.60%
        assumed_stabilized_noi_growth=Decimal("0.0200"),  # Yardi Matrix Student Housing Report, Sept 2026
        effective_date=date(2026, 2, 6),  # Berkadia's stated as-of date for its 2025 sales data
    ),
]


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)
    with Session(engine) as session:
        session.add_all(SEED_CAP_RATE_SPREADS)
        session.commit()
    print(f"Seeded {len(SEED_CAP_RATE_SPREADS)} cap rate spreads.")


if __name__ == "__main__":
    main()
