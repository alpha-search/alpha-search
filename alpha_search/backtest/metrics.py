"""Performance metrics for backtest evaluation.

All functions operate on pandas Series (vectorized) and return
scalar Python floats.
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TRADING_DAYS_PER_YEAR = 252


class Metrics:
    """Collection of performance metrics calculators."""

    # ---- Single metric functions --------------------------------------

    @staticmethod
    def total_return(returns: pd.Series) -> float:
        """Total compounded return over the period."""
        if returns.empty:
            return 0.0
        return float((1.0 + returns).prod() - 1.0)

    @staticmethod
    def annualized_return(returns: pd.Series) -> float:
        """Annualized geometric mean return."""
        if returns.empty or len(returns) < 2:
            return 0.0
        total = (1.0 + returns).prod()
        n_years = len(returns) / _TRADING_DAYS_PER_YEAR
        if n_years <= 0:
            return 0.0
        return float(total ** (1.0 / n_years) - 1.0)

    @staticmethod
    def sharpe_ratio(
        returns: pd.Series,
        risk_free: float = 0.02,
    ) -> float:
        """Sharpe ratio = (R_p - R_f) / sigma_p.

        Args:
            returns: Daily strategy returns.
            risk_free: Annual risk-free rate (default 2 %).
        """
        if returns.empty or returns.std() == 0:
            return 0.0
        excess = returns - risk_free / _TRADING_DAYS_PER_YEAR
        return float(excess.mean() / excess.std() * np.sqrt(_TRADING_DAYS_PER_YEAR))

    @staticmethod
    def sortino_ratio(
        returns: pd.Series,
        risk_free: float = 0.02,
    ) -> float:
        """Sortino ratio using downside deviation only.

        Downside deviation is computed from *excess* returns below the
        target (MAR = risk-free rate), not from raw returns below zero.
        """
        if returns.empty:
            return 0.0
        excess = returns - risk_free / _TRADING_DAYS_PER_YEAR
        # Downside deviation: std of negative *excess* returns only
        downside = excess[excess < 0].std()
        if downside == 0 or np.isnan(downside):
            return 0.0
        return float(excess.mean() / downside * np.sqrt(_TRADING_DAYS_PER_YEAR))

    @staticmethod
    def max_drawdown(equity: pd.Series) -> float:
        """Maximum peak-to-trough drawdown as a negative fraction.

        Returns a negative number, e.g. ``-0.20`` means a 20 % drawdown.
        A return of ``0.0`` means no drawdown occurred.
        """
        if equity.empty or len(equity) < 2:
            return 0.0
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        return float(drawdown.min())

    @staticmethod
    def max_drawdown_duration(equity: pd.Series) -> int:
        """Longest duration (in trading days) that equity stays below a previous peak.

        Uses a vectorised cumsum over drawdown-group runs — O(n) in pandas
        instead of a Python loop.
        """
        if equity.empty or len(equity) < 2:
            return 0
        cummax = equity.cummax()
        is_drawdown = equity < cummax

        if not is_drawdown.any():
            return 0

        # Group consecutive drawdown days and count each group's length
        # (~is_drawdown).cumsum() increments at every new peak → creates
        # a unique group id for each drawdown period.
        groups = (~is_drawdown).cumsum()
        # Count days per group, return the max (subtracting non-drawdown group 0)
        durations = is_drawdown.groupby(groups).sum()
        if 0 in durations.index:
            durations = durations.drop(0)
        return int(durations.max()) if len(durations) > 0 else 0

    @staticmethod
    def win_rate(returns: pd.Series) -> float:
        """Fraction of positive-return days."""
        if returns.empty:
            return 0.0
        n_pos = (returns > 0).sum()
        n_total = len(returns)
        return float(n_pos / n_total) if n_total > 0 else 0.0

    @staticmethod
    def profit_factor(returns: pd.Series) -> float:
        """Gross profit / gross loss."""
        if returns.empty:
            return 0.0
        gross_profit = returns[returns > 0].sum()
        gross_loss = -returns[returns < 0].sum()
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return float(gross_profit / gross_loss)

    @staticmethod
    def calmar_ratio(
        returns: pd.Series,
        max_dd: float | None = None,
    ) -> float:
        """Calmar ratio = annualized_return / max_drawdown.

        Args:
            returns: Daily returns.
            max_dd: Pre-computed max drawdown (positive). If ``None``,
                it is computed from a synthetic equity curve.
        """
        if returns.empty:
            return 0.0
        ann_ret = Metrics.annualized_return(returns)
        if max_dd is None:
            equity = (1.0 + returns).cumprod()
            max_dd = Metrics.max_drawdown(equity)
        if max_dd == 0:
            return float("inf") if ann_ret > 0 else 0.0
        return float(ann_ret / max_dd)

    @staticmethod
    def volatility(returns: pd.Series) -> float:
        """Annualized standard deviation of daily returns."""
        if returns.empty or len(returns) < 2:
            return 0.0
        return float(returns.std() * np.sqrt(_TRADING_DAYS_PER_YEAR))

    # ---- Batch computation --------------------------------------------

    @classmethod
    def compute_all(
        cls,
        returns: pd.Series,
        equity: pd.Series,
    ) -> Dict[str, float]:
        """Compute the full suite of metrics.

        Args:
            returns: Daily strategy returns.
            equity: Cumulative equity curve.

        Returns:
            Dictionary of metric name -> value.
        """
        if returns.empty:
            return {}

        max_dd = cls.max_drawdown(equity)

        return {
            "total_return": cls.total_return(returns),
            "annualized_return": cls.annualized_return(returns),
            "sharpe_ratio": cls.sharpe_ratio(returns),
            "sortino_ratio": cls.sortino_ratio(returns),
            "max_drawdown": max_dd,
            "max_drawdown_duration": cls.max_drawdown_duration(equity),
            "win_rate": cls.win_rate(returns),
            "profit_factor": cls.profit_factor(returns),
            "calmar_ratio": cls.calmar_ratio(returns, max_dd),
            "volatility": cls.volatility(returns),
            "num_days": float(len(returns)),
        }
