"""Application settings. See docs/build-plan.md 0.1.

The keys in backend/.env.example are the contract — don't rename them
here without updating that file too.
"""

from decimal import Decimal
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Render (and Heroku-style hosts) hand out postgres:// or
    postgresql:// URLs, which SQLAlchemy resolves to psycopg2. This
    project installs psycopg 3, so pin the driver explicitly.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    APP_ENV: str = "development"
    APP_NAME: str = "DealRank"
    LOG_LEVEL: str = "info"
    CORS_ORIGINS: str = "http://localhost:5173"

    # Sign-in (app/auth.py). AUTH_REQUIRED=false skips verification and treats
    # every request as one local dev user; never set it on a deployed service.
    AUTH_REQUIRED: bool = True
    GOOGLE_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    # Directory (tenant) id that Microsoft sign-ins must come from, e.g. Purdue's.
    MICROSOFT_TENANT_ID: str = ""
    # Optional comma-separated allowlist (e.g. "purdue.edu,gmail.com"); empty = any.
    ALLOWED_EMAIL_DOMAINS: str = ""

    # "Try the demo" (app/demo.py): a public endpoint that hands out a private
    # throwaway account with copies of the template deals. Off unless both are set.
    DEMO_ENABLED: bool = False
    DEMO_TOKEN_SECRET: SecretStr = SecretStr("")
    DEMO_TOKEN_TTL_MINUTES: int = Field(default=480, ge=5, le=1440)
    DEMO_RATE_LIMIT_PER_MIN: int = Field(default=5, ge=1, le=600)
    # Used when the live FRED lookup fails; the API labels any hurdle built
    # on it as "fallback" so it is never mistaken for a live quote.
    TREASURY_10Y_FALLBACK: Decimal = Decimal("0.046")
    FRED_SERIES_URL: str = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    # Second live source, tried when FRED is down. {month} (YYYYMM) is filled in at call time.
    TREASURY_YIELD_CURVE_URL: str = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        "pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month={month}"
    )

    # Chat assistant (app/api/chat.py). Any OpenAI-compatible endpoint works;
    # switching provider is an env-var change only. The key is read here and
    # nowhere else, and SecretStr keeps it out of reprs and logs. Unset key =
    # chat reports "not configured" and the UI falls back to preset answers.
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = "gemini-3.8-flash"
    LLM_MAX_TOKENS: int = Field(default=1024, ge=64, le=8192)
    CHAT_RATE_LIMIT_PER_MIN: int = Field(default=10, ge=1, le=600)

    @property
    def llm_configured(self) -> bool:
        return bool(self.LLM_API_KEY.get_secret_value().strip() and self.LLM_BASE_URL.strip())

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_psycopg3_driver(cls, url: str) -> str:
        return normalize_database_url(url)

    @property
    def demo_configured(self) -> bool:
        # A short secret is as good as none for HS256.
        return self.DEMO_ENABLED and len(self.DEMO_TOKEN_SECRET.get_secret_value()) >= 32

    @property
    def allowed_email_domains_list(self) -> list[str]:
        return [d.strip().lower() for d in self.ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so .env / the environment is read once per process."""
    return Settings()
