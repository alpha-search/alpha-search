"""YFinance data source — full live implementation.

Uses the ``yfinance`` library to fetch OHLCV price data, fundamentals,
and corporate actions for 100k+ tickers globally. No API key required.

Installation::

    pip install yfinance pandas

References:
    - https://github.com/ranaroussi/yfinance
    - https://aroussi.com/post/python-yahoo-finance
"""

from __future__ import annotations

import functools
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Tuple[Any, float]] = {}
_DEFAULT_TTL_SECONDS: int = int(os.environ.get("YF_CACHE_TTL", "300"))


def _cache_key(prefix: str, *args: Any) -> str:
    """Generate a deterministic cache key from prefix + args."""
    return f"{prefix}:{':'.join(str(a) for a in args)}"


def _get_cached(key: str, ttl: int = _DEFAULT_TTL_SECONDS) -> Any:
    """Return cached value if it exists and has not expired."""
    entry = _CACHE.get(key)
    if entry is None:
        return None
    value, timestamp = entry
    if time.time() - timestamp > ttl:
        _CACHE.pop(key, None)
        return None
    return value


def _set_cached(key: str, value: Any) -> None:
    """Store a value in the in-memory cache."""
    _CACHE[key] = (value, time.time())


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_MIN_INTERVAL_SECONDS: float = float(os.environ.get("YF_RATE_LIMIT", "0.25"))
_last_call_time: float = 0.0


def _rate_limit() -> None:
    """Enforce a minimum interval between yfinance API calls."""
    global _last_call_time  # noqa: PLW0603
    elapsed = time.time() - _last_call_time
    if elapsed < _MIN_INTERVAL_SECONDS:
        sleep_for = _MIN_INTERVAL_SECONDS - elapsed
        logger.debug("Rate limiting: sleeping %.3fs", sleep_for)
        time.sleep(sleep_for)
    _last_call_time = time.time()


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class YFinanceSource(DataSource):
    """Yahoo Finance data source powered by ``yfinance``.

    Provides:
        - OHLCV price history for any Yahoo-listed ticker
        - Fundamental data (P/E ratio, market cap, EPS, etc.)
        - Corporate actions (splits, dividends)
        - Multi-ticker batch downloads

    No API key is required — data is scraped from Yahoo Finance's
    publicly-available endpoints.

    Example::

        >>> src = YFinanceSource()
        >>> src.is_available()
        True
        >>> df = src.fetch_ohlcv("AAPL", "2023-01-01", "2023-12-31", "1d")
        >>> df.head()
                        open   high    low  close     volume
        date
        2023-01-03  130.28  130.9  124.17  125.07  112117500
    """

    meta = SourceMeta(
        name="yfinance",
        category="stocks",
        description=(
            "Free stock data from Yahoo Finance via yfinance. "
            "OHLCV, fundamentals, and corporate actions for 100k+ global tickers."
        ),
        requires_api_key=False,
        free_tier=True,
        rate_limit="~2000/hr (unofficial)",
        data_types=["ohlcv", "fundamentals", "splits", "dividends"],
        coverage="global",
        homepage="https://finance.yahoo.com",
        docs_url="https://github.com/ranaroussi/yfinance",
        install_cmd="pip install yfinance pandas",
        status="live",
    )

    # -- availability -------------------------------------------------------

    @functools.lru_cache(maxsize=1)
    def is_available(self) -> bool:
        """Check whether ``yfinance`` and ``pandas`` are importable.

        Returns:
            ``True`` when all dependencies are installed.
        """
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "yfinance is not installed. Run: %s",
                self.meta.install_cmd,
            )
            return False

    # -- OHLCV --------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch OHLCV price data from Yahoo Finance.

        Parameters:
            symbol: Ticker symbol, e.g. ``AAPL``, ``MSFT``, ``^GSPC``.
            start: Start date ``YYYY-MM-DD`` (inclusive).
            end: End date ``YYYY-MM-DD`` (inclusive).
            interval: Bar interval — ``1d`` (daily), ``1h`` (hourly),
                ``15m``, ``5m``, ``1m``.  Intraday intervals are limited
                to the last 7-30 days by Yahoo.

        Returns:
            DataFrame with columns ``open, high, low, close, volume``
            and a DatetimeIndex (name ``date``).

        Raises:
            ImportError: If ``yfinance`` is not installed.
            ValueError: If no data is returned for the symbol / date range.
            RuntimeError: On unexpected errors from the yfinance library.

        Example::

            >>> df = src.fetch_ohlcv("AAPL", "2023-01-01", "2023-01-31")
            >>> df.columns.tolist()
            ['open', 'high', 'low', 'close', 'volume']
        """
        if not self.is_available():
            raise ImportError(
                "yfinance is required. Install it with: "
                f"{self.meta.install_cmd}"
            )

        import yfinance as yf

        cache_key = _cache_key("ohlcv", symbol, start, end, interval)
        cached = _get_cached(cache_key)
        if cached is not None:
            logger.debug("YFinance cache hit: %s", cache_key)
            return cached.copy()

        _rate_limit()
        logger.info(
            "Fetching OHLCV from YFinance: %s (%s to %s, %s)",
            symbol, start, end, interval,
        )

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval)
        except Exception as exc:
            logger.error("YFinance request failed for %s: %s", symbol, exc)
            raise RuntimeError(f"YFinance failed for {symbol}: {exc}") from exc

        if df is None or df.empty:
            raise ValueError(
                f"No data returned for {symbol} between {start} and {end}. "
                "Check the ticker symbol and date range."
            )

        # Normalise column names to lower-case snake_case
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Keep only the columns we need
        expected_cols = ["open", "high", "low", "close", "volume"]
        available_cols = [c for c in expected_cols if c in df.columns]
        df = df[available_cols]

        # Ensure index is named "date"
        df.index.name = "date"

        # Cache and return
        _set_cached(cache_key, df.copy())
        logger.info(
            "YFinance returned %d rows for %s", len(df), symbol,
        )
        return df

    # -- Fundamentals -------------------------------------------------------

    def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Fetch fundamental data for *symbol*.

        Retrieves key metrics from Yahoo Finance including:
        P/E ratio, forward P/E, EPS, market cap, dividend yield,
        52-week high/low, beta, sector, and industry.

        Parameters:
            symbol: Ticker symbol, e.g. ``AAPL``.

        Returns:
            Dictionary of fundamental metrics.  Missing fields are ``None``.

        Raises:
            ImportError: If ``yfinance`` is not installed.
            RuntimeError: On unexpected errors.

        Example::

            >>> info = src.fetch_fundamentals("AAPL")
            >>> info.get("pe_ratio")
            28.5
        """
        if not self.is_available():
            raise ImportError(
                "yfinance is required. Install it with: "
                f"{self.meta.install_cmd}"
            )

        import yfinance as yf

        cache_key = _cache_key("fundamentals", symbol)
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached.copy()

        _rate_limit()
        logger.info("Fetching fundamentals from YFinance: %s", symbol)

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
        except Exception as exc:
            logger.error(
                "YFinance fundamentals failed for %s: %s", symbol, exc,
            )
            raise RuntimeError(
                f"YFinance fundamentals failed for {symbol}: {exc}"
            ) from exc

        # Extract key fields — Yahoo's info dict is huge; we cherry-pick
        result: Dict[str, Any] = {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "currency": info.get("currency"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "eps": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "book_value": info.get("bookValue"),
            "price_to_book": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "ex_dividend_date": info.get("exDividendDate"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "revenue": info.get("totalRevenue"),
            "profit_margins": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "employees": info.get("fullTimeEmployees"),
            "website": info.get("website"),
            "source": "yfinance",
            "fetched_at": datetime.utcnow().isoformat(),
        }

        _set_cached(cache_key, result.copy())
        return result

    # -- Corporate actions --------------------------------------------------

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """Fetch dividend history for *symbol*.

        Parameters:
            symbol: Ticker symbol.

        Returns:
            DataFrame with a single ``dividends`` column and DatetimeIndex.
        """
        if not self.is_available():
            raise ImportError(
                "yfinance is required. Install it with: "
                f"{self.meta.install_cmd}"
            )

        import yfinance as yf

        _rate_limit()
        logger.info("Fetching dividends from YFinance: %s", symbol)

        ticker = yf.Ticker(symbol)
        divs = ticker.dividends

        if divs is None or divs.empty:
            return pd.DataFrame(columns=["dividends"])

        df = divs.to_frame(name="dividends")
        df.index.name = "date"
        return df

    def fetch_splits(self, symbol: str) -> pd.DataFrame:
        """Fetch stock split history for *symbol*.

        Parameters:
            symbol: Ticker symbol.

        Returns:
            DataFrame with a single ``splits`` column and DatetimeIndex.
        """
        if not self.is_available():
            raise ImportError(
                "yfinance is required. Install it with: "
                f"{self.meta.install_cmd}"
            )

        import yfinance as yf

        _rate_limit()
        logger.info("Fetching splits from YFinance: %s", symbol)

        ticker = yf.Ticker(symbol)
        splits = ticker.splits

        if splits is None or splits.empty:
            return pd.DataFrame(columns=["splits"])

        df = splits.to_frame(name="splits")
        df.index.name = "date"
        return df

    # -- Batch helper -------------------------------------------------------

    def fetch_multiple(
        self,
        symbols: List[str],
        start: str,
        end: str,
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV for multiple symbols efficiently via ``yfinance.download``.

        Parameters:
            symbols: List of ticker symbols.
            start: Start date ``YYYY-MM-DD``.
            end: End date ``YYYY-MM-DD``.
            interval: Bar interval.

        Returns:
            Dictionary mapping symbol -> DataFrame.  Symbols with errors
            are logged and omitted from the result.
        """
        if not self.is_available():
            raise ImportError(
                "yfinance is required. Install it with: "
                f"{self.meta.install_cmd}"
            )

        import yfinance as yf

        _rate_limit()
        logger.info(
            "Batch downloading %d symbols from YFinance", len(symbols),
        )

        try:
            data = yf.download(
                symbols,
                start=start,
                end=end,
                interval=interval,
                group_by="ticker",
                progress=False,
            )
        except Exception as exc:
            logger.error("YFinance batch download failed: %s", exc)
            raise RuntimeError(f"YFinance batch download failed: {exc}") from exc

        result: Dict[str, pd.DataFrame] = {}
        if len(symbols) == 1:
            sym = symbols[0]
            df = self._normalise_ohlcv(data)
            result[sym] = df
        else:
            for sym in symbols:
                try:
                    df = self._normalise_ohlcv(data[sym])
                    result[sym] = df
                except Exception as exc:
                    logger.warning("Failed to parse data for %s: %s", sym, exc)

        return result

    # -- internal helpers ---------------------------------------------------

    @staticmethod
    def _normalise_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """Normalise raw yfinance DataFrame to standard OHLCV format."""
        df = df.copy()
        df.columns = df.columns.str.lower().str.replace(" ", "_")
        expected = ["open", "high", "low", "close", "volume"]
        available = [c for c in expected if c in df.columns]
        return df[available]
