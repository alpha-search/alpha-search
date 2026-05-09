"""Technical indicator signal generators (vectorized)."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def momentum(prices: pd.Series, window: int = 20) -> pd.Series:
    """Returns-based momentum signal.

    Computes the cumulative return over the look-back *window* and
    normalises to ``[0, 1]`` via a softmax-like squashing.

    Args:
        prices: Price series (typically Close).
        window: Look-back period in trading days.

    Returns:
        pd.Series of signal values in ``[0, 1]``.
    """
    if len(prices) < window + 1:
        return pd.Series(np.nan, index=prices.index, name="momentum")

    # Cumulative return over the window
    cum_ret = prices.pct_change(window)

    # Squash to [0, 1] via sigmoid
    signal = 1.0 / (1.0 + np.exp(-cum_ret * 10))
    signal.name = "momentum"
    return signal


def ma_crossover(
    prices: pd.Series,
    short: int = 20,
    long: int = 50,
) -> pd.Series:
    """Moving-average crossover signal.

    Returns ``1.0`` when the short MA is above the long MA,
    ``0.0`` otherwise.

    Args:
        prices: Price series.
        short: Short moving-average window.
        long: Long moving-average window.

    Returns:
        pd.Series of ``0.0`` / ``1.0`` values.
    """
    if short >= long:
        raise ValueError(f"short ({short}) must be < long ({long})")
    if len(prices) < long:
        return pd.Series(np.nan, index=prices.index, name="ma_crossover")

    ma_short = prices.rolling(window=short).mean()
    ma_long = prices.rolling(window=long).mean()

    signal = (ma_short > ma_long).astype(float)
    signal.name = "ma_crossover"
    return signal


def z_score_mean_reversion(
    returns: pd.Series,
    window: int = 20,
    threshold: float = 2.0,
) -> pd.Series:
    """Z-score mean-reversion signal.

    When the z-score of returns exceeds *threshold* in magnitude,
    a contrarian signal is generated (stronger as z-score grows).

    Args:
        returns: Daily return series.
        window: Rolling look-back for mean / std.
        threshold: Z-score threshold for signal activation.

    Returns:
        pd.Series of signal values in ``[-1, 1]``.
    """
    if len(returns) < window:
        return pd.Series(np.nan, index=returns.index, name="z_score")

    rolling_mean = returns.rolling(window=window).mean()
    rolling_std = returns.rolling(window=window).std()

    z = (returns - rolling_mean) / rolling_std.replace(0, np.nan)

    # Signal: negative z-score -> positive signal (buy the dip)
    #         positive z-score -> negative signal (sell the rip)
    signal = np.clip(-z / threshold, -1.0, 1.0)
    signal.name = "z_score"
    return signal


def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index signal.

    RSI is mapped to a ``[0, 1]`` signal where values below 30
    (oversold) map to ``~1.0`` and values above 70 (overbought)
    map to ``~0.0``.

    Args:
        prices: Price series.
        window: RSI look-back period.

    Returns:
        pd.Series of RSI values in ``[0, 100]``.
    """
    if len(prices) < window + 1:
        return pd.Series(np.nan, index=prices.index, name="rsi")

    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Wilder's smoothing — EMA with alpha = 1 / window
    # This matches the standard RSI calculation and the _rsi()
    # implementation in opportunities/strategies.py
    avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window).mean()

    rs = avg_gain / avg_loss
    rsi_val = 100.0 - (100.0 / (1.0 + rs))
    rsi_val.name = "rsi"
    return rsi_val


def bollinger_band_position(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.Series:
    """Position within Bollinger Bands as a signal.

    Returns a value in ``[0, 1]`` where ``0`` = at the lower band,
    ``1`` = at the upper band, and ``0.5`` = at the middle band.

    Args:
        prices: Price series.
        window: Moving-average window.
        num_std: Number of standard deviations for band width.

    Returns:
        pd.Series in ``[0, 1]``.
    """
    if len(prices) < window:
        return pd.Series(np.nan, index=prices.index, name="bb_position")

    ma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()

    upper = ma + num_std * std
    lower = ma - num_std * std

    band_width = upper - lower
    band_width = band_width.replace(0, np.nan)

    position = (prices - lower) / band_width
    position = np.clip(position, 0.0, 1.0)
    position.name = "bb_position"
    return position
