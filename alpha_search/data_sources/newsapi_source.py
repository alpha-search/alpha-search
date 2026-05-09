"""NewsAPI data source — full live implementation.

Fetches news articles and headlines from `NewsAPI.org <https://newsapi.org>`_,
with sentiment analysis via TextBlob when available.

Environment variables:
    - ``NEWSAPI_API_KEY`` — Required API key from newsapi.org.

Installation::

    pip install requests pandas

Optional for sentiment analysis::

    pip install textblob

References:
    - https://newsapi.org/docs
"""

from __future__ import annotations

import functools
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)

_NEWSAPI_BASE_URL = "https://newsapi.org/v2"


class NewsAPISource(DataSource):
    """News and sentiment data from NewsAPI.

    Provides:
        - Top headlines (global or per-country)
        - Everything search (symbol/keyword based)
        - Source discovery
        - Basic sentiment scoring via TextBlob (optional)

    Requires a free API key from https://newsapi.org.

    Example::

        >>> src = NewsAPISource()
        >>> src.is_available()
        True  # if NEWSAPI_API_KEY is set
        >>> articles = src.fetch_news("Apple", limit=5)
        >>> len(articles)
        5
    """

    meta = SourceMeta(
        name="newsapi",
        category="news_sentiment",
        description=(
            "News articles and headlines from NewsAPI.org. "
            "Search by keyword, source, or date. Optional TextBlob sentiment."
        ),
        requires_api_key=True,
        free_tier=True,
        rate_limit="100/day (free), 10000/day (developer)",
        data_types=["news", "sentiment"],
        coverage="global",
        homepage="https://newsapi.org",
        docs_url="https://newsapi.org/docs",
        install_cmd="pip install requests pandas",
        status="live",
    )

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialise the NewsAPI source.

        Parameters:
            api_key: NewsAPI key. Falls back to ``NEWSAPI_API_KEY`` env var.
        """
        self._api_key = api_key or os.environ.get("NEWSAPI_API_KEY")

    # -- OHLCV (not applicable) ---------------------------------------------

    def fetch_ohlcv(
        self, symbol: str, start: str, end: str, interval: str = "1d",
    ) -> pd.DataFrame:
        """NewsAPI does not provide OHLCV price data.

        This method raises :class:`NotImplementedError` because NewsAPI
        is a news/sentiment source, not a price data provider.  Use
        :meth:`fetch_news` or :meth:`fetch_sentiment` instead.

        Raises:
            NotImplementedError: Always — NewsAPI has no price data.
        """
        raise NotImplementedError(
            "NewsAPI does not provide OHLCV price data. "
            "Use fetch_news() or fetch_sentiment() instead."
        )

    # -- availability -------------------------------------------------------

    @functools.lru_cache(maxsize=1)
    def is_available(self) -> bool:
        """Check if NewsAPI key is configured and API is reachable.

        Returns:
            ``True`` when ``NEWSAPI_API_KEY`` is set and the API responds.
        """
        if not self._api_key:
            logger.warning(
                "NEWSAPI_API_KEY not set. Get a free key at %s",
                self.meta.homepage,
            )
            return False

        try:
            import requests  # noqa: F401
        except ImportError:
            logger.warning("requests is not installed.")
            return False

        # Ping the sources endpoint (lightweight)
        try:
            resp = self._request("GET", "/sources")
            if resp.get("status") == "ok":
                logger.debug("NewsAPI is available")
                return True
        except Exception as exc:
            logger.warning("NewsAPI ping failed: %s", exc)

        return False

    # -- News ---------------------------------------------------------------

    def fetch_news(
        self, symbol: str, limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Fetch news articles mentioning *symbol*.

        Uses the ``everything`` endpoint to search across all indexed
        articles from the last 30 days.

        Parameters:
            symbol: Company name or keyword to search for, e.g. ``Apple``.
            limit: Maximum articles to return (max 100 per API call).

        Returns:
            List of article dicts with keys: ``title``, ``url``,
            ``publishedAt``, ``source``, ``description``.

        Raises:
            ImportError: If ``requests`` is not installed.
            RuntimeError: On API errors.

        Example::

            >>> articles = src.fetch_news("Apple", limit=3)
            >>> articles[0]["title"]
            'Apple announces new product lineup...'
        """
        if not self.is_available():
            raise ImportError(
                "NewsAPI is not available. Ensure NEWSAPI_API_KEY is set "
                "and requests is installed."
            )

        # NewsAPI free tier only supports articles from last 30 days
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        params = {
            "q": symbol,
            "from": from_date,
            "to": to_date,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": min(limit, 100),
            "page": 1,
        }

        logger.info(
            "Fetching news from NewsAPI: %s (limit=%d)", symbol, limit,
        )

        try:
            resp = self._request("GET", "/everything", params=params)
        except Exception as exc:
            logger.error("NewsAPI everything request failed: %s", exc)
            raise RuntimeError(f"NewsAPI failed: {exc}") from exc

        if resp.get("status") != "ok":
            msg = resp.get("message", "Unknown error")
            logger.error("NewsAPI error: %s", msg)
            raise RuntimeError(f"NewsAPI error: {msg}")

        articles = resp.get("articles", [])
        results: List[Dict[str, str]] = []
        for article in articles:
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "published": article.get("publishedAt", ""),
                "source": article.get("source", {}).get("name", ""),
                "description": article.get("description", ""),
                "author": article.get("author", ""),
                "content": article.get("content", ""),
            })

        logger.info(
            "NewsAPI returned %d articles for '%s'", len(results), symbol,
        )
        return results[:limit]

    # -- Top headlines ------------------------------------------------------

    def fetch_headlines(
        self,
        country: str = "us",
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Fetch top headlines for a country/category.

        Parameters:
            country: Two-letter ISO country code, e.g. ``us``, ``gb``.
            category: One of ``business``, ``entertainment``, ``health``,
                ``science``, ``sports``, ``technology``.
            limit: Maximum articles to return.

        Returns:
            List of article dictionaries.
        """
        if not self.is_available():
            raise ImportError("NewsAPI is not available.")

        params: Dict[str, Any] = {
            "country": country,
            "pageSize": min(limit, 100),
            "page": 1,
        }
        if category:
            params["category"] = category

        logger.info(
            "Fetching headlines from NewsAPI: country=%s, category=%s",
            country, category,
        )

        resp = self._request("GET", "/top-headlines", params=params)

        if resp.get("status") != "ok":
            msg = resp.get("message", "Unknown error")
            raise RuntimeError(f"NewsAPI error: {msg}")

        articles = resp.get("articles", [])
        results: List[Dict[str, str]] = []
        for article in articles:
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "published": article.get("publishedAt", ""),
                "source": article.get("source", {}).get("name", ""),
                "description": article.get("description", ""),
                "author": article.get("author", ""),
            })

        return results[:limit]

    # -- Sentiment ----------------------------------------------------------

    def fetch_sentiment(self, symbol: str) -> Dict[str, float]:
        """Fetch sentiment for *symbol* based on recent news articles.

        Uses TextBlob for polarity scoring when available, falling back
        to a keyword-based heuristic.

        Parameters:
            symbol: Company name or keyword.

        Returns:
            Dictionary with ``bullish``, ``bearish``, ``neutral`` scores
            that sum to 1.0.
        """
        articles = self.fetch_news(symbol, limit=20)

        if not articles:
            return {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34}

        # Try TextBlob
        try:
            from textblob import TextBlob  # type: ignore[import-untyped]  # noqa: F401
            return self._textblob_sentiment(articles)
        except ImportError:
            logger.debug("TextBlob not installed; using keyword heuristic")
            return self._keyword_sentiment(articles)

    def _textblob_sentiment(
        self, articles: List[Dict[str, str]],
    ) -> Dict[str, float]:
        """Score sentiment using TextBlob polarity."""
        from textblob import TextBlob

        polarities: List[float] = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            if text.strip():
                polarity = TextBlob(text).sentiment.polarity
                polarities.append(polarity)

        if not polarities:
            return {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34}

        avg = sum(polarities) / len(polarities)

        # Map polarity [-1, 1] to [bearish, bullish]
        if avg > 0.1:
            bullish = min(0.5 + avg * 0.5, 1.0)
            return {"bullish": bullish, "bearish": 1.0 - bullish, "neutral": 0.0}
        elif avg < -0.1:
            bearish = min(0.5 - avg * 0.5, 1.0)
            return {"bullish": 0.0, "bearish": bearish, "neutral": 1.0 - bearish}
        else:
            neutral = 1.0 - abs(avg)
            return {"bullish": (1.0 - neutral) / 2, "bearish": (1.0 - neutral) / 2, "neutral": neutral}

    def _keyword_sentiment(
        self, articles: List[Dict[str, str]],
    ) -> Dict[str, float]:
        """Simple keyword-based sentiment heuristic."""
        bullish_words = {
            "surge", "rally", "gain", "rise", "soar", "jump", "boom",
            "bull", "outperform", "beat", "strong", "growth", "record",
            "high", "up", "positive", "optimistic", "upgrade",
        }
        bearish_words = {
            "fall", "drop", "crash", "decline", "plunge", "slump",
            "bear", "underperform", "miss", "weak", "loss", "low",
            "down", "negative", "pessimistic", "downgrade", "tumble",
        }

        bullish_count = 0
        bearish_count = 0

        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            words = set(text.lower().split())
            bullish_count += len(words & bullish_words)
            bearish_count += len(words & bearish_words)

        total = bullish_count + bearish_count
        if total == 0:
            return {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34}

        bullish = bullish_count / total
        bearish = bearish_count / total
        neutral = max(0.0, 1.0 - bullish - bearish)

        # Normalise
        total_score = bullish + bearish + neutral
        return {
            "bullish": round(bullish / total_score, 4),
            "bearish": round(bearish / total_score, 4),
            "neutral": round(neutral / total_score, 4),
        }

    # -- Internal request helper -------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated request to NewsAPI."""
        import requests

        url = f"{_NEWSAPI_BASE_URL}{path}"
        params = params or {}
        params["apiKey"] = self._api_key

        try:
            resp = requests.request(method, url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("NewsAPI request error: %s", exc)
            raise RuntimeError(f"NewsAPI request failed: {exc}") from exc
