"""High-performance Yahoo Finance data access with asynchronous requests, providing fundamentals, prices, and option chains. (stub).

YahooQuery -- faster Yahoo Finance data with async support.

To activate this source:
    1. pip install yahooquery
    2. Implement fetch_fundamentals() using yahooquery.Ticker

References:
    - https://yahooquery.dpguthrie.com/guide/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class YahooQuerySource(DataSource):
    """YahooQuery -- high-performance Yahoo Finance data access.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="yahoo_query",
        category="fundamentals",
        description="YahooQuery -- faster Yahoo Finance data with async support.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["fundamentals", "ohlcv", "options"],
        coverage="global",
        homepage="https://yahooquery.dpguthrie.com",
        docs_url="https://yahooquery.dpguthrie.com/guide/",
        install_cmd="pip install yahooquery",
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
            "YahooQuerySource is a stub. To activate it:\n"
            "1. pip install yahooquery\n"
            "2. Implement fetch_fundamentals() using yahooquery.Ticker"
        )
