"""FinBERT-based sentiment analyzer for financial text."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from alpha_search.sentiment.base import SentimentAnalyzer

logger = logging.getLogger(__name__)

# Default model from HuggingFace
_FINBERT_MODEL = "ProsusAI/finbert"


class FinBERTSentimentAnalyzer(SentimentAnalyzer):
    """Sentiment analyzer powered by ProsusAI/finBERT.

    Falls back to a simple keyword-based analyzer if ``transformers``
    is not installed.

    Example::

        analyzer = FinBERTSentimentAnalyzer()
        result = analyzer.analyze("The company reported strong earnings.")
        # {'positive': 0.85, 'negative': 0.05, 'neutral': 0.10, 'score': 0.80}
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or _FINBERT_MODEL
        self._pipeline = None
        self._tokenizer = None
        self._model = None
        self._available = False
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load the FinBERT pipeline."""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

            logger.info("Loading FinBERT model: %s", self.model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self._model,
                tokenizer=self._tokenizer,
            )
            self._available = True
            logger.info("FinBERT model loaded successfully.")
        except ImportError:
            logger.warning(
                "transformers library not installed. "
                "FinBERT will use fallback keyword analysis. "
                "Install with: pip install transformers torch"
            )
            self._available = False
        except Exception as exc:
            logger.warning("Failed to load FinBERT model: %s. Using fallback.", exc)
            self._available = False

    # -- SentimentAnalyzer interface ------------------------------------

    @property
    def name(self) -> str:
        return "finbert"

    def analyze(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of *text*.

        Returns:
            Dict with ``positive``, ``negative``, ``neutral`` probabilities
            and a composite ``score`` in ``[-1, 1]``.
        """
        if not text or not text.strip():
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0, "score": 0.0}

        if self._available and self._pipeline is not None:
            return self._analyze_with_model(text)
        return self._fallback_analyze(text)

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze a batch of texts efficiently."""
        if not texts:
            return []

        if self._available and self._pipeline is not None:
            try:
                results = self._pipeline(texts, truncation=True, max_length=512)
                return [self._parse_pipeline_result(r) for r in results]
            except Exception as exc:
                logger.warning("Batch analysis failed: %s. Falling back to loop.", exc)

        return [self.analyze(t) for t in texts]

    # -- Internal helpers -----------------------------------------------

    def _analyze_with_model(self, text: str) -> Dict[str, float]:
        """Use the loaded FinBERT pipeline."""
        try:
            result = self._pipeline(text, truncation=True, max_length=512)
            return self._parse_pipeline_result(result[0])
        except Exception as exc:
            logger.warning("Model inference failed: %s. Using fallback.", exc)
            return self._fallback_analyze(text)

    def _parse_pipeline_result(self, result) -> Dict[str, float]:
        """Parse the HuggingFace pipeline output to our standard format."""
        # result is like {"label": "positive", "score": 0.95}
        label = result.get("label", "neutral").lower()
        score = result.get("score", 0.5)

        # Map finbert labels to our format
        if label == "positive":
            return {
                "positive": score,
                "negative": (1.0 - score) * 0.3,
                "neutral": (1.0 - score) * 0.7,
                "score": score,
            }
        elif label == "negative":
            return {
                "positive": (1.0 - score) * 0.3,
                "negative": score,
                "neutral": (1.0 - score) * 0.7,
                "score": -score,
            }
        else:  # neutral
            return {
                "positive": (1.0 - score) * 0.5,
                "negative": (1.0 - score) * 0.5,
                "neutral": score,
                "score": 0.0,
            }

    def _fallback_analyze(self, text: str) -> Dict[str, float]:
        """Simple keyword-based fallback when FinBERT is unavailable."""
        text_lower = text.lower()

        positive_words = {
            "strong", "growth", "profit", "gain", "up", "rise", "bullish",
            " outperform", "beat", "exceed", "positive", "optimistic",
            "recovery", "rally", "surge", "boom", "expansion",
        }
        negative_words = {
            "weak", "loss", "decline", "down", "fall", "bearish",
            "underperform", "miss", "below", "negative", "pessimistic",
            "recession", "crash", "drop", "slump", "contraction",
            "risk", "debt", "bankruptcy", "lawsuit", "fraud",
        }

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total = pos_count + neg_count

        if total == 0:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        pos_prob = pos_count / total
        neg_prob = neg_count / total
        neutral_prob = max(0.0, 1.0 - pos_prob - neg_prob)

        # Normalize to sum to 1
        total_prob = pos_prob + neg_prob + neutral_prob
        pos_prob /= total_prob
        neg_prob /= total_prob
        neutral_prob /= total_prob

        score = pos_prob - neg_prob

        return {
            "positive": round(pos_prob, 4),
            "negative": round(neg_prob, 4),
            "neutral": round(neutral_prob, 4),
            "score": round(score, 4),
        }
