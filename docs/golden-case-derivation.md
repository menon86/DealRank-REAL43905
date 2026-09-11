# Golden-case derivation

Per `docs/build-plan.md` 2.1, this is the hand derivation the golden-case
tests (`backend/tests/engine/test_golden_cases.py`) are checked against.
Numbers here are independently derived from the seed deals in
`backend/seed.py` — that is, computed directly from the documented
formulas, not by reading `app/engine`'s output.

All three seed deals share the same year-1 formulas; only the leasing-mode
branch (units vs. beds) differs at the top.

```
GPR (per-unit)   = unit_count      x monthly_rent_per_unit x 12
GPR (per-bed)    = bed_count       x monthly_rent_per_bed  x 12
Vacancy loss     = GPR x vacancy_rate
EGI              = GPR - Vacancy loss + other_income_annual
Turnover expense = turnover_cost_per_unit_or_bed x (units or beds) x annual_turnover_rate
NOI              = EGI - opex_annual - Turnover expense
```

## Campus View Student Housing (per-bed, 240 beds @ $750/mo)

| Line | Calculation | Value |
| --- | --- | --- |
| GPR | 240 x 750 x 12 | 2,160,000.00 |
| Vacancy loss | 2,160,000.00 x 0.06 | 129,600.00 |
| EGI | 2,160,000.00 - 129,600.00 + 36,000.00 | 2,066,400.00 |
| Turnover | 350 x 240 x 0.85 | 71,400.00 |
| NOI | 2,066,400.00 - 620,000.00 - 71,400.00 | **1,375,000.00** |

Going-in cap rate: 1,375,000.00 / 21,500,000.00 = **6.395%**

## Willowbrook Suburban Garden (per-unit, 180 units @ $1,450/mo)

| Line | Calculation | Value |
| --- | --- | --- |
| GPR | 180 x 1,450 x 12 | 3,132,000.00 |
| Vacancy loss | 3,132,000.00 x 0.05 | 156,600.00 |
| EGI | 3,132,000.00 - 156,600.00 + 54,000.00 | 3,029,400.00 |
| Turnover | 900 x 180 x 0.55 | 89,100.00 |
| NOI | 3,029,400.00 - 980,000.00 - 89,100.00 | **1,960,300.00** |

Going-in cap rate: 1,960,300.00 / 28,800,000.00 = **6.807%**

## Meridian Urban Mid-Rise (per-unit, 95 units @ $2,100/mo)

| Line | Calculation | Value |
| --- | --- | --- |
| GPR | 95 x 2,100 x 12 | 2,394,000.00 |
| Vacancy loss | 2,394,000.00 x 0.07 | 167,580.00 |
| EGI | 2,394,000.00 - 167,580.00 + 42,000.00 | 2,268,420.00 |
| Turnover | 1,500 x 95 x 0.5 | 71,250.00 |
| NOI | 2,268,420.00 - 870,000.00 - 71,250.00 | **1,327,170.00** |

Going-in cap rate: 1,327,170.00 / 32,000,000.00 = **4.147%**

## Debt: closed-form check

Decision D2 amortizes monthly and aggregates to annual (see build plan
section 2). Rather than re-deriving the month-by-month simulation by hand,
the test suite cross-checks `app/engine/debt.py`'s simulated ending
balance against the standard closed-form remaining-balance formula for a
level-payment loan:

```
r = annual_rate / 12
n = amortization_years x 12
M = P x r x (1+r)^n / ((1+r)^n - 1)        (monthly payment)
B_k = P x (1+r)^k - M x ((1+r)^k - 1) / r   (balance after k payments)
```

computed independently in the test (not by calling into `app/engine`),
at `k = 12` (end of year 1) and `k = hold_period_years x 12` (end of the
hold).

| Deal | Loan | Rate | Balance end of year 1 | Balance end of hold |
| --- | --- | --- | --- | --- |
| Campus View | 14,000,000.00 | 6.25% | 13,835,948.60 | 12,604,702.72 (yr 7) |
| Willowbrook | 18,700,000.00 | 6.00% | 18,470,361.81 | 15,649,230.57 (yr 10) |
| Meridian | 20,800,000.00 | 6.15% | 20,551,643.50 | 17,475,857.96 (yr 10) |

## Full amortization sanity check (1.4 accept criterion)

A synthetic deal with `hold_period_years == amortization_years` should
end with a balance of zero (within a cent) — the loan is fully repaid at
the end of the hold by construction of a level-payment amortizing loan.
`test_golden_cases.py::test_full_amortization_ends_at_zero_balance`
checks this directly against `amortization_schedule()` rather than the
closed form above (both should agree, but the accept criterion is stated
in terms of the schedule).

## What downstream figures are *not* hand-verified line-by-line here

Full 7–10 year IRR streams are not reproduced by hand in this document —
that is what `app/engine` exists to automate. What is checked instead:

- Every year's NOI, debt service, and cash flow reconciles internally
  (`levered_cash_flow == noi - debt_service`, etc.) — see
  `test_full_annual_table_reconciles`.
- Levered IRR exceeds unlevered IRR for a positively-levered deal.
  Student housing (6.25% debt vs. 6.40% going-in cap) and suburban garden
  (6.00% vs. 6.81%) both borrow below their cap rate and show this.
  Meridian Urban Mid-Rise borrows at 6.15% against a 4.15% cap rate —
  negative leverage by construction — so its levered IRR is correctly
  *below* its unlevered IRR; this is a property of that seed deal, not an
  engine defect. See `test_irr_direction_is_positively_levered` and
  `test_irr_direction_is_negatively_levered_for_urban_midrise`.
- Exit value and net sale proceeds use forward (year N+1) NOI over the
  exit cap rate, per decision D1 — checked against an independently
  computed forward NOI in `test_exit_value_uses_forward_noi`.
