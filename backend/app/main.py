from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deals import router as deals_router
from app.api.market_check import router as market_check_router
from app.api.rank import router as rank_router
from app.api.reports import router as reports_router
from app.api.risk_rank import router as risk_rank_router
from app.api.sensitivity import router as sensitivity_router
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
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(deals_router)
app.include_router(rank_router)
app.include_router(reports_router)
app.include_router(risk_rank_router)
app.include_router(sensitivity_router)
app.include_router(market_check_router)
