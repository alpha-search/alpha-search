"""Pydantic data models for Alpha Search Global Multi-Asset Opportunity Discovery.

Defines the core data structures used throughout the opportunity scanning
pipeline across global multi-asset markets:
- StockOpportunity: Single-instrument trading opportunities (momentum / mean-reversion)
- PairOpportunity: Statistical arbitrage pair-trading opportunities

Models are asset-class agnostic and support US equities, Indian equities,
crypto, forex, and commodities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _now_utc() -> datetime:
    """Return current timestamp in UTC."""
    return datetime.now(timezone.utc)


class StockOpportunity(BaseModel):
    """A single-stock trading opportunity discovered by one of the strategy engines.

    Attributes
    ----------
    ticker : str
        Exchange ticker (e.g. ``"AAPL"`` for US, ``"RELIANCE.NS"`` for India,
        ``"BTC-USD"`` for crypto, ``"EURUSD=X"`` for FX).
    company_name : str
        Human-readable company name.
    sector : str
        Business sector (e.g. ``"IT"``, ``"Financial Services"``).
    strategy_type : {"momentum", "mean_reversion", "arbitrage"}
        Which scanning engine generated this opportunity.
    signal_direction : {"long", "short", "pair_trade", "watch", "avoid"}
        Recommended trade direction.
    confidence_score : float
        Overall opportunity confidence in ``[0, 1]``.
    liquidity_score : float
        Liquidity assessment in ``[0, 1]``.
    sentiment_score : float
        Sentiment assessment in ``[0, 1]``.
    volatility_score : float
        Volatility assessment in ``[0, 1]``.
    momentum_score : float
        Momentum sub-score in ``[0, 1]``.
    mean_reversion_score : float
        Mean-reversion sub-score in ``[0, 1]``.
    correlation_score : float
        Correlation sub-score in ``[0, 1]``.
    cointegration_score : float
        Cointegration sub-score in ``[0, 1]``.
    hedge_candidate : bool
        Whether the stock is suitable as a hedge leg.
    news_summary : str
        Brief summary of recent news / sentiment.
    risk_summary : str
        Key downside risks (at least two bullet points).
    thesis : str
        Human-readable investment thesis (2-4 sentences).
    recommended_action : str
        Actionable trade recommendation.
    created_at : datetime
        Timestamp in UTC when the opportunity was created.
    """

    ticker: str = Field(..., description="Exchange ticker (e.g. AAPL, RELIANCE.NS, BTC-USD)")
    company_name: str = Field(..., description="Human-readable company name")
    sector: str = Field(..., description="Business sector")
    strategy_type: Literal["momentum", "mean_reversion", "arbitrage"] = Field(
        ..., description="Strategy that generated this opportunity"
    )
    signal_direction: Literal["long", "short", "pair_trade", "watch", "avoid"] = Field(
        ..., description="Recommended trade direction"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall opportunity confidence [0,1]"
    )
    liquidity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Liquidity assessment [0,1]"
    )
    sentiment_score: float = Field(
        ..., ge=0.0, le=1.0, description="Sentiment assessment [0,1]"
    )
    volatility_score: float = Field(
        ..., ge=0.0, le=1.0, description="Volatility assessment [0,1]"
    )
    momentum_score: float = Field(
        ..., ge=0.0, le=1.0, description="Momentum sub-score [0,1]"
    )
    mean_reversion_score: float = Field(
        ..., ge=0.0, le=1.0, description="Mean-reversion sub-score [0,1]"
    )
    correlation_score: float = Field(
        ..., ge=0.0, le=1.0, description="Correlation sub-score [0,1]"
    )
    cointegration_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cointegration sub-score [0,1]"
    )
    hedge_candidate: bool = Field(
        ..., description="Whether the stock is suitable as a hedge leg"
    )
    news_summary: str = Field(default="", description="Recent news / sentiment summary")
    risk_summary: str = Field(..., description="Key downside risk factors")
    thesis: str = Field(..., description="Human-readable investment thesis")
    recommended_action: str = Field(..., description="Actionable trade recommendation")
    created_at: datetime = Field(
        default_factory=_now_utc, description="UTC timestamp of creation"
    )

    @field_validator("confidence_score", "liquidity_score", "sentiment_score",
                     "volatility_score", "momentum_score", "mean_reversion_score",
                     "correlation_score", "cointegration_score", mode="before")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        """Clamp any score to the [0, 1] range."""
        if v is None:
            return 0.0
        return float(max(0.0, min(1.0, v)))

    class Config:
        json_encoders = {datetime: lambda d: d.isoformat()}
        str_strip_whitespace = True


class PairOpportunity(BaseModel):
    """A statistical-arbitrage pair-trading opportunity.

    Attributes
    ----------
    stock_a : str
        First leg ticker (e.g. ``"AAPL"``, ``"BTC-USD"``).
    stock_b : str
        Second leg ticker (e.g. ``"MSFT"``, ``"ETH-USD"``).
    sector_a : str
        Sector of ``stock_a``.
    sector_b : str
        Sector of ``stock_b``.
    correlation : float
        Pearson correlation of the two price series.
    cointegration_score : float
        Cointegration strength in ``[0, 1]``.
    spread_zscore : float
        Current z-score of the price spread.
    beta_difference : float
        Difference between pair-beta and market-beta.
    sentiment_divergence : float
        Difference in sentiment scores of the two stocks.
    liquidity_score : float
        Combined liquidity score in ``[0, 1]``.
    hedge_ratio : float
        OLS hedge ratio (units of ``stock_b`` per unit of ``stock_a``).
    suggested_trade : str
        Actionable pair-trade recommendation.
    thesis : str
        Human-readable pair-trade thesis.
    risk_summary : str
        Key downside risks for the pair trade.
    confidence_score : float
        Overall confidence in ``[0, 1]``.
    created_at : datetime
        UTC timestamp when the opportunity was created.
    """

    stock_a: str = Field(..., description="First leg ticker (any asset class)")
    stock_b: str = Field(..., description="Second leg ticker (any asset class)")
    sector_a: str = Field(..., description="Sector of stock_a")
    sector_b: str = Field(..., description="Sector of stock_b")
    correlation: float = Field(..., description="Pearson correlation of price series")
    cointegration_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cointegration strength [0,1]"
    )
    spread_zscore: float = Field(..., description="Current spread z-score")
    beta_difference: float = Field(
        ..., description="Difference between pair-beta and market-beta"
    )
    sentiment_divergence: float = Field(
        ..., description="Sentiment score difference between the two stocks"
    )
    liquidity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Combined liquidity score [0,1]"
    )
    hedge_ratio: float = Field(
        ..., description="OLS hedge ratio (units of stock_b per unit of stock_a)"
    )
    suggested_trade: str = Field(..., description="Actionable pair-trade recommendation")
    thesis: str = Field(..., description="Human-readable pair-trade thesis")
    risk_summary: str = Field(..., description="Key downside risks for the pair trade")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence [0,1]"
    )
    created_at: datetime = Field(
        default_factory=_now_utc, description="UTC timestamp of creation"
    )

    @field_validator("cointegration_score", "liquidity_score", "confidence_score", mode="before")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        """Clamp any score to the [0, 1] range."""
        if v is None:
            return 0.0
        return float(max(0.0, min(1.0, v)))

    class Config:
        json_encoders = {datetime: lambda d: d.isoformat()}
        str_strip_whitespace = True
