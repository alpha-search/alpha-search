"""Composite sentiment that aggregates multiple analyzers."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from alpha_search.sentiment.base import SentimentAnalyzer

logger = logging.getLogger(__name__)


class CompositeSentiment:
    """Weighted composite of multiple sentiment analyzers.

    Each analyzer contributes a weighted score in ``[-1, 1]``.
    The composite score is the weighted average, also in ``[-1, 1]``.

    Example::

        composite = CompositeSentiment()
        composite.add_source("finbert", FinBERTSentimentAnalyzer(), weight=0.5)
        composite.add_source("social", SocialSentiment(), weight=0.5)
        result = composite.get_composite("AAPL")
    """

    def __init__(self) -> None:
        self._sources: List[Tuple[str, SentimentAnalyzer, float]] = []

    def add_source(self, name: str, analyzer: SentimentAnalyzer, weight: float = 1.0) -> None:
        """Register a sentiment source with a weight.

        Args:
            name: Identifier for this source.
            analyzer: SentimentAnalyzer instance.
            weight: Relative weight in the composite (default 1.0).

        Raises:
            ValueError: If weight is negative or name already exists.
        """
        if weight < 0:
            raise ValueError(f"Weight must be non-negative, got {weight}")
        existing = [n for n, _, _ in self._sources]
        if name in existing:
            raise ValueError(f"Source '{name}' already registered")
        self._sources.append((name, analyzer, weight))
        logger.info("Added sentiment source: %s (weight=%.2f)", name, weight)

    def get_composite(self, ticker: str) -> Dict[str, float]:
        """Compute weighted composite sentiment for a ticker.

        Args:
            ticker: Ticker symbol or text to analyze.

        Returns:
            Dict with ``score`` (weighted average in ``[-1, 1]``),
            ``positive``, ``negative``, ``neutral`` (average probabilities),
            ``sources`` (number of analyzers used), and a ``breakdown``
            of individual source scores.
        """
        if not self._sources:
            logger.warning("No sentiment sources registered; returning neutral.")
            return {
                "score": 0.0,
                "positive": 0.33,
                "negative": 0.33,
                "neutral": 0.34,
                "sources": 0,
                "breakdown": {},
            }

        total_weight = 0.0
        weighted_score = 0.0
        weighted_pos = 0.0
        weighted_neg = 0.0
        weighted_neutral = 0.0
        breakdown: Dict[str, Dict[str, float]] = {}

        for name, analyzer, weight in self._sources:
            try:
                result = analyzer.analyze(ticker)
                score = result.get("score", 0.0)
                pos = result.get("positive", 0.33)
                neg = result.get("negative", 0.33)
                neutral = result.get("neutral", 0.34)

                weighted_score += score * weight
                weighted_pos += pos * weight
                weighted_neg += neg * weight
                weighted_neutral += neutral * weight
                total_weight += weight

                breakdown[name] = {
                    "score": score,
                    "positive": pos,
                    "negative": neg,
                    "neutral": neutral,
                    "weight": weight,
                }
            except Exception as exc:
                logger.warning("Sentiment source '%s' failed: %s", name, exc)
                breakdown[name] = {"score": 0.0, "error": str(exc), "weight": weight}

        if total_weight == 0:
            return {
                "score": 0.0,
                "positive": 0.33,
                "negative": 0.33,
                "neutral": 0.34,
                "sources": len(self._sources),
                "breakdown": breakdown,
            }

        return {
            "score": round(weighted_score / total_weight, 4),
            "positive": round(weighted_pos / total_weight, 4),
            "negative": round(weighted_neg / total_weight, 4),
            "neutral": round(weighted_neutral / total_weight, 4),
            "sources": len(self._sources),
            "breakdown": breakdown,
        }

    def list_sources(self) -> List[str]:
        """Return a list of registered source names."""
        return [name for name, _, _ in self._sources]

    def remove_source(self, name: str) -> None:
        """Remove a source by name."""
        self._sources = [(n, a, w) for n, a, w in self._sources if n != name]

    def __repr__(self) -> str:
        names = self.list_sources()
        return f"<CompositeSentiment sources={names}>"
