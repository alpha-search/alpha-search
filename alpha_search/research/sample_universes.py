"""Synthetic OHLCV data generators for research and demonstration.

Each function produces realistic price data using Geometric Brownian
Motion (GBM) with asset-class-specific drift and volatility parameters.
The data is clearly labeled as *synthetic* and intended for strategy
development, backtesting demonstrations, and educational purposes only.

Example::

    df = generate_us_equity_data(tickers=["AAPL", "MSFT"], days=252)
    print(df.head())
    # MultiIndex columns: (ticker, field)
    #                    AAPL                MSFT
    #                  Open High Low Close Volume  Open High Low Close Volume

"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default ticker lists
# ---------------------------------------------------------------------------
_DEFAULT_US_TICKERS: List[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
_DEFAULT_INDIAN_TICKERS: List[str] = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ITC.NS",
]
_DEFAULT_CRYPTO_TICKERS: List[str] = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]
_DEFAULT_ETF_TICKERS: List[str] = ["SPY", "QQQ", "IWM", "VTI"]

# ---------------------------------------------------------------------------
# Asset-class parameters (annualised)
# ---------------------------------------------------------------------------
_US_EQUITY_PARAMS = {
    "mu": 0.08,          # 8 % annual drift
    "sigma": 0.20,       # 20 % annual volatility
    "trading_days": 252,
    "volume_low": 1_000_000,
    "volume_high": 10_000_000,
    "start_price": 150.0,
}

_INDIAN_EQUITY_PARAMS = {
    "mu": 0.12,          # 12 % annual drift
    "sigma": 0.30,       # 30 % annual volatility
    "trading_days": 252,
    "volume_low": 500_000,
    "volume_high": 5_000_000,
    "start_price": 2500.0,
}

_CRYPTO_PARAMS = {
    "mu": 0.50,          # 50 % annual drift
    "sigma": 0.80,       # 80 % annual volatility
    "trading_days": 365,
    "volume_low": 100_000,
    "volume_high": 1_000_000,
    "start_price": 50_000.0,
}

_ETF_PARAMS = {
    "mu": 0.07,          # 7 % annual drift
    "sigma": 0.15,       # 15 % annual volatility
    "trading_days": 252,
    "volume_low": 2_000_000,
    "volume_high": 20_000_000,
    "start_price": 400.0,
}

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _generate_ohlcv_for_ticker(
    ticker: str,
    dates: pd.DatetimeIndex,
    mu: float,
    sigma: float,
    volume_low: float,
    volume_high: float,
    start_price: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate a single-ticker OHLCV DataFrame via GBM.

    Parameters
    ----------
    ticker:
        Symbol name (used for logging only).
    dates:
        Trading-date index.
    mu:
        Annualised drift (decimal).
    sigma:
        Annualised volatility (decimal).
    volume_low, volume_high:
        Uniform sampling bounds for daily volume.
    start_price:
        Opening price on the first day.
    rng:
        NumPy random number generator.

    Returns
    -------
    pd.DataFrame
        Columns: Open, High, Low, Close, Volume.  Index: *dates*.
    """
    _n = len(dates)  # noqa: F841
    _dt = 1.0 / len(dates) * (len(dates) / 252)  # noqa: F841  # normalise to ~252 trading days/year
    # Actually — simpler: compute daily parameters from annual ones
    # For n days, the fraction of a year per step = 252 / n for equities, 365 / n for crypto
    # We'll compute below directly

    return _generate_ohlcv_gbm(
        dates=dates,
        mu=mu,
        sigma=sigma,
        volume_low=volume_low,
        volume_high=volume_high,
        start_price=start_price,
        rng=rng,
    )


def _generate_ohlcv_gbm(
    dates: pd.DatetimeIndex,
    mu: float,
    sigma: float,
    volume_low: float,
    volume_high: float,
    start_price: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate OHLCV data using Geometric Brownian Motion.

    Close prices follow:
        dS = mu * S * dt + sigma * S * sqrt(dt) * Z

    where Z ~ N(0, 1).

    Open  = previous Close (or *start_price* on day 0).
    High  = max(Open, Close) + random perturbation.
    Low   = min(Open, Close) - random perturbation.
    Volume is uniformly distributed between *volume_low* and *volume_high*.
    """
    n = len(dates)  # noqa: F841
    # Daily parameters
    days_per_year = 252 if n <= 300 else 365
    dt = 1.0 / days_per_year
    daily_drift = mu * dt
    daily_vol = sigma * np.sqrt(dt)

    # GBM returns
    returns = daily_drift + daily_vol * rng.standard_normal(n)

    # Close prices
    close_prices = start_price * np.exp(np.cumsum(returns))

    # Build OHLC
    opens = np.empty(n)
    opens[0] = start_price
    opens[1:] = close_prices[:-1]

    # Intraday range: random wick size ~1-3 % of the price level
    wick_pct = rng.uniform(0.005, 0.025, size=n)
    wick_size = close_prices * wick_pct

    highs = np.maximum(opens, close_prices) + wick_size * rng.uniform(0.3, 1.0, size=n)
    lows = np.minimum(opens, close_prices) - wick_size * rng.uniform(0.3, 1.0, size=n)

    # Volume
    volumes = rng.integers(volume_low, volume_high, size=n)

    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": close_prices,
            "Volume": volumes,
        },
        index=dates,
    )
    return df


def _build_multiindex_df(
    ticker_dfs: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Combine per-ticker DataFrames into a single MultiIndex-column DataFrame.

    Parameters
    ----------
    ticker_dfs:
        Mapping ticker -> OHLCV DataFrame.

    Returns
    -------
    pd.DataFrame
        Columns: MultiIndex(level_0=ticker, level_1=field).
        Index: date (DatetimeIndex).
    """
    combined = pd.concat(
        {ticker: df for ticker, df in ticker_dfs.items()},
        axis=1,
    )
    # Ensure column names are correct
    combined.columns.names = ["ticker", "field"]
    return combined


def _make_dates(n: int, freq: str = "B", seed: int = 42) -> pd.DatetimeIndex:
    """Generate a DatetimeIndex of *n* business days ending today."""
    end = pd.Timestamp.now().normalize()
    dates = pd.bdate_range(end=end, periods=n, freq=freq)
    return dates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_us_equity_data(
    tickers: Optional[List[str]] = None,
    days: int = 252,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate **synthetic** US equity OHLCV data for research.

    Uses GBM with parameters calibrated to large-cap US equities:
    drift = 8 %/year, volatility = 20 %/year, volume 1–10 M shares/day.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to ``["AAPL", "MSFT", "GOOGL", "AMZN", "META"]``.
    days:
        Number of trading days to generate (default 252 ≈ 1 year).
    seed:
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` where *field* is one of
        ``Open, High, Low, Close, Volume``.  Index is a business-day
        DatetimeIndex.  **This data is synthetic and for demonstration
        only.**
    """
    tickers = tickers or _DEFAULT_US_TICKERS
    rng = np.random.default_rng(seed)
    dates = _make_dates(days, freq="B")

    p = _US_EQUITY_PARAMS
    ticker_dfs: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        start_price = p["start_price"] * rng.uniform(0.5, 2.0)
        df = _generate_ohlcv_gbm(
            dates=dates,
            mu=p["mu"],
            sigma=p["sigma"],
            volume_low=p["volume_low"],
            volume_high=p["volume_high"],
            start_price=start_price,
            rng=rng,
        )
        ticker_dfs[ticker] = df

    logger.info(
        "Generated synthetic US equity data: %d tickers x %d days",
        len(tickers),
        days,
    )
    return _build_multiindex_df(ticker_dfs)


def generate_indian_equity_data(
    tickers: Optional[List[str]] = None,
    days: int = 252,
    seed: int = 43,
) -> pd.DataFrame:
    """Generate **synthetic** Indian equity OHLCV data for research.

    Uses GBM with parameters calibrated to Indian large-caps:
    drift = 12 %/year, volatility = 30 %/year, volume 0.5–5 M shares/day.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to
        ``["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS"]``.
    days:
        Number of trading days (default 252).
    seed:
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` with OHLCV data.
        **Synthetic — for demonstration only.**
    """
    tickers = tickers or _DEFAULT_INDIAN_TICKERS
    rng = np.random.default_rng(seed)
    dates = _make_dates(days, freq="B")

    p = _INDIAN_EQUITY_PARAMS
    ticker_dfs: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        start_price = p["start_price"] * rng.uniform(0.5, 2.0)
        df = _generate_ohlcv_gbm(
            dates=dates,
            mu=p["mu"],
            sigma=p["sigma"],
            volume_low=p["volume_low"],
            volume_high=p["volume_high"],
            start_price=start_price,
            rng=rng,
        )
        ticker_dfs[ticker] = df

    logger.info(
        "Generated synthetic Indian equity data: %d tickers x %d days",
        len(tickers),
        days,
    )
    return _build_multiindex_df(ticker_dfs)


def generate_crypto_data(
    tickers: Optional[List[str]] = None,
    days: int = 365,
    seed: int = 44,
) -> pd.DataFrame:
    """Generate **synthetic** cryptocurrency OHLCV data for research.

    Uses GBM with parameters calibrated to major crypto assets:
    drift = 50 %/year, volatility = 80 %/year, volume 0.1–1 M units/day.
    Crypto trades 24/7 so the index uses calendar days.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to
        ``["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]``.
    days:
        Number of calendar days (default 365 ≈ 1 year).
    seed:
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` with OHLCV data.
        Index is a daily calendar DatetimeIndex.  **Synthetic — for
        demonstration only.**
    """
    tickers = tickers or _DEFAULT_CRYPTO_TICKERS
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.now().normalize()
    dates = pd.date_range(end=end, periods=days, freq="D")

    p = _CRYPTO_PARAMS
    ticker_dfs: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        start_price = p["start_price"] * rng.uniform(0.2, 3.0)
        df = _generate_ohlcv_gbm(
            dates=dates,
            mu=p["mu"],
            sigma=p["sigma"],
            volume_low=p["volume_low"],
            volume_high=p["volume_high"],
            start_price=start_price,
            rng=rng,
        )
        ticker_dfs[ticker] = df

    logger.info(
        "Generated synthetic crypto data: %d tickers x %d days",
        len(tickers),
        days,
    )
    return _build_multiindex_df(ticker_dfs)


def generate_etf_data(
    tickers: Optional[List[str]] = None,
    days: int = 252,
    seed: int = 45,
) -> pd.DataFrame:
    """Generate **synthetic** ETF OHLCV data for research.

    Uses GBM with parameters calibrated to broad-market ETFs:
    drift = 7 %/year, volatility = 15 %/year, volume 2–20 M shares/day.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to ``["SPY", "QQQ", "IWM", "VTI"]``.
    days:
        Number of trading days (default 252).
    seed:
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` with OHLCV data.
        **Synthetic — for demonstration only.**
    """
    tickers = tickers or _DEFAULT_ETF_TICKERS
    rng = np.random.default_rng(seed)
    dates = _make_dates(days, freq="B")

    p = _ETF_PARAMS
    ticker_dfs: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        start_price = p["start_price"] * rng.uniform(0.5, 2.0)
        df = _generate_ohlcv_gbm(
            dates=dates,
            mu=p["mu"],
            sigma=p["sigma"],
            volume_low=p["volume_low"],
            volume_high=p["volume_high"],
            start_price=start_price,
            rng=rng,
        )
        ticker_dfs[ticker] = df

    logger.info(
        "Generated synthetic ETF data: %d tickers x %d days",
        len(tickers),
        days,
    )
    return _build_multiindex_df(ticker_dfs)
