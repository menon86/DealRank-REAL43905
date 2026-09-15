# TASK: Render deployment & DB provisioning

## Why
`render.yaml` (repo root) is checked in but the app has never actually been
deployed — see README's "Remaining manual steps" section. This is the
critical path item: the frontend deploy and any live-data testing depend on
this landing first.

## What to do

1. **Provision via Blueprint.** In the Render dashboard: New + → Blueprint,
   point it at this repo. This should create three resources from
   `render.yaml`: the `dealrank-api` web service, the `dealrank-frontend`
   static site, and the `dealrank-db` managed Postgres instance.

2. **Verify env var wiring.** `render.yaml`'s comments flag that
   `CORS_ORIGINS` (on the API) and `VITE_API_BASE_URL` (on the frontend) are
   hand-written assuming the default `onrender.com` hostnames, since
   Render's blueprint spec doesn't support string concatenation. After the
   first deploy, double check both against the actual assigned hostnames in
   the dashboard — if either service got renamed or a custom domain was
   attached, fix these two values by hand.

3. **Run migrations against prod.** The API's `startCommand` already runs
   `alembic upgrade head` before `uvicorn` starts on every deploy — confirm
   this actually completes cleanly in the deploy logs, don't just assume it
   did.

4. **Seed data.** Run `backend/seed.py` (deal data) against the prod DB.
   If the cap-rate-data branch has landed by the time you deploy, also run
   its reference-data seed script — check with that owner before you
   deploy so you're not seeding twice or missing it.

5. **Smoke test the live URLs.** Hit the deployed frontend, walk through
   Deals → Compare → Rank, and click both Download PDF and Download PPTX
   against the real deployed API (not localhost) — these haven't been
   verified against a live deploy at all yet.

6. **Submission housekeeping**, once everything above is green:
   ```
   git tag deliverable-2
   git push origin deliverable-2
   ```
   Also: add teammates as GitHub collaborators (Settings → Collaborators),
   and replace the placeholder `@methodology-owner` in `CODEOWNERS` with
   whoever's actually tracking methodology correctness.

## Acceptance
- Both `dealrank-api` and `dealrank-frontend` are live on `onrender.com` and
  reachable without a VPN/localhost.
- A deal entered on the live frontend produces correct metrics and a
  ranking, and both PDF and PPTX download successfully.
- `deliverable-2` tag exists on `origin`.
