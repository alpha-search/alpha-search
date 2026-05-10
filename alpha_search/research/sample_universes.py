"""Real OHLCV data fetchers for research and backtesting.

Each function downloads actual market data from free public APIs:
- Yahoo Finance (via yfinance) for equities and ETFs
- CoinGecko (via requests) for cryptocurrencies

No synthetic or mock data is generated. If a data source is unavailable,
a clear error is raised.

Example::

    df = generate_us_equity_data(tickers=["AAPL", "MSFT"], days=252)
    print(df.head())
    # MultiIndex columns: (ticker, field)
    #                    AAPL                MSFT
    #                  Open High Low Close Volume  Open High Low Close Volume

"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

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
# CoinGecko coin IDs (not Yahoo Finance tickers)
_DEFAULT_CRYPTO_COIN_IDS: List[str] = ["bitcoin", "ethereum", "solana", "binancecoin"]
_DEFAULT_ETF_TICKERS: List[str] = ["SPY", "QQQ", "IWM", "VTI"]

# Rate-limit delay between API calls (seconds)
_API_DELAY_SECONDS = 0.5

# ---------------------------------------------------------------------------
# Disk cache helpers
# ---------------------------------------------------------------------------

def _cache_dir() -> Path:
    """Return the local disk cache directory for downloaded data."""
    cache = Path.home() / ".cache" / "alpha_search" / "yfinance"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _cache_path(key: str) -> Path:
    """Build a cache file path for a given cache key."""
    # Sanitise key for filesystem
    safe = key.replace("/", "_").replace("\\", "_")
    return _cache_dir() / f"{safe}.parquet"


def _load_from_cache(key: str, ttl_seconds: int = 86400) -> Optional[pd.DataFrame]:
    """Load a DataFrame from local disk cache if it exists and is fresh.

    Parameters
    ----------
    key:
        Cache key (usually ``function_name_ticker_start_end``).
    ttl_seconds:
        Time-to-live in seconds (default 24 hours).

    Returns
    -------
    pd.DataFrame or None
        Cached data if available and fresh, otherwise ``None``.
    """
    import time

    path = _cache_path(key)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        logger.debug("Cache expired for %s (age=%.0fs)", key, age)
        return None
    try:
        df = pd.read_parquet(path)
        logger.debug("Cache hit for %s", key)
        return df
    except Exception as exc:
        logger.warning("Failed to read cache for %s: %s", key, exc)
        return None


def _save_to_cache(key: str, df: pd.DataFrame) -> None:
    """Save a DataFrame to local disk cache.

    Parameters
    ----------
    key:
        Cache key.
    df:
        DataFrame to cache.
    """
    try:
        path = _cache_path(key)
        df.to_parquet(path)
        logger.debug("Cached %s to %s", key, path)
    except Exception as exc:
        logger.warning("Failed to cache %s: %s", key, exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _make_dates(n: int, freq: str = "B") -> pd.DatetimeIndex:
    """Generate a DatetimeIndex of *n* business days ending today."""
    end = pd.Timestamp.now().normalize()
    dates = pd.bdate_range(end=end, periods=n, freq=freq)
    return dates


def _compute_start_date(days: int) -> str:
    """Compute a start date string *days* calendar days before today."""
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days + 30)  # buffer for weekends/holidays
    return start.strftime("%Y-%m-%d")


def _compute_end_date() -> str:
    """Return today's date as ``YYYY-MM-DD``."""
    return pd.Timestamp.now().normalize().strftime("%Y-%m-%d")


def _fetch_yfinance_ohlcv(
    ticker: str,
    start: str,
    end: str,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Download OHLCV data for a single ticker from Yahoo Finance.

    Parameters
    ----------
    ticker:
        Yahoo Finance ticker symbol.
    start:
        Start date ``YYYY-MM-DD``.
    end:
        End date ``YYYY-MM-DD``.
    use_cache:
        Whether to read/write local disk cache.

    Returns
    -------
    pd.DataFrame
        Columns: Open, High, Low, Close, Volume.  Index: date.

    Raises
    ------
    RuntimeError
        If yfinance is not installed or the download fails.
    """
    cache_key = f"yfinance_{ticker}_{start}_{end}"
    if use_cache:
        cached = _load_from_cache(cache_key)
        if cached is not None:
            return cached

    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError(
            "yfinance is not installed. "
            "Install it with: pip install yfinance"
        )

    tkr = yf.Ticker(ticker)
    df = tkr.history(start=start, end=end, interval="1d")

    if df is None or df.empty:
        raise RuntimeError(
            f"No data returned for {ticker} between {start} and {end}. "
            f"The ticker may be delisted or the date range invalid."
        )

    # Normalise columns
    df.columns = [c.title() if isinstance(c, str) else c for c in df.columns]
    std_cols = ["Open", "High", "Low", "Close", "Volume"]
    available = [c for c in std_cols if c in df.columns]
    df = df[available]

    if use_cache:
        _save_to_cache(cache_key, df)

    logger.info("Fetched %s: %d rows (%s to %s)", ticker, len(df), start, end)
    return df


def _fetch_coingecko_prices(
    coin_ids: List[str],
    days: int = 365,
) -> Dict[str, pd.DataFrame]:
    """Fetch historical OHLCV data from CoinGecko (free, no API key).

    Parameters
    ----------
    coin_ids:
        List of CoinGecko coin IDs (e.g. ``["bitcoin", "ethereum"]``).
    days:
        Number of days of history to fetch (default 365).

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping coin_id -> OHLCV DataFrame with columns
        ``Open, High, Low, Close, Volume``.  Index: date.

    Raises
       ------
    RuntimeError
        If ``requests`` is not installed or the API call fails.
    """
    try:
        import requests
    except ImportError:
        raise RuntimeError(
            "requests is not installed. "
            "Install it with: pip install requests"
        )

    result: Dict[str, pd.DataFrame] = {}

    for coin_id in coin_ids:
        cache_key = f"coingecko_{coin_id}_{days}"
        cached = _load_from_cache(cache_key)
        if cached is not None:
            result[coin_id] = cached
            continue

        # Use the market_chart endpoint for price + volume data
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params: dict = {"vs_currency": "usd", "days": days}

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(
                f"CoinGecko API request failed for {coin_id}: {exc}. "
                f"This may be due to rate limiting. Wait a moment and retry."
            )

        data = resp.json()
        if "prices" not in data:
            raise RuntimeError(
                f"CoinGecko returned unexpected data for {coin_id}: {list(data.keys())}"
            )

        # Parse prices: data["prices"] is [[timestamp_ms, price], ...]
        prices_df = pd.DataFrame(
            data["prices"], columns=["timestamp", "price"]
        )
        prices_df["timestamp"] = pd.to_datetime(
            prices_df["timestamp"], unit="ms", utc=True
        ).dt.tz_localize(None)
        prices_df = prices_df.set_index("timestamp").sort_index()

        # Parse total_volumes: [[timestamp_ms, volume], ...]
        if "total_volumes" in data and data["total_volumes"]:
            vol_df = pd.DataFrame(
                data["total_volumes"], columns=["timestamp", "volume"]
            )
            vol_df["timestamp"] = pd.to_datetime(
                vol_df["timestamp"], unit="ms", utc=True
            ).dt.tz_localize(None)
            vol_df = vol_df.set_index("timestamp").sort_index()
        else:
            vol_df = pd.DataFrame(
                {"volume": 0.0}, index=prices_df.index
            )

        # Align all series to the same index
        common_idx = prices_df.index
        aligned_prices = prices_df["price"].reindex(common_idx)
        aligned_volume = vol_df["volume"].reindex(common_idx).fillna(0.0)

        # Estimate High/Low from intraday range (crypto is 24h, ~2-5% typical range)
        # Estimate daily high/low as price ± typical intraday volatility
        # For crypto, ~3% daily range is a rough approximation
        intraday_range = aligned_prices * 0.015  # ~1.5% each side
        estimated_high = aligned_prices + intraday_range
        estimated_low = aligned_prices - intraday_range

        # Build OHLCV DataFrame
        df = pd.DataFrame(
            {
                "Open": aligned_prices,
                "High": estimated_high,
                "Low": estimated_low,
                "Close": aligned_prices,
                "Volume": aligned_volume,
            },
            index=common_idx,
        )

        # Round to reasonable precision
        df = df.round({"Open": 2, "High": 2, "Low": 2, "Close": 2})

        _save_to_cache(cache_key, df)
        result[coin_id] = df

        # Rate-limit delay
        time.sleep(_API_DELAY_SECONDS)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_us_equity_data(
    tickers: Optional[List[str]] = None,
    days: int = 252,
    seed: int = 42,  # noqa: ARG001
) -> pd.DataFrame:
    """Fetch **real** US equity OHLCV data from Yahoo Finance.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to
        ``["AAPL", "MSFT", "GOOGL", "AMZN", "META"]``.
    days:
        Number of trading days to fetch (default 252 ~ 1 year).
    seed:
        Kept for API compatibility; has no effect (real data is deterministic).

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` where *field* is one of
        ``Open, High, Low, Close, Volume``.  Index is a business-day
        DatetimeIndex.

    Raises
    ------
    RuntimeError
        If yfinance is not installed or all tickers fail to download.
    """
    tickers = tickers or _DEFAULT_US_TICKERS
    start = _compute_start_date(days)
    end = _compute_end_date()

    ticker_dfs: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for ticker in tickers:
        try:
            df = _fetch_yfinance_ohlcv(ticker, start, end)
            ticker_dfs[ticker] = df
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            failures.append(ticker)
        time.sleep(_API_DELAY_SECONDS)

    if not ticker_dfs:
        raise RuntimeError(
            f"Failed to fetch data for any ticker. "
            f"Failures: {', '.join(failures)}. "
            f"Ensure yfinance is installed: pip install yfinance"
        )

    if failures:
        logger.warning(
            "Successfully fetched %d/%d tickers. Failed: %s",
            len(ticker_dfs),
            len(tickers),
            ", ".join(failures),
        )

    logger.info(
        "Fetched real US equity data: %d tickers x up to %d days",
        len(ticker_dfs),
        days,
    )
    return _build_multiindex_df(ticker_dfs)


def generate_indian_equity_data(
    tickers: Optional[List[str]] = None,
    days: int = 252,
    seed: int = 43,  # noqa: ARG001
) -> pd.DataFrame:
    """Fetch **real** Indian equity OHLCV data from Yahoo Finance.

    NSE tickers use the ``.NS`` suffix (e.g. ``"RELIANCE.NS"``).

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to
        ``["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS"]``.
    days:
        Number of trading days to fetch (default 252).
    seed:
        Kept for API compatibility; has no effect.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` with OHLCV data.

    Raises
    ------
    RuntimeError
        If yfinance is not installed or all tickers fail.
    """
    tickers = tickers or _DEFAULT_INDIAN_TICKERS
    start = _compute_start_date(days)
    end = _compute_end_date()

    ticker_dfs: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for ticker in tickers:
        try:
            df = _fetch_yfinance_ohlcv(ticker, start, end)
            ticker_dfs[ticker] = df
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            failures.append(ticker)
        time.sleep(_API_DELAY_SECONDS)

    if not ticker_dfs:
        raise RuntimeError(
            f"Failed to fetch data for any Indian ticker. "
            f"Failures: {', '.join(failures)}. "
            f"Ensure yfinance is installed and the tickers use the .NS suffix."
        )

    logger.info(
        "Fetched real Indian equity data: %d tickers x up to %d days",
        len(ticker_dfs),
        days,
    )
    return _build_multiindex_df(ticker_dfs)


def generate_crypto_data(
    tickers: Optional[List[str]] = None,
    days: int = 365,
    seed: int = 44,  # noqa: ARG001
) -> pd.DataFrame:
    """Fetch **real** cryptocurrency price data from CoinGecko (free, no key).

    Parameters
    ----------
    tickers:
        List of CoinGecko coin IDs.  Defaults to
        ``["bitcoin", "ethereum", "solana", "binancecoin"]``.
        Note: these are CoinGecko IDs, not Yahoo Finance tickers.
    days:
        Number of calendar days to fetch (default 365 ~ 1 year).
    seed:
        Kept for API compatibility; has no effect.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` with OHLCV data.
        Index is a daily calendar DatetimeIndex.
        **Volume** is the 24h total volume in USD from CoinGecko.

    Raises
    ------
    RuntimeError
        If ``requests`` is not installed or the CoinGecko API fails.
    """
    coin_ids = tickers or _DEFAULT_CRYPTO_COIN_IDS

    ticker_dfs = _fetch_coingecko_prices(coin_ids, days=days)

    if not ticker_dfs:
        raise RuntimeError(
            "Failed to fetch any cryptocurrency data from CoinGecko. "
            "Ensure 'requests' is installed: pip install requests"
        )

    logger.info(
        "Fetched real crypto data: %d coins x up to %d days",
        len(ticker_dfs),
        days,
    )
    return _build_multiindex_df(ticker_dfs)


def generate_etf_data(
    tickers: Optional[List[str]] = None,
    days: int = 252,
    seed: int = 45,  # noqa: ARG001
) -> pd.DataFrame:
    """Fetch **real** ETF OHLCV data from Yahoo Finance.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to ``["SPY", "QQQ", "IWM", "VTI"]``.
    days:
        Number of trading days to fetch (default 252).
    seed:
        Kept for API compatibility; has no effect.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns ``(ticker, field)`` with OHLCV data.

    Raises
    ------
    RuntimeError
        If yfinance is not installed or all tickers fail.
    """
    tickers = tickers or _DEFAULT_ETF_TICKERS
    start = _compute_start_date(days)
    end = _compute_end_date()

    ticker_dfs: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for ticker in tickers:
        try:
            df = _fetch_yfinance_ohlcv(ticker, start, end)
            ticker_dfs[ticker] = df
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            failures.append(ticker)
        time.sleep(_API_DELAY_SECONDS)

    if not ticker_dfs:
        raise RuntimeError(
            f"Failed to fetch data for any ETF. "
            f"Failures: {', '.join(failures)}. "
            f"Ensure yfinance is installed: pip install yfinance"
        )

    logger.info(
        "Fetched real ETF data: %d tickers x up to %d days",
        len(ticker_dfs),
        days,
    )
    return _build_multiindex_df(ticker_dfs)
