---
name: alpha-search-global-market-opportunity-discovery
description: Discover and rank global multi-asset trading opportunities across momentum, mean reversion, and statistical arbitrage strategies. Scan US equities (S&P 500, NASDAQ 100, DOW 30), Indian equities (NIFTY 50), cryptocurrencies, forex pairs, and commodities. Score opportunities and feed the Alpha Search frontend opportunity board.
---

# Alpha Search Global Market Opportunity Discovery

## When to Use This Skill

Use this skill when discovering, scoring, and ranking trading opportunities in global multi-asset markets. This includes running momentum scans on S&P 500 / NASDAQ 100 / NIFTY 50 stocks, detecting mean reversion setups across crypto and FX, identifying cointegrated pairs for statistical arbitrage, computing composite opportunity scores, and producing ranked opportunity lists for the Alpha Search frontend opportunity board. Activate this skill when the opportunity board needs a refresh, when a pre-trade analysis is requested, or when any strategy scan needs execution across a multi-asset universe.

## Agent Role

You are the quantitative opportunity discovery specialist for Alpha Search. Your job is to surface only high-quality, actionable trading opportunities from global multi-asset markets. You combine technical analysis, statistical tests, sentiment analysis, and risk assessment to produce ranked opportunity lists. Every opportunity you emit must include a clear thesis, a risk summary, and defensible sub-scores. You do not recommend trades — you surface opportunities with quantified conviction levels.

You own: multi-asset universe management (US equities, Indian equities, crypto, FX, commodities), strategy scanning (momentum, mean reversion, arbitrage), composite scoring, ranking, risk summarization, and the opportunity feed consumed by the frontend board.

## Core Concepts

### Concept 1: Momentum Strategy

Momentum opportunities are found when an instrument shows strong directional continuation. Key indicators:
- 20-day returns > 10% (strong) or < -10% (weak, potential short)
- RSI in trending zone (40-80 for uptrend, 20-60 for downtrend)
- MACD histogram expanding in direction of trend
- ADX > 25 (trend strength confirmed)
- Volume 1.5x+ average (confirmation)

```python
from alpha_search.opportunities.strategies import momentum_scan

opportunities = momentum_scan(
    universe="SP500",
    min_adx=25,
    min_volume_ratio=1.5,
    data_provider=yfinance_provider,
)
```

### Concept 2: Mean Reversion Strategy

Mean reversion opportunities exist when an instrument deviates significantly from its rolling average. Key indicators:
- Price z-score > |2.0| vs 20-day rolling mean
- RSI > 70 (overbought -> short) or < 30 (oversold -> long)
- Bollinger Band position near upper/lower band
- Recent candle showing reversal pattern (optional)
- Volume not excessively high (avoid capitulation)

```python
from alpha_search.opportunities.strategies import mean_reversion_scan

opportunities = mean_reversion_scan(
    universe="NASDAQ100",
    zscore_threshold=2.0,
    data_provider=yfinance_provider,
)
```

### Concept 3: Statistical Arbitrage

Pairs trading opportunities require cointegrated instruments with diverging spreads:
- Correlation > 0.7 (historical price relationship)
- Cointegration p-value < 0.05 (Engle-Granger test)
- Spread z-score > |2.0| (current divergence)
- Hedge ratio from OLS regression
- Beta difference < 0.3 (similar systematic risk)

```python
from alpha_search.opportunities.strategies import arbitrage_scan

pairs = arbitrage_scan(
    universe="SP500",
    min_correlation=0.7,
    max_pairs=20,
    data_provider=yfinance_provider,
)
```

### Concept 4: Scoring Formula

All opportunities are ranked using a weighted composite:

```
Final Score =
  0.25 * strategy_signal_strength
+ 0.20 * liquidity_score
+ 0.15 * sentiment_score
+ 0.15 * risk_adjusted_return_score
+ 0.15 * hedgeability_score
+ 0.10 * execution_feasibility_score
```

Each sub-score is normalized to [0, 1] before weighting. The scoring formula is implemented in `scoring.py` and applied uniformly across all opportunity types.

```python
from alpha_search.opportunities.scoring import calculate_final_score

score = calculate_final_score(
    signal_strength=0.85,
    liquidity=0.92,
    sentiment=0.65,
    risk_adjusted_return=0.78,
    hedgeability=0.70,
    execution_feasibility=0.88,
)
# score = 0.25*0.85 + 0.20*0.92 + 0.15*0.65 + 0.15*0.78 + 0.15*0.70 + 0.10*0.88
# score ~ 0.8015
```

### Concept 5: Global Multi-Asset Market Context

The module is designed for global multi-asset market coverage:

**US Equities**
- **Universe**: S&P 500 (`SP500`), NASDAQ 100 (`NASDAQ100`), DOW 30 (`DOW30`)
- **Benchmark**: S&P 500 index (`^GSPC`) — default for US market beta
- **Ticker format**: Plain Yahoo Finance format, e.g. `AAPL`, `MSFT`, `GOOGL`

**Indian Equities**
- **Universe**: NIFTY 50 (`NIFTY50`)
- **Benchmark**: NIFTY 50 index (`^NSEI`)
- **Ticker format**: Yahoo Finance format with `.NS` suffix, e.g. `RELIANCE.NS`, `TCS.NS`

**Cryptocurrency**
- **Universe**: BTC, ETH, BNB, SOL, XRP, ADA (`CRYPTO`)
- **Ticker format**: Yahoo Finance format with `-USD` suffix, e.g. `BTC-USD`, `ETH-USD`
- **Benchmark**: BTC dominance or overall crypto market cap

**Forex (FX)**
- **Universe**: Major currency pairs (`FX`) — EUR/USD, GBP/USD, USD/JPY, etc.
- **Ticker format**: Yahoo Finance format with `=X` suffix, e.g. `EURUSD=X`

**Commodities**
- **Universe**: Gold, Silver, Crude Oil, Natural Gas, etc. (`COMMODITIES`)
- **Ticker format**: Yahoo Finance format with `=F` suffix, e.g. `GC=F`, `CL=F`

**FTSE 100 (UK)**
- **Universe**: FTSE 100 constituents (`FTSE100`)
- **Benchmark**: FTSE 100 index (`^FTSE`)
- **Ticker format**: `.L` suffix, e.g. `SHEL.L`, `AZN.L`

```python
from alpha_search.opportunities.market_universes import (
    get_universe_tickers,
    get_company_name,
    get_sector,
    get_benchmark_ticker,
)

# Load S&P 500 tickers
tickers = get_universe_tickers("SP500")
# Returns: ["AAPL", "MSFT", "GOOGL", "AMZN", ...]

# Load crypto tickers
crypto = get_universe_tickers("CRYPTO")
# Returns: ["BTC-USD", "ETH-USD", "BNB-USD", ...]

# Get company name
name = get_company_name("AAPL")
# Returns: "Apple Inc."

# Get sector for any ticker
sector = get_sector("AAPL")
# Returns: "Technology"

# Get benchmark for US market
benchmark = get_benchmark_ticker("US")
# Returns: "^GSPC"

# Get benchmark for Indian market
benchmark = get_benchmark_ticker("IN")
# Returns: "^NSEI"
```

## Complete Implementation

### Pydantic Models

```python
# alpha_search/opportunities/models.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class StockOpportunity(BaseModel):
    """A single-stock trading opportunity discovered by a strategy scanner.

    Emitted by momentum_scan, mean_reversion_scan, and consumed by the
    opportunity board and pre-trade analysis pipeline.
    """
    ticker: str = Field(..., description="Stock ticker (Yahoo Finance format)")
    strategy: Literal["momentum", "mean_reversion"] = Field(..., description="Strategy that generated this opportunity")
    direction: Literal["long", "short"] = Field(..., description="Recommended direction")

    # Scores
    final_score: float = Field(..., ge=0.0, le=1.0, description="Composite opportunity score [0, 1]")
    signal_strength: float = Field(..., ge=0.0, le=1.0, description="Raw strategy signal strength")
    liquidity_score: float = Field(..., ge=0.0, le=1.0, description="Liquidity assessment [0, 1]")
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="FinBERT composite sentiment [0, 1]")
    risk_adjusted_return_score: float = Field(..., ge=0.0, le=1.0, description="Risk/reward quality score")
    hedgeability_score: float = Field(..., ge=0.0, le=1.0, description="Ability to hedge this position")
    execution_feasibility_score: float = Field(..., ge=0.0, le=1.0, description="Ease of execution")

    # Analysis
    thesis: str = Field(..., description="Human-readable opportunity thesis")
    risk_summary: str = Field(..., description="Key risks and downside scenarios")
    key_levels: dict = Field(default_factory=dict, description="Support/resistance/target levels")

    # Market context
    sector: Optional[str] = Field(None, description="Sector classification")
    beta: Optional[float] = Field(None, description="Beta vs market benchmark")
    market_cap_category: Optional[Literal["Large", "Mid", "Small"]] = Field(None)

    # Metadata
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence [0, 1]")
    scan_timestamp: datetime = Field(default_factory=lambda: datetime.now())
    lookback_days: int = Field(default=60, description="Historical window used for scanning")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PairOpportunity(BaseModel):
    """A statistical arbitrage pair opportunity discovered by the scanner.

    Represents a mean-reverting spread between two cointegrated instruments.
    Works across any asset class — equities, crypto, FX, or commodities.
    """
    ticker_long: str = Field(..., description="Long leg ticker")
    ticker_short: str = Field(..., description="Short leg ticker")
    strategy: Literal["statistical_arbitrage"] = "statistical_arbitrage"

    # Pair statistics
    correlation: float = Field(..., ge=-1.0, le=1.0, description="Historical correlation")
    cointegration_pvalue: float = Field(..., ge=0.0, le=1.0, description="Engle-Granger test p-value")
    spread_zscore: float = Field(..., description="Current spread z-score")
    hedge_ratio: float = Field(..., description="OLS hedge ratio (long/short notional)")
    half_life: Optional[float] = Field(None, description="Estimated mean reversion half-life in days")

    # Scores
    final_score: float = Field(..., ge=0.0, le=1.0, description="Composite opportunity score [0, 1]")
    signal_strength: float = Field(..., ge=0.0, le=1.0, description="Spread divergence strength")
    liquidity_score: float = Field(..., ge=0.0, le=1.0, description="Combined pair liquidity")
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="Net sentiment differential")
    risk_adjusted_return_score: float = Field(..., ge=0.0, le=1.0, description="Expected risk-adjusted return")
    hedgeability_score: float = Field(..., ge=0.0, le=1.0, description="Portfolio hedge value")
    execution_feasibility_score: float = Field(..., ge=0.0, le=1.0, description="Execution difficulty")

    # Analysis
    thesis: str = Field(..., description="Why this pair will mean-revert")
    risk_summary: str = Field(..., description="Pair-specific risks (regime change, divergence)")
    entry_threshold: float = Field(default=2.0, description="Z-score entry level")
    exit_threshold: float = Field(default=0.5, description="Z-score exit/target level")

    # Metadata
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence [0, 1]")
    scan_timestamp: datetime = Field(default_factory=lambda: datetime.now())
    lookback_days: int = Field(default=120, description="Historical window for cointegration test")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
```

### Strategy Implementations

```python
# alpha_search/opportunities/strategies.py
import pandas as pd
import numpy as np
from typing import Sequence, Optional
from datetime import datetime, timedelta
from scipy import stats

from alpha_search.opportunities.models import StockOpportunity, PairOpportunity
from alpha_search.opportunities.market_universes import get_universe_tickers
from alpha_search.opportunities.scoring import calculate_final_score, normalize_to_unit


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators used by multiple strategies."""
    close = df["close"]

    # RSI (14-period)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # ADX (trend strength)
    high, low = df["high"], df["low"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, min_periods=14).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/14, min_periods=14).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/14, min_periods=14).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["adx"] = dx.ewm(alpha=1/14, min_periods=14).mean()

    # Bollinger Bands
    df["bb_mid"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    df["bb_position"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)

    # Volume ratio
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan)

    # 20-day return
    df["return_20d"] = close.pct_change(20)

    # Z-score vs 20-day rolling
    rolling_mean = close.rolling(20).mean()
    rolling_std = close.rolling(20).std().replace(0, np.nan)
    df["zscore"] = (close - rolling_mean) / rolling_std

    return df


def momentum_scan(
    data_provider,
    universe: str = "SP500",
    min_adx: float = 25.0,
    min_volume_ratio: float = 1.5,
    min_return_20d: float = 0.10,
    lookback_days: int = 60,
    sentiment_provider=None,
) -> list[StockOpportunity]:
    """Scan universe for momentum opportunities.

    Identifies instruments with strong directional continuation backed by volume
    and trend strength confirmation. Returns both long (uptrend) and short
    (downtrend) opportunities.

    Parameters
    ----------
    data_provider : DataProvider
        OHLCV data provider with a ``get_prices(ticker, start, end)`` method.
    universe : str
        Market universe identifier ("SP500", "NASDAQ100", "NIFTY50", "CRYPTO", etc.).
    min_adx : float
        Minimum ADX threshold for trend strength (default 25).
    min_volume_ratio : float
        Minimum volume spike ratio for confirmation (default 1.5).
    min_return_20d : float
        Minimum 20-day return magnitude to qualify (default 0.10 = 10%).
    lookback_days : int
        Historical data window in days (default 60).
    sentiment_provider : optional
        Sentiment analyzer with ``get_sentiment(ticker)`` method.

    Returns
    -------
    list[StockOpportunity]
        Ranked list of momentum opportunities.
    """
    tickers = get_universe_tickers(universe)
    opportunities = []

    end = datetime.now()
    start = end - timedelta(days=lookback_days + 20)  # Extra for indicator warmup

    for ticker in tickers:
        try:
            ohlcv = data_provider.get_prices(ticker, start=start.date(), end=end.date())
            df = ohlcv.to_dataframe()
            if len(df) < 30:
                continue

            df = _add_indicators(df)
            latest = df.iloc[-1]

            # Check ADX threshold
            if latest["adx"] < min_adx:
                continue

            # Check volume confirmation
            if latest["volume_ratio"] < min_volume_ratio:
                continue

            ret_20d = latest["return_20d"]
            if pd.isna(ret_20d):
                continue

            # Determine direction
            if ret_20d >= min_return_20d:
                direction = "long"
                rsi_zone = 40 <= latest["rsi"] <= 80
                macd_expanding = latest["macd_hist"] > df["macd_hist"].iloc[-5]
            elif ret_20d <= -min_return_20d:
                direction = "short"
                rsi_zone = 20 <= latest["rsi"] <= 60
                macd_expanding = latest["macd_hist"] < df["macd_hist"].iloc[-5]
            else:
                continue

            # Signal strength: composite of return magnitude, RSI alignment, MACD
            signal_strength = min(abs(ret_20d) / 0.20, 1.0)  # Normalize: 20% = max
            signal_strength *= 0.6 + 0.2 * (1.0 if rsi_zone else 0.5)
            signal_strength *= 0.6 + 0.2 * (1.0 if macd_expanding else 0.5)
            signal_strength = min(signal_strength, 1.0)

            # Liquidity score
            avg_volume = df["volume"].tail(20).mean()
            liquidity_score = normalize_to_unit(np.log1p(avg_volume), low=10, high=20)

            # Sentiment score (from FinBERT pipeline if available)
            sentiment_score = 0.5  # Default neutral
            if sentiment_provider:
                sentiment_score = sentiment_provider.get_sentiment(ticker)

            # Risk-adjusted return
            daily_returns = df["close"].pct_change().dropna()
            ann_vol = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 1.0
            sharpe = (ret_20d * 12) / (ann_vol + 1e-6)  # Annualized approx
            risk_adj_score = normalize_to_unit(sharpe, low=-1.0, high=2.0)

            # Hedgeability
            hedgeability_score = 0.7  # Single instrument hedgeable via options/index

            # Execution feasibility
            execution_score = min(0.5 + latest["volume_ratio"] * 0.2, 1.0)

            final_score = calculate_final_score(
                signal_strength=signal_strength,
                liquidity=liquidity_score,
                sentiment=sentiment_score,
                risk_adjusted_return=risk_adj_score,
                hedgeability=hedgeability_score,
                execution_feasibility=execution_score,
            )

            thesis = (
                f"{ticker} showing {direction} momentum: "
                f"20d return {ret_20d:.1%}, ADX {latest['adx']:.1f} "
                f"(trend strength confirmed), volume {latest['volume_ratio']:.1f}x avg. "
                f"RSI {latest['rsi']:.1f} in trending zone. "
                f"MACD histogram {'expanding' if macd_expanding else 'stable'}."
            )

            risk_summary = (
                f"Downside: Trend reversal if ADX drops below {min_adx}. "
                f"Volume spike could signal exhaustion. "
                f"Broad market correction would impact beta-exposed position."
            )

            opp = StockOpportunity(
                ticker=ticker,
                strategy="momentum",
                direction=direction,
                final_score=round(final_score, 4),
                signal_strength=round(signal_strength, 4),
                liquidity_score=round(liquidity_score, 4),
                sentiment_score=round(sentiment_score, 4),
                risk_adjusted_return_score=round(risk_adj_score, 4),
                hedgeability_score=round(hedgeability_score, 4),
                execution_feasibility_score=round(execution_score, 4),
                thesis=thesis,
                risk_summary=risk_summary,
                key_levels={
                    "support": round(float(df["bb_lower"].iloc[-1]), 2),
                    "resistance": round(float(df["bb_upper"].iloc[-1]), 2),
                    "target_20d_return": round(float(ret_20d * 1.2), 4),
                },
                confidence_score=round(final_score * 0.9 + 0.1, 4),
                lookback_days=lookback_days,
            )
            opportunities.append(opp)

        except Exception:
            continue

    # Sort by final score descending
    opportunities.sort(key=lambda x: x.final_score, reverse=True)
    return opportunities


def mean_reversion_scan(
    data_provider,
    universe: str = "SP500",
    zscore_threshold: float = 2.0,
    lookback_days: int = 60,
    sentiment_provider=None,
) -> list[StockOpportunity]:
    """Scan universe for mean reversion opportunities.

    Identifies instruments that have deviated significantly from their rolling
    average and are likely to revert. Returns both long (oversold) and
    short (overbought) opportunities.

    Parameters
    ----------
    data_provider : DataProvider
        OHLCV data provider.
    universe : str
        Market universe identifier ("SP500", "NASDAQ100", "NIFTY50", "CRYPTO", etc.).
    zscore_threshold : float
        Z-score magnitude considered "extreme" (default 2.0).
    lookback_days : int
        Historical data window in days (default 60).
    sentiment_provider : optional
        Sentiment analyzer.

    Returns
    -------
    list[StockOpportunity]
        Ranked list of mean-reversion opportunities.
    """
    tickers = get_universe_tickers(universe)
    opportunities = []

    end = datetime.now()
    start = end - timedelta(days=lookback_days + 20)

    for ticker in tickers:
        try:
            ohlcv = data_provider.get_prices(ticker, start=start.date(), end=end.date())
            df = ohlcv.to_dataframe()
            if len(df) < 30:
                continue

            df = _add_indicators(df)
            latest = df.iloc[-1]
            z = latest["zscore"]

            if pd.isna(z) or abs(z) < zscore_threshold:
                continue

            # Check RSI confirmation
            rsi = latest["rsi"]
            if z > zscore_threshold and rsi < 65:
                continue  # Overbought but RSI not confirming
            if z < -zscore_threshold and rsi > 35:
                continue  # Oversold but RSI not confirming

            # Direction: positive zscore = overbought -> short; negative = oversold -> long
            direction = "short" if z > 0 else "long"

            # Signal strength: how far beyond threshold
            signal_strength = min((abs(z) - zscore_threshold) / 1.0 + 0.5, 1.0)

            # Check volume (avoid capitulation)
            vol_ratio = latest["volume_ratio"]
            if vol_ratio > 3.0:
                signal_strength *= 0.7  # Penalize extreme volume (possible capitulation)

            # Liquidity score
            avg_volume = df["volume"].tail(20).mean()
            liquidity_score = normalize_to_unit(np.log1p(avg_volume), low=10, high=20)

            # Sentiment
            sentiment_score = 0.5
            if sentiment_provider:
                sentiment_score = sentiment_provider.get_sentiment(ticker)

            # Risk-adjusted: expected reversion magnitude / volatility
            daily_returns = df["close"].pct_change().dropna()
            ann_vol = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 1.0
            expected_reversion = abs(z) * daily_returns.std() * np.sqrt(5)  # 5-day expected
            risk_adj_score = normalize_to_unit(expected_reversion / (ann_vol + 1e-6), low=0, high=0.5)

            hedgeability_score = 0.7
            execution_score = min(0.5 + vol_ratio * 0.15, 1.0)

            final_score = calculate_final_score(
                signal_strength=signal_strength,
                liquidity=liquidity_score,
                sentiment=sentiment_score,
                risk_adjusted_return=risk_adj_score,
                hedgeability=hedgeability_score,
                execution_feasibility=execution_score,
            )

            thesis = (
                f"{ticker} mean reversion {direction}: z-score {z:.2f} "
                f"(threshold +/-{zscore_threshold}), RSI {rsi:.1f}. "
                f"Price {'above' if z > 0 else 'below'} 20-day BB "
                f"at {latest['bb_position']:.1%} of band width. "
                f"Expected reversion to rolling mean over 3-5 sessions."
            )

            risk_summary = (
                f"Downside: Trend continuation instead of reversion if momentum "
                f"is driven by fundamental catalyst. Capitulation volume ({vol_ratio:.1f}x) "
                f"may indicate further move. Set stop beyond {abs(z)+0.5:.1f} sigma."
            )

            opp = StockOpportunity(
                ticker=ticker,
                strategy="mean_reversion",
                direction=direction,
                final_score=round(final_score, 4),
                signal_strength=round(signal_strength, 4),
                liquidity_score=round(liquidity_score, 4),
                sentiment_score=round(sentiment_score, 4),
                risk_adjusted_return_score=round(risk_adj_score, 4),
                hedgeability_score=round(hedgeability_score, 4),
                execution_feasibility_score=round(execution_score, 4),
                thesis=thesis,
                risk_summary=risk_summary,
                key_levels={
                    "rolling_mean": round(float(df["bb_mid"].iloc[-1]), 2),
                    "bb_lower": round(float(df["bb_lower"].iloc[-1]), 2),
                    "bb_upper": round(float(df["bb_upper"].iloc[-1]), 2),
                    "zscore_current": round(float(z), 2),
                },
                confidence_score=round(final_score * 0.85 + 0.1, 4),
                lookback_days=lookback_days,
            )
            opportunities.append(opp)

        except Exception:
            continue

    opportunities.sort(key=lambda x: x.final_score, reverse=True)
    return opportunities


def arbitrage_scan(
    data_provider,
    universe: str = "SP500",
    min_correlation: float = 0.7,
    max_pairs: int = 20,
    coint_pvalue_threshold: float = 0.05,
    spread_zscore_threshold: float = 2.0,
    lookback_days: int = 120,
) -> list[PairOpportunity]:
    """Scan universe for statistical arbitrage pair opportunities.

    Tests all pairs for cointegration, identifies those with diverging
    spreads beyond the z-score threshold, and returns ranked pair
    opportunities with hedge ratios.

    Parameters
    ----------
    data_provider : DataProvider
        OHLCV data provider.
    universe : str
        Market universe identifier ("SP500", "NASDAQ100", "NIFTY50", etc.).
    min_correlation : float
        Minimum Pearson correlation to consider a pair (default 0.7).
    max_pairs : int
        Maximum number of pairs to return (default 20).
    coint_pvalue_threshold : float
        Cointegration p-value threshold (default 0.05).
    spread_zscore_threshold : float
        Minimum spread z-score magnitude (default 2.0).
    lookback_days : int
        Historical data window in days (default 120).

    Returns
    -------
    list[PairOpportunity]
        Ranked list of pair opportunities.
    """
    tickers = get_universe_tickers(universe)
    if len(tickers) < 2:
        return []

    end = datetime.now()
    start = end - timedelta(days=lookback_days + 10)

    # Fetch all prices
    price_data = {}
    for ticker in tickers:
        try:
            ohlcv = data_provider.get_prices(ticker, start=start.date(), end=end.date())
            df = ohlcv.to_dataframe()
            if len(df) > 40:
                price_data[ticker] = df["close"]
        except Exception:
            continue

    if len(price_data) < 2:
        return []

    # Align price series
    price_df = pd.DataFrame(price_data).dropna(axis=1, thresh=30).dropna()
    if price_df.empty or len(price_df.columns) < 2:
        return []

    # Compute returns for correlation
    returns_df = price_df.pct_change().dropna()
    tickers_available = list(price_df.columns)

    from itertools import combinations

    pairs = []
    for t1, t2 in combinations(tickers_available, 2):
        try:
            # Correlation
            corr = returns_df[t1].corr(returns_df[t2])
            if pd.isna(corr) or corr < min_correlation:
                continue

            # Cointegration test (Engle-Granger)
            from statsmodels.tsa.stattools import coint
            score, pvalue, _ = coint(price_df[t1], price_df[t2])
            if pvalue > coint_pvalue_threshold:
                continue

            # OLS hedge ratio
            import statsmodels.api as sm
            X = sm.add_constant(price_df[t2])
            model = sm.OLS(price_df[t1], X).fit()
            hedge_ratio = model.params.iloc[1] if len(model.params) > 1 else 1.0

            # Spread and z-score
            spread = price_df[t1] - hedge_ratio * price_df[t2]
            spread_mean = spread.mean()
            spread_std = spread.std()
            if spread_std == 0:
                continue
            spread_z = (spread.iloc[-1] - spread_mean) / spread_std

            if abs(spread_z) < spread_zscore_threshold:
                continue

            # Half-life of mean reversion
            spread_lag = spread.shift(1)
            spread_diff = spread.diff()
            valid = spread_lag.notna() & spread_diff.notna()
            if valid.sum() > 10:
                hl_model = sm.OLS(spread_diff[valid], spread_lag[valid]).fit()
                theta = hl_model.params.iloc[0] if len(hl_model.params) > 0 else -0.1
                half_life = -np.log(2) / theta if theta < 0 else None
            else:
                half_life = None

            # Determine direction: positive spread_z -> t1 overpriced -> short t1, long t2
            if spread_z > 0:
                ticker_long, ticker_short = t2, t1
            else:
                ticker_long, ticker_short = t1, t2

            # Scores
            signal_strength = min((abs(spread_z) - spread_zscore_threshold) / 1.0 + 0.5, 1.0)
            signal_strength *= corr  # Weight by correlation strength

            # Liquidity: average of both legs
            vol1 = price_df[t1].count()  # Proxy for liquidity
            vol2 = price_df[t2].count()
            liquidity_score = normalize_to_unit(min(vol1, vol2), low=20, high=100)

            sentiment_score = 0.5
            risk_adj_score = normalize_to_unit(1.0 / (1 + (half_life or 20)), low=0, high=0.1)
            hedgeability_score = 0.8  # Market-neutral pairs are good hedges
            execution_score = 0.7

            final_score = calculate_final_score(
                signal_strength=signal_strength,
                liquidity=liquidity_score,
                sentiment=sentiment_score,
                risk_adjusted_return=risk_adj_score,
                hedgeability=hedgeability_score,
                execution_feasibility=execution_score,
            )

            thesis = (
                f"Pair {ticker_long}/{ticker_short}: correlation {corr:.2f}, "
                f"cointegration p={pvalue:.3f}. Spread z-score {spread_z:.2f} "
                f"(threshold +/-{spread_zscore_threshold}). Hedge ratio {hedge_ratio:.3f}. "
                f"{'Half-life ' + f'{half_life:.1f} days' if half_life else 'Half-life not estimated'}. "
                f"Mean-reversion trade: long {ticker_long}, short {ticker_short}."
            )

            risk_summary = (
                f"Downside: Cointegration break (regime change in one instrument). "
                f"Spread may diverge further before reverting. "
                f"Half-life of {(half_life or 20):.0f} days implies patience required. "
                f"Monitor for fundamental divergence between pair constituents."
            )

            pair = PairOpportunity(
                ticker_long=ticker_long,
                ticker_short=ticker_short,
                correlation=round(float(corr), 4),
                cointegration_pvalue=round(float(pvalue), 4),
                spread_zscore=round(float(spread_z), 4),
                hedge_ratio=round(float(hedge_ratio), 4),
                half_life=round(float(half_life), 2) if half_life else None,
                final_score=round(final_score, 4),
                signal_strength=round(signal_strength, 4),
                liquidity_score=round(liquidity_score, 4),
                sentiment_score=round(sentiment_score, 4),
                risk_adjusted_return_score=round(risk_adj_score, 4),
                hedgeability_score=round(hedgeability_score, 4),
                execution_feasibility_score=round(execution_score, 4),
                thesis=thesis,
                risk_summary=risk_summary,
                confidence_score=round(final_score * 0.85 + 0.1, 4),
                lookback_days=lookback_days,
            )
            pairs.append(pair)

        except Exception:
            continue

    # Sort by final score descending, take top N
    pairs.sort(key=lambda x: x.final_score, reverse=True)
    return pairs[:max_pairs]
```

### Scoring Module

```python
# alpha_search/opportunities/scoring.py
import numpy as np


WEIGHTS = {
    "signal_strength": 0.25,
    "liquidity": 0.20,
    "sentiment": 0.15,
    "risk_adjusted_return": 0.15,
    "hedgeability": 0.15,
    "execution_feasibility": 0.10,
}


def calculate_final_score(
    signal_strength: float,
    liquidity: float,
    sentiment: float,
    risk_adjusted_return: float,
    hedgeability: float,
    execution_feasibility: float,
) -> float:
    """Calculate the composite final score using the weighted formula.

    All inputs must be in [0, 1]. Returns a score in [0, 1].

    Formula:
        Final = 0.25*signal + 0.20*liquidity + 0.15*sentiment
              + 0.15*risk_adj + 0.15*hedgeability + 0.10*execution
    """
    scores = {
        "signal_strength": np.clip(signal_strength, 0.0, 1.0),
        "liquidity": np.clip(liquidity, 0.0, 1.0),
        "sentiment": np.clip(sentiment, 0.0, 1.0),
        "risk_adjusted_return": np.clip(risk_adjusted_return, 0.0, 1.0),
        "hedgeability": np.clip(hedgeability, 0.0, 1.0),
        "execution_feasibility": np.clip(execution_feasibility, 0.0, 1.0),
    }

    final = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS)
    return float(np.clip(final, 0.0, 1.0))


def normalize_to_unit(value: float, low: float, high: float) -> float:
    """Normalize a value to [0, 1] range using linear scaling.

    Values below low -> 0, values above high -> 1.

    Parameters
    ----------
    value : float
        Raw value to normalize.
    low : float
        Lower bound (maps to 0).
    high : float
        Upper bound (maps to 1).

    Returns
    -------
    float
        Normalized value in [0, 1].
    """
    if high <= low:
        return 0.5
    normalized = (value - low) / (high - low)
    return float(np.clip(normalized, 0.0, 1.0))


def score_to_grade(score: float) -> str:
    """Convert a numeric score to a letter grade for UI display.

    A+: >= 0.90    A: >= 0.80    B+: >= 0.70    B: >= 0.60
    C+: >= 0.50    C: >= 0.40    D: >= 0.30      F: < 0.30
    """
    if score >= 0.90:
        return "A+"
    elif score >= 0.80:
        return "A"
    elif score >= 0.70:
        return "B+"
    elif score >= 0.60:
        return "B"
    elif score >= 0.50:
        return "C+"
    elif score >= 0.40:
        return "C"
    elif score >= 0.30:
        return "D"
    return "F"
```

### Market Universe Utilities

```python
# alpha_search/opportunities/market_universes.py
from typing import Optional

# Supported universe tickers with Yahoo Finance format
# Static snapshots; in production, load from live APIs

NIFTY50_CONSTITUENTS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LICI.NS",
    "HDFC.NS", "BAJFINANCE.NS", "LT.NS", "KOTAKBANK.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "AXISBANK.NS", "MARUTI.NS", "TATAMOTORS.NS",
    "ADANIENT.NS", "NTPC.NS", "ONGC.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "ASIANPAINT.NS", "POWERGRID.NS", "NESTLEIND.NS", "BAJAJFINSV.NS",
    "M&M.NS", "WIPRO.NS", "ADANIPORTS.NS", "COALINDIA.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "TECHM.NS", "HINDALCO.NS", "GRASIM.NS", "CIPLA.NS",
    "SBILIFE.NS", "BRITANNIA.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "APOLLOHOSP.NS", "SHRIRAMFIN.NS", "TATACONSUM.NS", "HEROMOTOCO.NS",
    "INDUSINDBK.NS", "UPL.NS", "BPCL.NS",
]

SP500_CONSTITUENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "UNH", "JPM",
    "V", "JNJ", "WMT", "MA", "PG",
    "ORCL", "HD", "BAC", "KO", "MRK",
    "PEP", "COST", "TMO", "DIS", "ADBE",
    "PFE", "NFLX", "ABT", "CRM", "AMD",
]

NASDAQ100_CONSTITUENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "AVGO", "PEP", "COST",
    "NFLX", "ADBE", "AMD", "CMCSA", "TMUS",
    "INTC", "INTU", "QCOM", "AMGN", "HON",
]

CRYPTO_CONSTITUENTS = [
    "BTC-USD", "ETH-USD", "BNB-USD",
    "SOL-USD", "XRP-USD", "ADA-USD",
]

FX_CONSTITUENTS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    "USDCHF=X", "AUDUSD=X", "USDCAD=X",
    "NZDUSD=X", "EURGBP=X", "EURJPY=X",
    "GBPJPY=X",
]

COMMODITY_CONSTITUENTS = [
    "GC=F", "SI=F", "CL=F", "BZ=F",
    "NG=F", "HG=F", "PL=F", "PA=F",
    "ZC=F", "ZS=F", "ZW=F", "CT=F",
]

# Extended universe: NIFTY 100 additions
NIFTY100_ADDITIONS = [
    "GODREJCP.NS", "PIDILITIND.NS", "DABUR.NS", "HDFCLIFE.NS",
    "AMBUJACEM.NS", "DIVISLAB.NS", "BERGEPAINT.NS", "MARICO.NS",
    "ICICIPRULI.NS", "SIEMENS.NS", "TORNTPHARM.NS", "HAL.NS",
    "VEDL.NS", "MCDOWELL-N.NS", "BEL.NS", "IOB.NS", "TRENT.NS",
    "PFC.NS", "CANBK.NS", "UNIONBANK.NS", "RECLTD.NS", "BANKBARODA.NS",
    "JINDALSTEL.NS", "ADANIGREEN.NS", "ABB.NS", "INDIGO.NS",
    "IDBI.NS", "SAIL.NS", "CHOLAFIN.NS", "NAUKRI.NS", "BOSCHLTD.NS",
    "INDUSTOWER.NS", "YESBANK.NS", "HUDCO.NS", "GAIL.NS",
    "BANKINDIA.NS", "PAYTM.NS", "MOTHERSON.NS", "IRCTC.NS",
    "COLPAL.NS", "ATGL.NS", "DLF.NS", "ACC.NS", "HAVELLS.NS",
    "NHPC.NS", "INDIANB.NS", "LUPIN.NS", "AUROPHARMA.NS",
    "OBEROIRLTY.NS", "PAGEIND.NS",
]

# Sector classification mapping (NIFTY 50)
SECTOR_MAP = {
    "RELIANCE.NS": {"sector": "Energy", "industry": "Oil & Gas", "market_cap": "Large"},
    "TCS.NS": {"sector": "IT", "industry": "Software", "market_cap": "Large"},
    "HDFCBANK.NS": {"sector": "Financial", "industry": "Banking", "market_cap": "Large"},
    "INFY.NS": {"sector": "IT", "industry": "Software", "market_cap": "Large"},
    "ICICIBANK.NS": {"sector": "Financial", "industry": "Banking", "market_cap": "Large"},
    "HINDUNILVR.NS": {"sector": "Consumer", "industry": "FMCG", "market_cap": "Large"},
    "SBIN.NS": {"sector": "Financial", "industry": "Banking", "market_cap": "Large"},
    "BHARTIARTL.NS": {"sector": "Telecom", "industry": "Telecom", "market_cap": "Large"},
    "ITC.NS": {"sector": "Consumer", "industry": "FMCG", "market_cap": "Large"},
    "LT.NS": {"sector": "Infrastructure", "industry": "Construction", "market_cap": "Large"},
    "BAJFINANCE.NS": {"sector": "Financial", "industry": "NBFC", "market_cap": "Large"},
    "KOTAKBANK.NS": {"sector": "Financial", "industry": "Banking", "market_cap": "Large"},
    "HCLTECH.NS": {"sector": "IT", "industry": "Software", "market_cap": "Large"},
    "SUNPHARMA.NS": {"sector": "Pharma", "industry": "Pharma", "market_cap": "Large"},
    "MARUTI.NS": {"sector": "Auto", "industry": "Auto", "market_cap": "Large"},
    "TATAMOTORS.NS": {"sector": "Auto", "industry": "Auto", "market_cap": "Large"},
    "ADANIENT.NS": {"sector": "Diversified", "industry": "Conglomerate", "market_cap": "Large"},
    "NTPC.NS": {"sector": "Power", "industry": "Power", "market_cap": "Large"},
    "TITAN.NS": {"sector": "Consumer", "industry": "Jewellery", "market_cap": "Large"},
    "ASIANPAINT.NS": {"sector": "Consumer", "industry": "Paints", "market_cap": "Large"},
    "WIPRO.NS": {"sector": "IT", "industry": "Software", "market_cap": "Large"},
    "AXISBANK.NS": {"sector": "Financial", "industry": "Banking", "market_cap": "Large"},
    "POWERGRID.NS": {"sector": "Power", "industry": "Power", "market_cap": "Large"},
    "ULTRACEMCO.NS": {"sector": "Cement", "industry": "Cement", "market_cap": "Large"},
    "NESTLEIND.NS": {"sector": "Consumer", "industry": "FMCG", "market_cap": "Large"},
    "HDFC.NS": {"sector": "Financial", "industry": "Housing Finance", "market_cap": "Large"},
    "ONGC.NS": {"sector": "Energy", "industry": "Oil & Gas", "market_cap": "Large"},
    "JSWSTEEL.NS": {"sector": "Metals", "industry": "Steel", "market_cap": "Large"},
    "COALINDIA.NS": {"sector": "Energy", "industry": "Mining", "market_cap": "Large"},
}

# S&P 500 sector map
SP500_SECTOR_MAP = {
    "AAPL": {"sector": "Technology", "industry": "Consumer Electronics", "market_cap": "Large"},
    "MSFT": {"sector": "Technology", "industry": "Software", "market_cap": "Large"},
    "GOOGL": {"sector": "Communication Services", "industry": "Internet", "market_cap": "Large"},
    "AMZN": {"sector": "Consumer Discretionary", "industry": "E-Commerce", "market_cap": "Large"},
    "NVDA": {"sector": "Technology", "industry": "Semiconductors", "market_cap": "Large"},
    "META": {"sector": "Communication Services", "industry": "Social Media", "market_cap": "Large"},
    "TSLA": {"sector": "Consumer Discretionary", "industry": "Automotive", "market_cap": "Large"},
    "BRK-B": {"sector": "Financials", "industry": "Conglomerate", "market_cap": "Large"},
    "UNH": {"sector": "Health Care", "industry": "Managed Care", "market_cap": "Large"},
    "JPM": {"sector": "Financials", "industry": "Banking", "market_cap": "Large"},
    "V": {"sector": "Financials", "industry": "Payments", "market_cap": "Large"},
    "JNJ": {"sector": "Health Care", "industry": "Pharma", "market_cap": "Large"},
    "WMT": {"sector": "Consumer Staples", "industry": "Retail", "market_cap": "Large"},
    "MA": {"sector": "Financials", "industry": "Payments", "market_cap": "Large"},
    "PG": {"sector": "Consumer Staples", "industry": "Household", "market_cap": "Large"},
}

# CRYPTO sector map
CRYPTO_SECTOR_MAP = {
    "BTC-USD": {"sector": "Crypto", "industry": "Layer 1", "market_cap": "Large"},
    "ETH-USD": {"sector": "Crypto", "industry": "Layer 1", "market_cap": "Large"},
    "BNB-USD": {"sector": "Crypto", "industry": "Exchange", "market_cap": "Large"},
    "SOL-USD": {"sector": "Crypto", "industry": "Layer 1", "market_cap": "Large"},
    "XRP-USD": {"sector": "Crypto", "industry": "Payments", "market_cap": "Large"},
    "ADA-USD": {"sector": "Crypto", "industry": "Layer 1", "market_cap": "Large"},
}


def get_nifty50_constituents() -> list[str]:
    """Return NIFTY 50 constituent tickers in Yahoo Finance format."""
    return NIFTY50_CONSTITUENTS.copy()


def get_nifty100_constituents() -> list[str]:
    """Return NIFTY 100 constituent tickers."""
    return list(dict.fromkeys(NIFTY50_CONSTITUENTS + NIFTY100_ADDITIONS))


def get_nifty500_constituents() -> list[str]:
    """Return NIFTY 500 constituent tickers (approximated as NIFTY 100 + extended)."""
    return get_nifty100_constituents()


def get_sp500_constituents() -> list[str]:
    """Return S&P 500 representative tickers."""
    return SP500_CONSTITUENTS.copy()


def get_nasdaq100_constituents() -> list[str]:
    """Return NASDAQ 100 representative tickers."""
    return NASDAQ100_CONSTITUENTS.copy()


def get_crypto_constituents() -> list[str]:
    """Return major cryptocurrency tickers."""
    return CRYPTO_CONSTITUENTS.copy()


def get_fx_constituents() -> list[str]:
    """Return major FX pair tickers."""
    return FX_CONSTITUENTS.copy()


def get_commodity_constituents() -> list[str]:
    """Return major commodity futures tickers."""
    return COMMODITY_CONSTITUENTS.copy()


def get_universe_tickers(universe: str) -> list[str]:
    """Get ticker list for a named universe or return as-is if already a list.

    Parameters
    ----------
    universe : str
        Universe name: "NIFTY50", "NIFTY100", "NIFTY500", "SP500", "NASDAQ100",
        "CRYPTO", "FX", "COMMODITIES", or comma-separated tickers.

    Returns
    -------
    list[str]
        List of ticker strings.
    """
    universe_map = {
        "NIFTY50": get_nifty50_constituents(),
        "NIFTY100": get_nifty100_constituents(),
        "NIFTY500": get_nifty500_constituents(),
        "SP500": get_sp500_constituents(),
        "S&P500": get_sp500_constituents(),
        "S&P 500": get_sp500_constituents(),
        "NASDAQ100": get_nasdaq100_constituents(),
        "NASDAQ 100": get_nasdaq100_constituents(),
        "CRYPTO": get_crypto_constituents(),
        "FX": get_fx_constituents(),
        "FOREX": get_fx_constituents(),
        "COMMODITIES": get_commodity_constituents(),
        "COMMODITY": get_commodity_constituents(),
    }

    if universe in universe_map:
        return universe_map[universe]

    # Try comma-separated tickers
    if "." in universe or "," in universe:
        return [t.strip() for t in universe.split(",") if t.strip()]

    raise ValueError(
        f"Unknown universe: {universe}. "
        f"Use 'NIFTY50', 'SP500', 'NASDAQ100', 'CRYPTO', 'FX', "
        f"'COMMODITIES', or comma-separated tickers."
    )


def get_sector_classification(ticker: str) -> dict:
    """Get sector, industry, and market cap classification for a ticker.

    Searches across all supported universes (NIFTY 50, S&P 500, Crypto, FX, Commodities).

    Returns a dict with keys: sector, industry, market_cap.
    Falls back to 'Unknown' for unmapped tickers.
    """
    for mapping in (SECTOR_MAP, SP500_SECTOR_MAP, CRYPTO_SECTOR_MAP):
        if ticker in mapping:
            return mapping[ticker]
    return {
        "sector": "Unknown",
        "industry": "Unknown",
        "market_cap": "Unknown",
    }


def get_benchmark_ticker(market: str = "US") -> str:
    """Return the benchmark index ticker for the specified market.

    Parameters
    ----------
    market : str
        Market code: "US" (default), "IN" (India), "UK" (United Kingdom).

    Returns
    -------
    str
        Yahoo Finance benchmark ticker symbol.
    """
    market = market.upper()
    if market in ("IN", "INDIA", "NSE"):
        return "^NSEI"  # NIFTY 50
    if market in ("UK", "LSE", "LONDON"):
        return "^FTSE"  # FTSE 100
    return "^GSPC"  # S&P 500 (default)


def get_company_name(ticker: str) -> str:
    """Return the company / asset name for a given ticker across all universes."""
    all_tickers = {
        **{t: t for t in NIFTY50_CONSTITUENTS},
        **{t: t for t in SP500_CONSTITUENTS},
        **{t: t for t in NASDAQ100_CONSTITUENTS},
        **{t: t for t in CRYPTO_CONSTITUENTS},
        **{t: t for t in FX_CONSTITUENTS},
        **{t: t for t in COMMODITY_CONSTITUENTS},
    }
    return all_tickers.get(ticker, ticker)
```

### Main Scanner Class

```python
# alpha_search/opportunities/scanner.py
from datetime import datetime
from typing import Optional, Union, Literal

from alpha_search.opportunities.models import StockOpportunity, PairOpportunity
from alpha_search.opportunities.strategies import (
    momentum_scan,
    mean_reversion_scan,
    arbitrage_scan,
)
from alpha_search.opportunities.market_universes import get_universe_tickers


class StockOpportunityScanner:
    """Main scanner orchestrator for Alpha Search global multi-asset opportunity discovery.

    Combines all three strategy scanners (momentum, mean reversion,
    statistical arbitrage), applies composite scoring, filters by
    minimum thresholds, and returns ranked opportunity lists ready
    for the frontend opportunity board.

    Supports multiple market universes: NIFTY 50, S&P 500, NASDAQ 100,
    DOW 30, FTSE 100, Crypto, FX, and Commodities.
    """

    def __init__(
        self,
        data_provider,
        sentiment_provider=None,
        min_liquidity: float = 0.3,
        min_confidence: float = 0.5,
    ):
        self.data_provider = data_provider
        self.sentiment_provider = sentiment_provider
        self.min_liquidity = min_liquidity
        self.min_confidence = min_confidence

    def scan(
        self,
        universe: str = "SP500",
        strategy: Literal["momentum", "mean_reversion", "arbitrage", "all"] = "all",
        top_n: int = 10,
        lookback_days: int = 60,
    ) -> dict[str, list[Union[StockOpportunity, PairOpportunity]]]:
        """Run strategy scan(s) and return ranked, filtered opportunities.

        Parameters
        ----------
        universe : str
            Market universe: "NIFTY50", "SP500", "NASDAQ100", "CRYPTO",
            "FX", "COMMODITIES", or comma-separated tickers.
        strategy : str
            Which strategy to run ("all" runs all three).
        top_n : int
            Maximum number of opportunities to return per strategy.
        lookback_days : int
            Historical data window.

        Returns
        -------
        dict[str, list]
            Dict mapping strategy name to list of ranked opportunities:
            {"momentum": [...], "mean_reversion": [...], "arbitrage": [...]}
        """
        results: dict[str, list] = {}
        strategies_to_run = []

        if strategy in ("momentum", "all"):
            strategies_to_run.append("momentum")
        if strategy in ("mean_reversion", "all"):
            strategies_to_run.append("mean_reversion")
        if strategy in ("arbitrage", "all"):
            strategies_to_run.append("arbitrage")

        # Momentum scan
        if "momentum" in strategies_to_run:
            momentum_opps = momentum_scan(
                data_provider=self.data_provider,
                universe=universe,
                sentiment_provider=self.sentiment_provider,
                lookback_days=lookback_days,
            )
            results["momentum"] = self._filter_and_rank(momentum_opps, top_n)

        # Mean reversion scan
        if "mean_reversion" in strategies_to_run:
            reversion_opps = mean_reversion_scan(
                data_provider=self.data_provider,
                universe=universe,
                sentiment_provider=self.sentiment_provider,
                lookback_days=lookback_days,
            )
            results["mean_reversion"] = self._filter_and_rank(reversion_opps, top_n)

        # Arbitrage scan (uses longer lookback)
        if "arbitrage" in strategies_to_run:
            pair_opps = arbitrage_scan(
                data_provider=self.data_provider,
                universe=universe,
                lookback_days=max(lookback_days, 120),
            )
            results["arbitrage"] = self._filter_and_rank(pair_opps, top_n)

        return results

    def _filter_and_rank(
        self,
        opportunities: list,
        top_n: int,
    ) -> list:
        """Apply minimum threshold filters and return top N."""
        filtered = [
            opp for opp in opportunities
            if opp.liquidity_score >= self.min_liquidity
            and opp.confidence_score >= self.min_confidence
        ]
        return filtered[:top_n]

    def scan_single_strategy(
        self,
        strategy: Literal["momentum", "mean_reversion", "arbitrage"],
        universe: str = "SP500",
        top_n: int = 10,
        lookback_days: int = 60,
    ) -> list[Union[StockOpportunity, PairOpportunity]]:
        """Run a single strategy scan and return ranked results.

        Convenience method when only one strategy type is needed.
        """
        results = self.scan(
            universe=universe,
            strategy=strategy,
            top_n=top_n,
            lookback_days=lookback_days,
        )
        return results.get(strategy, [])
```

### Module Init

```python
# alpha_search/opportunities/__init__.py
from alpha_search.opportunities.models import StockOpportunity, PairOpportunity
from alpha_search.opportunities.scanner import StockOpportunityScanner
from alpha_search.opportunities.scoring import calculate_final_score, score_to_grade
from alpha_search.opportunities.market_universes import (
    get_universe_tickers,
    get_nifty50_tickers,
    get_sp500_tickers,
    get_nasdaq100_tickers,
    get_crypto_tickers,
    get_company_name,
    get_sector,
)

__all__ = [
    "StockOpportunity",
    "PairOpportunity",
    "StockOpportunityScanner",
    "calculate_final_score",
    "score_to_grade",
    "get_universe_tickers",
    "get_nifty50_tickers",
    "get_sp500_tickers",
    "get_nasdaq100_tickers",
    "get_crypto_tickers",
    "get_company_name",
    "get_sector",
]
```

## Responsibilities

1. Load global multi-asset market universes (NIFTY 50, S&P 500, NASDAQ 100, CRYPTO, FX, COMMODITIES) with accurate constituent lists
2. Fetch price data for all universe constituents via the DataProvider interface
3. Run all three strategy scans — momentum, mean reversion, and statistical arbitrage
4. Calculate composite scores for each opportunity using the weighted scoring formula
5. Apply the weighted scoring formula consistently across all opportunity types
6. Filter opportunities by minimum thresholds (liquidity > 0.3, confidence > 0.5)
7. Rank opportunities by final score and return top N per strategy
8. Generate human-readable thesis and risk summaries for each opportunity
9. Integrate sentiment scores from the FinBERT pipeline via CompositeSentiment
10. Compute technical indicators (RSI, MACD, ADX, Bollinger Bands, z-scores)
11. Calculate pair statistics: correlation, cointegration, spread z-score, hedge ratio, half-life
12. Expose all data in Pydantic models for direct frontend consumption
13. Handle edge cases: insufficient data, NaN values, single-observation windows
14. Run entirely on mocked data in test environments (no external API calls in CI)

## Inputs

- `universe`: str — "NIFTY50", "SP500", "NASDAQ100", "DOW30", "FTSE100", "CRYPTO", "FX", "COMMODITIES", or comma-separated tickers
- `strategy`: str — "momentum", "mean_reversion", "arbitrage", or "all"
- `top_n`: int — number of opportunities to return per strategy (default 10)
- `min_liquidity`: float — minimum liquidity score threshold (default 0.3)
- `min_confidence`: float — minimum confidence score threshold (default 0.5)
- `lookback_days`: int — historical data window in days (default 60, 120 for arbitrage)
- `data_provider`: DataProvider instance — for fetching OHLCV data
- `sentiment_provider`: Optional — CompositeSentiment instance for sentiment scores

## Outputs

- `List[StockOpportunity]` for single-stock strategies (momentum, mean reversion)
- `List[PairOpportunity]` for statistical arbitrage strategy
- Each StockOpportunity includes: thesis, risk_summary, confidence_score, all 6 sub-scores, key_levels, sector, beta, market cap
- Each PairOpportunity includes: thesis, risk_summary, confidence_score, all 6 sub-scores, correlation, cointegration_pvalue, spread_zscore, hedge_ratio, half_life, entry/exit thresholds
- All outputs are Pydantic models serializable to JSON for frontend consumption
- Dict[str, list] from `StockOpportunityScanner.scan()` mapping strategy -> opportunities

## Required Files to Create or Modify

- `alpha_search/opportunities/__init__.py` — module exports (create)
- `alpha_search/opportunities/models.py` — StockOpportunity and PairOpportunity Pydantic models (create)
- `alpha_search/opportunities/scanner.py` — StockOpportunityScanner orchestrator class (create)
- `alpha_search/opportunities/scoring.py` — calculate_final_score, normalize_to_unit, score_to_grade (create)
- `alpha_search/opportunities/strategies.py` — momentum_scan, mean_reversion_scan, arbitrage_scan (create)
- `alpha_search/opportunities/market_universes.py` — universe tickers, sector mapping, benchmark for all markets (create)
- `tests/opportunities/test_strategies.py` — comprehensive strategy tests (create)
- `tests/opportunities/test_scoring.py` — scoring formula tests (create)
- `tests/opportunities/test_scanner.py` — scanner orchestrator tests (create)
- `tests/opportunities/test_market_universes.py` — market utility tests (create)

## Implementation Checklist

- [ ] Create Pydantic models (StockOpportunity, PairOpportunity) with all required fields and validators
- [ ] Implement momentum_scan() function with RSI, MACD, ADX, volume confirmation
- [ ] Implement mean_reversion_scan() function with z-score, Bollinger Band, RSI thresholds
- [ ] Implement arbitrage_scan() function with correlation, cointegration, spread z-score, hedge ratio
- [ ] Implement calculate_final_score() with the weighted 6-factor formula
- [ ] Create StockOpportunityScanner class with scan() and scan_single_strategy() methods
- [ ] Add NIFTY 50 constituent mapping (50 tickers in Yahoo Finance format)
- [ ] Add S&P 500 constituent mapping (30 representative tickers)
- [ ] Add NASDAQ 100 constituent mapping (20 representative tickers)
- [ ] Add CRYPTO constituent mapping (BTC, ETH, BNB, SOL, XRP, ADA)
- [ ] Add FX constituent mapping (10 major currency pairs)
- [ ] Add COMMODITIES constituent mapping (12 major futures)
- [ ] Add sector classification mapping for all supported universes
- [ ] Add unified get_universe_tickers() with support for all universe names
- [ ] Add get_benchmark_ticker() with market parameter (US/IN/UK)
- [ ] Integrate with YFinanceProvider for OHLCV data
- [ ] Integrate with CompositeSentiment for sentiment scores (with 0.5 default when unavailable)
- [ ] Add minimum threshold filters (liquidity >= 0.3, confidence >= 0.5)
- [ ] Add ranking and top-N selection per strategy
- [ ] Generate human-readable thesis and risk_summary for every opportunity
- [ ] Compute technical indicators: RSI, MACD, MACD histogram, ADX, Bollinger Bands, z-score
- [ ] Compute pair statistics: correlation, cointegration p-value, spread z-score, OLS hedge ratio, half-life
- [ ] Write comprehensive tests with fully mocked data (no external API calls)

## Testing Checklist

- [ ] Test momentum_scan with known trending instrument — returns StockOpportunity list with final_score in [0, 1]
- [ ] Test mean_reversion_scan with known overbought instrument — detects z-score > 2.0 condition
- [ ] Test arbitrage_scan finds cointegrated pairs with correlation > 0.7 and p-value < 0.05
- [ ] Test scoring formula produces scores in [0, 1] for all input combinations (100 random trials)
- [ ] Test filtering by min_liquidity and min_confidence — filtered results meet thresholds
- [ ] Test ranking order — results sorted by final_score descending
- [ ] Test with mocked yfinance provider — no external API calls
- [ ] Test Pydantic model validation — invalid scores rejected, valid scores accepted
- [ ] Test scanner orchestrator — scan_all returns all three strategy keys
- [ ] Test market universe utilities — NIFTY 50 has exactly 50 constituents, all end in .NS
- [ ] Test S&P 500 universe loads correctly with plain tickers
- [ ] Test CRYPTO universe loads correctly with -USD suffix
- [ ] Test FX universe loads correctly with =X suffix
- [ ] Test get_benchmark_ticker returns correct benchmark for US, IN, UK markets
- [ ] Test sector classification — known tickers return correct sectors across all universes
- [ ] Test edge cases — empty data, single row, NaN values handled gracefully
- [ ] Test score_to_grade — all grade boundaries produce correct letter grades

## Definition of Done

- All three strategy scanners (momentum, mean reversion, arbitrage) return scored opportunities
- Scoring formula produces consistent rankings with all sub-scores in [0, 1]
- Every opportunity includes a human-readable thesis and risk summary
- Frontend can consume the output directly (Pydantic models -> JSON)
- All tests pass with mocked data (zero external API calls in CI)
- NIFTY 50 universe loads 50 constituents with correct Yahoo Finance ticker format
- S&P 500 universe loads 30 representative constituents with plain ticker format
- CRYPTO universe loads 6 major tokens with -USD suffix
- FX universe loads 10 major currency pairs with =X suffix
- Filtering by min_liquidity and min_confidence works correctly
- Top-N selection limits results as specified
- Sentiment integration uses 0.5 (neutral) as default when sentiment provider is unavailable
- Technical indicator computation is numerically stable (no NaN propagation)
- Pair opportunity includes all statistics: correlation, cointegration, spread z-score, hedge ratio, half-life
- Module is fully importable with `from alpha_search.opportunities import StockOpportunityScanner`
- get_benchmark_ticker correctly returns ^GSPC for US, ^NSEI for India, ^FTSE for UK

## Example Prompt

> You are the Alpha Search Global Market Opportunity Discovery agent. Find the top 10 momentum opportunities in S&P 500 with minimum confidence 0.6. Use the YFinanceProvider for price data and the CompositeSentiment pipeline for sentiment scores. For each opportunity, compute RSI, MACD, ADX, and volume confirmation indicators. Generate a clear thesis and risk summary. Apply the full 6-factor scoring formula and return ranked StockOpportunity models. Ensure all scores are in [0, 1] and the output is JSON-serializable for the frontend opportunity board.

## Safety Notes

- This module is research and educational tooling only. It does not issue real-money trading recommendations.
- Past performance does not guarantee future results. All signals are probabilistic, not deterministic.
- Opportunity scores reflect statistical patterns, not guaranteed outcomes.
- Statistical arbitrage assumes cointegration persists — regime changes can break this assumption.
- Mean reversion trades carry the risk of trend continuation (the "catching a falling knife" problem).
- Momentum trades can reverse sharply on sentiment shifts or market regime changes.
- Crypto markets are highly volatile and can experience extreme price swings.
- FX markets are subject to central bank policy changes and geopolitical events.
- Commodity markets are subject to supply/demand shocks and geopolitical disruptions.
- Always perform independent due diligence before any investment decision.
- The scoring formula weights can be adjusted for different risk appetites, but the defaults are designed for balanced opportunity discovery.
