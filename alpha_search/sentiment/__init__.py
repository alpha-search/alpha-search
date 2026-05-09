"""Sentiment analysis module for Alpha Search."""

from alpha_search.sentiment.base import SentimentAnalyzer
from alpha_search.sentiment.composite import CompositeSentiment
from alpha_search.sentiment.news import NewsAPISentiment
from alpha_search.sentiment.social import RedditSentiment, SocialSentiment, TwitterSentiment

try:
    from alpha_search.sentiment.finbert import FinBERTSentimentAnalyzer
except ImportError:
    FinBERTSentimentAnalyzer = None  # type: ignore

__all__ = [
    "SentimentAnalyzer",
    "CompositeSentiment",
    "FinBERTSentimentAnalyzer",
    "NewsAPISentiment",
    "SocialSentiment",
    "RedditSentiment",
    "TwitterSentiment",
]
