"""Cryptocurrency price data, news aggregation, social metrics, and on-chain analytics from CryptoCompare. (stub).

CryptoCompare -- crypto prices, news, and social data.

To activate this source:
    1. Get API key at https://www.cryptocompare.com
    2. Set CRYPTOCOMPARE_API_KEY env var
    3. pip install cryptocompare
    4. Implement fetch_ohlcv()

References:
    - https://developers.cryptocompare.com/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class CryptoCompareSource(DataSource):
    """CryptoCompare -- cryptocurrency data and analytics platform.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="cryptocompare",
        category="crypto",
        description="CryptoCompare -- crypto prices, news, and social data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="100k calls/month (free)",
        data_types=["ohlcv", "news", "social", "onchain"],
        coverage="crypto",
        homepage="https://www.cryptocompare.com",
        docs_url="https://developers.cryptocompare.com/",
        install_cmd="pip install cryptocompare",
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
            "CryptoCompareSource is a stub. To activate it:\n"
            "1. Get API key at https://www.cryptocompare.com\n"
            "2. Set CRYPTOCOMPARE_API_KEY environment variable\n"
            "3. pip install cryptocompare\n"
            "4. Implement fetch_ohlcv() using cryptocompare.get_historical_price_day()"
        )
