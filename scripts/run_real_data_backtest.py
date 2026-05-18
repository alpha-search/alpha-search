#!/usr/bin/env python3
"""CLI entry-point for the real-data backtesting pipeline.

Usage examples
--------------
python scripts/run_real_data_backtest.py --universe us_large_cap --period 2y --interval 1d
python scripts/run_real_data_backtest.py --universe crypto --period 1y --interval 1d
python scripts/run_real_data_backtest.py --universe india_equity --period 2y --cost-bps 20 --slippage-bps 20
python scripts/run_real_data_backtest.py --csv-file my_data.csv --output-dir /tmp/results

DISCLAIMER
----------
RESEARCH / EDUCATIONAL PURPOSES ONLY.
NOT INVESTMENT ADVICE.
PAST PERFORMANCE DOES NOT GUARANTEE FUTURE RESULTS.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_real_data_backtest",
        description=(
            "Alpha Search — real OHLCV backtesting pipeline. "
            "Fetches market data, runs momentum / mean-reversion / breakout strategies, "
            "and exports metrics + figures to output-dir."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    data_group = p.add_mutually_exclusive_group()
    data_group.add_argument(
        "--universe",
        choices=["us_large_cap", "india_equity", "crypto", "all"],
        default="us_large_cap",
        help="Pre-defined symbol universe to backtest.",
    )
    data_group.add_argument(
        "--csv-file",
        metavar="PATH",
        help=(
            "Path to a CSV file with columns: timestamp,symbol,open,high,low,close,volume. "
            "Overrides --universe; no live download is performed."
        ),
    )

    p.add_argument(
        "--period",
        default="2y",
        metavar="PERIOD",
        help="yfinance history period (e.g. 1y, 2y, 5y, max). Ignored when --csv-file is used.",
    )
    p.add_argument(
        "--interval",
        default="1d",
        metavar="INTERVAL",
        help="Bar interval (e.g. 1d, 1h, 30m). Ignored when --csv-file is used.",
    )
    p.add_argument(
        "--output-dir",
        default="outputs/research_runs",
        metavar="DIR",
        help="Base directory for timestamped output folders.",
    )
    p.add_argument(
        "--cost-bps",
        type=float,
        default=10.0,
        metavar="BPS",
        help="Round-trip commission in basis points (10 bps = 0.10%%).",
    )
    p.add_argument(
        "--slippage-bps",
        type=float,
        default=10.0,
        metavar="BPS",
        help="Slippage per trade in basis points.",
    )
    p.add_argument(
        "--json-summary",
        action="store_true",
        help="Print a JSON summary to stdout after completion (in addition to normal logging).",
    )
    p.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity.",
    )
    return p


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _print_banner() -> None:
    print()
    print("=" * 65)
    print("  Alpha Search — Real Data Backtesting Pipeline")
    print("=" * 65)
    print(
        "  DISCLAIMER: Research / educational purposes only.\n"
        "  NOT investment advice. Past performance does not guarantee\n"
        "  future results."
    )
    print("=" * 65)
    print()


def _print_run_summary(results: dict) -> None:
    """Human-readable summary table printed after the run."""
    print()
    print("=" * 65)
    print("  Run Summary")
    print("=" * 65)
    print(f"  Universe       : {results.get('universe', 'csv')}")
    print(f"  Period         : {results.get('period', 'n/a')}")
    print(f"  Interval       : {results.get('interval', 'n/a')}")
    succeeded = results.get("symbols_succeeded", [])
    failed = results.get("symbols_failed", [])
    print(f"  Symbols OK     : {len(succeeded)}")
    if failed:
        print(f"  Symbols FAILED : {len(failed)}  ({', '.join(failed[:8])}{'...' if len(failed) > 8 else ''})")
    print()

    for strat in ("momentum", "mean_reversion", "breakout"):
        r = results.get(strat, {})
        verdict = r.get("verdict", "n/a")
        avg_sharpe = r.get("avg_sharpe")
        sharpe_str = f"{avg_sharpe:.3f}" if avg_sharpe is not None else "n/a"
        n_symbols = len(r.get("backtest_results", {}))
        print(f"  {strat:<18} verdict={verdict:<12}  avg_sharpe={sharpe_str}  symbols={n_symbols}")

    out_dir = results.get("output_dir")
    if out_dir:
        print()
        print(f"  Output dir : {out_dir}")
    print("=" * 65)
    print()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.log_level)
    _print_banner()

    # Resolve output dir relative to cwd
    output_dir = str(Path(args.output_dir).resolve())

    # Import here so startup is fast even if numpy/pandas are slow to load
    try:
        from alpha_search.research.real_data_pipeline import (
            UNIVERSES,
            load_csv_ohlcv,
            run_real_data_research,
        )
    except ImportError as exc:
        logging.getLogger(__name__).error(
            "Failed to import alpha_search: %s\n"
            "Make sure you have installed the package: pip install -e .",
            exc,
        )
        return 2

    if args.csv_file:
        # CSV fallback path: no live download
        csv_path = str(Path(args.csv_file).resolve())
        logging.getLogger(__name__).info("Loading OHLCV from CSV: %s", csv_path)
        results = run_real_data_research(
            universe="csv",
            period=args.period,
            interval=args.interval,
            output_dir=output_dir,
            transaction_cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            csv_fallback_path=csv_path,
        )
    else:
        universe = args.universe
        symbols = UNIVERSES.get(universe, [])
        logging.getLogger(__name__).info(
            "Starting backtest | universe=%s (%d symbols) | period=%s | interval=%s",
            universe,
            len(symbols),
            args.period,
            args.interval,
        )
        results = run_real_data_research(
            universe=universe,
            period=args.period,
            interval=args.interval,
            output_dir=output_dir,
            transaction_cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
        )

    _print_run_summary(results)

    if args.json_summary:
        # Emit machine-readable summary; strip non-serialisable objects
        summary = {
            "universe": results.get("universe"),
            "period": results.get("period"),
            "symbols_succeeded": results.get("symbols_succeeded", []),
            "symbols_failed": results.get("symbols_failed", []),
            "momentum_verdict": results.get("momentum", {}).get("verdict"),
            "momentum_avg_sharpe": results.get("momentum", {}).get("avg_sharpe"),
            "mean_reversion_verdict": results.get("mean_reversion", {}).get("verdict"),
            "mean_reversion_avg_sharpe": results.get("mean_reversion", {}).get("avg_sharpe"),
            "breakout_verdict": results.get("breakout", {}).get("verdict"),
            "breakout_avg_sharpe": results.get("breakout", {}).get("avg_sharpe"),
            "output_dir": results.get("output_dir"),
            "duration_seconds": results.get("duration_seconds"),
        }
        print(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
