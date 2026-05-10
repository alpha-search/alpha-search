"""Noise area / volatility breakout signal engine for intraday momentum trading.

A "noise area" is a volatility-defined trading range that captures random
intraday fluctuations.  Breakouts above the upper boundary signal long
momentum; breakouts below the lower boundary signal short momentum.
Re-entering the noise area signals the end of the momentum burst.

Designed for Indian ETFs (e.g., NIFTYBEES, SETFNIF50) but applicable to
any instrument with OHLC data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

__all__ = [
    "NoiseArea",
    "compute_noise_area",
    "generate_breakout_signals",
    "volatility_targeted_position",
    "trailing_stop_signal",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class NoiseArea:
    """Container for noise-area boundaries and metadata.

    Attributes:
        upper: Upper noise boundary (rolling high + ATR * multiplier).
        lower: Lower noise boundary (rolling low - ATR * multiplier).
        center: Centre line (rolling mean of close prices).
        atr: Average True Range series used in the calculation.
        lookback: Look-back window in trading days.
    """

    upper: pd.Series
    lower: pd.Series
    center: pd.Series
    atr: pd.Series
    lookback: int


# ---------------------------------------------------------------------------
# Core noise-area computation
# ---------------------------------------------------------------------------


def _compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int,
) -> pd.Series:
    """Vectorised Average True Range (ATR).

    True Range is the maximum of:
    * |high - low|
    * |high - prev_close|
    * |low  - prev_close|

    ATR is the rolling mean of True Range over *window* periods.

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        window: Rolling look-back window.

    Returns:
        pd.Series of ATR values.
    """
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=window, min_periods=window).mean()
    atr.name = "atr"
    return atr


def compute_noise_area(
    prices: pd.DataFrame,
    lookback: int = 20,
    atr_multiplier: float = 1.5,
) -> NoiseArea:
    """Compute the noise-area boundaries for volatility breakout signals.

    The noise area is anchored on the rolling high/low over *lookback*
    periods, expanded by ATR * *atr_multiplier* on each side.

    Args:
        prices: OHLC DataFrame with columns ``open``, ``high``, ``low``,
            ``close`` (column names are case-insensitive).
        lookback: Rolling window length in trading days.
        atr_multiplier: Multiplier applied to ATR to widen the noise bands.

    Returns:
        :class:`NoiseArea` dataclass containing the upper, lower, centre,
        and ATR series.

    Raises:
        ValueError: If *lookback* < 2 or required OHLC columns are missing.
    """
    if lookback < 2:
        raise ValueError(f"lookback ({lookback}) must be >= 2")

    # Normalise column names to lower-case for robustness
    prices = prices.rename(columns=lambda c: c.lower().strip())

    required = {"high", "low", "close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    high = prices["high"]
    low = prices["low"]
    close = prices["close"]

    # Rolling high / low over the look-back window (shifted by 1 so the
    # current bar is evaluated against the noise area established from
    # prior bars only -- prevents look-ahead bias).
    rolling_high = high.rolling(window=lookback, min_periods=lookback).max().shift(1)
    rolling_low = low.rolling(window=lookback, min_periods=lookback).min().shift(1)

    # Centre = rolling mean of close (also shifted to avoid look-ahead)
    center = close.rolling(window=lookback, min_periods=lookback).mean().shift(1)

    # ATR (computed on full window, then shifted)
    atr = _compute_atr(high, low, close, lookback).shift(1)

    # Noise boundaries
    band = atr * atr_multiplier
    upper = rolling_high + band
    lower = rolling_low - band

    upper.name = "noise_upper"
    lower.name = "noise_lower"
    center.name = "noise_center"

    return NoiseArea(
        upper=upper,
        lower=lower,
        center=center,
        atr=atr,
        lookback=lookback,
    )


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


def generate_breakout_signals(
    noise_area: NoiseArea,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    """Generate long / short breakout signals from the noise area.

    A long signal (+1) is triggered when the close price breaks **above**
    the upper noise boundary.  A short signal (-1) is triggered when the
    close breaks **below** the lower boundary.  When price sits inside the
    noise area the signal is 0.

    Args:
        noise_area: Pre-computed :class:`NoiseArea` instance.
        prices: OHLC DataFrame (column names case-insensitive).  Only
            the ``close`` column is used.

    Returns:
        pd.DataFrame with columns:
        * ``long_signal``   -- +1 on upper breakout, 0 otherwise.
        * ``short_signal``  -- -1 on lower breakout, 0 otherwise.
        * ``combined_signal`` -- ``long_signal + short_signal``.
        * ``in_noise``      -- 1 when close is between bands, 0 otherwise.
    """
    prices = prices.rename(columns=lambda c: c.lower().strip())
    if "close" not in prices.columns:
        raise ValueError("prices DataFrame must contain a 'close' column")

    close = prices["close"]

    long_signal = (close > noise_area.upper).astype(float)
    short_signal = -(close < noise_area.lower).astype(float)
    combined_signal = long_signal + short_signal

    in_noise = (
        (close >= noise_area.lower) & (close <= noise_area.upper)
    ).astype(float)

    return pd.DataFrame(
        {
            "long_signal": long_signal,
            "short_signal": short_signal,
            "combined_signal": combined_signal,
            "in_noise": in_noise,
        },
        index=close.index,
    )


# ---------------------------------------------------------------------------
# Volatility-targeted position sizing
# ---------------------------------------------------------------------------


def volatility_targeted_position(
    signal: pd.Series,
    returns: pd.Series,
    target_vol: float = 0.01,
    vol_lookback: int = 60,
) -> pd.Series:
    """Scale position size so realised volatility matches a target.

    Position is computed as:
        ``position = signal * target_vol / (rolling_vol * sqrt(252))``

    where *rolling_vol* is the annualised standard deviation of *returns*
    over *vol_lookback* periods.  The result is clipped to ``[-3.0, 3.0]``
    (maximum 3x leverage).  Positions are forced to 0 wherever the input
    *signal* is 0.

    Args:
        signal: Raw signal series (e.g. ``combined_signal`` from
            :func:`generate_breakout_signals`).
        returns: Daily (or bar) return series aligned with *signal*.
        target_vol: Target annualised volatility (e.g. 0.01 = 1%%).
        vol_lookback: Rolling window for realised-volatility estimation.

    Returns:
        pd.Series of position sizes.
    """
    if vol_lookback < 2:
        raise ValueError(f"vol_lookback ({vol_lookback}) must be >= 2")

    # Rolling realised volatility (annualised)
    rolling_vol = returns.rolling(window=vol_lookback, min_periods=vol_lookback).std()
    annualised_vol = rolling_vol * np.sqrt(252)

    # Avoid divide-by-zero: replace 0 vol with NaN so position becomes NaN
    safe_vol = annualised_vol.replace(0, np.nan)

    raw_position = target_vol / safe_vol
    raw_position = np.clip(raw_position, -3.0, 3.0)

    # Apply signal direction & magnitude; zero signal -> zero position
    position = raw_position * signal
    position = position.where(signal != 0, 0.0)
    position.name = "vol_targeted_position"
    return position


# ---------------------------------------------------------------------------
# Trailing stop
# ---------------------------------------------------------------------------


def trailing_stop_signal(
    prices: pd.Series,
    entry_price: pd.Series,
    current_signal: pd.Series,
    trailing_pct: float = 0.05,
) -> pd.Series:
    """Generate a stop-exit signal based on trailing stop logic.

    For **long** positions (signal > 0): exit (return 0) when price drops
    more than *trailing_pct* from the maximum price observed **since entry**.

    For **short** positions (signal < 0): exit (return 0) when price rises
    more than *trailing_pct* from the minimum price observed **since entry**.

    The function is fully vectorised and uses a forward-scan via
    ``pd.Series.cummax`` / ``cummin`` on mask-grouped data.

    Args:
        prices: Close price series.
        entry_price: Price at which the current position was entered.
            Aligned index with *prices*.
        current_signal: Current position signal (+1 long, -1 short, 0 flat).
            Aligned index with *prices*.
        trailing_pct: Trailing stop percentage (e.g. 0.05 = 5%%).

    Returns:
        pd.Series of stop signals where 1 = keep position, 0 = stop triggered.
    """
    if not (0 < trailing_pct < 1):
        raise ValueError(f"trailing_pct ({trailing_pct}) must be in (0, 1)")

    # --- Long trailing stop ---
    long_mask = current_signal > 0

    # Block-id: contiguous stretches where long_mask is True
    block_id = long_mask.ne(long_mask.shift(1)).cumsum()
    long_blocks = long_mask.astype(int) * block_id

    # Grouped cummax within each long block
    running_max = (
        prices.where(long_mask)
        .groupby(long_blocks.replace(0, np.nan))
        .cummax()
        .reindex(prices.index)
    )

    long_stop_triggered = prices < (running_max * (1.0 - trailing_pct))
    long_stop_triggered = long_stop_triggered.where(long_mask, False)

    # Once a stop triggers, all subsequent periods in that block are also stopped
    long_stopped = long_stop_triggered.groupby(long_blocks.replace(0, np.nan)).cummax()
    long_stopped = pd.Series(np.where(long_stopped.isna(), False, long_stopped.astype(bool)),
                              index=long_stopped.index, dtype=bool)

    long_keep = long_mask & (~long_stopped)

    # --- Short trailing stop ---
    short_mask = current_signal < 0
    short_block_id = short_mask.ne(short_mask.shift(1)).cumsum()
    short_blocks = short_mask.astype(int) * short_block_id

    running_min = (
        prices.where(short_mask)
        .groupby(short_blocks.replace(0, np.nan))
        .cummin()
        .reindex(prices.index)
    )

    short_stop_triggered = prices > (running_min * (1.0 + trailing_pct))
    short_stop_triggered = short_stop_triggered.where(short_mask, False)

    short_stopped = short_stop_triggered.groupby(short_blocks.replace(0, np.nan)).cummax()
    short_stopped = pd.Series(np.where(short_stopped.isna(), False, short_stopped.astype(bool)),
                               index=short_stopped.index, dtype=bool)

    short_keep = short_mask & (~short_stopped)

    # --- Combine ---
    keep_signal = (long_keep | short_keep).astype(float)
    keep_signal.name = "trailing_stop"
    return keep_signal
