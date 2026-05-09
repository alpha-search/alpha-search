"""Tests for walk-forward analysis and cross-validation."""

import numpy as np
import pandas as pd
import pytest

from alpha_search.backtest.walk_forward import WalkForwardValidator
from alpha_search.signals import ma_crossover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prices_df(n: int = 200) -> pd.DataFrame:
    """Create an OHLCV DataFrame for testing."""
    rng = np.random.default_rng(99)
    returns = rng.normal(0.0005, 0.01, n)
    closes = 100 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    opens = closes * 0.995
    highs = closes * 1.01
    lows = closes * 0.99
    volumes = np.full(n, 1_000_000.0)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


# ---------------------------------------------------------------------------
# WalkForwardValidator.run
# ---------------------------------------------------------------------------


class TestWalkForwardRuns:
    """Correct number and shape of walk-forward splits."""

    def test_walk_forward_run(self) -> None:
        """With 200 observations, train=100 and test=20, step=20 => 5 splits."""
        prices = _make_prices_df(200)

        def _signal_func(df: pd.DataFrame) -> pd.Series:
            return ma_crossover(df["Close"], short=10, long=20)

        wfv = WalkForwardValidator()
        results = wfv.run(
            prices=prices,
            signal_func=_signal_func,
            train_size=100,
            test_size=20,
            step=20,
        )

        assert isinstance(results, pd.DataFrame)
        # With n=200, train=100, test=20, step=20:
        # test_start goes 100, 120, 140, 160, 180 → 5 splits
        assert len(results) == 5

        expected_cols = [
            "split",
            "train_start",
            "train_end",
            "test_start",
            "test_end",
            "is_total_return",
            "is_sharpe",
            "is_max_dd",
            "oos_total_return",
            "oos_sharpe",
            "oos_max_dd",
            "sharpe_degradation",
        ]
        assert list(results.columns) == expected_cols

    def test_walk_forward_not_enough_data(self) -> None:
        """Too little data raises BacktestError."""
        prices = _make_prices_df(50)
        wfv = WalkForwardValidator()

        def _signal_func(df: pd.DataFrame) -> pd.Series:
            return ma_crossover(df["Close"], short=10, long=20)

        from alpha_search.core.errors import BacktestError

        with pytest.raises(BacktestError):
            wfv.run(prices=prices, signal_func=_signal_func, train_size=100, test_size=20, step=20)


# ---------------------------------------------------------------------------
# Degradation computation
# ---------------------------------------------------------------------------


class TestWalkForwardDegradation:
    """Detect when out-of-sample performance deteriorates."""

    def test_walk_forward_degradation(self) -> None:
        """A monotonically decreasing IS/OOS ratio flags degradation."""
        wfv = WalkForwardValidator()

        is_metrics = {"sharpe_ratio": 1.5}
        oos_metrics = {"sharpe_ratio": 1.0}

        degradation = wfv.degradation(is_metrics, oos_metrics, key="sharpe_ratio")

        # 1.0 - 1.0/1.5 = 0.333...
        assert degradation > 0
        assert degradation == pytest.approx(1 / 3, abs=1e-6)

    def test_no_degradation(self) -> None:
        """When IS and OOS are equal, degradation is zero."""
        wfv = WalkForwardValidator()

        is_metrics = {"sharpe_ratio": 1.5}
        oos_metrics = {"sharpe_ratio": 1.5}

        degradation = wfv.degradation(is_metrics, oos_metrics, key="sharpe_ratio")
        assert degradation == 0.0

    def test_degradation_negative_oos(self) -> None:
        """When OOS goes negative, degradation exceeds 1."""
        wfv = WalkForwardValidator()

        is_metrics = {"sharpe_ratio": 1.0}
        oos_metrics = {"sharpe_ratio": -0.5}

        degradation = wfv.degradation(is_metrics, oos_metrics, key="sharpe_ratio")
        assert degradation > 1.0
