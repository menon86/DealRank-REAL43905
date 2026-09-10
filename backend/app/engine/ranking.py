"""Ranking layer — EXTENSION POINT, not implemented yet.

Deliverable 2 (current): ranking is a simple sort of unlevered IRR minus a
single user-supplied hurdle rate. That logic lives inline in the /rank API
handler for now, not here, because it has no sub-class-specific behavior
yet.

Deliverable 3 (do not build until then): this module becomes the home for
the full risk-adjusted hurdle methodology:

    Risk-Adjusted Hurdle(sub_class) =
        10-Year Treasury (FRED)
        + cap_rate_spreads[sub_class]  (static, versioned survey lookup)
        + assumed_stabilized_noi_growth[sub_class]

    Rank Score = Unlevered IRR - Risk-Adjusted Hurdle(sub_class)

Also deferred to Deliverable 3, and belonging here once built:
  - DSCR gate (exclude deals below the configured minimum DSCR from
    ranking entirely, rather than blending DSCR into the score)
  - preference-weighted ranking across multiple criteria

Do not let ranking logic move into app/engine/calculations.py — the core
waterfall (NOI -> IRR/equity multiple/etc.) must stay independent of any
ranking/hurdle concept so it keeps being usable standalone.
"""
