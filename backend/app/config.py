"""Application settings. See docs/build-plan.md 0.1.

The keys in backend/.env.example are the contract — don't rename them
here without updating that file too.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    APP_ENV: str = "development"
    APP_NAME: str = "DealRank"
    LOG_LEVEL: str = "info"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so .env / the environment is read once per process."""
    return Settings()
