#!/usr/bin/env python3
"""Alpha Search — AI Infrastructure & Semiconductor Alpha Research Runner.

Executes the full AI-infrastructure alpha research pipeline (cross-sectional
momentum, trend following, mean reversion, Donchian breakout) on real Yahoo
Finance data and prints a run summary table on completion.

Usage:
    python scripts/run_ai_infra_research.py [OPTIONS]

Examples:
    # Default 5-year run with net costs
    python scripts/run_ai_infra_research.py

    # Long-only, custom output dir, JSON summary to stdout
    python scripts/run_ai_infra_research.py --long-only --json-summary \\
        --output-dir outputs/my_run

    # Cap universe to top 20 most liquid names, debug logging
    python scripts/run_ai_infra_research.py --top-n 20 --log-level DEBUG

    # Explicit ticker list
    python scripts/run_ai_infra_research.py --symbols NVDA AMD AVGO TSM

    # Custom cost assumptions and benchmark
    python scripts/run_ai_infra_research.py --cost-bps 5 --slippage-bps 5 \\
        --benchmark SMH
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path when invoked as a script
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DISCLAIMER = (
    "RESEARCH DISCLAIMER: This output is for informational and educational "
    "purposes only. It does NOT constitute investment advice, a solicitation, "
    "or a recommendation to buy or sell any security. Past performance is not "
    "indicative of future results. All backtest results are simulated with "
    "hindsight and may not reflect actual achievable returns. rf = 0 "
    "(no risk-free rate adjustment applied). Always consult a qualified "
    "financial professional before making any investment decision."
)

_BANNER = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║          Alpha Search — AI Infrastructure Alpha Research Pipeline           ║
║     Semiconductors · Semi Equipment · AI Infrastructure · US Equities       ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Strategies : Cross-Sectional Momentum | Trend Following |
               Mean Reversion | Donchian Breakout
  Data Source: Yahoo Finance (real OHLCV only — no synthetic data)
  Costs      : Net of one-way commission + slippage at every rebalance
  rf         : 0.0  (no FRED — Sharpe may be slightly overstated vs rf > 0)

  {disclaimer}
"""

logger = logging.getLogger("alpha_search.run_ai_infra_research")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_ai_infra_research.py",
        description=(
            "Alpha Search — AI Infrastructure & Semiconductor Alpha Research.\n"
            "Runs cross-sectional momentum, trend following, mean reversion, and "
            "Donchian breakout strategies on the US AI-infra / semiconductor "
            "universe using real Yahoo Finance data."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Data / universe
    p.add_argument(
        "--period",
        default="5y",
        metavar="PERIOD",
        help="yfinance history period, e.g. '5y', '2y', '1y'. (default: %(default)s)",
    )
    p.add_argument(
        "--interval",
        default="1d",
        metavar="INTERVAL",
        help="Bar interval, e.g. '1d', '1wk'. (default: %(default)s)",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Cap the universe to the top N symbols ordered by the pipeline's "
            "internal liquidity ranking. Optional — omit to use the full "
            "pre-defined universe."
        ),
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        metavar="TICKER",
        help=(
            "Explicit list of ticker symbols to use instead of the built-in "
            "universe. Example: --symbols NVDA AMD AVGO TSM"
        ),
    )
    p.add_argument(
        "--benchmark",
        default="SOXX",
        metavar="TICKER",
        help=(
            "Primary benchmark ticker for alpha/beta regression. "
            "(default: %(default)s)"
        ),
    )

    # Cost model
    p.add_argument(
        "--cost-bps",
        type=float,
        default=10.0,
        metavar="BPS",
        help="One-way commission in basis points charged on traded notional. (default: %(default)s)",
    )
    p.add_argument(
        "--slippage-bps",
        type=float,
        default=10.0,
        metavar="BPS",
        help="One-way slippage in basis points charged on traded notional. (default: %(default)s)",
    )

    # Portfolio
    p.add_argument(
        "--long-only",
        action="store_true",
        default=False,
        help=(
            "Run all strategies in long-only mode (suppress short legs). "
            "Cross-sectional momentum becomes long top tercile only."
        ),
    )

    # Output
    p.add_argument(
        "--output-dir",
        default="outputs/research_runs/ai_infrastructure",
        metavar="DIR",
        help=(
            "Directory to write output files (CSVs, JSON, report). "
            "Created automatically if it does not exist. (default: %(default)s)"
        ),
    )
    p.add_argument(
        "--json-summary",
        action="store_true",
        default=False,
        help=(
            "Print a machine-readable JSON summary of key results to stdout "
            "after the run completes. Useful for CI / programmatic consumption."
        ),
    )

    # Logging
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level. (default: %(default)s)",
    )

    return p


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)-35s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    logging.captureWarnings(True)
    # Quiet noisy third-party loggers unless the user asked for DEBUG
    if level > logging.DEBUG:
        for noisy in ("yfinance", "peewee", "urllib3", "requests"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    print(_BANNER.format(disclaimer=_DISCLAIMER), file=sys.stderr)


# ---------------------------------------------------------------------------
# Run summary table
# ---------------------------------------------------------------------------

def _print_summary(results: Dict[str, Any], args: argparse.Namespace) -> None:
    """Print a formatted run summary table to stderr."""
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    universe = results.get("universe_used", [])
    skipped = results.get("symbols_skipped", [])
    strategies: Dict[str, Any] = results.get("strategies", {})
    output_dir = results.get("output_dir", args.output_dir)
    duration = results.get("duration_seconds")
    error = results.get("error")

    sep = "=" * 80
    thin = "-" * 80

    print(f"\n{sep}", file=sys.stderr)
    print("  ALPHA SEARCH — AI INFRASTRUCTURE RESEARCH  |  RUN SUMMARY", file=sys.stderr)
    print(sep, file=sys.stderr)
    print(f"  Run time   : {run_ts}", file=sys.stderr)
    print(f"  Period     : {args.period}  Interval: {args.interval}", file=sys.stderr)
    print(f"  Costs      : {args.cost_bps} bps commission + {args.slippage_bps} bps slippage (one-way)", file=sys.stderr)
    print(f"  Benchmark  : {args.benchmark}", file=sys.stderr)
    print(f"  Long-only  : {args.long_only}", file=sys.stderr)
    print(f"  Universe   : {len(universe)} symbols used, {len(skipped)} skipped", file=sys.stderr)
    if skipped:
        print(f"  Skipped    : {', '.join(skipped)}", file=sys.stderr)
    print(f"  Output dir : {output_dir}", file=sys.stderr)
    if duration is not None:
        print(f"  Duration   : {duration:.1f}s", file=sys.stderr)
    print(thin, file=sys.stderr)

    if error:
        print(f"\n  ERROR: {error}\n", file=sys.stderr)
        print(sep, file=sys.stderr)
        return

    if not strategies:
        print("\n  No strategy results available.\n", file=sys.stderr)
        print(sep, file=sys.stderr)
        return

    # Strategy results table
    col_w = [30, 10, 10, 10, 10, 12, 10]
    headers = ["Strategy", "Verdict", "Sharpe", "Ann Ret", "Ann Vol", "Max DD", "Trades"]
    hdr_fmt = (
        f"  {{:<{col_w[0]}}} {{:>{col_w[1]}}} {{:>{col_w[2]}}} "
        f"{{:>{col_w[3]}}} {{:>{col_w[4]}}} {{:>{col_w[5]}}} {{:>{col_w[6]}}}"
    )
    row_fmt = hdr_fmt  # same widths

    print(hdr_fmt.format(*headers), file=sys.stderr)
    print("  " + "-" * (sum(col_w) + 2 * (len(col_w) - 1)), file=sys.stderr)

    _STRATEGY_DISPLAY_NAMES = {
        "cross_sectional_momentum": "Cross-Sectional Momentum",
        "trend_following": "Trend Following",
        "mean_reversion": "Mean Reversion",
        "breakout": "Donchian Breakout",
    }

    for key, strat in strategies.items():
        display_name = _STRATEGY_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
        verdict = strat.get("verdict", "n/a")
        metrics = strat.get("metrics_net", strat.get("metrics", {})) or {}
        sharpe = metrics.get("sharpe_ratio")
        ann_ret = metrics.get("annualized_return")
        ann_vol = metrics.get("annualized_volatility")
        max_dd = metrics.get("max_drawdown")
        trades = strat.get("num_trades", strat.get("trade_count", "n/a"))

        def _fmt_pct(v: Any) -> str:
            if v is None:
                return "n/a"
            try:
                return f"{float(v):.2%}"
            except (TypeError, ValueError):
                return str(v)

        def _fmt_float(v: Any, digits: int = 3) -> str:
            if v is None:
                return "n/a"
            try:
                return f"{float(v):.{digits}f}"
            except (TypeError, ValueError):
                return str(v)

        print(
            row_fmt.format(
                display_name[:col_w[0]],
                str(verdict)[:col_w[1]],
                _fmt_float(sharpe),
                _fmt_pct(ann_ret),
                _fmt_pct(ann_vol),
                _fmt_pct(max_dd) if max_dd is not None else "n/a",
                str(trades)[:col_w[6]],
            ),
            file=sys.stderr,
        )

    print(thin, file=sys.stderr)
    print(f"  DISCLAIMER: {_DISCLAIMER[:72]}...", file=sys.stderr)
    print(f"{sep}\n", file=sys.stderr)


# ---------------------------------------------------------------------------
# JSON summary
# ---------------------------------------------------------------------------

def _print_json_summary(results: Dict[str, Any]) -> None:
    """Print a compact machine-readable JSON summary to stdout."""
    strategies = results.get("strategies", {})
    summary: Dict[str, Any] = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "universe_size": len(results.get("universe_used", [])),
        "symbols_skipped": results.get("symbols_skipped", []),
        "output_dir": results.get("output_dir"),
        "duration_seconds": results.get("duration_seconds"),
        "error": results.get("error"),
        "strategies": {},
    }
    for key, strat in strategies.items():
        metrics = strat.get("metrics_net", strat.get("metrics", {})) or {}
        summary["strategies"][key] = {
            "verdict": strat.get("verdict"),
            "sharpe_ratio": metrics.get("sharpe_ratio"),
            "annualized_return": metrics.get("annualized_return"),
            "annualized_volatility": metrics.get("annualized_volatility"),
            "max_drawdown": metrics.get("max_drawdown"),
            "num_trades": strat.get("num_trades", strat.get("trade_count")),
        }
    print(json.dumps(summary, indent=2, default=str))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(args.log_level)
    _print_banner()

    # ------------------------------------------------------------------
    # Import pipeline — graceful ImportError with actionable hint
    # ------------------------------------------------------------------
    try:
        from alpha_search.research.ai_infra_strategy_pipeline import run_ai_infra_research
    except ImportError as exc:
        print(
            f"\n[ERROR] Could not import alpha_search: {exc}\n\n"
            "  Is the package installed?  Try:\n"
            "      pip install -e .\n"
            "  from the repository root, then retry.\n",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------
    # Build kwargs from CLI args
    # ------------------------------------------------------------------
    kwargs: Dict[str, Any] = {
        "period": args.period,
        "interval": args.interval,
        "cost_bps": args.cost_bps,
        "slippage_bps": args.slippage_bps,
        "output_dir": args.output_dir,
        "long_only": args.long_only,
        "primary_benchmark": args.benchmark,
    }
    if args.top_n is not None:
        kwargs["top_n"] = args.top_n
    if args.symbols is not None:
        kwargs["symbols"] = args.symbols

    logger.info(
        "Launching AI-infra research | period=%s interval=%s cost_bps=%.1f "
        "slippage_bps=%.1f long_only=%s benchmark=%s top_n=%s",
        args.period,
        args.interval,
        args.cost_bps,
        args.slippage_bps,
        args.long_only,
        args.benchmark,
        args.top_n,
    )

    # ------------------------------------------------------------------
    # Execute pipeline
    # ------------------------------------------------------------------
    try:
        results: Dict[str, Any] = run_ai_infra_research(**kwargs)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Run cancelled by user.\n", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("Pipeline raised an unexpected exception: %s", exc)
        # Build a minimal error results dict so summary still prints cleanly
        results = {
            "universe_used": [],
            "symbols_skipped": [],
            "strategies": {},
            "output_dir": args.output_dir,
            "duration_seconds": None,
            "error": str(exc),
        }
        _print_summary(results, args)
        if args.json_summary:
            _print_json_summary(results)
        return 1

    # ------------------------------------------------------------------
    # Print summary and optional JSON
    # ------------------------------------------------------------------
    _print_summary(results, args)

    if args.json_summary:
        _print_json_summary(results)

    # Exit 1 if the pipeline itself recorded a top-level error
    if results.get("error"):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
