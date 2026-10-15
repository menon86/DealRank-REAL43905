# Methodology — Deliverable 2

The short version of the formulas actually implemented, so a grader (or a teammate) doesn't have
to read `backend/app/engine/` to understand what the numbers mean. Decisions D1–D8 referenced
below are the ones settled in [`docs/build-plan.md`](build-plan.md) section 2; this document
restates the three that most change what a reader sees (D1–D3) and summarizes the rest.

For a worked numeric example, see [`docs/golden-case-derivation.md`](golden-case-derivation.md) —
every formula below is checked against that derivation in `backend/tests/engine/test_golden_cases.py`.

## Revenue

```
GPR (per-unit) = unit_count x monthly_rent_per_unit x 12
GPR (per-bed)  = bed_count  x monthly_rent_per_bed  x 12
```

Both leasing modes converge on one function once GPR is resolved — there is no separate per-unit
and per-bed code path past this point.

```
Vacancy loss = GPR x vacancy_rate
EGI          = GPR - Vacancy loss + other_income_annual
```

GPR, and everything downstream of it, grows at `rent_growth_rate` compounding annually:
`year_N_GPR = year_1_GPR x (1 + rent_growth_rate) ^ (N - 1)`.

## Expenses and turnover

```
OpEx (year N) = opex_annual x (1 + expense_growth_rate) ^ (N - 1)
```

**Turnover is its own visible line, never folded into OpEx:**

```
Turnover (year N) = turnover_cost_per_unit_or_bed x (units or beds) x annual_turnover_rate
                     x (1 + expense_growth_rate) ^ (N - 1)
```

**Decision D3 — turnover timing.** `lease_expiration_month` is carried on every deal for display
and for a future monthly model, but it does not shift *when* turnover cost hits in this annual
model — the full year's turnover cost is charged evenly, every year. A deal with an August lease
expiration and a deal with a June lease expiration, all else equal, show identical turnover
timing in Deliverable 2.

```
NOI = EGI - OpEx - Turnover
```

## Debt

**Decision D2 — monthly amortization, annual reporting.** The loan is simulated month by month
(`monthly_rate = interest_rate / 12`, a level monthly payment solved from the standard annuity
formula), and the twelve months' interest and principal are summed into one annual figure. This
is deliberately *not* annual-only compounding, which would overstate how fast principal pays down
relative to how the loan actually amortizes.

```
Annual debt service = sum of 12 months' (interest + principal)
Levered cash flow    = NOI - Annual debt service
```

A `loan_amount` of `0` (all-cash) produces zero debt service every year, not a division error —
DSCR is reported as undefined for that deal rather than computed.

## Exit and sale proceeds

**Decision D1 — forward-NOI exit.** Exit value uses *year N+1* NOI (one year past the end of the
hold), not year N's trailing NOI, divided by the exit cap rate:

```
Exit value = NOI(hold_period_years + 1) / exit_cap_rate
```

This is the standard institutional convention — it matches how a market exit cap rate is actually
quoted (against the next full year of income a buyer will receive) — but it is the single formula
choice most likely to visibly move every downstream IRR if it were ever revisited, since it
changes the largest cash flow in the entire stream.

```
Selling costs      = Exit value x selling_costs_rate
Net sale proceeds  = Exit value - Selling costs - ending loan balance
```

## Headline metrics

```
Going-in cap rate = Year 1 NOI / purchase_price
Year 1 DSCR        = Year 1 NOI / Year 1 debt service   (undefined if debt service = 0)
Equity invested     = purchase_price + closing_costs - loan_amount
Cash-on-cash        = Year 1 levered cash flow / Equity invested
Equity multiple      = (sum of levered cash flows + net sale proceeds) / Equity invested
```

**Unlevered IRR** discounts a stream with *no debt anywhere*: the outlay is the full
`purchase_price + closing_costs`, each year's cash flow is NOI (not levered cash flow), and the
terminal year adds `Exit value - Selling costs` (no loan payoff, since there's no loan in this
stream).

**Levered IRR** discounts the actual investor stream: the outlay is
`purchase_price + closing_costs - loan_amount` (equity invested), each year's cash flow is the
levered cash flow (NOI minus debt service), and the terminal year adds the net sale proceeds
(which do subtract the loan payoff).

Both IRRs are computed with a Newton's-method solver (`numpy-financial` in the backend, a small
JS/TS port in the frontend's earlier mock client) and return `None`/`null` rather than raising or
returning a nonsense value when a cash-flow stream doesn't converge to a real solution.

## Ranking

**Decision D7 wasn't a ranking rule but is worth restating here:** percentages are whole numbers
in every UI form field, decimal fractions (`0.06`, not `6`) everywhere else — one conversion
boundary (`frontend/src/lib/format.ts`), so a stray missing `/ 100` can't silently ship a
100x-wrong number.

Deliverable 2's ranking is deliberately simple: sort selected deals by
`Unlevered IRR - hurdle_rate`, descending, where `hurdle_rate` is one flat rate the user types in
— not sub-class-specific, not a Treasury-anchored total-return figure. **Ranking always uses
Unlevered IRR, never Levered IRR** — levered IRR is shown for reference, because ranking on it
would let a deal win by taking on more leverage rather than by being a better asset. A deal whose
unlevered IRR doesn't converge sorts last rather than disappearing from the list.

**Deliverable 3 (Underwriting Flexibility & Risk Framework)** replaces the flat hurdle with a risk-adjusted,
sub-class-specific one (`10-Year Treasury + cap-rate spread + assumed stabilized NOI growth`) and
adds a DSCR gate that excludes deals below a configured minimum from ranking entirely, rather than
blending DSCR into the score. See the docstring in `backend/app/engine/ranking.py`.

---

## Deliverable 3 Advanced Underwriting Extensions

### 1. Granular Unit Mix Modeling

In institutional underwriting, properties are rarely modeled as a single aggregate unit count or bed count. Deliverable 3 supports a granular unit mix breakdown across 5 standardized unit types:
- **Studio**
- **1 Bedroom (1BR)**
- **2 Bedroom (2BR)**
- **3 Bedroom (3BR)**
- **4+ Bedroom (4BR+)**

For each unit type $t$, the analyst can specify:
- $\text{units}_t$: Number of units of type $t$
- $\text{beds\_per\_unit}_t$: Number of beds per unit (critical for Student Housing)
- $\text{avg\_sqft}_t$: Average square footage per unit
- $\text{monthly\_rent}_t$: Market/underwritten monthly rent per unit (or per bed in per-bed leasing mode)

#### Aggregate Revenue Formulation
$$\text{Total Units} = \sum_{t} \text{units}_t, \quad \text{Total Beds} = \sum_{t} (\text{units}_t \times \text{beds\_per\_unit}_t)$$

Gross Potential Rent (GPR) is computed directly from the unit mix:
$$\text{GPR}_{\text{per-unit}} = 12 \times \sum_{t} (\text{units}_t \times \text{monthly\_rent}_t)$$
$$\text{GPR}_{\text{per-bed}} = 12 \times \sum_{t} (\text{units}_t \times \text{beds\_per\_unit}_t \times \text{monthly\_rent\_per\_bed}_t)$$

The weighted average rent per unit, weighted average rent per bed, and weighted average rent per square foot are derived automatically for benchmarking against market comp tables.

---

### 2. Housing-Type Specific Custom Inputs & Ancillary Revenue

Different multifamily asset sub-classes feature fundamentally distinct revenue and operational expense drivers:

#### A. Suburban Garden
- **Parking**: Surface parking stalls vs. detached garages vs. carports.
  $$\text{Parking Revenue} = 12 \times \sum (\text{stalls}_k \times \text{monthly\_rate}_k \times \text{occupancy}_k)$$
- **Storage**: Storage locker/unit counts and monthly fees.
- **Pet Revenue**: Monthly pet rent plus non-refundable pet fees amortized over average tenancy.
- **Utility Reimbursement (RUBS)**: Ratio Utility Billing System recovery percentage applied against water, sewer, and trash OpEx.

#### B. Student Housing
- **Per-Bed Leasing & Parental Guarantees**: Higher bad-debt recovery and individualized student leases.
- **Lease Expiration Concentration**: August turnover surge modeling (turnover rate routinely 75%–90%).
- **Mandatory Fee Packages**: Technology package fee (high-speed Wi-Fi), furniture package fees, and utility caps.
- **Summer Operations**: Summer term occupancy / short-term sublease bridge adjustments.

#### C. Urban Mid-Rise
- **Structured Parking**: Subterranean or structured garage parking stalls, higher monthly rates per stall, and parking ratio constraints (stalls / unit).
- **Ground-Floor Commercial / Retail**: Commercial square footage leased on NNN terms, providing non-residential ancillary income.
- **High-Density Amenities**: Dedicated concierge, package locker systems, and rooftop amenity premium fees.

#### Other Income Aggregation
$$\text{Other Income Annual} = \text{Parking Income} + \text{Storage Income} + \text{Pet Fees} + \text{Tech/Utility Fees} + \text{Commercial NNN} + \text{Miscellaneous}$$

---

### 3. Flexible Financing Structures & Loan Types

Deliverable 2 modeled a single fixed-rate amortizing loan with level monthly payments. Deliverable 3 introduces institutional financing flexibility:

#### A. Interest-Only (I/O) Periods
Borrowers frequently negotiate 1 to 5 years of interest-only payments before principal amortization begins:
- **During I/O Period ($m \le 12 \times \text{io\_years}$)**:
  $$\text{Monthly Payment} = \text{loan\_amount} \times \left(\frac{\text{interest\_rate}}{12}\right)$$
  $$\text{Principal Paid} = 0$$
- **Post-I/O Amortization Period ($m > 12 \times \text{io\_years}$)**:
  The loan amortizes over the *remaining* term ($\text{amortization\_years} - \text{io\_years}$):
  $$\text{Monthly Payment} = \text{loan\_amount} \times \frac{r(1+r)^{12 \times (\text{amort\_years} - \text{io\_years})}}{(1+r)^{12 \times (\text{amort\_years} - \text{io\_years})} - 1}$$
  where $r = \frac{\text{interest\_rate}}{12}$.

#### B. Floating-Rate Financing
- Modeled as **Reference Index (SOFR) + Margin / Spread**.
- Supports user-defined interest rate caps and index forward curves.

#### C. Balloon Payments at Loan Maturity
- Loan term (e.g., 5 or 7 years) may be shorter than the 30-year amortization schedule.
- At loan maturity or hold exit (whichever occurs first), the outstanding principal balance is paid in full as a balloon payment, properly factored into terminal net sale proceeds or refinancing cash flow.

#### D. Multi-Tranche Debt (Senior + Mezzanine)
- Blended Cost of Capital and composite DSCR calculation:
  $$\text{Composite DSCR} = \frac{\text{NOI}}{\text{Senior Debt Service} + \text{Mezzanine Debt Service}}$$

---

### 4. Excel Import / Upload Integration

To eliminate repetitive manual data entry, analysts can ingest property underwriting details and debt terms directly from standard Excel workbooks (`.xlsx`, `.xls`) or CSV files:

- **Property Details & Unit Mix Workbook**: Automatically maps columns for property identification, sub-asset class selection, 5-tier unit mix matrix, operating expenses, and turnover assumptions.
- **Financing Workbook**: Automatically ingests debt structure, LTV, loan amount, interest rate, I/O period, amortization duration, and loan fees.
- **Validation Engine**: Performs schema validation, verifies leasing-mode consistency, checks for positive unit counts and non-negative rents, and returns cell-level validation errors before database persistence.

