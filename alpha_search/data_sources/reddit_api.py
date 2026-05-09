"""Reddit post and comment data, subreddit activity, and social sentiment analysis for stocks, crypto, and market discussions. (stub).

Reddit API -- social sentiment and discussion tracking.

To activate this source:
    1. Create app at https://www.reddit.com/prefs/apps
    2. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars
    3. pip install praw
    4. Implement fetch_news() and fetch_sentiment()

References:
    - https://praw.readthedocs.io/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class RedditAPISource(DataSource):
    """Reddit -- social media sentiment and community discussions.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="reddit",
        category="news_sentiment",
        description="Reddit API -- social sentiment and discussion tracking.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="60 requests/min (OAuth)",
        data_types=["news", "sentiment", "social"],
        coverage="global",
        homepage="https://www.reddit.com",
        docs_url="https://praw.readthedocs.io/",
        install_cmd="pip install praw",
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
            "RedditAPISource is a stub. To activate it:\n"
            "1. Create Reddit app at https://www.reddit.com/prefs/apps\n"
            "2. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables\n"
            "3. pip install praw\n"
            "4. Implement fetch_sentiment() using praw.Reddit"
        )
