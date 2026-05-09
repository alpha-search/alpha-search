"""Yahoo Finance data provider for Alpha Search."""

from __future__ import annotations

import logging
import time
from typing import Optional

import pandas as pd

from alpha_search.core.base import DataProvider
from alpha_search.core.errors import DataProviderError
from alpha_search.data.cache import CacheManager
from alpha_search.data.normalizer import normalize_ohlcv

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds


class YFinanceProvider(DataProvider):
    """Data provider backed by ``yfinance`` (Yahoo Finance).

    Caches fetched data via :class:`CacheManager` and retries on
    transient network errors with exponential backoff.

    Example::

        prov = YFinanceProvider()
        df = prov.get_prices("AAPL", "2020-01-01", "2020-12-31")
    """

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        self._cache = cache or CacheManager()

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "yfinance"

    def get_prices(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV prices from Yahoo Finance.

        Args:
            ticker: Yahoo Finance ticker symbol (e.g. ``'AAPL'``).
            start: Start date ``YYYY-MM-DD``.
            end: End date ``YYYY-MM-DD``.

        Returns:
            Normalized DataFrame with ``['Open','High','Low','Close','Volume']``.

        Raises:
            DataProviderError: If the ticker is invalid or the network fails.
        """
        cache_key = f"yfinance_{ticker}_{start}_{end}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("YFinance cache hit for %s", ticker)
            return cached

        df = self._fetch_with_retry(ticker, start, end)
        normalized = normalize_ohlcv(df, source="yfinance")
        self._cache.set(cache_key, normalized, ttl=86400)
        return normalized

    def validate_ticker(self, ticker: str) -> bool:
        """Check whether *ticker* is recognized by Yahoo Finance.

        A lightweight ``history(period='5d')`` call is used; if it returns
        non-empty data the ticker is considered valid.
        """
        try:
            import yfinance as yf

            tkr = yf.Ticker(ticker)
            hist = tkr.history(period="5d", interval="1d")
            return len(hist) > 0
        except Exception as exc:
            logger.debug("Ticker validation failed for %s: %s", ticker, exc)
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_with_retry(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Fetch with exponential backoff."""
        import yfinance as yf

        last_exc: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                tkr = yf.Ticker(ticker)
                df = tkr.history(start=start, end=end, interval="1d")
                if df is None or df.empty:
                    raise DataProviderError(
                        f"No data returned for {ticker} between {start} and {end}",
                        provider=self.name,
                    )
                logger.info(
                    "YFinance fetched %s: %d rows (attempt %d)",
                    ticker,
                    len(df),
                    attempt,
                )
                return df
            except DataProviderError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "YFinance fetch attempt %d/%d failed for %s: %s",
                    attempt,
                    _MAX_RETRIES,
                    ticker,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF * (2 ** (attempt - 1)))

        raise DataProviderError(
            f"Failed to fetch {ticker} after {_MAX_RETRIES} attempts: {last_exc}",
            provider=self.name,
        )
