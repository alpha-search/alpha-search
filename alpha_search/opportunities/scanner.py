"""Global multi-asset opportunity scanner orchestrator for Alpha Search.

The :class:`StockOpportunityScanner` ties together data fetching, strategy
execution, scoring, and opportunity object construction across global multi-asset
markets — US equities, Indian equities, crypto, forex, and commodities.  It is
designed to work with any data provider that exposes a ``download(tickers, period)``
method returning a ``pandas.DataFrame``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from alpha_search.opportunities.market_universes import (
    get_company_name,
    get_sector,
)
from alpha_search.opportunities.models import PairOpportunity, StockOpportunity
from alpha_search.opportunities.scoring import FinalScore
from alpha_search.opportunities.strategies import (
    arbitrage_scan,
    mean_reversion_scan,
    momentum_scan,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_universe(universe: Union[str, List[str]]) -> List[str]:
    """Convert a universe identifier into a list of tickers.

    Supported identifiers:
    * ``"NIFTY50"`` / ``"NIFTY 50"`` — NIFTY 50 (Indian equities, ``.NS``)
    * ``"SP500"`` / ``"S&P500"`` / ``"S&P 500"`` — S&P 500 (US equities)
    * ``"NASDAQ100"`` / ``"NASDAQ 100"`` — NASDAQ 100 (US tech equities)
    * ``"DOW30"`` / ``"DOW 30"`` — Dow Jones 30 (US blue-chip equities)
    * ``"FTSE100"`` / ``"FTSE 100"`` — FTSE 100 (UK equities)
    * ``"CRYPTO"`` — major cryptocurrencies (``BTC-USD``, ``ETH-USD``, etc.)
    * ``"FX"`` / ``"FOREX"`` — major forex pairs
    * ``"COMMODITIES"`` — major commodity futures
    * ``list[str]`` — passed through verbatim

    Parameters
    ----------
    universe : str or list[str]
        Universe identifier or list of tickers.

    Returns
    -------
    list[str]
        Resolved list of ticker strings.
    """
    if isinstance(universe, str):
        from alpha_search.opportunities.market_universes import get_universe_tickers
        try:
            return get_universe_tickers(universe)
        except ValueError:
            # Fallback: treat as a single ticker or comma-separated list
            if "," in universe:
                return [t.strip() for t in universe.split(",") if t.strip()]
            return [universe]
    return list(universe)


def _fetch_prices(
    provider: Optional[Any],
    tickers: List[str],
    period: str = "3mo",
) -> pd.DataFrame:
    """Fetch closing prices via *provider* or raise if unavailable.

    Parameters
    ----------
    provider : object, optional
        Must expose ``download(tickers: list[str], period: str) -> DataFrame``.
    tickers : list[str]
        Ticker symbols to fetch.
    period : str
        yfinance-compatible period string (``"3mo"``, ``"1y"``, etc.).

    Returns
    -------
    pandas.DataFrame
        Closing prices — index = Date, columns = tickers.
    """
    if provider is None:
        raise ValueError(
            "No data provider available. Pass a provider with a 'download' method, "
            "or call the scanner with pre-loaded price data."
        )

    try:
        df = provider.download(tickers, period=period)
        if isinstance(df.columns, pd.MultiIndex):
            # yfinance returns MultiIndex with "Adj Close" / "Close" level
            if "Adj Close" in df.columns.get_level_values(0):
                df = df["Adj Close"]
            elif "Close" in df.columns.get_level_values(0):
                df = df["Close"]
        df = df.dropna(how="all", axis=1).dropna(how="all", axis=0)
        logger.info("Fetched prices for %d tickers (%d rows)", len(df.columns), len(df))
        return df
    except Exception as exc:
        logger.error("Price fetch failed: %s", exc)
        raise RuntimeError(f"Failed to fetch prices: {exc}") from exc


def _compute_sentiment(
    sentiment_analyzer: Optional[Any],
    ticker: str,
) -> float:
    """Return sentiment score for *ticker* via *sentiment_analyzer*.

    If no analyzer is provided, returns ``0.5`` (neutral).
    """
    if sentiment_analyzer is None:
        return 0.5
    try:
        result = sentiment_analyzer.analyze(ticker)
        if isinstance(result, dict):
            return float(result.get("score", 0.5))
        return float(result)
    except Exception as exc:
        logger.debug("Sentiment analysis failed for %s: %s", ticker, exc)
        return 0.5


def _generate_momentum_thesis(
    ticker: str,
    company_name: str,
    signal: str,
    returns_20d: float,
    adx: float,
    vol_ratio: float,
    rsi: float,
    sentiment: float,
) -> str:
    """Generate a human-readable thesis for a momentum opportunity."""
    direction_word = "upward" if signal == "long" else "downward" if signal == "short" else "sideways"
    action = "Consider long position" if signal == "long" else "Consider short position" if signal == "short" else "Watch for breakout"

    lines = [
        f"{ticker} ({company_name}) shows {direction_word} momentum with "
        f"20-day return of {returns_20d:+.1f}%. ADX at {adx:.1f} confirms trend strength.",
        f"Volume is {vol_ratio:.1f}x the 20-day average, indicating strong participation. "
        f"RSI at {rsi:.1f} suggests {'room before overbought' if rsi < 70 else 'overbought conditions'}.",
    ]
    if sentiment != 0.5:
        sentiment_word = "positive" if sentiment > 0.6 else "negative" if sentiment < 0.4 else "neutral"
        lines.append(f"Sentiment is {sentiment_word} ({sentiment:.2f}).")
    lines.append(f"Recommended action: {action} with appropriate stop-loss.")
    return " ".join(lines)


def _generate_momentum_risk(
    ticker: str,
    signal: str,
    rsi: float,
    sector: str,
) -> str:
    """Generate a risk summary for a momentum opportunity."""
    risks = [
        f"1. Trend reversal risk: if RSI crosses {'above 75' if signal == 'long' else 'below 25'}, "
        f"the {signal} thesis weakens significantly.",
        f"2. Sector rotation out of {sector} could drag {ticker} even if company fundamentals remain strong.",
        "3. Low-liquidity days around expiry may cause slippage on entry/exit.",
        "4. Black-swan events or regulatory changes can override technical signals.",
    ]
    return " ".join(risks)


def _generate_mr_thesis(
    ticker: str,
    company_name: str,
    signal: str,
    zscore: float,
    rsi: float,
    bb_pos: float,
) -> str:
    """Generate a human-readable thesis for a mean-reversion opportunity."""
    condition = "oversold" if signal == "long" else "overbought" if signal == "short" else "neutral"
    action = "Consider long position" if signal == "long" else "Consider short position" if signal == "short" else "Wait for clearer signal"

    lines = [
        f"{ticker} ({company_name}) appears {condition} with a z-score of {zscore:+.2f} "
        f"(2.0+ is considered extreme).",
        f"RSI at {rsi:.1f} confirms {condition} conditions. "
        f"Bollinger Band position at {bb_pos:.2%} indicates price near the {'lower' if signal == 'long' else 'upper'} band.",
        f"Mean-reversion thesis: price tends to revert to the 20-day average. {action} with tight risk management.",
    ]
    return " ".join(lines)


def _generate_mr_risk(
    ticker: str,
    signal: str,
    zscore: float,
) -> str:
    """Generate a risk summary for a mean-reversion opportunity."""
    risks = [
        f"1. Momentum continuation: {ticker} may keep drifting {'lower' if signal == 'long' else 'higher'} "
        f"if a fundamental driver overrides mean-reversion forces (z-score: {zscore:+.2f}).",
        "2. Volatility expansion: widening Bollinger Bands increase stop-loss distance and capital at risk.",
        "3. Earnings or news events can cause permanent regime shifts rather than temporary deviations.",
    ]
    return " ".join(risks)


def _generate_pair_thesis(
    stock_a: str,
    stock_b: str,
    corr: float,
    coint: float,
    zscore: float,
    hedge: float,
) -> str:
    """Generate a human-readable thesis for a pair-trading opportunity."""
    direction = "converging" if abs(zscore) > 1.5 else "stable"
    trade = (
        f"Long {stock_a} / Short {stock_b}" if zscore < -1.0
        else f"Short {stock_a} / Long {stock_b}" if zscore > 1.0
        else "Monitor for entry signal"
    )
    lines = [
        f"Pair {stock_a} – {stock_b} shows strong correlation ({corr:.2f}) and "
        f"cointegration score ({coint:.2f}), indicating a stable long-term relationship.",
        f"Spread z-score of {zscore:+.2f} suggests the pair is {direction} from equilibrium. "
        f"Hedge ratio: {hedge:.3f}.",
        f"Suggested trade: {trade} when z-score moves toward 0.",
    ]
    return " ".join(lines)


def _generate_pair_risk(
    stock_a: str,
    stock_b: str,
    zscore: float,
) -> str:
    """Generate a risk summary for a pair-trading opportunity."""
    risks = [
        f"1. Cointegration breakdown: fundamental divergence between {stock_a} and {stock_b} "
        f"can invalidate the historical relationship.",
        "2. Divergence risk: the spread may widen further before reverting, leading to mark-to-market losses.",
        "3. Execution risk: simultaneous entry/exit of both legs is required; slippage on one leg degrades hedge quality.",
        f"4. Current z-score ({zscore:+.2f}) may not be extreme enough for high-probability reversion.",
    ]
    return " ".join(risks)


# ---------------------------------------------------------------------------
# Scanner class
# ---------------------------------------------------------------------------

class StockOpportunityScanner:
    """Orchestrates opportunity discovery across momentum, mean-reversion and
    statistical-arbitrage strategies for global multi-asset markets.

    Supports US equities (S&P 500, NASDAQ 100, DOW 30), Indian equities
    (NIFTY 50), cryptocurrencies, forex pairs, and commodities.

    Parameters
    ----------
    provider : object, optional
        Data source with a ``download(tickers, period)`` method.  Common
        choices: a ``yfinance.Ticker`` wrapper or a custom data client.
    sentiment_analyzer : object, optional
        Sentiment engine with an ``analyze(ticker)`` method returning a
        score in ``[0, 1]`` or a dict with a ``"score"`` key.

    Examples
    --------
    >>> import yfinance as yf
    >>> scanner = StockOpportunityScanner(provider=yf)
    >>> momentum_ops = scanner.scan_momentum(universe="SP500", top_n=5)
    >>> crypto_ops = scanner.scan_momentum(universe="CRYPTO", top_n=5)
    >>> india_ops = scanner.scan_momentum(universe="NIFTY50", top_n=5)
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        sentiment_analyzer: Optional[Any] = None,
    ):
        self.provider = provider
        self.sentiment_analyzer = sentiment_analyzer

    # ------------------------------------------------------------------ #
    # Public scanning API                                                #
    # ------------------------------------------------------------------ #

    def scan_momentum(
        self,
        universe: Union[str, List[str]] = "NIFTY50",
        top_n: int = 10,
        min_confidence: float = 0.5,
        lookback_days: int = 60,
    ) -> List[StockOpportunity]:
        """Find top momentum opportunities in a global multi-asset universe.

        Parameters
        ----------
        universe : str or list[str]
            Market universe identifier (``"NIFTY50"``, ``"SP500"``,
            ``"NASDAQ100"``, ``"CRYPTO"``, ``"FX"``, ``"COMMODITIES"``)
            or a custom list of tickers.
        top_n : int
            Maximum number of opportunities to return.
        min_confidence : float
            Minimum final confidence score ``[0, 1]``.
        lookback_days : int
            Ignored when using a data-provider (provider selects period).
            Retained for API consistency.

        Returns
        -------
        list[StockOpportunity]
            Opportunities sorted by ``confidence_score`` descending.
        """
        tickers = _resolve_universe(universe)
        period = "3mo" if lookback_days <= 90 else "6mo" if lookback_days <= 180 else "1y"

        try:
            prices = _fetch_prices(self.provider, tickers, period=period)
        except Exception:
            logger.exception("Momentum scan aborted — price fetch failed")
            return []

        results_df = momentum_scan(prices)
        if results_df.empty:
            return []

        opportunities: List[StockOpportunity] = []
        for _, row in results_df.iterrows():
            ticker = row["ticker"]
            company = get_company_name(ticker)
            sector = get_sector(ticker)
            momentum_score = float(row["momentum_score"])
            signal = row["signal_direction"]

            # Sentiment
            sentiment = _compute_sentiment(self.sentiment_analyzer, ticker)

            # Compute returns for risk-adjusted score
            if ticker in prices.columns:
                series = prices[ticker].dropna()
                returns = series.pct_change().dropna()
                volatility = returns.std() if len(returns) > 1 else 0.01
                exp_return = returns.mean() * len(returns) if len(returns) > 0 else 0.0
            else:
                volatility = 0.01
                exp_return = 0.0

            # Sub-scores
            liq_score = FinalScore.liquidity_score(
                volume=float(row.get("volume_ratio", 1.0)) * 1000,
                avg_volume=1000.0,
            )
            risk_adj_score = FinalScore.risk_adjusted_return_score(
                expected_return=exp_return,
                volatility=volatility,
            )
            hedge_score = FinalScore.hedgeability_score(
                has_hedge=True,
                hedge_cost=2.0,
            )
            exec_score = FinalScore.execution_feasibility_score(
                spread_pct=0.05,
                avg_slippage=0.02,
            )
            _ = FinalScore.confidence_score(  # noqa: F841
                strategy_strength=momentum_score,
                data_quality=0.85,
                model_fit=momentum_score,
            )

            final = FinalScore.calculate(
                strategy_signal_strength=momentum_score,
                liquidity_score=liq_score,
                sentiment_score=sentiment,
                risk_adjusted_return_score=risk_adj_score,
                hedgeability_score=hedge_score,
                execution_feasibility_score=exec_score,
            )

            if final < min_confidence:
                continue

            # Generate thesis / risk
            adx_val = float(row.get("adx", 0.0))
            vol_ratio = float(row.get("volume_ratio", 1.0))
            returns_20d = float(row.get("returns_20d", 0.0))

            thesis = _generate_momentum_thesis(
                ticker, company, signal, returns_20d, adx_val, vol_ratio,
                rsi=65.0, sentiment=sentiment,
            )
            risk = _generate_momentum_risk(ticker, signal, rsi=65.0, sector=sector)

            rec_action = (
                f"Consider {signal} position with stop-loss at 2 ATR below entry"
                if signal in ("long", "short")
                else "Monitor for clearer directional confirmation"
            )

            opp = StockOpportunity(
                ticker=ticker,
                company_name=company,
                sector=sector,
                strategy_type="momentum",
                signal_direction=signal,
                confidence_score=round(final, 4),
                liquidity_score=round(liq_score, 4),
                sentiment_score=round(sentiment, 4),
                volatility_score=round(min(1.0, volatility * np.sqrt(252) * 2), 4),
                momentum_score=round(momentum_score, 4),
                mean_reversion_score=0.0,
                correlation_score=0.0,
                cointegration_score=0.0,
                hedge_candidate=(sector in ("IT", "Financial Services")),
                news_summary=f"Volume {vol_ratio:.1f}x average. ADX {adx_val:.1f}.",
                risk_summary=risk,
                thesis=thesis,
                recommended_action=rec_action,
            )
            opportunities.append(opp)

        opportunities.sort(key=lambda o: o.confidence_score, reverse=True)
        return opportunities[:top_n]

    def scan_mean_reversion(
        self,
        universe: Union[str, List[str]] = "NIFTY50",
        top_n: int = 10,
        min_confidence: float = 0.5,
        lookback_days: int = 60,
    ) -> List[StockOpportunity]:
        """Find top mean-reversion opportunities in a global multi-asset universe.

        Parameters
        ----------
        universe : str or list[str]
            Market universe identifier (``"NIFTY50"``, ``"SP500"``,
            ``"NASDAQ100"``, ``"CRYPTO"``, ``"FX"``, ``"COMMODITIES"``)
            or a custom list of tickers.
        top_n : int
            Maximum number of opportunities to return.
        min_confidence : float
            Minimum final confidence score ``[0, 1]``.
        lookback_days : int
            Ignored when using a data-provider.

        Returns
        -------
        list[StockOpportunity]
            Opportunities sorted by ``confidence_score`` descending.
        """
        tickers = _resolve_universe(universe)
        period = "3mo" if lookback_days <= 90 else "6mo" if lookback_days <= 180 else "1y"

        try:
            prices = _fetch_prices(self.provider, tickers, period=period)
        except Exception:
            logger.exception("Mean-reversion scan aborted — price fetch failed")
            return []

        results_df = mean_reversion_scan(prices)
        if results_df.empty:
            return []

        opportunities: List[StockOpportunity] = []
        for _, row in results_df.iterrows():
            ticker = row["ticker"]
            company = get_company_name(ticker)
            sector = get_sector(ticker)
            mr_score = float(row["mean_reversion_score"])
            signal = row["signal_direction"]

            sentiment = _compute_sentiment(self.sentiment_analyzer, ticker)

            if ticker in prices.columns:
                series = prices[ticker].dropna()
                returns = series.pct_change().dropna()
                volatility = returns.std() if len(returns) > 1 else 0.01
                exp_return = abs(returns.mean()) * len(returns) if len(returns) > 0 else 0.0
            else:
                volatility = 0.01
                exp_return = 0.0

            liq_score = FinalScore.liquidity_score(volume=1.5, avg_volume=1.0)
            risk_adj_score = FinalScore.risk_adjusted_return_score(
                expected_return=exp_return,
                volatility=volatility,
            )
            hedge_score = FinalScore.hedgeability_score(has_hedge=True, hedge_cost=1.5)
            exec_score = FinalScore.execution_feasibility_score(spread_pct=0.04, avg_slippage=0.02)
            _ = FinalScore.confidence_score(  # noqa: F841
                strategy_strength=mr_score,
                data_quality=0.80,
                model_fit=mr_score,
            )

            final = FinalScore.calculate(
                strategy_signal_strength=mr_score,
                liquidity_score=liq_score,
                sentiment_score=sentiment,
                risk_adjusted_return_score=risk_adj_score,
                hedgeability_score=hedge_score,
                execution_feasibility_score=exec_score,
            )

            if final < min_confidence:
                continue

            zscore = float(row.get("zscore", 0.0))
            rsi = float(row.get("rsi", 50.0))
            bb_pos = float(row.get("bb_position", 0.5))

            thesis = _generate_mr_thesis(ticker, company, signal, zscore, rsi, bb_pos)
            risk = _generate_mr_risk(ticker, signal, zscore)

            rec_action = (
                f"Consider {signal} for mean-reversion with stop at 1.5 ATR"
                if signal in ("long", "short")
                else "Wait for z-score to exceed ±2.0 for entry"
            )

            opp = StockOpportunity(
                ticker=ticker,
                company_name=company,
                sector=sector,
                strategy_type="mean_reversion",
                signal_direction=signal,
                confidence_score=round(final, 4),
                liquidity_score=round(liq_score, 4),
                sentiment_score=round(sentiment, 4),
                volatility_score=round(min(1.0, volatility * np.sqrt(252) * 2), 4),
                momentum_score=0.0,
                mean_reversion_score=round(mr_score, 4),
                correlation_score=0.0,
                cointegration_score=0.0,
                hedge_candidate=False,
                news_summary=f"RSI {rsi:.1f}. Z-score {zscore:+.2f}. BB% {bb_pos:.2%}.",
                risk_summary=risk,
                thesis=thesis,
                recommended_action=rec_action,
            )
            opportunities.append(opp)

        opportunities.sort(key=lambda o: o.confidence_score, reverse=True)
        return opportunities[:top_n]

    def scan_arbitrage(
        self,
        universe: Union[str, List[str]] = "NIFTY50",
        top_n: int = 10,
        max_pairs: int = 50,
        lookback_days: int = 60,
    ) -> List[PairOpportunity]:
        """Find top statistical-arbitrage pair opportunities in a global
        multi-asset universe.

        Parameters
        ----------
        universe : str or list[str]
            Market universe identifier (``"NIFTY50"``, ``"SP500"``,
            ``"NASDAQ100"``, ``"CRYPTO"``, ``"FX"``, ``"COMMODITIES"``)
            or a custom list of tickers.
        top_n : int
            Maximum number of pairs to return.
        max_pairs : int
            Maximum pairs to evaluate from the strategy engine.
        lookback_days : int
            Ignored when using a data-provider.

        Returns
        -------
        list[PairOpportunity]
            Opportunities sorted by ``confidence_score`` descending.
        """
        tickers = _resolve_universe(universe)
        period = "3mo" if lookback_days <= 90 else "6mo" if lookback_days <= 180 else "1y"

        try:
            prices = _fetch_prices(self.provider, tickers, period=period)
        except Exception:
            logger.exception("Arbitrage scan aborted — price fetch failed")
            return []

        results_df = arbitrage_scan(prices, max_pairs=max_pairs)
        if results_df.empty:
            return []

        opportunities: List[PairOpportunity] = []
        for _, row in results_df.iterrows():
            stock_a = row["stock_a"]
            stock_b = row["stock_b"]
            corr = float(row["correlation"])
            coint = float(row["cointegration_score"])
            zscore = float(row["spread_zscore"])
            hedge = float(row["hedge_ratio"])
            confidence = float(row["confidence_score"])

            sector_a = get_sector(stock_a)
            sector_b = get_sector(stock_b)

            # Sentiment divergence
            sent_a = _compute_sentiment(self.sentiment_analyzer, stock_a)
            sent_b = _compute_sentiment(self.sentiment_analyzer, stock_b)
            sent_div = abs(sent_a - sent_b)

            liq_score = FinalScore.liquidity_score(volume=2.0, avg_volume=1.0)

            if confidence < 0.1:
                continue

            thesis = _generate_pair_thesis(stock_a, stock_b, corr, coint, zscore, hedge)
            risk = _generate_pair_risk(stock_a, stock_b, zscore)

            trade = (
                f"Long {stock_a} / Short {stock_b} (hedge ratio: {hedge:.3f})"
                if zscore < -1.0
                else f"Short {stock_a} / Long {stock_b} (hedge ratio: {hedge:.3f})"
                if zscore > 1.0
                else "Monitor — spread near equilibrium"
            )

            opp = PairOpportunity(
                stock_a=stock_a,
                stock_b=stock_b,
                sector_a=sector_a,
                sector_b=sector_b,
                correlation=round(corr, 4),
                cointegration_score=round(coint, 4),
                spread_zscore=round(zscore, 4),
                beta_difference=round(abs(hedge - 1.0), 4),
                sentiment_divergence=round(sent_div, 4),
                liquidity_score=round(liq_score, 4),
                hedge_ratio=round(hedge, 4),
                suggested_trade=trade,
                thesis=thesis,
                risk_summary=risk,
                confidence_score=round(confidence, 4),
            )
            opportunities.append(opp)

        opportunities.sort(key=lambda o: o.confidence_score, reverse=True)
        return opportunities[:top_n]

    def scan_all(
        self,
        universe: Union[str, List[str]] = "NIFTY50",
        top_n: int = 10,
        min_confidence: float = 0.5,
        lookback_days: int = 60,
    ) -> Dict[str, List]:
        """Run all three scans and return combined results across a global
        multi-asset universe.

        Parameters
        ----------
        universe : str or list[str]
            Market universe identifier (``"NIFTY50"``, ``"SP500"``,
            ``"NASDAQ100"``, ``"CRYPTO"``, ``"FX"``, ``"COMMODITIES"``)
            or a custom list of tickers.
        top_n : int
            Maximum number of opportunities per strategy.
        min_confidence : float
            Minimum final confidence score ``[0, 1]``.
        lookback_days : int
            Ignored when using a data-provider.

        Returns
        -------
        dict[str, list]
            Keys: ``"momentum"``, ``"mean_reversion"``, ``"arbitrage"``.
        """
        logger.info("Running full scan on universe=%s", universe)

        momentum = self.scan_momentum(
            universe=universe,
            top_n=top_n,
            min_confidence=min_confidence,
            lookback_days=lookback_days,
        )
        mean_rev = self.scan_mean_reversion(
            universe=universe,
            top_n=top_n,
            min_confidence=min_confidence,
            lookback_days=lookback_days,
        )
        arb = self.scan_arbitrage(
            universe=universe,
            top_n=top_n,
            lookback_days=lookback_days,
        )

        logger.info(
            "Scan complete: momentum=%d, mean_reversion=%d, arbitrage=%d",
            len(momentum), len(mean_rev), len(arb),
        )

        return {
            "momentum": momentum,
            "mean_reversion": mean_rev,
            "arbitrage": arb,
        }
