"""POST /auth/demo: start a throwaway demo account. Public on purpose, so it is
off unless DEMO_ENABLED and a DEMO_TOKEN_SECRET are set, and rate-limited per client.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.chat import client_key
from app.config import Settings, get_settings
from app.db import get_db
from app.demo import start_demo
from app.services.rate_limit import demo_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/demo")
def create_demo_session(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not settings.demo_configured:
        raise HTTPException(status_code=404, detail="The demo is not available.")
    retry_after = demo_limiter.check(client_key(request), settings.DEMO_RATE_LIMIT_PER_MIN)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many demo sessions. Wait a moment and try again.",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )
    token, email = start_demo(db, settings)
    return {"token": token, "email": email}
