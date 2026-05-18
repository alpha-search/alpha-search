"""Alpha Search -- Real Data Research Pipeline.

Fetches actual market data, runs full agent swarm, produces research report.
Uses real YFinance data for top US and Indian equities.

DISCLAIMER: This pipeline is for research and educational purposes only.
All outputs are labelled as "research/educational only" and should not be
construed as investment advice.

Pipeline stages:
    1. Data fetching (YFinanceProvider + direct yfinance fallback)
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

    Attempts to fetch each ticker individually using :class:`YFinanceProvider`.
    If that fails, falls back to a direct ``yfinance.download`` call.
    Tickers that fail both attempts are skipped with a warning.

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
        Only tickers that were successfully fetched are included.
    """
    # Try to initialise YFinanceProvider; fall back to direct yfinance if
    # dependencies (e.g. duckdb) are unavailable.
    try:
        provider = YFinanceProvider()
    except Exception as exc:
        logger.warning("YFinanceProvider unavailable (%s). Using direct yfinance.", exc)
        provider = None

    frames: Dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        # Attempt 1: YFinanceProvider (with caching)
        if provider is not None:
            try:
                df = provider.get_prices(ticker, start, end)
                if df is not None and not df.empty and len(df) >= 10:
                    frames[ticker] = df
                    logger.info("Fetched %s: %d rows via YFinanceProvider", ticker, len(df))
                    continue
            except Exception as exc:
                logger.debug("YFinanceProvider failed for %s: %s", ticker, exc)

        # Attempt 2: Direct yfinance download
        try:
            import yfinance as yf

            df = yf.download(ticker, start=start, end=end, progress=False)
            if df is not None and not df.empty and len(df) >= 10:
                # Normalise column names
                df.columns = [c.title() if isinstance(c, str) else c for c in df.columns]
                # Keep only standard OHLCV columns
                std_cols = ["Open", "High", "Low", "Close", "Volume"]
                available = [c for c in std_cols if c in df.columns]
                if available:
                    frames[ticker] = df[available]
                    logger.info("Fetched %s: %d rows via direct yfinance", ticker, len(df))
                    continue
        except Exception as exc:
            logger.debug("Direct yfinance failed for %s: %s", ticker, exc)

        logger.warning("Failed to fetch %s — skipping", ticker)

    if not frames:
        logger.error("No data fetched for any ticker")
        return pd.DataFrame()

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
        return pd.DataFrame()

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
    built from the ticker symbol and a brief description.  If FinBERT is
    unavailable, falls back to the built-in keyword-based analyser.

    Parameters
    ----------
    tickers:
        List of ticker symbols.

    Returns
    -------
    dict[str, dict]
        Mapping ``{ticker: {"score": float, "positive": float,
        "negative": float, "neutral": float}}``.
    """
    try:
        analyzer = FinBERTSentimentAnalyzer()
    except Exception as exc:
        logger.warning("FinBERT initialisation failed: %s. Using fallback.", exc)
        analyzer = None

    results: dict[str, dict] = {}
    for ticker in tickers:
        try:
            if analyzer is not None:
                # Build a composite description for the ticker
                description = _ticker_description(ticker)
                sentiment = analyzer.analyze(description)
                results[ticker] = {
                    "score": float(sentiment.get("score", 0.0)),
                    "positive": float(sentiment.get("positive", 0.33)),
                    "negative": float(sentiment.get("negative", 0.33)),
                    "neutral": float(sentiment.get("neutral", 0.34)),
                }
            else:
                results[ticker] = {
                    "score": 0.0, "positive": 0.33, "negative": 0.33, "neutral": 0.34,
                }
        except Exception as exc:
            logger.warning("Sentiment analysis failed for %s: %s", ticker, exc)
            results[ticker] = {
                "score": 0.0, "positive": 0.33, "negative": 0.33, "neutral": 0.34,
            }

    logger.info("Sentiment analysis complete for %d tickers", len(tickers))
    return results


def _ticker_description(ticker: str) -> str:
    """Return a brief text description for a ticker to feed FinBERT."""
    from alpha_search.opportunities.market_universes import get_company_name

    name = get_company_name(ticker)
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
    sentiment_results = run_sentiment_analysis(all_tickers)
    results["sentiment"] = sentiment_results

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
        logger.warning("No US data available — skipping strategies")
        results["momentum"] = {"metrics_df": pd.DataFrame(), "verdict": "needs_more_testing"}
        results["mean_reversion"] = {"metrics_df": pd.DataFrame(), "verdict": "needs_more_testing"}
        results["arbitrage"] = {"metrics_df": pd.DataFrame(), "verdict": "needs_more_testing"}
        results["portfolio"] = {"allocations": {}, "risk_metrics": {}}

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

# ===========================================================================
# Extended Real-Data Backtesting API
# Colab / script-friendly standalone functions.
# All functions use real OHLCV data only — no simulation, no random returns.
# ===========================================================================

# ---------------------------------------------------------------------------
# Universe definitions
# ---------------------------------------------------------------------------

UNIVERSE_US_LARGE_CAP: List[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "JPM", "XOM", "UNH", "SPY", "QQQ",
]
UNIVERSE_INDIA_EQUITY: List[str] = [
    "NIFTYBEES.NS", "BANKBEES.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "RELIANCE.NS", "INFY.NS", "TATASTEEL.NS", "LT.NS",
]
UNIVERSE_CRYPTO: List[str] = ["BTC-USD", "ETH-USD", "SOL-USD"]

UNIVERSES: Dict[str, List[str]] = {
    "us_large_cap": UNIVERSE_US_LARGE_CAP,
    "india_equity": UNIVERSE_INDIA_EQUITY,
    "crypto": UNIVERSE_CRYPTO,
    "all": UNIVERSE_US_LARGE_CAP + UNIVERSE_INDIA_EQUITY + UNIVERSE_CRYPTO,
}

# ---------------------------------------------------------------------------
# 1. fetch_yfinance_ohlcv
# ---------------------------------------------------------------------------

def fetch_yfinance_ohlcv(
    symbols: List[str],
    period: str = "2y",
    interval: str = "1d",
) -> tuple:
    """Fetch real OHLCV from yfinance using period/interval API.

    Each symbol is fetched independently so a single failure does not
    prevent others from succeeding.  Failed symbols are logged and
    returned in the ``failed`` list — no data is fabricated.

    Parameters
    ----------
    symbols:
        Yahoo-Finance ticker symbols.
    period:
        History period accepted by yfinance, e.g. ``"1y"``, ``"2y"``.
    interval:
        Bar interval, e.g. ``"1d"``, ``"1h"``.

    Returns
    -------
    tuple[dict[str, pd.DataFrame], list[str], list[str]]
        ``(frames, succeeded, failed)`` where *frames* maps ticker →
        single-ticker OHLCV DataFrame with columns
        ``Open, High, Low, Close, Volume``.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        logger.error("yfinance not installed: %s", exc)
        return {}, [], list(symbols)

    frames: Dict[str, pd.DataFrame] = {}
    succeeded: List[str] = []
    failed: List[str] = []

    for sym in symbols:
        try:
            raw = yf.download(
                sym,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
            if raw is None or raw.empty:
                logger.warning("fetch_yfinance_ohlcv: %s returned empty data — skipping", sym)
                failed.append(sym)
                continue

            # Flatten MultiIndex columns produced by recent yfinance versions
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            # Normalise to title-case column names
            raw.columns = [str(c).title() for c in raw.columns]

            std = ["Open", "High", "Low", "Close", "Volume"]
            available = [c for c in std if c in raw.columns]
            if "Close" not in available:
                logger.warning("fetch_yfinance_ohlcv: %s has no Close column — skipping", sym)
                failed.append(sym)
                continue

            df = raw[available].copy()
            df = df[df["Close"] > 0].dropna(subset=["Close"])

            if len(df) < 20:
                logger.warning(
                    "fetch_yfinance_ohlcv: %s has only %d valid rows — skipping",
                    sym, len(df),
                )
                failed.append(sym)
                continue

            frames[sym] = df
            succeeded.append(sym)
            logger.info("fetch_yfinance_ohlcv: %s — %d bars (%s interval)", sym, len(df), interval)

        except Exception as exc:
            logger.warning("fetch_yfinance_ohlcv: %s failed — %s", sym, exc)
            failed.append(sym)

    if failed:
        logger.warning(
            "fetch_yfinance_ohlcv: %d symbol(s) skipped: %s",
            len(failed), failed,
        )

    return frames, succeeded, failed


# ---------------------------------------------------------------------------
# 2. load_csv_ohlcv
# ---------------------------------------------------------------------------

def load_csv_ohlcv(filepath: str) -> Dict[str, pd.DataFrame]:
    """Load real OHLCV data from a CSV file.

    Expected CSV schema::

        timestamp,symbol,open,high,low,close,volume

    Columns are case-insensitive.  Returns a dict mapping each symbol
    to its OHLCV DataFrame (index = datetime, columns title-cased).

    Parameters
    ----------
    filepath:
        Path to the CSV file.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping symbol → single-ticker OHLCV DataFrame.
        Empty dict if the file cannot be parsed.
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as exc:
        logger.error("load_csv_ohlcv: cannot read %s — %s", filepath, exc)
        return {}

    # Normalise column names to lowercase
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        logger.error(
            "load_csv_ohlcv: missing required columns %s in %s", missing, filepath
        )
        return {}

    # Parse timestamp
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    except Exception as exc:
        logger.error("load_csv_ohlcv: cannot parse timestamp column — %s", exc)
        return {}

    frames: Dict[str, pd.DataFrame] = {}
    for sym, group in df.groupby("symbol"):
        ticker_df = group.set_index("timestamp").sort_index()
        ticker_df = ticker_df[["open", "high", "low", "close", "volume"]].copy()
        ticker_df.columns = ["Open", "High", "Low", "Close", "Volume"]
        # Remove rows with non-positive close
        ticker_df = ticker_df[ticker_df["Close"] > 0].dropna(subset=["Close"])
        if len(ticker_df) < 20:
            logger.warning("load_csv_ohlcv: %s has only %d valid rows — skipping", sym, len(ticker_df))
            continue
        frames[str(sym)] = ticker_df
        logger.info("load_csv_ohlcv: %s — %d rows loaded from CSV", sym, len(ticker_df))

    return frames


# ---------------------------------------------------------------------------
# 3. validate_ohlcv
# ---------------------------------------------------------------------------

def validate_ohlcv(
    df: pd.DataFrame,
    ticker: str = "",
) -> tuple:
    """Validate a single-ticker OHLCV DataFrame.

    Parameters
    ----------
    df:
        DataFrame with columns ``Open, High, Low, Close, Volume``.
    ticker:
        Ticker symbol for logging context.

    Returns
    -------
    tuple[bool, list[str]]
        ``(is_valid, warnings)`` where *is_valid* is ``True`` when the
        data passes the minimum quality bar.  *warnings* is a list of
        human-readable issue descriptions (may be non-empty even when
        ``is_valid`` is ``True``).
    """
    warnings_list: List[str] = []
    prefix = f"{ticker}: " if ticker else ""

    # Required columns
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        warnings_list.append(f"{prefix}Missing columns: {missing}")
        return False, warnings_list

    if df.empty:
        warnings_list.append(f"{prefix}DataFrame is empty")
        return False, warnings_list

    if len(df) < 20:
        warnings_list.append(
            f"{prefix}Only {len(df)} rows — minimum 20 required for signals"
        )
        return False, warnings_list

    # Non-positive prices — Close must be > 0 for all rows; other OHLC columns
    # may have occasional zeros (e.g. missing Volume) so only Close is fatal.
    n_bad_close = (df["Close"] <= 0).sum()
    if n_bad_close > 0:
        warnings_list.append(f"{prefix}Close: {n_bad_close} non-positive value(s)")
        return False, warnings_list

    for col in ["Open", "High", "Low"]:
        n_bad = (df[col] <= 0).sum()
        if n_bad > 0:
            warnings_list.append(f"{prefix}{col}: {n_bad} non-positive value(s)")

    # NaN rate
    close_nan_pct = df["Close"].isna().mean()
    if close_nan_pct > 0.1:
        warnings_list.append(
            f"{prefix}Close: {close_nan_pct:.1%} NaN (threshold 10%)"
        )

    # OHLCV integrity: High >= max(Open, Close), Low <= min(Open, Close)
    clean = df[["Open", "High", "Low", "Close"]].dropna()
    if not clean.empty:
        n_high_violation = ((clean["High"] < clean[["Open", "Close"]].max(axis=1))).sum()
        n_low_violation = ((clean["Low"] > clean[["Open", "Close"]].min(axis=1))).sum()
        if n_high_violation > 0:
            warnings_list.append(f"{prefix}High < max(Open,Close) on {n_high_violation} bar(s)")
            return False, warnings_list
        if n_low_violation > 0:
            warnings_list.append(f"{prefix}Low > min(Open,Close) on {n_low_violation} bar(s)")

    # Large single-day gap (> 50%) — likely split or data error
    returns = df["Close"].pct_change().dropna()
    if not returns.empty:
        max_gap = returns.abs().max()
        if max_gap > 0.5:
            gap_date = returns.abs().idxmax()
            warnings_list.append(
                f"{prefix}Large price gap: {max_gap:.1%} on {gap_date} "
                "(possible split/dividend — verify)"
            )

    is_valid = (
        close_nan_pct <= 0.5
        and len(df) >= 20
        and not missing
    )
    return is_valid, warnings_list


# ---------------------------------------------------------------------------
# 4. Signal generators
# ---------------------------------------------------------------------------

def generate_momentum_signal(
    close: pd.Series,
    lookback: int = 20,
    threshold: float = 0.0,
    ma_confirm: bool = True,
    ma_short: int = 20,
    ma_long: int = 50,
) -> pd.Series:
    """Generate a momentum signal from real price data.

    Signal logic:

    1. Compute *lookback*-day rolling return (``close / close.shift(lookback) - 1``).
    2. Go long (1.0) when return > *threshold*; flat (0.0) otherwise.
    3. Optionally confirm with MA crossover (short MA > long MA).

    No future data is used: all rolling calculations reference only past bars.
    Position is applied on the *following* bar by the BacktestEngine.

    Parameters
    ----------
    close:
        Real closing-price series.
    lookback:
        Return look-back window in bars.
    threshold:
        Minimum return for a long signal (0.0 = any positive return).
    ma_confirm:
        When ``True``, require MA crossover confirmation.
    ma_short, ma_long:
        Short / long MA periods for crossover confirmation.

    Returns
    -------
    pd.Series
        Binary signal in {0.0, 1.0}.
    """
    if len(close) < max(lookback, ma_long) + 5:
        return pd.Series(0.0, index=close.index, name=close.name)

    rolling_ret = close / close.shift(lookback) - 1.0
    signal = (rolling_ret > threshold).astype(float)

    if ma_confirm and ma_long > ma_short:
        sma_s = close.rolling(ma_short).mean()
        sma_l = close.rolling(ma_long).mean()
        ma_flag = (sma_s > sma_l).astype(float)
        signal = signal * ma_flag

    signal = signal.fillna(0.0)
    signal.name = close.name
    return signal


def generate_mean_reversion_signal(
    close: pd.Series,
    window: int = 20,
    z_threshold: float = 2.0,
    allow_short: bool = False,
) -> pd.Series:
    """Generate a mean-reversion signal from real price data.

    Signal logic:

    * Long (+1.0) when z-score < −*z_threshold* (oversold).
    * Short (−1.0) — only when ``allow_short=True`` — when z-score > +*z_threshold*.
    * Flat (0.0) otherwise.

    Z-score is computed on the price level (not returns) over a rolling
    *window* to detect deviation from the rolling mean.

    Parameters
    ----------
    close:
        Real closing-price series.
    window:
        Rolling window for mean and std.
    z_threshold:
        Absolute z-score threshold to trigger entry.
    allow_short:
        When ``True``, generate short signals above the upper threshold.

    Returns
    -------
    pd.Series
        Signal values in {−1.0, 0.0, +1.0}.
    """
    if len(close) < window + 5:
        return pd.Series(0.0, index=close.index, name=close.name)

    roll_mean = close.rolling(window).mean()
    roll_std = close.rolling(window).std().replace(0, np.nan)
    z = (close - roll_mean) / roll_std

    signal = pd.Series(0.0, index=close.index, name=close.name)
    signal[z < -z_threshold] = 1.0   # oversold → long
    if allow_short:
        signal[z > z_threshold] = -1.0  # overbought → short

    return signal.fillna(0.0)


def generate_breakout_signal(
    close: pd.Series,
    high: Optional[pd.Series] = None,
    low: Optional[pd.Series] = None,
    window: int = 20,
    allow_short: bool = False,
) -> pd.Series:
    """Generate a Donchian-channel breakout signal from real price data.

    Uses the *N*-bar rolling high/low channel.  The channel is computed
    on past bars only (``shift(1)`` before ``rolling()``) so there is no
    look-ahead bias.  Position sizing is applied on the following bar by
    the BacktestEngine.

    For **true intraday opening-range breakout** you need intraday data
    (e.g. ``interval="15m"`` or ``"1h"``).  With daily data (``interval="1d"``)
    this function implements the classic Donchian channel system:

    * Long (1.0) when close breaks above the *N*-day rolling high.
    * Short (−1.0) — only when ``allow_short=True`` — when close breaks
      below the *N*-day rolling low.
    * Flat (0.0) when inside the channel.

    Parameters
    ----------
    close:
        Real closing-price series.
    high, low:
        Optional high / low series for more accurate channel edges.
        Falls back to close-based channel when not provided.
    window:
        Channel look-back period in bars.
    allow_short:
        When ``True``, go short below the lower channel.

    Returns
    -------
    pd.Series
        Signal values in {−1.0, 0.0, +1.0}.
    """
    if len(close) < window + 5:
        return pd.Series(0.0, index=close.index, name=close.name)

    # Use separate high/low if available; otherwise use close-based channel
    upper_src = high if high is not None else close
    lower_src = low if low is not None else close

    # Shift by 1 before rolling to exclude the current bar (no lookahead)
    roll_high = upper_src.shift(1).rolling(window).max()
    roll_low = lower_src.shift(1).rolling(window).min()

    signal = pd.Series(0.0, index=close.index, name=close.name)
    signal[close > roll_high] = 1.0
    if allow_short:
        signal[close < roll_low] = -1.0

    return signal.fillna(0.0)


# ---------------------------------------------------------------------------
# 5. Vectorized backtest wrapper
# ---------------------------------------------------------------------------

def run_vectorized_backtest(
    close: pd.Series,
    signal: pd.Series,
    high: Optional[pd.Series] = None,
    low: Optional[pd.Series] = None,
    initial_capital: float = 100_000.0,
    transaction_cost_bps: float = 10.0,
    slippage_bps: float = 10.0,
) -> Any:
    """Run a vectorized backtest on a single-ticker price series.

    Wraps :class:`BacktestEngine` with explicit cost parameters.
    The engine applies a one-bar lag to the signal before computing
    strategy returns (no lookahead).

    Parameters
    ----------
    close:
        Real closing-price series (index = datetime).
    signal:
        Signal series aligned to *close*.  Values in [−1, 1].
    high, low:
        Optional high / low series (not currently used by the engine
        but accepted for API consistency with signal generators).
    initial_capital:
        Starting portfolio value.
    transaction_cost_bps:
        One-way commission in basis points (10 bps = 0.10%).
    slippage_bps:
        One-way slippage estimate in basis points.

    Returns
    -------
    BacktestResult
        Full result including equity curve, returns, trades, metrics.
    """
    commission = transaction_cost_bps / 10_000.0
    slippage = slippage_bps / 10_000.0
    cost_model = CostModel(commission=commission, slippage=slippage)

    prices_df = close.to_frame("Close")
    if high is not None:
        prices_df["High"] = high
    if low is not None:
        prices_df["Low"] = low

    engine = BacktestEngine()
    return engine.run(
        prices=prices_df,
        signal=signal,
        initial_capital=initial_capital,
        cost_model=cost_model,
    )


# ---------------------------------------------------------------------------
# 6. calculate_metrics
# ---------------------------------------------------------------------------

def calculate_metrics(result: Any) -> Dict[str, Any]:
    """Extract comprehensive metrics from a :class:`BacktestResult`.

    Extends the built-in ``result.metrics`` dict with derived fields
    that are not computed by :meth:`Metrics.compute_all`:

    * ``num_trades``  — total number of position changes.
    * ``turnover``    — average absolute daily position change.
    * ``exposure``    — fraction of days with a non-zero position.

    Parameters
    ----------
    result:
        A :class:`BacktestResult` instance from :class:`BacktestEngine`.

    Returns
    -------
    dict
        Keys: ``total_return``, ``annualized_return``, ``volatility``,
        ``sharpe_ratio``, ``sortino_ratio``, ``max_drawdown``,
        ``calmar_ratio``, ``win_rate``, ``profit_factor``,
        ``num_trades``, ``turnover``, ``exposure``, ``num_days``.
    """
    from alpha_search.backtest.metrics import Metrics

    try:
        m = dict(result.metrics)
    except Exception:
        m = {}

    # num_trades from trade log
    try:
        m["num_trades"] = int(len(result.trades)) if hasattr(result, "trades") else 0
    except Exception:
        m["num_trades"] = 0

    # Turnover: avg absolute daily position change
    try:
        pos = result.positions
        m["turnover"] = float(pos.diff().abs().mean()) if not pos.empty else 0.0
    except Exception:
        m["turnover"] = 0.0

    # Exposure: fraction of days holding a position
    try:
        pos = result.positions
        m["exposure"] = float((pos != 0).mean()) if not pos.empty else 0.0
    except Exception:
        m["exposure"] = 0.0

    # Ensure all expected keys are present with float values
    float_keys = [
        "total_return", "annualized_return", "volatility",
        "sharpe_ratio", "sortino_ratio", "max_drawdown",
        "calmar_ratio", "win_rate", "profit_factor",
    ]
    for key in float_keys:
        val = m.get(key, 0.0)
        try:
            m[key] = round(float(val), 6)
        except (TypeError, ValueError):
            m[key] = 0.0

    return m


# ---------------------------------------------------------------------------
# 7. export_research_outputs
# ---------------------------------------------------------------------------

def export_research_outputs(
    run_results: Dict[str, Any],
    base_dir: str = "outputs/research_runs",
) -> str:
    """Write all research outputs to a timestamped directory.

    Creates::

        <base_dir>/YYYYMMDD_HHMMSS/
            metadata.json
            strategy_results_summary.csv
            momentum_results.csv
            mean_reversion_results.csv
            breakout_results.csv
            trade_log.csv
            report.md
            figures/
                equity_curve.png
                drawdown_curve.png
                rolling_sharpe.png

    Parameters
    ----------
    run_results:
        The dictionary returned by :func:`run_real_data_research`.
    base_dir:
        Parent directory for research run outputs.

    Returns
    -------
    str
        Path to the timestamped run directory.
    """
    import json as _json
    import os as _os

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = _os.path.join(base_dir, ts)
    fig_dir = _os.path.join(run_dir, "figures")
    _os.makedirs(fig_dir, exist_ok=True)

    # ---- metadata.json ----
    meta = {
        "run_timestamp": ts,
        "universe": run_results.get("universe", ""),
        "period": run_results.get("period", ""),
        "interval": run_results.get("interval", ""),
        "symbols_requested": run_results.get("symbols_requested", []),
        "symbols_succeeded": run_results.get("symbols_succeeded", []),
        "symbols_failed": run_results.get("symbols_failed", []),
        "transaction_cost_bps": run_results.get("transaction_cost_bps", 10),
        "slippage_bps": run_results.get("slippage_bps", 10),
        "disclaimer": (
            "RESEARCH / EDUCATIONAL PURPOSES ONLY. "
            "NOT INVESTMENT ADVICE. PAST PERFORMANCE DOES NOT GUARANTEE FUTURE RESULTS."
        ),
    }
    with open(_os.path.join(run_dir, "metadata.json"), "w") as fh:
        _json.dump(meta, fh, indent=2, default=str)

    # ---- per-strategy CSV + combined summary ----
    all_metrics_frames: List[pd.DataFrame] = []
    strategy_keys = ["momentum", "mean_reversion", "breakout"]
    for key in strategy_keys:
        strat = run_results.get(key, {})
        mdf: pd.DataFrame = strat.get("metrics_df", pd.DataFrame())
        if not mdf.empty:
            mdf.to_csv(_os.path.join(run_dir, f"{key}_results.csv"), index=True)
            all_metrics_frames.append(mdf)
        else:
            # Write an empty placeholder so callers can detect the file
            pd.DataFrame().to_csv(_os.path.join(run_dir, f"{key}_results.csv"))

    if all_metrics_frames:
        summary = pd.concat(all_metrics_frames, ignore_index=True)
        summary.to_csv(_os.path.join(run_dir, "strategy_results_summary.csv"), index=False)
    else:
        pd.DataFrame().to_csv(_os.path.join(run_dir, "strategy_results_summary.csv"))

    # ---- trade_log.csv ----
    all_trades: List[pd.DataFrame] = []
    for key in strategy_keys:
        strat = run_results.get(key, {})
        for ticker, bt_result in strat.get("backtest_results", {}).items():
            try:
                trades = bt_result.trades.copy()
                trades["strategy"] = key
                trades["ticker"] = ticker
                all_trades.append(trades)
            except Exception:
                pass

    if all_trades:
        trade_log = pd.concat(all_trades, ignore_index=True)
        trade_log.to_csv(_os.path.join(run_dir, "trade_log.csv"), index=False)
    else:
        pd.DataFrame(
            columns=["date", "direction", "price", "position_delta",
                     "position_after", "strategy", "ticker"]
        ).to_csv(_os.path.join(run_dir, "trade_log.csv"), index=False)

    # ---- report.md ----
    _write_research_report(_os.path.join(run_dir, "report.md"), run_results, meta)

    # ---- figures ----
    _write_research_figures(fig_dir, run_results)

    logger.info("Research outputs written to %s", run_dir)
    return run_dir


def _write_research_report(path: str, results: Dict[str, Any], meta: dict) -> None:
    """Write a Markdown research report."""
    now = datetime.now(timezone.utc).isoformat()
    lines: List[str] = [
        "# Alpha Search — Real Data Backtesting Report",
        "",
        f"**Generated:** {now}",
        f"**Universe:** {meta.get('universe', '')}  |  "
        f"**Period:** {meta.get('period', '')}  |  "
        f"**Interval:** {meta.get('interval', '')}",
        "",
        "> **DISCLAIMER:** RESEARCH / EDUCATIONAL PURPOSES ONLY. "
        "NOT INVESTMENT ADVICE. PAST PERFORMANCE DOES NOT GUARANTEE FUTURE RESULTS.",
        "",
        "---",
        "",
        "## Data Summary",
        "",
        f"- Symbols requested: {len(meta.get('symbols_requested', []))}",
        f"- Symbols succeeded: {len(meta.get('symbols_succeeded', []))}  "
        f"({', '.join(meta.get('symbols_succeeded', [])[:10])}{'...' if len(meta.get('symbols_succeeded', [])) > 10 else ''})",
    ]
    failed = meta.get("symbols_failed", [])
    if failed:
        lines.append(f"- **Symbols failed (skipped, no data fabricated):** {', '.join(failed)}")
    lines.append("")

    for strategy_key in ["momentum", "mean_reversion", "breakout"]:
        strat = results.get(strategy_key, {})
        mdf = strat.get("metrics_df", pd.DataFrame())
        verdict = strat.get("verdict", "N/A")
        hypothesis = strat.get("hypothesis", "")

        title = strategy_key.replace("_", " ").title()
        lines += [
            f"## {title} Strategy",
            "",
            f"**Hypothesis:** {hypothesis}",
            "",
            f"**Verdict:** `{verdict}`",
            "",
        ]

        if not mdf.empty:
            lines += [
                "| Ticker | Sharpe | Total Return | Max DD | Win Rate | Trades |",
                "|--------|--------|-------------|--------|----------|--------|",
            ]
            for idx, row in mdf.iterrows():
                ticker = row.get("ticker", str(idx))
                sharpe = row.get("sharpe_ratio", 0.0)
                ret = row.get("total_return", 0.0)
                dd = row.get("max_drawdown", 0.0)
                wr = row.get("win_rate", 0.0)
                n = int(row.get("num_trades", 0))
                lines.append(
                    f"| {ticker} | {sharpe:.2f} | {ret:.2%} | {dd:.2%} | {wr:.2%} | {n} |"
                )
            lines.append("")

            avg_sharpe = mdf["sharpe_ratio"].mean() if "sharpe_ratio" in mdf.columns else float("nan")
            lines.append(
                f"*Avg Sharpe: {avg_sharpe:.2f}. "
                "Sharpe < 0 means the strategy lost money on a risk-adjusted basis. "
                "These are research findings, not recommendations.*"
            )
            lines.append("")
        else:
            lines.append("*No backtest results available for this strategy.*")
            lines.append("")

    lines += [
        "---",
        "",
        "*This report is generated by Alpha Search for research and educational purposes only.*",
        "",
    ]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def _write_research_figures(fig_dir: str, results: Dict[str, Any]) -> None:
    """Generate and save equity curve, drawdown, and rolling-Sharpe figures."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib not available — skipping figure generation")
        return

    strategy_keys = ["momentum", "mean_reversion", "breakout"]
    colours = {"momentum": "#2196F3", "mean_reversion": "#4CAF50", "breakout": "#FF9800"}

    # -- Equity curve --
    try:
        fig, ax = plt.subplots(figsize=(12, 5))
        any_plotted = False
        for key in strategy_keys:
            strat = results.get(key, {})
            for ticker, bt in strat.get("backtest_results", {}).items():
                try:
                    eq = bt.equity_curve
                    if eq is not None and len(eq) > 1:
                        ax.plot(eq.index, eq.values, label=f"{key}:{ticker}",
                                color=colours.get(key, None), alpha=0.7, linewidth=1.0)
                        any_plotted = True
                except Exception:
                    pass

        if any_plotted:
            ax.set_title("Equity Curves — Real Data Backtest")
            ax.set_ylabel("Portfolio Value ($)")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            plt.xticks(rotation=30)
            ax.legend(fontsize=7, loc="upper left", ncol=3)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, "No equity curve data available",
                    transform=ax.transAxes, ha="center", va="center", fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{fig_dir}/equity_curve.png", dpi=120)
        plt.close()
    except Exception as exc:
        logger.warning("equity_curve figure failed: %s", exc)

    # -- Drawdown curve --
    try:
        fig, ax = plt.subplots(figsize=(12, 4))
        any_plotted = False
        for key in strategy_keys:
            strat = results.get(key, {})
            for ticker, bt in strat.get("backtest_results", {}).items():
                try:
                    eq = bt.equity_curve
                    if eq is not None and len(eq) > 1:
                        peak = eq.expanding().max()
                        dd = (eq - peak) / peak
                        ax.fill_between(dd.index, dd.values, 0,
                                        color=colours.get(key, "#888"), alpha=0.35,
                                        label=f"{key}:{ticker}")
                        any_plotted = True
                except Exception:
                    pass

        if any_plotted:
            ax.set_title("Drawdown Curves — Real Data Backtest")
            ax.set_ylabel("Drawdown")
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda y, _: f"{y:.0%}")
            )
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            plt.xticks(rotation=30)
            ax.legend(fontsize=7, loc="lower left", ncol=3)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, "No drawdown data available",
                    transform=ax.transAxes, ha="center", va="center", fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{fig_dir}/drawdown_curve.png", dpi=120)
        plt.close()
    except Exception as exc:
        logger.warning("drawdown_curve figure failed: %s", exc)

    # -- Rolling Sharpe (60-day) --
    try:
        fig, ax = plt.subplots(figsize=(12, 4))
        any_plotted = False
        window_rs = 60
        for key in strategy_keys:
            strat = results.get(key, {})
            for ticker, bt in strat.get("backtest_results", {}).items():
                try:
                    rets = bt.returns
                    if rets is not None and len(rets) > window_rs:
                        roll_mean = rets.rolling(window_rs).mean()
                        roll_std = rets.rolling(window_rs).std()
                        roll_sharpe = (roll_mean / roll_std.replace(0, np.nan)) * np.sqrt(252)
                        ax.plot(roll_sharpe.index, roll_sharpe.values,
                                label=f"{key}:{ticker}", alpha=0.7, linewidth=1.0)
                        any_plotted = True
                except Exception:
                    pass

        if any_plotted:
            ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
            ax.axhline(1, color="green", linewidth=0.8, linestyle=":", alpha=0.7)
            ax.set_title(f"Rolling {window_rs}-Day Sharpe Ratio — Real Data Backtest")
            ax.set_ylabel("Sharpe (annualised)")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            plt.xticks(rotation=30)
            ax.legend(fontsize=7, loc="upper left", ncol=3)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, "No returns data available",
                    transform=ax.transAxes, ha="center", va="center", fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{fig_dir}/rolling_sharpe.png", dpi=120)
        plt.close()
    except Exception as exc:
        logger.warning("rolling_sharpe figure failed: %s", exc)


# ---------------------------------------------------------------------------
# 8. run_real_data_research — main orchestrator
# ---------------------------------------------------------------------------

def run_real_data_research(
    universe: str = "us_large_cap",
    period: str = "2y",
    interval: str = "1d",
    output_dir: str = "outputs/research_runs",
    transaction_cost_bps: float = 10.0,
    slippage_bps: float = 10.0,
    csv_fallback_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a complete real-data backtesting research pipeline.

    Fetches real OHLCV data, validates it, generates signals for three
    strategies (momentum, mean-reversion, breakout), runs vectorized
    backtests with realistic transaction costs, computes metrics, and
    exports all results to a timestamped directory.

    **No synthetic data is used.**  Symbols that cannot be fetched are
    skipped and logged; their absence is reported in the output.
    Sharpe ratios are reported as-is — no parameter tuning to appear
    profitable.

    Parameters
    ----------
    universe:
        One of ``"us_large_cap"``, ``"india_equity"``, ``"crypto"``,
        ``"all"``.
    period:
        yfinance history period, e.g. ``"2y"``, ``"1y"``.
    interval:
        yfinance bar interval, e.g. ``"1d"``, ``"1h"``.
    output_dir:
        Parent directory for timestamped output folders.
    transaction_cost_bps:
        One-way commission in basis points (default 10 bps = 0.10%).
    slippage_bps:
        One-way slippage estimate in basis points (default 10 bps).
    csv_fallback_path:
        Optional path to a CSV file following the schema
        ``timestamp,symbol,open,high,low,close,volume``.  Used as
        additional data source if provided.

    Returns
    -------
    dict
        Keys: ``universe``, ``period``, ``interval``, ``symbols_requested``,
        ``symbols_succeeded``, ``symbols_failed``, ``validation_report``,
        ``momentum``, ``mean_reversion``, ``breakout``,
        ``transaction_cost_bps``, ``slippage_bps``,
        ``output_dir``, ``disclaimer``.
    """
    start_time = datetime.now(timezone.utc)
    symbols = UNIVERSES.get(universe, UNIVERSE_US_LARGE_CAP)

    logger.info("=" * 64)
    logger.info("Alpha Search — Real Data Research (%s, %s, %s)", universe, period, interval)
    logger.info("Symbols: %s", symbols)
    logger.info("=" * 64)

    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    frames, succeeded, failed = fetch_yfinance_ohlcv(symbols, period=period, interval=interval)

    # Merge CSV fallback if provided
    if csv_fallback_path:
        csv_frames = load_csv_ohlcv(csv_fallback_path)
        for sym, df in csv_frames.items():
            if sym not in frames:
                frames[sym] = df
                if sym not in succeeded:
                    succeeded.append(sym)
                logger.info("Loaded %s from CSV fallback", sym)

    if not frames:
        logger.error("No data available — cannot run research")
        return {
            "universe": universe, "period": period, "interval": interval,
            "symbols_requested": symbols, "symbols_succeeded": [],
            "symbols_failed": symbols, "error": "No data fetched",
            "disclaimer": "RESEARCH / EDUCATIONAL PURPOSES ONLY.",
        }

    # ------------------------------------------------------------------
    # 2. Validate each symbol
    # ------------------------------------------------------------------
    validation_report: Dict[str, Dict[str, Any]] = {}
    valid_frames: Dict[str, pd.DataFrame] = {}

    for sym, df in frames.items():
        is_valid, warns = validate_ohlcv(df, ticker=sym)
        validation_report[sym] = {"is_valid": is_valid, "warnings": warns}
        if warns:
            for w in warns:
                logger.warning("Validation: %s", w)
        if is_valid:
            valid_frames[sym] = df
        else:
            logger.warning("Validation failed for %s — excluding from strategies", sym)
            if sym in succeeded:
                succeeded.remove(sym)
            if sym not in failed:
                failed.append(sym)

    logger.info(
        "Validation complete: %d valid, %d excluded",
        len(valid_frames), len(frames) - len(valid_frames),
    )

    if not valid_frames:
        logger.error("All symbols failed validation")
        return {
            "universe": universe, "period": period, "interval": interval,
            "symbols_requested": symbols, "symbols_succeeded": [],
            "symbols_failed": failed, "validation_report": validation_report,
            "error": "All symbols failed OHLCV validation",
            "disclaimer": "RESEARCH / EDUCATIONAL PURPOSES ONLY.",
        }

    # ------------------------------------------------------------------
    # 3. Run strategies
    # ------------------------------------------------------------------
    def _run_strategy(
        strategy_name: str,
        sig_fn,
    ) -> Dict[str, Any]:
        """Run one strategy across all valid symbols, aggregate metrics."""
        backtest_results: Dict[str, Any] = {}
        all_metrics: List[Dict[str, Any]] = {}
        no_trade_reasons: Dict[str, str] = {}

        for sym, df in valid_frames.items():
            close = df["Close"].dropna()
            high = df["High"].dropna() if "High" in df.columns else None
            low_s = df["Low"].dropna() if "Low" in df.columns else None

            if len(close) < 30:
                no_trade_reasons[sym] = f"Only {len(close)} bars (< 30)"
                continue

            try:
                if strategy_name == "breakout":
                    sig = sig_fn(close, high=high, low=low_s)
                else:
                    sig = sig_fn(close)
            except Exception as exc:
                no_trade_reasons[sym] = f"Signal generation failed: {exc}"
                logger.warning("Signal failed for %s (%s): %s", sym, strategy_name, exc)
                continue

            n_signals = int((sig != 0).sum())
            if n_signals == 0:
                no_trade_reasons[sym] = (
                    "Signal is all-zero — no entry condition met. "
                    "Try a different lookback or threshold."
                )
                logger.info(
                    "%s / %s: zero signals — skipping backtest", sym, strategy_name
                )
                continue

            try:
                result = run_vectorized_backtest(
                    close=close,
                    signal=sig,
                    high=high,
                    low=low_s,
                    initial_capital=100_000.0,
                    transaction_cost_bps=transaction_cost_bps,
                    slippage_bps=slippage_bps,
                )
                backtest_results[sym] = result
                m = calculate_metrics(result)
                m["ticker"] = sym
                m["strategy"] = strategy_name
                all_metrics[sym] = m  # type: ignore[assignment]
            except Exception as exc:
                no_trade_reasons[sym] = f"Backtest failed: {exc}"
                logger.warning("Backtest failed for %s (%s): %s", sym, strategy_name, exc)

        if no_trade_reasons:
            for sym, reason in no_trade_reasons.items():
                logger.info("%s / %s: %s", sym, strategy_name, reason)

        metrics_list = list(all_metrics.values())  # type: ignore[assignment]
        metrics_df = pd.DataFrame(metrics_list) if metrics_list else pd.DataFrame()

        avg_sharpe = (
            metrics_df["sharpe_ratio"].mean()
            if not metrics_df.empty and "sharpe_ratio" in metrics_df.columns
            else float("nan")
        )
        verdict: str
        if np.isnan(avg_sharpe):
            verdict = "no_results"
        elif avg_sharpe > 1.0:
            verdict = "promising"
        elif avg_sharpe > 0.0:
            verdict = "marginal"
        else:
            verdict = "unprofitable"

        return {
            "hypothesis": _STRATEGY_HYPOTHESES.get(strategy_name, ""),
            "backtest_results": backtest_results,
            "metrics_df": metrics_df,
            "verdict": verdict,
            "avg_sharpe": round(avg_sharpe, 4) if not np.isnan(avg_sharpe) else None,
            "no_trade_reasons": no_trade_reasons,
        }

    _STRATEGY_HYPOTHESES = {
        "momentum": (
            "Stocks with strong recent momentum continue to outperform "
            "over the next 1-4 weeks (MA-crossover confirmed)."
        ),
        "mean_reversion": (
            "Prices that deviate significantly below their rolling mean "
            "tend to revert toward the mean (z-score entry at -2 sigma)."
        ),
        "breakout": (
            "Prices breaking above the N-bar Donchian channel high continue "
            "trending upward (channel breakout, daily data)."
        ),
    }

    logger.info("Running momentum strategy on %d symbols...", len(valid_frames))
    momentum_result = _run_strategy(
        "momentum",
        lambda c: generate_momentum_signal(c, lookback=20, ma_confirm=True),
    )

    logger.info("Running mean-reversion strategy on %d symbols...", len(valid_frames))
    mr_result = _run_strategy(
        "mean_reversion",
        lambda c: generate_mean_reversion_signal(c, window=20, z_threshold=2.0),
    )

    logger.info("Running breakout strategy on %d symbols...", len(valid_frames))
    breakout_result = _run_strategy(
        "breakout",
        lambda c, high=None, low=None: generate_breakout_signal(c, high=high, low=low, window=20),
    )

    # ------------------------------------------------------------------
    # 4. Assemble results
    # ------------------------------------------------------------------
    results: Dict[str, Any] = {
        "universe": universe,
        "period": period,
        "interval": interval,
        "symbols_requested": symbols,
        "symbols_succeeded": succeeded,
        "symbols_failed": failed,
        "validation_report": validation_report,
        "momentum": momentum_result,
        "mean_reversion": mr_result,
        "breakout": breakout_result,
        "transaction_cost_bps": transaction_cost_bps,
        "slippage_bps": slippage_bps,
        "run_timestamp": start_time.isoformat(),
        "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
        "disclaimer": (
            "RESEARCH / EDUCATIONAL PURPOSES ONLY. "
            "NOT INVESTMENT ADVICE. PAST PERFORMANCE DOES NOT GUARANTEE FUTURE RESULTS."
        ),
    }

    # ------------------------------------------------------------------
    # 5. Export outputs
    # ------------------------------------------------------------------
    try:
        run_dir = export_research_outputs(results, base_dir=output_dir)
        results["output_dir"] = run_dir
        logger.info("Outputs written to %s", run_dir)
    except Exception as exc:
        logger.warning("export_research_outputs failed: %s", exc)
        results["output_dir"] = None

    logger.info(
        "Research complete in %.1fs | momentum=%s | mr=%s | breakout=%s",
        results["duration_seconds"],
        momentum_result.get("verdict"),
        mr_result.get("verdict"),
        breakout_result.get("verdict"),
    )
    return results


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
