"""Fundamental signal generators (structured stubs with real code).

This module provides placeholders for fundamental signals that require
external data (financial statements, analyst estimates, etc.).
Each function has a real implementation that returns a neutral signal
when data is unavailable, making the module safe to import and use.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def pe_ratio_signal(pe_series: pd.Series, undervalued: float = 10.0, overvalued: float = 30.0) -> pd.Series:
    """Signal based on P/E ratio (lower = potentially undervalued).

    Args:
        pe_series: Time series of P/E ratios.
        undervalued: Threshold below which the stock is considered cheap.
        overvalued: Threshold above which the stock is considered expensive.

    Returns:
        pd.Series in ``[-1, 1]`` where ``1`` = buy (cheap), ``-1`` = sell (expensive).
    """
    if pe_series.empty:
        return pd.Series(dtype=float)

    # Map PE to [-1, 1]: low PE -> positive signal
    signal = 1.0 - 2.0 * (pe_series - undervalued) / (overvalued - undervalued)
    signal = np.clip(signal, -1.0, 1.0)
    signal.name = "pe_signal"
    return signal


def earnings_growth_signal(earnings_growth: pd.Series, threshold: float = 0.15) -> pd.Series:
    """Signal based on year-over-year earnings growth.

    Args:
        earnings_growth: YoY earnings growth rates.
        threshold: Growth rate above which signal is positive.

    Returns:
        pd.Series in ``[0, 1]``.
    """
    if earnings_growth.empty:
        return pd.Series(dtype=float)

    signal = np.clip(earnings_growth / threshold, 0.0, 1.0)
    signal.name = "earnings_growth"
    return signal


def debt_to_equity_signal(de_ratio: pd.Series, threshold: float = 1.0) -> pd.Series:
    """Signal based on debt-to-equity ratio (lower is better).

    Args:
        de_ratio: Debt-to-equity ratio series.
        threshold: D/E above this is considered risky.

    Returns:
        pd.Series in ``[-1, 1]`` where positive = low debt (good).
    """
    if de_ratio.empty:
        return pd.Series(dtype=float)

    signal = 1.0 - 2.0 * np.clip(de_ratio / threshold, 0.0, 1.0)
    signal.name = "de_signal"
    return signal


def roe_signal(roe_series: pd.Series, good_threshold: float = 0.15) -> pd.Series:
    """Signal based on Return on Equity.

    Args:
        roe_series: ROE time series.
        good_threshold: ROE above this is considered good.

    Returns:
        pd.Series in ``[0, 1]``.
    """
    if roe_series.empty:
        return pd.Series(dtype=float)

    signal = np.clip(roe_series / good_threshold, 0.0, 1.0)
    signal.name = "roe_signal"
    return signal


class FundamentalSignalAdapter:
    """Adapter that wraps fundamental functions to conform to the Signal ABC.

    Since fundamental data is usually lower-frequency than price data,
    this adapter forward-fills the signal to match a price index.
    """

    def __init__(self, signal_func, name: str) -> None:
        self.signal_func = signal_func
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def generate(self, data: pd.DataFrame) -> pd.Series:
        """Generate signal - returns neutral if no fundamental data available."""
        logger.debug("Fundamental signal %s requires external data; returning neutral.", self._name)
        return pd.Series(0.5, index=data.index, name=self._name)
