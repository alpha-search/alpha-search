"""Run the Indian ETF intraday momentum breakout research pipeline.

Usage:
    python -m alpha_search.research.indian_etf_intraday
    # or
    python scripts/run_indian_etf_breakout.py

Fetches real Indian ETF data (NIFTYBEES, BANKBEES, ITBEES, JUNIORBEES)
and runs the full noise-breakout backtest pipeline.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

from alpha_search.research.indian_etf_intraday import run_full_pipeline


def main() -> None:
    print("=" * 60)
    print("Alpha Search — Indian ETF Intraday Momentum Breakout")
    print("=" * 60)
    print()

    results = run_full_pipeline(output_dir="reports/indian_etf")

    print()
    print("=" * 60)
    print("Pipeline Complete")
    print("=" * 60)
    print(f"  Output directory: reports/indian_etf/")
    print(f"  Report:           reports/indian_etf/report.md")
    print(f"  Metrics CSV:      reports/indian_etf/strategy_metrics.csv")
    print(f"  Trade Log:        reports/indian_etf/trade_log.csv")
    print(f"  Parameters:       reports/indian_etf/parameter_results.csv")
    print()

    # Print summary
    best = results.get("best_result", {})
    if best:
        print(f"Best Result:")
        print(f"  ETF:          {best.get('etf', 'N/A')}")
        print(f"  Lookback:     {best.get('lookback', 'N/A')}")
        print(f"  Sharpe:       {best.get('sharpe_ratio', 0):.3f}")
        print(f"  Max Drawdown: {best.get('max_drawdown', 0):.1%}")
        print(f"  Total Return: {best.get('total_return', 0):.1%}")
        print()

    portfolio = results.get("portfolio_results", {})
    for method, metrics in portfolio.items():
        if metrics:
            print(f"Portfolio ({method}):")
            print(f"  Sharpe:       {metrics.get('sharpe_ratio', 0):.3f}")
            print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.1%}")
            print(f"  Total Return: {metrics.get('total_return', 0):.1%}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
