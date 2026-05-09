"""Stock market data, forex, crypto, and fundamentals from Alpha Vantage.

Alpha Vantage provides free stock market data, foreign exchange rates,
cryptocurrency prices, and fundamental data through a REST API.

Setup:
    1. Get a free API key at https://www.alphavantage.co/support/#api-key
    2. Set the ``ALPHA_VANTAGE_API_KEY`` environment variable

Free-tier limits:
    - 25 API calls per day
    - ~5 calls per minute (enforced by rate limiting in this module)

References:
    - https://www.alphavantage.co
    - https://www.alphavantage.co/documentation/
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict

import pandas as pd
import requests

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class AlphaVantageSource(DataSource):
    """Alpha Vantage — stock prices, forex, crypto, and fundamentals.

    Provides:
        - Daily OHLCV for global stocks (TIME_SERIES_DAILY_ADJUSTED)
        - Fundamental data: P/E, market cap, EPS, etc. (OVERVIEW endpoint)
        - Rate-limited API access (5 calls/min free tier)

    Example::

        >>> src = AlphaVantageSource()
        >>> src.is_available()  # checks for ALPHA_VANTAGE_API_KEY
        True
        >>> df = src.fetch_ohlcv("AAPL", "2023-01-01", "2023-12-31")
        >>> df.head()
                       open     high      low   close  adjusted_close     volume  dividend  split_coeff
        date
        2023-01-03  130.28  130.900  124.17  125.07      124....)}
    """

    meta = SourceMeta(
        name="alpha_vantage",
        category="stocks",
        description=(
            "Stock prices, forex, crypto, and fundamentals via Alpha Vantage API. "
            "Daily OHLCV and company overview data for global equities."
        ),
        requires_api_key=True,
        free_tier=True,
        rate_limit="5/min",
        data_types=["ohlcv", "fundamentals"],
        coverage="global",
        homepage="https://www.alphavantage.co",
        docs_url="https://www.alphavantage.co/documentation/",
        install_cmd="pip install requests pandas",
        status="live",
    )

    BASE_URL = "https://www.alphavantage.co/query"
    _last_call: float = 0.0
    MIN_INTERVAL: float = 12.0  # seconds between calls (5/min)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the Alpha Vantage API key is configured.

        Returns:
            ``True`` if the ``ALPHA_VANTAGE_API_KEY`` environment variable is set.
        """
        return bool(os.environ.get("ALPHA_VANTAGE_API_KEY"))

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limited_get(self, params: Dict[str, Any]) -> requests.Response:
        """Execute a rate-limited GET request to the Alpha Vantage API.

        Enforces a minimum ``MIN_INTERVAL`` seconds between consecutive calls.
        Automatically injects the API key into the parameters.

        Parameters:
            params: Query parameters for the API request.

        Returns:
            The :class:`requests.Response` object.

        Raises:
            RuntimeError: If the request fails after retries.
        """
        elapsed = time.time() - self._last_call
        if elapsed < self.MIN_INTERVAL:
            sleep_for = self.MIN_INTERVAL - elapsed
            logger.debug("Alpha Vantage rate limit: sleeping %.2fs", sleep_for)
            time.sleep(sleep_for)

        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ALPHA_VANTAGE_API_KEY environment variable is not set. "
                "Get a free key at https://www.alphavantage.co/support/#api-key"
            )

        params["apikey"] = api_key
        logger.debug("Alpha Vantage API call: function=%s", params.get("function"))

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Alpha Vantage request failed: %s", exc)
            raise RuntimeError(f"Alpha Vantage API request failed: {exc}") from exc
        finally:
            self._last_call = time.time()

        return resp

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch daily OHLCV data from Alpha Vantage.

        Uses the ``TIME_SERIES_DAILY_ADJUSTED`` endpoint.  Returns adjusted
        close prices along with raw OHLCV, dividends, and split coefficients.

        Parameters:
            symbol: Stock ticker symbol, e.g. ``AAPL``, ``MSFT``.
            start: Start date ``YYYY-MM-DD`` (inclusive).
            end: End date ``YYYY-MM-DD`` (inclusive).
            interval: Bar interval — only ``"1d"`` is supported by the free tier.

        Returns:
            DataFrame with columns
            ``[open, high, low, close, adjusted_close, volume, dividend, split_coeff]``
            and a timezone-naive DatetimeIndex named ``date``.

        Raises:
            ValueError: If no data is returned or the symbol is invalid.
            RuntimeError: If the API request fails.

        Example::

            >>> df = src.fetch_ohlcv("IBM", "2023-01-01", "2023-01-31")
            >>> df.columns.tolist()
            ['open', 'high', 'low', 'close', 'adjusted_close', 'volume', 'dividend', 'split_coeff']
        """
        if not self.is_available():
            raise RuntimeError(
                "Alpha Vantage API key not configured. "
                "Set ALPHA_VANTAGE_API_KEY environment variable."
            )

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)

        logger.info(
            "Fetching Alpha Vantage OHLCV: %s (%s to %s)",
            symbol, start, end,
        )

        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
        }

        resp = self._rate_limited_get(params)
        data = resp.json()

        # Check for API error messages
        if "Error Message" in data:
            raise ValueError(
                f"Alpha Vantage API error for symbol '{symbol}': "
                f"{data['Error Message']}"
            )
        if "Information" in data:
            raise RuntimeError(
                f"Alpha Vantage API limit or info: {data['Information']}"
            )

        time_series_key = "Time Series (Daily)"
        if time_series_key not in data:
            raise ValueError(
                f"No time series data returned for {symbol}. "
                f"Response keys: {list(data.keys())}"
            )

        raw_ts = data[time_series_key]
        if not raw_ts:
            raise ValueError(f"Empty time series data for {symbol}.")

        # Convert to DataFrame
        records = []
        for date_str, values in raw_ts.items():
            record = {"date": date_str}
            record.update(values)
            records.append(record)

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()

        # Rename columns from Alpha Vantage naming to standard names
        column_map = {
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. adjusted close": "adjusted_close",
            "6. volume": "volume",
            "7. dividend amount": "dividend",
            "8. split coefficient": "split_coeff",
        }
        df = df.rename(columns=column_map)

        # Convert numeric columns
        numeric_cols = [
            "open", "high", "low", "close", "adjusted_close",
            "volume", "dividend", "split_coeff",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Filter by date range
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]

        if df.empty:
            raise ValueError(
                f"No data for {symbol} between {start} and {end}. "
                "Check the symbol and date range."
            )

        logger.info(
            "Alpha Vantage returned %d rows for %s", len(df), symbol,
        )
        return df

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def fetch_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Fetch fundamental data for *symbol* from Alpha Vantage.

        Uses the ``OVERVIEW`` endpoint to retrieve company metrics including
        P/E ratio, market cap, EPS, dividend yield, and more.

        Parameters:
            symbol: Stock ticker symbol, e.g. ``AAPL``.

        Returns:
            Dictionary of fundamental metrics.  All values are strings from
            the API — callers should cast to numeric types as needed.

        Raises:
            ValueError: If the symbol is not found.
            RuntimeError: If the API request fails.

        Example::

            >>> info = src.fetch_fundamentals("IBM")
            >>> info.get("PERatio")
            '20.5'
        """
        if not self.is_available():
            raise RuntimeError(
                "Alpha Vantage API key not configured. "
                "Set ALPHA_VANTAGE_API_KEY environment variable."
            )

        logger.info("Fetching Alpha Vantage fundamentals: %s", symbol)

        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
        }

        resp = self._rate_limited_get(params)
        data = resp.json()

        if "Error Message" in data:
            raise ValueError(
                f"Alpha Vantage API error for symbol '{symbol}': "
                f"{data['Error Message']}"
            )
        if "Information" in data:
            raise RuntimeError(
                f"Alpha Vantage API limit or info: {data['Information']}"
            )
        if not data:
            raise ValueError(f"No overview data returned for {symbol}.")

        # Add metadata
        data["symbol"] = symbol
        data["source"] = "alpha_vantage"
        data["fetched_at"] = datetime.utcnow().isoformat()

        logger.info(
            "Alpha Vantage fundamentals fetched for %s (%d fields)",
            symbol, len(data),
        )
        return data


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    src = AlphaVantageSource()

    if not src.is_available():
        print("ALPHA_VANTAGE_API_KEY not set. Exiting.")
        sys.exit(1)

    print(f"Source info: {src.info()}")

    # Demo OHLCV
    try:
        df = src.fetch_ohlcv("IBM", "2023-01-01", "2023-01-31")
        print("\n--- OHLCV (IBM) ---")
        print(df.head())
        print(f"\nShape: {df.shape}")
    except Exception as exc:
        print(f"OHLCV fetch failed: {exc}")

    # Demo fundamentals
    try:
        info = src.fetch_fundamentals("IBM")
        print("\n--- Fundamentals (IBM) ---")
        print(f"Name: {info.get('Name')}")
        print(f"P/E Ratio: {info.get('PERatio')}")
        print(f"Market Cap: {info.get('MarketCapitalization')}")
        print(f"EPS: {info.get('EPS')}")
    except Exception as exc:
        print(f"Fundamentals fetch failed: {exc}")
