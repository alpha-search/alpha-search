"""Scoring engine for Alpha Search Opportunity Discovery.

Provides the ``FinalScore`` class that aggregates multiple sub-scores into a
single opportunity confidence value.  All helper methods clamp results to the
``[0, 1]`` range and are designed to be used independently as well as through
:meth:`FinalScore.calculate`.
"""

from __future__ import annotations

import math
from typing import Optional


def _clamp(value: float) -> float:
    """Clamp *value* to the inclusive range ``[0, 1]``."""
    return float(max(0.0, min(1.0, value)))


class FinalScore:
    """Weighted scoring engine for trading opportunities.

    The final score is a convex combination of six sub-scores:

    ===== =========================== ======
    #     Component                   Weight
    ===== =========================== ======
    1     strategy_signal_strength    0.25
    2     liquidity_score             0.20
    3     sentiment_score             0.15
    4     risk_adjusted_return_score  0.15
    5     hedgeability_score          0.15
    6     execution_feasibility_score 0.10
    ===== =========================== ======

    All sub-scores are expected in ``[0, 1]``; the class provides static helpers
    to derive each sub-score from raw market data.
    """

    @staticmethod
    def calculate(
        strategy_signal_strength: float,
        liquidity_score: float,
        sentiment_score: float,
        risk_adjusted_return_score: float,
        hedgeability_score: float,
        execution_feasibility_score: float,
    ) -> float:
        """Calculate the final weighted opportunity score.

        Parameters
        ----------
        strategy_signal_strength : float
            Strength of the raw strategy signal ``[0, 1]``.
        liquidity_score : float
            Liquidity assessment ``[0, 1]``.
        sentiment_score : float
            Sentiment assessment ``[0, 1]``.
        risk_adjusted_return_score : float
            Normalised risk-adjusted return ``[0, 1]``.
        hedgeability_score : float
            Ease/cost of hedging ``[0, 1]``.
        execution_feasibility_score : float
            Expected slippage / market-impact ``[0, 1]``.

        Returns
        -------
        float
            Final composite score in ``[0, 1]``.
        """
        final = (
            0.25 * _clamp(strategy_signal_strength)
            + 0.20 * _clamp(liquidity_score)
            + 0.15 * _clamp(sentiment_score)
            + 0.15 * _clamp(risk_adjusted_return_score)
            + 0.15 * _clamp(hedgeability_score)
            + 0.10 * _clamp(execution_feasibility_score)
        )
        return _clamp(final)

    # ------------------------------------------------------------------ #
    # Helper methods                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def liquidity_score(
        volume: float,
        avg_volume: float,
        market_cap: Optional[float] = None,
    ) -> float:
        """Normalise trading volume to a ``[0, 1]`` liquidity score.

        Logic
        -----
        - Compute the volume ratio ``volume / avg_volume``.
        - Pass through a soft sigmoid: ``ratio / (1 + ratio)`` → ``[0, 1]``.
        - If *market_cap* is provided, boost the score slightly for
          large-cap names (``> 50 k Cr``).

        Parameters
        ----------
        volume : float
            Latest daily traded volume (shares).
        avg_volume : float
            20-day average traded volume (shares).
        market_cap : float, optional
            Market capitalisation in INR Crores.  Large caps get a small boost.

        Returns
        -------
        float
            Liquidity score in ``[0, 1]``.
        """
        if avg_volume <= 0 or volume <= 0:
            return 0.0

        ratio = volume / avg_volume
        score = ratio / (1.0 + ratio)  # soft sigmoid → [0, 1)

        # Large-cap liquidity boost
        if market_cap is not None and market_cap > 50_000:  # > 50 k Cr
            score = min(1.0, score * 1.15)

        return _clamp(score)

    @staticmethod
    def risk_adjusted_return_score(
        expected_return: float,
        volatility: float,
    ) -> float:
        """Normalise a Sharpe-like ratio to ``[0, 1]``.

        Uses the approximation::

            score = tanh(0.5 * expected_return / volatility)

        which maps any real-valued Sharpe ratio into ``[0, 1]`` with a
        sensible knee around ``Sharpe ≈ 2``.

        Parameters
        ----------
        expected_return : float
            Expected return (any frequency, e.g. 20-day).
        volatility : float
            Standard deviation of returns (same frequency).  Must be > 0.

        Returns
        -------
        float
            Normalised risk-adjusted return score in ``[0, 1]``.
        """
        if volatility <= 0 or not math.isfinite(volatility):
            return 0.0
        sharpe_like = expected_return / volatility
        # tanh gives a smooth [0,1] mapping; 0.5 factor centres the knee
        score = math.tanh(0.5 * sharpe_like)
        return _clamp(score)

    @staticmethod
    def hedgeability_score(
        has_hedge: bool,
        hedge_cost: float,
    ) -> float:
        """Score the feasibility of hedging a position.

        Parameters
        ----------
        has_hedge : bool
            Whether a liquid hedge instrument exists (futures / options / ETF).
        hedge_cost : float
            Annualised hedge cost in percent (e.g. ``2.5`` for 2.5 %).
            Lower is better.

        Returns
        -------
        float
            Hedgeability score in ``[0, 1]``.
        """
        if not has_hedge:
            return 0.0

        # Cost penalty: 0% cost → 1.0, 5% cost → 0.5, 10% cost → 0.33, 20%+ → ~0.2
        cost_factor = 1.0 / (1.0 + 0.1 * max(0.0, hedge_cost))
        return _clamp(cost_factor)

    @staticmethod
    def execution_feasibility_score(
        spread_pct: float,
        avg_slippage: float,
    ) -> float:
        """Score how easy it is to execute the trade without excessive slippage.

        Parameters
        ----------
        spread_pct : float
            Bid-ask spread as a percentage of mid-price (e.g. ``0.05`` for 5 bps).
        avg_slippage : float
            Historical average slippage in percent (e.g. ``0.02`` for 2 bps).

        Returns
        -------
        float
            Execution feasibility score in ``[0, 1]``.
        """
        total_cost = max(0.0, spread_pct) + max(0.0, avg_slippage)
        # Exponential decay: 0 cost → 1.0, 1% total cost → ~0.37
        score = math.exp(-total_cost)
        return _clamp(score)

    @staticmethod
    def confidence_score(
        strategy_strength: float,
        data_quality: float,
        model_fit: float,
    ) -> float:
        """Compute a composite confidence score.

        The confidence is the geometric mean of the three inputs, which
        penalises weak links more aggressively than an arithmetic mean.

        Parameters
        ----------
        strategy_strength : float
            Raw signal strength ``[0, 1]``.
        data_quality : float
            Data completeness / freshness ``[0, 1]``.
        model_fit : float
            Model fit quality (R², cointegration p-value, etc.) ``[0, 1]``.

        Returns
        -------
        float
            Confidence score in ``[0, 1]``.
        """
        s = _clamp(strategy_strength)
        d = _clamp(data_quality)
        m = _clamp(model_fit)

        if s <= 0 or d <= 0 or m <= 0:
            return 0.0

        # Geometric mean — penalises weak links
        geometric_mean = (s * d * m) ** (1.0 / 3.0)
        return _clamp(geometric_mean)
