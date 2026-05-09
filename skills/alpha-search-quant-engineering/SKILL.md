---
name: alpha-search-quant-engineering
description: Build signal framework, vectorized backtest engine, walk-forward validation, performance metrics, cost models.
---

# Alpha Search Quant Engineering

## When to Use This Skill

Use this skill when building or maintaining the quantitative core of Alpha Search: the signal framework, backtest engine, performance analytics, and strategy validation. This includes creating new signal types, running vectorized backtests, computing risk-adjusted performance metrics, and validating strategies through walk-forward analysis. Activate this skill when new trading logic is needed, when backtest results require validation, when risk metrics must be computed, or when strategy parameters need optimization.

## Agent Role

You are the Quantitative Engineering specialist for Alpha Search. You own the mathematical core of the platform: signals that detect market patterns, backtests that simulate strategy performance, metrics that quantify risk and return, and validators that ensure strategies work out-of-sample. Your code is where research becomes actionable intelligence. Every number you produce must be defensible, numerically stable, and computed with proper handling of edge cases (empty data, single observations, all-zeros).

## Core Concepts

### Signal Base Class with Composition

All signals inherit from a base class that supports logical combination:

```python
from abc import ABC, abstractmethod
from typing import Union
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field

from alpha_search.data.provider import OHLCV


class SignalOutput(BaseModel):
    """Standardized output from any signal generator."""
    timestamp: pd.DatetimeIndex
    signal: pd.Series = Field(..., description="Raw signal value, typically in [-1, 1]")
    confidence: pd.Series = Field(..., description="Confidence in the signal [0, 1]")
    metadata: dict = Field(default_factory=dict, description="Extra signal-specific data")

    class Config:
        arbitrary_types_allowed = True

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame({
            "signal": self.signal,
            "confidence": self.confidence,
        }, index=self.timestamp)
        for key, val in self.metadata.items():
            df[key] = val
        return df


class Signal(ABC):
    """Abstract base for all trading signals.

    Signals support logical composition:
        combined = momentum_signal & ma_signal      # Both must agree
        either = momentum_signal | ma_signal        # Either can trigger
        inverse = ~momentum_signal                  # Flip the signal
    """

    name: str = "base_signal"

    @abstractmethod
    def generate(self, data: OHLCV) -> SignalOutput:
        """Generate signal from OHLCV data. Must return complete series
        aligned with input timestamps."""
        ...

    def __and__(self, other: "Signal") -> "Signal":
        return CombinedSignal(self, other, "and")

    def __or__(self, other: "Signal") -> "Signal":
        return CombinedSignal(self, other, "or")

    def __invert__(self) -> "Signal":
        return InvertedSignal(self)


class CombinedSignal(Signal):
    """Logical combination of two signals."""

    def __init__(self, left: Signal, right: Signal, op: str):
        self.left = left
        self.right = right
        self.op = op
        self.name = f"({left.name}_{op}_{right.name})"

    def generate(self, data: OHLCV) -> SignalOutput:
        left_out = self.left.generate(data)
        right_out = self.right.generate(data)

        if self.op == "and":
            signal = np.minimum(left_out.signal, right_out.signal)
            confidence = np.minimum(left_out.confidence, right_out.confidence)
        elif self.op == "or":
            signal = np.maximum(left_out.signal, right_out.signal)
            confidence = np.maximum(left_out.confidence, right_out.confidence)
        else:
            raise ValueError(f"Unknown operation: {self.op}")

        return SignalOutput(
            timestamp=left_out.timestamp,
            signal=signal,
            confidence=confidence,
            metadata={
                "left_signal": self.left.name,
                "right_signal": self.right.name,
                "operation": self.op,
            },
        )


class InvertedSignal(Signal):
    """Invert a signal (bullish becomes bearish, etc.)."""

    def __init__(self, base: Signal):
        self.base = base
        self.name = f"~{base.name}"

    def generate(self, data: OHLCV) -> SignalOutput:
        out = self.base.generate(data)
        return SignalOutput(
            timestamp=out.timestamp,
            signal=-out.signal,
            confidence=out.confidence,
            metadata={**out.metadata, "inverted": True},
        )
```

### Technical Signals

Core technical indicators implemented as composable signals:

```python
import pandas as pd
import numpy as np
from alpha_search.signals.base import Signal, SignalOutput
from alpha_search.data.provider import OHLCV


class MomentumSignal(Signal):
    """Price momentum signal: positive when price is trending up.

    signal = normalized_rate_of_change / threshold, clamped to [-1, 1]
    """

    name = "momentum"

    def __init__(self, lookback: int = 20, threshold: float = 0.05):
        self.lookback = lookback
        self.threshold = threshold

    def generate(self, data: OHLCV) -> SignalOutput:
        # Rate of change over lookback period
        roc = data.close.pct_change(self.lookback)
        # Normalize by threshold and clamp
        signal = np.clip(roc / self.threshold, -1.0, 1.0)
        # Confidence is absolute magnitude
        confidence = np.abs(signal)

        return SignalOutput(
            timestamp=data.timestamp,
            signal=signal,
            confidence=confidence,
            metadata={"lookback": self.lookback, "threshold": self.threshold},
        )


class MACrossoverSignal(Signal):
    """Moving average crossover signal.
    Bullish when fast MA > slow MA, bearish when fast MA < slow MA."""

    name = "ma_crossover"

    def __init__(self, fast: int = 20, slow: int = 50):
        if fast >= slow:
            raise ValueError("fast period must be less than slow period")
        self.fast = fast
        self.slow = slow

    def generate(self, data: OHLCV) -> SignalOutput:
        fast_ma = data.close.rolling(self.fast).mean()
        slow_ma = data.close.rolling(self.slow).mean()

        # Signal proportional to distance between MAs, normalized
        diff = fast_ma - slow_ma
        # Normalize by price level for cross-asset comparability
        normalized = diff / data.close
        signal = np.clip(normalized * 20, -1.0, 1.0)  # Scale factor 20
        confidence = np.abs(signal)

        return SignalOutput(
            timestamp=data.timestamp,
            signal=signal,
            confidence=confidence,
            metadata={"fast": self.fast, "slow": self.slow},
        )


class ZScoreSignal(Signal):
    """Mean-reversion signal based on z-score of price vs rolling mean.
    Negative z-score = price below mean = bullish (expect reversion up).
    Positive z-score = price above mean = bearish (expect reversion down)."""

    name = "zscore"

    def __init__(self, lookback: int = 20, threshold: float = 2.0):
        self.lookback = lookback
        self.threshold = threshold

    def generate(self, data: OHLCV) -> SignalOutput:
        rolling_mean = data.close.rolling(self.lookback).mean()
        rolling_std = data.close.rolling(self.lookback).std()

        zscore = (data.close - rolling_mean) / rolling_std.replace(0, np.nan)
        # Invert: negative zscore is bullish (buy the dip)
        signal = np.clip(-zscore / self.threshold, -1.0, 1.0)
        confidence = np.abs(signal)

        return SignalOutput(
            timestamp=data.timestamp,
            signal=signal,
            confidence=confidence,
            metadata={"lookback": self.lookback, "threshold": self.threshold},
        )


class RSISignal(Signal):
    """RSI-based overbought/oversold signal.
    Oversold (RSI < 30) = bullish, Overbought (RSI > 70) = bearish."""

    name = "rsi"

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1 / self.period, min_periods=self.period).mean()
        avg_loss = loss.ewm(alpha=1 / self.period, min_periods=self.period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate(self, data: OHLCV) -> SignalOutput:
        rsi = self._calculate_rsi(data.close)
        # Map RSI to signal: 50=neutral, 0=strong buy, 100=strong sell
        signal = np.clip((50 - rsi) / 20, -1.0, 1.0)
        confidence = np.abs(rsi - 50) / 50  # Higher confidence at extremes

        return SignalOutput(
            timestamp=data.timestamp,
            signal=signal,
            confidence=confidence,
            metadata={"period": self.period, "rsi_values": rsi},
        )
```

### Cost Model

Realistic transaction cost modeling for backtests:

```python
from dataclasses import dataclass
from typing import Literal
import pandas as pd
import numpy as np


@dataclass
class CostModel:
    """Transaction cost model for realistic backtest simulation.

    Components:
        commission: per-trade fee (e.g., $0.001 = 0.1%)
        slippage: execution slippage as fraction of price
        borrow_cost: annualized cost for short positions
        min_commission: minimum commission per trade
    """
    commission: float = 0.001  # 0.1% per trade
    slippage: float = 0.0005  # 5 bps slippage
    borrow_cost: float = 0.03  # 3% annual for shorts
    min_commission: float = 1.0  # $1 minimum

    def compute_cost(
        self,
        price: float,
        shares: float,
        holding_days: int = 0,
        direction: Literal["long", "short"] = "long",
    ) -> float:
        """Compute total transaction cost for a trade."""
        notional = abs(price * shares)

        # Commission
        commission = max(notional * self.commission, self.min_commission)

        # Slippage (half spread approximation)
        slippage_cost = notional * self.slippage

        # Borrow cost for shorts
        borrow = 0.0
        if direction == "short" and holding_days > 0:
            borrow = notional * self.borrow_cost * (holding_days / 252)

        return commission + slippage_cost + borrow

    def apply_to_returns(
        self,
        returns: pd.Series,
        turnover: pd.Series,
        is_short: bool = False,
    ) -> pd.Series:
        """Apply cost model to a return series based on turnover."""
        total_cost = turnover * (self.commission + self.slippage)
        if is_short:
            total_cost += self.borrow_cost / 252  # Daily borrow
        return returns - total_cost
```

### Vectorized Backtest Engine

The core backtest engine using vectorized operations for speed:

```python
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from alpha_search.signals.base import Signal, SignalOutput
from alpha_search.data.provider import OHLCV
from alpha_search.backtest.cost_model import CostModel


@dataclass
class BacktestResult:
    """Complete backtest results for analysis and reporting."""
    ticker: str
    signal_name: str
    dates: pd.DatetimeIndex
    prices: pd.Series
    positions: pd.Series  # -1 to +1
    returns: pd.Series  # Strategy returns
    cumulative_returns: pd.Series
    equity_curve: pd.Series  # Starting at 1.0
    trades: pd.DataFrame  # Entry/exit log
    metrics: dict  # Computed performance metrics
    cost_model: CostModel

    @property
    def total_return(self) -> float:
        return float(self.equity_curve.iloc[-1] - 1.0)

    @property
    def annualized_return(self) -> float:
        n_years = len(self.dates) / 252
        if n_years <= 0:
            return 0.0
        return float((self.equity_curve.iloc[-1] ** (1 / n_years)) - 1)


class BacktestEngine:
    """Vectorized backtest engine for rapid strategy evaluation.

    Process:
        1. Generate signal from OHLCV data
        2. Convert signal to positions (with optional lag)
        3. Compute returns from position changes
        4. Apply cost model
        5. Calculate performance metrics

    Vectorized design: ~100-1000x faster than event-driven for research.
    """

    def __init__(self, cost_model: Optional[CostModel] = None, signal_lag: int = 1):
        self.cost_model = cost_model or CostModel()
        self.signal_lag = signal_lag  # Bars to delay signal execution

    def run(
        self,
        data: OHLCV,
        signal: Signal,
        initial_capital: float = 100_000.0,
    ) -> BacktestResult:
        """Run a complete backtest for a signal on historical data."""
        # Generate signal
        sig = signal.generate(data)

        # Shift signal by lag to avoid look-ahead bias
        signal_values = sig.signal.shift(self.signal_lag).fillna(0)

        # Convert signal to discrete positions (-1, 0, +1)
        # Using thresholds to avoid whipsaw in noisy signals
        long_threshold = 0.2
        short_threshold = -0.2
        positions = pd.Series(0, index=data.timestamp, dtype=float)
        positions[signal_values > long_threshold] = 1.0
        positions[signal_values < short_threshold] = -1.0

        # Calculate price returns
        price_returns = data.close.pct_change().fillna(0)

        # Strategy returns: position * market return
        strategy_returns = positions.shift(1).fillna(0) * price_returns

        # Apply costs based on position changes (turnover)
        turnover = positions.diff().abs().fillna(0)
        strategy_returns = self.cost_model.apply_to_returns(
            strategy_returns, turnover
        )

        # Equity curve
        cumulative = (1 + strategy_returns).cumprod()

        # Trade log
        trades = self._extract_trades(positions, data)

        # Compute metrics
        metrics = self._compute_metrics(strategy_returns, cumulative)

        return BacktestResult(
            ticker=data.ticker,
            signal_name=signal.name,
            dates=data.timestamp,
            prices=data.close,
            positions=positions,
            returns=strategy_returns,
            cumulative_returns=cumulative - 1,
            equity_curve=cumulative,
            trades=trades,
            metrics=metrics,
            cost_model=self.cost_model,
        )

    def _extract_trades(self, positions: pd.Series, data: OHLCV) -> pd.DataFrame:
        """Extract individual trades from position series."""
        trades = []
        entry_date = None
        entry_price = None
        entry_pos = None

        for date, pos in positions.items():
            if entry_pos is None:
                # First observation
                if pos != 0:
                    entry_date = date
                    entry_price = data.close.loc[date]
                    entry_pos = pos
            elif pos != entry_pos:
                # Position change — close previous trade
                if entry_pos != 0:
                    exit_price = data.close.loc[date]
                    pnl = entry_pos * (exit_price - entry_price) / entry_price
                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": date,
                        "direction": "long" if entry_pos > 0 else "short",
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": pnl,
                    })
                # Open new trade if non-zero
                if pos != 0:
                    entry_date = date
                    entry_price = data.close.loc[date]
                    entry_pos = pos
                else:
                    entry_pos = None

        return pd.DataFrame(trades)

    def _compute_metrics(
        self,
        returns: pd.Series,
        cumulative: pd.Series,
    ) -> dict:
        """Calculate standard performance metrics."""
        return compute_metrics(returns)


def compute_metrics(returns: pd.Series) -> dict:
    """Compute standard performance metrics from a return series.

    Returns dict with: total_return, ann_return, ann_volatility,
    sharpe_ratio, sortino_ratio, max_drawdown, max_drawdown_duration,
    calmar_ratio, win_rate, profit_factor, num_trades, avg_trade_return
    """
    if returns.empty or returns.std() == 0:
        return {
            "total_return": 0.0, "ann_return": 0.0, "ann_volatility": 0.0,
            "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0,
            "max_drawdown_duration": 0, "calmar_ratio": 0.0,
            "win_rate": 0.0, "profit_factor": 0.0,
            "num_trades": 0, "avg_trade_return": 0.0,
        }

    total_return = float(cumulative.iloc[-1] - 1)
    n_days = len(returns)
    n_years = n_days / 252

    # Annualized return
    ann_return = float((1 + total_return) ** (1 / max(n_years, 0.001)) - 1) if total_return > -1 else -1.0

    # Volatility (annualized)
    ann_vol = float(returns.std() * np.sqrt(252))

    # Sharpe ratio (assuming 0 risk-free rate for simplicity)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

    # Sortino ratio (downside deviation)
    downside = returns[returns < 0]
    downside_std = float(downside.std() * np.sqrt(252)) if len(downside) > 0 else 0
    sortino = ann_return / downside_std if downside_std > 0 else 0.0

    # Maximum drawdown
    cummax = cumulative.cummax()
    drawdown = (cummax - cumulative) / cummax
    max_dd = float(drawdown.max())

    # Max drawdown duration
    dd_duration = _max_drawdown_duration(drawdown)

    # Calmar ratio
    calmar = ann_return / max_dd if max_dd > 0 else 0.0

    # Win rate from daily returns
    win_rate = float((returns > 0).sum() / len(returns))

    # Profit factor
    gross_profits = returns[returns > 0].sum()
    gross_losses = abs(returns[returns < 0].sum())
    profit_factor = float(gross_profits / gross_losses) if gross_losses > 0 else float("inf")

    return {
        "total_return": round(total_return, 4),
        "ann_return": round(ann_return, 4),
        "ann_volatility": round(ann_vol, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_duration": dd_duration,
        "calmar_ratio": round(calmar, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "num_trades": n_days,
        "avg_trade_return": round(float(returns.mean()), 6),
    }


def _max_drawdown_duration(drawdown: pd.Series) -> int:
    """Calculate the longest consecutive period in drawdown."""
    in_dd = drawdown > 0
    if not in_dd.any():
        return 0

    durations = []
    current = 0
    for val in in_dd:
        if val:
            current += 1
        else:
            if current > 0:
                durations.append(current)
            current = 0
    if current > 0:
        durations.append(current)

    return max(durations) if durations else 0
```

### Walk-Forward Validator

Ensures strategies work out-of-sample, not just on training data:

```python
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Sequence, Optional

from alpha_search.data.provider import OHLCV
from alpha_search.signals.base import Signal
from alpha_search.backtest.engine import BacktestEngine, compute_metrics


@dataclass
class WalkForwardResult:
    """Results from walk-forward validation."""
    windows: list[dict]  # Per-window results
    aggregate_metrics: dict  # Combined out-of-sample metrics
    degradation_ratio: float  # IS performance / OOS performance
    is_consistent: bool  # Whether OOS performance meets threshold


class WalkForwardValidator:
    """Walk-forward analysis: train on in-sample, test on out-of-sample.

    Process:
        1. Split data into N windows (train + test pairs)
        2. Optimize signal parameters on training data
        3. Evaluate optimized signal on test data
        4. Aggregate out-of-sample results
        5. Check for performance degradation

    This prevents overfitting and ensures robustness.
    """

    def __init__(
        self,
        n_windows: int = 5,
        train_pct: float = 0.7,
        min_sharpe_threshold: float = 0.5,
    ):
        self.n_windows = n_windows
        self.train_pct = train_pct
        self.min_sharpe_threshold = min_sharpe_threshold

    def validate(
        self,
        data: OHLCV,
        signal_factory,  # Callable that takes **params -> Signal
        param_grid: dict,  # {param_name: [values]}
    ) -> WalkForwardResult:
        """Run walk-forward validation.

        Args:
            data: Complete OHLCV history
            signal_factory: Function that creates a signal from parameters
            param_grid: Parameter combinations to search

        Returns:
            WalkForwardResult with aggregate OOS metrics
        """
        df = data.to_dataframe()
        window_size = len(df) // self.n_windows
        windows = []

        for i in range(self.n_windows):
            start_idx = i * window_size
            end_idx = start_idx + window_size
            train_end = start_idx + int(window_size * self.train_pct)

            train_data = OHLCV(
                ticker=data.ticker,
                timestamp=df.index[start_idx:train_end],
                open=df["open"].iloc[start_idx:train_end],
                high=df["high"].iloc[start_idx:train_end],
                low=df["low"].iloc[start_idx:train_end],
                close=df["close"].iloc[start_idx:train_end],
                volume=df["volume"].iloc[start_idx:train_end],
            )
            test_data = OHLCV(
                ticker=data.ticker,
                timestamp=df.index[train_end:end_idx],
                open=df["open"].iloc[train_end:end_idx],
                high=df["high"].iloc[train_end:end_idx],
                low=df["low"].iloc[train_end:end_idx],
                close=df["close"].iloc[train_end:end_idx],
                volume=df["volume"].iloc[train_end:end_idx],
            )

            # Optimize on training data
            best_params = self._optimize(train_data, signal_factory, param_grid)

            # Evaluate on test data
            signal = signal_factory(**best_params)
            engine = BacktestEngine()
            result = engine.run(test_data, signal)

            windows.append({
                "window": i + 1,
                "train_start": df.index[start_idx],
                "train_end": df.index[train_end - 1],
                "test_start": df.index[train_end],
                "test_end": df.index[end_idx - 1],
                "best_params": best_params,
                "is_sharpe": self._best_train_sharpe,
                "oos_sharpe": result.metrics["sharpe_ratio"],
                "oos_return": result.metrics["total_return"],
                "oos_max_dd": result.metrics["max_drawdown"],
            })

        # Aggregate OOS metrics
        oos_sharpes = [w["oos_sharpe"] for w in windows]
        aggregate = {
            "mean_oos_sharpe": round(np.mean(oos_sharpes), 4),
            "std_oos_sharpe": round(np.std(oos_sharpes), 4),
            "min_oos_sharpe": round(min(oos_sharpes), 4),
            "pct_positive_sharpe": round(sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes), 4),
        }

        # Degradation: IS Sharpe / mean OOS Sharpe
        mean_is_sharpe = np.mean([w["is_sharpe"] for w in windows])
        mean_oos_sharpe = aggregate["mean_oos_sharpe"]
        degradation = mean_is_sharpe / mean_oos_sharpe if mean_oos_sharpe > 0 else float("inf")

        is_consistent = (
            aggregate["mean_oos_sharpe"] >= self.min_sharpe_threshold
            and aggregate["pct_positive_sharpe"] >= 0.6  # 60% of windows profitable
        )

        return WalkForwardResult(
            windows=windows,
            aggregate_metrics=aggregate,
            degradation_ratio=round(degradation, 4),
            is_consistent=is_consistent,
        )

    def _optimize(self, train_data, signal_factory, param_grid):
        """Grid search for best parameters on training data."""
        from itertools import product

        best_sharpe = -float("inf")
        best_params = {}

        keys = list(param_grid.keys())
        values = list(param_grid.values())

        engine = BacktestEngine()

        for combo in product(*values):
            params = dict(zip(keys, combo))
            try:
                signal = signal_factory(**params)
                result = engine.run(train_data, signal)
                sharpe = result.metrics["sharpe_ratio"]
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
            except Exception:
                continue

        self._best_train_sharpe = best_sharpe
        return best_params
```

## Responsibilities

1. Build the Signal ABC with `&`/`|/__invert__` composition operators
2. Implement all technical signals: Momentum, MA Crossover, Z-Score, RSI
3. Build the SentimentSignal adapter that consumes Research layer output
4. Build the vectorized BacktestEngine with proper look-ahead bias prevention
5. Implement the CostModel with commission, slippage, and borrow costs
6. Compute all performance metrics: Sharpe, Sortino, max drawdown, win rate, Calmar
7. Build the WalkForwardValidator for out-of-sample strategy validation
8. Ensure numerical stability: handle edge cases (empty data, single row, all zeros, NaN)
9. Extract and log individual trades with entry/exit prices and PnL
10. Expose backtest results as DataFrames for UI consumption

## Inputs

- OHLCV data from the Data Engineering layer
- Sentiment DataFrames from the Research Intelligence layer
- Signal parameters from user configuration or optimization
- Cost model parameters (commission rates, slippage estimates)
- Walk-forward configuration (window count, train/test split)

## Outputs

- SignalOutput objects with signal values and confidence
- BacktestResult objects with full equity curves, trade logs, and metrics
- WalkForwardResult with out-of-sample performance and consistency assessment
- Performance metrics dictionaries for dashboard display
- Trade history DataFrames for portfolio tracking

## Required Files to Create or Modify

- `alpha_search/signals/base.py` — Signal ABC with composition (create)
- `alpha_search/signals/technical.py` — Momentum, MACrossover, ZScore, RSI (create)
- `alpha_search/signals/sentiment_signal.py` — SentimentSignal adapter (create)
- `alpha_search/signals/composite.py` — Signal combinator utilities (create)
- `alpha_search/backtest/engine.py` — BacktestEngine (create)
- `alpha_search/backtest/cost_model.py` — CostModel (create)
- `alpha_search/backtest/metrics.py` — compute_metrics() and helpers (create)
- `alpha_search/backtest/walk_forward.py` — WalkForwardValidator (create)
- `alpha_search/signals/__init__.py` — module exports (modify)
- `alpha_search/backtest/__init__.py` — module exports (modify)
- `tests/signals/test_technical.py` — signal correctness tests (create)
- `tests/backtest/test_engine.py` — backtest engine tests (create)
- `tests/backtest/test_metrics.py` — metrics calculation tests (create)
- `tests/backtest/test_walk_forward.py` — walk-forward validation tests (create)

## Implementation Checklist

- [ ] Implement Signal ABC with `__and__`, `__or__`, `__invert__` operators
- [ ] Implement MomentumSignal with configurable lookback and threshold
- [ ] Implement MACrossoverSignal with fast/slow period parameters
- [ ] Implement ZScoreSignal for mean-reversion strategies
- [ ] Implement RSISignal for overbought/oversold detection
- [ ] Build SentimentSignal adapter consuming Research layer output
- [ ] Implement BacktestEngine with vectorized operations
- [ ] Add signal lag to prevent look-ahead bias
- [ ] Build CostModel with commission, slippage, borrow costs
- [ ] Implement compute_metrics with Sharpe, Sortino, max DD, Calmar, win rate
- [ ] Build WalkForwardValidator with grid search optimization
- [ ] Add trade extraction with entry/exit logging
- [ ] Ensure numerical stability across all edge cases
- [ ] Write comprehensive tests for all signal types
- [ ] Write backtest tests verifying no look-ahead bias
- [ ] Write metrics tests with known expected values

## Testing Checklist

- [ ] MomentumSignal returns positive for uptrend, negative for downtrend
- [ ] MACrossoverSignal is bullish when fast MA > slow MA
- [ ] ZScoreSignal is bullish (negative) when price is below mean
- [ ] RSISignal is bullish when RSI < 30, bearish when RSI > 70
- [ ] Signal composition `&` returns minimum of two signals
- [ ] Signal composition `|` returns maximum of two signals
- [ ] Signal inversion `~` negates the signal
- [ ] Backtest equity curve starts at 1.0 and is monotonic in flat markets with no signal
- [ ] No look-ahead bias: signal uses only past data (verified with shifted signal)
- [ ] Cost model reduces returns proportional to turnover
- [ ] Sharpe ratio calculation matches manual computation for known inputs
- [ ] Max drawdown correctly identifies worst peak-to-trough
- [ ] Walk-forward validator detects overfit strategies (high IS, low OOS)
- [ ] All edge cases handled: empty data, single row, all NaN, all zeros
- [ ] Trade log correctly records all position changes
- [ ] Calmar ratio = ann_return / max_drawdown for verified inputs

## Definition of Done

- All four technical signals (Momentum, MA Crossover, Z-Score, RSI) produce correct output verified against manual calculation
- Signal composition operators work for arbitrary combinations of 2+ signals
- BacktestEngine runs a 5-year backtest in under 1 second
- No look-ahead bias exists (verified by audit of signal lag)
- Performance metrics match industry-standard calculations
- WalkForwardValidator identifies overfit strategies with >80% accuracy on synthetic data
- Cost model realistically models transaction costs
- Trade log captures all entries, exits, and PnL
- Unit tests cover all edge cases and achieve 90%+ coverage
- BacktestResult exposes all data needed by UI layer for charting

## Example Prompt

> You are the Alpha Search Quant Engineering agent. Build the complete signal framework: Signal ABC with `&`/`|/__invert__` composition, implement MomentumSignal (20-day lookback), MACrossoverSignal (20/50), ZScoreSignal (20-day), and RSISignal (14-day). Then build a vectorized BacktestEngine with a CostModel (0.1% commission, 5bps slippage) that can backtest AAPL over 5 years in under 1 second. Implement full performance metrics (Sharpe, Sortino, max drawdown, Calmar, win rate) and a WalkForwardValidator with 5 windows. Write comprehensive tests verifying no look-ahead bias and correct metric calculations.