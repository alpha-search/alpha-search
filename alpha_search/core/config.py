"""Alpha Search configuration settings loaded from environment variables."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _default_end_date() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def _default_start_date() -> str:
    """Return 2 years ago as YYYY-MM-DD."""
    return (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")


class QuantOsConfig(BaseModel):
    """Alpha Search configuration from environment variables."""

    # Binance API credentials (optional)
    binance_api_key: Optional[str] = Field(
        default=None,
        description="Binance API key",
        alias="BINANCE_API_KEY",
    )
    binance_secret: Optional[str] = Field(
        default=None,
        description="Binance API secret",
        alias="BINANCE_SECRET",
    )

    # Alpaca API credentials (optional)
    alpaca_api_key: Optional[str] = Field(
        default=None,
        description="Alpaca API key",
        alias="ALPACA_API_KEY",
    )
    alpaca_secret: Optional[str] = Field(
        default=None,
        description="Alpaca API secret",
        alias="ALPACA_SECRET",
    )

    # NewsAPI key (optional)
    newsapi_key: Optional[str] = Field(
        default=None,
        description="NewsAPI key for news sentiment",
        alias="NEWSAPI_KEY",
    )

    # Cache settings
    cache_dir: str = Field(
        default=str(Path.home() / ".alpha_search" / "cache"),
        description="Directory for DuckDB cache",
        alias="CACHE_DIR",
    )

    # Date defaults
    default_start_date: str = Field(
        default_factory=_default_start_date,
        description="Default backtest start date",
        alias="DEFAULT_START_DATE",
    )
    default_end_date: str = Field(
        default_factory=_default_end_date,
        description="Default backtest end date",
        alias="DEFAULT_END_DATE",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        alias="LOG_LEVEL",
    )

    # Safety
    paper_trading: bool = Field(
        default=True,
        description="Force paper trading mode",
        alias="QUANTOS_PAPER_TRADING",
    )

    model_config = {"populate_by_name": True, "env_prefix": ""}

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in levels:
            raise ValueError(f"LOG_LEVEL must be one of {levels}, got {v}")
        return v

    @property
    def cache_path(self) -> Path:
        """Return Path to cache directory."""
        path = Path(self.cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


def _env_or_none(env: dict, key: str) -> Optional[str]:
    """Return env value or None if not set/empty."""
    val = env.get(key)
    return val if val else None


def get_config() -> QuantOsConfig:
    """Get the Alpha Search configuration singleton."""
    env = dict(os.environ)
    kwargs: dict = {
        "BINANCE_API_KEY": _env_or_none(env, "BINANCE_API_KEY"),
        "BINANCE_SECRET": _env_or_none(env, "BINANCE_SECRET"),
        "ALPACA_API_KEY": _env_or_none(env, "ALPACA_API_KEY"),
        "ALPACA_SECRET": _env_or_none(env, "ALPACA_SECRET"),
        "NEWSAPI_KEY": _env_or_none(env, "NEWSAPI_KEY"),
        "DEFAULT_START_DATE": env.get("DEFAULT_START_DATE", _default_start_date()),
        "DEFAULT_END_DATE": env.get("DEFAULT_END_DATE", _default_end_date()),
        "LOG_LEVEL": env.get("LOG_LEVEL", "INFO"),
        "QUANTOS_PAPER_TRADING": env.get("QUANTOS_PAPER_TRADING", "true").lower() != "false",
    }
    # Only pass CACHE_DIR if explicitly set, otherwise use Pydantic default
    cache_dir = _env_or_none(env, "CACHE_DIR")
    if cache_dir is not None:
        kwargs["CACHE_DIR"] = cache_dir
    return QuantOsConfig(**kwargs)
