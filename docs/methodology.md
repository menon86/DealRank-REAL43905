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

**Deliverable 3, not yet built**, replaces the flat hurdle with a risk-adjusted,
sub-class-specific one (`10-Year Treasury + cap-rate spread + assumed stabilized NOI growth`) and
adds a DSCR gate that excludes deals below a configured minimum from ranking entirely, rather than
blending DSCR into the score. See the docstring in `backend/app/engine/ranking.py` — that module
is currently just a placeholder describing this future work; none of it exists yet, and nothing in
Deliverable 2's engine or API assumes it will look exactly like this description.
