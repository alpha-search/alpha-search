"""Portfolio optimization utilities (structured with real code).

Provides mean-variance optimization helpers. When scipy is available,
actual quadratic programming is used; otherwise, analytical approximations
or equal-weight fallbacks are provided.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def equal_weight(tickers: List[str]) -> Dict[str, float]:
    """Return equal weights for a list of tickers.

    Args:
        tickers: List of ticker symbols.

    Returns:
        Ticker -> weight mapping summing to 1.0.
    """
    if not tickers:
        return {}
    w = 1.0 / len(tickers)
    return {t: w for t in tickers}


def inverse_volatility(returns: pd.DataFrame) -> Dict[str, float]:
    """Inverse-volatility weighting (lower vol -> higher weight).

    Args:
        returns: DataFrame of asset returns (columns = tickers).

    Returns:
        Ticker -> weight mapping.
    """
    if returns is None or returns.empty:
        return {}
    vols = returns.std()
    inv_vol = 1.0 / vols.replace(0, np.nan)
    inv_vol = inv_vol.dropna()
    if inv_vol.sum() == 0:
        return equal_weight(list(returns.columns))
    weights = inv_vol / inv_vol.sum()
    return weights.to_dict()


def mean_variance_optimization(
    returns: pd.DataFrame,
    target_return: Optional[float] = None,
    risk_aversion: float = 1.0,
    allow_short: bool = False,
) -> Dict[str, float]:
    """Mean-variance portfolio optimization (analytical or numerical).

    When scipy is available, solves the quadratic optimization problem.
    Otherwise, falls back to inverse-volatility weighting.

    Args:
        returns: DataFrame of asset returns (columns = tickers).
        target_return: Optional target portfolio return.
        risk_aversion: Risk aversion parameter (lambda). Higher = more conservative.
        allow_short: If True, allows negative weights.

    Returns:
        Ticker -> optimal weight mapping.
    """
    if returns is None or returns.empty:
        return {}

    tickers = list(returns.columns)
    n = len(tickers)

    if n == 1:
        return {tickers[0]: 1.0}

    mu = returns.mean().values
    sigma = returns.cov().values

    # Ensure covariance is positive semi-definite
    eigvals = np.linalg.eigvalsh(sigma)
    if np.min(eigvals) < 1e-10:
        sigma = sigma + np.eye(n) * 1e-6

    # Try scipy quadratic programming
    try:
        from scipy.optimize import minimize

        def objective(w):
            port_return = w @ mu
            port_var = w @ sigma @ w
            if target_return is not None:
                return port_var
            return -port_return + risk_aversion * port_var

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        if target_return is not None:
            constraints.append({"type": "eq", "fun": lambda w: w @ mu - target_return})

        if allow_short:
            bounds = [(None, None)] * n
        else:
            bounds = [(0.0, 1.0)] * n

        x0 = np.ones(n) / n
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9},
        )

        if result.success:
            weights = np.maximum(result.x, 0) if not allow_short else result.x
            weights = weights / weights.sum() if weights.sum() > 0 else np.ones(n) / n
            return {t: float(w) for t, w in zip(tickers, weights)}

        logger.warning("MVO optimization did not converge; falling back.")
    except ImportError:
        logger.debug("scipy not installed; using inverse-volatility fallback.")

    # Fallback: inverse volatility
    return inverse_volatility(returns)


def risk_parity(returns: pd.DataFrame) -> Dict[str, float]:
    """Risk parity weighting (equal risk contribution).

    When scipy is available, solves for equal risk contribution weights.
    Otherwise, falls back to inverse volatility.

    Args:
        returns: DataFrame of asset returns.

    Returns:
        Ticker -> weight mapping.
    """
    if returns is None or returns.empty:
        return {}

    tickers = list(returns.columns)
    n = len(tickers)

    if n == 1:
        return {tickers[0]: 1.0}

    sigma = returns.cov().values
    eigvals = np.linalg.eigvalsh(sigma)
    if np.min(eigvals) < 1e-10:
        sigma = sigma + np.eye(n) * 1e-6

    try:
        from scipy.optimize import minimize

        def risk_contrib(w):
            port_var = w @ sigma @ w
            if port_var <= 0:
                return np.zeros(n)
            marginal = (sigma @ w) / np.sqrt(port_var)
            rc = w * marginal
            return rc

        def objective(w):
            rc = risk_contrib(w)
            target_rc = np.mean(rc)
            return np.sum((rc - target_rc) ** 2)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(1e-6, 1.0)] * n
        x0 = np.ones(n) / n

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = result.x / result.x.sum()
            return {t: float(w) for t, w in zip(tickers, weights)}
    except ImportError:
        logger.debug("scipy not installed; using inverse-volatility fallback.")

    return inverse_volatility(returns)
