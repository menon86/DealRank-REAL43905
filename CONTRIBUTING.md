# Contributing

## Branching

- `main` is protected — no direct pushes, merge via PR only.
- Work on `feature/<name>` branches, e.g. `feature/turnover-expense`, `feature/rank-endpoint`.
- Rebase or merge `main` into your branch before opening a PR if it's gone stale.

## Commit messages

Short, imperative subject line; body explains *why* if it's not obvious.

```
Add turnover expense as a separate OpEx line

Sizes per-bed cost against the share of beds turning that year,
keyed to lease_expiration_month.
```

If a commit touches the calculation engine (`backend/app/engine/`), say so in the PR (see the PR
template's "Methodology impact" section) — that's the layer the grade hinges on.

## Local setup

Prereqs: Python 3.11+ (see `.python-version`), Node 20 (see `.nvmrc`), Docker.

```bash
# 1. Start Postgres
docker-compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # defaults already match docker-compose
alembic upgrade head
python seed.py                # loads one example deal per sub-type
uvicorn app.main:app --reload --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

## Running tests

```bash
cd backend
pytest                        # engine + API tests
ruff check .                  # lint
black --check .               # format check
```

```bash
cd frontend
npm run lint
npm run build
```

Pre-commit hooks run `black`/`ruff` on the backend and `prettier`/`eslint` on the frontend
automatically:

```bash
pip install pre-commit        # once, anywhere
pre-commit install
```

## Schema changes

Every schema change is a committed Alembic migration — never hand-edit the DB with `ALTER TABLE`.

```bash
cd backend
# after changing a model in app/models/
alembic revision --autogenerate -m "describe the change"
alembic upgrade head           # apply it locally, then check the generated file before committing
```

## Opening a PR

Use the PR template. Every PR needs: what changed, which layer(s), how it was tested, and whether
it has methodology impact. CI (`.github/workflows/ci.yml`) runs backend tests/lint and frontend
lint/build on every PR against `main` — it must pass before merge.
