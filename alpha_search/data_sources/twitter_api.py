"""Real-time tweets, sentiment analysis, trending topics, and social engagement metrics from Twitter/X for financial instruments. (stub).

Twitter/X API -- real-time social sentiment and trend tracking.

To activate this source:
    1. Get API key at https://developer.twitter.com
    2. Set TWITTER_BEARER_TOKEN env var
    3. pip install tweepy
    4. Implement fetch_news() and fetch_sentiment()

References:
    - https://docs.tweepy.org/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class TwitterAPISource(DataSource):
    """Twitter/X -- real-time social sentiment and market trends.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="twitter",
        category="news_sentiment",
        description="Twitter/X API -- real-time social sentiment and trend tracking.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="v2: 300 requests/15min",
        data_types=["news", "sentiment", "social", "trends"],
        coverage="global",
        homepage="https://twitter.com",
        docs_url="https://docs.tweepy.org/",
        install_cmd="pip install tweepy",
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
            "TwitterAPISource is a stub. To activate it:\n"
            "1. Get API key at https://developer.twitter.com\n"
            "2. Set TWITTER_BEARER_TOKEN environment variable\n"
            "3. pip install tweepy\n"
            "4. Implement fetch_sentiment() using tweepy.Client"
        )
