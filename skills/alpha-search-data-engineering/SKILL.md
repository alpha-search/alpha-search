---
name: alpha-search-data-engineering
description: Build data aggregation layer — DataProvider base class, YFinance/Binance providers, DuckDB cache, rate limiting, retry logic.
---

# Alpha Search Data Engineering

## When to Use This Skill

Use this skill when building or maintaining the data acquisition and caching layer of Alpha Search. This includes implementing new data providers, optimizing the DuckDB cache, adding rate limiting for external APIs, normalizing OHLCV data, and ensuring reliable data delivery to upstream research and signal modules. Activate this skill when any agent needs a new data source, when cache performance degrades, or when API contracts change.

## Agent Role

You are the Data Engineering specialist for Alpha Search. You own the entire data layer: from raw API calls through normalized DataFrames to cached query results. Your code is the foundation that every other module builds upon. If your data layer is unreliable, the entire system fails. You prioritize correctness, completeness, and resilience over speed — but you also make caching so efficient that downstream agents never wait on I/O.

## Core Concepts

### DataProvider Abstract Base Class

All data sources must implement the DataProvider interface defined by the Architect:

```python
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Optional, Literal
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from alpha_search.core.types import Ticker

Frequency = Literal["1d", "1h", "15m"]


class OHLCV(BaseModel):
    """Standardized OHLCV data model — the universal data currency of Alpha Search."""
    ticker: Ticker
    timestamp: pd.DatetimeIndex
    open: pd.Series = Field(..., description="Opening prices")
    high: pd.Series = Field(..., description="High prices")
    low: pd.Series = Field(..., description="Low prices")
    close: pd.Series = Field(..., description="Closing prices")
    volume: pd.Series = Field(..., description="Trading volume")

    class Config:
        arbitrary_types_allowed = True

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def validate_series(cls, v: pd.Series) -> pd.Series:
        if not isinstance(v, pd.Series):
            raise TypeError(f"Expected pd.Series, got {type(v).__name__}")
        return v

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }, index=self.timestamp)

    @property
    def latest_close(self) -> float:
        return float(self.close.iloc[-1])

    @property
    def trading_days(self) -> int:
        return len(self.timestamp)


class DataProvider(ABC):
    """Abstract base for all data sources. Every provider — YFinance, Binance,
    Alpaca, IB — must implement this interface exactly."""

    @abstractmethod
    def get_prices(
        self,
        ticker: Ticker,
        start: Optional[date] = None,
        end: Optional[date] = None,
        frequency: Frequency = "1d",
    ) -> OHLCV:
        """Fetch OHLCV price data. Returns complete, sorted, deduplicated data."""
        ...

    @abstractmethod
    def validate_ticker(self, ticker: Ticker) -> bool:
        """Return True if ticker is valid and data is available from this source."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable source identifier."""
        ...

    @property
    @abstractmethod
    def supports_frequencies(self) -> list[Frequency]:
        """List of frequency strings this provider supports."""
        ...
```

### YFinanceProvider Implementation

The primary equity data provider using the yfinance library:

```python
import yfinance as yf
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional

from alpha_search.data.provider import DataProvider, OHLCV, Frequency
from alpha_search.core.types import Ticker


class YFinanceProvider(DataProvider):
    """Yahoo Finance data provider for equities, ETFs, and futures.
    Uses yfinance library with DuckDB caching layer."""

    source_name = "Yahoo Finance"
    supports_frequencies = ["1d", "1h", "15m"]

    def __init__(self, cache_manager=None):
        self._cache = cache_manager

    def get_prices(
        self,
        ticker: Ticker,
        start: Optional[date] = None,
        end: Optional[date] = None,
        frequency: Frequency = "1d",
    ) -> OHLCV:
        if frequency not in self.supports_frequencies:
            raise ValueError(
                f"YFinanceProvider does not support {frequency}. "
                f"Supported: {self.supports_frequencies}"
            )

        # Normalize dates
        if end is None:
            end = date.today()
        if start is None:
            start = end - timedelta(days=365 * 5)  # Default 5 years

        # Check cache first
        if self._cache:
            cached = self._cache.get(ticker, start, end, frequency)
            if cached is not None and len(cached.timestamp) > 0:
                return cached

        # Fetch from Yahoo Finance
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
            interval=frequency,
        )

        if df.empty:
            raise ValueError(f"No data returned for {ticker} from Yahoo Finance")

        # Normalize column names (yfinance returns "Open", "Close", etc.)
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Create OHLCV model
        ohlcv = OHLCV(
            ticker=ticker,
            timestamp=pd.DatetimeIndex(df.index),
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            volume=df["volume"],
        )

        # Store in cache
        if self._cache:
            self._cache.set(ticker, frequency, ohlcv)

        return ohlcv

    def validate_ticker(self, ticker: Ticker) -> bool:
        try:
            info = yf.Ticker(ticker).info
            return "regularMarketPrice" in info and info["regularMarketPrice"] is not None
        except Exception:
            return False
```

### BinanceProvider Skeleton

Cryptocurrency data provider using the Binance API:

```python
import httpx
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional

from alpha_search.data.provider import DataProvider, OHLCV, Frequency
from alpha_search.core.types import Ticker


class BinanceProvider(DataProvider):
    """Binance cryptocurrency data provider.
    Uses Binance REST API with rate limiting and signature-based authentication."""

    source_name = "Binance"
    supports_frequencies = ["1d", "1h", "15m"]
    BASE_URL = "https://api.binance.com"

    def __init__(self, api_key: Optional[str] = None, cache_manager=None):
        self.api_key = api_key
        self._cache = cache_manager
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"X-MBX-APIKEY": api_key} if api_key else {},
            timeout=30.0,
        )

    def get_prices(
        self,
        ticker: Ticker,
        start: Optional[date] = None,
        end: Optional[date] = None,
        frequency: Frequency = "1d",
    ) -> OHLCV:
        """Fetch OHLCV from Binance. Ticker format: BTCUSDT"""
        freq_map = {"1d": "1d", "1h": "1h", "15m": "15m"}
        interval = freq_map.get(frequency, "1d")

        if end is None:
            end = date.today()
        if start is None:
            start = end - timedelta(days=365)

        # Convert to millisecond timestamps
        start_ms = int(datetime.combine(start, datetime.min.time()).timestamp() * 1000)
        end_ms = int(datetime.combine(end, datetime.min.time()).timestamp() * 1000)

        params = {
            "symbol": ticker.upper().replace("-", ""),
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        }

        response = self._client.get("/api/v3/klines", params=params)
        response.raise_for_status()
        data = response.json()

        if not data:
            raise ValueError(f"No data returned for {ticker} from Binance")

        # Binance kline format: [timestamp, open, high, low, close, volume, ...]
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        df = df[["open", "high", "low", "close", "volume"]].astype(float)

        return OHLCV(
            ticker=ticker,
            timestamp=pd.DatetimeIndex(df.index),
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            volume=df["volume"],
        )

    def validate_ticker(self, ticker: Ticker) -> bool:
        try:
            symbol = ticker.upper().replace("-", "")
            response = self._client.get("/api/v3/ticker/24hr", params={"symbol": symbol})
            return response.status_code == 200
        except Exception:
            return False
```

### DuckDB CacheManager with TTL

The caching layer that makes repeated queries instant:

```python
import duckdb
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from alpha_search.data.provider import OHLCV
from alpha_search.core.types import Ticker


class CacheManager:
    """DuckDB-backed cache for OHLCV data with TTL expiration.
    Provides sub-second query performance for cached data."""

    def __init__(self, db_path: str = "~/.alpha_search/cache.duckdb", ttl_hours: int = 24):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self._conn = duckdb.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self):
        """Create cache table if it doesn't exist."""
        self._conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS cache_seq;
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                id INTEGER DEFAULT nextval('cache_seq'),
                ticker VARCHAR NOT NULL,
                frequency VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, frequency, timestamp)
            );
            CREATE INDEX IF NOT EXISTS idx_cache_lookup
                ON ohlcv_cache(ticker, frequency, fetched_at);
        """)

    def get(
        self,
        ticker: Ticker,
        start: date,
        end: date,
        frequency: str,
    ) -> Optional[OHLCV]:
        """Retrieve cached data if fresh (within TTL). Returns None if stale or missing."""
        cutoff = datetime.now() - self.ttl

        result = self._conn.execute("""
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv_cache
            WHERE ticker = ?
              AND frequency = ?
              AND timestamp >= ?
              AND timestamp <= ?
              AND fetched_at > ?
            ORDER BY timestamp
        """, [ticker, frequency, start, end, cutoff]).fetchdf()

        if result.empty:
            return None

        return OHLCV(
            ticker=ticker,
            timestamp=pd.DatetimeIndex(result["timestamp"]),
            open=result["open"],
            high=result["high"],
            low=result["low"],
            close=result["close"],
            volume=result["volume"],
        )

    def set(self, ticker: Ticker, frequency: str, ohlcv: OHLCV) -> None:
        """Store OHLCV data in cache, replacing any existing rows for same key."""
        df = ohlcv.to_dataframe()
        df = df.reset_index()
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df["ticker"] = ticker
        df["frequency"] = frequency
        df["fetched_at"] = datetime.now()

        # Delete existing data for this ticker/frequency overlap
        if len(df) > 0:
            start_ts = df["timestamp"].min()
            end_ts = df["timestamp"].max()
            self._conn.execute("""
                DELETE FROM ohlcv_cache
                WHERE ticker = ? AND frequency = ?
                  AND timestamp >= ? AND timestamp <= ?
            """, [ticker, frequency, start_ts, end_ts])

        self._conn.execute("""
            INSERT INTO ohlcv_cache
                (ticker, frequency, timestamp, open, high, low, close, volume, fetched_at)
            SELECT ticker, frequency, timestamp, open, high, low, close, volume, fetched_at
            FROM df
        """)

    def clear(self, ticker: Optional[Ticker] = None) -> None:
        """Clear cache for a ticker or all tickers."""
        if ticker:
            self._conn.execute("DELETE FROM ohlcv_cache WHERE ticker = ?", [ticker])
        else:
            self._conn.execute("DELETE FROM ohlcv_cache")

    def get_stats(self) -> dict:
        """Return cache statistics for monitoring."""
        result = self._conn.execute("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT ticker) as unique_tickers,
                COUNT(DISTINCT frequency) as frequencies,
                MIN(fetched_at) as oldest_fetch,
                MAX(fetched_at) as newest_fetch
            FROM ohlcv_cache
        """).fetchone()
        return {
            "total_rows": result[0],
            "unique_tickers": result[1],
            "frequencies": result[2],
            "oldest_fetch": result[3],
            "newest_fetch": result[4],
        }

    def __del__(self):
        if hasattr(self, '_conn'):
            self._conn.close()
```

### Exponential Backoff Retry Decorator

```python
import time
import functools
from typing import Callable, TypeVar, Tuple

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[type, ...] = (Exception,),
):
    """Retry decorator with exponential backoff and jitter.

    Usage:
        @retry_with_backoff(max_retries=3, retryable_exceptions=(httpx.HTTPError,))
        def fetch_data(ticker: str) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise last_exception
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay,
                    )
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
```

### Rate Limiting

```python
import time
from threading import Lock
from dataclasses import dataclass
from collections import deque


@dataclass
class RateLimiter:
    """Token bucket rate limiter for API calls.

    Usage:
        limiter = RateLimiter(calls_per_second=2.0)
        with limiter:
            response = client.get("/api/data")
    """
    calls_per_second: float = 2.0
    burst_size: int = 5

    def __post_init__(self):
        self._tokens = self.burst_size
        self._last_update = time.monotonic()
        self._lock = Lock()
        self._window = deque(maxlen=100)  # Track recent call times

    def _add_tokens(self):
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.burst_size,
            self._tokens + elapsed * self.calls_per_second,
        )
        self._last_update = now

    def acquire(self):
        with self._lock:
            self._add_tokens()
            if self._tokens >= 1:
                self._tokens -= 1
                self._window.append(time.monotonic())
                return
            # Need to wait
            wait_time = (1 - self._tokens) / self.calls_per_second
            time.sleep(wait_time)
            self._tokens = 0
            self._window.append(time.monotonic())

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        pass

    @property
    def current_tps(self) -> float:
        """Current transactions per second over the last window."""
        now = time.monotonic()
        recent = [t for t in self._window if now - t < 1.0]
        return len(recent)
```

### Async Concurrent Fetching

```python
import asyncio
import httpx
import pandas as pd
from typing import Sequence

from alpha_search.data.provider import DataProvider, OHLCV
from alpha_search.core.types import Ticker


async def fetch_multiple(
    provider: DataProvider,
    tickers: Sequence[Ticker],
    **kwargs,
) -> dict[Ticker, OHLCV]:
    """Fetch OHLCV data for multiple tickers concurrently.
    Falls back to sequential for providers that don't support async."""
    results = {}

    async def _fetch_one(ticker: Ticker):
        try:
            ohlcv = provider.get_prices(ticker, **kwargs)
            results[ticker] = ohlcv
        except Exception as e:
            results[ticker] = e

    tasks = [_fetch_one(t) for t in tickers]
    await asyncio.gather(*tasks, return_exceptions=True)

    return results


def fetch_batch(
    provider: DataProvider,
    tickers: Sequence[Ticker],
    max_workers: int = 5,
    **kwargs,
) -> dict[Ticker, OHLCV]:
    """Synchronous wrapper for concurrent fetching with ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor

    def _fetch(ticker):
        try:
            return ticker, provider.get_prices(ticker, **kwargs)
        except Exception as e:
            return ticker, e

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for ticker, result in executor.map(_fetch, tickers):
            results[ticker] = result

    return results
```

### Data Normalization Pipeline

```python
import pandas as pd
import numpy as np
from alpha_search.data.provider import OHLCV


def normalize_ohlcv(ohlcv: OHLCV) -> OHLCV:
    """Clean and normalize raw OHLCV data. Handles common data issues:
    - Missing values (forward fill for price, 0 for volume)
    - Duplicate timestamps (keep last)
    - Non-monotonic index (sort)
    - Zero/negative prices (filter)
    """
    df = ohlcv.to_dataframe()

    # Sort by timestamp
    df = df.sort_index()

    # Remove duplicate timestamps (keep last)
    df = df[~df.index.duplicated(keep="last")]

    # Forward fill price columns, backward fill any remaining NAs at start
    price_cols = ["open", "high", "low", "close"]
    df[price_cols] = df[price_cols].ffill().bfill()

    # Zero-fill volume
    df["volume"] = df["volume"].fillna(0)

    # Remove rows where all prices are zero or negative
    df = df[(df[price_cols] > 0).all(axis=1)]

    return OHLCV(
        ticker=ohlcv.ticker,
        timestamp=pd.DatetimeIndex(df.index),
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        volume=df["volume"],
    )


def resample_ohlcv(ohlcv: OHLCV, target_freq: str) -> OHLCV:
    """Resample OHLCV data to a different frequency.

    Args:
        target_freq: Pandas frequency string ("W"=weekly, "M"=monthly)
    """
    df = ohlcv.to_dataframe()
    resampled = df.resample(target_freq).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    return OHLCV(
        ticker=ohlcv.ticker,
        timestamp=pd.DatetimeIndex(resampled.index),
        open=resampled["open"],
        high=resampled["high"],
        low=resampled["low"],
        close=resampled["close"],
        volume=resampled["volume"],
    )
```

## Responsibilities

1. Implement the DataProvider ABC for every supported data source (YFinance, Binance, and stubs for Alpaca, Kraken, IB)
2. Build and maintain the DuckDB CacheManager with configurable TTL
3. Implement rate limiting for every external API to prevent throttling/bans
4. Implement exponential backoff retry logic for all network calls
5. Normalize all incoming data to the standard OHLCV format regardless of source quirks
6. Ensure data completeness — no gaps, no NaNs, no duplicates in delivered data
7. Build async concurrent fetching for batch ticker operations
8. Expose cache statistics for monitoring and debugging
9. Document each provider's ticker format, supported frequencies, and known limitations
10. Maintain backward compatibility when extending the DataProvider interface

## Inputs

- DataProvider ABC from Architect (alpha_search/data/provider.py)
- API credentials from Pydantic Settings (YFinance free, Binance optional API key)
- Ticker symbols with source specification
- Date ranges and frequency preferences from upstream agents
- Cache configuration (TTL, database path)

## Outputs

- OHLCV objects guaranteed complete, sorted, deduplicated, NaN-free
- Cached data in DuckDB for repeated queries
- Cache statistics for monitoring
- Error reports for invalid tickers or unavailable data

## Required Files to Create or Modify

- `alpha_search/data/provider.py` — DataProvider ABC + OHLCV model (modify)
- `alpha_search/data/yfinance_provider.py` — YFinanceProvider (create)
- `alpha_search/data/binance_provider.py` — BinanceProvider (create)
- `alpha_search/data/cache.py` — CacheManager with DuckDB (create)
- `alpha_search/data/rate_limiter.py` — RateLimiter (create)
- `alpha_search/data/retry.py` — retry_with_backoff decorator (create)
- `alpha_search/data/normalize.py` — data normalization functions (create)
- `alpha_search/data/__init__.py` — module exports (modify)
- `tests/data/test_yfinance_provider.py` — unit tests (create)
- `tests/data/test_binance_provider.py` — unit tests with mocks (create)
- `tests/data/test_cache.py` — cache functionality tests (create)
- `tests/data/test_normalize.py` — normalization pipeline tests (create)

## Implementation Checklist

- [ ] Implement DataProvider ABC with OHLCV Pydantic model
- [ ] Implement YFinanceProvider with full error handling
- [ ] Implement BinanceProvider with REST API integration
- [ ] Build DuckDB CacheManager with TTL expiration
- [ ] Implement rate limiting for all external APIs
- [ ] Implement exponential backoff retry decorator
- [ ] Build data normalization pipeline (NaN handling, dedup, sorting)
- [ ] Implement async concurrent batch fetching
- [ ] Add cache statistics and health monitoring
- [ ] Write unit tests for all providers with mocked external calls
- [ ] Write integration tests with real API calls (optional, manual trigger)
- [ ] Document ticker formats per provider
- [ ] Add retry and rate limit configuration to Pydantic Settings
- [ ] Ensure 100% OHLCV validation at output boundary

## Testing Checklist

- [ ] YFinanceProvider returns valid OHLCV for AAPL with correct column types
- [ ] BinanceProvider returns valid OHLCV for BTCUSDT
- [ ] CacheManager stores and retrieves data correctly
- [ ] CacheManager respects TTL (returns None for stale data)
- [ ] RateLimiter enforces calls_per_second correctly
- [ ] Retry decorator retries exactly max_retries times then raises
- [ ] Normalization pipeline handles NaN, duplicates, and zero prices
- [ ] Batch fetching returns results for all tickers (success or error)
- [ ] All tests use mocked HTTP responses (no real API calls in CI)
- [ ] Cache stats return accurate counts and timestamps
- [ ] Invalid tickers raise clear error messages
- [ ] All providers support the full DataProvider interface ( ABC compliance)

## Definition of Done

- All data providers implement DataProvider ABC with 100% method coverage
- DuckDB cache provides sub-second query for cached data
- Rate limiting prevents any API throttling in normal usage
- Retry logic handles transient failures transparently
- Normalized OHLCV data has zero NaNs, zero duplicates, monotonic timestamps
- Batch fetching works for up to 50 tickers concurrently
- Unit tests cover all error paths with mocked dependencies
- Cache statistics are queryable for operational monitoring
- Documentation exists for each provider's capabilities and limitations

## Example Prompt

> You are the Alpha Search Data Engineering agent. Implement the YFinanceProvider following the DataProvider ABC. Use the DuckDB CacheManager for all queries. Add rate limiting at 2 requests/second and exponential backoff retry for network errors. Ensure the returned OHLCV has zero NaN values, no duplicate timestamps, and is sorted by date. Write unit tests with mocked yfinance responses achieving 90%+ coverage.