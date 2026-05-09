"""Abstract base classes for Alpha Search plugin architecture."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from alpha_search.core.models import OHLCV, Order, Position


class DataProvider(ABC):
    """Abstract base class for all data providers.

    Concrete providers (YFinanceProvider, BinanceProvider, etc.) must
    implement ``get_prices`` and ``validate_ticker``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...

    @abstractmethod
    def get_prices(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Fetch historical OHLCV prices.

        Args:
            ticker: Symbol / ticker string.
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            DataFrame with columns ``['Open','High','Low','Close','Volume']``
            indexed by a ``DatetimeIndex``.
        """
        ...

    @abstractmethod
    def validate_ticker(self, ticker: str) -> bool:
        """Return ``True`` if *ticker* is recognized by this provider."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class BrokerAdapter(ABC):
    """Abstract base class for broker / execution adapters.

    Paper trading and live broker implementations should subclass this.
    Safety defaults (paper trading) are baked in.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Broker name."""
        ...

    @property
    @abstractmethod
    def is_paper(self) -> bool:
        """True if this adapter runs in paper/simulation mode."""
        ...

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the broker."""
        ...

    @abstractmethod
    def place_order(self, order: Order) -> Dict[str, Any]:
        """Submit an order. Returns fill details dict."""
        ...

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Return current positions keyed by ticker."""
        ...

    @abstractmethod
    def get_account_value(self) -> float:
        """Return total account value."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} paper={self.is_paper}>"


class SentimentAnalyzer(ABC):
    """Abstract base class for sentiment analysis engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Analyzer name."""
        ...

    @abstractmethod
    def analyze(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of a single text.

        Returns:
            Dictionary with keys ``positive``, ``negative``, ``neutral``,
            and ``score`` in range ``[-1, 1]``.
        """
        ...

    def batch_analyze(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze a batch of texts.

        The default implementation simply loops over *texts*.
        Override for vectorized / parallel batch processing.
        """
        return [self.analyze(t) for t in texts]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class Signal(ABC):
    """Abstract base class for quantitative signals.

    Signals support boolean composition via ``&`` (AND), ``|`` (OR),
    and ``~`` (invert) operators.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Signal name."""
        ...

    @abstractmethod
    def generate(self, data: pd.DataFrame) -> pd.Series:
        """Generate signal from price data.

        Args:
            data: OHLCV DataFrame.

        Returns:
            pd.Series of signal values indexed like *data*.
        """
        ...

    def __and__(self, other: "Signal") -> "CompositeSignal":
        """Return a composite signal that is the logical AND of self and other."""
        return CompositeSignal("AND", self, other, lambda a, b: a & b)

    def __or__(self, other: "Signal") -> "CompositeSignal":
        """Return a composite signal that is the logical OR of self and other."""
        return CompositeSignal("OR", self, other, lambda a, b: a | b)

    def __invert__(self) -> "CompositeSignal":
        """Return an inverted (logical NOT) signal."""
        return CompositeSignal("NOT", self, None, lambda a, _: ~a.astype(bool))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class CompositeSignal(Signal):
    """A signal composed from two signals with a binary operator."""

    def __init__(
        self,
        op_name: str,
        left: Signal,
        right: Optional[Signal],
        operator,
    ) -> None:
        self._op_name = op_name
        self._left = left
        self._right = right
        self._operator = operator

    @property
    def name(self) -> str:
        if self._op_name == "NOT":
            return f"~{self._left.name}"
        return f"({self._left.name} {self._op_name} {self._right.name if self._right else ''})"

    def generate(self, data: pd.DataFrame) -> pd.Series:
        left_vals = self._left.generate(data)
        if self._right is None:
            result = self._operator(left_vals, None)
        else:
            right_vals = self._right.generate(data)
            # Align indices
            aligned_l, aligned_r = left_vals.align(right_vals, join="inner")
            result = self._operator(aligned_l, aligned_r)
        return pd.Series(result, index=left_vals.index, name=self.name)
