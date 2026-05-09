"""Cryptocurrency prices, market capitalization, trading volume, exchange data, and community metrics from CoinGecko. (stub).

CoinGecko -- crypto prices, market cap, volume, and exchange data.

To activate this source:
    1. No API key required for basic tier
    2. pip install pycoingecko
    3. Implement fetch_ohlcv()

References:
    - https://www.coingecko.com/en/api
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class CoinGeckoSource(DataSource):
    """CoinGecko -- comprehensive cryptocurrency data aggregator.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="coingecko",
        category="crypto",
        description="CoinGecko -- crypto prices, market cap, volume, and exchange data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="10-30 calls/min (free)",
        data_types=["ohlcv", "market_cap", "volume", "exchange_data"],
        coverage="crypto",
        homepage="https://www.coingecko.com",
        docs_url="https://www.coingecko.com/en/api",
        install_cmd="pip install pycoingecko",
        status="stub",
    )

    def is_available(self) -> bool:
        """Return ``False`` -- this source is a stub and not yet implemented."""
        return False

    def fetch_ohlcv(
        self, symbol: str, start: str, end: str, interval: str = "1d",
    ) -> pd.DataFrame:
        """Not implemented -- activate by overriding this method."""
        raise NotImplementedError(
            "CoinGeckoSource is a stub. To activate it:\n"
            "1. No API key required for basic usage\n"
            "2. pip install pycoingecko\n"
            "3. Implement fetch_ohlcv() using pycoingecko.CoinGeckoAPI.get_coin_market_chart_by_id()"
        )
