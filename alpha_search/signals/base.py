"""Abstract base class and composition helpers for trading signals."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

import pandas as pd


class Signal(ABC):
    """Abstract base class for quantitative signals.

    Signals support boolean composition via ``&`` (AND), ``|`` (OR),
    and ``~`` (invert / NOT) operators.

    Subclasses must implement ``name`` (property) and ``generate`` (method).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable signal name."""
        ...

    @abstractmethod
    def generate(self, data: pd.DataFrame) -> pd.Series:
        """Generate a signal from price data.

        Args:
            data: OHLCV DataFrame with standard columns.

        Returns:
            pd.Series of signal values indexed like *data*.
        """
        ...

    # Composition operators ------------------------------------------------

    def __and__(self, other: "Signal") -> "CompositeSignal":
        """Logical AND of two signals (both must fire)."""
        return CompositeSignal("AND", self, other, lambda a, b: a & b)

    def __or__(self, other: "Signal") -> "CompositeSignal":
        """Logical OR of two signals (either fires)."""
        return CompositeSignal("OR", self, other, lambda a, b: a | b)

    def __invert__(self) -> "CompositeSignal":
        """Logical NOT (invert) of a signal."""
        return CompositeSignal("NOT", self, None, lambda a, _: ~a.astype(bool))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class CompositeSignal(Signal):
    """A signal built by combining two signals with a binary operator."""

    def __init__(
        self,
        op_name: str,
        left: Signal,
        right: Signal | None,
        operator: Callable,
    ) -> None:
        self._op_name = op_name
        self._left = left
        self._right = right
        self._operator = operator

    @property
    def name(self) -> str:
        if self._op_name == "NOT":
            return f"NOT({self._left.name})"
        return f"({self._left.name} {self._op_name} {self._right.name if self._right else '?'})"

    def generate(self, data: pd.DataFrame) -> pd.Series:
        left_vals = self._left.generate(data)
        if self._right is None:
            result = self._operator(left_vals, None)
        else:
            right_vals = self._right.generate(data)
            aligned_l, aligned_r = left_vals.align(right_vals, join="inner")
            result = self._operator(aligned_l, aligned_r)
        return pd.Series(result, index=left_vals.index, name=self.name)


# Convenience: wrap a pure function as a Signal ---------------------------

class FuncSignal(Signal):
    """Wrap a pure function as a :class:`Signal`."""

    def __init__(
        self,
        name: str,
        func: Callable[[pd.DataFrame], pd.Series],
    ) -> None:
        self._name = name
        self._func = func

    @property
    def name(self) -> str:
        return self._name

    def generate(self, data: pd.DataFrame) -> pd.Series:
        return self._func(data)


def compose_and(a: pd.Series, b: pd.Series) -> pd.Series:
    """Element-wise AND of two signals."""
    return (a & b).astype(int)


def compose_or(a: pd.Series, b: pd.Series) -> pd.Series:
    """Element-wise OR of two signals."""
    return (a | b).astype(int)
