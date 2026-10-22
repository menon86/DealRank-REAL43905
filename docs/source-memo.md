---
title: "DealRank: Source Memo"
---

**What this is.** A list of every data input DealRank uses, where it came from and how fresh it is, followed by a plain-English account of how the numbers are produced. Anything that is not real market data is labelled **synthetic** or **user assumption**.

## 1. Data inputs

| Input | Type | Source and date | Used for |
|---|---|---|---|
| 10-year Treasury yield | Public API, live | FRED series DGS10 (fred.stlouisfed.org); if FRED is down, the US Treasury daily yield-curve feed (home.treasury.gov). Cached up to 6 hours. If both fail, a fixed 4.60% is used and the screen says "fallback". A user can also type an override, labelled "override". | Base of every hurdle |
| Cap-rate spread, urban mid-rise (60 bps) and suburban garden (61 bps) | Published survey, hand-transcribed | CBRE U.S. Cap Rate Survey H1 2026 (published 12 Aug 2026), Class A stabilized multifamily. Average of metro midpoints (5.20% infill, 5.21% suburban) minus the 4.60% Treasury the report cites. | Hurdle |
| Cap-rate spread, student housing (130 bps) | Published survey, hand-transcribed | Berkadia 2026 U.S. Student Housing Market Report: national average cap rate 5.90% on 2025 sales, as of 6 Feb 2026, minus the same 4.60%. | Hurdle |
| Stabilized NOI growth: 1.4% (garden, mid-rise), 2.0% (student) | Published forecast, hand-transcribed | Yardi Matrix, national multifamily rent-growth press release (5 Aug 2026) for 1.4%; Yardi Matrix Student Housing Report (Sept 2026) for 2.0%. Yardi gives one blended multifamily figure, so garden and mid-rise share it. **Re-check the 2.0% against the report before citing it.** | Hurdle |
| Market rents by metro | Public data download | Zillow Observed Rent Index (ZORI), all homes plus multifamily, smoothed, metro level, 24 months Oct 2024 to Sep 2026, from zillow.com/research/data. Added to the project 20 Oct 2026; the exact download date was not recorded. Apartment List files can be loaded the same way but none are bundled. | Rent sanity check only; never feeds returns |
| 18 demo deals (6 per property type) | **Synthetic** | Fictional properties with rents, costs, prices and loans set to look plausible against the ranges above. Not real listings. | Demonstration |
| 3 example deals and their hand-worked answers | **Synthetic** | Canned examples used to prove the math (docs/golden-case-derivation.md). | Testing |
| Every deal a user types in | **User assumption** | Rents, vacancy, expenses, price, loan terms, exit cap, hold period. | All returns |
| Modeling settings | **Judgment, not data** | 1.25x minimum debt coverage; scoring ranges; Monte Carlo spreads (exit cap ±0.50%, rent growth ±1.0%, vacancy ±2.0%). | Gates, scores, risk ranges |

**CoStar.** No CoStar data is loaded or used anywhere in the application. If comps are pulled before the pitch, they need to be added here with a pull date, and should be described as a cross-check on the user-entered rents, not as an input.

**What is not in the app.** No live listings, no transaction database, no lender quotes. The cap-rate spreads are a snapshot: they were measured against a 4.60% Treasury, while the live Treasury moves.

## 2. How the numbers are produced

**Step 1: project each property.** For each year of the hold we start with rent (units × monthly rent × 12), subtract vacancy and any bad debt, and add other income. We then subtract operating costs, turnover costs and (if entered) a management fee. What is left is **net operating income (NOI)**, the property's cash earnings before any loan. Rents and costs grow at the rates the analyst chooses. Replacement reserves, if entered, are deducted below NOI.

**Step 2: the loan.** Each loan is run month by month: interest-only periods, then level payments, with balloons if the loan comes due during the hold. Mezzanine debt and preferred equity are layered on the same way. Cash left after loan payments is the investor's cash flow.

**Step 3: the sale.** At the end of the hold the property is valued at next year's NOI divided by the exit cap rate (what a buyer would pay for the income they are about to receive). We subtract selling costs, repay the loans and any preferred equity, and the remainder goes to the investor.

**Step 4: the returns.** The **unlevered IRR** is the annual return on the whole purchase price as if bought with no debt. The **levered IRR** is the return on the investor's own money after the loan. Debt coverage (DSCR) is NOI divided by loan payments.

**Step 5: ranking.** We rank on the **unlevered** return, because ranking on the levered one would let a deal win just by borrowing more. Each deal is compared with a **hurdle**: what the market expects from that type of property.

> Hurdle = 10-year Treasury + the survey spread between cap rates and Treasuries + expected income growth

A deal's **spread** is its unlevered IRR (before closing and selling costs, which the hurdle does not include) minus its own hurdle. Student housing, garden and mid-rise deals each use their own hurdle, so they can be compared fairly. Two safeguards apply:

- **Gates remove a deal from the ranking** rather than quietly marking it down: the lowest debt coverage in any year of the hold must reach 1.25x, and an optional minimum on NOI relative to total debt. A deal that cannot pay its loan does not rank.
- **Warnings** flag assumptions that flatter the answer, such as an exit cap below the entry cap, or rent growth well above the market growth the hurdle assumes.

Optionally, three scores (return, cash flow, safety) are blended using the user's stated preferences. Each score is measured against fixed ranges, so adding another deal to the comparison never changes the scores of the others.

**Step 6: stress tests.** Sliders and a 1,000-run simulation vary the exit cap rate, rent growth and vacancy around the user's assumptions, and report the range of returns and the chance of falling below the hurdle or the coverage minimum. A seed is shown so any run can be reproduced.

## 3. Limits to state out loud

- Returns are only as good as the assumptions typed in. The app checks that they are possible (no negative rents, no deal funded entirely by debt), not that they are right.
- Cash flows are annual, and a loan due during the hold is repaid from cash flow rather than refinanced.
- The market-rent check compares whole-unit rents and is not run for student housing leased by the bed.
- Reference figures are as of the dates above and need refreshing each quarter.
