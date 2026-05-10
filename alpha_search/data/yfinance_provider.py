"""Yahoo Finance data provider for Alpha Search."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from alpha_search.core.base import DataProvider
from alpha_search.core.errors import DataProviderError
from alpha_search.data.cache import CacheManager
from alpha_search.data.normalizer import normalize_ohlcv

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_DELAY_BASE = 1.0  # Base delay in seconds; doubles each retry


# ---------------------------------------------------------------------------
# Disk cache helpers (module-level for broader access)
# ---------------------------------------------------------------------------

def _disk_cache_dir() -> Path:
    """Return the local disk cache directory for yfinance data."""
    cache = Path.home() / ".cache" / "alpha_search" / "yfinance"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _disk_cache_path(ticker: str, start: str, end: str) -> Path:
    """Build a cache file path for a ticker + date range."""
    safe_key = f"{ticker}_{start}_{end}".replace("/", "_").replace("\\", "_")
    return _disk_cache_dir() / f"{safe_key}.parquet"


def _load_from_disk_cache(
    ticker: str, start: str, end: str, ttl_seconds: int = 86400
) -> Optional[pd.DataFrame]:
    """Load a DataFrame from local disk cache if it exists and is fresh.

    Parameters
    ----------
    ticker:
        Yahoo Finance ticker symbol.
    start:
        Start date ``YYYY-MM-DD``.
    end:
        End date ``YYYY-MM-DD``.
    ttl_seconds:
        Cache time-to-live in seconds (default 24 hours).

    Returns
    -------
    pd.DataFrame or None
        Cached data if available and fresh, otherwise ``None``.
    """
    path = _disk_cache_path(ticker, start, end)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        logger.debug("Disk cache expired for %s (age=%.0fs)", ticker, age)
        return None
    try:
        df = pd.read_parquet(path)
        logger.debug("Disk cache hit for %s %s to %s", ticker, start, end)
        return df
    except Exception as exc:
        logger.warning("Failed to read disk cache for %s: %s", ticker, exc)
        return None


def _save_to_disk_cache(ticker: str, start: str, end: str, df: pd.DataFrame) -> None:
    """Save a DataFrame to the local disk cache.

    Parameters
    ----------
    ticker:
        Yahoo Finance ticker symbol.
    start:
        Start date ``YYYY-MM-DD``.
    end:
        End date ``YYYY-MM-DD``.
    df:
        DataFrame to cache.
    """
    try:
        path = _disk_cache_path(ticker, start, end)
        df.to_parquet(path)
        logger.debug("Cached %s %s to %s to disk", ticker, start, end)
    except Exception as exc:
        logger.warning("Failed to write disk cache for %s: %s", ticker, exc)


# ---------------------------------------------------------------------------
# Standalone download with retry
# ---------------------------------------------------------------------------

def _download_with_retry(
    ticker: str,
    start: str,
    end: str,
    max_retries: int = _MAX_RETRIES,
) -> pd.DataFrame:
    """Download OHLCV data from Yahoo Finance with exponential backoff retries.

    Retries on transient errors with delays of 1s, 2s, 4s, 8s, 16s
    between attempts.  If all retries are exhausted, raises a clear
    :class:`DataProviderError`.

    Parameters
    ----------
    ticker:
        Yahoo Finance ticker symbol (e.g. ``'AAPL'``).
    start:
        Start date ``YYYY-MM-DD``.
    end:
        End date ``YYYY-MM-DD``.
    max_retries:
        Maximum number of download attempts (default 5).

    Returns
    -------
    pd.DataFrame
        Raw OHLCV DataFrame as returned by ``yfinance``.

    Raises
    ------
    DataProviderError
        If yfinance is not installed or all retry attempts fail.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise DataProviderError(
            "yfinance is not installed. Install it with: pip install yfinance",
            provider="yfinance",
        )

    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            tkr = yf.Ticker(ticker)
            df = tkr.history(start=start, end=end, interval="1d")
            if df is None or df.empty:
                raise DataProviderError(
                    f"No data returned for {ticker} between {start} and {end}. "
                    f"The ticker may be delisted or the date range invalid.",
                    provider="yfinance",
                )
            logger.info(
                "YFinance fetched %s: %d rows (attempt %d/%d)",
                ticker,
                len(df),
                attempt,
                max_retries,
            )
            return df
        except DataProviderError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = _RETRY_DELAY_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "YFinance fetch attempt %d/%d failed for %s: %s. "
                    "Retrying in %.1fs...",
                    attempt,
                    max_retries,
                    ticker,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "YFinance fetch failed for %s after %d attempts: %s",
                    ticker,
                    max_retries,
                    exc,
                )

    raise DataProviderError(
        f"Failed to fetch {ticker} after {max_retries} attempts. "
        f"Last error: {last_exc}. "
        f"Possible causes: network issues, rate limiting, or invalid ticker. "
        f"Wait a moment and retry, or verify the ticker symbol at "
        f"https://finance.yahoo.com/lookup.",
        provider="yfinance",
    )


# ---------------------------------------------------------------------------
# YFinanceProvider class
# ---------------------------------------------------------------------------

class YFinanceProvider(DataProvider):
    """Data provider backed by ``yfinance`` (Yahoo Finance).

    Caches fetched data both via :class:`CacheManager` (in-memory) and on
    local disk. Retries on transient network errors with exponential
    backoff (1s, 2s, 4s, 8s, 16s).

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
        """Fetch OHLCV prices from Yahoo Finance with caching and retry.

        Checks the in-memory cache first, then the local disk cache
        (24-hour TTL), then downloads from Yahoo Finance with up to 5
        retries using exponential backoff.

        Args:
            ticker: Yahoo Finance ticker symbol (e.g. ``'AAPL'``).
            start: Start date ``YYYY-MM-DD``.
            end: End date ``YYYY-MM-DD``.

        Returns:
            Normalized DataFrame with ``['Open','High','Low','Close','Volume']``.

        Raises:
            DataProviderError: If the ticker is invalid or the network fails
                after all retries.
        """
        cache_key = f"yfinance_{ticker}_{start}_{end}"

        # 1. In-memory cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("YFinance in-memory cache hit for %s", ticker)
            return cached

        # 2. Disk cache (24h TTL)
        disk_cached = _load_from_disk_cache(ticker, start, end)
        if disk_cached is not None:
            logger.info("YFinance disk cache hit for %s", ticker)
            normalized = normalize_ohlcv(disk_cached, source="yfinance")
            self._cache.set(cache_key, normalized, ttl=86400)
            return normalized

        # 3. Download with retry
        df = _download_with_retry(ticker, start, end)

        # 4. Save to disk cache
        _save_to_disk_cache(ticker, start, end, df)

        # 5. Normalize and save to in-memory cache
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
