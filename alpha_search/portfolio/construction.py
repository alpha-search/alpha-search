"""Portfolio construction utilities."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from alpha_search.core.models import Position

logger = logging.getLogger(__name__)


class Portfolio:
    """A portfolio of assets with weight tracking.

    Attributes:
        weights: Dict mapping ticker -> target weight.
        positions: Dict mapping ticker -> Position objects.
        cash: Current cash balance.
    """

    def __init__(self, cash: float = 100000.0) -> None:
        self.cash: float = cash
        self.weights: Dict[str, float] = {}
        self.positions: Dict[str, Position] = {}
        self._history: List[Dict] = []

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Set target portfolio weights (must sum to <= 1.0).

        Args:
            weights: Ticker -> weight mapping. Negative values indicate short.

        Raises:
            ValueError: If absolute weights sum to > 1.0.
        """
        total_abs = sum(abs(w) for w in weights.values())
        if total_abs > 1.0 + 1e-9:
            raise ValueError(
                f"Absolute weights sum to {total_abs:.4f}, must be <= 1.0"
            )
        self.weights = dict(weights)
        logger.debug("Set portfolio weights: %s", self.weights)

    def update_positions(self, prices: Dict[str, float]) -> None:
        """Update position mark-to-market prices.

        Args:
            prices: Ticker -> current price mapping.
        """
        for ticker, price in prices.items():
            if ticker in self.positions:
                self.positions[ticker] = self.positions[ticker].update_price(price)

    def get_position_sizes(self, total_value: float) -> Dict[str, float]:
        """Compute dollar position sizes from weights.

        Args:
            total_value: Total portfolio value.

        Returns:
            Ticker -> dollar amount mapping.
        """
        return {
            ticker: total_value * weight
            for ticker, weight in self.weights.items()
        }

    def get_market_value(self) -> float:
        """Return total market value of all positions."""
        return sum(p.market_value for p in self.positions.values())

    def get_total_value(self) -> float:
        """Return total portfolio value (cash + positions)."""
        return self.cash + self.get_market_value()

    def get_sector_exposure(self, sector_map: Dict[str, str]) -> Dict[str, float]:
        """Compute exposure by sector.

        Args:
            sector_map: Ticker -> sector mapping.

        Returns:
            Sector -> total weight mapping.
        """
        exposure: Dict[str, float] = {}
        for ticker, weight in self.weights.items():
            sector = sector_map.get(ticker, "Unknown")
            exposure[sector] = exposure.get(sector, 0.0) + weight
        return exposure

    def rebalance(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate rebalancing trades to achieve target weights.

        Args:
            prices: Ticker -> current price mapping.

        Returns:
            Ticker -> shares to trade (positive = buy, negative = sell).
        """
        total_value = self.get_total_value()
        trades: Dict[str, float] = {}

        for ticker, weight in self.weights.items():
            target_dollar = total_value * weight
            price = prices.get(ticker, 0.0)
            if price <= 0:
                trades[ticker] = 0.0
                continue

            target_shares = target_dollar / price
            current_shares = self.positions.get(ticker, Position(ticker=ticker, quantity=0, avg_cost=0)).quantity
            trades[ticker] = target_shares - current_shares

        return trades

    def snapshot(self) -> Dict:
        """Return a snapshot of the portfolio state."""
        snap = {
            "cash": self.cash,
            "weights": dict(self.weights),
            "positions": {
                t: {
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pnl,
                }
                for t, p in self.positions.items()
            },
            "total_value": self.get_total_value(),
        }
        self._history.append(snap)
        return snap

    def __repr__(self) -> str:
        return (
            f"<Portfolio cash={self.cash:,.2f} "
            f"positions={len(self.positions)} "
            f"total={self.get_total_value():,.2f}>"
        )
