"""Alpha Search Research Pipelines — end-to-end strategy research.

This module provides complete research pipelines that wire together
existing Alpha Search components (signal generators, backtest engines,
portfolio constructors, and opportunity scoring) into cohesive
strategy discovery workflows.

Example::

    from alpha_search.research import run_all_pipelines

    results = run_all_pipelines(output_dir="reports")
    print(results["momentum"]["metrics"])
    print(results["mean_reversion"]["metrics"])
    print(results["arbitrage"]["metrics"])
"""

from __future__ import annotations

from alpha_search.research.sample_universes import (
    generate_us_equity_data,
    generate_indian_equity_data,
    generate_crypto_data,
    generate_etf_data,
)
from alpha_search.research.strategy_pipeline import (
    MomentumPipeline,
    MeanReversionPipeline,
    ArbitragePipeline,
    run_all_pipelines,
)
from alpha_search.research.strategy_report import (
    StrategyReportGenerator,
    generate_docx_report,
    generate_csv_summary,
)

__all__ = [
    # Sample data generators
    "generate_us_equity_data",
    "generate_indian_equity_data",
    "generate_crypto_data",
    "generate_etf_data",
    # Strategy pipelines
    "MomentumPipeline",
    "MeanReversionPipeline",
    "ArbitragePipeline",
    "run_all_pipelines",
    # Reporting
    "StrategyReportGenerator",
    "generate_docx_report",
    "generate_csv_summary",
]
