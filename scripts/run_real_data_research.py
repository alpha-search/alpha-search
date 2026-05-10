"""
Alpha Search — Real Data Strategy Research Pipeline

A complete, production-grade CLI entry point that executes a 10-step
quantitative research pipeline on real market data fetched from yfinance.

Usage:
    python scripts/run_real_data_research.py --start 2019-01-01 --end latest \\
        --universe us_large_cap --output-dir alpha_search/reports

Pipeline Steps:
    1. Real Data Ingestion      — fetch OHLCV from yfinance
    2. Return Calculation       — daily returns, rolling vol, momentum
    3. Liquidity Summary        — volume, missing data, ranks
    4. Momentum Strategy        — 60-day momentum + 20-day confirmation
    5. Mean Reversion Strategy  — z-score mean reversion
    6. Statistical Arbitrage    — correlated pairs + spread trading
    7. Portfolio Optimization   — equal weight, inverse vol, risk parity
    8. Combined Metrics         — aggregate all strategy results
    9. Memory Logging           — persist to MemoryStore
   10. Report Generation        — Markdown report + metadata.json
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from alpha_search.research.metrics import (
    compute_all_metrics,
    rolling_momentum,
    rolling_volatility,
)

# ---------------------------------------------------------------------------
# Alpha Search imports
# ---------------------------------------------------------------------------
from alpha_search.research.universes import US_LARGE_CAP, get_universe

try:
    from alpha_search.memory import MemoryStore
    from alpha_search.memory.models import StrategyMemory
    _HAS_MEMORY: bool = True
except Exception:
    _HAS_MEMORY = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
logger = logging.getLogger("alpha_search.run_real_data_research")
DISCLAIMER: str = (
    "This research is for informational and educational purposes only. "
    "It does not constitute investment advice. Past performance is not "
    "indicative of future results. Always consult a qualified financial "
    "advisor before making investment decisions."
)
RUN_TS: str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.captureWarnings(True)
    warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------
def _ensure_dirs(out: Path) -> tuple[Path, Path]:
    latest = out / "latest"
    run = out / "runs" / RUN_TS
    latest.mkdir(parents=True, exist_ok=True)
    run.mkdir(parents=True, exist_ok=True)
    return latest, run

def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Wrote %s (%d rows)", path.name, len(df))

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_real_data_research.py",
        description="Alpha Search — Real Data Strategy Research Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="latest")
    p.add_argument("--universe", default="us_large_cap",
                   choices=["us_large_cap", "us_tech", "us_financials", "india_nifty"])
    p.add_argument("--output-dir", default="alpha_search/reports")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--transaction-cost", type=float, default=0.001)
    p.add_argument("--skip-memory", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p

# No fallback data generation — if real data cannot be fetched,
# the pipeline raises a clear error telling the user how to fix it.


# ===================================================================
# STEP 1 — Real Data Ingestion
# ===================================================================
def step_1_fetch(tickers: list[str], start: str, end: str | None, out: Path) -> pd.DataFrame:
    logger.info("STEP 1 — Fetching data for %d tickers …", len(tickers))
    records: list[dict] = []
    for t in tickers:
        try:
            logger.info("  → %s", t)
            df = yf.Ticker(t).history(
                start=start, end=end if end and end.lower() != "latest" else None, auto_adjust=False
            )
            if df.empty:
                logger.warning("  ⚠ %s empty — skipping", t)
                continue
            df = df.reset_index()
            rename = {"Date": "date", "Open": "open", "High": "high", "Low": "low",
                      "Close": "close", "Adj Close": "adjusted_close", "Volume": "volume"}
            df = df.rename(columns=rename)
            for _, r in df.iterrows():
                records.append({
                    "date": r["date"], "ticker": t,
                    "open": float(r.get("open", np.nan)), "high": float(r.get("high", np.nan)),
                    "low": float(r.get("low", np.nan)), "close": float(r.get("close", np.nan)),
                    "adjusted_close": float(r.get("adjusted_close", r.get("close", np.nan))),
                    "volume": float(r.get("volume", 0)), "source": "yfinance",
                })
        except Exception as exc:
            logger.warning("  ⚠ %s failed: %s — skipping", t, exc)
    if not records:
        raise RuntimeError(
            f"Failed to fetch data for any of the {len(tickers)} requested tickers. "
            f"Check your network connection, verify ticker symbols, "
            f"and ensure yfinance is installed: pip install yfinance"
        )
    price = pd.DataFrame(records)
    price["date"] = pd.to_datetime(price["date"]).dt.tz_localize(None)
    price = price.sort_values(["ticker", "date"]).reset_index(drop=True)
    _write_csv(price, out / "price_data.csv")
    logger.info("STEP 1 done — %d rows, %d tickers",
                len(price), price["ticker"].nunique())
    return price

# ===================================================================
# STEP 2 — Return Calculation
# ===================================================================
def step_2_returns(price: pd.DataFrame, out: Path) -> pd.DataFrame:
    logger.info("STEP 2 — Calculating returns …")
    frames = []
    for t, g in price.groupby("ticker"):
        g = g.sort_values("date").copy()
        g["daily_return"] = g["close"].pct_change()
        g["log_return"] = np.log(g["close"] / g["close"].shift(1))
        g["rolling_vol_20d"] = rolling_volatility(g["daily_return"], 20)
        g["rolling_vol_60d"] = rolling_volatility(g["daily_return"], 60)
        g["rolling_momentum_20d"] = rolling_momentum(g["close"], 20)
        g["rolling_momentum_60d"] = rolling_momentum(g["close"], 60)
        frames.append(g)
    ret = pd.concat(frames, ignore_index=True)
    _write_csv(ret, out / "returns_data.csv")
    logger.info("STEP 2 done")
    return ret

# ===================================================================
# STEP 3 — Liquidity Summary
# ===================================================================
def step_3_liquidity(price: pd.DataFrame, out: Path) -> pd.DataFrame:
    logger.info("STEP 3 — Liquidity summary …")
    rows = []
    for t, g in price.groupby("ticker"):
        g = g.sort_values("date")
        n = len(g)
        miss = g[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum()
        avg_vol = g["volume"].mean()
        avg_px = g["close"].mean()
        rows.append({
            "ticker": t, "avg_daily_volume": round(avg_vol, 2) if pd.notna(avg_vol) else 0.0,
            "avg_dollar_volume": round(avg_vol * avg_px, 2) if pd.notna(avg_vol * avg_px) else 0.0,
            "missing_pct": round(100.0 * miss / n, 4) if n else 0.0,
            "first_date": g["date"].min().strftime("%Y-%m-%d"),
            "last_date": g["date"].max().strftime("%Y-%m-%d"),
        })
    liq = pd.DataFrame(rows).sort_values("avg_dollar_volume", ascending=False).reset_index(drop=True)
    liq["liquidity_rank"] = liq.index + 1
    _write_csv(liq, out / "liquidity_summary.csv")
    logger.info("STEP 3 done — %d tickers", len(liq))
    return liq

# ===================================================================
# STEP 4 — Momentum Strategy
# ===================================================================
def step_4_momentum(ret: pd.DataFrame, capital: float, tc: float, out: Path) -> pd.DataFrame:
    logger.info("STEP 4 — Momentum strategy …")
    try:
        close = ret.pivot(index="date", columns="ticker", values="close").dropna(how="all", axis=1).ffill()
        mom60 = close.pct_change(60)
        mom20 = close.pct_change(20)
        signals: dict = {}
        for dt in close.index:
            m60 = mom60.loc[dt].dropna()
            m20 = mom20.loc[dt].dropna()
            cand = m60[m20 > 0].dropna()
            if len(cand) >= 3:
                top3 = cand.nlargest(3)
                signals[dt] = pd.Series(1.0 / 3.0, index=top3.index)
        if not signals:
            logger.warning("  No momentum signals")
            return pd.DataFrame()
        sig = pd.DataFrame(signals).T.reindex(close.index).ffill().fillna(0)
        rets = close.pct_change().fillna(0)
        pr = (sig * rets).sum(axis=1).fillna(0)
        pr -= sig.diff().abs().sum(axis=1).fillna(0) * tc
        m = {"strategy": "momentum", **compute_all_metrics(pr)}
        df = pd.DataFrame([m])
        _write_csv(df, out / "momentum_results.csv")
        logger.info("STEP 4 done — Sharpe %.3f", m["sharpe_ratio"])
        return df
    except Exception as exc:
        logger.error("STEP 4 failed: %s", exc)
        return pd.DataFrame()

# ===================================================================
# STEP 5 — Mean Reversion Strategy
# ===================================================================
def step_5_mr(ret: pd.DataFrame, capital: float, tc: float, out: Path) -> pd.DataFrame:
    logger.info("STEP 5 — Mean reversion strategy …")
    try:
        close = ret.pivot(index="date", columns="ticker", values="close").dropna(how="all", axis=1).ffill()
        z = (close - close.rolling(20).mean()) / close.rolling(20).std().replace(0, np.nan)
        sig = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        sig[z < -1.5] = 1.0
        sig[z > -0.5] = 0.0
        sig = sig.ffill().fillna(0)
        active = sig.sum(axis=1).replace(0, np.nan)
        sig = sig.div(active, axis=0).fillna(0)
        rets = close.pct_change().fillna(0)
        pr = (sig * rets).sum(axis=1).fillna(0)
        pr -= sig.diff().abs().sum(axis=1).fillna(0) * tc
        m = {"strategy": "mean_reversion", **compute_all_metrics(pr)}
        df = pd.DataFrame([m])
        _write_csv(df, out / "mean_reversion_results.csv")
        logger.info("STEP 5 done — Sharpe %.3f", m["sharpe_ratio"])
        return df
    except Exception as exc:
        logger.error("STEP 5 failed: %s", exc)
        return pd.DataFrame()

# ===================================================================
# STEP 6 — Statistical Arbitrage (Pairs)
# ===================================================================
def step_6_arb(ret: pd.DataFrame, capital: float, tc: float, out: Path) -> pd.DataFrame:
    logger.info("STEP 6 — Statistical arbitrage …")
    try:
        close = ret.pivot(index="date", columns="ticker", values="close").dropna(how="all", axis=1).ffill().dropna()
        if close.shape[1] < 2:
            return pd.DataFrame()
        corr = close.pct_change().corr()
        pairs = [(corr.index[i], corr.columns[j], corr.iloc[i, j])
                 for i in range(len(corr)) for j in range(i + 1, len(corr)) if pd.notna(corr.iloc[i, j])]
        pairs.sort(key=lambda x: x[2], reverse=True)
        rows = []
        for a, b, c in pairs[:5]:
            try:
                va, vb = close[a], close[b]
                valid = va.dropna().index.intersection(vb.dropna().index)
                if len(valid) < 60:
                    continue
                x, y = vb.loc[valid].values, va.loc[valid].values
                beta = np.cov(x, y)[0, 1] / np.var(x)
                if np.isnan(beta) or beta == 0:
                    continue
                spread = va.loc[valid] - beta * vb.loc[valid]
                z = (spread - spread.rolling(60).mean()) / spread.rolling(60).std().replace(0, np.nan)
                sig = pd.Series(0.0, index=spread.index)
                sig[z < -2] = 1.0
                sig[z > 2] = -1.0
                ra, rb = va.pct_change().loc[valid], vb.pct_change().loc[valid]
                pr = sig.shift(1).fillna(0) * (ra - beta * rb).fillna(0)
                pr -= sig.diff().abs().fillna(0) * tc * 2
                metrics = compute_all_metrics(pr)
                metrics["strategy"] = f"arbitrage_{a}_{b}"
                metrics["pair"] = f"{a}/{b}"
                metrics["correlation"] = round(c, 4)
                metrics["hedge_ratio"] = round(beta, 4)
                rows.append(metrics)
            except Exception as e:
                logger.warning("  Pair %s/%s: %s", a, b, e)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            _write_csv(df, out / "arbitrage_pairs_results.csv")
        logger.info("STEP 6 done — %d pairs", len(df))
        return df
    except Exception as exc:
        logger.error("STEP 6 failed: %s", exc)
        return pd.DataFrame()

# ===================================================================
# STEP 7 — Portfolio Optimization
# ===================================================================
def step_7_portfolio(ret: pd.DataFrame, capital: float, out: Path) -> pd.DataFrame:
    logger.info("STEP 7 — Portfolio optimization …")
    try:
        close = ret.pivot(index="date", columns="ticker", values="close").dropna(how="all", axis=1).ffill().dropna()
        rets = close.pct_change().dropna()
        if rets.shape[1] < 2:
            return pd.DataFrame()
        n = rets.shape[1]
        strategies = [
            ("equal_weight", pd.Series(1.0 / n, index=rets.columns)),
        ]
        vol = rets.rolling(60).std().iloc[-1].dropna()
        if not vol.empty:
            strategies.append(("inverse_volatility", (1.0 / vol) / (1.0 / vol).sum()))
        var = rets.rolling(60).var().iloc[-1].dropna()
        if not var.empty:
            strategies.append(("risk_parity", (1.0 / var) / (1.0 / var).sum()))
        rows = [{"strategy": f"portfolio_{name}", **compute_all_metrics((rets * w).sum(axis=1))} for name, w in strategies]
        df = pd.DataFrame(rows)
        _write_csv(df, out / "portfolio_optimization_results.csv")
        logger.info("STEP 7 done — %d methods", len(df))
        return df
    except Exception as exc:
        logger.error("STEP 7 failed: %s", exc)
        return pd.DataFrame()

# ===================================================================
# STEP 8 — Combined Metrics
# ===================================================================
def step_8_combine(mom: pd.DataFrame, mr: pd.DataFrame, arb: pd.DataFrame, port: pd.DataFrame, out: Path) -> pd.DataFrame:
    logger.info("STEP 8 — Combining metrics …")
    frames = [f for f in [mom, mr, arb, port] if not f.empty]
    if not frames:
        return pd.DataFrame()
    comb = pd.concat(frames, ignore_index=True)
    _write_csv(comb, out / "strategy_results_summary.csv")
    logger.info("STEP 8 done — %d rows", len(comb))
    return comb

# ===================================================================
# STEP 9 — Memory Logging
# ===================================================================
def step_9_memory(comb: pd.DataFrame, args: argparse.Namespace, out: Path) -> pd.DataFrame:
    logger.info("STEP 9 — Memory logging …")
    records = []
    if args.skip_memory or not _HAS_MEMORY:
        logger.info("  Skipped (flag=%s, module=%s)", args.skip_memory, _HAS_MEMORY)
        return pd.DataFrame(records)
    try:
        store = MemoryStore()
        for _, r in comb.iterrows():
            try:
                name = r.get("strategy", r.get("method", r.get("pair", "unknown")))
                mem = StrategyMemory(name=str(name), description=f"Backtest: {name}",
                                     signal_type=str(name), metrics=r.to_dict(),
                                     tags=["backtest", "real_data", str(name)])
                store.add(mem)
                records.append({"strategy": name, "status": "created", "timestamp": RUN_TS})
            except Exception as e:
                logger.warning("  Memory log for %s failed: %s", name, e)
    except Exception as exc:
        logger.error("STEP 9 failed: %s", exc)
    df = pd.DataFrame(records)
    _write_csv(df, out / "memory_records_created.csv")
    logger.info("STEP 9 done — %d records", len(df))
    return df

# ===================================================================
# STEP 10 — Report Generation
# ===================================================================
def step_10_report(comb: pd.DataFrame, liq: pd.DataFrame, price: pd.DataFrame,
                   args: argparse.Namespace, out: Path) -> None:
    logger.info("STEP 10 — Generating report …")
    end_dt = args.end if args.end and args.end != "latest" else datetime.now().strftime("%Y-%m-%d")
    meta = {
        "run_timestamp": RUN_TS, "pipeline_version": "1.0.0",
        "start_date": args.start, "end_date": end_dt, "universe": args.universe,
        "tickers_fetched": liq["ticker"].tolist() if not liq.empty else [],
        "initial_capital": args.capital, "transaction_cost": args.transaction_cost,
        "skip_memory": args.skip_memory, "disclaimer": DISCLAIMER,
        "data_source": "yfinance",
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))

    lines = [
        "# Alpha Search — Real Data Strategy Research Report\n",
        f"**Run Date:** {RUN_TS}\n**Universe:** `{args.universe}`\n"
        f"**Period:** {args.start} → {end_dt}\n"
        f"**Capital:** ${args.capital:,.2f}  **Tx Cost:** {args.transaction_cost * 100:.2f}%\n",
        "---\n",
    ]
    if not liq.empty:
        lines.extend(["## Liquidity Summary\n", "| Ticker | Avg Daily Vol | Avg $ Vol | Missing % | Rank |",
                      "|--------|--------------|-----------|-----------|------|"])
        for _, r in liq.head(10).iterrows():
            lines.append(f"| {r['ticker']} | {r['avg_daily_volume']:,.0f} | "
                         f"${r['avg_dollar_volume']:,.0f} | {r['missing_pct']:.2f}% | {r['liquidity_rank']} |")
        lines.append("")
    if not comb.empty:
        lines.extend(["## Strategy Results\n",
                      "| Strategy | Total Ret | Ann Ret | Ann Vol | Sharpe | Max DD | Win Rate |",
                      "|----------|-----------|---------|---------|--------|--------|----------|"])
        for _, r in comb.iterrows():
            s = r.get("strategy", "?")
            lines.append(f"| {s} | {r.get('total_return', 0):.4f} | {r.get('annualized_return', 0):.4f} | "
                         f"{r.get('annualized_volatility', 0):.4f} | {r.get('sharpe_ratio', 0):.4f} | "
                         f"{r.get('max_drawdown', 0):.4f} | {r.get('win_rate', 0):.4f} |")
        lines.append("")
    else:
        lines.append("## Strategy Results\n*No results.*\n")
    lines.extend(["## Generated Files\n"] + [f"- `{f.name}`" for f in sorted(out.iterdir()) if f.is_file()] + [""])
    lines.extend(["## Disclaimer\n", f"> {DISCLAIMER}\n"])
    (out / "real_data_strategy_report.md").write_text("\n".join(lines))
    logger.info("STEP 10 done")

# ===================================================================
# Console summary
# ===================================================================
def _print_summary(comb: pd.DataFrame, liq: pd.DataFrame, args: argparse.Namespace, out: Path) -> None:
    print("\n" + "=" * 70)
    print("  ALPHA SEARCH — REAL DATA STRATEGY RESEARCH PIPELINE")
    print("=" * 70)
    print(f"  Run ID     : {RUN_TS}\n  Universe   : {args.universe}")
    print(f"  Period     : {args.start} → {args.end}\n  Capital    : ${args.capital:,.2f}")
    print(f"  Tx Cost    : {args.transaction_cost * 100:.2f}%\n  Output     : {out}")
    print("-" * 70)
    if not liq.empty:
        print(f"\n  Tickers    : {liq['ticker'].nunique()}  Avg $Vol: ${liq['avg_dollar_volume'].mean():,.0f}")
    if not comb.empty:
        print(f"\n  {'Strategy':<25} {'TotRet':>8} {'AnnRet':>8} {'AnnVol':>8} {'Sharpe':>8} {'MaxDD':>8} {'WinRate':>8}")
        print("  " + "-" * 73)
        for _, r in comb.iterrows():
            s = r.get("strategy", "?")
            print(f"  {s:<25} {r.get('total_return', 0):>8.4f} {r.get('annualized_return', 0):>8.4f} "
                  f"{r.get('annualized_volatility', 0):>8.4f} {r.get('sharpe_ratio', 0):>8.4f} "
                  f"{r.get('max_drawdown', 0):>8.4f} {r.get('win_rate', 0):>8.4f}")
    print(f"\n  DISCLAIMER: {DISCLAIMER[:75]}...")
    print("=" * 70 + "\n")

# ===================================================================
# Main pipeline
# ===================================================================
def run_pipeline(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    logger.info("=" * 50)
    logger.info("Alpha Search Pipeline  |  Run: %s", RUN_TS)
    logger.info("=" * 50)

    out_base = Path(args.output_dir).resolve()
    latest, run = _ensure_dirs(out_base)

    try:
        universe = get_universe(args.universe)
        tickers = list(universe.tickers)
    except Exception:
        tickers = list(US_LARGE_CAP)
    logger.info("Universe '%s' → %d tickers: %s", args.universe, len(tickers), tickers)
    end = args.end if args.end.lower() != "latest" else None

    # --- STEP 1 ---
    price = step_1_fetch(tickers, args.start, end, latest)

    # --- STEPS 2-7 (each wrapped, continue on failure) ---
    ret = price.copy()
    for step_name, step_fn in [
        ("STEP 2", lambda: step_2_returns(price, latest)),
        ("STEP 3", lambda: step_3_liquidity(price, latest)),
    ]:
        try:
            result = step_fn()
            if step_name == "STEP 2":
                ret = result
            elif step_name == "STEP 3":
                liq = result
        except Exception as exc:
            logger.error("%s failed: %s", step_name, exc)
            if step_name == "STEP 3":
                liq = pd.DataFrame()

    # Strategies (each independent, failure of one doesn't block others)
    mom = mr = arb = port = pd.DataFrame()
    for name, fn in [
        ("momentum", lambda: step_4_momentum(ret, args.capital, args.transaction_cost, latest)),
        ("mean_reversion", lambda: step_5_mr(ret, args.capital, args.transaction_cost, latest)),
        ("arbitrage", lambda: step_6_arb(ret, args.capital, args.transaction_cost, latest)),
        ("portfolio", lambda: step_7_portfolio(ret, args.capital, latest)),
    ]:
        try:
            result = fn()
            if name == "momentum":
                mom = result
            elif name == "mean_reversion":
                mr = result
            elif name == "arbitrage":
                arb = result
            else:
                port = result
        except Exception as exc:
            logger.error("Strategy %s failed: %s", name, exc)

    # --- STEP 8 ---
    try:
        comb = step_8_combine(mom, mr, arb, port, latest)
    except Exception as exc:
        logger.error("STEP 8 failed: %s", exc)
        comb = pd.DataFrame()

    # --- STEP 9 ---
    try:
        step_9_memory(comb, args, latest)
    except Exception as exc:
        logger.error("STEP 9 failed: %s", exc)

    # --- STEP 10 ---
    try:
        step_10_report(comb, liq if "liq" in dir() else pd.DataFrame(), price, args, latest)
    except Exception as exc:
        logger.error("STEP 10 failed: %s", exc)

    # Archive
    try:
        for f in latest.iterdir():
            if f.is_file():
                shutil.copy2(f, run / f.name)
        logger.info("Archived to %s", run)
    except Exception as exc:
        logger.error("Archive failed: %s", exc)

    _print_summary(comb, liq if "liq" in dir() else pd.DataFrame(), args, latest)
    logger.info("Pipeline complete. Outputs: %s", latest)
    return 0


def main() -> int:
    return run_pipeline(_build_parser().parse_args())


if __name__ == "__main__":
    sys.exit(main())
