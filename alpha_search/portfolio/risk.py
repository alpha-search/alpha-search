"""Portfolio risk metrics (vectorized)."""

from __future__ import annotations

from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

_TRADING_DAYS = 252


def portfolio_volatility(
    returns: pd.DataFrame,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Annualized portfolio volatility.

    Args:
        returns: DataFrame of asset returns (columns = tickers).
        weights: Ticker -> weight dict. If ``None``, equal weights.

    Returns:
        Annualized standard deviation.
    """
    if returns is None or returns.empty:
        return 0.0

    tickers = list(returns.columns)
    n = len(tickers)

    if weights is None:
        w = np.ones(n) / n
    else:
        w = np.array([weights.get(t, 0.0) for t in tickers])

    cov = returns.cov().values
    daily_var = w @ cov @ w
    if daily_var < 0:
        daily_var = 0.0
    return float(np.sqrt(daily_var * _TRADING_DAYS))


def value_at_risk(
    returns: Union[pd.Series, pd.DataFrame],
    confidence: float = 0.95,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Historical Value at Risk at given confidence level.

    Args:
        returns: Return series or DataFrame.
        confidence: Confidence level (e.g. 0.95 = 95%% VaR).
        weights: Required if returns is a DataFrame.

    Returns:
        VaR as a positive number (e.g. 0.02 = 2% daily VaR).
    """
    if isinstance(returns, pd.DataFrame):
        if weights is None:
            tickers = list(returns.columns)
            weights = {t: 1.0 / len(tickers) for t in tickers}
        w = np.array([weights.get(t, 0.0) for t in returns.columns])
        port_returns = returns @ w
    else:
        port_returns = returns

    if port_returns.empty:
        return 0.0

    var = -np.percentile(port_returns.dropna(), (1 - confidence) * 100)
    return float(var)


def conditional_var(
    returns: Union[pd.Series, pd.DataFrame],
    confidence: float = 0.95,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Conditional Value at Risk (Expected Shortfall).

    Average of returns worse than the VaR threshold.

    Args:
        returns: Return series or DataFrame.
        confidence: Confidence level.
        weights: Required if returns is a DataFrame.

    Returns:
        CVaR as a positive number.
    """
    if isinstance(returns, pd.DataFrame):
        if weights is None:
            tickers = list(returns.columns)
            weights = {t: 1.0 / len(tickers) for t in tickers}
        w = np.array([weights.get(t, 0.0) for t in returns.columns])
        port_returns = returns @ w
    else:
        port_returns = returns

    if port_returns.empty:
        return 0.0

    var_threshold = -value_at_risk(port_returns, confidence)
    tail_returns = port_returns[port_returns <= var_threshold]
    if tail_returns.empty:
        return float(-var_threshold)
    return float(-tail_returns.mean())


def beta(
    asset_returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """Compute beta of an asset relative to the market.

    Args:
        asset_returns: Asset daily returns.
        market_returns: Market daily returns.

    Returns:
        Beta coefficient.
    """
    aligned = pd.concat([asset_returns, market_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 1.0

    cov = aligned.cov().values
    if cov[1, 1] == 0:
        return 1.0
    return float(cov[0, 1] / cov[1, 1])


def tracking_error(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """Annualized tracking error (standard deviation of return differences).

    Args:
        portfolio_returns: Portfolio daily returns.
        benchmark_returns: Benchmark daily returns.

    Returns:
        Annualized tracking error.
    """
    diff = portfolio_returns - benchmark_returns
    diff = diff.dropna()
    if len(diff) < 2:
        return 0.0
    return float(diff.std() * np.sqrt(_TRADING_DAYS))


def information_ratio(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """Information ratio = active return / tracking error.

    Args:
        portfolio_returns: Portfolio daily returns.
        benchmark_returns: Benchmark daily returns.

    Returns:
        Information ratio.
    """
    te = tracking_error(portfolio_returns, benchmark_returns)
    if te == 0:
        return 0.0
    active_return = (portfolio_returns.mean() - benchmark_returns.mean()) * _TRADING_DAYS
    return float(active_return / te)
