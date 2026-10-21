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

Both IRRs are computed with `numpy-financial` and return `None`/`null` rather than raising or
returning a nonsense value when a cash-flow stream doesn't converge, **or when it changes sign
more than once** (for example a loan balloon repaid out of operating cash flow), because such a
stream can have several IRRs and picking one would be arbitrary.

Exit value is floored at zero: a property with negative forward NOI is worth nothing, not a
negative amount. Cash-on-cash and the equity multiple are `None` when common equity is zero or
negative.

## Optional underwriting lines

Each is a deal input that defaults to 0, which reproduces the model above exactly.

```
Other income (year N) = other_income_annual x (1 + other_income_growth_rate) ^ (N - 1)
Credit loss           = GPR x credit_loss_rate                 (bad debt and concessions)
EGI                   = GPR - Vacancy loss - Credit loss + Other income
Management fee        = EGI x management_fee_rate
NOI                   = EGI - OpEx - Turnover - Management fee
Replacement reserves  = replacement_reserve_per_unit_or_bed x (units or beds)
                         x (1 + expense_growth_rate) ^ (N - 1)
```

Reserves are paid **below NOI**: NOI, the going-in cap rate, DSCR and the exit value are before
reserves, while levered and unlevered cash flow (and so every IRR and the multiple) are after them.
Property-tax reassessment on sale is not modeled; put an expected post-sale tax level in OpEx.

**Input ranges.** Rents, price, counts, hold and exit cap must be above zero; vacancy, turnover,
credit loss and management fee are 0-100%; expense growth, closing and selling costs, OpEx, reserves
and every capital stack amount, rate and fee are non-negative; rent growth may be negative (a
declining market) but not -100% or lower. The API enforces this on create and update, and the
engine re-checks it so a row edited directly in the database can't produce numbers.

---

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
sub-class-specific one (`10-Year Treasury + cap-rate spread + assumed stabilized NOI growth`).
See the docstring in `backend/app/engine/ranking.py`. How it ranks:

- **Spread** = unlevered IRR *before closing and selling costs* minus the deal's hurdle. The hurdle
  is a gross market return with no transaction costs, so comparing it with the net IRR would
  penalize short holds (about 130 bps at a 3-year hold, 40 bps at 10).
- **Gates** exclude a deal entirely rather than blending into the score: lowest DSCR over the hold
  below the minimum (not year one, which hides an interest-only start), and an optional debt-yield
  minimum (year-one NOI / total debt).
- **Preference score** (only with weights or questionnaire answers) blends three factors, each
  scaled against **fixed anchors** so a deal's score never depends on which other deals are
  selected: return = spread (-3% to +5%); cash flow = unlevered year-one cash yield, NOI / (price +
  closing costs) (3% to 8%); safety = the mean of lowest DSCR (1.0x to 2.0x) and equity share,
  1 - (all debt + preferred equity) / price (20% to 60%). All-cash counts as maximum coverage.
- The return and cash-flow factors are unlevered. The safety factor is deliberately leverage-aware,
  so a non-zero risk weight lets financing choices move the order.
- Rank order does not depend on the live Treasury (it shifts every deal's hurdle equally); only the
  absolute spreads do.
- A warning is attached when the exit cap is below the going-in cap, because the return then leans
  on cap-rate compression.

---

## Deliverable 3 Advanced Underwriting Extensions

### 1. Granular Unit Mix Modeling

> **Status:** a form-only calculator. The unit mix collapses into the aggregate unit/bed count and
> average rent on the deal; the mix itself is not stored, and the engine has no per-tier code path.

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

> **Status:** form-only helpers that total parking, storage, pet and package income into
> `other_income_annual`. RUBS recovery, parental guarantees, bad debt, summer operations and
> commercial vacancy are **not modeled**. Other income is held flat across the hold.

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

### 3. Capital Stack: Multi-Layer Financing

Deliverable 2 modeled a single fixed-rate amortizing loan. A deal can now carry a **capital
stack** (`deals.capital_stack`): one or more layers, each with a type, an amount and its own
terms. The engine lives in `backend/app/engine/financing.py` and `debt.py`. A deal without a
stack keeps the original single loan, modeled as one implicit senior layer with no I/O and no
maturity, so every Deliverable 2 golden case is unchanged.

**Layer types.** Senior debt: Agency (Fannie Mae, Freddie Mac), HUD/FHA 223(f) and 221(d)(4),
bank / credit union, life company, CMBS, bridge / debt fund, construction, loan assumption,
seller financing. Subordinate: mezzanine, preferred equity, supplemental loan, seller carryback
second. Equity: sponsor / GP, LP syndication, JV partner, 1031 proceeds, DST / TIC, Opportunity
Zone fund, all cash. Each group has an "Other" type with a user-entered name, which reports
show as typed. Every subordinate type except preferred equity is debt.

**Rules.** Exactly one senior debt layer unless the deal is all cash (and an all-cash deal has
no debt layers); at least one equity layer; common equity of at least 5% of total cost (debt and
preferred equity can't cover the whole deal); floating-rate layers need an index rate and a
spread; I/O months can't exceed the term. When a stack is saved, `loan_amount`,
`interest_rate` and `amortization_years` are overwritten from the senior layer, so anything
reading them (LTV, the assumptions report) sees the senior loan.

#### A. Debt layers
Each debt layer is simulated month by month (decision D2) and the layers are summed per year.
- **Rate**: fixed, or floating = index + spread, held flat over the hold (no forward curve).
- **Interest-only**: for months $m \le \text{io\_months}$, payment = balance $\times r$,
  principal = 0, where $r = \text{rate}/12$.
- **Amortization**: after I/O, a level payment solved on the balance at the end of I/O over the
  *remaining* months, $12 \times \text{amortization\_years} - \text{io\_months}$. A blank
  amortization means interest-only for the whole term (typical for mezzanine).
- **Maturity**: a term ending inside the hold is repaid as a **balloon** that month, out of
  that year's levered cash flow (no refinancing is modeled). A term ending at or after the exit
  is repaid from sale proceeds like any other loan balance.
- **Upfront costs**: origination fee (% of the layer), rate cap cost and upfront FHA mortgage
  insurance are paid at closing out of equity.
- **FHA mortgage insurance (HUD 223(f), 221(d)(4), or an assumed HUD loan)**: the annual
  premium is charged monthly on the opening balance ($	ext{balance} 	imes 	ext{MIP}/12$) and
  is part of debt service, so it is in both DSCRs, as HUD underwrites it. The upfront premium is
  a share of the loan amount. The form defaults both to 0.25%, HUD's rate for applications from
  Oct 1, 2025 (Federal Register final notice, Sept 23, 2025); older loans carry higher rates.
- **Prepayment at the sale**: a debt layer still outstanding at the exit and repaid before its
  maturity pays a penalty out of net sale proceeds (levered only; unlevered IRR is unaffected).
  A loan that matures by the exit pays none.
  - *Step-down* (bank loans 5-4-3-2-1, HUD 10% declining 1% a year): the rate for the loan year
    the sale falls in (year = hold period) × the balance; 0% once the schedule runs out.
  - *Yield maintenance* (Agency, life company): with $t$ = Treasury/12 and $B_k$ the scheduled
    opening balance in month $k$ after the exit,
    $\maxig(\sum_k B_k \cdot (	ext{note rate} - 	ext{Treasury})/12 \,/\, (1+t)^k,\;
    1\% 	imes 	ext{balance}ig)$.
  - *Defeasance* (CMBS): the cost of Treasuries that replace every remaining scheduled payment
    and the balloon at maturity, $\sum_k 	ext{payment}_k/(1+t)^k$, less the balance retired;
    never below zero. Defeasance transaction fees aren't modeled.
  - The Treasury rate is an input (the form pre-fills the 10-Year Treasury the app already
    looks up for the hurdle). Open windows before maturity and lockouts aren't modeled.
- **Recourse** is recorded and reported but has no effect on the math.

#### B. Preferred equity
Funds its amount at closing, receives `amount × preferred_return` every year ahead of common
equity (current pay, but only out of cash left after debt service, balloons and reserves; any
shortfall accrues unpaid), and gets its capital back plus the accrued shortfall at exit after debt. It is not debt: it's in
neither DSCR.

#### C. Waterfall and metrics with a stack
```
Debt service (year n)   = sum of every debt layer's interest + principal
                          + FHA mortgage insurance
Levered CF (year n)     = NOI - debt service - preferred return - any balloon that year
Common equity invested  = price + closing costs + fees, rate caps and upfront MIP
                          - all debt - preferred equity
                          (must be >= 5% of that total cost)
Net sale proceeds       = exit value - selling costs - every debt balance at exit
                          - prepayment penalties - preferred equity repaid
Senior DSCR             = NOI / senior loan debt service
Combined DSCR           = NOI / debt service on every debt layer   (year_one_dscr)
```
Cash-on-cash, levered IRR and the equity multiple are measured on common equity. **Unlevered
IRR, and therefore ranking, is unaffected by financing.** Equity layer amounts describe who
supplied the equity; the math always uses the residual common equity above.

---

### 4. Excel Import / Upload Integration

> **Status:** a client-side CSV/TSV importer only. `.xlsx` is not supported, and there is no
> server-side validation engine; the API's normal 422 validation applies when the deal is saved.

To eliminate repetitive manual data entry, analysts can ingest property underwriting details and debt terms directly from standard Excel workbooks (`.xlsx`, `.xls`) or CSV files:

- **Property Details & Unit Mix Workbook**: Automatically maps columns for property identification, sub-asset class selection, 5-tier unit mix matrix, operating expenses, and turnover assumptions.
- **Financing Workbook**: Automatically ingests debt structure, LTV, loan amount, interest rate, I/O period, amortization duration, and loan fees.
- **Validation Engine**: Performs schema validation, verifies leasing-mode consistency, checks for positive unit counts and non-negative rents, and returns cell-level validation errors before database persistence.



---

## Sensitivity and Monte Carlo

Each simulation draws an exit cap rate, a rent growth and a vacancy from normal distributions
centred on the deal's own inputs. Exit cap and rent growth are correlated (default -0.3: weak rent
markets tend to come with wider exit caps; adjustable per request). A draw applies to the **whole
hold**, so this models uncertainty about the assumptions, not year-to-year volatility; interest
rates, expense growth and the floating index are not varied. A run whose IRR doesn't converge counts
as below the hurdle. The response always returns the seed used (one is drawn when none is sent), so
any run can be reproduced. When the hurdle is the risk-adjusted one, runs are compared on the IRR
before closing and selling costs, the basis the hurdle is quoted on.

## Known limitations

- Annual, end-of-period cash flows and IRR (no monthly timing or XIRR).
- No refinancing: a loan maturing inside the hold is repaid from cash flow, and the resulting IRR is
  reported as undefined if the cash flows change sign more than once.
- The static cap-rate spread assumes cap rates move one-for-one with the Treasury; historically the
  beta is lower, so the absolute hurdle (not the rank order) is sensitive to the Treasury input.
- The two ranking endpoints differ: `/rank` uses one flat user hurdle (and the PDF/PPTX exports use
  it too); `/rank/risk-adjusted` uses sub-class hurdles, gates and preferences.
- `lease_expiration_month` is stored and shown but not used by the annual model.
- There is no authentication.
