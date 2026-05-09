"""End-of-day prices, historical data, news feeds, and fundamental data for US-listed equities from Tiingo. (stub).

Tiingo -- end-of-day prices, news, and fundamentals for US equities.

To activate this source:
    1. Get API key at https://tiingo.com
    2. Set TIINGO_API_KEY env var
    3. pip install tiingo
    4. Implement fetch_ohlcv()

References:
    - https://www.tiingo.com/documentation/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class TiingoSource(DataSource):
    """Tiingo -- US stock data with news and fundamentals.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="tiingo",
        category="stocks",
        description="Tiingo -- end-of-day prices, news, and fundamentals for US equities.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="500/day (free)",
        data_types=["ohlcv", "fundamentals", "news"],
        coverage="us",
        homepage="https://tiingo.com",
        docs_url="https://www.tiingo.com/documentation/",
        install_cmd="pip install tiingo",
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
            "TiingoSource is a stub. To activate it:\n"
            "1. Get API key at https://tiingo.com\n"
            "2. Set TIINGO_API_KEY environment variable\n"
            "3. pip install tiingo\n"
            "4. Implement fetch_ohlcv() using tiingo.TiingoClient"
        )
