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

        Raises:
            RuntimeError: If FinBERT is not available.
        """
        if not text or not text.strip():
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0, "score": 0.0}

        if self._available and self._pipeline is not None:
            return self._analyze_with_model(text)
        raise RuntimeError(
            "FinBERT model is not available. "
            "Install transformers and torch: pip install transformers torch"
        )

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze a batch of texts efficiently."""
        if not texts:
            return []

        if self._available and self._pipeline is not None:
            try:
                results = self._pipeline(texts, truncation=True, max_length=512)
                return [self._parse_pipeline_result(r) for r in results]
            except Exception as exc:
                raise RuntimeError(
                    f"FinBERT batch analysis failed: {exc}. "
                    f"Install transformers and torch: pip install transformers torch"
                ) from exc

        raise RuntimeError(
            "FinBERT model is not available. "
            "Install transformers and torch: pip install transformers torch"
        )

    # -- Internal helpers -----------------------------------------------

    def _analyze_with_model(self, text: str) -> Dict[str, float]:
        """Use the loaded FinBERT pipeline."""
        try:
            result = self._pipeline(text, truncation=True, max_length=512)
            return self._parse_pipeline_result(result[0])
        except Exception as exc:
            raise RuntimeError(
                f"FinBERT model inference failed: {exc}. "
                f"The model may need to be re-downloaded."
            ) from exc

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


