# Build plan — Deliverable 2 (MVP), due Week 6

Scope: everything between the current scaffold (schema, CI, empty engine) and a submittable
Deliverable 2. Deliverable 3 items appear only where a D2 decision would otherwise paint us into a
corner.

**Definition of done.** An analyst can enter 3–5 deals by hand across the three sub-asset classes, in
either leasing mode, see every deal's NOI / cap rate / DSCR / cash-on-cash / levered and unlevered
IRR / equity multiple side by side, rank them against one hurdle rate they type in, and export the
comparison as a PDF and a PPTX. The engine is unit-tested against hand-computed figures. The app is
deployed on Render. `main` is tagged `deliverable-2`.

---

## 1. Current state

| Built | Not built |
| --- | --- |
| Monorepo layout, `.env.example`, docker-compose Postgres | `app/config.py`, `app/db.py`, CORS |
| `deals` / `cap_rate_spreads` / `market_rents` + migration 0001 | Every engine module |
| `seed.py`, one deal per sub-type | Every route except `/health` |
| CI: backend lint/migrate/test, frontend lint/build | All frontend beyond a placeholder heading |
| Branch protection, PR and issue templates, CODEOWNERS | PDF and PPTX export, Render deploy |

Two pieces of scaffolding are deliberately inert and stay that way through D2:
`app/engine/ranking.py` (a docstring reserving the module for the D3 hurdle) and the
`cap_rate_spreads` / `market_rents` tables (migrated but unread). Do not consume them this
deliverable.

---

## 2. Decisions made here

These are settled so nobody relitigates them mid-phase. Each is reversible, but reversing one after
its phase lands means re-deriving the test fixtures, so raise objections now.

| # | Decision | Why | Cost to reverse later |
| --- | --- | --- | --- |
| D1 | **Exit value uses forward NOI** — year *N+1* NOI ÷ exit cap rate | Standard institutional convention; matches how the exit cap is quoted | High: every IRR and fixture changes |
| D2 | **Debt amortizes monthly, aggregated to annual** | Matches how the loan actually pays; annual-only compounding overstates principal paydown | Medium: `debt.py` and fixtures |
| D3 | **Turnover is charged annually**, not shifted by `lease_expiration_month` | D2's model is annual; the month field is carried for display and D3 monthly modeling | Low: additive in D3 |
| D4 | **Server-side export**, `reportlab` for PDF and `python-pptx` for PPTX | One layout code path; PPTX forces a Python library anyway. `reportlab` is pure Python, so Render needs no system packages (WeasyPrint would need cairo/pango) | Medium |
| D5 | **Hand-written CSS**, no component library | Three weeks, four views, and the graded artifact is the export, not the UI | Low |
| D6 | **Tests run against real Postgres**, a separate `dealrank_test` database | Models use Postgres `UUID` and native `ENUM`; SQLite cannot run this schema | Low |
| D7 | **Percentages are whole numbers in the UI, decimal fractions everywhere behind it**, converted at exactly one boundary in the API client | The likeliest source of a wrong number on submission day | Low |
| D8 | **No auth in D2** | Single-analyst tool; the Render URL is unlisted | Low |

---

## 3. Schedule

Three working weeks. Fill in real dates once the team confirms the Week 6 deadline.

| Week | Engine lane | API lane | Frontend lane |
| --- | --- | --- | --- |
| **3** | Phase 0, then 1.1–1.3 with tests | Waits on 1.1, then 3.1 | 5.1, 5.2 against mocked client |
| **4** | 1.4–1.6, Phase 2 complete | 3.2–3.5, Phase 4 | 5.3, 5.4 |
| **5** | Review, fixture reconciliation | Phase 6 export | 5.5, wire to real API |
| **6** | Phase 7 — everyone, first half of the week | | |

**Critical path:** Phase 0 → 1.1 → 1.5 → 1.6 → 3.3 → 3.4 → 6.2 → 7.3. Anything slipping on that line
slips submission; anything else has slack.

**Cut list, in the order things get cut if Week 5 is tight:** 5.5 polish, then PPTX theming, then
`PATCH /deals`, then the deployed Render instance in favor of a local demo. Do not cut Phase 2.

Each numbered task below is one PR. Owner column is left blank for the team to claim.

---

## Phase 0 — Application plumbing

Blocks everything. One person, half a day.

**0.1 Settings module.** `app/config.py` — a `pydantic-settings` `Settings` class reading
`DATABASE_URL`, `APP_ENV`, `APP_NAME`, `LOG_LEVEL`, `CORS_ORIGINS` (comma-separated, parsed to a
list), with a cached accessor so it is read once. The `.env.example` keys are the contract; do not
rename them.
*Accepts when:* importing settings with no `.env` present raises an error naming the missing key.

**0.2 DB session and CORS.** `app/db.py` — engine, `sessionmaker`, and a `get_db` dependency that
yields a session and closes it. `app/main.py` gains CORS middleware from the settings origin list.
*Accepts when:* a throwaway route queries `deals` and returns a row count against docker-compose
Postgres.

**0.3 Test database fixtures.** `tests/conftest.py` — a session-scoped fixture that creates
`dealrank_test`, runs `alembic upgrade head` against it, and a function-scoped fixture that wraps each
test in a rolled-back transaction. CI gets a second `POSTGRES_DB` or creates the test database in a
step; update `.github/workflows/ci.yml` in this PR.
*Accepts when:* two tests writing the same deal name both pass, in either order.

**0.4 Retire the placeholder.** Delete `tests/test_placeholder.py` in whichever PR first adds a real
test file. Its own docstring says to.

---

## Phase 1 — Calculation engine

The grading-sensitive layer. `backend/app/engine/` imports nothing from `app.api`, `app.models`, or
FastAPI — plain dataclasses in, plain dataclasses out, exercisable from a REPL with no database. All
money is `Decimal`; rates are `Decimal` fractions (6% is `Decimal("0.06")`). The only float
conversion in the codebase happens at the IRR boundary, where `numpy-financial` requires it.

| Module | Holds |
| --- | --- |
| `types.py` | `DealInputs`, `AnnualCashFlow`, `DealMetrics` |
| `revenue.py` | GPR by leasing mode, vacancy, other income → EGI |
| `expenses.py` | OpEx growth, turnover line → total OpEx |
| `debt.py` | Amortization schedule, annual debt service, ending balance |
| `waterfall.py` | Year-by-year projection, exit, net sale proceeds |
| `metrics.py` | NOI, cap rate, DSCR, CoC, IRR both ways, equity multiple |
| `ranking.py` | **untouched this deliverable** |

**1.1 Input types.** `types.py`. The ORM-row-to-`DealInputs` converter lives in `app/api/`, not the
engine, so the engine keeps zero model imports. Unblocks the API lane.
*Accepts when:* `DealInputs` rejects a per-bed deal carrying unit fields, and vice versa, mirroring
the nullable column pairs in `app/models/deal.py`.

**1.2 GPR and EGI.** Per-unit GPR is `units × monthly_rent × 12`. Per-bed GPR is
`beds × monthly_rent_per_bed × 12`, vacancy applied against leased beds. Both converge on
`EGI = GPR − vacancy loss + other income`. This convergence is the project's whole thesis — write it
as one function taking a resolved GPR, not two parallel EGI paths.
*Accepts when:* a per-unit and a per-bed deal with identical GPR produce identical EGI, asserted as
`Decimal` equality.

**1.3 OpEx and the turnover line.** OpEx grows at `expense_growth_rate` annually. Turnover is a
separate, individually visible line: `turnover_cost_per_unit_or_bed × (units or beds) ×
annual_turnover_rate`, grown at the same rate, reported separately rather than folded into total
OpEx. Per D3, `lease_expiration_month` does not shift timing in the annual model — say so in the
module docstring so nobody later reads the field as if it were doing work.
*Accepts when:* student housing at 85% turnover shows a materially larger turnover line than suburban
garden at 55%, and the two appear as distinct fields in the output.

**1.4 Debt.** Fixed-rate amortization from `loan_amount`, `interest_rate`, `amortization_years`,
monthly per D2. Annual debt service, annual interest/principal split, balance at the end of
`hold_period_years`. Handle `loan_amount = 0` without dividing by zero.
*Accepts when:* the final balance at full amortization is zero within a cent, and the year-*n*
balance matches a spreadsheet `CUMPRINC` check.

**1.5 Waterfall.** Year 1 through `hold_period_years`: EGI → NOI → debt service → levered cash flow.
Exit value per D1. Net sale proceeds are exit value less `selling_costs_rate` less the outstanding
balance.
*Accepts when:* the full annual table for the seeded student housing deal matches the hand-built
spreadsheet to the cent.

**1.6 Metrics.** Going-in cap rate on year-1 NOI over purchase price. DSCR per year plus a year-1
headline. Cash-on-cash on equity (`purchase_price + closing_costs − loan_amount`). Equity multiple.
Unlevered IRR on the unlevered stream (outlay = price + closing costs, no debt anywhere). Levered IRR
on the levered stream.
*Accepts when:* the two IRRs differ in the expected direction for a positively-levered seeded deal,
and a non-converging IRR returns `None` rather than raising.

**Guardrails.** No ranking, hurdle, or sub-class-conditional branch enters these modules. The D3
hurdle keys off sub-asset class, and if that concept leaks into the waterfall now, the engine stops
being independently usable. Nothing here touches the database.

---

## Phase 2 — Engine tests

Written alongside Phase 1 and reviewed as its specification. Coverage target is every branch in
`app/engine/`, not a percentage.

**2.1 Golden-case fixtures.** One hand-computed case per sub-asset class, derived from `seed.py`, as
a checked-in fixture carrying every intermediate line (GPR, vacancy loss, EGI, OpEx, turnover, NOI,
debt service, levered CF, exit value, net proceeds) and every headline metric. A human does the
arithmetic in a spreadsheet first; the test asserts the code agrees. Commit the spreadsheet to
`docs/` so a grader can follow the derivation. **This task starts in Week 3 and is not optional** —
it turns every later code review into an arithmetic check anyone on the team can perform.

**2.2 Leasing-mode equivalence.** The per-unit and per-bed inputs that should agree do agree, at EGI
and at every metric downstream.

**2.3 Edge cases.** Zero vacancy; 100% turnover; all-cash (DSCR undefined rather than a division
error); a negative-cash-flow deal; a one-year hold; a non-converging IRR.

**2.4 Decimal discipline.** Assert no float appears in any returned money field, so a stray `/ 12`
cannot silently reintroduce binary rounding.

---

## Phase 3 — API

**3.1 Schemas and converter.** `app/api/schemas.py` — `DealCreate`, `DealUpdate`, `DealOut`,
`MetricsOut`, `RankRequest`, `RankedDealOut`. `app/api/converters.py` — ORM row to `DealInputs`.
Cross-field validation that leasing mode matches the populated branch, rejected with a 422 naming the
offending field.

**3.2 Deal CRUD.** `app/api/deals.py` — `POST /deals`, `GET /deals`, `GET /deals/{id}`,
`PATCH /deals/{id}`, `DELETE /deals/{id}`.

**3.3 Metrics.** `GET /deals/{id}/metrics` — load the row, convert, run the engine, return
`MetricsOut`. Computed on demand every time; nothing derived is written back to `deals`, as the model
docstring already forbids.

**3.4 Rank.** `POST /rank` taking `{deal_ids, hurdle_rate}`, returning deals sorted by
`unlevered_irr − hurdle_rate` descending, each with its spread and rank. Levered IRR is returned for
display and never sorted on. D2's hurdle is one flat user-entered rate across all sub-classes; per
the `ranking.py` docstring this stays inline in the handler, because it has no sub-class behavior yet
to justify the module.
*Accepts when:* the response carries an explicit basis note, so an exported report cannot be read as
ranking on levered returns.

**3.5 Router wiring.** Register routers in `app/main.py`, keep `/health`, confirm `/docs` lists every
route in section 5.

---

## Phase 4 — API tests

`httpx` against the app on the Phase 0.3 test database. Round-trip create-then-read for both leasing
modes; 422 on a mode/branch mismatch; 404s on unknown IDs; a metrics response matching the Phase 2
golden fixture through the API rather than only in-process; a rank response whose order is verified
against hand-computed IRRs, including one deal below the hurdle to confirm negative spreads still
rank rather than disappear — the DSCR gate that excludes deals is D3, not D2.

---

## Phase 5 — Frontend

React + Vite + TypeScript, already scaffolded. Hand-written CSS per D5. Four views, no router needed
if a tab strip suffices.

**5.1 Shell and client.** Layout, a typed `api.ts` hand-mirrored against the section 5 contract, the
D7 percentage conversion in exactly one place, and a shared table/field CSS module.

**5.2 Deal form.** Every field in `app/models/deal.py`, with the leasing-mode toggle swapping the GPR
branch between units/rent-per-unit and beds/rent-per-bed. Defaults drawn from the seed deals.
Client-side validation mirroring the 422 rules.

**5.3 Deal list.** Saved deals, select 3–5 for comparison, edit and delete.

**5.4 Comparison table.** Deals as columns, line items as rows: the waterfall down to NOI, then the
headline metrics. Turnover is its own visible row. Both IRRs shown, unlevered marked as the ranking
basis.

**5.5 Ranking view.** Hurdle input, ranked order, spread over hurdle per deal, and a visible statement
that ranking uses unlevered IRR against a user-entered hurdle, naming the D3 successor so a grader
sees the direction of travel.

---

## Phase 6 — Export

**6.1 Dependencies.** Add `reportlab` and `python-pptx` to `pyproject.toml` per D4, plus a
`app/reports/` package.

**6.2 PDF.** `GET /reports/pdf?deal_ids=...&hurdle_rate=...` returning the comparison table, the
ranking, and an assumptions block listing every input per deal, so the file is self-contained.

**6.3 PPTX.** The same content as slides: title, comparison table, ranking, assumptions. This is the
artifact that gets presented, so it carries the methodology note about unlevered-IRR ranking.

**6.4 Download buttons.** Triggers on the comparison and ranking views.

---

## Phase 7 — Submission

**7.1 README refresh.** Replace the "not yet built" language, add screenshots, document the export
endpoints.

**7.2 Methodology note in `docs/`.** Formulas as implemented, with decisions D1–D3 stated explicitly.
The full provenance memo is D3-the-deliverable; this is the short version that keeps a grader from
having to read the engine.

**7.3 Render deploy.** `render.yaml` for API and static frontend, a managed Postgres, migrations run
on deploy, and `CORS_ORIGINS` pointed at the deployed frontend. Do this in Week 5 if the lane frees
up, not on submission day.

**7.4 Housekeeping and tag.** Replace `@methodology-owner` in `CODEOWNERS` with a real username, add
teammates as collaborators, then:

```bash
git tag deliverable-2 && git push origin deliverable-2
```

---

## 5. Frozen API contract

Frozen before Phases 3 and 5 start so they proceed in parallel. Money as decimal strings, rates as
decimal fractions, IDs as UUIDs.

| Method | Path | Body / query | Returns |
| --- | --- | --- | --- |
| GET | `/health` | — | `{status}` |
| POST | `/deals` | `DealCreate` | `DealOut` |
| GET | `/deals` | — | `DealOut[]` |
| GET | `/deals/{id}` | — | `DealOut` |
| PATCH | `/deals/{id}` | `DealUpdate` | `DealOut` |
| DELETE | `/deals/{id}` | — | 204 |
| GET | `/deals/{id}/metrics` | — | `MetricsOut` |
| POST | `/rank` | `{deal_ids, hurdle_rate}` | `RankedDealOut[]` |
| GET | `/reports/pdf` | `deal_ids`, `hurdle_rate` | `application/pdf` |
| GET | `/reports/pptx` | `deal_ids`, `hurdle_rate` | `…presentationml.presentation` |

`MetricsOut` carries the annual cash flow table plus `year_one_noi`, `going_in_cap_rate`,
`year_one_dscr`, `cash_on_cash`, `unlevered_irr`, `levered_irr`, `equity_multiple`, `exit_value`,
`net_sale_proceeds`, and turnover expense per year as its own field.

---

## 6. Risks

**The engine is the grade and it sits on one person's critical path.** Mitigated by 2.1: fixtures
computed by hand before the code exists.

**Percentage unit confusion between UI and API.** Mitigated by D7 and a test at that boundary.

**Export lands last and is the artifact a grader actually opens.** Mitigated by the cut list — Phase
5 polish goes before any part of Phase 6.

**Exit convention moves the headline IRR.** D1 is a methodology choice, not an implementation detail.
Disagree now; changing it after Phase 2 means re-deriving every fixture.

**Scope creep from Deliverable 3.** Treasury lookups, DSCR gates, sensitivity sliders, and rent sanity
checks are all out. `ranking.py` stays a docstring.
