"""Cryptocurrency prices, market capitalization, trading volume, and exchange data from CoinGecko.

CoinGecko is the world's largest independent crypto data aggregator.
No API key is required for the free tier.

Setup:
    No setup required.  The free tier allows 10-30 calls/minute.
    For higher limits, set COINGECKO_API_KEY environment variable.

References:
    - https://www.coingecko.com
    - https://www.coingecko.com/en/api
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

# Mapping of common ticker symbols to CoinGecko coin IDs.
# Covers the top 50+ cryptocurrencies by market cap.
_COIN_ID_MAP: Dict[str, str] = {
    # Major coins
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "USDC": "usd-coin",
    "XRP": "ripple",
    "STETH": "staked-ether",
    "DOGE": "dogecoin",
    "TRX": "tron",
    "TON": "the-open-network",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "SHIB": "shiba-inu",
    "WBTC": "wrapped-bitcoin",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "BCH": "bitcoin-cash",
    "NEAR": "near",
    "LTC": "litecoin",
    "MATIC": "matic-network",
    "ICP": "internet-computer",
    "UNI": "uniswap",
    "LEO": "leo-token",
    "DAI": "dai",
    "ETC": "ethereum-classic",
    "APT": "aptos",
    "PEPE": "pepe",
    "XLM": "stellar",
    "FET": "fetch-ai",
    "OP": "optimism",
    "CRO": "crypto-com-chain",
    "XMR": "monero",
    "OKB": "okb",
    "ARB": "arbitrum",
    "FIL": "filecoin",
    "MNT": "mantle",
    "IMX": "immutable-x",
    "HBAR": "hedera-hashgraph",
    "TAO": "bittensor",
    "VET": "vechain",
    "MKR": "maker",
    "KAS": "kaspa",
    "INJ": "injective-protocol",
    "RENDER": "render-token",
    "FDUSD": "first-digital-usd",
    "SUI": "sui",
    "WIF": "dogwifcoin",
    "TIA": "celestia",
    "GRT": "the-graph",
    "LDO": "lido-dao",
    "THETA": "theta-token",
    "RUNE": "thorchain",
    "FTM": "fantom",
    "AR": "arweave",
    "SEI": "sei-network",
    "AAVE": "aave",
    "ALGO": "algorand",
    "QNT": "quant-network",
    "EGLD": "elrond-erd-2",
    "BSV": "bitcoin-cash-sv",
    "ATOM": "cosmos",
    "FLOW": "flow",
    "FLR": "flare-networks",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "AXS": "axie-infinity",
    "XTZ": "tezos",
    "EOS": "eos",
    "NEO": "neo",
    "IOTA": "iota",
    "KCS": "kucoin-shares",
    "XEC": "ecash",
    "BTT": "bittorrent",
    "USDD": "usdd",
    "FRAX": "frax",
}


class CoinGeckoSource(DataSource):
    """CoinGecko — cryptocurrency prices, market cap, volume, and exchange data.

    Provides:
        - OHLCV price data for 10,000+ cryptocurrencies
        - Market capitalization and trading volume
        - Exchange rates against USD, EUR, BTC, etc.
        - No API key required for basic usage

    Symbols are automatically mapped from ticker symbols (e.g. ``BTC``) to
    CoinGecko's internal coin IDs (e.g. ``bitcoin``).  A hardcoded mapping
    covers the top 50+ coins.  For unmapped coins, the ticker is lower-cased
    and used directly as the coin ID.

    Example::

        >>> src = CoinGeckoSource()
        >>> src.is_available()
        True
        >>> df = src.fetch_ohlcv("BTC", "2023-01-01", "2023-01-31")
        >>> df.head()
                       open      high       low     close      volume
        date
        2023-01-01  16547.50  16600.12  16520.00  16550.00  1234567890
    """

    meta = SourceMeta(
        name="coingecko",
        category="crypto",
        description=(
            "CoinGecko — crypto prices, market cap, volume, and exchange data. "
            "10,000+ cryptocurrencies, no API key required."
        ),
        requires_api_key=False,
        free_tier=True,
        rate_limit="10-30 calls/min (free)",
        data_types=["ohlcv", "market_cap", "volume", "exchange_data"],
        coverage="crypto",
        homepage="https://www.coingecko.com",
        docs_url="https://www.coingecko.com/en/api",
        install_cmd="pip install requests pandas",
        status="live",
    )

    BASE_URL = "https://api.coingecko.com/api/v3"
    _last_call: float = 0.0
    MIN_INTERVAL: float = 2.0  # seconds between calls (~30/min)

    # ------------------------------------------------------------------
    # Coin ID mapping
    # ------------------------------------------------------------------

    @classmethod
    def _get_coin_id(cls, symbol: str) -> str:
        """Map a ticker symbol to a CoinGecko coin ID.

        Parameters:
            symbol: Ticker symbol, e.g. ``BTC``, ``ETH``.

        Returns:
            CoinGecko coin ID string.
        """
        symbol_upper = symbol.upper()
        if symbol_upper in _COIN_ID_MAP:
            return _COIN_ID_MAP[symbol_upper]
        # Fallback: try lowercase symbol as coin ID
        return symbol.lower()

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether CoinGecko API is reachable.

        Returns:
            ``True`` always — no API key or dependencies required.
        """
        return True

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limited_get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Execute a rate-limited GET request to the CoinGecko API.

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
            logger.debug("CoinGecko rate limit: sleeping %.2fs", sleep_for)
            time.sleep(sleep_for)

        url = f"{self.BASE_URL}/{endpoint}"
        headers: Dict[str, str] = {}
        api_key = os.environ.get("COINGECKO_API_KEY")
        if api_key:
            headers["x-cg-demo-api-key"] = api_key

        logger.debug("CoinGecko API call: %s", endpoint)

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("CoinGecko request failed: %s", exc)
            raise RuntimeError(f"CoinGecko API request failed: {exc}") from exc
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
        """Fetch OHLCV data for a cryptocurrency from CoinGecko.

        Uses the ``/coins/{id}/market_chart/range`` endpoint to fetch
        price, market cap, and volume data within a Unix timestamp range.
        OHLCV bars are constructed from the returned price data points.

        Parameters:
            symbol: Cryptocurrency ticker symbol, e.g. ``BTC``, ``ETH``.
            start: Start date ``YYYY-MM-DD`` (inclusive).
            end: End date ``YYYY-MM-DD`` (inclusive).
            interval: Bar interval — ``"1d"`` (default), ``"1h"`` not
                directly supported by the free endpoint.

        Returns:
            DataFrame with columns ``[open, high, low, close, volume]``
            and a timezone-naive DatetimeIndex named ``date``.

        Raises:
            ValueError: If no data is returned or the symbol is invalid.
            RuntimeError: If the API request fails.

        Example::

            >>> df = src.fetch_ohlcv("BTC", "2023-01-01", "2023-01-31")
            >>> df.columns.tolist()
            ['open', 'high', 'low', 'close', 'volume']
        """
        coin_id = self._get_coin_id(symbol)
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)

        # CoinGecko uses Unix timestamps
        from_ts = int(start_dt.timestamp())
        to_ts = int(end_dt.timestamp())

        logger.info(
            "Fetching CoinGecko OHLCV: %s (coin_id=%s, %s to %s)",
            symbol, coin_id, start, end,
        )

        params = {
            "vs_currency": "usd",
            "from": from_ts,
            "to": to_ts,
        }

        resp = self._rate_limited_get(f"coins/{coin_id}/market_chart/range", params)
        data = resp.json()

        if not data:
            raise ValueError(f"No data returned for {symbol} (coin_id={coin_id}).")

        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])

        if not prices:
            raise ValueError(
                f"No price data for {symbol} between {start} and {end}."
            )

        # Build DataFrames for prices and volumes
        price_df = pd.DataFrame(prices, columns=["timestamp", "price"])
        price_df["date"] = pd.to_datetime(price_df["timestamp"], unit="ms")
        price_df = price_df.set_index("date").drop(columns=["timestamp"])

        vol_df = pd.DataFrame(volumes, columns=["timestamp", "volume"])
        vol_df["date"] = pd.to_datetime(vol_df["timestamp"], unit="ms")
        vol_df = vol_df.set_index("date").drop(columns=["timestamp"])

        # Combine price and volume
        df = price_df.join(vol_df, how="outer")
        df = df.fillna(0)

        # Resample to daily OHLCV
        df = df.resample("D").agg({
            "price": ["first", "max", "min", "last"],
            "volume": "sum",
        })
        df.columns = ["open", "high", "low", "close", "volume"]
        df = df.dropna(subset=["open", "high", "low", "close"])

        if df.empty:
            raise ValueError(
                f"No OHLCV data for {symbol} between {start} and {end}."
            )

        logger.info(
            "CoinGecko returned %d rows for %s", len(df), symbol,
        )
        return df

    # ------------------------------------------------------------------
    # Market data helpers
    # ------------------------------------------------------------------

    def fetch_market_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch current market data for a cryptocurrency.

        Uses the ``/coins/{id}`` endpoint to retrieve current price,
        market cap, 24h volume, and supply metrics.

        Parameters:
            symbol: Cryptocurrency ticker symbol, e.g. ``BTC``.

        Returns:
            Dictionary with current market data.

        Raises:
            ValueError: If the coin is not found.
            RuntimeError: If the API request fails.
        """
        coin_id = self._get_coin_id(symbol)

        logger.info("Fetching CoinGecko market data: %s", symbol)

        params = {"localization": "false", "tickers": "false", "market_data": "true"}
        resp = self._rate_limited_get(f"coins/{coin_id}", params)
        data = resp.json()

        if not data or "id" not in data:
            raise ValueError(f"Coin '{symbol}' (id={coin_id}) not found on CoinGecko.")

        market_data = data.get("market_data", {})
        result: Dict[str, Any] = {
            "symbol": symbol,
            "coin_id": coin_id,
            "name": data.get("name"),
            "current_price_usd": market_data.get("current_price", {}).get("usd"),
            "market_cap_usd": market_data.get("market_cap", {}).get("usd"),
            "total_volume_usd": market_data.get("total_volume", {}).get("usd"),
            "high_24h_usd": market_data.get("high_24h", {}).get("usd"),
            "low_24h_usd": market_data.get("low_24h", {}).get("usd"),
            "price_change_24h": market_data.get("price_change_24h"),
            "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
            "circulating_supply": market_data.get("circulating_supply"),
            "total_supply": market_data.get("total_supply"),
            "max_supply": market_data.get("max_supply"),
            "ath_usd": market_data.get("ath", {}).get("usd"),
            "ath_date": market_data.get("ath_date", {}).get("usd"),
            "atl_usd": market_data.get("atl", {}).get("usd"),
            "source": "coingecko",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        return result

    def fetch_exchange_rate(
        self,
        from_symbol: str,
        to_currency: str = "usd",
    ) -> Dict[str, Any]:
        """Fetch the current exchange rate for a cryptocurrency.

        Parameters:
            from_symbol: Cryptocurrency ticker, e.g. ``BTC``.
            to_currency: Target currency (default ``usd``).

        Returns:
            Dictionary with exchange rate info.
        """
        coin_id = self._get_coin_id(from_symbol)

        logger.info(
            "Fetching CoinGecko exchange rate: %s -> %s", from_symbol, to_currency,
        )

        params = {"ids": coin_id, "vs_currencies": to_currency.lower()}
        resp = self._rate_limited_get("simple/price", params)
        data = resp.json()

        if coin_id not in data:
            raise ValueError(
                f"Exchange rate not found for {from_symbol} (id={coin_id})."
            )

        rate = data[coin_id].get(to_currency.lower())
        return {
            "from": from_symbol,
            "to": to_currency.upper(),
            "rate": rate,
            "source": "coingecko",
            "fetched_at": datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    src = CoinGeckoSource()
    print(f"Source info: {src.info()}")

    # Demo OHLCV
    try:
        df = src.fetch_ohlcv("BTC", "2023-01-01", "2023-01-10")
        print("\n--- OHLCV (BTC) ---")
        print(df.head())
        print(f"\nShape: {df.shape}")
    except Exception as exc:
        print(f"OHLCV fetch failed: {exc}")

    # Demo market data
    try:
        market = src.fetch_market_data("BTC")
        print("\n--- Market Data (BTC) ---")
        print(f"Price (USD): ${market.get('current_price_usd'):,.2f}")
        print(f"Market Cap: ${market.get('market_cap_usd'):,.0f}")
    except Exception as exc:
        print(f"Market data fetch failed: {exc}")

    # Demo exchange rate
    try:
        rate = src.fetch_exchange_rate("ETH", "usd")
        print("\n--- Exchange Rate (ETH/USD) ---")
        print(f"Rate: ${rate.get('rate'):,.2f}")
    except Exception as exc:
        print(f"Exchange rate fetch failed: {exc}")
