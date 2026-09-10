from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Deal

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, int]:
    """Throwaway route proving the DB session wiring works end to end
    (docs/build-plan.md 0.2 accept criterion) — queries deals and returns
    a row count against docker-compose Postgres. Superseded once
    GET /deals lands in the API scaffolding phase.
    """
    count = db.execute(select(func.count()).select_from(Deal)).scalar_one()
    return {"deal_count": count}


# Deal CRUD and /rank routes are added in the API scaffolding phase
# (see docs/build-plan.md) — not wired yet.
