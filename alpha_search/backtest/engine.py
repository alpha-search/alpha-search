"""Vectorized backtesting engine for Alpha Search."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.metrics import Metrics
from alpha_search.core.errors import BacktestError
from alpha_search.core.models import BacktestResult, Order

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Fully vectorized backtest engine.

    Given a price series and a signal series, the engine computes:

    1. Position sizes from signals (scaled to target position).
    2. Daily returns from position * price returns.
    3. Equity curve from cumulative returns.
    4. Trade log from position changes.
    5. Cost deduction from turnover.

    Example::

        engine = BacktestEngine()
        result = engine.run(prices_df, signal_series, initial_capital=100_000)
        print(result.metrics)
    """

    def __init__(self) -> None:
        self.metrics = Metrics()

    def run(
        self,
        prices: pd.DataFrame,
        signal: pd.Series,
        initial_capital: float = 100000.0,
        cost_model: Optional[CostModel] = None,
    ) -> BacktestResult:
        """Run a vectorized backtest.

        Args:
            prices: OHLCV DataFrame with at least ``'Close'`` column.
            signal: Signal values indexed by date. Positive = long,
                negative = short, zero = flat. Values may be continuous
                (position sizing) or binary (0/1).
            initial_capital: Starting portfolio value.
            cost_model: Optional :class:`CostModel` for transaction costs.

        Returns:
            :class:`BacktestResult` with returns, equity curve, trades,
            metrics, and costs.
        """
        try:
            return self._run(prices, signal, initial_capital, cost_model)
        except BacktestError:
            raise
        except Exception as exc:
            raise BacktestError(
                f"Backtest failed: {exc}", stage="run"
            ) from exc

    def _run(
        self,
        prices: pd.DataFrame,
        signal: pd.Series,
        initial_capital: float,
        cost_model: Optional[CostModel],
    ) -> BacktestResult:
        # Validate inputs
        if prices is None or prices.empty:
            raise BacktestError("prices DataFrame is empty", stage="validation")
        if "Close" not in prices.columns:
            raise BacktestError(
                "prices must contain a 'Close' column", stage="validation"
            )
        if signal is None or signal.empty:
            raise BacktestError("signal is empty", stage="validation")

        close = prices["Close"]

        # Align signal to price index (inner join - only days with both data and signal)
        aligned_signal = signal.reindex(close.index)
        aligned_signal = aligned_signal.ffill().fillna(0.0)

        # Compute daily price returns
        price_returns = close.pct_change().fillna(0.0)

        # Position sizing: signal directly maps to position
        # If signal is in [0, 1], interpret as position fraction
        # If signal has negative values, allow short positions
        position = aligned_signal.copy()
        position.name = "position"

        # Strategy returns = position(t-1) * market_return(t)
        # (position decided at close of day t-1, applied during day t)
        shifted_position = position.shift(1).fillna(0.0)
        strategy_returns = shifted_position * price_returns
        strategy_returns.name = "returns"

        # Compute costs from position changes
        costs = pd.Series(0.0, index=close.index, name="costs")
        if cost_model is not None:
            position_changes = position.diff().abs().fillna(0.0)
            costs = cost_model.apply(position_changes, close)
            # Deduct costs from returns
            # Cost as fraction of capital
            cost_fraction = costs / initial_capital
            strategy_returns = strategy_returns - cost_fraction

        # Equity curve
        cumulative_returns = (1.0 + strategy_returns).cumprod()
        equity_curve = initial_capital * cumulative_returns
        equity_curve.name = "equity"

        # Generate trade log from position changes
        trades = self._build_trade_log(position, close)

        # Compute metrics
        metrics = self.metrics.compute_all(strategy_returns, equity_curve)

        ticker = signal.name if isinstance(signal.name, str) else ""

        return BacktestResult(
            returns=strategy_returns,
            equity_curve=equity_curve,
            positions=position,
            trades=trades,
            metrics=metrics,
            costs=costs,
            initial_capital=initial_capital,
            ticker=ticker,
        )

    def _build_trade_log(
        self,
        position: pd.Series,
        close: pd.Series,
    ) -> pd.DataFrame:
        """Build a trade log from position changes (vectorized).

        A "trade" is defined as a change in position. Entries are recorded
        with direction, price, and position delta.
        """
        pos_diff = position.diff().fillna(0.0)

        # Only include days with actual position changes
        trade_mask = pos_diff != 0
        if not trade_mask.any():
            return pd.DataFrame(
                columns=["date", "direction", "price", "position_delta", "position_after"]
            )

        trades = pd.DataFrame(
            {
                "date": close.index[trade_mask],
                "direction": np.where(pos_diff[trade_mask] > 0, "BUY", "SELL"),
                "price": close[trade_mask].values,
                "position_delta": pos_diff[trade_mask].values,
                "position_after": position[trade_mask].values,
            }
        )
        return trades
