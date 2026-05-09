"""Global Database of Events, Language, and Tone (GDELT) -- worldwide news monitoring, event tracking, and sentiment analysis. (stub).

GDELT -- global event and news database with sentiment analysis.

To activate this source:
    1. pip install gdeltdoc
    2. Implement fetch_news() and fetch_sentiment()

References:
    - https://github.com/alex9smith/gdelt-doc-api
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class GDELTSource(DataSource):
    """GDELT -- global database of events, language, and tone.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="gdelt",
        category="news_sentiment",
        description="GDELT -- global event and news database with sentiment analysis.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="unspecified",
        data_types=["news", "sentiment", "events", "global"],
        coverage="global",
        homepage="https://www.gdeltproject.org",
        docs_url="https://github.com/alex9smith/gdelt-doc-api",
        install_cmd="pip install gdeltdoc",
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
            "GDELTSource is a stub. To activate it:\n"
            "1. pip install gdeltdoc\n"
            "2. Implement fetch_sentiment() using gdeltdoc to query GDELT data"
        )
