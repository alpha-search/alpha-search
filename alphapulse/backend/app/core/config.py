"""Application configuration loaded from environment variables.

All settings are strictly typed and validated at startup via pydantic-settings,
so a misconfigured deployment fails fast instead of erroring at request time.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed runtime configuration for the AlphaPulse API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core service ---------------------------------------------------
    ENVIRONMENT: str = Field(default="development")
    API_V1_PREFIX: str = Field(default="/api/v1")
    PROJECT_NAME: str = Field(default="AlphaPulse")
    DEBUG: bool = Field(default=False)

    # --- Datastores -----------------------------------------------------
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://alphapulse:alphapulse@localhost:5432/alphapulse"
    )
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")

    # --- Security / JWT -------------------------------------------------
    JWT_SECRET: str = Field(default="change-me-in-production-please-use-a-long-random-string")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)

    # --- Stripe ---------------------------------------------------------
    STRIPE_SECRET_KEY: str = Field(default="sk_test_mock")
    STRIPE_WEBHOOK_SECRET: str = Field(default="whsec_mock")
    STRIPE_PRICE_PREMIUM: str = Field(default="price_premium_mock")
    STRIPE_PRICE_PRO: str = Field(default="price_pro_mock")

    # --- External market data (mocked, FMP/Polygon-shaped) --------------
    MARKET_DATA_API_KEY: str = Field(default="demo")
    MARKET_DATA_BASE_URL: str = Field(default="https://financialmodelingprep.com/api/v3")
    USE_MOCK_MARKET_DATA: bool = Field(default=True)

    # --- Caching policy (seconds) --------------------------------------
    CACHE_TTL_QUOTE: int = Field(default=15)
    CACHE_TTL_PROFILE: int = Field(default=86_400)
    CACHE_TTL_FINANCIALS: int = Field(default=43_200)
    CACHE_TTL_CHART: int = Field(default=300)

    # --- CORS -----------------------------------------------------------
    # NoDecode stops pydantic-settings from JSON-parsing the env value, so a
    # plain comma-separated string (CORS_ORIGINS=http://a.com,http://b.com)
    # is accepted and split by the validator below.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default=["http://localhost:3000"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (parsed once per process)."""
    return Settings()


settings = get_settings()
