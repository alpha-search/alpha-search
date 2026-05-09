"""Alpha Search -- Swarm Pipeline Integration.

Bridges the real data pipeline (:mod:`alpha_search.research.real_data_pipeline`)
with the agent swarm collaboration system (:mod:`alpha_search.agents`) to
produce a unified research output.

Pipeline stages:
    1. Fetch real market data (US + India equities via YFinance)
    2. Run sentiment analysis (FinBERT)
    3. Run real-data pipeline strategies (momentum / mean-reversion / arbitrage)
    4. Run agent swarm collaboration on the same data
    5. Combine pipeline and swarm results
    6. Generate reports (StrategyReportGenerator + AgentSwarmReportGenerator)
    7. Log everything to persistent memory
    8. Print combined console summary

DISCLAIMER: This pipeline is for research and educational purposes only.
All outputs are labelled as "research/educational only" and should not be
construed as investment advice.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd

# -- Agent Swarm imports -------------------------------------------------------
from alpha_search.agents import (
    AgentSwarm,
    DataEngineerAgent,
    OpportunityAgent,
    QuantEngineerAgent,
    ResearchAgent,
    RiskManagerAgent,
)

# -- Memory layer --------------------------------------------------------------
from alpha_search.memory import AgentJournal, MemoryStore
from alpha_search.memory.models import StrategyMemory
from alpha_search.research.agent_report import AgentSwarmReportGenerator

# -- Real Data Pipeline imports ------------------------------------------------
from alpha_search.research.real_data_pipeline import (
    COST_MODEL,
    INDIA_TOP20,
    US_TOP20,
    build_portfolio,
    fetch_real_data,
    run_arbitrage_strategy,
    run_mean_reversion_strategy,
    run_momentum_strategy,
    run_sentiment_analysis,
)

# -- Report generators ---------------------------------------------------------
from alpha_search.research.strategy_report import StrategyReportGenerator

logger = logging.getLogger("alpha_search.swarm_pipeline")

# Standard disclaimer
DISCLAIMER: str = (
    "RESEARCH / EDUCATIONAL PURPOSES ONLY. "
    "NOT INVESTMENT ADVICE. PAST PERFORMANCE DOES NOT GUARANTEE FUTURE RESULTS."
)


# ===========================================================================
# 1. Agent Swarm Setup
# ===========================================================================

def create_agent_swarm() -> AgentSwarm:
    """Create and configure a fully-registered :class:`AgentSwarm`.

    Registers all five specialised agents:

    * **data_engineer** — :class:`DataEngineerAgent`
    * **quant_engineer** — :class:`QuantEngineerAgent`
    * **risk_manager** — :class:`RiskManagerAgent`
    * **research_agent** — :class:`ResearchAgent`
    * **opportunity_agent** — :class:`OpportunityAgent`

    Returns
    -------
    AgentSwarm
        Fully-registered swarm ready for :meth:`run_collaboration`.
    """
    swarm = AgentSwarm()

    # Inject FinBERT sentiment analyser into ResearchAgent if available
    sentiment_analyzer = None
    try:
        from alpha_search.sentiment.finbert import FinBERTSentimentAnalyzer

        sentiment_analyzer = FinBERTSentimentAnalyzer()
    except Exception as exc:
        logger.debug("FinBERT not available for ResearchAgent: %s", exc)

    swarm.register("data_engineer", DataEngineerAgent())
    swarm.register("quant_engineer", QuantEngineerAgent())
    swarm.register("risk_manager", RiskManagerAgent())
    swarm.register("research_agent", ResearchAgent(sentiment_analyzer=sentiment_analyzer))
    swarm.register("opportunity_agent", OpportunityAgent())

    logger.info("AgentSwarm created with %d agents", len(swarm.agents))
    return swarm


# ===========================================================================
# 2. Swarm Pipeline Orchestrator
# ===========================================================================

def run_swarm_pipeline(
    output_dir: str = "reports",
) -> dict:
    """Execute the complete swarm-integrated real-data research pipeline.

    This is the main entry point.  It orchestrates:

    1. Data fetching for US_TOP20 + INDIA_TOP20 tickers
    2. Sentiment analysis
    3. Pipeline strategy research (momentum / mean-reversion / arbitrage)
    4. Agent swarm collaboration on the same data
    5. Result combination and report generation
    6. Persistent memory logging

    Parameters
    ----------
    output_dir:
        Directory for output reports (created if it does not exist).

    Returns
    -------
    dict
        Unified result dictionary with keys:

        * ``pipeline_results`` — results from the real-data pipeline
        * ``swarm_results`` — results from the agent swarm
        * ``reports`` — paths to generated reports
        * ``disclaimer`` — standard disclaimer string
    """
    os.makedirs(output_dir, exist_ok=True)
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("Alpha Search Swarm Pipeline Starting")
    logger.info("Timestamp: %s", start_time.isoformat())
    logger.info("=" * 60)

    # Determine date range: last 6 months
    end_date = start_time.date()
    start_date = end_date - timedelta(days=180)
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    # ------------------------------------------------------------------
    # 1. Fetch US data
    # ------------------------------------------------------------------
    logger.info("--- Fetching US equity data (%d tickers) ---", len(US_TOP20))
    us_prices = fetch_real_data(US_TOP20, start_str, end_str)
    us_tickers_fetched = (
        list(us_prices.columns.get_level_values(0).unique())
        if not us_prices.empty and us_prices.columns.nlevels >= 2
        else []
    )

    # ------------------------------------------------------------------
    # 2. Fetch India data
    # ------------------------------------------------------------------
    logger.info("--- Fetching India equity data (%d tickers) ---", len(INDIA_TOP20))
    india_prices = fetch_real_data(INDIA_TOP20, start_str, end_str)
    india_tickers_fetched = (
        list(india_prices.columns.get_level_values(0).unique())
        if not india_prices.empty and india_prices.columns.nlevels >= 2
        else []
    )

    # Combine US + India prices for the swarm
    combined_prices = _combine_price_frames(us_prices, india_prices)
    all_tickers = list(set(us_tickers_fetched + india_tickers_fetched))

    logger.info(
        "Combined data: %d tickers, %d rows",
        len(all_tickers),
        len(combined_prices),
    )

    # ------------------------------------------------------------------
    # 3. Run sentiment analysis
    # ------------------------------------------------------------------
    logger.info("--- Running sentiment analysis ---")
    sentiment_results = run_sentiment_analysis(all_tickers)

    # ------------------------------------------------------------------
    # 4. Run pipeline strategies on US data
    # ------------------------------------------------------------------
    pipeline_results: Dict[str, Any] = {
        "us_data": {
            "tickers_requested": len(US_TOP20),
            "tickers_fetched": len(us_tickers_fetched),
            "rows": len(us_prices),
        },
        "india_data": {
            "tickers_requested": len(INDIA_TOP20),
            "tickers_fetched": len(india_tickers_fetched),
            "rows": len(india_prices),
        },
        "sentiment": sentiment_results,
        "disclaimer": DISCLAIMER,
    }

    if not us_prices.empty:
        us_tickers = us_tickers_fetched

        logger.info("--- Running pipeline: momentum (US) ---")
        momentum_result = run_momentum_strategy(us_prices, us_tickers)
        pipeline_results["momentum"] = momentum_result

        logger.info("--- Running pipeline: mean-reversion (US) ---")
        mr_result = run_mean_reversion_strategy(us_prices, us_tickers)
        pipeline_results["mean_reversion"] = mr_result

        logger.info("--- Running pipeline: arbitrage (US) ---")
        arb_result = run_arbitrage_strategy(us_prices, us_tickers)
        pipeline_results["arbitrage"] = arb_result

        # ------------------------------------------------------------------
        # 5. Build portfolio from pipeline metrics
        # ------------------------------------------------------------------
        logger.info("--- Building portfolio from pipeline metrics ---")
        all_metrics_frames: List[pd.DataFrame] = []
        for sr in [momentum_result, mr_result, arb_result]:
            mdf = sr.get("metrics_df", pd.DataFrame())
            if not mdf.empty:
                all_metrics_frames.append(mdf)

        if all_metrics_frames:
            combined_metrics = pd.concat(all_metrics_frames, ignore_index=True)
            portfolio_result = build_portfolio(combined_metrics)
            pipeline_results["portfolio"] = portfolio_result
        else:
            pipeline_results["portfolio"] = {
                "allocations": {},
                "risk_metrics": {},
                "summary": "No metrics available for portfolio construction",
            }
    else:
        logger.warning("No US data available -- skipping pipeline strategies")
        pipeline_results["momentum"] = {
            "metrics_df": pd.DataFrame(),
            "verdict": "needs_more_testing",
        }
        pipeline_results["mean_reversion"] = {
            "metrics_df": pd.DataFrame(),
            "verdict": "needs_more_testing",
        }
        pipeline_results["arbitrage"] = {
            "metrics_df": pd.DataFrame(),
            "verdict": "needs_more_testing",
        }
        pipeline_results["portfolio"] = {"allocations": {}, "risk_metrics": {}}

    # ------------------------------------------------------------------
    # 6. Run agent swarm collaboration
    # ------------------------------------------------------------------
    logger.info("--- Running Agent Swarm collaboration ---")
    swarm_results: Dict[str, Any] = {}

    try:
        swarm = create_agent_swarm()

        if not combined_prices.empty and all_tickers:
            swarm_output = swarm.run_collaboration(
                tickers=all_tickers,
                prices=combined_prices,
            )
            swarm_results = swarm_output
            logger.info(
                "AgentSwarm complete (run_id=%s). Critiques: %d, Improvements: %d",
                swarm_results.get("run_id", "N/A"),
                len(swarm_results.get("critiques", [])),
                len(swarm_results.get("improvements", [])),
            )
        else:
            logger.warning("No combined price data -- skipping swarm collaboration")
            swarm_results = {
                "run_id": "skipped",
                "strategies": [],
                "critiques": [],
                "improvements": [],
                "consensus": "No data available for swarm collaboration.",
                "memory_records": [],
            }
    except Exception as exc:
        logger.error("AgentSwarm collaboration failed: %s", exc)
        swarm_results = {
            "run_id": "error",
            "strategies": [],
            "critiques": [],
            "improvements": [],
            "consensus": f"Swarm error: {exc}",
            "memory_records": [],
        }

    # ------------------------------------------------------------------
    # 7. Generate reports
    # ------------------------------------------------------------------
    logger.info("--- Generating reports ---")
    reports: Dict[str, str] = {}

    # Pipeline report via StrategyReportGenerator
    try:
        pipeline_report_gen = StrategyReportGenerator(
            results=pipeline_results,
            output_dir=output_dir,
        )
        pipeline_report_paths = pipeline_report_gen.generate_all()
        # Use the markdown path as the primary pipeline report
        reports["pipeline_report"] = pipeline_report_paths.get(
            "markdown",
            os.path.join(output_dir, "alpha_search_strategy_research_report.md"),
        )
        logger.info("Pipeline report generated: %s", reports["pipeline_report"])
    except Exception as exc:
        logger.warning("Pipeline report generation failed: %s", exc)
        reports["pipeline_report"] = ""

    # Swarm report via AgentSwarmReportGenerator
    try:
        swarm_report_gen = AgentSwarmReportGenerator(
            results=swarm_results,
            output_dir=output_dir,
        )
        swarm_report_paths = swarm_report_gen.generate_all()
        reports["swarm_report"] = swarm_report_paths.get(
            "markdown",
            os.path.join(output_dir, "agent_swarm_report_unknown.md"),
        )
        logger.info("Swarm report generated: %s", reports["swarm_report"])
    except Exception as exc:
        logger.warning("Swarm report generation failed: %s", exc)
        reports["swarm_report"] = ""

    # ------------------------------------------------------------------
    # 8. Log combined results to memory
    # ------------------------------------------------------------------
    logger.info("--- Logging results to memory ---")
    memory_logged = False
    try:
        _log_combined_results(pipeline_results, swarm_results)
        memory_logged = True
    except Exception as exc:
        logger.warning("Memory logging error: %s", exc)

    # ------------------------------------------------------------------
    # 9. Assemble unified result
    # ------------------------------------------------------------------
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    unified_result: Dict[str, Any] = {
        "pipeline_results": pipeline_results,
        "swarm_results": swarm_results,
        "reports": reports,
        "disclaimer": DISCLAIMER,
        "pipeline_start": start_time.isoformat(),
        "pipeline_end": end_time.isoformat(),
        "duration_seconds": duration,
        "memory_logged": memory_logged,
    }

    # Also save a combined markdown report
    try:
        combined_report_path = os.path.join(output_dir, "swarm_pipeline_combined_report.md")
        _write_combined_markdown_report(combined_report_path, unified_result)
        reports["combined_report"] = combined_report_path
        logger.info("Combined report written to %s", combined_report_path)
    except Exception as exc:
        logger.warning("Combined report writing failed: %s", exc)

    logger.info("=" * 60)
    logger.info("Swarm Pipeline Complete in %.1f seconds", duration)
    logger.info("=" * 60)

    return unified_result


# ===========================================================================
# 3. Console Summary
# ===========================================================================

def print_combined_summary(
    results: dict,
) -> None:
    """Print a beautifully formatted console summary of combined results.

    Displays both pipeline results and swarm results in a unified view.

    Parameters
    ----------
    results:
        The unified results dictionary returned by :func:`run_swarm_pipeline`.
    """
    print("\n" + "=" * 72)
    print("   ALPHA SEARCH -- SWARM PIPELINE INTEGRATION SUMMARY")
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

    # ---- Pipeline Results ------------------------------------------------
    pipeline = results.get("pipeline_results", {})

    # Data
    us_data = pipeline.get("us_data", {})
    india_data = pipeline.get("india_data", {})
    print("\n   --- DATA FETCHING ---")
    print(f"   US tickers:    {us_data.get('tickers_fetched', 0)}/{us_data.get('tickers_requested', 0)} fetched")
    print(f"   India tickers: {india_data.get('tickers_fetched', 0)}/{india_data.get('tickers_requested', 0)} fetched")

    # Sentiment
    sentiment = pipeline.get("sentiment", {})
    if sentiment:
        avg_score = sum(s.get("score", 0) for s in sentiment.values()) / max(len(sentiment), 1)
        most_bullish = max(sentiment.items(), key=lambda x: x[1].get("score", 0))
        most_bearish = min(sentiment.items(), key=lambda x: x[1].get("score", 0))
        print("\n   --- SENTIMENT (FinBERT) ---")
        print(f"   Tickers analysed: {len(sentiment)}")
        print(f"   Average score:    {avg_score:+.3f}")
        print(f"   Most bullish:     {most_bullish[0]} ({most_bullish[1].get('score', 0):+.3f})")
        print(f"   Most bearish:     {most_bearish[0]} ({most_bearish[1].get('score', 0):+.3f})")

    # Pipeline strategies
    for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
        sr = pipeline.get(strategy_name, {})
        metrics_df = sr.get("metrics_df", pd.DataFrame())
        verdict = sr.get("verdict", "N/A")
        top_picks = sr.get("top_picks", [])

        print(f"\n   --- PIPELINE: {strategy_name.upper()} ---")
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

    # Pipeline portfolio
    portfolio = pipeline.get("portfolio", {})
    if portfolio and portfolio.get("allocations"):
        print("\n   --- PIPELINE: PORTFOLIO ---")
        for method_name, weights in portfolio["allocations"].items():
            weight_str = ", ".join(f"{k}={v:.1%}" for k, v in weights.items())
            print(f"   {method_name:15s}: {weight_str}")

    # ---- Swarm Results ---------------------------------------------------
    swarm = results.get("swarm_results", {})
    run_id = swarm.get("run_id", "N/A")
    critiques = swarm.get("critiques", [])
    improvements = swarm.get("improvements", [])
    consensus = swarm.get("consensus", "")
    strategies = swarm.get("strategies", [])

    print("\n   --- AGENT SWARM COLLABORATION ---")
    print(f"   Run ID:       {run_id}")
    print(f"   Strategies:   {len(strategies)}")
    print(f"   Critiques:    {len(critiques)}")
    print(f"   Improvements: {len(improvements)}")

    # Critique severity breakdown
    if critiques:
        critical = sum(1 for c in critiques if c.get("severity") == "critical")
        warning = sum(1 for c in critiques if c.get("severity") == "warning")
        info = sum(1 for c in critiques if c.get("severity") == "info")
        print(f"   [CRIT]: {critical}  [WARN]: {warning}  [INFO]: {info}")

    # Consensus preview
    if consensus:
        consensus_lines = consensus.splitlines()
        print("\n   --- CONSENSUS ---")
        for line in consensus_lines[:15]:
            print(f"   {line}")
        if len(consensus_lines) > 15:
            print(f"   ... ({len(consensus_lines) - 15} more lines)")

    # ---- Reports ---------------------------------------------------------
    reports = results.get("reports", {})
    print("\n   --- REPORTS ---")
    for report_name, report_path in reports.items():
        if report_path:
            print(f"   {report_name:20s}: {report_path}")

    # Memory
    print("\n   --- MEMORY ---")
    print(f"   Logged to persistent memory: {results.get('memory_logged', False)}")

    print("\n" + "=" * 72)
    print(f"   END OF REPORT -- {disclaimer}")
    print("=" * 72 + "\n")


# ===========================================================================
# 4. Internal Helpers
# ===========================================================================

def _combine_price_frames(
    us_prices: pd.DataFrame,
    india_prices: pd.DataFrame,
) -> pd.DataFrame:
    """Combine US and India price DataFrames into a single frame.

    Parameters
    ----------
    us_prices:
        MultiIndex DataFrame with US ticker data.
    india_prices:
        MultiIndex DataFrame with India ticker data.

    Returns
    -------
    pandas.DataFrame
        Combined DataFrame with all tickers.  Empty if both inputs are empty.
    """
    frames: List[pd.DataFrame] = []

    if not us_prices.empty:
        frames.append(us_prices)
    if not india_prices.empty:
        frames.append(india_prices)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, axis=1)
    # Drop duplicate columns (should not happen with distinct tickers)
    combined = combined.loc[:, ~combined.columns.duplicated()]
    combined = combined.sort_index(axis=1)

    return combined


def _log_combined_results(
    pipeline_results: dict,
    swarm_results: dict,
    db_path: str = "memory/alpha_search_research.duckdb",
) -> None:
    """Log both pipeline and swarm results to the persistent memory layer.

    Uses :class:`MemoryStore` for structured storage and
    :class:`AgentJournal` for dual-write (DB + Markdown) logging.

    Parameters
    ----------
    pipeline_results:
        Results dictionary from the real-data pipeline.
    swarm_results:
        Results dictionary from the agent swarm.
    db_path:
        Path to the DuckDB/SQLite memory database.
    """
    try:
        store = MemoryStore(db_path=db_path)
        store.initialize()
        journal = AgentJournal(store=store, journal_dir="memory")

        run_timestamp = datetime.now(timezone.utc)

        # Log pipeline execution
        journal.log_task(
            agent_name="swarm_pipeline",
            task="Swarm-integrated pipeline execution",
            status="completed",
            notes=(
                f"Timestamp: {run_timestamp.isoformat()}. "
                f"Pipeline strategies: momentum, mean_reversion, arbitrage. "
                f"Swarm run_id: {swarm_results.get('run_id', 'N/A')}."
            ),
            tags=["research", "swarm_pipeline", "real_data"],
        )

        # Log each pipeline strategy result
        for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
            strategy_result = pipeline_results.get(strategy_name, {})
            metrics_df = strategy_result.get("metrics_df", pd.DataFrame())
            if metrics_df is None or metrics_df.empty:
                continue

            avg_sharpe = (
                metrics_df["sharpe_ratio"].mean()
                if "sharpe_ratio" in metrics_df.columns
                else 0.0
            )
            avg_drawdown = (
                metrics_df["max_drawdown"].mean()
                if "max_drawdown" in metrics_df.columns
                else 0.0
            )
            avg_return = (
                metrics_df["total_return"].mean()
                if "total_return" in metrics_df.columns
                else 0.0
            )
            verdict = strategy_result.get("verdict", "watch")
            hypothesis = strategy_result.get("hypothesis", "")
            risks = strategy_result.get("risks", [])
            top_picks = strategy_result.get("top_picks", [])

            memory = StrategyMemory(
                strategy_name=f"{strategy_name}_swarm_pipeline",
                strategy_type=strategy_name,
                market="US+India",
                asset_class="equity",
                universe=(
                    metrics_df["ticker"].tolist()
                    if "ticker" in metrics_df.columns
                    else []
                )[:20],
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
                win_rate=None,
                turnover=None,
                transaction_cost_assumption=str(COST_MODEL),
                validation_method="backtest_with_transaction_costs",
                verdict=verdict,
                rejection_reason="" if verdict != "rejected" else "; ".join(risks),
                lessons_learned="; ".join(risks),
            )
            journal.log_strategy_result(memory)

        # Log swarm collaboration result
        critiques = swarm_results.get("critiques", [])
        improvements = swarm_results.get("improvements", [])
        consensus = swarm_results.get("consensus", "")

        journal.log_task(
            agent_name="agent_swarm",
            task="Multi-agent swarm collaboration",
            status="completed",
            notes=(
                f"Run ID: {swarm_results.get('run_id', 'N/A')}. "
                f"Critiques: {len(critiques)}, Improvements: {len(improvements)}. "
                f"Consensus length: {len(consensus)} chars."
            ),
            tags=["swarm", "collaboration", "multi_agent"],
        )

        # Log swarm consensus as a decision
        if consensus:
            journal.log_decision(
                agent_name="agent_swarm",
                decision="Swarm consensus reached",
                rationale=consensus[:500],
                tags=["swarm", "consensus", "research"],
                importance_score=0.9,
            )

        # Log portfolio result
        portfolio = pipeline_results.get("portfolio", {})
        if portfolio and portfolio.get("allocations"):
            journal.log_decision(
                agent_name="portfolio_constructor",
                decision="Portfolio allocation computed",
                rationale=str(portfolio.get("summary", "")),
                tags=["portfolio", "allocation", "research"],
                importance_score=0.8,
            )

        # Log sentiment result
        sentiment = pipeline_results.get("sentiment", {})
        if sentiment:
            avg_score = (
                sum(s.get("score", 0) for s in sentiment.values())
                / max(len(sentiment), 1)
            )
            journal.log_task(
                agent_name="sentiment_analyzer",
                task="FinBERT sentiment analysis",
                status="completed",
                notes=f"Analysed {len(sentiment)} tickers. Avg sentiment score: {avg_score:.3f}.",
                tags=["sentiment", "finbert"],
            )

        store.close()
        logger.info("Combined results logged to memory at %s", db_path)

    except Exception as exc:
        logger.warning("Memory logging failed: %s", exc)


def _write_combined_markdown_report(
    path: str,
    results: dict,
) -> None:
    """Write a combined Markdown report covering both pipeline and swarm results.

    Parameters
    ----------
    path:
        File path to write the Markdown report.
    results:
        The unified results dictionary.
    """
    pipeline = results.get("pipeline_results", {})
    swarm = results.get("swarm_results", {})

    lines: List[str] = [
        "# Alpha Search -- Swarm Pipeline Integration Report",
        "",
        f"**Generated:** {results.get('pipeline_end', 'N/A')}  ",
        f"**Duration:** {results.get('duration_seconds', 0):.1f}s",
        "",
        "> **DISCLAIMER:** {}".format(results.get("disclaimer", "")),
        "",
        "---",
        "",
        "## 1. Data Fetching",
        "",
    ]

    us_data = pipeline.get("us_data", {})
    india_data = pipeline.get("india_data", {})
    lines.extend([
        f"- US equities: {us_data.get('tickers_fetched', 0)}/{us_data.get('tickers_requested', 0)} tickers fetched ({us_data.get('rows', 0)} rows)",
        f"- India equities: {india_data.get('tickers_fetched', 0)}/{india_data.get('tickers_requested', 0)} tickers fetched ({india_data.get('rows', 0)} rows)",
        "",
        "## 2. Sentiment Analysis (FinBERT)",
        "",
    ])

    sentiment = pipeline.get("sentiment", {})
    if sentiment:
        avg_score = sum(s.get("score", 0) for s in sentiment.values()) / max(len(sentiment), 1)
        lines.append(f"- Tickers analysed: {len(sentiment)}")
        lines.append(f"- Average sentiment score: {avg_score:+.3f}")
        lines.append("")
        lines.append("| Ticker | Score |")
        lines.append("|--------|-------|")
        for ticker, s in sorted(
            sentiment.items(), key=lambda x: abs(x[1].get("score", 0)), reverse=True
        )[:10]:
            score = s.get("score", 0)
            lines.append(f"| {ticker} | {score:+.3f} |")
        lines.append("")

    lines.extend([
        "## 3. Pipeline Strategies",
        "",
    ])

    for strategy_name in ["momentum", "mean_reversion", "arbitrage"]:
        sr = pipeline.get(strategy_name, {})
        hypothesis = sr.get("hypothesis", "")
        verdict = sr.get("verdict", "N/A")
        metrics_df = sr.get("metrics_df", pd.DataFrame())
        top_picks = sr.get("top_picks", [])

        lines.extend([
            f"### {strategy_name.replace('_', ' ').title()}",
            "",
            f"**Hypothesis:** {hypothesis}",
            "",
            f"**Verdict:** {verdict}",
            "",
        ])

        if not metrics_df.empty:
            lines.append("#### Performance Metrics")
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

    # Pipeline portfolio
    portfolio = pipeline.get("portfolio", {})
    if portfolio and portfolio.get("allocations"):
        lines.extend([
            "## 4. Portfolio Allocation",
            "",
        ])
        for method_name, weights in portfolio["allocations"].items():
            weight_str = ", ".join(f"{k}={v:.1%}" for k, v in weights.items())
            lines.append(f"- **{method_name}**: {weight_str}")
        lines.append("")

    # Swarm section
    lines.extend([
        "---",
        "",
        "## 5. Agent Swarm Collaboration",
        "",
        f"**Run ID:** `{swarm.get('run_id', 'N/A')}`",
        "",
        f"- Strategies: {len(swarm.get('strategies', []))}",
        f"- Critiques: {len(swarm.get('critiques', []))}",
        f"- Improvements: {len(swarm.get('improvements', []))}",
        "",
        "### Strategies",
        "",
    ])

    strategies = swarm.get("strategies", [])
    if strategies:
        lines.append("| ID | Name | Type |")
        lines.append("|---|---|---|")
        for strat in strategies:
            lines.append(
                f"| {strat.get('id', 'N/A')} "
                f"| {strat.get('name', 'N/A')} "
                f"| {strat.get('type', 'N/A')} |"
            )
    else:
        lines.append("No strategies generated.")
    lines.append("")

    # Critique stats
    critiques = swarm.get("critiques", [])
    if critiques:
        lines.extend([
            "### Critique Summary",
            "",
        ])
        critical = sum(1 for c in critiques if c.get("severity") == "critical")
        warning = sum(1 for c in critiques if c.get("severity") == "warning")
        info_c = sum(1 for c in critiques if c.get("severity") == "info")
        lines.extend([
            f"- Critical: {critical}",
            f"- Warning: {warning}",
            f"- Info: {info_c}",
            "",
        ])

    # Improvements
    improvements = swarm.get("improvements", [])
    if improvements:
        lines.extend([
            "### Improvements Applied",
            "",
        ])
        for imp in improvements:
            agent = imp.get("agent", "N/A")
            action = imp.get("action", "")
            impact = imp.get("impact", "")
            lines.append(f"- **{agent}**: {action}")
            if impact:
                lines.append(f"  - Impact: {impact}")
        lines.append("")

    # Consensus
    consensus = swarm.get("consensus", "")
    if consensus:
        lines.extend([
            "### Consensus",
            "",
            "```",
            consensus,
            "```",
            "",
        ])

    lines.extend([
        "---",
        "",
        "*This report is for research and educational purposes only.*",
        "",
        f"*Generated: {results.get('pipeline_end', 'N/A')}*",
        "",
    ])

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("Combined Markdown report written to %s", path)


# ===========================================================================
# 5. CLI Entry Point
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    print("\n" + "=" * 60)
    print("Alpha Search -- Swarm Pipeline Integration")
    print("=" * 60)
    print("DISCLAIMER: Research/educational purposes only.\n")

    results = run_swarm_pipeline()
    print_combined_summary(results)
