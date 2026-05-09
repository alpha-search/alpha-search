"""Real-time and historical market data for US stocks, options, forex, and crypto from Polygon.io.

Polygon.io provides market data APIs for equities, options, forex, and
cryptocurrencies with both free and paid tiers.

Setup:
    1. Sign up for a free API key at https://polygon.io
    2. Set the ``POLYGON_API_KEY`` environment variable

Free-tier limits:
    - 5 API calls per minute
    - 2 years of historical data
    - Delayed data (15 min for stocks)

References:
    - https://polygon.io
    - https://polygon.io/docs/
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import requests

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class PolygonSource(DataSource):
    """Polygon.io — real-time and historical market data API.

    Provides:
        - OHLCV price data for US stocks, forex, and crypto
        - Aggregates (bars) at various intervals
        - Rate-limited API access (5 calls/min free tier)

    Example::

        >>> src = PolygonSource()
        >>> src.is_available()  # checks for POLYGON_API_KEY
        True
        >>> df = src.fetch_ohlcv("AAPL", "2023-01-01", "2023-01-31")
        >>> df.head()
                        open     high      low   close    volume  vwap  transactions
        date
        2023-01-03  130.28   130.90   124.17  125.07  112117500  ...
    """

    meta = SourceMeta(
        name="polygon",
        category="stocks",
        description=(
            "Polygon.io — real-time and historical market data for US stocks, "
            "options, forex, and cryptocurrencies."
        ),
        requires_api_key=True,
        free_tier=True,
        rate_limit="5 API calls/min (free)",
        data_types=["ohlcv", "options", "forex", "crypto"],
        coverage="us",
        homepage="https://polygon.io",
        docs_url="https://polygon.io/docs/",
        install_cmd="pip install requests pandas",
        status="live",
    )

    BASE_URL = "https://api.polygon.io"
    _last_call: float = 0.0
    MIN_INTERVAL: float = 12.1  # seconds between calls (5/min free tier)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the Polygon.io API key is configured.

        Returns:
            ``True`` if the ``POLYGON_API_KEY`` environment variable is set.
        """
        return bool(os.environ.get("POLYGON_API_KEY"))

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limited_get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Execute a rate-limited GET request to the Polygon.io API.

        Enforces a minimum ``MIN_INTERVAL`` seconds between consecutive calls.
        Automatically injects the API key into the parameters.

        Parameters:
            endpoint: API endpoint path (without base URL).
            params: Optional query parameters.

        Returns:
            The :class:`requests.Response` object.

        Raises:
            RuntimeError: If the request fails.
        """
        elapsed = time.time() - self._last_call
        if elapsed < self.MIN_INTERVAL:
            sleep_for = self.MIN_INTERVAL - elapsed
            logger.debug("Polygon.io rate limit: sleeping %.2fs", sleep_for)
            time.sleep(sleep_for)

        api_key = os.environ.get("POLYGON_API_KEY")
        if not api_key:
            raise RuntimeError(
                "POLYGON_API_KEY environment variable is not set. "
                "Get a free key at https://polygon.io"
            )

        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["apiKey"] = api_key

        logger.debug("Polygon.io API call: %s", endpoint)

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Polygon.io request failed: %s", exc)
            raise RuntimeError(f"Polygon.io API request failed: {exc}") from exc
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
        """Fetch OHLCV aggregates from Polygon.io.

        Uses the ``/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from}/{to}``
        endpoint to retrieve aggregated bars.

        Parameters:
            symbol: Ticker symbol, e.g. ``AAPL``, ``X:BTCUSD``.
                Prefix ``X:`` for crypto, ``C:`` for forex.
            start: Start date ``YYYY-MM-DD`` (inclusive).
            end: End date ``YYYY-MM-DD`` (inclusive).
            interval: Bar interval — ``"1d"`` (daily, default),
                ``"1h"`` (hourly), ``"15m"`` (15-minute), etc.

        Returns:
            DataFrame with columns
            ``[open, high, low, close, volume, vwap, transactions]``
            and a timezone-naive DatetimeIndex named ``date``.

        Raises:
            ValueError: If no data is returned or the symbol is invalid.
            RuntimeError: If the API request fails.

        Example::

            >>> df = src.fetch_ohlcv("AAPL", "2023-01-01", "2023-01-31")
            >>> df.columns.tolist()
            ['open', 'high', 'low', 'close', 'volume', 'vwap', 'transactions']
        """
        if not self.is_available():
            raise RuntimeError(
                "Polygon.io API key not configured. "
                "Set POLYGON_API_KEY environment variable."
            )

        # Map interval to Polygon multiplier and timespan
        interval_map = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "15m": (15, "minute"),
            "30m": (30, "minute"),
            "1h": (1, "hour"),
            "4h": (4, "hour"),
            "1d": (1, "day"),
            "1w": (1, "week"),
            "1M": (1, "month"),
        }
        multiplier, timespan = interval_map.get(interval, (1, "day"))

        logger.info(
            "Fetching Polygon.io OHLCV: %s (%s to %s, %s)",
            symbol, start, end, interval,
        )

        endpoint = (
            f"v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}"
            f"/{start}/{end}"
        )
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}

        resp = self._rate_limited_get(endpoint, params)
        data = resp.json()

        if data.get("status") != "OK":
            error_msg = data.get("error", "Unknown error")
            raise RuntimeError(
                f"Polygon.io API error: {error_msg} "
                f"(status={data.get('status')})"
            )

        results = data.get("results", [])
        if not results:
            raise ValueError(
                f"No data returned for {symbol} between {start} and {end}. "
                "Check the symbol format (e.g., 'AAPL' for stocks, "
                "'X:BTCUSD' for crypto)."
            )

        # Parse results into DataFrame
        df = pd.DataFrame(results)

        # Convert timestamp (milliseconds) to datetime
        if "t" in df.columns:
            df["date"] = pd.to_datetime(df["t"], unit="ms")
            df = df.drop(columns=["t"])
            df = df.set_index("date")

        # Rename columns to standard names
        column_map = {
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "transactions",
        }
        df = df.rename(columns=column_map)

        # Ensure index is timezone-naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "date"

        # Select standard columns in order
        standard_cols = ["open", "high", "low", "close", "volume", "vwap", "transactions"]
        available_cols = [c for c in standard_cols if c in df.columns]
        df = df[available_cols]

        logger.info(
            "Polygon.io returned %d rows for %s", len(df), symbol,
        )
        return df

    # ------------------------------------------------------------------
    # Previous close helper
    # ------------------------------------------------------------------

    def fetch_previous_close(self, symbol: str) -> Dict[str, Any]:
        """Fetch the previous day's closing data for a ticker.

        Parameters:
            symbol: Ticker symbol, e.g. ``AAPL``.

        Returns:
            Dictionary with previous close data.

        Raises:
            ValueError: If no data is returned.
            RuntimeError: If the API request fails.
        """
        if not self.is_available():
            raise RuntimeError("Polygon.io API key not configured.")

        logger.info("Fetching Polygon.io previous close: %s", symbol)

        endpoint = f"v2/aggs/ticker/{symbol}/prev"
        resp = self._rate_limited_get(endpoint)
        data = resp.json()

        if data.get("status") != "OK":
            raise RuntimeError(f"Polygon.io API error: {data}")

        results = data.get("results", [])
        if not results:
            raise ValueError(f"No previous close data for {symbol}.")

        result = results[0]
        return {
            "symbol": symbol,
            "open": result.get("o"),
            "high": result.get("h"),
            "low": result.get("l"),
            "close": result.get("c"),
            "volume": result.get("v"),
            "vwap": result.get("vw"),
            "transactions": result.get("n"),
            "timestamp": result.get("t"),
            "source": "polygon",
            "fetched_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Ticker details
    # ------------------------------------------------------------------

    def fetch_ticker_details(self, symbol: str) -> Dict[str, Any]:
        """Fetch detailed information about a ticker symbol.

        Parameters:
            symbol: Ticker symbol, e.g. ``AAPL``.

        Returns:
            Dictionary with ticker details (name, market cap, shares, etc.).

        Raises:
            ValueError: If the ticker is not found.
            RuntimeError: If the API request fails.
        """
        if not self.is_available():
            raise RuntimeError("Polygon.io API key not configured.")

        logger.info("Fetching Polygon.io ticker details: %s", symbol)

        endpoint = f"v3/reference/tickers/{symbol}"
        resp = self._rate_limited_get(endpoint)
        data = resp.json()

        if data.get("status") != "OK":
            raise RuntimeError(f"Polygon.io API error: {data}")

        result = data.get("results", {})
        if not result:
            raise ValueError(f"Ticker '{symbol}' not found on Polygon.io.")

        return {
            "symbol": result.get("ticker"),
            "name": result.get("name"),
            "market": result.get("market"),
            "locale": result.get("locale"),
            "primary_exchange": result.get("primary_exchange"),
            "type": result.get("type"),
            "active": result.get("active"),
            "currency_name": result.get("currency_name"),
            "cik": result.get("cik"),
            "composite_figi": result.get("composite_figi"),
            "share_class_figi": result.get("share_class_figi"),
            "market_cap": result.get("market_cap"),
            "phone_number": result.get("phone_number"),
            "address": result.get("address"),
            "description": result.get("description"),
            "sic_code": result.get("sic_code"),
            "sic_description": result.get("sic_description"),
            "ticker_root": result.get("ticker_root"),
            "homepage_url": result.get("homepage_url"),
            "total_employees": result.get("total_employees"),
            "list_date": result.get("list_date"),
            "icon_url": result.get("branding", {}).get("icon_url"),
            "logo_url": result.get("branding", {}).get("logo_url"),
            "source": "polygon",
            "fetched_at": datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    src = PolygonSource()

    if not src.is_available():
        print("POLYGON_API_KEY not set. Exiting.")
        sys.exit(1)

    print(f"Source info: {src.info()}")

    # Demo OHLCV
    try:
        df = src.fetch_ohlcv("AAPL", "2023-01-01", "2023-01-31")
        print("\n--- OHLCV (AAPL) ---")
        print(df.head())
        print(f"\nShape: {df.shape}")
    except Exception as exc:
        print(f"OHLCV fetch failed: {exc}")

    # Demo previous close
    try:
        prev = src.fetch_previous_close("AAPL")
        print("\n--- Previous Close (AAPL) ---")
        print(f"Close: ${prev.get('close')}")
        print(f"Volume: {prev.get('volume'):,.0f}")
    except Exception as exc:
        print(f"Previous close fetch failed: {exc}")

    # Demo ticker details
    try:
        details = src.fetch_ticker_details("AAPL")
        print("\n--- Ticker Details (AAPL) ---")
        print(f"Name: {details.get('name')}")
        print(f"Market Cap: ${details.get('market_cap'):,.0f}")
        print(f"SIC: {details.get('sic_description')}")
    except Exception as exc:
        print(f"Ticker details fetch failed: {exc}")
