"""Data normalization utilities for standardizing OHLCV data from different sources."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from alpha_search.core.errors import ValidationError

logger = logging.getLogger(__name__)

# Mapping of common column name variants to standard names
_COLUMN_ALIASES = {
    "open": "Open",
    "o": "Open",
    "high": "High",
    "h": "High",
    "low": "Low",
    "l": "Low",
    "close": "Close",
    "c": "Close",
    "adj close": "Adj Close",
    "adj_close": "Adj Close",
    "volume": "Volume",
    "vol": "Volume",
    "v": "Volume",
}

_SOURCE_SPECIFIC = {
    "yfinance": {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    },
    "binance": {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    },
    "alphavantage": {
        "1. open": "Open",
        "2. high": "High",
        "3. low": "Low",
        "4. close": "Close",
        "5. volume": "Volume",
    },
}


def normalize_ohlcv(df: pd.DataFrame, source: str = "generic") -> pd.DataFrame:
    """Standardize column names of an OHLCV DataFrame.

    Args:
        df: Raw DataFrame from a data provider.
        source: Provider name hint (``'yfinance'``, ``'binance'``, etc.).

    Returns:
        DataFrame with columns ``['Open','High','Low','Close','Volume']``
        (and optionally ``'Adj Close'``). Index is coerced to DatetimeIndex.

    Raises:
        ValidationError: If required columns cannot be resolved.
    """
    if df is None or df.empty:
        raise ValidationError("Cannot normalize an empty DataFrame", field="df")

    df = df.copy()

    # Coerce index to DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception as exc:
            raise ValidationError(
                f"Cannot coerce index to DatetimeIndex: {exc}", field="index"
            )

    # Normalize column names to lower for matching
    rename_map: dict[str, str] = {}
    source_lower = source.lower()

    if source_lower in _SOURCE_SPECIFIC:
        rename_map = _SOURCE_SPECIFIC[source_lower]
    else:
        # Try generic matching
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if col_lower in _COLUMN_ALIASES:
                rename_map[col] = _COLUMN_ALIASES[col_lower]

    # Apply renames
    if rename_map:
        df = df.rename(columns=rename_map)

    # Ensure standard columns exist
    required = ["Open", "High", "Low", "Close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValidationError(
            f"Missing required columns after normalization: {missing}. "
            f"Available columns: {list(df.columns)}",
            field="columns",
        )

    # Add Volume if missing
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
        logger.debug("Volume column missing; filling with zeros.")

    # Select and order standard columns
    standard_cols = [c for c in required + ["Volume"] if c in df.columns]
    df = df[standard_cols]

    # Ensure numeric types
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows where all OHLC are NaN
    df = df.dropna(subset=required, how="all")

    logger.debug(
        "Normalized OHLCV: source=%s rows=%d cols=%s",
        source,
        len(df),
        list(df.columns),
    )
    return df


def resample_to_daily(
    df: pd.DataFrame,
    aggregation: Optional[dict[str, str]] = None,
) -> pd.DataFrame:
    """Resample intraday OHLCV data to daily frequency.

    Args:
        df: DataFrame with DatetimeIndex and standard OHLCV columns.
        aggregation: Dict mapping column names to aggregation functions.
            Defaults are ``{'Open':'first','High':'max','Low':'min',
            'Close':'last','Volume':'sum'}``.

    Returns:
        Daily resampled DataFrame.
    """
    if df.empty:
        return df.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValidationError("DataFrame must have DatetimeIndex", field="index")

    if aggregation is None:
        aggregation = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }

    # Only aggregate columns that exist
    agg = {k: v for k, v in aggregation.items() if k in df.columns}
    daily = df.resample("D").agg(agg)
    daily = daily.dropna(subset=["Open", "High", "Low", "Close"], how="all")
    return daily


def fill_missing_timestamps(
    df: pd.DataFrame,
    method: str = "ffill",
    fill_volume: float = 0.0,
) -> pd.DataFrame:
    """Reindex to a complete daily index and fill missing values.

    Args:
        df: DataFrame with DatetimeIndex.
        method: Forward-fill (``'ffill'``) or another fill strategy.
        fill_volume: Value to fill missing Volume entries.

    Returns:
        DataFrame with no missing trading days.
    """
    if df.empty:
        return df.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValidationError("DataFrame must have DatetimeIndex", field="index")

    start = df.index.min()
    end = df.index.max()
    full_index = pd.date_range(start=start, end=end, freq="D")

    df = df.reindex(full_index)

    # Forward-fill OHLCV
    ohlc_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
    if ohlc_cols:
        df[ohlc_cols] = df[ohlc_cols].fillna(method=method)

    # Fill volume separately
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].fillna(fill_volume)

    return df
