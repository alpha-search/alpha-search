---
name: alpha-search-execution-gateway
description: Build paper trading simulator and live execution gateway — broker adapters, position tracking, risk controls.
---

# Alpha Search Execution Gateway

## When to Use This Skill

Use this skill when building or maintaining the order execution and portfolio tracking layer of Alpha Search. This includes the paper trading simulator for strategy validation, broker adapter interfaces for live connectivity, position and PNL tracking, and risk control enforcement. Activate this skill when the Quant Engineering layer has validated signals and needs realistic order simulation, when live broker integration is requested, or when risk limits need configuration.

**CRITICAL SAFETY RULE**: No live trading (real money) is enabled by default. All execution starts in paper mode. Live trading requires explicit user opt-in with risk acknowledgement.

## Agent Role

You are the Execution Gateway specialist for Alpha Search. You build the bridge between research signals and market orders. Your PaperTrader lets users validate strategies risk-free. Your BrokerAdapters provide the path to live execution when users are ready. Your RiskControls prevent catastrophic losses. You own every line of code that could move money — which means you take safety, correctness, and defensive programming more seriously than any other agent.

## Core Concepts

### PaperTrader: Risk-Free Strategy Validation

The paper trading simulator is the primary execution mode. It tracks positions, orders, fills, and PNL without real capital at risk:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal, Sequence
from enum import Enum
import pandas as pd
import numpy as np

from alpha_search.core.types import Ticker
from alpha_search.backtest.engine import BacktestResult


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Order:
    """Represents a single order in the system."""
    id: str
    ticker: Ticker
    side: OrderSide
    order_type: OrderType
    quantity: float
    status: OrderStatus = OrderStatus.PENDING
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    commission: float = 0.0


@dataclass
class Position:
    """Current position in a security."""
    ticker: Ticker
    side: PositionSide
    quantity: float
    avg_entry_price: float
    market_price: float
    unrealized_pnl: float
    realized_pnl: float
    opened_at: datetime = field(default_factory=datetime.now)

    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl

    @property
    def pnl_pct(self) -> float:
        if self.avg_entry_price == 0:
            return 0.0
        return (self.market_price - self.avg_entry_price) / self.avg_entry_price


@dataclass
class Portfolio:
    """Complete portfolio snapshot."""
    cash: float
    positions: dict[Ticker, Position]
    total_equity: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_exposure(self) -> float:
        return sum(abs(p.market_value) for p in self.positions.values())

    @property
    def net_exposure(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def gross_leverage(self) -> float:
        return self.total_exposure / self.total_equity if self.total_equity > 0 else 0.0

    @property
    def net_leverage(self) -> float:
        return self.net_exposure / self.total_equity if self.total_equity > 0 else 0.0


class PaperTrader:
    """Paper trading simulator for risk-free strategy validation.

    Tracks virtual cash, positions, orders, and fills. Simulates
    market orders at current price with configurable slippage.

    SAFETY: PaperTrader never connects to real brokers.
    All orders are simulated internally.
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_rate: float = 0.001,
        slippage: float = 0.0005,
        allow_short: bool = True,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.allow_short = allow_short

        self.positions: dict[Ticker, Position] = {}
        self.orders: list[Order] = []
        self.trade_history: list[dict] = []
        self.equity_curve: list[dict] = []

        self._order_counter = 0

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"paper_{self._order_counter:06d}"

    def submit_order(
        self,
        ticker: Ticker,
        side: OrderSide,
        quantity: float,
        current_price: float,
        order_type: OrderType = OrderType.MARKET,
    ) -> Order:
        """Submit an order for simulated execution.

        Market orders fill immediately at current_price +/- slippage.
        """
        if quantity <= 0:
            raise ValueError(f"Order quantity must be positive, got {quantity}")

        order = Order(
            id=self._next_order_id(),
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
        )

        if order_type == OrderType.MARKET:
            self._fill_market_order(order, current_price)
        else:
            # Limit/stop orders tracked for later fill
            self.orders.append(order)

        return order

    def _fill_market_order(self, order: Order, current_price: float):
        """Simulate market order fill with slippage."""
        # Apply slippage: buy higher, sell lower
        if order.side == OrderSide.BUY:
            fill_price = current_price * (1 + self.slippage)
        else:
            fill_price = current_price * (1 - self.slippage)

        commission = fill_price * order.quantity * self.commission_rate
        total_cost = fill_price * order.quantity + commission

        # Check buying power for buys
        if order.side == OrderSide.BUY and total_cost > self.cash:
            order.status = OrderStatus.REJECTED
            self.orders.append(order)
            return

        order.filled_price = fill_price
        order.filled_at = datetime.now()
        order.commission = commission
        order.status = OrderStatus.FILLED
        self.orders.append(order)

        # Update cash
        if order.side == OrderSide.BUY:
            self.cash -= total_cost
        else:
            self.cash += (fill_price * order.quantity - commission)

        # Update position
        self._update_position(order, fill_price)

        # Record trade
        self.trade_history.append({
            "order_id": order.id,
            "ticker": order.ticker,
            "side": order.side.value,
            "quantity": order.quantity,
            "price": fill_price,
            "commission": commission,
            "timestamp": order.filled_at,
        })

    def _update_position(self, order: Order, fill_price: float):
        """Update position after a fill."""
        pos = self.positions.get(order.ticker)

        if pos is None or pos.side == PositionSide.FLAT:
            # New position
            side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
            self.positions[order.ticker] = Position(
                ticker=order.ticker,
                side=side,
                quantity=order.quantity,
                avg_entry_price=fill_price,
                market_price=fill_price,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
            )
            return

        # Existing position
        if order.side == OrderSide.BUY and pos.side == PositionSide.LONG:
            # Adding to long
            total_cost = (pos.avg_entry_price * pos.quantity) + (fill_price * order.quantity)
            pos.quantity += order.quantity
            pos.avg_entry_price = total_cost / pos.quantity

        elif order.side == OrderSide.SELL and pos.side == PositionSide.SHORT:
            # Adding to short
            total_cost = (pos.avg_entry_price * pos.quantity) + (fill_price * order.quantity)
            pos.quantity += order.quantity
            pos.avg_entry_price = total_cost / pos.quantity

        elif order.side == OrderSide.SELL and pos.side == PositionSide.LONG:
            # Reducing or closing long
            close_qty = min(order.quantity, pos.quantity)
            pnl = (fill_price - pos.avg_entry_price) * close_qty
            pos.realized_pnl += pnl - order.commission
            pos.quantity -= close_qty
            if pos.quantity <= 0:
                pos.side = PositionSide.FLAT
                pos.quantity = 0

        elif order.side == OrderSide.BUY and pos.side == PositionSide.SHORT:
            # Reducing or closing short
            close_qty = min(order.quantity, pos.quantity)
            pnl = (pos.avg_entry_price - fill_price) * close_qty
            pos.realized_pnl += pnl - order.commission
            pos.quantity -= close_qty
            if pos.quantity <= 0:
                pos.side = PositionSide.FLAT
                pos.quantity = 0

    def update_prices(self, prices: dict[Ticker, float]):
        """Update market prices and recalculate PNL."""
        for ticker, price in prices.items():
            if ticker in self.positions:
                pos = self.positions[ticker]
                pos.market_price = price
                if pos.side == PositionSide.LONG:
                    pos.unrealized_pnl = (price - pos.avg_entry_price) * pos.quantity
                elif pos.side == PositionSide.SHORT:
                    pos.unrealized_pnl = (pos.avg_entry_price - price) * pos.quantity

        # Record equity snapshot
        total_equity = self.cash + sum(
            p.market_value for p in self.positions.values()
        )
        self.equity_curve.append({
            "timestamp": datetime.now(),
            "cash": self.cash,
            "equity": total_equity,
            "unrealized_pnl": sum(p.unrealized_pnl for p in self.positions.values()),
            "realized_pnl": sum(p.realized_pnl for p in self.positions.values()),
        })

    def get_portfolio(self) -> Portfolio:
        """Get current portfolio snapshot."""
        total_equity = self.cash + sum(
            p.market_value for p in self.positions.values()
        )
        return Portfolio(
            cash=self.cash,
            positions=self.positions.copy(),
            total_equity=total_equity,
            total_unrealized_pnl=sum(p.unrealized_pnl for p in self.positions.values()),
            total_realized_pnl=sum(p.realized_pnl for p in self.positions.values()),
        )

    def get_equity_curve_df(self) -> pd.DataFrame:
        """Return equity curve as DataFrame for charting."""
        return pd.DataFrame(self.equity_curve)

    def reset(self):
        """Reset all state to initial values."""
        self.cash = self.initial_cash
        self.positions.clear()
        self.orders.clear()
        self.trade_history.clear()
        self.equity_curve.clear()
        self._order_counter = 0
```

### BrokerAdapter Abstract Base Class

Interface for live broker connectivity (stubs for supported brokers):

```python
from abc import ABC, abstractmethod
from typing import Optional, Sequence
from datetime import datetime

from alpha_search.execution.paper_trader import Order, OrderSide, OrderType, OrderStatus, Position, Portfolio


class BrokerAdapter(ABC):
    """Abstract base for all broker integrations.

    All broker adapters must implement this interface for unified execution.
    No real trading without explicit user opt-in.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Human-readable broker name."""
        ...

    @property
    @abstractmethod
    def is_paper(self) -> bool:
        """True if connected to paper/sandbox environment."""
        ...

    @abstractmethod
    def connect(self, credentials: dict) -> bool:
        """Establish connection to broker. Return True on success."""
        ...

    @abstractmethod
    def disconnect(self):
        """Close broker connection."""
        ...

    @abstractmethod
    def submit_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> str:
        """Submit an order. Returns broker order ID."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""
        ...

    @abstractmethod
    def get_positions(self) -> Sequence[Position]:
        """Get all current positions."""
        ...

    @abstractmethod
    def get_portfolio(self) -> Portfolio:
        """Get current portfolio snapshot."""
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Check status of an order."""
        ...

    @abstractmethod
    def get_account_value(self) -> float:
        """Get total account value (cash + positions)."""
        ...

    def validate_credentials(self, credentials: dict) -> tuple[bool, str]:
        """Validate broker credentials without connecting."""
        required = self.required_credentials()
        missing = [k for k in required if k not in credentials or not credentials[k]]
        if missing:
            return False, f"Missing credentials: {missing}"
        return True, "OK"

    @abstractmethod
    def required_credentials(self) -> Sequence[str]:
        """Return list of required credential keys."""
        ...
```

### Broker Adapter Skeletons

```python
import os
from typing import Sequence, Optional

from alpha_search.execution.broker_adapter import BrokerAdapter
from alpha_search.execution.paper_trader import OrderSide, OrderType, OrderStatus, Position, Portfolio


class AlpacaAdapter(BrokerAdapter):
    """Alpaca Markets broker adapter (stocks & ETFs).
    Supports both paper and live trading.
    """

    broker_name = "Alpaca"

    def __init__(self, paper: bool = True):
        self.paper = paper
        self._connected = False
        self._api_key = None
        self._secret_key = None

    @property
    def is_paper(self) -> bool:
        return self.paper

    def connect(self, credentials: dict) -> bool:
        valid, msg = self.validate_credentials(credentials)
        if not valid:
            raise ValueError(msg)
        self._api_key = credentials["api_key"]
        self._secret_key = credentials["secret_key"]
        # Full implementation uses alpaca-trade-api SDK
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def submit_order(self, ticker: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     limit_price: Optional[float] = None) -> str:
        raise NotImplementedError("Alpaca adapter requires alpaca-trade-api SDK")

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()

    def get_positions(self) -> Sequence[Position]:
        raise NotImplementedError()

    def get_portfolio(self) -> Portfolio:
        raise NotImplementedError()

    def get_order_status(self, order_id: str) -> OrderStatus:
        raise NotImplementedError()

    def get_account_value(self) -> float:
        raise NotImplementedError()

    def required_credentials(self) -> Sequence[str]:
        return ["api_key", "secret_key"]


class KrakenAdapter(BrokerAdapter):
    """Kraken exchange adapter (cryptocurrency).
    Supports both sandbox and live trading.
    """

    broker_name = "Kraken"

    def __init__(self, sandbox: bool = True):
        self.sandbox = sandbox
        self._connected = False

    @property
    def is_paper(self) -> bool:
        return self.sandbox

    def connect(self, credentials: dict) -> bool:
        valid, msg = self.validate_credentials(credentials)
        if not valid:
            raise ValueError(msg)
        # Full implementation uses krakenex or ccxt library
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def submit_order(self, ticker: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     limit_price: Optional[float] = None) -> str:
        raise NotImplementedError("Kraken adapter requires krakenex SDK")

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()

    def get_positions(self) -> Sequence[Position]:
        raise NotImplementedError()

    def get_portfolio(self) -> Portfolio:
        raise NotImplementedError()

    def get_order_status(self, order_id: str) -> OrderStatus:
        raise NotImplementedError()

    def get_account_value(self) -> float:
        raise NotImplementedError()

    def required_credentials(self) -> Sequence[str]:
        return ["api_key", "api_secret"]


class InteractiveBrokersAdapter(BrokerAdapter):
    """Interactive Brokers adapter (global multi-asset).
    Uses IB API or ib_insync library.
    """

    broker_name = "Interactive Brokers"

    def __init__(self, paper: bool = True):
        self.paper = paper
        self._connected = False

    @property
    def is_paper(self) -> bool:
        return self.paper

    def connect(self, credentials: dict) -> bool:
        # IB uses host/port/clientId, not API keys
        self._host = credentials.get("host", "127.0.0.1")
        self._port = credentials.get("port", 7497)
        self._client_id = credentials.get("client_id", 1)
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def submit_order(self, ticker: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     limit_price: Optional[float] = None) -> str:
        raise NotImplementedError("IB adapter requires ib_insync library")

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()

    def get_positions(self) -> Sequence[Position]:
        raise NotImplementedError()

    def get_portfolio(self) -> Portfolio:
        raise NotImplementedError()

    def get_order_status(self, order_id: str) -> OrderStatus:
        raise NotImplementedError()

    def get_account_value(self) -> float:
        raise NotImplementedError()

    def required_credentials(self) -> Sequence[str]:
        return ["host", "port", "client_id"]
```

### Risk Controls

```python
from dataclasses import dataclass
from typing import Optional, Sequence
from datetime import datetime
import pandas as pd

from alpha_search.execution.paper_trader import PaperTrader, Order, OrderSide


@dataclass
class RiskLimits:
    """Configurable risk limits for trading.

    All limits are enforced BEFORE order submission.
    An order that violates any limit is rejected.
    """
    max_position_pct: float = 0.25  # Max 25% of equity in one position
    max_gross_leverage: float = 2.0  # Max 2x gross exposure
    max_net_leverage: float = 1.0  # Max 1x net exposure
    max_drawdown_pct: float = 0.10  # Stop trading at 10% drawdown
    daily_loss_limit: float = 5000.0  # Max daily loss in currency
    max_orders_per_minute: int = 10  # Rate limit
    require_stop_loss: bool = False  # All positions must have stop
    allowed_tickers: Optional[Sequence[str]] = None  # Whitelist


class RiskController:
    """Enforces risk limits on all orders.

    Integrated into PaperTrader and BrokerAdapters.
    Rejects orders that exceed configured limits.
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self._daily_pnl = 0.0
        self._daily_pnl_date = datetime.now().date()
        self._orders_this_minute: list[datetime] = []
        self._circuit_breaker_tripped = False
        self._peak_equity = 0.0

    def check_order(self, trader: PaperTrader, order: Order, current_price: float) -> tuple[bool, str]:
        """Check if an order passes all risk controls.

        Returns: (allowed, reason_if_rejected)
        """
        if self._circuit_breaker_tripped:
            return False, "Circuit breaker tripped — trading halted"

        portfolio = trader.get_portfolio()

        # 1. Ticker whitelist
        if self.limits.allowed_tickers and order.ticker not in self.limits.allowed_tickers:
            return False, f"Ticker {order.ticker} not in allowed list"

        # 2. Position concentration
        notional = order.quantity * current_price
        max_position_value = portfolio.total_equity * self.limits.max_position_pct
        existing = portfolio.positions.get(order.ticker)
        existing_value = existing.market_value if existing else 0
        if order.side == OrderSide.BUY and existing_value + notional > max_position_value:
            return False, f"Position would exceed {self.limits.max_position_pct*100}% limit"

        # 3. Leverage check
        new_exposure = portfolio.total_exposure + notional
        new_gross_lev = new_exposure / portfolio.total_equity if portfolio.total_equity > 0 else 0
        if new_gross_lev > self.limits.max_gross_leverage:
            return False, f"Gross leverage would exceed {self.limits.max_gross_leverage}x"

        # 4. Drawdown circuit breaker
        if portfolio.total_equity > self._peak_equity:
            self._peak_equity = portfolio.total_equity
        drawdown = (self._peak_equity - portfolio.total_equity) / self._peak_equity if self._peak_equity > 0 else 0
        if drawdown > self.limits.max_drawdown_pct:
            self._circuit_breaker_tripped = True
            return False, f"Max drawdown {self.limits.max_drawdown_pct*100}% exceeded — trading halted"

        # 5. Daily loss limit
        today = datetime.now().date()
        if today != self._daily_pnl_date:
            self._daily_pnl = 0.0
            self._daily_pnl_date = today
        # Approximate impact
        approx_pnl = 0 if order.side == OrderSide.BUY else -notional * 0.01
        if self._daily_pnl + approx_pnl < -self.limits.daily_loss_limit:
            return False, f"Daily loss limit ${self.limits.daily_loss_limit} would be exceeded"

        # 6. Order rate limiting
        now = datetime.now()
        self._orders_this_minute = [
            t for t in self._orders_this_minute
            if (now - t).total_seconds() < 60
        ]
        if len(self._orders_this_minute) >= self.limits.max_orders_per_minute:
            return False, f"Rate limit: {self.limits.max_orders_per_minute} orders/minute"

        self._orders_this_minute.append(now)
        return True, "OK"

    def reset(self):
        """Reset all risk state."""
        self._circuit_breaker_tripped = False
        self._daily_pnl = 0.0
        self._peak_equity = 0.0
        self._orders_this_minute.clear()
```

### Unified Execution Interface

```python
from typing import Optional, Literal, Sequence
from dataclasses import dataclass

from alpha_search.execution.paper_trader import PaperTrader, OrderSide, OrderType, Portfolio
from alpha_search.execution.broker_adapter import BrokerAdapter
from alpha_search.execution.risk_controls import RiskController, RiskLimits


class ExecutionGateway:
    """Unified execution interface for Alpha Search.

    Routes orders to paper trader or live broker based on mode.
    All orders pass through risk controls before execution.

    Usage:
        gateway = ExecutionGateway(mode="paper", initial_cash=100_000)
        gateway.submit_order("AAPL", OrderSide.BUY, 100, current_price=150.0)
        portfolio = gateway.get_portfolio()
    """

    def __init__(
        self,
        mode: Literal["paper", "live"] = "paper",
        paper_config: Optional[dict] = None,
        broker_adapter: Optional[BrokerAdapter] = None,
        risk_limits: Optional[RiskLimits] = None,
    ):
        self.mode = mode
        self.paper_trader = PaperTrader(**(paper_config or {}))
        self.broker = broker_adapter
        self.risk = RiskController(risk_limits)

        if mode == "live" and broker_adapter is None:
            raise ValueError("Live mode requires a broker_adapter")
        if mode == "live" and broker_adapter and not broker_adapter.is_paper:
            raise RuntimeError(
                " SAFETY: Attempting live trading. "
                "Confirm you understand the risks before proceeding."
            )

    def submit_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: float,
        current_price: float,
        order_type: OrderType = OrderType.MARKET,
    ):
        """Submit an order through the execution gateway."""
        order = self.paper_trader.submit_order(
            ticker=ticker,
            side=side,
            quantity=quantity,
            current_price=current_price,
            order_type=order_type,
        )

        # Risk check (on the pending order)
        allowed, reason = self.risk.check_order(self.paper_trader, order, current_price)
        if not allowed:
            # Cancel the order if risk check fails
            order.status = __import__("alpha_search.execution.paper_trader", fromlist=["OrderStatus"]).OrderStatus.REJECTED
            raise RuntimeError(f"Order rejected by risk control: {reason}")

        return order

    def get_portfolio(self) -> Portfolio:
        """Get current portfolio snapshot."""
        return self.paper_trader.get_portfolio()

    def update_prices(self, prices: dict[str, float]):
        """Update market prices in paper trader."""
        self.paper_trader.update_prices(prices)

    def get_equity_curve(self):
        """Get equity curve for performance analysis."""
        return self.paper_trader.get_equity_curve_df()

    def reset(self):
        """Reset all state."""
        self.paper_trader.reset()
        self.risk.reset()
```

## Responsibilities

1. Build the PaperTrader with realistic fill simulation (slippage, commission)
2. Implement the BrokerAdapter ABC for unified broker connectivity
3. Create skeleton adapters for Alpaca (stocks), Kraken (crypto), and Interactive Brokers (multi-asset)
4. Build RiskController with position limits, leverage caps, drawdown circuit breakers, and rate limiting
5. Ensure NO live trading by default — paper mode is the only active mode without explicit opt-in
6. Track positions, orders, fills, and PNL with full audit history
7. Expose equity curve as DataFrame for UI charting
8. Implement order validation before submission (sufficient funds, valid quantities)
9. Build the unified ExecutionGateway that routes orders based on mode
10. Document the safety model and opt-in process for live trading

## Inputs

- Signal output from Quant Engineering layer (buy/sell/hold with quantity)
- Current market prices for the target ticker(s)
- User configuration (initial capital, risk limits, trading mode)
- Broker credentials (only when live mode is explicitly enabled)
- Risk limit configuration (position size, leverage, drawdown thresholds)

## Outputs

- Order objects with fill confirmations
- Portfolio snapshots with positions, cash, and PNL
- Equity curve DataFrame for charting
- Trade history log for performance review
- Risk rejection reasons for debugging

## Required Files to Create or Modify

- `alpha_search/execution/paper_trader.py` — PaperTrader with full simulation (create)
- `alpha_search/execution/broker_adapter.py` — BrokerAdapter ABC (create)
- `alpha_search/execution/adapters/alpaca.py` — Alpaca adapter skeleton (create)
- `alpha_search/execution/adapters/kraken.py` — Kraken adapter skeleton (create)
- `alpha_search/execution/adapters/interactive_brokers.py` — IB adapter skeleton (create)
- `alpha_search/execution/risk_controls.py` — RiskController + RiskLimits (create)
- `alpha_search/execution/gateway.py` — ExecutionGateway (create)
- `alpha_search/execution/__init__.py` — module exports (modify)
- `alpha_search/execution/adapters/__init__.py` — adapter exports (create)
- `tests/execution/test_paper_trader.py` — paper trading tests (create)
- `tests/execution/test_risk_controls.py` — risk limit enforcement tests (create)
- `tests/execution/test_gateway.py` — gateway integration tests (create)

## Implementation Checklist

- [ ] Implement PaperTrader with cash, positions, orders, and fills tracking
- [ ] Add realistic fill simulation (slippage, commission deduction)
- [ ] Implement position update logic (add, reduce, close, flip)
- [ ] Build BrokerAdapter ABC with all required methods
- [ ] Create AlpacaAdapter skeleton with credential validation
- [ ] Create KrakenAdapter skeleton with credential validation
- [ ] Create InteractiveBrokersAdapter skeleton
- [ ] Build RiskController with all limit types
- [ ] Implement drawdown circuit breaker that halts trading
- [ ] Implement order rate limiting
- [ ] Build ExecutionGateway as unified interface
- [ ] Enforce paper-only mode by default (no live trading without explicit opt-in)
- [ ] Add equity curve tracking with DataFrame export
- [ ] Write comprehensive paper trader tests
- [ ] Write risk control tests verifying each limit type
- [ ] Document safety model and live trading opt-in process

## Testing Checklist

- [ ] PaperTrader starts with correct initial cash
- [ ] Buy order reduces cash, creates position
- [ ] Sell order increases cash, reduces position
- [ ] Position PNL updates correctly when prices change
- [ ] Commission is deducted from cash on every trade
- [ ] Slippage applies in correct direction (worse fill for buyer)
- [ ] Risk controller rejects orders exceeding position limit
- [ ] Risk controller rejects orders exceeding leverage limit
- [ ] Circuit breaker trips at configured drawdown threshold
- [ ] Daily loss limit rejects orders that would exceed it
- [ ] Rate limiter blocks excessive order frequency
- [ ] Equity curve is monotonically recorded after each price update
- [ ] Portfolio snapshot matches manual calculation
- [ ] Broker adapter validate_credentials catches missing fields
- [ ] ExecutionGateway rejects live mode without broker adapter
- [ ] Reset function clears all state to initial values

## Definition of Done

- PaperTrader simulates realistic fills with configurable slippage and commission
- All risk limits are enforced before order execution
- Circuit breaker halts trading at configured drawdown
- BrokerAdapter ABC is fully defined with type hints
- Three broker skeletons exist (Alpaca, Kraken, IB) with credential validation
- ExecutionGateway routes orders correctly in paper mode
- NO live trading is possible without explicit multi-step opt-in
- Equity curve exports as DataFrame for UI consumption
- Portfolio snapshot includes cash, positions, unrealized PNL, and leverage
- Unit tests verify all risk controls and trading scenarios
- Safety documentation explains the paper-first model

## Example Prompt

> You are the Alpha Search Execution Gateway agent. Build a PaperTrader that simulates market orders with configurable slippage (5bps) and commission (0.1%). Track positions, orders, fills, and PNL. Build a RiskController that enforces: max 25% position size, max 2x gross leverage, 10% drawdown circuit breaker, and 10 orders/minute rate limit. Create BrokerAdapter ABC and skeletons for Alpaca and Kraken. Build the unified ExecutionGateway that defaults to paper mode and requires explicit opt-in for live trading. Write comprehensive tests for all risk controls and trading scenarios.