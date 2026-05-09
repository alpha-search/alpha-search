"""Transaction cost model for backtesting."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class CostModel:
    """Simple linear transaction-cost model.

    Costs are applied proportional to the absolute change in position
    size (turnover) each day.

    Args:
        commission: Commission rate per trade (e.g. ``0.001`` = 10 bps).
        slippage: Slippage estimate per trade (e.g. ``0.001`` = 10 bps).
    """

    def __init__(self, commission: float = 0.001, slippage: float = 0.001) -> None:
        if commission < 0 or slippage < 0:
            raise ValueError("commission and slippage must be non-negative")
        self.commission = commission
        self.slippage = slippage
        self._total_cost_rate = commission + slippage

    def apply(
        self,
        position_changes: pd.Series,
        prices: pd.Series,
    ) -> pd.Series:
        """Compute daily transaction costs.

        Args:
            position_changes: Absolute change in position size per day.
            prices: Price series (same index as *position_changes*).

        Returns:
            Daily cost in currency terms.
        """
        turnover = position_changes.abs().fillna(0.0)
        costs = turnover * prices * self._total_cost_rate
        costs.name = "costs"
        return costs

    def __repr__(self) -> str:
        return (
            f"<CostModel commission={self.commission:.4f} "
            f"slippage={self.slippage:.4f}>"
        )
