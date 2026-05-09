"""Stock market data, fundamentals, and technical indicators from Alpha Vantage. (stub).

Alpha Vantage -- stock data, fundamentals, and technical indicators.

To activate this source:
    1. Get a free API key at https://www.alphavantage.co/support/#api-key
    2. Set ALPHA_VANTAGE_API_KEY environment variable
    3. pip install alpha-vantage
    4. Implement fetch_ohlcv()

References:
    - https://www.alphavantage.co/documentation/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class AlphaVantageSource(DataSource):
    """Alpha Vantage -- stock data, fundamentals, and technical indicators.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="alpha_vantage",
        category="stocks",
        description="Alpha Vantage -- stock data, fundamentals, and technical indicators.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="5/min",
        data_types=["ohlcv", "fundamentals", "indicators", "forex", "crypto"],
        coverage="global",
        homepage="https://www.alphavantage.co",
        docs_url="https://www.alphavantage.co/documentation/",
        install_cmd="pip install alpha-vantage",
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
            "AlphaVantageSource is a stub. To activate it:\n"
            "1. Get a free API key at https://www.alphavantage.co/support/#api-key\n"
            "2. Set ALPHA_VANTAGE_API_KEY environment variable\n"
            "3. pip install alpha-vantage\n"
            "4. Implement fetch_ohlcv() using alpha_vantage.timeseries.TimeSeries"
        )
