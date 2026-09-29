# TASK: Render deployment & DB provisioning

## Why
`render.yaml` (repo root) is checked in but the app has never actually been
deployed — see README's "Remaining manual steps" section. This is the
critical path item: the frontend deploy and any live-data testing depend on
this landing first.

---

## Completed Engineering & Configuration Fixes

Before deploying, several critical blockers and automation improvements were implemented:

1. **Driver compatibility for Render PostgreSQL (`psycopg` v3)**:
   - Render's managed PostgreSQL connection strings use the `postgresql://` or `postgres://` scheme. In SQLAlchemy 2.0, omitting the driver causes it to look for `psycopg2` (which is not installed; `psycopg` v3 is the project's dependency).
   - Added automatic scheme normalization (`postgresql+psycopg://`) across:
     - `backend/app/config.py` (`Settings.normalize_database_url` field validator)
     - `backend/migrations/env.py` (Alembic runner)
     - `backend/seed.py` and `backend/seed_reference_data.py`

2. **Automated & Idempotent Production Seeding**:
   - Because Render's Free tier does not provide SSH / web shell access, seeding cannot be performed manually from the Render dashboard.
   - Updated `seed.py` and `seed_reference_data.py` to be idempotent (checks if records already exist before inserting; skips gracefully if populated).
   - Added automated seeding to `dealrank-api`'s `startCommand` in `render.yaml`:
     ```bash
     alembic upgrade head && python seed_reference_data.py && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - On every deploy or restart, migrations run, reference cap rate spreads are seeded, example deals are seeded, and the API server starts cleanly.

3. **CORS Flexibility for Render Subdomains**:
   - Added `allow_origin_regex=r"https://.*\.onrender\.com"` in `backend/app/main.py` alongside `CORS_ORIGINS`.
   - This ensures requests from any Render preview, static site, or assigned custom subdomain are accepted without CORS blocking.

4. **Frontend Node Engine Pinning**:
   - Pinned `NODE_VERSION: "20"` in `render.yaml` under `dealrank-frontend` and placed `.nvmrc` in `frontend/` to satisfy `frontend/package.json`'s `"engines": { "node": ">=20 <21" }` constraint.

5. **`CODEOWNERS` Housekeeping**:
   - Replaced placeholder `@methodology-owner` with `@menon86` in `CODEOWNERS`.

---

## Deployment & Verification Steps

### 1. Provision via Blueprint
1. Open the [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **Blueprint**.
3. Connect and select the repository: `menon86/DealRank-REAL43905` (branch: `feat/render-deploy` or after merging to `main`).
4. Click **Apply**.
5. Render will provision three resources according to `render.yaml`:
   - `dealrank-db` (PostgreSQL 16, free tier)
   - `dealrank-api` (Python 3.11 web service, free tier)
   - `dealrank-frontend` (Static site, free tier)

### 2. Verify Hostnames & Environment Variables
- Check the assigned URLs for `dealrank-api` and `dealrank-frontend`.
- If the default URLs (`https://dealrank-api.onrender.com` and `https://dealrank-frontend.onrender.com`) were assigned, the hardcoded blueprint variables work out-of-the-box.
- If Render assigned a unique suffix (e.g. `dealrank-api-xxxx.onrender.com`):
  - In `dealrank-frontend` -> **Environment**: update `VITE_API_BASE_URL` to the actual API URL and trigger a manual redeploy (since Vite bakes `VITE_` variables at build time).
  - In `dealrank-api` -> **Environment**: verify `CORS_ORIGINS` (or rely on the built-in `allow_origin_regex` wildcard for `*.onrender.com`).

### 3. Verify Deploy Logs & Seeding
In the `dealrank-api` deploy logs, verify:
1. `alembic upgrade head` applies all migrations (0001 through head).
2. `seed_reference_data.py` outputs: `Seeded 3 cap rate spreads.`
3. `seed.py` outputs: `Seeded 3 deals.`
4. `uvicorn app.main:app` binds to port and begins serving traffic.

### 4. Live Smoke Testing
1. Navigate to the live frontend URL: `https://dealrank-frontend.onrender.com` (or assigned hostname).
2. **Deals Tab**:
   - Verify the 3 seeded deals appear: *Campus View Student Housing*, *Willowbrook Suburban Garden*, and *Meridian Urban Mid-Rise*.
   - Create a test deal (e.g. 50 units, $1,500/mo, 5% vacancy) and save it.
3. **Compare Tab**:
   - Select 3 deals and view side-by-side metrics (NOI, Cap Rate, DSCR, Cash-on-Cash, Unlevered IRR, Levered IRR, Equity Multiple).
4. **Rank Tab**:
   - Enter a hurdle rate (e.g., `0.08` for 8%).
   - Confirm deals are ranked in descending order by spread over hurdle (`unlevered_irr - hurdle_rate`).
5. **Export Buttons**:
   - Click **Download PDF** → Confirm `dealrank-comparison.pdf` downloads and opens properly.
   - Click **Download PPTX** → Confirm `dealrank-comparison.pptx` downloads and opens properly.

### 5. Submission Housekeeping
Once all checks pass:
```bash
git tag deliverable-2
git push origin deliverable-2
```
Add teammates as GitHub collaborators under **Settings → Collaborators**.

---

## Acceptance Status
- [x] Pre-deploy database URL driver bug identified and resolved (`postgresql+psycopg://`).
- [x] Automated, idempotent data seeding wired into `startCommand` for Render free tier.
- [x] Node version and build environment configured for static frontend.
- [x] `CODEOWNERS` updated with methodology reviewer `@menon86`.
- [ ] Blueprint applied on Render dashboard.
- [ ] Live URL smoke tests verified.
- [ ] `deliverable-2` tag pushed to `origin`.

---

# TASK: UI/UX — Deal form & deal list (Completed in PR #7)

## Why
The core MVP flow (build, form fields, API wiring) already works end to end
— this is polish, not new functionality. Grading likely weighs on the app
being pleasant and clear to actually use, not just functionally correct.

## Where
- `frontend/src/components/DealForm.tsx`
- `frontend/src/components/DealList.tsx`
- Shared CSS: `frontend/src/styles.css`

## What was completed
1. **Leasing-mode toggle clarity.** Visual distinction between active modes with conditional field display.
2. **Validation & error states.** In-line field-level validation and clear error states.
3. **Empty states.** Helpful call-to-action prompts when no deals are present.
4. **Responsive layout.** Form and list responsive styling across various viewport widths.
5. **Field grouping/labels.** Grouped inputs into logical sections with clear typography.
