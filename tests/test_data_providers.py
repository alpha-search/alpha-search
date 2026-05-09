"""Tests for the data providers layer."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from alpha_search.data.cache import CacheManager
from alpha_search.data.normalizer import normalize_ohlcv
from alpha_search.data.providers import ProviderRegistry
from alpha_search.data.yfinance_provider import YFinanceProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(start: str, periods: int) -> pd.DataFrame:
    """Return a deterministic OHLCV DataFrame for testing."""
    idx = pd.date_range(start=start, periods=periods, freq="D")
    base = 100.0
    opens = base + np.arange(periods).astype(float)
    closes = opens + np.sin(np.arange(periods)) * 2
    highs = np.maximum(opens, closes) + 1.5
    lows = np.minimum(opens, closes) - 1.5
    volumes = np.full(periods, 1_000_000.0)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def _temp_file_cache() -> CacheManager:
    """Return a CacheManager backed by a temp file (avoids :memory: reconnect bug)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return CacheManager(tmp.name)


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    """Test-suite for the real provider registry."""

    def test_register_and_get(self) -> None:
        """Providers can be registered and retrieved by name."""
        registry = ProviderRegistry()
        # Prevent auto-registration from interfering
        registry._auto_registered = True

        provider = YFinanceProvider(cache=_temp_file_cache())
        registry.register(provider)

        fetched = registry.get("yfinance")
        assert fetched.name == "yfinance"

    def test_list_providers(self) -> None:
        """list_providers() returns registered names."""
        registry = ProviderRegistry()
        registry._auto_registered = True
        provider = YFinanceProvider(cache=_temp_file_cache())
        registry.register(provider)

        names = registry.list_providers()
        assert "yfinance" in names

    def test_get_missing_raises(self) -> None:
        """Getting an unregistered provider raises an error."""
        registry = ProviderRegistry()
        registry._auto_registered = True

        with pytest.raises(Exception):
            registry.get("nonexistent")


# ---------------------------------------------------------------------------
# YFinance provider (mocked)
# ---------------------------------------------------------------------------


class TestYFinanceProvider:
    """Tests for the Yahoo Finance data provider using mocked yfinance."""

    @patch("yfinance.Ticker")
    def test_yfinance_provider_mock(self, mock_ticker_cls: MagicMock) -> None:
        """Mock yfinance.Ticker and assert get_prices returns a DataFrame."""
        fixture = _make_ohlcv("2023-01-01", 30)
        ticker_instance = MagicMock()
        ticker_instance.history.return_value = fixture
        mock_ticker_cls.return_value = ticker_instance

        cache = _temp_file_cache()
        try:
            provider = YFinanceProvider(cache=cache)
            result = provider.get_prices("AAPL", start="2023-01-01", end="2023-01-31")

            mock_ticker_cls.assert_called_once_with("AAPL")
            assert isinstance(result, pd.DataFrame)
            assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
            assert len(result) == 30
        finally:
            db_path = cache.db_path
            cache.close()
            try:
                os.unlink(db_path)
            except FileNotFoundError:
                pass

    @patch("yfinance.Ticker")
    def test_yfinance_provider_uses_cache(self, mock_ticker_cls: MagicMock) -> None:
        """Second call with same params should hit cache."""
        fixture = _make_ohlcv("2023-01-01", 30)
        ticker_instance = MagicMock()
        ticker_instance.history.return_value = fixture
        mock_ticker_cls.return_value = ticker_instance

        cache = _temp_file_cache()
        try:
            provider = YFinanceProvider(cache=cache)

            # First fetch — hits yfinance
            result1 = provider.get_prices("AAPL", start="2023-01-01", end="2023-01-31")
            assert len(result1) == 30
            assert mock_ticker_cls.call_count == 1

            # Second fetch — should hit cache, not call yfinance again
            result2 = provider.get_prices("AAPL", start="2023-01-01", end="2023-01-31")
            assert len(result2) == 30
            # yfinance.Ticker should NOT have been called a second time
            assert mock_ticker_cls.call_count == 1
        finally:
            db_path = cache.db_path
            cache.close()
            try:
                os.unlink(db_path)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# OHLCV normalisation
# ---------------------------------------------------------------------------


class TestNormalizeOHLCV:
    """Test column standardisation for OHLCV data."""

    def test_normalize_ohlcv(self) -> None:
        """Columns are renamed to standard OHLCV; index is DatetimeIndex."""
        raw = pd.DataFrame(
            {
                "Date": pd.date_range("2023-01-01", periods=5),
                "OPEN": [1, 2, 3, 4, 5],
                "HIGH": [2, 3, 4, 5, 6],
                "LOW": [0, 1, 2, 3, 4],
                "CLOSE": [1.5, 2.5, 3.5, 4.5, 5.5],
                "VOLUME": [100, 200, 300, 400, 500],
                "Adj Close": [1.4, 2.4, 3.4, 4.4, 5.4],
            }
        )
        raw.set_index("Date", inplace=True)

        normalized = normalize_ohlcv(raw, source="generic")
        expected_cols = ["Open", "High", "Low", "Close", "Volume"]
        assert list(normalized.columns) == expected_cols
        assert isinstance(normalized.index, pd.DatetimeIndex)
        assert len(normalized) == 5

    def test_normalize_ohlcv_already_clean(self) -> None:
        """Normalising an already-clean DataFrame is a no-op."""
        clean = pd.DataFrame(
            {
                "Open": [1, 2],
                "High": [2, 3],
                "Low": [0, 1],
                "Close": [1.5, 2.5],
                "Volume": [100, 200],
            },
            index=pd.date_range("2023-01-01", periods=2),
        )

        result = normalize_ohlcv(clean, source="yfinance")
        pd.testing.assert_frame_equal(result, clean)

    def test_normalize_ohlcv_empty_raises(self) -> None:
        """Normalising an empty DataFrame raises ValidationError."""
        empty = pd.DataFrame()
        from alpha_search.core.errors import ValidationError

        with pytest.raises(ValidationError):
            normalize_ohlcv(empty)
