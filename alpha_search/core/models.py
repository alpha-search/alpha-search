"""Pydantic data models for Alpha Search."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator


class OHLCV(BaseModel):
    """OHLCV price data container with DataFrame storage.

    Attributes:
        timestamp: DatetimeIndex of the price data.
        open: Opening prices as numpy array.
        high: High prices as numpy array.
        low: Low prices as numpy array.
        close: Closing prices as numpy array.
        volume: Trading volume as numpy array.
    """

    model_config = {"arbitrary_types_allowed": True}

    timestamp: pd.DatetimeIndex = Field(..., description="DatetimeIndex of price data")
    open: np.ndarray = Field(..., description="Opening prices")
    high: np.ndarray = Field(..., description="High prices")
    low: np.ndarray = Field(..., description="Low prices")
    close: np.ndarray = Field(..., description="Closing prices")
    volume: np.ndarray = Field(..., description="Trading volume")
    ticker: str = Field(..., description="Ticker symbol")

    @model_validator(mode="after")
    def _validate_lengths(self) -> "OHLCV":
        """Ensure all arrays have the same length."""
        n = len(self.timestamp)
        for field in ("open", "high", "low", "close", "volume"):
            arr = getattr(self, field)
            if len(arr) != n:
                raise ValueError(
                    f"Length mismatch: timestamp has {n} rows, "
                    f"but '{field}' has {len(arr)} rows"
                )
        return self

    @model_validator(mode="after")
    def _validate_ohlc(self) -> "OHLCV":
        """Ensure OHLC relationships hold."""
        if len(self.high) > 0:
            if not np.all(self.high >= self.low):
                raise ValueError("high must be >= low")
            if not np.all(self.high >= self.open):
                raise ValueError("high must be >= open")
            if not np.all(self.high >= self.close):
                raise ValueError("high must be >= close")
            if not np.all(self.low <= self.open):
                raise ValueError("low must be <= open")
            if not np.all(self.low <= self.close):
                raise ValueError("low must be <= close")
        return self

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, v: Any) -> pd.DatetimeIndex:
        """Coerce to DatetimeIndex."""
        if isinstance(v, pd.DatetimeIndex):
            return v
        if isinstance(v, pd.Index):
            return pd.to_datetime(v)
        return pd.DatetimeIndex(v)

    @field_validator("open", "high", "low", "close", "volume", mode="before")
    @classmethod
    def _coerce_array(cls, v: Any) -> np.ndarray:
        """Coerce input to numpy array."""
        return np.asarray(v, dtype=np.float64)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to a pandas DataFrame with OHLCV columns.

        Returns:
            DataFrame with columns ['Open', 'High', 'Low', 'Close', 'Volume']
            indexed by timestamp.
        """
        return pd.DataFrame(
            {
                "Open": self.open,
                "High": self.high,
                "Low": self.low,
                "Close": self.close,
                "Volume": self.volume,
            },
            index=self.timestamp,
        )

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, ticker: str = "") -> "OHLCV":
        """Create an OHLCV instance from a DataFrame.

        Args:
            df: DataFrame with columns matching OHLCV names (case-insensitive).
            ticker: Ticker symbol for the data.

        Returns:
            OHLCV instance.
        """
        df = df.copy()
        df.columns = [c.title() for c in df.columns]
        return cls(
            timestamp=pd.DatetimeIndex(df.index),
            open=df["Open"].values,
            high=df["High"].values,
            low=df["Low"].values,
            close=df["Close"].values,
            volume=df.get("Volume", pd.Series(np.zeros(len(df)), index=df.index)).values,
            ticker=ticker,
        )

    @property
    def n_rows(self) -> int:
        """Return the number of rows of data."""
        return len(self.timestamp)

    @property
    def returns(self) -> np.ndarray:
        """Return daily returns computed from close prices."""
        return np.diff(self.close) / self.close[:-1]


class SignalData(BaseModel):
    """A quantitative trading signal as a time-indexed series.

    Attributes:
        timestamps: DatetimeIndex of signal values.
        values: Signal values (can be float or boolean-like).
        name: Human-readable name of the signal.
        metadata: Additional context (parameters, description).
    """

    model_config = {"arbitrary_types_allowed": True}

    timestamps: pd.DatetimeIndex = Field(..., description="DatetimeIndex")
    values: np.ndarray = Field(..., description="Signal values")
    name: str = Field(..., description="Signal name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra context")

    @model_validator(mode="after")
    def _validate_lengths(self) -> "SignalData":
        """Ensure timestamps and values align."""
        if len(self.timestamps) != len(self.values):
            raise ValueError(
                f"timestamps ({len(self.timestamps)}) and values "
                f"({len(self.values)}) must have the same length"
            )
        return self

    def to_series(self) -> pd.Series:
        """Return the signal as a pandas Series."""
        return pd.Series(self.values, index=self.timestamps, name=self.name)

    @classmethod
    def from_series(cls, series: pd.Series, name: str | None = None, metadata: Optional[Dict[str, Any]] = None) -> "SignalData":
        """Create SignalData from a pandas Series."""
        return cls(
            timestamps=pd.DatetimeIndex(series.index),
            values=series.values.astype(float),
            name=name or series.name or "signal",
            metadata=metadata or {},
        )


class BacktestResult(BaseModel):
    """Container for backtest output.

    Attributes:
        returns: Daily returns series.
        equity_curve: Cumulative portfolio value over time.
        positions: Daily position sizes.
        trades: DataFrame of executed trades.
        metrics: Computed performance metrics dictionary.
        costs: Daily transaction costs.
        initial_capital: Starting portfolio value.
    """

    model_config = {"arbitrary_types_allowed": True}

    returns: pd.Series = Field(..., description="Daily returns")
    equity_curve: pd.Series = Field(..., description="Cumulative equity curve")
    positions: pd.Series = Field(..., description="Daily position sizes")
    trades: pd.DataFrame = Field(..., description="Trade log")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Performance metrics")
    costs: pd.Series = Field(default_factory=lambda: pd.Series(dtype=float), description="Daily costs")
    initial_capital: float = Field(default=100000.0, description="Initial capital")
    ticker: str = Field(default="", description="Ticker symbol")

    @model_validator(mode="after")
    def _validate_index_alignment(self) -> "BacktestResult":
        """Ensure returns, equity_curve, positions, and costs share the same index."""
        idx = self.returns.index
        for attr in ("equity_curve", "positions"):
            series = getattr(self, attr)
            if len(series) > 0 and not series.index.equals(idx):
                raise ValueError(f"'{attr}' index does not align with 'returns' index")
        if len(self.costs) > 0 and not self.costs.index.equals(idx):
            raise ValueError("'costs' index does not align with 'returns' index")
        return self

    @property
    def total_return(self) -> float:
        """Compute total return from equity curve."""
        if len(self.equity_curve) < 2:
            return 0.0
        return float(self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1)

    @property
    def n_trades(self) -> int:
        """Number of round-trip trades."""
        return len(self.trades)

    def summary(self) -> str:
        """Return a human-readable backtest summary."""
        lines = [
            f"Backtest Summary for {self.ticker}",
            f"{'=' * 40}",
            f"Initial Capital: ${self.initial_capital:,.2f}",
            f"Total Return:    {self.total_return * 100:.2f}%",
            f"Trades Executed: {self.n_trades}",
            f"Backtest Period: {len(self.returns)} days",
        ]
        if self.metrics:
            lines.append("--- Metrics ---")
            for k, v in self.metrics.items():
                lines.append(f"  {k}: {v:.4f}")
        lines.append("=" * 40)
        return "\n".join(lines)


class Order(BaseModel):
    """A trade order.

    Attributes:
        id: Unique order identifier (auto-generated).
        ticker: Symbol to trade.
        side: 'BUY' or 'SELL'.
        quantity: Number of shares/contracts.
        order_type: 'MARKET' or 'LIMIT'.
        limit_price: Limit price (required for LIMIT orders).
        timestamp: Order creation time.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="Order ID")
    ticker: str = Field(..., description="Ticker symbol")
    side: str = Field(..., description="BUY or SELL")
    quantity: float = Field(..., gt=0, description="Order quantity")
    order_type: str = Field(default="MARKET", description="MARKET or LIMIT")
    limit_price: Optional[float] = Field(default=None, description="Limit price")
    timestamp: datetime = Field(default_factory=datetime.now, description="Order time")

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> str:
        v = v.upper()
        if v not in {"BUY", "SELL"}:
            raise ValueError(f"side must be 'BUY' or 'SELL', got {v}")
        return v

    @field_validator("order_type")
    @classmethod
    def _validate_order_type(cls, v: str) -> str:
        v = v.upper()
        if v not in {"MARKET", "LIMIT"}:
            raise ValueError(f"order_type must be 'MARKET' or 'LIMIT', got {v}")
        return v

    @model_validator(mode="after")
    def _validate_limit(self) -> "Order":
        if self.order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        return self

    @property
    def is_buy(self) -> bool:
        return self.side == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.side == "SELL"


class Position(BaseModel):
    """A portfolio position.

    Attributes:
        ticker: Symbol held.
        quantity: Number of shares/contracts (negative for short).
        avg_cost: Average entry cost per share.
        current_price: Last known market price.
    """

    ticker: str = Field(..., description="Ticker symbol")
    quantity: float = Field(..., description="Position quantity")
    avg_cost: float = Field(..., ge=0, description="Average cost basis")
    current_price: float = Field(default=0.0, description="Current market price")

    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """Total cost basis."""
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized profit/loss as a percentage."""
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost

    def update_price(self, new_price: float) -> "Position":
        """Return a new Position with updated current_price."""
        return self.model_copy(update={"current_price": new_price})
