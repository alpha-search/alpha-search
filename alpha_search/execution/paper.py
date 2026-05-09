"""Paper trading simulator for Alpha Search."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from alpha_search.core.models import Order, Position
from alpha_search.execution.broker_base import BrokerAdapter

logger = logging.getLogger(__name__)


class PaperTrader(BrokerAdapter):
    """Paper (simulated) trading broker.

    Simulates order fills at the last known price. Tracks cash, positions,
    and order history internally. No real money is ever used.

    Example::

        trader = PaperTrader(initial_cash=100_000)
        order = Order(ticker="AAPL", side="BUY", quantity=10, order_type="MARKET")
        fill = trader.place_order(order)
        positions = trader.get_positions()
    """

    def __init__(self, initial_cash: float = 100000.0) -> None:
        self._cash: float = initial_cash
        self._initial_cash: float = initial_cash
        self._positions: Dict[str, Position] = {}
        self._orders: List[Dict[str, Any]] = []
        self._fills: List[Dict[str, Any]] = []
        self._last_prices: Dict[str, float] = {}
        self._connected: bool = False

    # -- BrokerAdapter interface ----------------------------------------

    @property
    def name(self) -> str:
        return "paper_trader"

    @property
    def is_paper(self) -> bool:
        return True

    def connect(self) -> bool:
        """No-op for paper trading (always succeeds)."""
        self._connected = True
        logger.info("PaperTrader connected (simulation mode).")
        return True

    def disconnect(self) -> None:
        """No-op disconnect."""
        self._connected = False
        logger.info("PaperTrader disconnected.")

    def place_order(self, order: Order) -> Dict[str, Any]:
        """Simulate an order fill.

        Market orders fill immediately at the last known price.
        Limit orders fill if the limit price is reachable.

        Returns:
            Fill details dict.
        """
        if not self._connected:
            self.connect()

        ticker = order.ticker.upper()
        price = self._last_prices.get(ticker, 0.0)

        if price <= 0:
            # No price data - reject
            result = {
                "order_id": order.id,
                "status": "REJECTED",
                "reason": "No price data available",
                "filled_qty": 0.0,
                "avg_price": 0.0,
                "timestamp": order.timestamp.isoformat(),
            }
            self._orders.append({"order": order, "result": result})
            return result

        # Check limit price
        if order.order_type == "LIMIT" and order.limit_price is not None:
            if order.side == "BUY" and price > order.limit_price:
                result = {
                    "order_id": order.id,
                    "status": "PENDING",
                    "reason": f"Price {price} above limit {order.limit_price}",
                    "filled_qty": 0.0,
                    "avg_price": 0.0,
                }
                self._orders.append({"order": order, "result": result})
                return result
            if order.side == "SELL" and price < order.limit_price:
                result = {
                    "order_id": order.id,
                    "status": "PENDING",
                    "reason": f"Price {price} below limit {order.limit_price}",
                    "filled_qty": 0.0,
                    "avg_price": 0.0,
                }
                self._orders.append({"order": order, "result": result})
                return result

        # Execute fill
        fill_value = order.quantity * price

        if order.side == "BUY":
            if fill_value > self._cash:
                result = {
                    "order_id": order.id,
                    "status": "REJECTED",
                    "reason": f"Insufficient cash: ${self._cash:.2f} needed ${fill_value:.2f}",
                    "filled_qty": 0.0,
                    "avg_price": 0.0,
                }
                self._orders.append({"order": order, "result": result})
                return result

            self._cash -= fill_value
            self._update_position(ticker, order.quantity, price)

        else:  # SELL
            current_pos = self._positions.get(ticker)
            if current_pos is None or current_pos.quantity < order.quantity:
                result = {
                    "order_id": order.id,
                    "status": "REJECTED",
                    "reason": f"Insufficient shares: have {getattr(current_pos, 'quantity', 0)}, need {order.quantity}",
                    "filled_qty": 0.0,
                    "avg_price": 0.0,
                }
                self._orders.append({"order": order, "result": result})
                return result

            self._cash += fill_value
            self._update_position(ticker, -order.quantity, price)

        result = {
            "order_id": order.id,
            "status": "FILLED",
            "filled_qty": order.quantity,
            "avg_price": price,
            "timestamp": order.timestamp.isoformat(),
            "ticker": ticker,
            "side": order.side,
            "total_value": fill_value,
        }
        self._fills.append(result)
        self._orders.append({"order": order, "result": result})
        logger.info(
            "PaperTrader: %s %s %s @ $%.2f = $%.2f",
            order.side,
            order.quantity,
            ticker,
            price,
            fill_value,
        )
        return result

    def get_positions(self) -> Dict[str, Position]:
        """Return current positions keyed by ticker."""
        # Update prices on all positions
        updated = {}
        for ticker, pos in self._positions.items():
            updated[ticker] = pos.update_price(self._last_prices.get(ticker, pos.current_price))
        self._positions = updated
        return dict(updated)

    def get_account_value(self) -> float:
        """Return total account value (cash + positions)."""
        positions_value = sum(
            pos.quantity * self._last_prices.get(ticker, pos.current_price)
            for ticker, pos in self._positions.items()
        )
        return self._cash + positions_value

    # -- Additional public methods --------------------------------------

    def update_price(self, ticker: str, price: float) -> None:
        """Update the last known price for a ticker."""
        self._last_prices[ticker.upper()] = price

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Batch-update last known prices."""
        for ticker, price in prices.items():
            self._last_prices[ticker.upper()] = price

    def get_portfolio_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Get total portfolio value using provided or cached prices."""
        if current_prices:
            self.update_prices(current_prices)
        return self.get_account_value()

    def get_pnl(self) -> float:
        """Return total P&L (current value - initial cash)."""
        return self.get_account_value() - self._initial_cash

    def get_pnl_pct(self) -> float:
        """Return total P&L as a percentage of initial cash."""
        if self._initial_cash == 0:
            return 0.0
        return self.get_pnl() / self._initial_cash

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def order_count(self) -> int:
        return len(self._orders)

    @property
    def fill_count(self) -> int:
        return len(self._fills)

    def get_order_history(self) -> List[Dict[str, Any]]:
        """Return full order and fill history."""
        return [
            {
                "order_id": o["order"].id,
                "ticker": o["order"].ticker,
                "side": o["order"].side,
                "quantity": o["order"].quantity,
                "status": o["result"]["status"],
                "filled_qty": o["result"].get("filled_qty", 0),
                "avg_price": o["result"].get("avg_price", 0),
            }
            for o in self._orders
        ]

    # -- Internal helpers -----------------------------------------------

    def _update_position(self, ticker: str, qty_delta: float, price: float) -> None:
        """Update a position after a fill."""
        ticker = ticker.upper()
        pos = self._positions.get(ticker)
        if pos is None:
            self._positions[ticker] = Position(
                ticker=ticker,
                quantity=qty_delta,
                avg_cost=price,
                current_price=price,
            )
        else:
            new_qty = pos.quantity + qty_delta
            if new_qty == 0:
                del self._positions[ticker]
            elif new_qty > 0 and qty_delta > 0:
                # Buying more - update avg cost
                total_cost = pos.quantity * pos.avg_cost + qty_delta * price
                new_avg = total_cost / new_qty
                self._positions[ticker] = Position(
                    ticker=ticker,
                    quantity=new_qty,
                    avg_cost=new_avg,
                    current_price=price,
                )
            else:
                self._positions[ticker] = Position(
                    ticker=ticker,
                    quantity=new_qty,
                    avg_cost=pos.avg_cost,
                    current_price=price,
                )

    def __repr__(self) -> str:
        return (
            f"<PaperTrader cash=${self._cash:,.2f} "
            f"positions={len(self._positions)} "
            f"value=${self.get_account_value():,.2f}>"
        )
