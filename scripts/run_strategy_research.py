#!/usr/bin/env python3
"""Alpha Search — Strategy Research Pipeline Runner.

Executes end-to-end research across momentum, mean reversion, and statistical
arbitrage strategies using the existing Alpha Search architecture.

Usage:
    python scripts/run_strategy_research.py

Outputs:
    reports/alpha_search_strategy_research_report.md
    reports/alpha_search_strategy_research_report.docx
    reports/strategy_results_summary.csv
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

# Ensure alpha_search is on path when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alpha_search.research.strategy_pipeline import run_all_pipelines
from alpha_search.research.strategy_report import StrategyReportGenerator
from alpha_search.memory import MemoryStore, AgentJournal
from alpha_search.memory.models import StrategyMemory


def main() -> None:
    """Run the complete strategy research pipeline and generate reports."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("alpha_search.research")

    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Alpha Search — Strategy Research Pipeline")
    logger.info("=" * 60)
    logger.info("Using synthetic/demo data for research purposes.")
    logger.info("Results are educational only — not investment advice.")
    logger.info("")

    # --- Step 1: Run all pipelines ---
    logger.info("[1/4] Running strategy pipelines...")
    results = run_all_pipelines(output_dir=output_dir)
    logger.info("      Momentum, Mean Reversion, Arbitrage complete.")

    # --- Step 2: Generate reports ---
    logger.info("[2/4] Generating reports (Markdown, CSV, DOCX)...")
    generator = StrategyReportGenerator(results, output_dir=output_dir)
    paths = generator.generate_all()
    logger.info(f"      Markdown: {paths.get('markdown', 'N/A')}")
    logger.info(f"      CSV:      {paths.get('csv', 'N/A')}")
    logger.info(f"      DOCX:     {paths.get('docx', 'N/A')}")

    # --- Step 3: Log to memory ---
    logger.info("[3/4] Logging results to persistent memory...")
    _log_to_memory(results)
    logger.info("      Strategy results stored in memory.")

    # --- Step 4: Print summary ---
    logger.info("[4/4] Pipeline complete.")
    logger.info("")
    logger.info("=" * 60)
    logger.info("OUTPUT FILES")
    logger.info("=" * 60)
    for fmt, path in paths.items():
        size = os.path.getsize(path) if path and os.path.exists(path) else 0
        logger.info(f"  {fmt:10s} {path} ({size:,} bytes)")
    logger.info("")
    logger.info("Disclaimer: All results use synthetic demo data.")
    logger.info("This is research/educational output — not investment advice.")


def _log_to_memory(results: dict) -> None:
    """Log strategy results to the Alpha Search persistent memory layer."""
    try:
        store = MemoryStore()
        store.initialize()
        journal = AgentJournal(store=store)

        timestamp = datetime.now(timezone.utc).isoformat()

        for strat_key in ("momentum", "mean_reversion", "arbitrage"):
            strat = results.get(strat_key, {})
            metrics_df = strat.get("metrics")
            if metrics_df is None or metrics_df.empty:
                continue

            # Compute average metrics across tickers
            avg_return = metrics_df["total_return"].mean() if "total_return" in metrics_df.columns else 0.0
            avg_sharpe = metrics_df["sharpe_ratio"].mean() if "sharpe_ratio" in metrics_df.columns else 0.0
            avg_dd = metrics_df["max_drawdown"].mean() if "max_drawdown" in metrics_df.columns else 0.0

            # Determine verdict
            verdict = "watch"
            rejection_reason = None
            if avg_sharpe < 0.3:
                verdict = "rejected"
                rejection_reason = f"Average Sharpe too low ({avg_sharpe:.2f}) for live deployment."
            elif avg_sharpe > 0.8 and avg_dd < 0.20:
                verdict = "accepted"
            elif avg_sharpe > 0.5:
                verdict = "needs_more_testing"

            universe = strat.get("tickers", [])
            tickers_sample = universe[:5] if len(universe) > 5 else universe

            memory = StrategyMemory(
                strategy_name=f"{strat_key.replace('_', ' ').title()} Strategy",
                strategy_type=strat_key if strat_key != "arbitrage" else "arbitrage",
                market="Global (US, India, Crypto)",
                asset_class="multi_asset",
                universe=tickers_sample,
                hypothesis=strat.get("hypothesis", ""),
                result_summary=f"Average return: {avg_return:.2%}, Sharpe: {avg_sharpe:.2f}, Max DD: {avg_dd:.2%}",
                sharpe=round(avg_sharpe, 4) if avg_sharpe else None,
                max_drawdown=round(avg_dd, 4) if avg_dd else None,
                total_return=round(avg_return, 4) if avg_return else None,
                validation_method="synthetic_backtest",
                verdict=verdict,
                rejection_reason=rejection_reason,
                lessons_learned="Synthetic data results. Need validation on real data before any deployment.",
            )
            journal.log_strategy_result(memory)

        # Log overall pipeline completion
        journal.log_decision(
            agent_name="Research Pipeline",
            decision=f"Completed 3-strategy research pipeline at {timestamp}",
            rationale="All pipelines executed. Results stored in reports/ directory.",
            tags=["research", "pipeline", "strategy"],
            importance_score=0.8,
        )
        store.close()
    except Exception as exc:
        logging.getLogger("alpha_search.research").warning(f"Memory logging skipped: {exc}")


if __name__ == "__main__":
    main()
