"""Real-time and historical market data for US stocks, options, forex, and cryptocurrencies from Polygon.io. (stub).

Polygon.io -- US stocks, options, forex, and crypto market data.

To activate this source:
    1. Get API key at https://polygon.io
    2. Set POLYGON_API_KEY env var
    3. pip install polygon-api-client
    4. Implement fetch_ohlcv()

References:
    - https://polygon.io/docs/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class PolygonSource(DataSource):
    """Polygon.io -- real-time and historical market data API.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="polygon",
        category="alternative",
        description="Polygon.io -- US stocks, options, forex, and crypto market data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="5 API calls/min (free)",
        data_types=["ohlcv", "options", "forex", "crypto"],
        coverage="us",
        homepage="https://polygon.io",
        docs_url="https://polygon.io/docs/",
        install_cmd="pip install polygon-api-client",
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
            "PolygonSource is a stub. To activate it:\n"
            "1. Get API key at https://polygon.io\n"
            "2. Set POLYGON_API_KEY environment variable\n"
            "3. pip install polygon-api-client\n"
            "4. Implement fetch_ohlcv() using polygon.RESTClient"
        )
