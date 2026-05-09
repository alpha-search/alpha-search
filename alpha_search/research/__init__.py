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

from alpha_search.research.agent_report import (
    AgentSwarmReportGenerator,
)
from alpha_search.research.real_data_pipeline import (
    build_portfolio,
    fetch_real_data,
    print_summary,
    run_arbitrage_strategy,
    run_full_pipeline,
    run_mean_reversion_strategy,
    run_momentum_strategy,
    run_sentiment_analysis,
)
from alpha_search.research.sample_universes import (
    generate_crypto_data,
    generate_etf_data,
    generate_indian_equity_data,
    generate_us_equity_data,
)
from alpha_search.research.strategy_pipeline import (
    ArbitragePipeline,
    MeanReversionPipeline,
    MomentumPipeline,
    run_all_pipelines,
)
from alpha_search.research.strategy_report import (
    StrategyReportGenerator,
    generate_csv_summary,
    generate_docx_report,
)
from alpha_search.research.swarm_pipeline import (
    create_agent_swarm,
    print_combined_summary,
    run_swarm_pipeline,
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
    # Real data pipeline
    "run_full_pipeline",
    "print_summary",
    "fetch_real_data",
    "run_sentiment_analysis",
    "run_momentum_strategy",
    "run_mean_reversion_strategy",
    "run_arbitrage_strategy",
    "build_portfolio",
    # Agent swarm pipeline
    "run_swarm_pipeline",
    "create_agent_swarm",
    "print_combined_summary",
    # Reporting
    "StrategyReportGenerator",
    "AgentSwarmReportGenerator",
    "generate_docx_report",
    "generate_csv_summary",
]
