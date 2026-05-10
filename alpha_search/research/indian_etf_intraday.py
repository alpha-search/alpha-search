"""Indian ETF Intraday Momentum Breakout Strategy — Full Research Pipeline.

This module implements a complete end-to-end research pipeline for a noise-area
breakout strategy applied to Indian-listed ETFs (Nippon India ETF series):

    * NIFTYBEES.NS  – Nifty 50 ETF
    * BANKBEES.NS   – Nifty Bank ETF
    * ITBEES.NS     – Nifty IT ETF
    * JUNIORBEES.NS – Nifty Next 50 ETF

The pipeline fetches real OHLCV data from yfinance, computes noise-area
volatility bands, generates long/short breakout signals, backtests each ETF
with volatility-targeted sizing, constructs equal-weight / inverse-volatility /
risk-parity portfolios, persists results to the Alpha Search memory layer,
and generates Markdown + CSV + PNG reports.

Disclaimer
----------
This is research / educational code only.  It is not financial advice and
should not be used for live trading without independent validation.

Example::

    from alpha_search.research.indian_etf_intraday import run_full_pipeline
    results = run_full_pipeline(output_dir="reports/indian_etf")
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.backtest.metrics import Metrics
from alpha_search.memory.journal import AgentJournal
from alpha_search.memory.models import MemoryRecord, StrategyMemory
from alpha_search.memory.store import MemoryStore
from alpha_search.signals.noise_breakout import (
    NoiseArea,
    compute_noise_area,
    generate_breakout_signals,
    volatility_targeted_position,
)

# Lazy import — plotting is optional and not available in CI
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    plt = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

INDIAN_ETFS: List[str] = ["NIFTYBEES.NS", "BANKBEES.NS", "ITBEES.NS", "JUNIORBEES.NS"]
"""Indian ETF tickers traded on the NSE (.NS suffix for yfinance)."""

LOOKBACK_WINDOWS: List[int] = [20, 45, 90]
"""Noise-area lookback windows to test (trading days)."""

PORTFOLIO_METHODS: List[str] = ["equal_weight", "inverse_volatility", "risk_parity"]
"""Portfolio construction methods."""

TRADING_DAYS_PER_YEAR = 252


# ===========================================================================
# 1. Data fetching
# ===========================================================================


def fetch_indian_etf_data(
    etfs: Optional[List[str]] = None,
    period: str = "2y",
) -> pd.DataFrame:
    """Fetch real Indian ETF OHLCV data from yfinance.

    Downloads historical data for each ETF and assembles a MultiIndex
    DataFrame with (ticker, field) column levels matching the Alpha Search
    convention.

    Args:
        etfs: List of ETF ticker symbols.  Defaults to :data:`INDIAN_ETFS`.
        period: yfinance period string (e.g. ``"2y"``, ``"1y"``).

    Returns:
        MultiIndex DataFrame with columns ``(ticker, field)`` where
        *field* is one of ``['Open', 'High', 'Low', 'Close', 'Volume']``.
        Index is a DatetimeIndex.

    Raises:
        RuntimeError: If yfinance is unavailable or *all* downloads fail.
        ValueError: If the resulting DataFrame is empty.
    """
    etfs = etfs or INDIAN_ETFS.copy()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is required to fetch Indian ETF data. "
            "Install it with: pip install yfinance"
        ) from exc

    logger.info("Fetching Indian ETF data for %s (period=%s)", etfs, period)

    all_data: Dict[str, pd.DataFrame] = {}
    failures: List[str] = []

    for ticker in etfs:
        try:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
            if df is None or df.empty:
                logger.warning("No data returned for %s", ticker)
                failures.append(ticker)
                continue

            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            # Normalise column names
            df.columns = [c.title() for c in df.columns]

            # Ensure required columns exist
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            for col in required_cols:
                if col not in df.columns:
                    if col == "Volume":
                        df[col] = 0
                    else:
                        logger.warning("Missing column %s for %s — skipping", col, ticker)
                        failures.append(ticker)
                        break
            else:
                all_data[ticker] = df[required_cols].copy()

            # Rate-limit sleep
            time.sleep(2)

        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            failures.append(ticker)

    if not all_data:
        raise RuntimeError(
            f"All ETF data downloads failed.  Failures: {failures}.  "
            "This may be due to yfinance rate limiting from a shared IP."
        )

    if failures:
        logger.warning(
            "Partial failures — %d/%d tickers fetched: %s",
            len(all_data),
            len(etfs),
            sorted(all_data.keys()),
        )

    # Build MultiIndex DataFrame (ticker, field)
    frames: List[pd.DataFrame] = []
    for ticker, df in all_data.items():
        cols = pd.MultiIndex.from_product(
            [[ticker], ["Open", "High", "Low", "Close", "Volume"]]
        )
        sub = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        sub.columns = cols
        frames.append(sub)

    combined = pd.concat(frames, axis=1)
    combined = combined.sort_index(axis=1, level=[0, 1])

    if combined.empty:
        raise ValueError("Combined ETF DataFrame is empty after construction.")

    logger.info(
        "MultiIndex DataFrame shape: %s, tickers: %s",
        combined.shape,
        list(combined.columns.get_level_values(0).unique()),
    )
    return combined


# ===========================================================================
# 2. Individual ETF backtest
# ===========================================================================


def run_noise_breakout_backtest(
    prices: pd.DataFrame,
    etf: str,
    lookback: int = 20,
    atr_multiplier: float = 1.5,
    target_vol: float = 0.10,
) -> Dict[str, Any]:
    """Run a noise-area breakout backtest on a single ETF.

    Uses :func:`compute_noise_area` and :func:`generate_breakout_signals`
    together with :func:`volatility_targeted_position` for sizing and the
    :class:`BacktestEngine` with a :class:`CostModel`.

    Args:
        prices: OHLCV DataFrame for a *single* ticker.  Must contain
            ``'Open'``, ``'High'``, ``'Low'``, ``'Close'``, ``'Volume'``
            columns.
        etf: Ticker name for logging / result labelling.
        lookback: Rolling window for the noise-area bands.
        atr_multiplier: Multiplier applied to ATR for band width.
        target_vol: Annualised volatility target for position sizing
            (default 10 %%).

    Returns:
        Dict with keys:

        * ``"etf"`` — ticker symbol
        * ``"lookback"`` — lookback window used
        * ``"backtest_result"`` — :class:`BacktestResult` instance
        * ``"equity_curve"`` — pd.Series equity curve
        * ``"signal"`` — pd.Series of final position signals
        * ``"noise_area"`` — :class:`NoiseArea` instance
        * ``"metrics"`` — dict of performance metrics
        * ``"trades"`` — DataFrame of executed trades
    """
    logger.info("Backtesting %s with lookback=%d", etf, lookback)

    # Ensure we have the required columns
    close = prices["Close"].copy()

    # Compute noise area — requires OHLC DataFrame
    noise: NoiseArea = compute_noise_area(
        prices,
        lookback=lookback,
        atr_multiplier=atr_multiplier,
    )

    # Generate breakout signals — returns DataFrame with combined_signal
    raw_signals: pd.DataFrame = generate_breakout_signals(noise, prices)
    combined_signal = raw_signals["combined_signal"]

    # Volatility-targeted position sizing
    returns = close.pct_change().fillna(0.0)
    position = volatility_targeted_position(
        signal=combined_signal,
        returns=returns,
        target_vol=target_vol,
        vol_lookback=min(60, lookback * 2),
    )

    # Fill NaN positions with 0
    position = position.fillna(0.0)
    position.name = f"{etf}_position"

    # Run backtest
    engine = BacktestEngine()
    cost_model = CostModel(commission=0.001, slippage=0.001)

    result = engine.run(
        prices=prices,
        signal=position,
        initial_capital=100_000.0,
        cost_model=cost_model,
    )

    return {
        "etf": etf,
        "lookback": lookback,
        "backtest_result": result,
        "equity_curve": result.equity_curve,
        "signal": position,
        "noise_area": noise,
        "metrics": result.metrics,
        "trades": result.trades,
    }


# ===========================================================================
# 3. Portfolio construction
# ===========================================================================


def _compute_inverse_volatility_weights(
    individual_returns: Dict[str, pd.Series],
) -> Dict[str, float]:
    """Compute inverse-volatility portfolio weights.

    Weights are proportional to 1 / annualised volatility.
    """
    inv_vols: Dict[str, float] = {}
    for ticker, rets in individual_returns.items():
        vol = rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        if vol > 0 and not np.isnan(vol):
            inv_vols[ticker] = 1.0 / vol
        else:
            inv_vols[ticker] = 0.0

    total = sum(inv_vols.values())
    if total == 0:
        n = len(inv_vols)
        return {t: 1.0 / n for t in inv_vols}
    return {t: v / total for t, v in inv_vols.items()}


def _compute_risk_parity_weights(
    individual_returns: Dict[str, pd.Series],
    max_iter: int = 10,
) -> Dict[str, float]:
    """Compute risk-parity portfolio weights via iterative budget equalisation."""
    tickers = list(individual_returns.keys())
    n = len(tickers)

    df_rets = pd.DataFrame(individual_returns).dropna()
    if df_rets.empty:
        return {t: 1.0 / n for t in tickers}

    weights = np.ones(n) / n
    cov = df_rets.cov().values * TRADING_DAYS_PER_YEAR

    for _ in range(max_iter):
        port_vol = np.sqrt(weights @ cov @ weights)
        if port_vol == 0:
            break
        mrc = (cov @ weights) / port_vol
        rc = weights * mrc
        avg_rc = rc.mean()
        adj = np.where(rc > avg_rc, -0.1, 0.1)
        weights = weights + adj
        weights = np.clip(weights, 0.01, 1.0)
        weights = weights / weights.sum()

    return {t: float(w) for t, w in zip(tickers, weights)}


def run_portfolio_backtest(
    individual_results: Dict[str, Dict[str, Any]],
    method: str = "equal_weight",
) -> Dict[str, Any]:
    """Combine individual ETF backtests into a portfolio.

    Args:
        individual_results: Mapping from ticker symbol to the dict
            returned by :func:`run_noise_breakout_backtest`.
        method: Portfolio construction method — one of
            ``"equal_weight"``, ``"inverse_volatility"``, ``"risk_parity"``.

    Returns:
        Dict with keys:

        * ``"method"`` — construction method used
        * ``"weights"`` — dict of ticker -> weight
        * ``"portfolio_returns"`` — daily portfolio return series
        * ``"equity_curve"`` — cumulative equity curve
        * ``"metrics"`` — performance metrics dict
    """
    logger.info("Constructing %s portfolio", method)

    individual_returns: Dict[str, pd.Series] = {}
    for ticker, res in individual_results.items():
        bt = res["backtest_result"]
        individual_returns[ticker] = bt.returns

    df_rets = pd.DataFrame(individual_returns).dropna(how="all")
    df_rets = df_rets.fillna(0.0)

    tickers = list(df_rets.columns)
    n = len(tickers)

    if n == 0:
        raise ValueError("No individual returns available for portfolio construction.")

    if method == "equal_weight":
        weights = {t: 1.0 / n for t in tickers}
    elif method == "inverse_volatility":
        weights = _compute_inverse_volatility_weights({t: df_rets[t] for t in tickers})
    elif method == "risk_parity":
        weights = _compute_risk_parity_weights({t: df_rets[t] for t in tickers})
    else:
        raise ValueError(f"Unknown portfolio method: {method}")

    w_arr = np.array([weights.get(t, 0.0) for t in tickers])
    portfolio_returns = (df_rets * w_arr).sum(axis=1)
    portfolio_returns.name = f"portfolio_{method}"

    cumulative = (1.0 + portfolio_returns).cumprod()
    equity = 100_000.0 * cumulative
    equity.name = f"equity_{method}"

    metrics = Metrics.compute_all(portfolio_returns, equity)

    return {
        "method": method,
        "weights": weights,
        "portfolio_returns": portfolio_returns,
        "equity_curve": equity,
        "metrics": metrics,
    }


# ===========================================================================
# 4. Full pipeline orchestration
# ===========================================================================


def run_full_pipeline(
    output_dir: str = "reports/indian_etf",
) -> Dict[str, Any]:
    """Run the complete Indian ETF intraday breakout research pipeline.

    Steps:

        1. Fetch real OHLCV data for :data:`INDIAN_ETFS` via yfinance.
        2. For each lookback (20, 45, 90): backtest each ETF individually.
        3. For each portfolio method (equal_weight, inverse_volatility,
           risk_parity): construct and evaluate portfolio.
        4. Store all results to the Alpha Search memory layer.
        5. Generate reports (Markdown, CSV, PNG).

    Args:
        output_dir: Directory for output reports and plots.

    Returns:
        Nested results dict with structure::

            {
                "data": MultiIndex DataFrame of prices,
                "individual_results": {
                    (etf, lookback): { backtest dict },
                    ...
                },
                "portfolio_results": {
                    lookback: {
                        "equal_weight": { portfolio dict },
                        "inverse_volatility": { portfolio dict },
                        "risk_parity": { portfolio dict },
                    },
                    ...
                },
                "best_params": { "best_lookback": int, "best_etf": str, ... },
                "output_dir": str,
            }
    """
    logger.info("=" * 60)
    logger.info("Indian ETF Intraday Breakout Pipeline — starting")
    logger.info("=" * 60)

    results: Dict[str, Any] = {
        "data": None,
        "individual_results": {},
        "portfolio_results": {},
        "best_params": {},
        "output_dir": output_dir,
    }

    # ------------------------------------------------------------------
    # Step 1: Fetch data
    # ------------------------------------------------------------------
    try:
        data = fetch_indian_etf_data()
        results["data"] = data
    except Exception as exc:
        logger.error("Data fetch failed: %s", exc)
        raise

    tickers = list(data.columns.get_level_values(0).unique())
    logger.info("Processing tickers: %s", tickers)

    # ------------------------------------------------------------------
    # Step 2: Backtest each ETF at each lookback
    # ------------------------------------------------------------------
    all_sharpe_records: List[Dict[str, Any]] = []

    for lookback in LOOKBACK_WINDOWS:
        logger.info("--- Lookback window: %d days ---", lookback)
        lb_results: Dict[str, Dict[str, Any]] = {}

        for ticker in tickers:
            try:
                # Extract single-ticker OHLCV from MultiIndex
                ticker_df = data[ticker].copy()

                # Ensure all required columns exist
                for col in ["Open", "High", "Low", "Close", "Volume"]:
                    if col not in ticker_df.columns:
                        ticker_df[col] = (
                            ticker_df["Close"] if col != "Volume" else 0
                        )

                bt_result = run_noise_breakout_backtest(
                    prices=ticker_df,
                    etf=ticker,
                    lookback=lookback,
                )
                lb_results[ticker] = bt_result
                results["individual_results"][(ticker, lookback)] = bt_result

                sharpe = bt_result["metrics"].get("sharpe_ratio", 0.0)
                all_sharpe_records.append({
                    "etf": ticker,
                    "lookback": lookback,
                    "sharpe_ratio": sharpe,
                    "total_return": bt_result["metrics"].get("total_return", 0.0),
                    "max_drawdown": bt_result["metrics"].get("max_drawdown", 0.0),
                    "win_rate": bt_result["metrics"].get("win_rate", 0.0),
                })

            except Exception as exc:
                logger.warning(
                    "Backtest failed for %s (lb=%d): %s", ticker, lookback, exc
                )
                results["individual_results"][(ticker, lookback)] = {
                    "etf": ticker,
                    "lookback": lookback,
                    "error": str(exc),
                    "metrics": {},
                }

        # ------------------------------------------------------------------
        # Step 3: Portfolio construction for this lookback
        # ------------------------------------------------------------------
        valid_results = {
            k: v
            for k, v in lb_results.items()
            if "error" not in v and v.get("metrics")
        }

        if len(valid_results) >= 2:
            portfolios: Dict[str, Dict[str, Any]] = {}
            for method in PORTFOLIO_METHODS:
                try:
                    p = run_portfolio_backtest(valid_results, method=method)
                    portfolios[method] = p
                except Exception as exc:
                    logger.warning(
                        "Portfolio %s failed for lb=%d: %s", method, lookback, exc
                    )

            results["portfolio_results"][lookback] = portfolios

            for method, p in portfolios.items():
                all_sharpe_records.append({
                    "etf": f"PORTFOLIO_{method}",
                    "lookback": lookback,
                    "sharpe_ratio": p["metrics"].get("sharpe_ratio", 0.0),
                    "total_return": p["metrics"].get("total_return", 0.0),
                    "max_drawdown": p["metrics"].get("max_drawdown", 0.0),
                    "win_rate": p["metrics"].get("win_rate", 0.0),
                })

    # ------------------------------------------------------------------
    # Best parameters
    # ------------------------------------------------------------------
    valid_sharpe = [
        r
        for r in all_sharpe_records
        if not r["etf"].startswith("PORTFOLIO_") and r.get("sharpe_ratio") is not None
    ]
    if valid_sharpe:
        best = max(valid_sharpe, key=lambda x: x["sharpe_ratio"])
        results["best_params"] = {
            "best_lookback": best["lookback"],
            "best_etf": best["etf"],
            "best_sharpe": best["sharpe_ratio"],
            "best_total_return": best["total_return"],
            "best_max_drawdown": best["max_drawdown"],
        }
        logger.info(
            "Best params: %s (lb=%d, sharpe=%.3f)",
            best["etf"],
            best["lookback"],
            best["sharpe_ratio"],
        )

    # ------------------------------------------------------------------
    # Step 4: Store to memory
    # ------------------------------------------------------------------
    try:
        store_results_to_memory(results)
    except Exception as exc:
        logger.warning("Memory storage failed (non-critical): %s", exc)

    # ------------------------------------------------------------------
    # Step 5: Generate reports
    # ------------------------------------------------------------------
    try:
        generate_report(results, output_dir)
    except Exception as exc:
        logger.warning("Report generation failed (non-critical): %s", exc)

    logger.info("Pipeline complete.  Output: %s", output_dir)
    return results


# ===========================================================================
# 5. Report generation
# ===========================================================================


def _setup_matplotlib() -> None:
    """Configure matplotlib for headless PNG generation."""
    plt.rcParams.update({
        "figure.dpi": 150,
        "figure.figsize": (12, 6),
        "axes.grid": True,
        "grid.alpha": 0.3,
    })


def generate_report(
    results: Dict[str, Any],
    output_dir: str = "reports/indian_etf",
) -> None:
    """Generate full research report: Markdown, CSV, and PNG visualisations.

    Files written to *output_dir*:

        * ``report.md`` — narrative summary with metrics table
        * ``strategy_metrics.csv`` — all backtest metrics
        * ``trade_log.csv`` — all trades across ETFs
        * ``parameter_results.csv`` — parameter-sensitivity grid
        * ``equity_curve.png`` — equity curves for best lookback
        * ``drawdown.png`` — drawdown charts
        * ``sharpe_by_etf.png`` — Sharpe ratio comparison
        * ``parameter_sensitivity.png`` — heatmap of Sharpe vs lookback

    Args:
        results: Results dict from :func:`run_full_pipeline`.
        output_dir: Target directory for report files.
    """
    os.makedirs(output_dir, exist_ok=True)
    _setup_matplotlib()

    individual = results.get("individual_results", {})
    portfolios = results.get("portfolio_results", {})
    best_params = results.get("best_params", {})

    # ------------------------------------------------------------------
    # 5a. strategy_metrics.csv
    # ------------------------------------------------------------------
    metrics_rows: List[Dict[str, Any]] = []
    for key, res in individual.items():
        if isinstance(key, tuple):
            ticker, lb = key
        else:
            ticker = res.get("etf", "unknown")
            lb = res.get("lookback", 0)
        if "error" in res or not res.get("metrics"):
            continue
        m = res["metrics"].copy()
        m["etf"] = ticker
        m["lookback"] = lb
        m["n_trades"] = len(res.get("trades", []))
        metrics_rows.append(m)

    for lb, port_dict in portfolios.items():
        for method, p in port_dict.items():
            m = p["metrics"].copy()
            m["etf"] = f"PORTFOLIO_{method}"
            m["lookback"] = lb
            m["n_trades"] = 0
            metrics_rows.append(m)

    if metrics_rows:
        df_metrics = pd.DataFrame(metrics_rows)
        df_metrics.to_csv(
            os.path.join(output_dir, "strategy_metrics.csv"), index=False
        )

    # ------------------------------------------------------------------
    # 5b. trade_log.csv
    # ------------------------------------------------------------------
    trade_frames: List[pd.DataFrame] = []
    for key, res in individual.items():
        if isinstance(key, tuple):
            ticker, lb = key
        else:
            ticker = res.get("etf", "unknown")
            lb = res.get("lookback", 0)
        trades = res.get("trades")
        if trades is not None and not trades.empty:
            t = trades.copy()
            t["etf"] = ticker
            t["lookback"] = lb
            trade_frames.append(t)
    if trade_frames:
        pd.concat(trade_frames, ignore_index=True).to_csv(
            os.path.join(output_dir, "trade_log.csv"), index=False
        )
    else:
        pd.DataFrame(
            columns=[
                "date",
                "direction",
                "price",
                "position_delta",
                "position_after",
                "etf",
                "lookback",
            ]
        ).to_csv(os.path.join(output_dir, "trade_log.csv"), index=False)

    # ------------------------------------------------------------------
    # 5c. parameter_results.csv
    # ------------------------------------------------------------------
    param_rows: List[Dict[str, Any]] = []
    for key, res in individual.items():
        if isinstance(key, tuple):
            ticker, lb = key
        else:
            ticker = res.get("etf", "unknown")
            lb = res.get("lookback", 0)
        if "error" in res:
            param_rows.append({
                "etf": ticker,
                "lookback": lb,
                "status": "FAILED",
                "sharpe_ratio": np.nan,
                "total_return": np.nan,
                "max_drawdown": np.nan,
                "win_rate": np.nan,
            })
        elif res.get("metrics"):
            param_rows.append({
                "etf": ticker,
                "lookback": lb,
                "status": "OK",
                "sharpe_ratio": res["metrics"].get("sharpe_ratio", np.nan),
                "total_return": res["metrics"].get("total_return", np.nan),
                "max_drawdown": res["metrics"].get("max_drawdown", np.nan),
                "win_rate": res["metrics"].get("win_rate", np.nan),
            })
    if param_rows:
        pd.DataFrame(param_rows).to_csv(
            os.path.join(output_dir, "parameter_results.csv"), index=False
        )

    # ------------------------------------------------------------------
    # 5d. PNG visualisations
    # ------------------------------------------------------------------

    # --- equity_curve.png ---
    fig, ax = plt.subplots(figsize=(12, 6))
    best_lb = best_params.get("best_lookback", 20)
    plotted = 0
    for key, res in individual.items():
        if isinstance(key, tuple) and key[1] == best_lb and "equity_curve" in res:
            eq = res["equity_curve"]
            if not eq.empty:
                ax.plot(eq, label=key[0], alpha=0.8)
                plotted += 1
    if plotted > 0:
        ax.set_title(f"Equity Curves (lookback={best_lb})")
        ax.set_xlabel("Date")
        ax.set_ylabel("Portfolio Value (INR)")
        ax.legend()
        fig.savefig(
            os.path.join(output_dir, "equity_curve.png"),
            dpi=150,
            bbox_inches="tight",
        )
    plt.close(fig)

    # --- drawdown.png ---
    fig, ax = plt.subplots(figsize=(12, 6))
    plotted = 0
    for key, res in individual.items():
        if isinstance(key, tuple) and key[1] == best_lb and "equity_curve" in res:
            eq = res["equity_curve"]
            if not eq.empty:
                cummax = eq.cummax()
                dd = (eq - cummax) / cummax
                ax.plot(dd, label=key[0], alpha=0.8)
                plotted += 1
    if plotted > 0:
        ax.set_title(f"Drawdown (lookback={best_lb})")
        ax.set_xlabel("Date")
        ax.set_ylabel("Drawdown")
        ax.legend()
        fig.savefig(
            os.path.join(output_dir, "drawdown.png"),
            dpi=150,
            bbox_inches="tight",
        )
    plt.close(fig)

    # --- sharpe_by_etf.png ---
    fig, ax = plt.subplots(figsize=(10, 6))
    sharpe_data: Dict[int, List[float]] = {}
    for lb in LOOKBACK_WINDOWS:
        sharpe_data[lb] = []
        for ticker in INDIAN_ETFS:
            key = (ticker, lb)
            if key in individual and individual[key].get("metrics"):
                sharpe_data[lb].append(
                    individual[key]["metrics"].get("sharpe_ratio", 0.0)
                )
            else:
                sharpe_data[lb].append(np.nan)

    x = np.arange(len(INDIAN_ETFS))
    width = 0.25
    for i, lb in enumerate(LOOKBACK_WINDOWS):
        offset = (i - 1) * width
        vals = [v if not np.isnan(v) else 0.0 for v in sharpe_data[lb]]
        ax.bar(x + offset, vals, width, label=f"lb={lb}")

    ax.set_xticks(x)
    ax.set_xticklabels(INDIAN_ETFS, rotation=15)
    ax.set_ylabel("Sharpe Ratio")
    ax.set_title("Sharpe Ratio by ETF and Lookback Window")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend()
    fig.savefig(
        os.path.join(output_dir, "sharpe_by_etf.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)

    # --- parameter_sensitivity.png ---
    fig, ax = plt.subplots(figsize=(8, 6))
    pivot_data: Dict[str, Dict[int, float]] = {}
    for key, res in individual.items():
        if isinstance(key, tuple) and res.get("metrics"):
            ticker, lb = key
            pivot_data.setdefault(ticker, {})[lb] = res["metrics"].get(
                "sharpe_ratio", 0.0
            )

    if pivot_data:
        pivot_df = pd.DataFrame(pivot_data, index=LOOKBACK_WINDOWS).T
        pivot_df = pivot_df.fillna(0.0)
        im = ax.imshow(pivot_df.values, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(LOOKBACK_WINDOWS)))
        ax.set_xticklabels(LOOKBACK_WINDOWS)
        ax.set_yticks(range(len(pivot_df.index)))
        ax.set_yticklabels(pivot_df.index)
        for i in range(len(pivot_df.index)):
            for j in range(len(LOOKBACK_WINDOWS)):
                val = pivot_df.iloc[i, j]
                ax.text(
                    j, i, f"{val:.2f}", ha="center", va="center", fontsize=9
                )
        plt.colorbar(im, ax=ax, label="Sharpe Ratio")
        ax.set_title("Parameter Sensitivity: Sharpe vs Lookback")
        ax.set_xlabel("Lookback Window (days)")
        ax.set_ylabel("ETF")
        fig.savefig(
            os.path.join(output_dir, "parameter_sensitivity.png"),
            dpi=150,
            bbox_inches="tight",
        )
    plt.close(fig)

    # ------------------------------------------------------------------
    # 5e. report.md
    # ------------------------------------------------------------------
    _write_markdown_report(results, output_dir, metrics_rows)

    logger.info("Reports written to %s", output_dir)


def _write_markdown_report(
    results: Dict[str, Any],
    output_dir: str,
    metrics_rows: List[Dict[str, Any]],
) -> None:
    """Write the narrative Markdown report."""
    best_params = results.get("best_params", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines: List[str] = [
        "# Indian ETF Intraday Momentum Breakout Strategy — Research Report",
        "",
        f"**Generated:** {now}  ",
        "**Pipeline:** `alpha_search.research.indian_etf_intraday`  ",
        "**Status:** Research / Educational Use Only",
        "",
        "---",
        "",
        "## 1. Strategy Hypothesis",
        "",
        "This strategy tests a **noise-area breakout** concept on Indian-listed",
        "ETFs (Nippon India ETF series).  The core hypothesis is:",
        "",
        "> *When price breaks outside a volatility-defined 'noise area', it",
        "> *signals a directional momentum move.  Going long above the upper",
        "> *band and short below the lower band should capture these breakout moves.*",
        "",
        "### 1.1 Signal Construction",
        "",
        "- **Noise area** = rolling high/low expanded by ATR * multiplier",
        "- **Long signal**  when Close > upper boundary  (position = +1, vol-scaled)",
        "- **Short signal** when Close < lower boundary  (position = -1, vol-scaled)",
        "- **Flat** when price is inside the noise area  (position = 0)",
        "",
        "### 1.2 Volatility Targeting",
        "",
        "Position sizes are scaled by `target_vol / realised_vol` so that each",
        "position targets the same annualised risk budget (default: 10%%).",
        "",
        "---",
        "",
        "## 2. Universe",
        "",
        "| Ticker | Description |",
        "|--------|-------------|",
        "| NIFTYBEES.NS  | Nippon India Nifty 50 ETF    |",
        "| BANKBEES.NS   | Nippon India Nifty Bank ETF  |",
        "| ITBEES.NS     | Nippon India Nifty IT ETF    |",
        "| JUNIORBEES.NS | Nippon India Nifty Next 50   |",
        "",
        "---",
        "",
        "## 3. Parameter Search",
        "",
        "The following lookback windows were tested for noise-area computation:",
        "",
        "| Lookback | Description |",
        "|----------|-------------|",
        "| 20 days  | Short-term (approx. 1 month)   |",
        "| 45 days  | Medium-term (approx. 2 months) |",
        "| 90 days  | Long-term (approx. 4 months)   |",
        "",
    ]

    best_lookback = best_params.get("best_lookback", "N/A")
    best_etf = best_params.get("best_etf", "N/A")
    best_sharpe = best_params.get("best_sharpe")
    lines.append(f"**Best lookback:** `{best_lookback}`  ")
    lines.append(f"**Best ETF:** `{best_etf}`  ")
    if best_sharpe is not None:
        lines.append(f"**Best Sharpe:** `{best_sharpe:.3f}`")
    else:
        lines.append("**Best Sharpe:** N/A")
    lines.extend(["", "---", ""])

    # Metrics table
    lines.extend([
        "## 4. Backtest Results",
        "",
    ])

    if metrics_rows:
        lines.extend([
            "### 4.1 Strategy Metrics",
            "",
            "| ETF | Lookback | Sharpe | Total Return | Max Drawdown | Win Rate | Trades |",
            "|-----|----------|--------|--------------|--------------|----------|--------|",
        ])
        for row in metrics_rows:
            etf_name = row.get("etf", "")
            lb = row.get("lookback", "")
            sharpe = row.get("sharpe_ratio", 0.0) or 0.0
            tr = row.get("total_return", 0.0) or 0.0
            mdd = row.get("max_drawdown", 0.0) or 0.0
            wr = row.get("win_rate", 0.0) or 0.0
            nt = row.get("n_trades", 0)
            lines.append(
                f"| {etf_name} | {lb} | "
                f"{sharpe:.3f} | {tr:.2%} | {mdd:.2%} | {wr:.2%} | {nt} |"
            )
        lines.append("")

    # Portfolio results
    portfolios = results.get("portfolio_results", {})
    if portfolios:
        lines.extend([
            "### 4.2 Portfolio Results",
            "",
            "| Method | Lookback | Sharpe | Total Return | Max Drawdown | Win Rate |",
            "|--------|----------|--------|--------------|--------------|----------|",
        ])
        for lb, port_dict in portfolios.items():
            for method, p in port_dict.items():
                m = p["metrics"]
                lines.append(
                    f"| {method} | {lb} | "
                    f"{m.get('sharpe_ratio', 0.0):.3f} | "
                    f"{m.get('total_return', 0.0):.2%} | "
                    f"{m.get('max_drawdown', 0.0):.2%} | "
                    f"{m.get('win_rate', 0.0):.2%} |"
                )
        lines.append("")

    # Assumptions section
    lines.extend([
        "---",
        "",
        "## 5. Assumptions and Limitations",
        "",
        "### 5.1 Assumptions",
        "",
        "- **Transaction costs:** 10 bps commission + 10 bps slippage per trade",
        "  (total 20 bps round-trip).  This is realistic for Indian retail",
        "  brokers but may vary by account type.",
        "- **Volatility targeting:** Annual target of 10%%.  This is",
        "  moderate — actual sizing should be calibrated to risk tolerance.",
        "- **Continuous signals:** Positions are rebalanced daily based on",
        "  the signal.  In practice, execution frequency may need to be",
        "  reduced to manage turnover.",
        "- **No market impact:** The backtest assumes fills at closing prices",
        "  without market impact.  For small retail positions this is",
        "  approximately true; for larger sizes it is not.",
        "",
        "### 5.2 Limitations",
        "",
        "- **Data quality:** Uses adjusted closing prices from yfinance.",
        "  Corporate actions (splits, dividends) are reflected in adjusted",
        "  prices but the data may have gaps or errors.",
        "- **Survivorship bias:** All four ETFs are currently listed and",
        "  liquid.  The backtest does not account for ETFs that may have",
        "  been delisted or merged.",
        "- **Look-ahead bias:** The noise area uses rolling windows and",
        "  does not peek into the future.  However, the parameter search",
        "  across three lookbacks introduces selection bias (see overfitting).",
        "- **Short selling:** Short signals assume the ability to short",
        "  Indian ETFs.  In practice, shorting may be restricted,",
        "  require SLBM (Securities Lending & Borrowing), or incur",
        "  additional costs not captured here.",
        "- **Taxes:** No tax considerations (STCG/LTCG, STT) are included.",
        "",
        "### 5.3 Overfitting Discussion",
        "",
        "**Risk level: HIGH.**  This backtest tests only 3 lookback windows",
        "on 4 ETFs with a single signal type.  Key overfitting risks:",
        "",
        "1. **Parameter selection:** The 'best' lookback was chosen",
        "   *ex-post* from only 3 candidates.  Out-of-sample performance",
        "   may differ substantially.",
        "2. **Multiple comparison:** With 12 parameter combinations",
        "   (4 ETFs x 3 lookbacks), some may appear good by chance.",
        "3. **No walk-forward validation:** The backtest uses the full",
        "   period for both training and evaluation.  Walk-forward or",
        "   cross-validation is needed for honest estimates.",
        "4. **No regime testing:** The ~2-year period may not cover",
        "   different market regimes (bull, bear, high volatility, etc.).",
        "",
        "**Recommendation:** Before any capital deployment, run a proper",
        "walk-forward analysis with at least 12 months of out-of-sample",
        "data and test across multiple market regimes.",
        "",
        "### 5.4 Cost Sensitivity",
        "",
        "The strategy generates signals based on daily noise-area breaks.",
        "If the number of trades is high, transaction costs can erode",
        "returns significantly.  At 20 bps per round-trip, a strategy",
        "that turns over 100%% monthly loses ~2.4%% annually to costs.",
        "Consider reducing trading frequency (e.g., trade only on",
        "confirmed breaks with minimum hold periods) to improve",
        "net-of-cost performance.",
        "",
        "---",
        "",
        "## 6. Disclaimer",
        "",
        "> **This research is for educational and informational purposes only.**",
        "> It does not constitute investment advice, an offer to sell, or a",
        "> solicitation of an offer to buy any securities.  Past performance",
        "> is not indicative of future results.  Always conduct your own",
        "> research and consult a licensed financial advisor before making",
        "> investment decisions.",
        "",
        "---",
        "",
        "## 7. Files Generated",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `report.md` | This narrative report |",
        "| `strategy_metrics.csv` | All backtest metrics per ETF/lookback |",
        "| `trade_log.csv` | Complete trade log |",
        "| `parameter_results.csv` | Parameter sensitivity grid |",
        "| `equity_curve.png` | Equity curves (best lookback) |",
        "| `drawdown.png` | Drawdown charts (best lookback) |",
        "| `sharpe_by_etf.png` | Sharpe ratio comparison |",
        "| `parameter_sensitivity.png` | Heatmap of Sharpe vs lookback |",
        "",
    ])

    md_path = os.path.join(output_dir, "report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ===========================================================================
# 6. Memory storage
# ===========================================================================


def store_results_to_memory(results: Dict[str, Any]) -> None:
    """Persist all research results to the Alpha Search memory layer.

    Uses :class:`MemoryStore` for structured storage and :class:`AgentJournal`
    for human-readable audit trails.

    Stored items:

    * Parameter combinations and their Sharpe ratios
    * Drawdown records
    * Rejected ideas (failed backtests)
    * Best-performing ETF and noise window
    * Risk decisions (overfitting warnings)
    * Strategy memory entries

    Args:
        results: Results dict from :func:`run_full_pipeline`.
    """
    output_dir = results.get("output_dir", "reports/indian_etf")
    memory_dir = os.path.join(output_dir, "memory")
    os.makedirs(memory_dir, exist_ok=True)

    db_path = os.path.join(memory_dir, "alpha_search_memory.duckdb")
    store = MemoryStore(db_path)
    store.initialize()
    journal = AgentJournal(store, journal_dir=memory_dir)

    individual = results.get("individual_results", {})
    best_params = results.get("best_params", {})

    # Log the overall task
    journal.log_task(
        agent_name="indian_etf_researcher",
        task="Run Indian ETF intraday breakout pipeline",
        status="done",
        notes=(
            f"Tested {len(INDIAN_ETFS)} ETFs across "
            f"{len(LOOKBACK_WINDOWS)} lookback windows. "
            f"Best: {best_params.get('best_etf', 'N/A')} with "
            f"lb={best_params.get('best_lookback', 'N/A')}"
        ),
        tags=["indian_etf", "momentum", "breakout", "research"],
    )

    # Store each parameter result
    for key, res in individual.items():
        if isinstance(key, tuple):
            ticker, lb = key
        else:
            ticker = res.get("etf", "unknown")
            lb = res.get("lookback", 0)

        if "error" in res:
            rejection_record = StrategyMemory(
                strategy_name=f"noise_breakout_{ticker}_lb{lb}",
                strategy_type="momentum",
                market="India",
                asset_class="equity",
                universe=[ticker],
                hypothesis=f"Noise-area breakout with {lb}-day lookback on {ticker}",
                result_summary=f"Backtest failed: {res['error']}",
                verdict="rejected",
                rejection_reason=res["error"],
                lessons_learned="Data fetch or backtest error — retry with different period or check data quality.",
                validation_method="in_sample_backtest",
            )
            journal.log_strategy_result(rejection_record)
            continue

        metrics = res.get("metrics", {})
        sharpe = metrics.get("sharpe_ratio")
        mdd = metrics.get("max_drawdown")
        tr = metrics.get("total_return")
        wr = metrics.get("win_rate")

        if sharpe is not None and sharpe > 0.5:
            verdict = "accepted"
            lessons = f"Promising Sharpe of {sharpe:.3f} with {lb}-day lookback."
        elif sharpe is not None and sharpe > 0.0:
            verdict = "watch"
            lessons = f"Marginal Sharpe of {sharpe:.3f} — worth monitoring but not deploying."
        # Pre-format summary strings
        sharpe_str = f"{sharpe:.3f}" if sharpe is not None else "N/A"

        if sharpe is not None and sharpe > 0.5:
            verdict = "accepted"
            lessons = f"Promising Sharpe of {sharpe:.3f} with {lb}-day lookback."
        elif sharpe is not None and sharpe > 0.0:
            verdict = "watch"
            lessons = f"Marginal Sharpe of {sharpe:.3f} — worth monitoring but not deploying."
        else:
            verdict = "watch"
            lessons = f"Weak or negative Sharpe ({sharpe_str})."

        # Format remaining summary strings
        mdd_str = f"{mdd:.2%}" if mdd is not None else "N/A"
        tr_str = f"{tr:.2%}" if tr is not None else "N/A"

        record = StrategyMemory(
            strategy_name=f"noise_breakout_{ticker}_lb{lb}",
            strategy_type="momentum",
            market="India",
            asset_class="equity",
            universe=[ticker],
            hypothesis=(
                f"Noise-area breakout: long above upper band, short below lower band "
                f"({lb}-day lookback)"
            ),
            result_summary=(
                f"Sharpe={sharpe_str}, "
                f"MaxDD={mdd_str}, "
                f"Return={tr_str}"
            ),
            sharpe=sharpe,
            max_drawdown=mdd,
            total_return=tr,
            win_rate=wr,
            turnover=None,
            transaction_cost_assumption="10 bps commission + 10 bps slippage",
            validation_method="in_sample_backtest",
            verdict=verdict,
            lessons_learned=lessons,
        )
        journal.log_strategy_result(record)

    # Store portfolio results
    for lb, port_dict in results.get("portfolio_results", {}).items():
        for method, p in port_dict.items():
            m = p["metrics"]
            record = StrategyMemory(
                strategy_name=f"noise_breakout_portfolio_{method}_lb{lb}",
                strategy_type="portfolio",
                market="India",
                asset_class="equity",
                universe=INDIAN_ETFS,
                hypothesis=f"Portfolio construction: {method} with {lb}-day lookback",
                result_summary=(
                    f"Sharpe={m.get('sharpe_ratio', 0.0):.3f}, "
                    f"Return={m.get('total_return', 0.0):.2%}"
                ),
                sharpe=m.get("sharpe_ratio"),
                max_drawdown=m.get("max_drawdown"),
                total_return=m.get("total_return"),
                win_rate=m.get("win_rate"),
                transaction_cost_assumption="10 bps commission + 10 bps slippage",
                validation_method="in_sample_backtest",
                verdict="watch",
                lessons_learned=f"Portfolio {method} result for {lb}-day lookback.",
            )
            journal.log_strategy_result(record)

    # Risk decision: overfitting warning
    journal.log_risk_decision(
        agent_name="indian_etf_researcher",
        object_type="strategy",
        object_id="noise_breakout_indian_etf",
        decision="flagged",
        reason=(
            "High overfitting risk: only 3 lookbacks tested on 4 ETFs with in-sample "
            "evaluation.  Parameter selection is ex-post.  Walk-forward validation "
            "required before deployment."
        ),
        severity="high",
    )

    # Store best params as a decision
    if best_params:
        journal.log_decision(
            agent_name="indian_etf_researcher",
            decision=(
                f"Best parameters: {best_params.get('best_etf')} with "
                f"lookback={best_params.get('best_lookback')} "
                f"(Sharpe={best_params.get('best_sharpe', 0.0):.3f})"
            ),
            rationale=(
                "Selected based on highest in-sample Sharpe ratio across all "
                "parameter combinations.  Note: this is subject to look-ahead bias "
                "and must be validated out-of-sample."
            ),
            tags=["indian_etf", "parameter_selection", "best_params"],
            importance_score=0.8,
        )

    # Memory record for each lookback tested
    for lb in LOOKBACK_WINDOWS:
        record = MemoryRecord(
            agent_name="indian_etf_researcher",
            memory_type="research_finding",
            title=f"Noise-area breakout: {lb}-day lookback results",
            content=(
                f"Backtested {len(INDIAN_ETFS)} Indian ETFs with {lb}-day "
                f"noise-area lookback.  Results stored in strategy_memory table."
            ),
            tags=["indian_etf", "noise_breakout", f"lookback_{lb}"],
            importance_score=0.6,
        )
        store.add_memory(record)

    store.close()
    logger.info("Results stored to memory at %s", memory_dir)


# ===========================================================================
# Module exports
# ===========================================================================

__all__ = [
    "INDIAN_ETFS",
    "LOOKBACK_WINDOWS",
    "PORTFOLIO_METHODS",
    "fetch_indian_etf_data",
    "run_noise_breakout_backtest",
    "run_portfolio_backtest",
    "run_full_pipeline",
    "generate_report",
    "store_results_to_memory",
]
