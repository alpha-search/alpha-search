"""Cryptocurrency market data, price rankings, market capitalization, volume, and metadata from CoinMarketCap. (stub).

CoinMarketCap -- cryptocurrency market data and rankings.

To activate this source:
    1. Get API key at https://coinmarketcap.com/api
    2. Set CMC_API_KEY env var
    3. pip install python-coinmarketcap
    4. Implement fetch_ohlcv()

References:
    - https://coinmarketcap.com/api/documentation/v1/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class CoinMarketCapSource(DataSource):
    """CoinMarketCap -- crypto market data, rankings, and metadata.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="coinmarketcap",
        category="crypto",
        description="CoinMarketCap -- cryptocurrency market data and rankings.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="10k calls/month (free)",
        data_types=["ohlcv", "market_cap", "volume", "metadata"],
        coverage="crypto",
        homepage="https://coinmarketcap.com",
        docs_url="https://coinmarketcap.com/api/documentation/v1/",
        install_cmd="pip install python-coinmarketcap",
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
            "CoinMarketCapSource is a stub. To activate it:\n"
            "1. Get API key at https://coinmarketcap.com/api\n"
            "2. Set CMC_API_KEY environment variable\n"
            "3. pip install python-coinmarketcap\n"
            "4. Implement fetch_ohlcv() using the CMC API"
        )
