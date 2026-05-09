"""Real-time financial news, market sentiment analysis, fundamental data, and economic calendar from Finnhub. (stub).

Finnhub -- real-time financial news, sentiment, and fundamentals.

To activate this source:
    1. Get API key at https://finnhub.io
    2. Set FINNHUB_API_KEY env var
    3. pip install finnhub-python
    4. Implement fetch_news() and fetch_sentiment()

References:
    - https://finnhub.io/docs/api/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class FinnhubNewsSource(DataSource):
    """Finnhub -- financial news, sentiment, and market data.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="finnhub",
        category="news_sentiment",
        description="Finnhub -- real-time financial news, sentiment, and fundamentals.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="60 calls/min (free)",
        data_types=["news", "sentiment", "fundamentals", "ohlcv"],
        coverage="global",
        homepage="https://finnhub.io",
        docs_url="https://finnhub.io/docs/api/",
        install_cmd="pip install finnhub-python",
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
            "FinnhubNewsSource is a stub. To activate it:\n"
            "1. Get API key at https://finnhub.io\n"
            "2. Set FINNHUB_API_KEY environment variable\n"
            "3. pip install finnhub-python\n"
            "4. Implement fetch_sentiment() using finnhub.Client"
        )
