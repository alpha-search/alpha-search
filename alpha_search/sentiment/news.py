"""NewsAPI-based sentiment analyzer.

Structured stub with real code. Requires a NEWSAPI_KEY environment variable.
Falls back to a neutral response when the API key is missing or the service
is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from alpha_search.core.config import get_config
from alpha_search.sentiment.base import SentimentAnalyzer

logger = logging.getLogger(__name__)

_NEWSAPI_BASE = "https://newsapi.org/v2"


class NewsAPISentiment(SentimentAnalyzer):
    """Sentiment analyzer that fetches news articles and analyses headlines.

    Requires ``NEWSAPI_KEY`` to be set in the environment or config.
    Without a key, returns neutral sentiment.

    Example::

        analyzer = NewsAPISentiment()
        result = analyzer.analyze("AAPL")
        # Analyses recent news headlines for AAPL
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or get_config().newsapi_key
        self._session = requests.Session()

    @property
    def name(self) -> str:
        return "newsapi"

    def analyze(self, text: str) -> Dict[str, float]:
        """Analyze sentiment by fetching news for *text* (ticker or keyword).

        Returns:
            Aggregated sentiment dict with ``positive``, ``negative``,
            ``neutral``, and ``score`` in ``[-1, 1]``.
        """
        if not self._api_key:
            logger.debug("No NEWSAPI_KEY configured; returning neutral.")
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        try:
            headlines = self._fetch_headlines(text)
            if not headlines:
                return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

            # Simple keyword-based sentiment on headlines
            return self._aggregate_headline_sentiment(headlines)
        except Exception as exc:
            logger.warning("NewsAPI analysis failed: %s", exc)
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

    def _fetch_headlines(self, query: str, days_back: int = 7) -> List[str]:
        """Fetch news headlines for a query from NewsAPI."""
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"{_NEWSAPI_BASE}/everything"
        params = {
            "q": query,
            "from": from_date,
            "sortBy": "relevancy",
            "language": "en",
            "apiKey": self._api_key,
            "pageSize": 20,
        }
        try:
            resp = self._session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            return [a.get("title", "") for a in articles if a.get("title")]
        except Exception as exc:
            logger.debug("NewsAPI fetch failed: %s", exc)
            return []

    def _aggregate_headline_sentiment(self, headlines: List[str]) -> Dict[str, float]:
        """Aggregate simple keyword sentiment across headlines."""
        pos_words = {"strong", "growth", "profit", "gain", "up", "rise", "bullish",
                     "beat", "positive", "surge", "rally", "boom", "success"}
        neg_words = {"weak", "loss", "decline", "down", "fall", "bearish",
                     "miss", "negative", "drop", "crash", "slump", "risk", "fear"}

        total_pos = 0
        total_neg = 0
        for h in headlines:
            h_lower = h.lower()
            total_pos += sum(1 for w in pos_words if w in h_lower)
            total_neg += sum(1 for w in neg_words if w in h_lower)

        total = total_pos + total_neg
        if total == 0:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        pos_prob = total_pos / total
        neg_prob = total_neg / total
        neutral_prob = max(0.0, 1.0 - pos_prob - neg_prob)

        # Renormalize
        s = pos_prob + neg_prob + neutral_prob
        pos_prob /= s
        neg_prob /= s
        neutral_prob /= s

        score = pos_prob - neg_prob
        return {
            "positive": round(pos_prob, 4),
            "negative": round(neg_prob, 4),
            "neutral": round(neutral_prob, 4),
            "score": round(score, 4),
        }
