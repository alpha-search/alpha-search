"""Tests for the sentiment analysis module (FinBERT)."""

from unittest.mock import MagicMock, patch

import pytest

from alpha_search.sentiment.composite import CompositeSentiment
from alpha_search.sentiment.finbert import FinBERTSentimentAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_transformers_pipeline(label: str, score: float) -> MagicMock:
    """Return a mock pipeline that always returns the given label/score."""
    mock = MagicMock()
    mock.return_value = [{"label": label.upper(), "score": score}]
    return mock


def _make_analyzer_with_mock_pipeline(label: str = "positive", score: float = 0.88) -> FinBERTSentimentAnalyzer:
    """Create a FinBERTSentimentAnalyzer with a mocked pipeline (no transformers needed)."""
    mock_pipeline = _mock_transformers_pipeline(label, score)
    analyzer = FinBERTSentimentAnalyzer.__new__(FinBERTSentimentAnalyzer)  # noqa: F841
    analyzer.model_name = "ProsusAI/finbert"
    analyzer._pipeline = mock_pipeline
    analyzer._tokenizer = None
    analyzer._model = None
    analyzer._available = True
    return analyzer


# ---------------------------------------------------------------------------
# FinBERT model loading
# ---------------------------------------------------------------------------


class TestFinBERTLoads:
    """Ensure the sentiment model can be loaded (mocked)."""

    @patch.object(FinBERTSentimentAnalyzer, "_load_model")
    def test_finbert_loads(self, mock_load: MagicMock) -> None:
        """Loading the sentiment analyser calls _load_model once."""
        mock_load.return_value = None
        _ = FinBERTSentimentAnalyzer(model_name="ProsusAI/finbert")  # noqa: F841
        mock_load.assert_called_once()


# ---------------------------------------------------------------------------
# Single-text analysis
# ---------------------------------------------------------------------------


class TestFinBERTAnalyze:
    """Individual text scoring."""

    def test_finbert_analyze(self) -> None:
        """Analyzing text returns a dict with positive, negative, neutral, score keys."""
        analyzer = _make_analyzer_with_mock_pipeline("positive", 0.88)
        result = analyzer.analyze("Apple reports record quarterly revenue.")

        assert isinstance(result, dict)
        assert "positive" in result
        assert "negative" in result
        assert "neutral" in result
        assert "score" in result
        assert result["positive"] > result["negative"]
        assert -1.0 <= result["score"] <= 1.0

    def test_finbert_analyze_empty_text(self) -> None:
        """Empty text returns neutral default."""
        analyzer = _make_analyzer_with_mock_pipeline("positive", 0.88)
        result = analyzer.analyze("")

        assert result["neutral"] > result["positive"]
        assert result["neutral"] > result["negative"]
        assert result["score"] == 0.0

    def test_finbert_batch_analyze(self) -> None:
        """analyze_batch returns a list of results."""
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = [
            {"label": "POSITIVE", "score": 0.90},
            {"label": "NEGATIVE", "score": 0.70},
        ]

        analyzer = FinBERTSentimentAnalyzer.__new__(FinBERTSentimentAnalyzer)  # noqa: F841
        analyzer.model_name = "ProsusAI/finbert"
        analyzer._pipeline = mock_pipeline
        analyzer._tokenizer = None
        analyzer._model = None
        analyzer._available = True

        texts = ["Bullish outlook.", "Bearish signal."]
        results = analyzer.analyze_batch(texts)

        assert len(results) == 2
        for r in results:
            assert "positive" in r
            assert "negative" in r
            assert "neutral" in r
            assert "score" in r


# ---------------------------------------------------------------------------
# Composite / aggregated sentiment
# ---------------------------------------------------------------------------


class TestCompositeSentiment:
    """Weighted aggregation across multiple sources."""

    def test_composite_sentiment(self) -> None:
        """Composite score is a weighted average of individual scores."""
        composite = CompositeSentiment()

        # Mock analyzer that always returns the same score
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {
            "positive": 0.85,
            "negative": 0.05,
            "neutral": 0.10,
            "score": 0.80,
        }

        composite.add_source("mock", mock_analyzer, weight=0.6)
        composite.add_source("mock2", mock_analyzer, weight=0.4)

        result = composite.get_composite("AAPL")

        assert "score" in result
        assert "positive" in result
        assert "negative" in result
        assert "neutral" in result
        assert "sources" in result
        assert "breakdown" in result
        assert result["sources"] == 2
        # Weighted average of identical scores is the same score
        assert result["score"] == pytest.approx(0.80, abs=1e-4)

    def test_composite_empty(self) -> None:
        """Empty composite returns neutral default."""
        composite = CompositeSentiment()
        result = composite.get_composite("AAPL")

        assert result["score"] == 0.0
        assert result["sources"] == 0

    def test_composite_add_source_validation(self) -> None:
        """Duplicate names and negative weights are rejected."""
        composite = CompositeSentiment()
        mock_analyzer = MagicMock()

        composite.add_source("a", mock_analyzer, weight=1.0)

        with pytest.raises(ValueError):
            composite.add_source("a", mock_analyzer, weight=1.0)

        with pytest.raises(ValueError):
            composite.add_source("b", mock_analyzer, weight=-1.0)
