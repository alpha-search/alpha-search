"""Binance crypto data provider for Alpha Search."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from alpha_search.core.base import DataProvider
from alpha_search.core.config import get_config
from alpha_search.core.errors import DataProviderError
from alpha_search.data.cache import CacheManager
from alpha_search.data.normalizer import normalize_ohlcv

logger = logging.getLogger(__name__)

# Binance rate limit: 1200 requests per minute = 20 per second
_MIN_INTERVAL_SEC = 1.0 / 20.0


class BinanceProvider(DataProvider):
    """Data provider backed by the Binance API (``python-binance``).

    Respects the 1200 req/min rate limit and caches responses.

    Example::

        prov = BinanceProvider()
        df = prov.get_prices("BTCUSDT", "2023-01-01", "2023-12-31")
    """

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        self._cache = cache or CacheManager()
        self._config = get_config()
        self._last_request_time: float = 0.0
        self._client: Optional[object] = None  # lazily loaded

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "binance"

    def get_prices(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV prices from Binance.

        Args:
            symbol: Trading pair, e.g. ``'BTCUSDT'``.
            start: Start date ``YYYY-MM-DD``.
            end: End date ``YYYY-MM-DD``.

        Returns:
            Normalized DataFrame with ``['Open','High','Low','Close','Volume']``.

        Raises:
            DataProviderError: If the API call fails.
        """
        cache_key = f"binance_{symbol}_{start}_{end}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Binance cache hit for %s", symbol)
            return cached

        df = self._fetch(symbol, start, end)
        normalized = normalize_ohlcv(df, source="binance")
        self._cache.set(cache_key, normalized, ttl=43200)  # 12h for crypto
        return normalized

    def validate_ticker(self, symbol: str) -> bool:
        """Check whether *symbol* is a valid Binance trading pair."""
        try:
            client = self._get_client()
            info = client.get_symbol_info(symbol.upper())
            return info is not None
        except Exception as exc:
            logger.debug("Binance validation failed for %s: %s", symbol, exc)
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-load the Binance client."""
        if self._client is not None:
            return self._client
        try:
            from binance.client import Client
        except ImportError as exc:
            raise DataProviderError(
                "python-binance is not installed. Run: pip install python-binance",
                provider=self.name,
            ) from exc

        config = get_config()
        self._client = Client(
            api_key=config.binance_api_key or "",
            api_secret=config.binance_secret or "",
        )
        return self._client

    def _rate_limit(self) -> None:
        """Enforce minimum delay between API requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < _MIN_INTERVAL_SEC:
            time.sleep(_MIN_INTERVAL_SEC - elapsed)
        self._last_request_time = time.time()

    def _fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch klines from Binance and convert to DataFrame."""
        client = self._get_client()

        # Convert dates to milliseconds timestamps
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

        self._rate_limit()
        try:
            klines = client.get_historical_klines(
                symbol.upper(),
                Client.KLINE_INTERVAL_1DAY,
                start_str=start_ms,
                end_str=end_ms,
            )
        except Exception as exc:
            raise DataProviderError(
                f"Binance API error for {symbol}: {exc}", provider=self.name
            ) from exc

        if not klines:
            raise DataProviderError(
                f"No kline data returned for {symbol} between {start} and {end}",
                provider=self.name,
            )

        df = pd.DataFrame(
            klines,
            columns=[
                "Open time", "Open", "High", "Low", "Close", "Volume",
                "Close time", "Quote asset volume", "Number of trades",
                "Taker buy base asset volume", "Taker buy quote asset volume",
                "Ignore",
            ],
        )
        df["Open time"] = pd.to_datetime(df["Open time"], unit="ms")
        df = df.set_index("Open time")
        logger.info("Binance fetched %s: %d rows", symbol, len(df))
        return df
