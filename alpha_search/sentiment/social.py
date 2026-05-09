"""Social media sentiment analyzer (structured stub).

Provides a framework for social-media-based sentiment analysis.
Without actual API credentials, returns neutral sentiment with a
structured interface that can be extended with real data sources
(Twitter/X API, Reddit API, StockTwits, etc.).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from alpha_search.sentiment.base import SentimentAnalyzer

logger = logging.getLogger(__name__)

# Common emoji / keyword mappings for social sentiment
_BULLISH_TERMS = {
    "moon", "rocket", "bullish", "long", "calls", "yolo", "tendies",
    "diamond hands", "hold", "hodl", "buy", "strong", "rally",
    "breakout", "pump", "all in", "undervalued", "gem",
    "🚀", "📈", "🟢", "💎", "🙌", "💪",
}

_BEARISH_TERMS = {
    "bearish", "short", "puts", "crash", "dump", "sell", "panic",
    "weak", "overvalued", "bubble", "recession", "fear", "capitulation",
    "paper hands", "bagholder", "rugpull", "fd", "zero",
    "📉", "🔴", "😱", "💀", "☠️", "🩸",
}


class SocialSentiment(SentimentAnalyzer):
    """Social media sentiment analyzer.

    Analyses text for bullish / bearish social-media language.
    Can be extended to pull live data from Twitter, Reddit, etc.

    Example::

        analyzer = SocialSentiment()
        result = analyzer.analyze("$AAPL to the moon! 🚀 Diamond hands!")
    """

    def __init__(self, platform: Optional[str] = None) -> None:
        self.platform = platform or "generic"

    @property
    def name(self) -> str:
        return f"social_{self.platform}"

    def analyze(self, text: str) -> Dict[str, float]:
        """Analyze social-media text for bullish/bearish sentiment.

        Args:
            text: A social media post or combined text.

        Returns:
            Dict with ``positive``, ``negative``, ``neutral`` probabilities
            and a composite ``score`` in ``[-1, 1]``.
        """
        if not text or not text.strip():
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        text_lower = text.lower()

        pos_count = sum(1 for term in _BULLISH_TERMS if term.lower() in text_lower)
        neg_count = sum(1 for term in _BEARISH_TERMS if term.lower() in text_lower)

        # Also check for emoji patterns
        pos_count += len(re.findall(r"[🚀📈🟢💎🙌💪]", text))
        neg_count += len(re.findall(r"[📉🔴😱💀☠️🩸]", text))

        total = pos_count + neg_count
        if total == 0:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        pos_prob = pos_count / total
        neg_prob = neg_count / total
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

    def analyze_mentions(self, ticker: str, texts: List[str]) -> Dict[str, float]:
        """Aggregate sentiment across multiple social media mentions.

        Args:
            ticker: The ticker symbol being discussed.
            texts: List of social media posts mentioning the ticker.

        Returns:
            Aggregated sentiment dictionary.
        """
        if not texts:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        results = self.batch_analyze(texts)
        avg_score = sum(r["score"] for r in results) / len(results)
        avg_pos = sum(r["positive"] for r in results) / len(results)
        avg_neg = sum(r["negative"] for r in results) / len(results)
        avg_neutral = sum(r["neutral"] for r in results) / len(results)

        return {
            "positive": round(avg_pos, 4),
            "negative": round(avg_neg, 4),
            "neutral": round(avg_neutral, 4),
            "score": round(avg_score, 4),
            "mention_count": len(texts),
        }


class RedditSentiment(SocialSentiment):
    """Reddit-specific sentiment analyzer."""

    def __init__(self) -> None:
        super().__init__(platform="reddit")


class TwitterSentiment(SocialSentiment):
    """Twitter/X-specific sentiment analyzer."""

    def __init__(self) -> None:
        super().__init__(platform="twitter")
