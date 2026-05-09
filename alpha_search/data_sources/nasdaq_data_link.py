"""Access to the Nasdaq Data Link (formerly Quandl) platform with hundreds of financial, economic, and alternative datasets. (stub).

Nasdaq Data Link (formerly Quandl) -- financial and economic datasets.

To activate this source:
    1. Get API key at https://data.nasdaq.com
    2. Set NASDAQ_DATA_LINK_API_KEY env var
    3. pip install nasdaq-data-link
    4. Implement fetch_ohlcv()

References:
    - https://docs.data.nasdaq.com/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class NasdaqDataLinkSource(DataSource):
    """Nasdaq Data Link -- institutional-quality financial datasets.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="nasdaq_data_link",
        category="stocks",
        description="Nasdaq Data Link (formerly Quandl) -- financial and economic datasets.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="2000 calls/day",
        data_types=["ohlcv", "fundamentals", "macro", "alternative"],
        coverage="global",
        homepage="https://data.nasdaq.com",
        docs_url="https://docs.data.nasdaq.com/",
        install_cmd="pip install nasdaq-data-link",
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
            "NasdaqDataLinkSource is a stub. To activate it:\n"
            "1. Get API key at https://data.nasdaq.com\n"
            "2. Set NASDAQ_DATA_LINK_API_KEY environment variable\n"
            "3. pip install nasdaq-data-link\n"
            "4. Implement fetch_ohlcv() using nasdaqdatalink.get()"
        )
