# DealRank *(working title — not finalized; candidates under discussion: "Basis", "Bearing")*

Risk-adjusted deal comparison and ranking tool for residential multifamily real estate, built for
Purdue REAL 43905. Lets an analyst compare deals across sub-asset classes with different leasing
mechanics (per-unit vs. per-bed) and different risk profiles on one apples-to-apples basis, instead
of the per-unit-only view most underwriting tools (e.g. DealCheck) provide.

**Current phase: Deliverable 2 (MVP), due Week 6.** See [`docs/build-plan.md`](docs/build-plan.md)
for the full task breakdown.

**Status: functionally complete end to end.** The calculation engine, the FastAPI CRUD/metrics/
ranking/export endpoints, and the React frontend all exist and are wired together — see
[What's built](#whats-built) below. Not yet done: the Render deploy itself (config is checked in,
see [`render.yaml`](render.yaml)) and this deliverable's git tag.

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

Full formulas and rationale live in the project spec (see team docs) and in
[`docs/methodology.md`](docs/methodology.md); the calculation engine in
[`backend/app/engine/`](backend/app/engine/) is the authoritative implementation.

## What's built

| Layer | Status |
| --- | --- |
| Calculation engine (`backend/app/engine/`) | Done — golden-case fixtures in [`docs/golden-case-derivation.md`](docs/golden-case-derivation.md) |
| API (`backend/app/api/`) | Done — deal CRUD, `GET /deals/{id}/metrics`, `POST /rank`, `GET /reports/{pdf,pptx}` |
| Frontend (`frontend/`) | Done — deal form, deal list, comparison table, ranking view, PDF/PPTX download buttons, wired to the real API |
| Deploy (Render) | Config checked in ([`render.yaml`](render.yaml)); not yet deployed |

## Chat assistant

A read-only, tool-grounded chat drawer ("Ask DealRank") answers questions such as "why is Deal B
ranked below Deal A?" or "which deals failed the DSCR gate?". The model never does math: it can only
call read-only tools (`backend/app/api/chat_tools.py`) that wrap the deterministic engine, and it is
told to quote their output. Tool calls are validated with Pydantic and limited to an allowlist.
It talks to any OpenAI-compatible endpoint (Gemini free tier by default); set `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_MODEL` in `backend/.env` (see `backend/.env.example`, including Groq,
OpenRouter and Ollama examples). With no key, or when the provider is rate-limited or down, the UI
falls back to deterministic preset questions (`GET /chat/suggestions`, `POST /chat/preset`).
`POST /chat` is rate-limited per IP in memory (`CHAT_RATE_LIMIT_PER_MIN`, per process only).

## Scope

**In scope (Deliverable 2 MVP - Completed):** multifamily residential assets — student housing, suburban garden, urban
mid-rise; manual entry of 3-5 deals; NOI/cap rate/DSCR/cash-on-cash/levered & unlevered
IRR/equity multiple; side-by-side comparison dashboard; ranking against user-defined hurdle;
PDF/PPTX report export; deployed on Render.

**Deliverable 3 (built):** per-sub-class risk-adjusted hurdle (10-Year Treasury from FRED + survey
cap-rate spread + stabilized NOI growth), DSCR gate (excluded, not penalized), preference-weighted
ranking (questionnaire or direct weights over return / cash flow / safety), rent sanity check
against Zillow ZORI / Apartment List CSVs, single-variable sensitivity sliders (exit cap rate, rent
growth), and Monte Carlo over exit cap, rent growth and vacancy. Endpoints: `GET /reference/hurdles`,
`POST /rank/risk-adjusted`, `POST /deals/{id}/sensitivity`, `POST /deals/{id}/monte-carlo`,
`GET /deals/{id}/rent-check`, `GET /market-rents/geographies`. Load market rents with
`python ingest_market_rents.py zillow_zori <csv>` (Zillow's rent metrics are CSV downloads, not an
API). **Not yet written:** the data provenance memo documenting the spread source and methodology.

**In scope (Deliverable 3 Roadmap):**
- **Asset-Class-Customized Inputs**: Housing-type specific operational drivers:
  - *Student Housing*: per-bed leasing, academic lease terms, August turn schedule, utility/tech packages, furniture fees.
  - *Suburban Garden*: surface/covered parking, storage garages, pet fees, utility reimbursements (RUBS), amenity fees.
  - *Urban Mid-Rise*: structured/garage parking stalls & monthly rates, retail/commercial NNN leases, high-density storage.
- **Granular Unit Mix Modeling**: Detailed bedroom breakdown across Studio, 1-Bed, 2-Bed, 3-Bed, and 4+ Beds with unit counts, bed counts, and unit-type rents feeding Gross Potential Rent (GPR).
- **Expanded Operational Inputs**: Dedicated revenue and expense drivers including parking spaces, parking ratios, monthly stall rent, storage income, pet deposits, and capital reserve line items.
- **Financing Flexibility & Multiple Loan Types**:
  - Full amortizing vs. Interest-Only (I/O) periods (e.g., 1-5 years I/O followed by amortization).
  - Fixed-rate vs. floating rate (SOFR + spread) structures with optional rate caps.
  - Mezzanine / second-lien financing tranches and balloon payment modeling at loan maturity.
- **Spreadsheet import**: a formatted Excel underwriting template, and import from the template or your own `.xlsx` / `.csv` model, with a review screen that shows where each value came from before the deal form is filled.
- **Risk & Ranking Enhancements**: 10-Year Treasury + sub-class cap rate spread hurdles, hard DSCR gate enforcement (~1.20x-1.25x), preference-weighted ranking, and sensitivity sliders.

**Permanently out of scope:** any asset class beyond residential multifamily sub-types, automated OM/PDF OCR scraping, live CoStar/licensed comp data, portfolio-level aggregation, development ground-up construction feasibility.

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
    /reports     PDF/PPTX export
  /tests
  /migrations    Alembic migrations
/frontend        React app
/docs            build plan, methodology notes, golden-case derivation
/.github         PR template, issue templates, CI workflow
docker-compose.yml   local Postgres for dev
render.yaml          Render deploy config (API, frontend, managed Postgres)
```

## Local setup

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full instructions (Docker Postgres, backend venv,
Alembic, seed data, frontend dev server).

Quick start:

```bash
docker-compose up -d
cd backend && pip install -e ".[dev]" && cp .env.example .env && alembic upgrade head && python seed.py
uvicorn app.main:app --reload --port 8000   # in one terminal
cd frontend && npm install && npm run dev   # in another
```

The frontend defaults to `http://localhost:8000` for the API — copy `frontend/.env.example` to
`frontend/.env.local` and set `VITE_API_BASE_URL` if the backend runs somewhere else.

## Team workflow

- `main` is protected: no direct pushes, PR + review required, CI must pass.
- Branch naming, commit conventions, and local test/run instructions: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- The calculation engine (`backend/app/engine/`) is the grading-sensitive layer — see
  [`CODEOWNERS`](CODEOWNERS) for the review requirement on that directory.

### GitHub setup status

- Repo created and pushed: [github.com/menon86/DealRank-REAL43905](https://github.com/menon86/DealRank-REAL43905)
  (public — GitHub's free plan only supports branch protection on public repos)
- Branch protection on `main` is **enabled**: requires 1 PR approval, requires the `backend` and
  `frontend` CI jobs to pass, blocks force-pushes and deletions.

### Remaining manual steps

1. **Add teammates as collaborators** (Settings -> Collaborators): add each teammate's GitHub
   username once you have them.
2. **Set `CODEOWNERS` reviewer**: replace `@methodology-owner` in [`CODEOWNERS`](CODEOWNERS) with
   the actual GitHub username of whoever is tracking methodology correctness, once the team decides.
3. **Tag Deliverable 2 at submission time** (don't rely on whatever `main` happens to be on
   submission day):
   ```bash
   git tag deliverable-2
   git push origin deliverable-2
   ```
4. **Deploy to Render**: [`render.yaml`](render.yaml) defines the API service and the static
   frontend. Postgres is hosted on [Neon](https://neon.tech) (free tier, no expiry; Render's
   free Postgres is deleted after 30 days): create a Neon project, and paste its connection
   string into the API's `DATABASE_URL` when the Blueprint prompts for it. The first deploy
   runs the migrations and seeds on the empty database. In the Render dashboard, "New +" ->
   "Blueprint", point it at this repo, and Render provisions the two services. After the first deploy,
   set `VITE_API_BASE_URL` (frontend) to the deployed API's URL and `CORS_ORIGINS` (API) to the
   deployed frontend's URL — `render.yaml` wires these automatically via Render's `fromService`
   references, but double-check them in the dashboard if either service is renamed.

## Disclaimer

This project is coursework for Purdue REAL 43905. It is not investment advice and should not be
used to make real capital allocation decisions.
