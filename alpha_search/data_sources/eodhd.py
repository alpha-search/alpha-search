"""Stock price data from 70+ exchanges worldwide with fundamental data, ETFs, mutual funds, and bonds from EOD Historical Data. (stub).

EOD Historical Data -- 70+ exchanges, 60k+ tickers, fundamental data.

To activate this source:
    1. Get API key at https://eodhistoricaldata.com
    2. Set EODHD_API_KEY env var
    3. pip install eodhd
    4. Implement fetch_ohlcv()

References:
    - https://eodhistoricaldata.com/financial-apis/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class EODHDSource(DataSource):
    """EOD Historical Data -- global stock prices and fundamentals.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="eodhd",
        category="stocks",
        description="EOD Historical Data -- 70+ exchanges, 60k+ tickers, fundamental data.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="1000/day",
        data_types=["ohlcv", "fundamentals", "splits", "dividends"],
        coverage="global",
        homepage="https://eodhistoricaldata.com",
        docs_url="https://eodhistoricaldata.com/financial-apis/",
        install_cmd="pip install eodhd",
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
            "EODHDSource is a stub. To activate it:\n"
            "1. Get API key at https://eodhistoricaldata.com\n"
            "2. Set EODHD_API_KEY environment variable\n"
            "3. pip install eodhd\n"
            "4. Implement fetch_ohlcv() using eodhd.APICall"
        )
