# DealRank *(working title — not finalized; candidates under discussion: "Basis", "Bearing")*

Risk-adjusted deal comparison and ranking tool for residential multifamily real estate, built for
Purdue REAL 43905. Lets an analyst compare deals across sub-asset classes with different leasing
mechanics (per-unit vs. per-bed) and different risk profiles on one apples-to-apples basis, instead
of the per-unit-only view most underwriting tools (e.g. DealCheck) provide.

**Current phase: Deliverable 2 (MVP), due Week 6.** See [`docs/build-plan.md`](docs/build-plan.md)
for the full task breakdown (added after Deliverable 2 planning is approved).

## Methodology summary

- Two input modes feed one identical downstream engine: per-unit GPR (`units x rent x 12`) and
  per-bed GPR (`beds x rent/bed x 12`, occupancy applied on leased beds). Everything from EGI
  onward is the same code path for both.
- Turnover/make-ready cost is its own visible OpEx line, keyed to a lease-expiration month
  (default August for student housing), sized against the share of units/beds turning that year.
- Core waterfall: `EGI -> NOI -> DSCR -> Levered CF -> Exit Value -> Net Sale Proceeds -> IRR /
  Equity Multiple / Cash-on-Cash`.
- **Levered IRR is displayed** (investor decision-making) but **ranking uses Unlevered IRR only**,
  against a risk-adjusted hurdle — never levered IRR, since leverage choice (LTV) would otherwise
  let a deal win the ranking by taking on more debt rather than by being a better asset.
- Deliverable 2's hurdle is a single user-entered rate. Deliverable 3 replaces it with
  `10-Year Treasury + sub-class cap-rate spread + assumed stabilized NOI growth` (a total-return
  figure, comparable to unlevered IRR) and adds a DSCR gate (deals below ~1.20-1.25x are excluded
  from ranking, not blended into the score).
- Cap rate spreads and market rent data are static, versioned, manually-refreshed lookup tables —
  never live queries, never CoStar or other licensed data.

Full formulas and rationale live in the project spec (see team docs); the calculation engine in
[`backend/app/engine/`](backend/app/engine/) is the authoritative implementation once built.

## Scope

**In scope (Deliverable 2 MVP):** multifamily only — student housing, suburban garden, urban
mid-rise; manual entry of 3-5 deals; NOI/cap rate/DSCR/cash-on-cash/levered & unlevered
IRR/equity multiple; side-by-side comparison dashboard; ranking against a single user-defined
hurdle; PDF/PPTX report export.

**Deferred to Deliverable 3:** Treasury+spread hurdle by sub-class, DSCR gate enforcement,
preference-weighted ranking, rent sanity checks against Zillow/Apartment List, sensitivity
sliders, provenance memo.

**Permanently out of scope:** any asset class beyond the three residential multifamily sub-types
above, automated OM/document parsing, live CoStar/licensed comp data, portfolio-level aggregation,
Monte Carlo sensitivity, development feasibility analysis.

## Stack

- **Frontend:** React (Vite) SPA
- **Backend:** Python + FastAPI
- **Calculation engine:** standalone Python package (`backend/app/engine/`), zero API/UI imports,
  independently unit-tested — `Decimal` for all money math, `numpy-financial` for IRR
- **Database:** PostgreSQL, Alembic migrations from commit one
- **Deployment:** Render (API + frontend)

## Repo layout

```
/backend
  /app
    /engine      calculation engine — zero API/UI imports
    /api         FastAPI routes
    /models      SQLAlchemy models / Pydantic schemas
  /tests
  /migrations    Alembic migrations
/frontend        React app
/docs            build plan, methodology notes, provenance memo (later)
/.github         PR template, issue templates, CI workflow
docker-compose.yml   local Postgres for dev
```

## Local setup

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full instructions (Docker Postgres, backend venv,
Alembic, seed data, frontend dev server).

Quick start:

```bash
docker-compose up -d
cd backend && pip install -e ".[dev]" && alembic upgrade head && python seed.py
uvicorn app.main:app --reload --port 8000   # in one terminal
cd frontend && npm install && npm run dev   # in another
```

## Team workflow

- `main` is protected: no direct pushes, PR + review required, CI must pass.
- Branch naming, commit conventions, and local test/run instructions: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- The calculation engine (`backend/app/engine/`) is the grading-sensitive layer — see
  [`CODEOWNERS`](CODEOWNERS) for the review requirement on that directory.

### Manual GitHub setup steps (not scriptable without `gh` CLI access)

This repo was initialized locally. To finish setup on GitHub:

1. Create the repo (name: `DealRank-REAL43905`, suggested visibility: private) and push:
   ```bash
   git remote add origin <repo-url>
   git push -u origin main
   ```
2. **Enable branch protection on `main`** (Settings -> Branches -> Add rule):
   - Require a pull request before merging (require at least 1 approval)
   - Require status checks to pass before merging — select the `backend` and `frontend` CI jobs
   - Do this only *after* the first push, since a rule can't protect a branch that doesn't exist yet
3. **Add teammates as collaborators** (Settings -> Collaborators): add each teammate's GitHub
   username once you have them.
4. **Set `CODEOWNERS` reviewer**: replace `@methodology-owner` in [`CODEOWNERS`](CODEOWNERS) with
   the actual GitHub username of whoever is tracking methodology correctness, once the team decides.
5. **Tag Deliverable 2 at submission time** (don't rely on whatever `main` happens to be on
   submission day):
   ```bash
   git tag deliverable-2
   git push origin deliverable-2
   ```

## Disclaimer

This project is coursework for Purdue REAL 43905. It is not investment advice and should not be
used to make real capital allocation decisions.
