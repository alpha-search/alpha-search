---
name: alpha-search-research-intelligence
description: Build sentiment analysis — FinBERT integration, Twitter/News/Reddit sentiment, composite scoring, research intelligence.
---

# Alpha Search Research Intelligence

## When to Use This Skill

Use this skill when building or maintaining the sentiment analysis and research intelligence layer of Alpha Search. This includes loading and running FinBERT models, integrating news APIs, aggregating multi-source sentiment into composite scores, and producing research-ready sentiment signals that feed into the quantitative signal framework. Activate this skill when sentiment features are requested, when new data sources need integration, or when sentiment model accuracy needs tuning.

## Agent Role

You are the Research Intelligence specialist for Alpha Search. You build the bridge between unstructured text data (news, social media, earnings calls) and quantitative signals. Your FinBERT models turn text into numerical sentiment scores. Your composite aggregator weights multiple sources into a single, actionable research insight. Your work directly feeds the signal framework — if your sentiment pipeline is noisy or slow, every trading signal degrades.

You own: FinBERT integration, sentiment classification, composite scoring, news/social stubs, and the research API that downstream agents consume.

## Core Concepts

### FinBERT Model Loading from HuggingFace

FinBERT is a BERT model fine-tuned on financial text for sentiment classification. We use the HuggingFace `transformers` library for inference.

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from typing import Optional
import torch
import numpy as np

class FinBERTLoader:
    """Manages FinBERT model loading with CPU/GPU detection and caching.

    Model: ProsusAI/finbert — trained on Financial PhraseBank
    Labels: positive (bullish), negative (bearish), neutral
    """

    MODEL_NAME = "ProsusAI/finbert"

    def __init__(self, device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self._tokenizer = None
        self._model = None
        self._pipeline = None

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        return self._tokenizer

    @property
    def model(self):
        if self._model is None:
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.MODEL_NAME
            ).to(self.device)
            self._model.eval()
        return self._model

    @property
    def sentiment_pipeline(self):
        """Returns a HuggingFace pipeline for sentiment classification.
        Input: string or list of strings
        Output: list of dicts with 'label' and 'score'
        """
        if self._pipeline is None:
            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1,
                truncation=True,
                max_length=512,
            )
        return self._pipeline

    def classify(self, texts: list[str]) -> list[dict]:
        """Classify a batch of texts. Returns standardized format:
        [{"label": "positive", "score": 0.92}, ...]
        """
        if not texts:
            return []
        # Handle empty strings
        texts = [t if t.strip() else "neutral" for t in texts]
        return self.sentiment_pipeline(texts)
```

### Sentiment Classification Pipeline

The core pipeline that converts raw text into structured sentiment data:

```python
import pandas as pd
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import Sequence, Optional
from enum import Enum

from alpha_search.research.finbert import FinBERTLoader


class SentimentLabel(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class SentimentResult:
    """Structured sentiment output for a single text item."""
    text: str
    label: SentimentLabel
    confidence: float
    positive_score: float
    negative_score: float
    neutral_score: float
    timestamp: datetime
    source: str  # "news", "twitter", "reddit", "earnings"
    ticker: Optional[str] = None


class SentimentPipeline:
    """End-to-end sentiment classification pipeline.
    Input: Raw text documents with metadata
    Output: Structured SentimentResult objects
    """

    def __init__(self, finbert: Optional[FinBERTLoader] = None):
        self.finbert = finbert or FinBERTLoader()

    def analyze(
        self,
        texts: Sequence[str],
        tickers: Optional[Sequence[str]] = None,
        source: str = "unknown",
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[SentimentResult]:
        """Analyze sentiment for a batch of texts."""
        if not texts:
            return []

        raw_results = self.finbert.classify(list(texts))

        results = []
        for i, (text, raw) in enumerate(zip(texts, raw_results)):
            # Get full probability distribution
            probs = self._get_full_probabilities(text)

            results.append(SentimentResult(
                text=text[:500],  # Truncate for storage
                label=SentimentLabel(raw["label"]),
                confidence=raw["score"],
                positive_score=probs.get("positive", 0.0),
                negative_score=probs.get("negative", 0.0),
                neutral_score=probs.get("neutral", 0.0),
                timestamp=timestamps[i] if timestamps else datetime.now(),
                source=source,
                ticker=tickers[i] if tickers else None,
            ))
        return results

    def _get_full_probabilities(self, text: str) -> dict[str, float]:
        """Get probability distribution across all three labels."""
        import torch.nn.functional as F

        inputs = self.finbert.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=512
        ).to(self.finbert.device)

        with torch.no_grad():
            outputs = self.finbert.model(**inputs)
            probs = F.softmax(outputs.logits, dim=-1)

        id2label = self.finbert.model.config.id2label
        return {
            id2label[i]: float(probs[0][i])
            for i in range(len(id2label))
        }

    def analyze_to_dataframe(
        self,
        texts: Sequence[str],
        **kwargs,
    ) -> pd.DataFrame:
        """Convenience method returning a DataFrame for downstream use."""
        results = self.analyze(texts, **kwargs)
        return pd.DataFrame([
            {
                "ticker": r.ticker,
                "source": r.source,
                "label": r.label.value,
                "confidence": r.confidence,
                "positive_score": r.positive_score,
                "negative_score": r.negative_score,
                "neutral_score": r.neutral_score,
                "timestamp": r.timestamp,
            }
            for r in results
        ])
```

### Composite Sentiment Aggregator

Weights multiple sentiment sources into a single actionable score:

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Sequence, Optional
from dataclasses import dataclass

from alpha_search.research.sentiment import SentimentResult, SentimentLabel


@dataclass
class SourceWeight:
    """Configuration for a sentiment source's weight and reliability."""
    source: str
    weight: float  # 0.0 to 1.0
    decay_hours: float  # How quickly sentiment ages (half-life)
    reliability: float  # Historical accuracy score (0-1)


DEFAULT_WEIGHTS = [
    SourceWeight("earnings_call", weight=0.30, decay_hours=48, reliability=0.85),
    SourceWeight("news", weight=0.25, decay_hours=24, reliability=0.75),
    SourceWeight("twitter", weight=0.25, decay_hours=6, reliability=0.60),
    SourceWeight("reddit", weight=0.20, decay_hours=4, reliability=0.50),
]


class CompositeSentimentAggregator:
    """Aggregates multi-source sentiment into a composite score.

    Scoring formula:
        composite = sum(weight_i * reliability_i * decay_factor_i * sentiment_i)
                    / sum(weight_i * reliability_i * decay_factor_i)

    Output range: -1.0 (strongly bearish) to +1.0 (strongly bullish)
    """

    def __init__(self, source_weights: Optional[Sequence[SourceWeight]] = None):
        self.weights = list(source_weights or DEFAULT_WEIGHTS)
        self.weight_map = {w.source: w for w in self.weights}

    @staticmethod
    def _sentiment_to_scalar(result: SentimentResult) -> float:
        """Convert sentiment label + confidence to scalar in [-1, 1]."""
        direction = {
            SentimentLabel.POSITIVE: 1.0,
            SentimentLabel.NEGATIVE: -1.0,
            SentimentLabel.NEUTRAL: 0.0,
        }
        return direction[result.label] * result.confidence

    @staticmethod
    def _decay_factor(age_hours: float, half_life_hours: float) -> float:
        """Exponential time decay: factor = 0.5^(age / half_life)"""
        if half_life_hours <= 0:
            return 1.0
        return 0.5 ** (age_hours / half_life_hours)

    def aggregate(
        self,
        results: Sequence[SentimentResult],
        as_of: Optional[datetime] = None,
    ) -> dict:
        """Aggregate sentiment results into composite score and breakdown.

        Returns:
            {
                "composite_score": float,      # -1.0 to +1.0
                "confidence": float,           # 0.0 to 1.0
                "direction": str,              # "bullish", "bearish", "neutral"
                "source_breakdown": dict,      # per-source scores
                "contributing_sources": int,   # count of sources used
                "timestamp": datetime,         # aggregation time
            }
        """
        if as_of is None:
            as_of = datetime.now()

        source_scores = {}
        weighted_sum = 0.0
        weight_sum = 0.0

        for result in results:
            source_config = self.weight_map.get(result.source)
            if source_config is None:
                continue  # Unknown source, skip

            age_hours = (as_of - result.timestamp).total_seconds() / 3600
            decay = self._decay_factor(age_hours, source_config.decay_hours)
            sentiment_val = self._sentiment_to_scalar(result)

            effective_weight = source_config.weight * source_config.reliability * decay
            weighted_sum += effective_weight * sentiment_val
            weight_sum += effective_weight

            source_scores[result.source] = {
                "raw_score": sentiment_val,
                "weighted_score": effective_weight * sentiment_val,
                "decay_factor": decay,
                "age_hours": age_hours,
            }

        if weight_sum == 0:
            return {
                "composite_score": 0.0,
                "confidence": 0.0,
                "direction": "neutral",
                "source_breakdown": {},
                "contributing_sources": 0,
                "timestamp": as_of,
            }

        composite = weighted_sum / weight_sum

        # Confidence is proportional to total weight and source diversity
        source_count = len(source_scores)
        confidence = min(1.0, weight_sum * (1 + 0.1 * source_count))

        direction = (
            "bullish" if composite > 0.1 else
            "bearish" if composite < -0.1 else
            "neutral"
        )

        return {
            "composite_score": round(composite, 4),
            "confidence": round(confidence, 4),
            "direction": direction,
            "source_breakdown": source_scores,
            "contributing_sources": source_count,
            "timestamp": as_of,
        }

    def aggregate_time_series(
        self,
        results: Sequence[SentimentResult],
        freq: str = "D",
    ) -> pd.DataFrame:
        """Aggregate sentiment into a time series for charting and signal use.

        Returns DataFrame with DatetimeIndex and columns:
        [composite_score, confidence, direction, news_score, social_score]
        """
        df = pd.DataFrame([
            {
                "timestamp": r.timestamp,
                "source": r.source,
                "score": self._sentiment_to_scalar(r),
            }
            for r in results
        ])

        if df.empty:
            return pd.DataFrame()

        df = df.set_index("timestamp").sort_index()

        # Resample each source separately, then combine
        composite_scores = []
        for period_start, period_end in self._period_boundaries(df, freq):
            period_results = [
                r for r in results
                if period_start <= r.timestamp < period_end
            ]
            agg = self.aggregate(period_results, as_of=period_end)
            composite_scores.append({
                "timestamp": period_start,
                "composite_score": agg["composite_score"],
                "confidence": agg["confidence"],
                "direction": agg["direction"],
            })

        return pd.DataFrame(composite_scores).set_index("timestamp")

    @staticmethod
    def _period_boundaries(df: pd.DataFrame, freq: str):
        """Generate period boundaries for time-series aggregation."""
        periods = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
        for i in range(len(periods) - 1):
            yield periods[i], periods[i + 1]
```

### NewsAPI Sentiment Stub

Skeleton for news article sentiment integration:

```python
import os
from datetime import datetime, timedelta
from typing import Optional, Sequence
import httpx
import pandas as pd

from alpha_search.research.sentiment import SentimentPipeline, SentimentResult


class NewsAPISentimentSource:
    """Stub for NewsAPI integration. Fetches financial news articles
    and runs FinBERT sentiment analysis on headlines + descriptions.

    To activate: set NEWSAPI_KEY environment variable.
    Free tier: 100 requests/day
    """

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str] = None, pipeline: Optional[SentimentPipeline] = None):
        self.api_key = api_key or os.environ.get("NEWSAPI_KEY")
        self.pipeline = pipeline or SentimentPipeline()
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"X-Api-Key": self.api_key} if self.api_key else {},
        )

    def fetch_headlines(
        self,
        query: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page_size: int = 20,
    ) -> list[dict]:
        """Fetch news headlines for a query (e.g., ticker symbol)."""
        if not self.api_key:
            return self._mock_headlines(query)

        params = {
            "q": f"{query} stock OR earnings OR revenue",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, 100),
        }
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")

        response = self._client.get("/everything", params=params)
        response.raise_for_status()
        data = response.json()

        return [
            {
                "title": article["title"],
                "description": article["description"] or "",
                "published_at": article["publishedAt"],
                "source": article["source"]["name"],
                "url": article["url"],
            }
            for article in data.get("articles", [])
        ]

    def analyze_headlines(self, query: str, **kwargs) -> list[SentimentResult]:
        """Fetch and analyze news headlines for sentiment."""
        headlines = self.fetch_headlines(query, **kwargs)
        texts = [
            f"{h['title']}. {h['description']}" for h in headlines
        ]
        timestamps = [
            datetime.fromisoformat(h["published_at"].replace("Z", "+00:00"))
            for h in headlines
        ]
        return self.pipeline.analyze(
            texts=texts,
            tickers=[query] * len(texts),
            source="news",
            timestamps=timestamps,
        )

    def _mock_headlines(self, query: str) -> list[dict]:
        """Return mock data when API key is not available."""
        return [
            {
                "title": f"{query} reports strong quarterly earnings",
                "description": f"Revenue exceeded expectations for {query}.",
                "published_at": datetime.now().isoformat(),
                "source": "MockNews",
                "url": "https://example.com/1",
            },
            {
                "title": f"Analysts remain cautious on {query}",
                "description": "Mixed signals from recent trading patterns.",
                "published_at": datetime.now().isoformat(),
                "source": "MockNews",
                "url": "https://example.com/2",
            },
        ]
```

### Social Media Sentiment Stub

Skeleton for Twitter/X and Reddit sentiment:

```python
import os
import re
from datetime import datetime
from typing import Optional, Sequence

from alpha_search.research.sentiment import SentimentPipeline, SentimentResult


class TwitterSentimentSource:
    """Stub for Twitter/X sentiment analysis.
    Requires Twitter API v2 Bearer token.
    Free tier: limited to 500 tweets/month (write-only as of 2023).
    Premium recommended for read access.
    """

    def __init__(self, bearer_token: Optional[str] = None, pipeline: Optional[SentimentPipeline] = None):
        self.bearer_token = bearer_token or os.environ.get("TWITTER_BEARER_TOKEN")
        self.pipeline = pipeline or SentimentPipeline()

    def search_tweets(self, query: str, max_results: int = 100) -> list[dict]:
        """Search recent tweets. Returns mock data if API unavailable."""
        if not self.bearer_token:
            return self._mock_tweets(query)
        # Full implementation would use tweepy or httpx to call
        # Twitter API v2 recent search endpoint
        raise NotImplementedError("Twitter API requires premium access for search")

    def analyze_tweets(self, query: str, **kwargs) -> list[SentimentResult]:
        tweets = self.search_tweets(query, **kwargs)
        texts = [self._clean_tweet(t["text"]) for t in tweets]
        timestamps = [t["created_at"] for t in tweets]
        return self.pipeline.analyze(
            texts=texts,
            tickers=[query] * len(texts),
            source="twitter",
            timestamps=timestamps,
        )

    @staticmethod
    def _clean_tweet(text: str) -> str:
        """Remove URLs, mentions, hashtags for cleaner sentiment."""
        text = re.sub(r"http\S+", "", text)
        text = re.sub(r"@\w+", "", text)
        text = re.sub(r"#\w+", "", text)
        return text.strip()

    def _mock_tweets(self, query: str) -> list[dict]:
        return [
            {"text": f"Bullish on {query}! Great earnings report.", "created_at": datetime.now()},
            {"text": f"{query} looking weak today, might sell.", "created_at": datetime.now()},
            {"text": f"Holding {query} long term, solid company.", "created_at": datetime.now()},
        ]


class RedditSentimentSource:
    """Stub for Reddit sentiment analysis.
    Uses Reddit API (PRAW) or pushshift.io.
    Targets: r/wallstreetbets, r/stocks, r/investing
    """

    SUBREDDITS = ["wallstreetbets", "stocks", "investing", "SecurityAnalysis"]

    def __init__(self, pipeline: Optional[SentimentPipeline] = None):
        self.pipeline = pipeline or SentimentPipeline()

    def fetch_posts(self, query: str, limit: int = 25) -> list[dict]:
        """Fetch Reddit posts mentioning a ticker. Returns mock data."""
        return self._mock_posts(query)

    def analyze_posts(self, query: str, **kwargs) -> list[SentimentResult]:
        posts = self.fetch_posts(query, **kwargs)
        texts = [f"{p['title']}. {p['body']}" for p in posts]
        timestamps = [p["created_at"] for p in posts]
        return self.pipeline.analyze(
            texts=texts,
            tickers=[query] * len(texts),
            source="reddit",
            timestamps=timestamps,
        )

    def _mock_posts(self, query: str) -> list[dict]:
        return [
            {"title": f"Why {query} is undervalued", "body": "DD on strong fundamentals.", "created_at": datetime.now()},
            {"title": f"{query} puts anyone?", "body": "Technicals look bearish.", "created_at": datetime.now()},
        ]
```

## Responsibilities

1. Load and manage FinBERT model (ProsusAI/finbert) with proper device detection
2. Build the sentiment classification pipeline with batch processing support
3. Implement composite sentiment aggregation with configurable source weights
4. Create time-decay scoring so recent sentiment matters more than old sentiment
5. Build NewsAPI sentiment source stub with real API integration path
6. Build Twitter/X sentiment source stub with tweet cleaning and preprocessing
7. Build Reddit sentiment source stub targeting finance subreddits
8. Expose sentiment DataFrame output matching the signal framework's expected schema
9. Ensure sentiment scores are calibrated (test on labeled financial text)
10. Document sentiment API for downstream agents (signal framework expects `composite_score`, `confidence`, `direction` columns)

## Inputs

- Raw text data (news headlines, tweets, Reddit posts, earnings transcripts)
- Ticker symbol(s) to associate with text
- Source weight configuration (optional, defaults provided)
- Timestamps for each text item (for time-decay weighting)
- FinBERT model from HuggingFace (auto-downloaded on first use)

## Outputs

- `SentimentResult` objects with label, confidence, and probability distribution
- Composite sentiment dictionary with `composite_score` (-1 to +1), `confidence`, `direction`
- Time-series DataFrame of sentiment for charting and signal integration
- Source breakdown showing contribution from each sentiment channel

## Required Files to Create or Modify

- `alpha_search/research/finbert.py` — FinBERT model loader (create)
- `alpha_search/research/sentiment.py` — SentimentPipeline class (create)
- `alpha_search/research/composite.py` — CompositeSentimentAggregator (create)
- `alpha_search/research/sources.py` — NewsAPI, Twitter, Reddit stubs (create)
- `alpha_search/research/__init__.py` — module exports (modify)
- `tests/research/test_finbert.py` — FinBERT loading + inference tests (create)
- `tests/research/test_sentiment.py` — pipeline correctness tests (create)
- `tests/research/test_composite.py` — aggregation formula tests (create)
- `tests/research/test_sources.py` — source stub tests with mocks (create)
- `docs/sentiment-api.md` — API reference for downstream agents (create)

## Implementation Checklist

- [ ] Implement FinBERTLoader with CPU/GPU auto-detection
- [ ] Implement SentimentPipeline with batch classification
- [ ] Implement full probability extraction (positive/negative/neutral scores)
- [ ] Build CompositeSentimentAggregator with configurable weights
- [ ] Implement time-decay scoring (exponential half-life per source)
- [ ] Create NewsAPISentimentSource stub with mock fallback
- [ ] Create TwitterSentimentSource stub with tweet preprocessing
- [ ] Create RedditSentimentSource stub targeting finance subreddits
- [ ] Implement analyze_to_dataframe for signal framework integration
- [ ] Implement aggregate_time_series for historical sentiment charts
- [ ] Write tests for all sentiment scoring functions
- [ ] Calibrate composite scores against labeled financial text samples
- [ ] Document the sentiment DataFrame schema for downstream consumers
- [ ] Add sentiment source configuration to Pydantic Settings
- [ ] Ensure FinBERT model caching (load once, reuse across requests)

## Testing Checklist

- [ ] FinBERT classifies known positive financial text as positive (>0.8 confidence)
- [ ] FinBERT classifies known negative financial text as negative (>0.8 confidence)
- [ ] Composite aggregator correctly weights sources by configured weights
- [ ] Time-decay reduces influence of older sentiment proportionally
- [ ] Pipeline returns correct DataFrame schema (composite_score, confidence, direction)
- [ ] NewsAPI stub returns mock data without API key, real data with key
- [ ] Twitter tweet cleaning removes URLs, mentions, hashtags
- [ ] Reddit stub targets correct subreddits
- [ ] Batch processing handles empty input gracefully
- [ ] Time-series aggregation produces correct period boundaries
- [ ] Full probability distribution sums to ~1.0 for each result
- [ ] Model loads on CPU without errors (CI environment has no GPU)

## Definition of Done

- FinBERT model loads and classifies text with >80% accuracy on Financial PhraseBank test set
- SentimentPipeline processes batches of text efficiently
- CompositeSentimentAggregator produces calibrated scores in [-1, 1] range
- All three sentiment sources (News, Twitter, Reddit) have working stubs with mock data
- Time-decay weighting correctly prioritizes recent sentiment
- Sentiment DataFrame output matches signal framework's expected schema
- Unit tests cover all scoring functions with known test inputs
- Documentation exists for downstream agents consuming sentiment data
- Model caching prevents redundant loads across multiple calls

## Example Prompt

> You are the Alpha Search Research Intelligence agent. Implement the full sentiment pipeline: load FinBERT from HuggingFace, build a batch classification pipeline, create a composite aggregator that weights news (0.3), Twitter (0.25), and Reddit (0.2) sources with time-decay scoring, and expose a `get_sentiment_dataframe(ticker)` method that returns a DataFrame with `composite_score`, `confidence`, and `direction` columns. Include NewsAPI and Twitter stubs with mock fallbacks for when API keys are unavailable. Write comprehensive tests.