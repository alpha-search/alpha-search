"""Real-time and historical market data for stocks, forex, cryptocurrencies, ETFs, and indices from Twelve Data. (stub).

Twelve Data -- stocks, forex, crypto, and ETF real-time data.

To activate this source:
    1. Get API key at https://twelvedata.com
    2. Set TWELVEDATA_API_KEY env var
    3. pip install twelvedata
    4. Implement fetch_ohlcv()

References:
    - https://twelvedata.com/docs/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class TwelveDataSource(DataSource):
    """Twelve Data -- real-time market data for multiple asset classes.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="twelvedata",
        category="forex_commodities",
        description="Twelve Data -- stocks, forex, crypto, and ETF real-time data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="800/day (free)",
        data_types=["ohlcv", "forex", "crypto", "etf"],
        coverage="global",
        homepage="https://twelvedata.com",
        docs_url="https://twelvedata.com/docs/",
        install_cmd="pip install twelvedata",
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
            "TwelveDataSource is a stub. To activate it:\n"
            "1. Get API key at https://twelvedata.com\n"
            "2. Set TWELVEDATA_API_KEY environment variable\n"
            "3. pip install twelvedata\n"
            "4. Implement fetch_ohlcv() using twelvedata.TDClient"
        )
