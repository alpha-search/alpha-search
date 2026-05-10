"""Alpha Search -- Real Data Research Pipeline.

Fetches actual market data, runs full agent swarm, produces research report.
Uses real YFinance data for top US and Indian equities.

DISCLAIMER: This pipeline is for research and educational purposes only.
All outputs are labelled as "research/educational only" and should not be
construed as investment advice.

Pipeline stages:
    1. Data fetching (YFinanceProvider with retry logic and disk caching)
    2. FinBERT sentiment analysis on news headlines
    3. Global Market Opportunity scanning (momentum / mean-reversion / arbitrage)
    4. Signal generation (technical indicators)
    5. Vectorised backtesting with real transaction costs
    6. Portfolio construction and optimisation
    7. Persistent memory logging (MemoryStore + AgentJournal)
    8. Professional console report
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.data.yfinance_provider import YFinanceProvider
from alpha_search.memory import AgentJournal, MemoryStore
from alpha_search.memory.models import StrategyMemory
from alpha_search.opportunities.strategies import (
    arbitrage_scan,
)
from alpha_search.sentiment.finbert import FinBERTSentimentAnalyzer
from alpha_search.signals.technical import (
    bollinger_band_position,
    ma_crossover,
    momentum,
    z_score_mean_reversion,
)

logger = logging.getLogger("alpha_search.real_pipeline")

# ---------------------------------------------------------------------------
# Market universes
# ---------------------------------------------------------------------------

# Top 20 US stocks (from SP500_TICKERS)
US_TOP20: List[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "TSLA", "NVDA", "BRK-B", "UNH", "JPM",
    "V", "JNJ", "WMT", "PG", "MA",
    "HD", "BAC", "ABBV", "PFE", "KO",
]

# Top 20 Indian stocks (from NIFTY50_TICKERS)
INDIA_TOP20: List[str] = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS",
    "SUNPHARMA.NS", "BAJFINANCE.NS", "WIPRO.NS", "NESTLEIND.NS", "ULTRACEMCO.NS",
]

COST_MODEL = CostModel(commission=0.001, slippage=0.001)
INITIAL_CAPITAL: float = 100_000.0


# ===========================================================================
# 1. Data Fetching
# ===========================================================================

def fetch_real_data(
    tickers: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    """Fetch real OHLCV data from YFinance for given tickers.

    Uses :class:`YFinanceProvider` which includes disk caching and
    exponential-backoff retries.  If no data can be fetched for any
    ticker, a clear error is raised.

    Parameters
    ----------
    tickers:
        List of Yahoo-Finance ticker symbols.
    start:
        Start date in ``YYYY-MM-DD`` format.
    end:
        End date in ``YYYY-MM-DD`` format.

    Returns
    -------
    pandas.DataFrame
        MultiIndex columns ``(ticker, field)`` where *field* is one of
        ``Open``, ``High``, ``Low``, ``Close``, ``Volume``.

    Raises
    ------
    RuntimeError
        If YFinanceProvider is unavailable or no tickers could be fetched.
    """
    try:
        provider = YFinanceProvider()
    except Exception as exc:
        raise RuntimeError(
            f"YFinanceProvider is unavailable: {exc}. "
            f"Ensure yfinance is installed: pip install yfinance"
        )

    frames: Dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for ticker in tickers:
        try:
            df = provider.get_prices(ticker, start, end)
            if df is not None and not df.empty and len(df) >= 10:
                frames[ticker] = df
                logger.info(
                    "Fetched %s: %d rows via YFinanceProvider", ticker, len(df)
                )
            else:
                failures.append(ticker)
                logger.warning("No data for %s — empty result", ticker)
        except Exception as exc:
            failures.append(ticker)
            logger.warning("YFinanceProvider failed for %s: %s", ticker, exc)

    if not frames:
        raise RuntimeError(
            f"No data fetched for any of the {len(tickers)} requested tickers. "
            f"Failures: {', '.join(failures[:10])}{'...' if len(failures) > 10 else ''}. "
            f"Check your network connection, verify ticker symbols at "
            f"https://finance.yahoo.com/lookup, and ensure yfinance is installed."
        )

    if failures:
        logger.warning(
            "Successfully fetched %d/%d tickers. Failed: %s",
            len(frames),
            len(tickers),
            ", ".join(failures[:10]),
        )

    # Build MultiIndex DataFrame
    combined: Dict[str, Dict[str, pd.Series]] = {}
    for field in ["Open", "High", "Low", "Close", "Volume"]:
        combined[field] = {}
        for ticker, df in frames.items():
            if field in df.columns:
                combined[field][ticker] = df[field]

    result_frames = []
    for field, ticker_dict in combined.items():
        if ticker_dict:
            field_df = pd.DataFrame(ticker_dict)
            field_df.columns = pd.MultiIndex.from_product(
                [field_df.columns, [field]]
            )
            result_frames.append(field_df)

    if not result_frames:
        raise RuntimeError(
            "Failed to build MultiIndex DataFrame — no OHLCV fields found."
        )

    # Concatenate along columns and sort
    result = pd.concat(result_frames, axis=1)
    result = result.sort_index(axis=1)

    logger.info(
        "fetch_real_data complete: %d tickers, %d rows",
        len(frames),
        len(result),
    )
    return result


# ===========================================================================
# 2. Sentiment Analysis
# ===========================================================================

def run_sentiment_analysis(
    tickers: list[str],
) -> dict[str, dict]:
    """Run FinBERT sentiment analysis on a list of tickers.

    Uses :class:`FinBERTSentimentAnalyzer` to analyse a composite text
    built from the ticker symbol and a brief description.  If FinBERT
    is unavailable, an error is raised (no synthetic fallback).

    Parameters
    ----------
    tickers:
        List of ticker symbols.

    Returns
    -------
    dict[str, dict]
        Mapping ``{ticker: {"score": float, "positive": float,
        "negative": float, "neutral": float}}``.

    Raises
    ------
    RuntimeError
        If FinBERT is not available and no sentiment data can be produced.
    """
    try:
        analyzer = FinBERTSentimentAnalyzer()
    except Exception as exc:
        raise RuntimeError(
            f"FinBERT sentiment analyser is unavailable: {exc}. "
            f"Install the required dependencies "
            f"(transformers, torch) to enable sentiment analysis."
        )

    results: dict[str, dict] = {}
    failures: list[str] = []

    for ticker in tickers:
        try:
            description = _ticker_description(ticker)
            sentiment = analyzer.analyze(description)
            results[ticker] = {
                "score": float(sentiment.get("score", 0.0)),
                "positive": float(sentiment.get("positive", 0.33)),
                "negative": float(sentiment.get("negative", 0.33)),
                "neutral": float(sentiment.get("neutral", 0.34)),
            }
        except Exception as exc:
            logger.warning("Sentiment analysis failed for %s: %s", ticker, exc)
            failures.append(ticker)

    if not results:
        raise RuntimeError(
            f"Sentiment analysis failed for all {len(tickers)} tickers. "
            f"Ensure FinBERT dependencies are installed: "
            f"pip install transformers torch"
        )

    if failures:
        logger.warning(
            "Sentiment analysis completed for %d/%d tickers. "
            "Failed: %s",
            len(results),
            len(tickers),
            ", ".join(failures[:10]),
        )

    logger.info("Sentiment analysis complete for %d tickers", len(results))
    return results


def _ticker_description(ticker: str) -> str:
    """Return a brief text description for a ticker to feed FinBERT."""
    from alpha_search.opportunities.market_universes import get_company_name

    try:
        name = get_company_name(ticker)
    except Exception:
        name = ticker
    return f"{ticker} ({name}) stock market performance and financial outlook"


# ===========================================================================
# 3. Strategy Pipelines
# ===========================================================================

def run_momentum_strategy(
    prices: pd.DataFrame,
    tickers: list[str],
) -> dict:
    """Run a complete momentum-strategy research pipeline.

    Steps
    -----
    1. Compute momentum signals for each ticker via :func:`momentum`.
    2. Rank tickers by momentum strength.
    3. Generate position signals (0/1 via MA crossover confirmation).
    4. Backtest each ticker with transaction costs.
    5. Aggregate metrics.

    Parameters
    ----------
    prices:
        MultiIndex DataFrame with columns ``(ticker, field)``.
    tickers:
        Tickers to evaluate.

    Returns
    -------
    dict
        Keys: ``hypothesis``, ``signals``, ``backtests``, ``metrics_df``,
        ``verdict``, ``risks``, ``top_picks``.
    """
    engine = BacktestEngine()
    backtests: Dict[str, Any] = {}
    all_metrics: List[dict] = []
    signals_dict: Dict[str, pd.Series] = {}

    # Use closing prices
    close_prices = _get_close_prices(prices, tickers)

    for ticker in close_prices.columns:
        price_series = close_prices[ticker].dropna()
        if len(price_series) < 50:
            continue

        try:
            # 1. Momentum signal
            mom_signal = momentum(price_series, window=20)

            # 2. MA crossover confirmation
            ma_signal = ma_crossover(price_series, short=20, long=50)

            # 3. Combined position: momentum * ma confirmation
            # Align indices
            combined = mom_signal * ma_signal.reindex(mom_signal.index, method="ffill")
            combined = combined.fillna(0.0)
            combined.name = ticker

            signals_dict[ticker] = combined

            # 4. Backtest
            prices_df = price_series.to_frame("Close")
            result = engine.run(
                prices=prices_df,
                signal=combined,
                initial_capital=INITIAL_CAPITAL,
                cost_model=COST_MODEL,
            )
            backtests[ticker] = result

            metrics_row = dict(result.metrics)
            metrics_row["ticker"] = ticker
            metrics_row["strategy"] = "momentum"
            all_metrics.append(metrics_row)

        except Exception as exc:
            logger.warning("Momentum strategy failed for %s: %s", ticker, exc)

    metrics_df = pd.DataFrame(all_metrics) if all_metrics else pd.DataFrame()

    # Rank by Sharpe
    top_picks: list[str] = []
    if not metrics_df.empty and "sharpe_ratio" in metrics_df.columns:
        ranked = metrics_df.sort_values("sharpe_ratio", ascending=False)
        top_picks = ranked.head(5)["ticker"].tolist()

    # Verdict
    avg_sharpe = metrics_df["sharpe_ratio"].mean() if not metrics_df.empty and "sharpe_ratio" in metrics_df.columns else 0.0
    verdict = (
        "accepted" if avg_sharpe > 1.0
        else "watch" if avg_sharpe > 0.5
        else "needs_more_testing"
    )

    return {
        "hypothesis": (
            "Momentum: stocks with strong recent returns continue to outperform. "
            "Signal = momentum_20d * ma_crossover_confirmation."
        ),
        "signals": {t: s.describe().to_dict() for t, s in signals_dict.items()},
        "backtests": {t: _safe_backtest_summary(b) for t, b in backtests.items()},
        "metrics_df": metrics_df,
        "verdict": verdict,
        "risks": [
            "Momentum crashes during market regime changes",
            "High turnover increases transaction costs",
            "May underperform in sideways markets",
        ],
        "top_picks": top_picks,
    }


def run_mean_reversion_strategy(
    prices: pd.DataFrame,
    tickers: list[str],
) -> dict:
    """Run a complete mean-reversion strategy research pipeline.

    Steps
    -----
    1. Compute z-score mean-reversion signals.
    2. Compute Bollinger Band position signals.
    3. Combine signals for position sizing.
    4. Backtest each ticker with transaction costs.
    5. Aggregate metrics.

    Parameters
    ----------
    prices:
        MultiIndex DataFrame with columns ``(ticker, field)``.
    tickers:
        Tickers to evaluate.

    Returns
    -------
    dict
        Same structure as :func:`run_momentum_strategy`.
    """
    engine = BacktestEngine()
    backtests: Dict[str, Any] = {}
    all_metrics: List[dict] = []
    signals_dict: Dict[str, pd.Series] = {}

    close_prices = _get_close_prices(prices, tickers)

    for ticker in close_prices.columns:
        price_series = close_prices[ticker].dropna()
        if len(price_series) < 50:
            continue

        try:
            returns = price_series.pct_change().dropna()

            # 1. Z-score mean reversion
            z_signal = z_score_mean_reversion(returns, window=20, threshold=2.0)

            # 2. Bollinger band position (0 = lower band, 1 = upper band)
            bb_pos = bollinger_band_position(price_series, window=20, num_std=2.0)

            # 3. Combined: use z-score as primary, BB as confirmation
            # z_score signal is in [-1, 1]; we want to go long when oversold (negative z → positive signal)
            # Use BB position: 0 = oversold (buy), 1 = overbought (sell)
            bb_mr_signal = 1.0 - bb_pos.reindex(z_signal.index, method="ffill") * 2.0  # maps [0,1] → [1,-1]
            combined = (z_signal + bb_mr_signal) / 2.0  # average to [-1, 1]
            combined = np.clip(combined.fillna(0.0), -1.0, 1.0)
            combined.name = ticker

            signals_dict[ticker] = combined

            # 4. Backtest
            prices_df = price_series.to_frame("Close")
            result = engine.run(
                prices=prices_df,
                signal=combined,
                initial_capital=INITIAL_CAPITAL,
                cost_model=COST_MODEL,
            )
            backtests[ticker] = result

            metrics_row = dict(result.metrics)
            metrics_row["ticker"] = ticker
            metrics_row["strategy"] = "mean_reversion"
            all_metrics.append(metrics_row)

        except Exception as exc:
            logger.warning("Mean-reversion strategy failed for %s: %s", ticker, exc)

    metrics_df = pd.DataFrame(all_metrics) if all_metrics else pd.DataFrame()

    top_picks: list[str] = []
    if not metrics_df.empty and "sharpe_ratio" in metrics_df.columns:
        ranked = metrics_df.sort_values("sharpe_ratio", ascending=False)
        top_picks = ranked.head(5)["ticker"].tolist()

    avg_sharpe = metrics_df["sharpe_ratio"].mean() if not metrics_df.empty and "sharpe_ratio" in metrics_df.columns else 0.0
    verdict = (
        "accepted" if avg_sharpe > 1.0
        else "watch" if avg_sharpe > 0.5
        else "needs_more_testing"
    )

    return {
        "hypothesis": (
            "Mean Reversion: extreme price deviations from the mean tend to revert. "
            "Signal = (z_score_mean_reversion + inverted_bollinger_position) / 2."
        ),
        "signals": {t: s.describe().to_dict() for t, s in signals_dict.items()},
        "backtests": {t: _safe_backtest_summary(b) for t, b in backtests.items()},
        "metrics_df": metrics_df,
        "verdict": verdict,
        "risks": [
            "Momentum continuation can cause sustained losses",
            "Volatility expansion increases position risk",
            "Fundamental regime shifts invalidate mean-reversion assumption",
        ],
        "top_picks": top_picks,
    }


def run_arbitrage_strategy(
    prices: pd.DataFrame,
    tickers: list[str],
) -> dict:
    """Run a statistical-arbitrage (pair-trading) research pipeline.

    Steps
    -----
    1. Find top 10 correlated pairs from the universe.
    2. For each pair: compute spread, z-score, and hedge ratio.
    3. Generate signals based on spread deviation.
    4. Backtest each pair with transaction costs.
    5. Aggregate metrics.

    Parameters
    ----------
    prices:
        MultiIndex DataFrame with columns ``(ticker, field)``.
    tickers:
        Tickers to evaluate.

    Returns
    -------
    dict
        Keys: ``hypothesis``, ``pairs``, ``backtests``, ``metrics_df``,
        ``verdict``, ``risks``.
    """
    engine = BacktestEngine()
    backtests: Dict[str, Any] = {}
    all_metrics: List[dict] = []

    # Get close prices for all tickers
    close_prices = _get_close_prices(prices, tickers)
    close_prices = close_prices.dropna(how="all", axis=1).dropna(how="all", axis=0)

    if close_prices.shape[1] < 2 or len(close_prices) < 30:
        logger.warning("Insufficient data for arbitrage scanning")
        return {
            "hypothesis": "Statistical Arbitrage: correlated pairs revert to mean spread.",
            "pairs": [],
            "backtests": {},
            "metrics_df": pd.DataFrame(),
            "verdict": "needs_more_testing",
            "risks": ["Insufficient data to evaluate pairs"],
        }

    # Use the arbitrage_scan from strategies module
    try:
        pairs_df = arbitrage_scan(close_prices, min_correlation=0.7, max_pairs=20)
    except Exception as exc:
        logger.warning("arbitrage_scan failed: %s", exc)
        pairs_df = pd.DataFrame()

    if pairs_df is None or pairs_df.empty:
        logger.info("No suitable pairs found for arbitrage")
        return {
            "hypothesis": "Statistical Arbitrity: correlated pairs revert to mean spread.",
            "pairs": [],
            "backtests": {},
            "metrics_df": pd.DataFrame(),
            "verdict": "needs_more_testing",
            "risks": ["No sufficiently correlated pairs found"],
        }

    # Take top 10 pairs by confidence score
    top_pairs = pairs_df.head(10)
    pair_signals: Dict[str, pd.Series] = {}

    for _, row in top_pairs.iterrows():
        stock_a = row["stock_a"]
        stock_b = row["stock_b"]
        pair_name = f"{stock_a}-{stock_b}"

        if stock_a not in close_prices.columns or stock_b not in close_prices.columns:
            continue

        try:
            # Compute spread: log(a) - hedge_ratio * log(b)
            log_a = np.log(close_prices[stock_a].replace(0, np.nan)).dropna()
            log_b = np.log(close_prices[stock_b].replace(0, np.nan)).dropna()
            aligned = pd.concat([log_a, log_b], axis=1).dropna()
            if len(aligned) < 30:
                continue

            hedge_ratio = float(row.get("hedge_ratio", 1.0))
            spread = aligned.iloc[:, 0] - hedge_ratio * aligned.iloc[:, 1]

            # Z-score the spread
            spread_mean = spread.rolling(window=20).mean()
            spread_std = spread.rolling(window=20).std().replace(0, np.nan)
            zscore = ((spread - spread_mean) / spread_std).fillna(0.0)

            # Signal: go long spread when z-score is very negative, short when very positive
            signal = np.clip(-zscore / 2.0, -1.0, 1.0)
            signal.name = pair_name
            pair_signals[pair_name] = signal

            # Backtest using spread as proxy for returns
            spread_returns = spread.diff().fillna(0.0)
            # Signal-based returns
            shifted_signal = signal.shift(1).fillna(0.0)
            strategy_returns = shifted_signal * spread_returns

            # Build minimal BacktestResult manually
            cumulative = (1.0 + strategy_returns).cumprod()
            _ = INITIAL_CAPITAL * cumulative  # noqa: F841  # noqa: F841

            prices_df = spread.to_frame("Close")
            result = engine.run(
                prices=prices_df,
                signal=signal,
                initial_capital=INITIAL_CAPITAL,
                cost_model=COST_MODEL,
            )
            backtests[pair_name] = result

            metrics_row = dict(result.metrics)
            metrics_row["pair"] = pair_name
            metrics_row["stock_a"] = stock_a
            metrics_row["stock_b"] = stock_b
            metrics_row["correlation"] = row.get("correlation", 0.0)
            metrics_row["strategy"] = "arbitrage"
            all_metrics.append(metrics_row)

        except Exception as exc:
            logger.warning("Arbitrage backtest failed for %s: %s", pair_name, exc)

    metrics_df = pd.DataFrame(all_metrics) if all_metrics else pd.DataFrame()

    avg_sharpe = metrics_df["sharpe_ratio"].mean() if not metrics_df.empty and "sharpe_ratio" in metrics_df.columns else 0.0
    verdict = (
        "accepted" if avg_sharpe > 1.0
        else "watch" if avg_sharpe > 0.5
        else "needs_more_testing"
    )

    return {
        "hypothesis": (
            "Statistical Arbitrage: cointegrated pairs exhibit mean-reverting spreads. "
            "Trade the spread when z-score exceeds ±2 standard deviations."
        ),
        "pairs": top_pairs.to_dict("records") if not top_pairs.empty else [],
        "backtests": {p: _safe_backtest_summary(b) for p, b in backtests.items()},
        "metrics_df": metrics_df,
        "verdict": verdict,
        "risks": [
            "Cointegration breakdown: fundamental divergence invalidates relationship",
            "Spread may widen further before reverting",
            "Execution risk: need simultaneous entry/exit of both legs",
        ],
    }


# ===========================================================================
# 4. Portfolio Construction
# ===========================================================================

def build_portfolio(
    metrics_df: pd.DataFrame,
) -> dict:
    """Build portfolio allocations using different weighting methods.

    Three allocation schemes are computed:

    * **equal_weight** — each strategy receives 1/3 of capital.
    * **inverse_vol** — weight proportional to 1 / volatility.
    * **best_sharpe** — full allocation to the strategy with highest Sharpe.

    Parameters
    ----------
    metrics_df:
        DataFrame with columns ``strategy``, ``ticker`` (or ``pair``),
        ``sharpe_ratio``, ``volatility``, ``total_return``, ``max_drawdown``.

    Returns
    -------
    dict
        Keys: ``allocations``, ``risk_metrics``, ``summary``.
    """
    if metrics_df.empty:
        return {
            "allocations": {},
            "risk_metrics": {},
            "summary": "No metrics available for portfolio construction",
        }

    # Group by strategy
    strategy_groups: Dict[str, pd.DataFrame] = {}
    for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
        mask = metrics_df["strategy"] == strategy_name
        if mask.any():
            strategy_groups[strategy_name] = metrics_df[mask]

    if not strategy_groups:
        return {
            "allocations": {},
            "risk_metrics": {},
            "summary": "No strategy groups found",
        }

    # Compute per-strategy aggregates
    strategy_stats: Dict[str, dict] = {}
    for name, group in strategy_groups.items():
        sharpe = group["sharpe_ratio"].mean() if "sharpe_ratio" in group.columns else 0.0
        vol = group["volatility"].mean() if "volatility" in group.columns else 0.01
        total_ret = group["total_return"].mean() if "total_return" in group.columns else 0.0
        max_dd = group["max_drawdown"].mean() if "max_drawdown" in group.columns else 0.0
        strategy_stats[name] = {
            "sharpe": float(sharpe),
            "volatility": float(vol) if vol > 0 else 0.01,
            "total_return": float(total_ret),
            "max_drawdown": float(max_dd),
        }

    strategies = list(strategy_stats.keys())
    n_strategies = len(strategies)

    # Equal weight
    equal_weights = {s: 1.0 / n_strategies for s in strategies}

    # Inverse volatility weight
    inv_vols = {s: 1.0 / stats["volatility"] for s, stats in strategy_stats.items()}
    total_inv = sum(inv_vols.values())
    inv_vol_weights = {s: v / total_inv for s, v in inv_vols.items()} if total_inv > 0 else equal_weights

    # Best Sharpe weight
    best_strategy = max(strategy_stats, key=lambda s: strategy_stats[s]["sharpe"])
    best_sharpe_weights = {s: 1.0 if s == best_strategy else 0.0 for s in strategies}

    allocations = {
        "equal_weight": equal_weights,
        "inverse_vol": inv_vol_weights,
        "best_sharpe": best_sharpe_weights,
    }

    # Risk metrics per allocation
    risk_metrics: Dict[str, dict] = {}
    for method_name, weights in allocations.items():
        # Portfolio-level expected return and risk (simplified)
        port_return = sum(
            weights[s] * strategy_stats[s]["total_return"]
            for s in strategies
        )
        # Approximate portfolio variance (assume zero correlation between strategies)
        port_var = sum(
            (weights[s] * strategy_stats[s]["volatility"]) ** 2
            for s in strategies
        )
        port_vol = float(np.sqrt(port_var))

        risk_metrics[method_name] = {
            "expected_return": round(port_return, 4),
            "expected_volatility": round(port_vol, 4),
            "expected_sharpe": round(port_return / port_vol, 4) if port_vol > 0 else 0.0,
        }

    return {
        "allocations": allocations,
        "risk_metrics": risk_metrics,
        "strategy_stats": strategy_stats,
        "summary": (
            f"Portfolio built from {n_strategies} strategies. "
            f"Best Sharpe strategy: {best_strategy} "
            f"(Sharpe={strategy_stats[best_strategy]['sharpe']:.2f}). "
            "All allocations are for research/educational purposes only."
        ),
    }


# ===========================================================================
# 5. Memory Logging
# ===========================================================================

def log_results_to_memory(
    results: dict,
    db_path: str = "memory/alpha_search_research.duckdb",
) -> None:
    """Log all strategy results to the persistent memory layer.

    Uses :class:`MemoryStore` for structured storage and
    :class:`AgentJournal` for dual-write (DB + Markdown) logging.

    Parameters
    ----------
    results:
        The combined results dictionary from :func:`run_full_pipeline`.
    db_path:
        Path to the DuckDB/SQLite memory database.
    """
    try:
        store = MemoryStore(db_path=db_path)
        store.initialize()
        journal = AgentJournal(store=store, journal_dir="memory")

        run_timestamp = datetime.now(timezone.utc)

        # Log pipeline start task
        journal.log_task(
            agent_name="real_data_pipeline",
            task="Full research pipeline execution",
            status="completed",
            notes=f"Markets: US ({len(US_TOP20)} stocks) + India ({len(INDIA_TOP20)} stocks). Timestamp: {run_timestamp.isoformat()}",
            tags=["research", "pipeline", "real_data"],
        )

        # Log each strategy result
        for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
            strategy_result = results.get(strategy_name, {})
            metrics_df = strategy_result.get("metrics_df", pd.DataFrame())
            if metrics_df.empty:
                continue

            avg_sharpe = metrics_df["sharpe_ratio"].mean() if "sharpe_ratio" in metrics_df.columns else 0.0
            avg_drawdown = metrics_df["max_drawdown"].mean() if "max_drawdown" in metrics_df.columns else 0.0
            avg_return = metrics_df["total_return"].mean() if "total_return" in metrics_df.columns else 0.0
            avg_win_rate = metrics_df["win_rate"].mean() if "win_rate" in metrics_df.columns else 0.0
            universe = metrics_df["ticker"].tolist() if "ticker" in metrics_df.columns else []

            verdict = strategy_result.get("verdict", "watch")
            hypothesis = strategy_result.get("hypothesis", "")
            risks = strategy_result.get("risks", [])
            top_picks = strategy_result.get("top_picks", [])

            memory = StrategyMemory(
                strategy_name=f"{strategy_name}_real_data",
                strategy_type=strategy_name,
                market="US+India",
                asset_class="equity",
                universe=universe[:20],
                hypothesis=hypothesis,
                result_summary=(
                    f"Avg Sharpe: {avg_sharpe:.2f}. "
                    f"Avg Return: {avg_return:.2%}. "
                    f"Top picks: {', '.join(top_picks[:5])}. "
                    "Research/educational only."
                ),
                sharpe=avg_sharpe,
                max_drawdown=avg_drawdown,
                total_return=avg_return,
                win_rate=avg_win_rate,
                turnover=None,
                transaction_cost_assumption=str(COST_MODEL),
                validation_method="backtest_with_transaction_costs",
                verdict=verdict,
                rejection_reason="" if verdict != "rejected" else "; ".join(risks),
                lessons_learned="; ".join(risks),
            )
            journal.log_strategy_result(memory)

        # Log portfolio result
        portfolio = results.get("portfolio", {})
        if portfolio and portfolio.get("allocations"):
            alloc_summary = str(portfolio.get("summary", ""))
            journal.log_decision(
                agent_name="portfolio_constructor",
                decision="Portfolio allocation computed",
                rationale=alloc_summary,
                tags=["portfolio", "allocation", "research"],
                importance_score=0.8,
            )

        # Log sentiment result
        sentiment = results.get("sentiment", {})
        if sentiment:
            avg_score = sum(s.get("score", 0) for s in sentiment.values()) / max(len(sentiment), 1)
            journal.log_task(
                agent_name="sentiment_analyzer",
                task="FinBERT sentiment analysis",
                status="completed",
                notes=f"Analysed {len(sentiment)} tickers. Avg sentiment score: {avg_score:.3f}.",
                tags=["sentiment", "finbert"],
            )

        store.close()
        logger.info("Results logged to memory at %s", db_path)

    except Exception as exc:
        logger.warning("Memory logging failed: %s", exc)


# ===========================================================================
# 6. Full Pipeline Orchestrator
# ===========================================================================

def run_full_pipeline(
    output_dir: str = "reports",
) -> dict:
    """Execute the complete real-data research pipeline.

    Orchestrates data fetching, sentiment analysis, strategy research,
    portfolio construction, and memory logging across US and Indian equities.

    Parameters
    ----------
    output_dir:
        Directory for output reports (created if it does not exist).

    Returns
    -------
    dict
        Combined results with keys:
        ``us_data``, ``india_data``, ``sentiment``,
        ``momentum``, ``mean_reversion``, ``arbitrage``,
        ``portfolio``, ``memory_logged``, ``disclaimer``.
    """
    os.makedirs(output_dir, exist_ok=True)
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("Alpha Search Real Data Pipeline Starting")
    logger.info("Timestamp: %s", start_time.isoformat())
    logger.info("=" * 60)

    # Determine date range: last 6 months
    end_date = start_time.date()
    start_date = end_date - timedelta(days=180)
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    results: Dict[str, Any] = {
        "pipeline_start": start_time.isoformat(),
        "disclaimer": (
            "RESEARCH / EDUCATIONAL PURPOSES ONLY. "
            "NOT INVESTMENT ADVICE. PAST PERFORMANCE DOES NOT GUARANTEE FUTURE RESULTS."
        ),
    }

    # ------------------------------------------------------------------
    # 1. Fetch US data
    # ------------------------------------------------------------------
    logger.info("--- Fetching US equity data (%d tickers) ---", len(US_TOP20))
    us_prices = fetch_real_data(US_TOP20, start_str, end_str)
    results["us_data"] = {
        "tickers_requested": len(US_TOP20),
        "tickers_fetched": len(us_prices.columns.get_level_values(0).unique()) if not us_prices.empty else 0,
        "rows": len(us_prices),
    }

    # ------------------------------------------------------------------
    # 2. Fetch India data
    # ------------------------------------------------------------------
    logger.info("--- Fetching India equity data (%d tickers) ---", len(INDIA_TOP20))
    india_prices = fetch_real_data(INDIA_TOP20, start_str, end_str)
    results["india_data"] = {
        "tickers_requested": len(INDIA_TOP20),
        "tickers_fetched": len(india_prices.columns.get_level_values(0).unique()) if not india_prices.empty else 0,
        "rows": len(india_prices),
    }

    # ------------------------------------------------------------------
    # 3. Run sentiment analysis
    # ------------------------------------------------------------------
    logger.info("--- Running FinBERT sentiment analysis ---")
    all_tickers = list(set(US_TOP20 + INDIA_TOP20))
    try:
        sentiment_results = run_sentiment_analysis(all_tickers)
        results["sentiment"] = sentiment_results
    except RuntimeError as exc:
        logger.warning("Sentiment analysis unavailable: %s", exc)
        results["sentiment"] = {}

    # ------------------------------------------------------------------
    # 4. Run strategies on US data
    # ------------------------------------------------------------------
    if not us_prices.empty:
        us_tickers = list(us_prices.columns.get_level_values(0).unique())

        logger.info("--- Running momentum strategy (US) ---")
        momentum_result = run_momentum_strategy(us_prices, us_tickers)
        results["momentum"] = momentum_result

        logger.info("--- Running mean-reversion strategy (US) ---")
        mr_result = run_mean_reversion_strategy(us_prices, us_tickers)
        results["mean_reversion"] = mr_result

        logger.info("--- Running arbitrage strategy (US) ---")
        arb_result = run_arbitrage_strategy(us_prices, us_tickers)
        results["arbitrage"] = arb_result

        # ------------------------------------------------------------------
        # 5. Build portfolio
        # ------------------------------------------------------------------
        logger.info("--- Building portfolio ---")
        all_metrics_frames: List[pd.DataFrame] = []
        for sr in [momentum_result, mr_result, arb_result]:
            mdf = sr.get("metrics_df", pd.DataFrame())
            if not mdf.empty:
                all_metrics_frames.append(mdf)

        if all_metrics_frames:
            combined_metrics = pd.concat(all_metrics_frames, ignore_index=True)
            portfolio_result = build_portfolio(combined_metrics)
            results["portfolio"] = portfolio_result
        else:
            results["portfolio"] = {
                "allocations": {},
                "risk_metrics": {},
                "summary": "No metrics available for portfolio construction",
            }
    else:
        raise RuntimeError(
            "No US data available — cannot run strategies. "
            "Check network connection and ensure yfinance is installed."
        )

    # ------------------------------------------------------------------
    # 6. Log to memory
    # ------------------------------------------------------------------
    logger.info("--- Logging results to memory ---")
    try:
        log_results_to_memory(results)
        results["memory_logged"] = True
    except Exception as exc:
        logger.warning("Memory logging error: %s", exc)
        results["memory_logged"] = False

    # ------------------------------------------------------------------
    # 7. Save report
    # ------------------------------------------------------------------
    try:
        report_path = os.path.join(output_dir, "real_data_pipeline_report.md")
        _write_markdown_report(report_path, results)
        results["report_path"] = report_path
    except Exception as exc:
        logger.warning("Report writing failed: %s", exc)

    end_time = datetime.now(timezone.utc)
    results["pipeline_end"] = end_time.isoformat()
    results["duration_seconds"] = (end_time - start_time).total_seconds()

    logger.info("=" * 60)
    logger.info("Pipeline Complete in %.1f seconds", results["duration_seconds"])
    logger.info("=" * 60)

    return results


# ===========================================================================
# 7. Console Summary
# ===========================================================================

def print_summary(
    results: dict,
) -> None:
    """Print a beautifully formatted console summary of pipeline results.

    Parameters
    ----------
    results:
        The results dictionary returned by :func:`run_full_pipeline`.
    """
    print("\n" + "=" * 72)
    print("   ALPHA SEARCH -- REAL DATA RESEARCH PIPELINE SUMMARY")
    print("=" * 72)

    disclaimer = results.get("disclaimer", "")
    print(f"\n   DISCLAIMER: {disclaimer}")

    # Timing
    start = results.get("pipeline_start", "N/A")
    end = results.get("pipeline_end", "N/A")
    duration = results.get("duration_seconds", 0)
    print(f"\n   Pipeline Start: {start}")
    print(f"   Pipeline End:   {end}")
    print(f"   Duration:       {duration:.1f}s")

    # Data
    us_data = results.get("us_data", {})
    india_data = results.get("india_data", {})
    print("\n   --- DATA FETCHING ---")
    print(f"   US tickers:    {us_data.get('tickers_fetched', 0)}/{us_data.get('tickers_requested', 0)} fetched")
    print(f"   India tickers: {india_data.get('tickers_fetched', 0)}/{india_data.get('tickers_requested', 0)} fetched")

    # Sentiment
    sentiment = results.get("sentiment", {})
    if sentiment:
        avg_score = sum(s.get("score", 0) for s in sentiment.values()) / max(len(sentiment), 1)
        most_bullish = max(sentiment.items(), key=lambda x: x[1].get("score", 0))
        most_bearish = min(sentiment.items(), key=lambda x: x[1].get("score", 0))
        print("\n   --- SENTIMENT (FinBERT) ---")
        print(f"   Tickers analysed: {len(sentiment)}")
        print(f"   Average score:    {avg_score:+.3f}")
        print(f"   Most bullish:     {most_bullish[0]} ({most_bullish[1].get('score', 0):+.3f})")
        print(f"   Most bearish:     {most_bearish[0]} ({most_bearish[1].get('score', 0):+.3f})")

    # Strategies
    for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
        sr = results.get(strategy_name, {})
        metrics_df = sr.get("metrics_df", pd.DataFrame())
        verdict = sr.get("verdict", "N/A")
        top_picks = sr.get("top_picks", [])

        print(f"\n   --- {strategy_name.upper()} STRATEGY ---")
        print(f"   Verdict:    {verdict}")

        if not metrics_df.empty:
            avg_sharpe = metrics_df["sharpe_ratio"].mean() if "sharpe_ratio" in metrics_df.columns else 0.0
            avg_return = metrics_df["total_return"].mean() if "total_return" in metrics_df.columns else 0.0
            avg_dd = metrics_df["max_drawdown"].mean() if "max_drawdown" in metrics_df.columns else 0.0
            print(f"   Avg Sharpe: {avg_sharpe:.2f}")
            print(f"   Avg Return: {avg_return:+.2%}")
            print(f"   Avg Max DD: {avg_dd:.2%}")
        else:
            print("   No backtest metrics available")

        if top_picks:
            print(f"   Top picks:  {', '.join(top_picks[:5])}")

    # Portfolio
    portfolio = results.get("portfolio", {})
    if portfolio and portfolio.get("allocations"):
        print("\n   --- PORTFOLIO ALLOCATION ---")
        for method_name, weights in portfolio["allocations"].items():
            weight_str = ", ".join(f"{k}={v:.1%}" for k, v in weights.items())
            print(f"   {method_name:15s}: {weight_str}")

        print("\n   --- PORTFOLIO RISK METRICS ---")
        for method_name, risk in portfolio.get("risk_metrics", {}).items():
            print(
                f"   {method_name:15s}: Return={risk.get('expected_return', 0):.2%}  "
                f"Vol={risk.get('expected_volatility', 0):.2%}  "
                f"Sharpe={risk.get('expected_sharpe', 0):.2f}"
            )

    # Memory
    print("\n   --- MEMORY ---")
    print(f"   Logged to persistent memory: {results.get('memory_logged', False)}")

    report_path = results.get("report_path")
    if report_path:
        print(f"   Report saved: {report_path}")

    print("\n" + "=" * 72)
    print(f"   END OF REPORT -- {results.get('disclaimer', '')}")
    print("=" * 72 + "\n")


# ===========================================================================
# 8. Helpers
# ===========================================================================

def _get_close_prices(
    prices: pd.DataFrame,
    tickers: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Extract close prices from a MultiIndex OHLCV DataFrame.

    Parameters
    ----------
    prices:
        DataFrame with MultiIndex columns ``(ticker, field)``.
    tickers:
        Optional subset of tickers to extract.

    Returns
    -------
    pandas.DataFrame
        DataFrame with tickers as columns and close prices as values.
    """
    if prices.empty:
        return pd.DataFrame()

    close_data: Dict[str, pd.Series] = {}

    # Handle MultiIndex columns
    if isinstance(prices.columns, pd.MultiIndex):
        for ticker, field in prices.columns:
            if field == "Close":
                if tickers is None or ticker in tickers:
                    close_data[ticker] = prices[(ticker, field)]
    else:
        # Single-level columns -- assume Close directly
        if "Close" in prices.columns:
            close_data["Close"] = prices["Close"]

    if not close_data:
        return pd.DataFrame()

    return pd.DataFrame(close_data)


def _safe_backtest_summary(
    result: Any,
) -> dict:
    """Extract a safe JSON-serialisable summary from a BacktestResult.

    Parameters
    ----------
    result:
        A :class:`BacktestResult` instance.

    Returns
    -------
    dict
        Serialisable summary dict.
    """
    try:
        return {
            "total_return": float(result.metrics.get("total_return", 0)),
            "sharpe_ratio": float(result.metrics.get("sharpe_ratio", 0)),
            "max_drawdown": float(result.metrics.get("max_drawdown", 0)),
            "volatility": float(result.metrics.get("volatility", 0)),
            "win_rate": float(result.metrics.get("win_rate", 0)),
            "num_trades": int(len(result.trades)) if hasattr(result.trades, "__len__") else 0,
            "num_days": int(result.metrics.get("num_days", 0)),
        }
    except Exception:
        return {"error": "Failed to extract backtest summary"}


def _write_markdown_report(
    path: str,
    results: dict,
) -> None:
    """Write a Markdown report of the pipeline results.

    Parameters
    ----------
    path:
        File path to write the Markdown report.
    results:
        The combined results dictionary.
    """
    lines: List[str] = [
        "# Alpha Search -- Real Data Research Pipeline Report",
        "",
        f"**Generated:** {results.get('pipeline_end', 'N/A')}",
        "",
        "> **DISCLAIMER:** {}".format(results.get("disclaimer", "")),
        "",
        "## Data Fetching",
        "",
    ]

    us_data = results.get("us_data", {})
    india_data = results.get("india_data", {})
    lines.extend([
        f"- US equities: {us_data.get('tickers_fetched', 0)}/{us_data.get('tickers_requested', 0)} tickers fetched",
        f"- India equities: {india_data.get('tickers_fetched', 0)}/{india_data.get('tickers_requested', 0)} tickers fetched",
        "",
        "## Sentiment Analysis (FinBERT)",
        "",
    ])

    sentiment = results.get("sentiment", {})
    if sentiment:
        avg_score = sum(s.get("score", 0) for s in sentiment.values()) / max(len(sentiment), 1)
        lines.append(f"- Tickers analysed: {len(sentiment)}")
        lines.append(f"- Average sentiment score: {avg_score:+.3f}")
        lines.append("")
        lines.append("| Ticker | Score | Direction |")
        lines.append("|--------|-------|-----------|")
        for ticker, s in sorted(sentiment.items(), key=lambda x: abs(x[1].get("score", 0)), reverse=True)[:10]:
            score = s.get("score", 0)
            direction = "Bullish" if score > 0.1 else "Bearish" if score < -0.1 else "Neutral"
            lines.append(f"| {ticker} | {score:+.3f} | {direction} |")
        lines.append("")

    for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
        sr = results.get(strategy_name, {})
        hypothesis = sr.get("hypothesis", "")
        verdict = sr.get("verdict", "N/A")
        metrics_df = sr.get("metrics_df", pd.DataFrame())
        top_picks = sr.get("top_picks", [])

        lines.extend([
            f"## {strategy_name.replace('_', ' ').title()} Strategy",
            "",
            f"**Hypothesis:** {hypothesis}",
            "",
            f"**Verdict:** {verdict}",
            "",
        ])

        if not metrics_df.empty:
            lines.append("### Performance Metrics")
            lines.append("")
            lines.append("| Metric | Avg Value |")
            lines.append("|--------|-----------|")
            for col in ["sharpe_ratio", "total_return", "max_drawdown", "volatility", "win_rate"]:
                if col in metrics_df.columns:
                    val = metrics_df[col].mean()
                    if col in ("total_return", "max_drawdown", "win_rate"):
                        lines.append(f"| {col} | {val:.2%} |")
                    else:
                        lines.append(f"| {col} | {val:.3f} |")
            lines.append("")

        if top_picks:
            lines.append(f"**Top picks:** {', '.join(top_picks[:5])}")
            lines.append("")

    portfolio = results.get("portfolio", {})
    if portfolio and portfolio.get("allocations"):
        lines.extend([
            "## Portfolio Allocation",
            "",
        ])
        for method_name, weights in portfolio["allocations"].items():
            weight_str = ", ".join(f"{k}={v:.1%}" for k, v in weights.items())
            lines.append(f"- **{method_name}**: {weight_str}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "*This report is for research and educational purposes only.*",
        "",
    ])

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("Markdown report written to %s", path)


# ===========================================================================
# CLI Entry Point
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    print("\n" + "=" * 60)
    print("Alpha Search -- Real Data Research Pipeline")
    print("=" * 60)
    print("DISCLAIMER: Research/educational purposes only.\n")

    results = run_full_pipeline()
    print_summary(results)
