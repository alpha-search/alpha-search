"""Risk management controls for order execution."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskManager:
    """Pre-trade and post-trade risk controls.

    Enforces position limits, portfolio exposure caps, and daily loss limits.
    All checks return ``True`` if the risk is acceptable.

    Example::

        rm = RiskManager(max_position_pct=0.25, max_exposure_pct=1.5)
        ok = rm.check_position_limit(30000, 100000)
    """

    def __init__(
        self,
        max_position_pct: float = 0.25,
        max_exposure_pct: float = 2.0,
        max_daily_loss_pct: float = 0.05,
        max_single_order_pct: float = 0.10,
    ) -> None:
        """Initialize risk controls.

        Args:
            max_position_pct: Maximum single position as fraction of portfolio.
            max_exposure_pct: Maximum gross exposure (long + |short|).
            max_daily_loss_pct: Maximum daily loss as fraction of portfolio.
            max_single_order_pct: Maximum single order as fraction of portfolio.
        """
        self.max_position_pct = max_position_pct
        self.max_exposure_pct = max_exposure_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_single_order_pct = max_single_order_pct
        self._daily_pnl: Dict[str, float] = {}  # date -> P&L
        self._violations: List[Dict] = []

    def check_position_limit(
        self,
        position_size: float,
        portfolio_value: float,
    ) -> bool:
        """Check if a position size is within limits.

        Args:
            position_size: Absolute dollar size of the position.
            portfolio_value: Total portfolio value.

        Returns:
            ``True`` if the position is within the limit.
        """
        if portfolio_value <= 0:
            return True
        limit = portfolio_value * self.max_position_pct
        ok = abs(position_size) <= limit
        if not ok:
            self._log_violation(
                "position_limit",
                f"Position ${abs(position_size):,.2f} exceeds limit ${limit:,.2f}",
            )
        return ok

    def check_portfolio_exposure(
        self,
        total_long_value: float,
        total_short_value: float,
        portfolio_value: float,
    ) -> bool:
        """Check if gross exposure is within limits.

        Args:
            total_long_value: Total dollar value of long positions.
            total_short_value: Total absolute dollar value of short positions.
            portfolio_value: Total portfolio value.

        Returns:
            ``True`` if exposure is within the limit.
        """
        if portfolio_value <= 0:
            return True
        gross_exposure = (total_long_value + abs(total_short_value)) / portfolio_value
        ok = gross_exposure <= self.max_exposure_pct
        if not ok:
            self._log_violation(
                "exposure_limit",
                f"Gross exposure {gross_exposure:.2f}x exceeds limit {self.max_exposure_pct:.2f}x",
            )
        return ok

    def check_daily_loss(
        self,
        current_pnl: float,
        portfolio_value: float,
    ) -> bool:
        """Check if daily loss is within the limit.

        Args:
            current_pnl: Today's P&L (can be negative).
            portfolio_value: Total portfolio value.

        Returns:
            ``True`` if the daily loss is within the limit.
        """
        if portfolio_value <= 0:
            return True
        daily_loss = -min(0, current_pnl)
        max_loss = portfolio_value * self.max_daily_loss_pct
        ok = daily_loss <= max_loss
        if not ok:
            self._log_violation(
                "daily_loss",
                f"Daily loss ${daily_loss:,.2f} exceeds limit ${max_loss:,.2f}",
            )
        return ok

    def check_order_size(
        self,
        order_value: float,
        portfolio_value: float,
    ) -> bool:
        """Check if a single order size is within limits.

        Args:
            order_value: Dollar value of the order.
            portfolio_value: Total portfolio value.

        Returns:
            ``True`` if the order size is acceptable.
        """
        if portfolio_value <= 0:
            return True
        limit = portfolio_value * self.max_single_order_pct
        ok = abs(order_value) <= limit
        if not ok:
            self._log_violation(
                "order_size",
                f"Order ${abs(order_value):,.2f} exceeds limit ${limit:,.2f}",
            )
        return ok

    def check_all(
        self,
        position_size: float,
        total_long_value: float,
        total_short_value: float,
        current_pnl: float,
        portfolio_value: float,
    ) -> Dict[str, bool]:
        """Run all risk checks at once.

        Returns:
            Dict of check name -> bool result.
        """
        return {
            "position_limit": self.check_position_limit(position_size, portfolio_value),
            "exposure": self.check_portfolio_exposure(
                total_long_value, total_short_value, portfolio_value
            ),
            "daily_loss": self.check_daily_loss(current_pnl, portfolio_value),
        }

    def _log_violation(self, rule: str, message: str) -> None:
        """Record a risk violation."""
        violation = {"rule": rule, "message": message}
        self._violations.append(violation)
        logger.warning("RISK VIOLATION [%s]: %s", rule, message)

    @property
    def violations(self) -> List[Dict]:
        """Return recorded risk violations."""
        return list(self._violations)

    def reset_violations(self) -> None:
        """Clear violation history."""
        self._violations = []

    def __repr__(self) -> str:
        return (
            f"<RiskManager pos={self.max_position_pct:.0%} "
            f"exp={self.max_exposure_pct:.1f}x "
            f"loss={self.max_daily_loss_pct:.0%}>"
        )
