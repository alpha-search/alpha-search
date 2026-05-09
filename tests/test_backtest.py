"""Tests for the vectorised backtest engine."""

import numpy as np
import pandas as pd
import pytest

from alpha_search.backtest import BacktestEngine, CostModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prices_df(periods: int = 100, drift: float = 0.0005) -> pd.DataFrame:
    """Geometric-Brownian-Motion price DataFrame with 'Close' column."""
    rng = np.random.default_rng(42)
    returns = rng.normal(drift, 0.015, periods)
    prices = 100 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2023-01-01", periods=periods, freq="D")
    return pd.DataFrame({"Close": prices}, index=idx)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


class TestBacktestRuns:
    """Sanity checks that the engine executes without error."""

    def test_backtest_runs(self) -> None:
        """The engine returns a result object with expected attributes."""
        prices = _make_prices_df(100)
        signal = pd.Series(np.zeros(len(prices)), index=prices.index)
        # Long-only ramp
        signal.iloc[20:] = 1.0

        engine = BacktestEngine()
        result = engine.run(prices=prices, signal=signal, initial_capital=100_000)

        assert hasattr(result, "equity_curve")
        assert hasattr(result, "metrics")
        assert isinstance(result.metrics, dict)
        assert hasattr(result, "positions")
        assert hasattr(result, "trades")
        assert hasattr(result, "total_return")
        assert hasattr(result, "n_trades")


# ---------------------------------------------------------------------------
# Position behaviour
# ---------------------------------------------------------------------------


class TestBacktestLongOnly:
    """A constant +1 signal should stay fully invested."""

    def test_backtest_long_only(self) -> None:
        """All-positive signal => positions are always long."""
        prices = _make_prices_df(100, drift=0.001)
        signal = pd.Series(1.0, index=prices.index)

        engine = BacktestEngine()
        result = engine.run(prices=prices, signal=signal, initial_capital=100_000)

        # Equity should generally grow with positive drift
        assert result.equity_curve.iloc[-1] > result.equity_curve.iloc[0]
        # Positions should be 100 % invested after the first bar
        assert (result.positions.iloc[1:] == 1.0).all()


class TestBacktestCash:
    """A zero signal should produce no positions."""

    def test_backtest_cash(self) -> None:
        """Zero signal => equity stays at initial capital (minus negligible slippage)."""
        prices = _make_prices_df(100)
        signal = pd.Series(0.0, index=prices.index)

        engine = BacktestEngine()
        result = engine.run(
            prices=prices, signal=signal, initial_capital=100_000, cost_model=CostModel(0, 0)
        )

        # Equity stays flat at 100 k when there are no costs
        assert result.equity_curve.iloc[-1] == pytest.approx(100_000, abs=1.0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestBacktestMetrics:
    """Metric calculations produce reasonable magnitudes."""

    def test_backtest_metrics(self) -> None:
        """Sharpe, return, max-drawdown are present and within sensible bounds."""
        prices = _make_prices_df(252, drift=0.0008)  # ~1 year
        signal = pd.Series(1.0, index=prices.index)

        engine = BacktestEngine()
        result = engine.run(prices=prices, signal=signal, initial_capital=100_000)
        m = result.metrics

        assert "total_return" in m
        assert "sharpe_ratio" in m
        assert "max_drawdown" in m

        assert m["total_return"] > 0  # positive drift => positive return
        assert m["max_drawdown"] >= 0  # drawdown is non-negative
        assert m["max_drawdown"] <= 1.0  # cannot lose more than 100 %
        # Sharpe should be modestly positive for a drifting series
        assert m["sharpe_ratio"] > -2.0


# ---------------------------------------------------------------------------
# Transaction costs
# ---------------------------------------------------------------------------


class TestBacktestWithCosts:
    """Costs erode returns."""

    def test_backtest_with_costs(self) -> None:
        """Higher transaction costs produce lower final equity."""
        prices = _make_prices_df(100, drift=0.001)
        signal = pd.Series(0.0, index=prices.index)
        # Flip between 0 and 1 every 10 bars to generate turnover
        for i in range(0, len(signal), 20):
            signal.iloc[i : i + 10] = 1.0

        cheap = CostModel(commission=0.0001, slippage=0.0)
        expensive = CostModel(commission=0.01, slippage=0.0)

        engine = BacktestEngine()
        result_cheap = engine.run(
            prices=prices, signal=signal, initial_capital=100_000, cost_model=cheap
        )
        result_exp = engine.run(
            prices=prices, signal=signal, initial_capital=100_000, cost_model=expensive
        )

        assert result_exp.equity_curve.iloc[-1] < result_cheap.equity_curve.iloc[-1]


# ---------------------------------------------------------------------------
# Equity curve monotonicity sanity
# ---------------------------------------------------------------------------


class TestEquityCurve:
    """Properties of the equity curve time-series."""

    def test_equity_curve(self) -> None:
        """Equity is always non-decreasing when signal == 1 and prices rise."""
        # Deterministic rising price staircase
        prices = pd.DataFrame(
            {"Close": np.linspace(100, 200, 50)},
            index=pd.date_range("2023-01-01", periods=50, freq="D"),
        )
        signal = pd.Series(1.0, index=prices.index)

        engine = BacktestEngine()
        result = engine.run(
            prices=prices, signal=signal, initial_capital=100_000, cost_model=CostModel(0, 0)
        )

        # Equity should monotonically increase with a strictly rising price
        diffs = result.equity_curve.diff().dropna()
        assert (diffs >= 0).all()
        assert result.equity_curve.iloc[-1] > result.equity_curve.iloc[0]


# ---------------------------------------------------------------------------
# BacktestResult properties
# ---------------------------------------------------------------------------


class TestBacktestResult:
    """Verify computed properties on BacktestResult."""

    def test_total_return_property(self) -> None:
        """total_return property reflects equity curve growth."""
        prices = pd.DataFrame(
            {"Close": [100, 110, 120]},
            index=pd.date_range("2023-01-01", periods=3, freq="D"),
        )
        signal = pd.Series(1.0, index=prices.index)

        engine = BacktestEngine()
        result = engine.run(prices=prices, signal=signal, initial_capital=100_000)

        assert result.total_return > 0
        assert result.n_trades >= 0
