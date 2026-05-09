"""Strategy metrics calculation for Alpha Search research pipelines.

This module contains the core set of performance and risk metrics used
to evaluate trading strategies during the research phase.  All functions
accept either a :class:`pandas.Series` or a :class:`numpy.ndarray` of
daily returns and return scalar or vector results as documented.

Typical usage::

    from alpha_search.research.metrics import compute_all_metrics
    metrics = compute_all_metrics(daily_returns, label="my_strategy")
    print(metrics["sharpe_ratio"])
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_numpy_1d(returns: pd.Series | np.ndarray) -> np.ndarray:
    """Coerce *returns* to a 1-D float64 ndarray, dropping NaNs.

    Parameters
    ----------
    returns:
        Daily return series or array.

    Returns
    -------
    np.ndarray
        1-D array with NaN values removed.
    """
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim == 0:
        arr = arr.reshape(-1)
    elif arr.ndim > 1:
        arr = arr.ravel()
    mask = np.isfinite(arr)
    if not mask.any():
        logger.warning("All input returns are NaN / inf; returning empty array")
    return arr[mask]


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

def total_return(returns: pd.Series | np.ndarray) -> float:
    """Cumulative total return from daily returns.

    Parameters
    ----------
    returns:
        Daily simple returns (e.g. ``0.01`` for +1 %).

    Returns
    -------
    float
        ``prod(1 + r_i) - 1``.  Returns ``np.nan`` when *returns* is
        empty.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0:
        return float(np.nan)
    return float(np.prod(1.0 + r) - 1.0)


def annualized_return(returns: pd.Series | np.ndarray, periods_per_year: int = 252) -> float:
    """Annualized return from daily returns.

    Parameters
    ----------
    returns:
        Daily simple returns.
    periods_per_year:
        Number of trading periods per year (default 252).

    Returns
    -------
    float
        ``(1 + total_return) ** (N / periods_per_year) - 1``.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0 or periods_per_year <= 0:
        return float(np.nan)
    cum = float(np.prod(1.0 + r) - 1.0)
    ann = (1.0 + cum) ** (periods_per_year / r.size) - 1.0
    return float(ann)


def annualized_volatility(returns: pd.Series | np.ndarray, periods_per_year: int = 252) -> float:
    """Annualized volatility from daily returns.

    Uses the sample standard deviation (ddof=1).

    Parameters
    ----------
    returns:
        Daily simple returns.
    periods_per_year:
        Number of trading periods per year (default 252).

    Returns
    -------
    float
        ``std(returns, ddof=1) * sqrt(periods_per_year)``.
    """
    r = _to_numpy_1d(returns)
    if r.size < 2 or periods_per_year <= 0:
        return float(np.nan)
    return float(np.std(r, ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Sharpe ratio from daily returns.

    Parameters
    ----------
    returns:
        Daily simple returns.
    risk_free_rate:
        Annual risk-free rate expressed as a decimal (e.g. ``0.04`` for
        4 %).  Defaults to ``0.0``.
    periods_per_year:
        Number of trading periods per year (default 252).

    Returns
    -------
    float
        ``(annualized_return - risk_free_rate) / annualized_volatility``.
        Returns ``np.nan`` if volatility is zero.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0:
        return float(np.nan)
    ann_ret = annualized_return(r, periods_per_year)
    ann_vol = annualized_volatility(r, periods_per_year)
    if ann_vol == 0.0 or not np.isfinite(ann_vol):
        return float(np.nan)
    return float((ann_ret - risk_free_rate) / ann_vol)


def max_drawdown(returns: pd.Series | np.ndarray) -> float:
    """Maximum drawdown from daily returns.

    Parameters
    ----------
    returns:
        Daily simple returns.

    Returns
    -------
    float
        The maximum peak-to-trough decline expressed as a **negative**
        number (e.g. ``-0.25`` for a 25 % drawdown).  Returns ``0.0``
        for an empty series.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0:
        return 0.0
    cum = np.cumprod(1.0 + r)
    running_max = np.maximum.accumulate(cum)
    drawdowns = cum / running_max - 1.0
    return float(np.min(drawdowns))


def win_rate(returns: pd.Series | np.ndarray) -> float:
    """Percentage of positive return days.

    Parameters
    ----------
    returns:
        Daily simple returns.

    Returns
    -------
    float
        Fraction in ``[0.0, 1.0]``.  Returns ``np.nan`` when *returns*
        is empty.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0:
        return float(np.nan)
    return float(np.mean(r > 0))


def calmar_ratio(
    returns: pd.Series | np.ndarray,
    periods_per_year: int = 252,
) -> float:
    """Calmar ratio = annualized_return / |max_drawdown|.

    Parameters
    ----------
    returns:
        Daily simple returns.
    periods_per_year:
        Number of trading periods per year (default 252).

    Returns
    -------
    float
        Returns ``np.nan`` if max drawdown is zero.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0:
        return float(np.nan)
    ann_ret = annualized_return(r, periods_per_year)
    mdd = max_drawdown(r)
    mdd_abs = abs(mdd)
    if mdd_abs == 0.0:
        return float(np.nan)
    return float(ann_ret / mdd_abs)


def sortino_ratio(
    returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Sortino ratio using downside deviation only.

    Downside deviation is computed on **negative** returns only, using
    a target return of zero.

    Parameters
    ----------
    returns:
        Daily simple returns.
    risk_free_rate:
        Annual risk-free rate (default ``0.0``).
    periods_per_year:
        Number of trading periods per year (default 252).

    Returns
    -------
    float
        ``(annualized_return - risk_free_rate) / downside_deviation``.
    """
    r = _to_numpy_1d(returns)
    if r.size == 0:
        return float(np.nan)
    downside = r[r < 0]
    if downside.size == 0:
        return float(np.nan)
    downside_dev = float(np.std(downside, ddof=1) * np.sqrt(periods_per_year))
    if downside_dev == 0.0:
        return float(np.nan)
    ann_ret = annualized_return(r, periods_per_year)
    return float((ann_ret - risk_free_rate) / downside_dev)


def compute_all_metrics(
    returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    label: str = "",
) -> Dict[str, float]:
    """Compute all standard metrics at once.

    Parameters
    ----------
    returns:
        Daily simple returns.
    risk_free_rate:
        Annual risk-free rate (default ``0.0``).
    periods_per_year:
        Number of trading periods per year (default 252).
    label:
        Optional strategy label prepended to each key as
        ``"{label}_metric_name"``.

    Returns
    -------
    Dict[str, float]
        Dictionary with keys:

        * ``total_return``
        * ``annualized_return``
        * ``annualized_volatility``
        * ``sharpe_ratio``
        * ``max_drawdown``
        * ``win_rate``
        * ``calmar_ratio``
        * ``sortino_ratio``
    """
    r = _to_numpy_1d(returns)
    prefix = f"{label}_" if label else ""

    if r.size == 0:
        logger.warning("compute_all_metrics received empty return series")
        keys = [
            "total_return",
            "annualized_return",
            "annualized_volatility",
            "sharpe_ratio",
            "max_drawdown",
            "win_rate",
            "calmar_ratio",
            "sortino_ratio",
        ]
        return {f"{prefix}{k}": float(np.nan) for k in keys}

    result: Dict[str, float] = {
        f"{prefix}total_return": total_return(r),
        f"{prefix}annualized_return": annualized_return(r, periods_per_year),
        f"{prefix}annualized_volatility": annualized_volatility(r, periods_per_year),
        f"{prefix}sharpe_ratio": sharpe_ratio(r, risk_free_rate, periods_per_year),
        f"{prefix}max_drawdown": max_drawdown(r),
        f"{prefix}win_rate": win_rate(r),
        f"{prefix}calmar_ratio": calmar_ratio(r, periods_per_year),
        f"{prefix}sortino_ratio": sortino_ratio(r, risk_free_rate, periods_per_year),
    }

    logger.debug(
        "Metrics %s-> total_return=%.4f sharpe=%.4f mdd=%.4f",
        f"[{label}] " if label else "",
        result[f"{prefix}total_return"],
        result[f"{prefix}sharpe_ratio"],
        result[f"{prefix}max_drawdown"],
    )
    return result


# ---------------------------------------------------------------------------
# Rolling metrics
# ---------------------------------------------------------------------------

def rolling_volatility(
    prices: pd.Series,
    window: int = 20,
    periods_per_year: int = 252,
) -> pd.Series:
    """Rolling annualized volatility from a price series.

    Parameters
    ----------
    prices:
        Price level series (e.g. adjusted close).  Must have a
        DatetimeIndex for meaningful results.
    window:
        Rolling window size in periods (default 20).
    periods_per_year:
        Annualization factor (default 252).

    Returns
    -------
    pd.Series
        Series of annualized rolling volatility, aligned with *prices*.
        The first *window* values will be ``NaN``.
    """
    if prices.empty:
        logger.warning("rolling_volatility received empty price series")
        return pd.Series(dtype=np.float64, name="vol")
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    returns = prices.pct_change().dropna()
    vol = returns.rolling(window=window, min_periods=window).std() * np.sqrt(periods_per_year)
    vol.name = f"vol_{window}d"
    return vol


def rolling_momentum(prices: pd.Series, window: int = 20) -> pd.Series:
    """Rolling momentum = price / price.shift(window) - 1.

    Parameters
    ----------
    prices:
        Price level series.
    window:
        Look-back window in periods (default 20).

    Returns
    -------
    pd.Series
        Momentum values.  The first *window* entries are ``NaN``.
    """
    if prices.empty:
        logger.warning("rolling_momentum received empty price series")
        return pd.Series(dtype=np.float64, name="mom")
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    mom = prices / prices.shift(window) - 1.0
    mom.name = f"momentum_{window}d"
    return mom


def z_score(prices: pd.Series, window: int = 20) -> pd.Series:
    """Rolling z-score = (price - rolling_mean) / rolling_std.

    Parameters
    ----------
    prices:
        Price level series.
    window:
        Rolling window size in periods (default 20).

    Returns
    -------
    pd.Series
        Z-score values.  The first *window* entries are ``NaN``.
    """
    if prices.empty:
        logger.warning("z_score received empty price series")
        return pd.Series(dtype=np.float64, name="zscore")
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    roll_mean = prices.rolling(window=window, min_periods=window).mean()
    roll_std = prices.rolling(window=window, min_periods=window).std()
    z = (prices - roll_mean) / roll_std
    z.name = f"zscore_{window}d"
    return z


def _calculate_returns_single_ticker(
    ohlcv: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """Return calculations for a single-ticker OHLCV DataFrame.

    Parameters
    ----------
    ohlcv:
        DataFrame with columns ``['open', 'high', 'low', 'close',
        'volume']`` (case-insensitive) and a DatetimeIndex.
    ticker:
        Ticker symbol to use in the output column level.

    Returns
    -------
    pd.DataFrame
        DataFrame with MultiIndex columns ``(ticker, field)``.
    """
    cols = {c.lower(): c for c in ohlcv.columns}
    close_col = cols.get("close", cols.get("adj close", cols.get("adj_close", "close")))
    close = ohlcv[close_col]

    simple_ret = close.pct_change()
    log_ret = np.log(close / close.shift(1))

    data: Dict[str, pd.Series] = {
        "simple_return": simple_ret,
        "log_return": log_ret,
        "vol_20d": rolling_volatility(close, window=20),
        "vol_60d": rolling_volatility(close, window=60),
        "momentum_20d": rolling_momentum(close, window=20),
        "momentum_60d": rolling_momentum(close, window=60),
    }

    df = pd.concat(data, axis=1)
    df.columns = pd.MultiIndex.from_product([[ticker], df.columns])
    return df


def calculate_returns(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily simple returns, log returns, rolling vol, and momentum.

    Supports both single-ticker and multi-ticker DataFrames.  For a
    multi-ticker input the columns should be a MultiIndex of
    ``(ticker, field)``.  For a single-ticker input the columns should
    be field names such as ``['open', 'high', 'low', 'close',
    'volume']``.

    Parameters
    ----------
    ohlcv:
        OHLCV data.  For multi-ticker data use a MultiIndex column
        with levels ``(ticker, field)`` where *field* contains at
        least ``"close"`` (or ``"adj close"``).

    Returns
    -------
    pd.DataFrame
        DataFrame with MultiIndex columns ``(ticker, metric)`` where
        *metric* is one of:

        * ``simple_return``
        * ``log_return``
        * ``vol_20d``
        * ``vol_60d``
        * ``momentum_20d``
        * ``momentum_60d``
    """
    if ohlcv.empty:
        logger.warning("calculate_returns received empty DataFrame")
        return pd.DataFrame()

    # Multi-ticker: columns are (ticker, field) MultiIndex
    if isinstance(ohlcv.columns, pd.MultiIndex):
        tickers = ohlcv.columns.get_level_values(0).unique()
        frames: list[pd.DataFrame] = []

        for ticker in tickers:
            try:
                sub = ohlcv[ticker].copy()
            except KeyError:
                logger.warning("Skipping ticker '%s' — not found in columns", ticker)
                continue
            if "close" not in [c.lower() for c in sub.columns]:
                logger.warning("Skipping ticker '%s' — no 'close' column", ticker)
                continue
            df = _calculate_returns_single_ticker(sub, ticker)
            frames.append(df)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1)

    # Single-ticker: columns are field names
    ticker = ohlcv.attrs.get("ticker", "unknown")
    return _calculate_returns_single_ticker(ohlcv, ticker)


# ---------------------------------------------------------------------------
# Liquidity
# ---------------------------------------------------------------------------

def liquidity_summary(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Compute liquidity summary per ticker.

    Parameters
    ----------
    ohlcv:
        OHLCV data with MultiIndex columns ``(ticker, field)`` or
        a single-ticker DataFrame with field columns.  Required fields
        are ``close`` and ``volume``.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by ticker with columns:

        * ``avg_daily_volume`` — mean daily shares traded
        * ``avg_dollar_volume`` — mean daily ``close * volume``
        * ``missing_pct`` — fraction of rows with missing close or volume
        * ``first_date`` — first observation date
        * ``last_date`` — last observation date
        * ``liquidity_rank`` — rank (1 = most liquid by avg_dollar_volume)
    """
    if ohlcv.empty:
        logger.warning("liquidity_summary received empty DataFrame")
        return pd.DataFrame(
            columns=[
                "avg_daily_volume",
                "avg_dollar_volume",
                "missing_pct",
                "first_date",
                "last_date",
                "liquidity_rank",
            ]
        )

    records: list[dict] = []

    # Multi-ticker
    if isinstance(ohlcv.columns, pd.MultiIndex):
        tickers = ohlcv.columns.get_level_values(0).unique()
        for ticker in tickers:
            try:
                sub = ohlcv[ticker].copy()
            except KeyError:
                continue
            close = _get_column_case_insensitive(sub, "close")
            volume = _get_column_case_insensitive(sub, "volume")
            if close is None or volume is None:
                logger.warning("Skipping '%s' — missing close/volume", ticker)
                continue
            records.append(_liquidity_record(ticker, close, volume))
    else:
        ticker = ohlcv.attrs.get("ticker", "unknown")
        close = _get_column_case_insensitive(ohlcv, "close")
        volume = _get_column_case_insensitive(ohlcv, "volume")
        if close is not None and volume is not None:
            records.append(_liquidity_record(ticker, close, volume))

    if not records:
        return pd.DataFrame()

    summary = pd.DataFrame.from_records(records).set_index("ticker")
    summary["liquidity_rank"] = summary["avg_dollar_volume"].rank(
        ascending=False, method="min"
    ).astype(int)
    return summary


def _get_column_case_insensitive(df: pd.DataFrame, col: str) -> pd.Series | None:
    """Fetch a column from *df* matching *col* case-insensitively.

    Parameters
    ----------
    df:
        Source DataFrame.
    col:
        Target column name (e.g. ``"close"``).

    Returns
    -------
    pd.Series | None
        The matched column or ``None``.
    """
    lower_map = {c.lower(): c for c in df.columns}
    actual = lower_map.get(col.lower())
    return df[actual] if actual is not None else None


def _liquidity_record(
    ticker: str,
    close: pd.Series,
    volume: pd.Series,
) -> dict:
    """Build a single liquidity summary record.

    Parameters
    ----------
    ticker:
        Ticker symbol.
    close:
        Close price series.
    volume:
        Volume series.

    Returns
    -------
    dict
        Record dict ready for :func:`pd.DataFrame.from_records`.
    """
    dollar_volume = close * volume
    n_total = len(close)
    n_missing = int(close.isna().sum() + volume.isna().sum())
    missing_pct = n_missing / (n_total * 2) if n_total > 0 else 0.0

    return {
        "ticker": ticker,
        "avg_daily_volume": float(volume.mean()),
        "avg_dollar_volume": float(dollar_volume.mean()),
        "missing_pct": missing_pct,
        "first_date": close.index[0] if len(close) > 0 else pd.NaT,
        "last_date": close.index[-1] if len(close) > 0 else pd.NaT,
    }
