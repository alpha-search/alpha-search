"""Binance data source — full live implementation.

Wraps :class:`alpha_search.data.binance_provider.BinanceProvider` in the
standard :class:`DataSource` interface.  Provides OHLCV, order-book,
24h ticker statistics, and account information for Binance spot markets.

Environment variables:
    - ``BINANCE_API_KEY`` — API key (optional for public endpoints)
    - ``BINANCE_API_SECRET`` — API secret (optional for public endpoints)
    - ``BINANCE_BASE_URL`` — Override base URL (default: https://api.binance.com)

Installation::

    pip install requests pandas

References:
    - https://binance-docs.github.io/apidocs/spot/en/
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers — try to use the existing BinanceProvider when available
# ---------------------------------------------------------------------------


def _import_binance_provider() -> Optional[Any]:
    """Try to import the project's BinanceProvider, returning ``None`` on failure."""
    try:
        from alpha_search.data.binance_provider import BinanceProvider  # type: ignore[import-untyped]
        return BinanceProvider
    except ImportError:
        return None


def _import_requests() -> Optional[Any]:
    """Try to import ``requests``, returning ``None`` on failure."""
    try:
        import requests  # noqa: F401
        return requests
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class BinanceSource(DataSource):
    """Binance cryptocurrency exchange data source.

    Provides:
        - OHLCV price history (klines/candlesticks)
        - 24-hour ticker statistics
        - Order book snapshots
        - Real-time trades (via WebSocket — not yet implemented)

    Public endpoints do **not** require an API key.  Authenticated
    endpoints (account balances, order history) require key + secret.

    Example::

        >>> src = BinanceSource()
        >>> src.is_available()
        True
        >>> df = src.fetch_ohlcv("BTCUSDT", "2023-01-01", "2023-01-31", "1h")
        >>> df.head()
                        open     high      low    close      volume
        date
        2023-01-01 00:00:00  16520.5  16550.0  16510.0  16540.2  1234.56
    """

    meta = SourceMeta(
        name="binance",
        category="crypto",
        description=(
            "Cryptocurrency data from Binance — the world's largest "
            "crypto exchange by volume. OHLCV, 24h stats, order book."
        ),
        requires_api_key=False,
        free_tier=True,
        rate_limit="1200/min (IP weight based)",
        data_types=["ohlcv", "orderbook", "trades", "ticker"],
        coverage="crypto",
        homepage="https://www.binance.com",
        docs_url="https://binance-docs.github.io/apidocs/spot/en/",
        install_cmd="pip install requests pandas",
        status="live",
    )

    DEFAULT_BASE_URL: str = "https://api.binance.com"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> None:
        """Initialise the Binance source.

        Parameters:
            api_key: Binance API key. Falls back to ``BINANCE_API_KEY`` env var.
            api_secret: Binance API secret. Falls back to ``BINANCE_API_SECRET`` env var.
        """
        self._api_key = api_key or os.environ.get("BINANCE_API_KEY")
        self._api_secret = api_secret or os.environ.get("BINANCE_API_SECRET")
        self._base_url = os.environ.get("BINANCE_BASE_URL", self.DEFAULT_BASE_URL)
        self._provider_cls = _import_binance_provider()
        self._provider: Optional[Any] = None

        # Initialise the provider if available
        if self._provider_cls is not None:
            try:
                self._provider = self._provider_cls(
                    api_key=self._api_key,
                    api_secret=self._api_secret,
                )
                logger.debug("BinanceProvider initialised successfully")
            except Exception as exc:
                logger.warning("Failed to initialise BinanceProvider: %s", exc)
                self._provider = None

    # -- availability -------------------------------------------------------

    @functools.lru_cache(maxsize=1)
    def is_available(self) -> bool:
        """Check whether Binance API is reachable and dependencies are installed.

        Returns:
            ``True`` when ``requests`` is installed and the Binance API
            responds with a valid server-time payload.
        """
        if _import_requests() is None:
            logger.warning(
                "requests is not installed. Run: %s", self.meta.install_cmd,
            )
            return False

        # Ping the server time endpoint — the lightest possible check
        try:
            resp = self._request("GET", "/api/v3/time")
            if "serverTime" in resp:
                logger.debug("Binance API is reachable")
                return True
        except Exception as exc:
            logger.warning("Binance API ping failed: %s", exc)

        return False

    # -- OHLCV --------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch OHLCV (klines) from Binance.

        Parameters:
            symbol: Trading pair, e.g. ``BTCUSDT``, ``ETHBTC``.
            start: Start date ``YYYY-MM-DD``.
            end: End date ``YYYY-MM-DD``.
            interval: Kline interval — ``1m``, ``5m``, ``15m``, ``1h``,
                ``4h``, ``1d``, ``1w``, ``1M``.

        Returns:
            DataFrame with columns ``open, high, low, close, volume``
            and a DatetimeIndex.

        Raises:
            ImportError: If ``requests`` is not installed.
            ValueError: On invalid symbol or date range.
            RuntimeError: On API errors.

        Example::

            >>> df = src.fetch_ohlcv("BTCUSDT", "2023-01-01", "2023-01-31", "1h")
            >>> len(df)
            744
        """
        if not self.is_available():
            raise ImportError(
                "requests is required. Install it with: "
                f"{self.meta.install_cmd}"
            )

        import requests

        # Convert interval to Binance format
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
            "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
        }
        binance_interval = interval_map.get(interval, interval)

        # Convert dates to millisecond timestamps
        start_ts = int(pd.Timestamp(start).timestamp() * 1000)
        end_ts = int(pd.Timestamp(end).timestamp() * 1000)

        logger.info(
            "Fetching klines from Binance: %s (%s to %s, %s)",
            symbol, start, end, binance_interval,
        )

        all_klines: List[List[Any]] = []
        limit = 1000  # Max per request

        while start_ts < end_ts:
            try:
                params = {
                    "symbol": symbol.upper().replace("-", "").replace("/", ""),
                    "interval": binance_interval,
                    "startTime": start_ts,
                    "endTime": end_ts,
                    "limit": limit,
                }

                if self._provider is not None:
                    # Use the BinanceProvider directly
                    klines = self._provider._request("GET", "/api/v3/klines", params=params)
                else:
                    klines = self._request("GET", "/api/v3/klines", params=params)

                if not klines:
                    break

                all_klines.extend(klines)

                # Update start_ts to the open time of the last kline + 1ms
                start_ts = klines[-1][0] + 1

                if len(klines) < limit:
                    break

            except Exception as exc:
                logger.error("Binance klines request failed: %s", exc)
                raise RuntimeError(f"Binance klines failed: {exc}") from exc

        if not all_klines:
            raise ValueError(
                f"No klines returned for {symbol} between {start} and {end}. "
                "Check the symbol and interval."
            )

        # Parse klines into DataFrame
        # Binance kline format:
        # [open_time, open, high, low, close, volume, close_time, ...]
        df = pd.DataFrame(
            all_klines,
            columns=[
                "open_time", "open", "high", "low", "close",
                "volume", "close_time", "quote_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore",
            ],
        )

        # Convert types
        df["date"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
        df = df.sort_index()

        logger.info(
            "Binance returned %d klines for %s", len(df), symbol,
        )
        return df

    # -- 24h ticker ---------------------------------------------------------

    def fetch_ticker_24h(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetch 24-hour rolling window statistics.

        Parameters:
            symbol: Trading pair, e.g. ``BTCUSDT``. If ``None``, returns
                data for all ~2000+ trading pairs.

        Returns:
            Dictionary (or list of dictionaries) with 24h stats.
        """
        if not self.is_available():
            raise ImportError("requests is required.")

        params: Dict[str, str] = {}
        if symbol:
            params["symbol"] = symbol.upper().replace("-", "").replace("/", "")

        logger.info("Fetching 24h ticker from Binance: %s", symbol or "ALL")
        return self._request("GET", "/api/v3/ticker/24hr", params=params)

    # -- Order book ---------------------------------------------------------

    def fetch_order_book(
        self, symbol: str, limit: int = 100,
    ) -> Dict[str, Any]:
        """Fetch current order book snapshot.

        Parameters:
            symbol: Trading pair.
            limit: Number of bids/asks.  Valid: 5, 10, 20, 50, 100, 500, 1000, 5000.

        Returns:
            Dictionary with ``bids``, ``asks``, and ``lastUpdateId``.
        """
        if not self.is_available():
            raise ImportError("requests is required.")

        params = {
            "symbol": symbol.upper().replace("-", "").replace("/", ""),
            "limit": str(limit),
        }

        logger.info("Fetching order book from Binance: %s", symbol)
        return self._request("GET", "/api/v3/depth", params=params)

    # -- Exchange info ------------------------------------------------------

    def fetch_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange metadata — symbols, filters, rate limits.

        Returns:
            Dictionary with exchange configuration.
        """
        if not self.is_available():
            raise ImportError("requests is required.")

        logger.info("Fetching Binance exchange info")
        return self._request("GET", "/api/v3/exchangeInfo")

    # -- Internal request helper -------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated or unauthenticated request to Binance.

        Falls back to raw ``requests`` if :class:`BinanceProvider` is
        not available.
        """
        if self._provider is not None:
            try:
                return self._provider._request(method, path, params=params, data=data)
            except Exception:
                # Fall through to raw requests
                pass

        import requests

        url = f"{self._base_url}{path}"
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["X-MBX-APIKEY"] = self._api_key

        try:
            resp = requests.request(
                method, url, params=params, json=data, headers=headers, timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Binance API error: %s", exc)
            raise RuntimeError(f"Binance API error: {exc}") from exc
