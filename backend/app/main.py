from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.deals import router as deals_router
from app.api.demo import router as demo_router
from app.api.imports import router as imports_router
from app.api.market_check import router as market_check_router
from app.api.rank import router as rank_router
from app.api.reports import router as reports_router
from app.api.risk_rank import router as risk_rank_router
from app.api.sensitivity import router as sensitivity_router
from app.auth import User, current_user
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # Only the configured origins (CORS_ORIGINS), not every *.onrender.com
    # site. The API uses no cookies, so credentials stay off.
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
def me(user: User = Depends(current_user)) -> dict[str, str]:
    return {"email": user.email, "username": user.username}


# Every router requires a signed-in user; routes that read or write deals
# also take the owner and filter on it (app/api/ownership.py).
_signed_in = [Depends(current_user)]

# The one public route besides /health: it is how a visitor gets a demo account.
app.include_router(demo_router)

# Before deals_router, whose /deals/{deal_id} would otherwise claim /deals/import.
app.include_router(imports_router, dependencies=_signed_in)
app.include_router(deals_router, dependencies=_signed_in)
app.include_router(rank_router, dependencies=_signed_in)
app.include_router(reports_router, dependencies=_signed_in)
app.include_router(risk_rank_router, dependencies=_signed_in)
app.include_router(sensitivity_router, dependencies=_signed_in)
app.include_router(market_check_router, dependencies=_signed_in)
app.include_router(chat_router, dependencies=_signed_in)
