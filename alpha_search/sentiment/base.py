"""Abstract base class for sentiment analyzers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List


class SentimentAnalyzer(ABC):
    """Abstract base class for sentiment analysis engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable analyzer name."""
        ...

    @abstractmethod
    def analyze(self, text: str) -> Dict[str, float]:
        """Analyze the sentiment of a single text.

        Returns:
            Dictionary with keys ``positive``, ``negative``, ``neutral``
            (probabilities summing to 1.0) and ``score`` in ``[-1, 1]``.
        """
        ...

    def batch_analyze(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze a batch of texts.

        The default implementation loops over *texts*. Override for
        vectorized or parallel processing.
        """
        return [self.analyze(t) for t in texts]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
