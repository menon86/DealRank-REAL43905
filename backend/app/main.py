from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deals import router as deals_router
from app.api.rank import router as rank_router
from app.api.reports import router as reports_router
from app.config import get_settings

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


app.include_router(deals_router)
app.include_router(rank_router)
app.include_router(reports_router)
