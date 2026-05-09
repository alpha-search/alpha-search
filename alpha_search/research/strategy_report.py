"""Strategy report generation utilities.

Provides tools to convert research pipeline results into human-readable
reports (DOCX documents) and machine-readable summaries (CSV files).

Example::

    from alpha_search.research import run_all_pipelines, generate_docx_report

    results = run_all_pipelines()
    generate_docx_report(results, "/mnt/agents/output/quant-os/reports/report.docx")
"""

from __future__ import annotations

import csv
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# StrategyReportGenerator
# ---------------------------------------------------------------------------

class StrategyReportGenerator:
    """Generate structured text and tabular reports from pipeline results.

    Parameters
    ----------
    results: dict
        The combined results dictionary returned by
        :func:`alpha_search.research.run_all_pipelines`.
    """

    def __init__(self, results: Dict[str, Any], output_dir: str = "reports") -> None:
        self.results = results
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt_pct(value: float) -> str:
        """Format a float as a percentage string."""
        if pd.isna(value) or not isinstance(value, (int, float)):
            return "N/A"
        return f"{value * 100:.2f}%"

    @staticmethod
    def _fmt_float(value: float, decimals: int = 4) -> str:
        """Format a float with given precision."""
        if pd.isna(value) or not isinstance(value, (int, float)):
            return "N/A"
        return f"{value:.{decimals}f}"

    def _render_metrics_table(self, pipeline_name: str) -> str:
        """Render a pipeline's metrics DataFrame as an ASCII table."""
        metrics = self.results.get(pipeline_name, {}).get("metrics")
        if metrics is None or metrics.empty:
            return f"  No metrics available for {pipeline_name}.\n"

        lines = []
        lines.append(f"  {'Ticker':<18} {'Total Ret':>10} {'Sharpe':>8} {'Max DD':>8} {'Win Rate':>8} {'Ann. Ret':>10} {'Vol':>8}")
        lines.append(f"  {'-' * 18} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 10} {'-' * 8}")

        for ticker, row in metrics.iterrows():
            lines.append(
                f"  {ticker:<18} "
                f"{self._fmt_pct(row.get('total_return', 0.0)):>10} "
                f"{self._fmt_float(row.get('sharpe_ratio', 0.0), 2):>8} "
                f"{self._fmt_pct(row.get('max_drawdown', 0.0)):>8} "
                f"{self._fmt_pct(row.get('win_rate', 0.0)):>8} "
                f"{self._fmt_pct(row.get('annualized_return', 0.0)):>10} "
                f"{self._fmt_pct(row.get('volatility', 0.0)):>8}"
            )
        lines.append("")
        return "\n".join(lines)

    def _render_opportunities(self, pipeline_name: str) -> str:
        """Render the top opportunities for a pipeline."""
        opp = self.results.get(pipeline_name, {}).get("opportunities")
        if opp is None or opp.empty:
            return "  No opportunities discovered.\n"

        lines = []
        lines.append(opp.head(10).to_string())
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def generate_text_report(self) -> str:
        """Generate a comprehensive plain-text report.

        Returns
        -------
        str
            Multi-line report covering all three pipelines.
        """
        lines: List[str] = [
            "=" * 72,
            "           ALPHA SEARCH — STRATEGY RESEARCH REPORT",
            "=" * 72,
            "",
            f"Report Directory: {self.results.get('output_dir', 'N/A')}",
            "",
            "NOTE: All results are based on SYNTHETIC / DEMO data for",
            "      research and educational purposes only.",
            "",
        ]

        # --- Momentum ---
        lines.extend([
            "-" * 72,
            "1. MOMENTUM (TREND-FOLLOWING) PIPELINE",
            "-" * 72,
            "",
            "Hypothesis:",
            f"  {self.results.get('momentum', {}).get('hypothesis', 'N/A')}",
            "",
            "Risks:",
        ])
        for risk in self.results.get("momentum", {}).get("risks", []):
            lines.append(f"  - {risk}")
        lines.extend([
            "",
            "Top Opportunities:",
            self._render_opportunities("momentum"),
            "",
            "Performance Metrics:",
            self._render_metrics_table("momentum"),
            "",
        ])

        # --- Mean Reversion ---
        lines.extend([
            "-" * 72,
            "2. MEAN-REVERSION PIPELINE",
            "-" * 72,
            "",
            "Hypothesis:",
            f"  {self.results.get('mean_reversion', {}).get('hypothesis', 'N/A')}",
            "",
            "Risks:",
        ])
        for risk in self.results.get("mean_reversion", {}).get("risks", []):
            lines.append(f"  - {risk}")
        lines.extend([
            "",
            "Top Opportunities:",
            self._render_opportunities("mean_reversion"),
            "",
            "Performance Metrics:",
            self._render_metrics_table("mean_reversion"),
            "",
        ])

        # --- Arbitrage ---
        lines.extend([
            "-" * 72,
            "3. STATISTICAL ARBITRAGE (PAIRS) PIPELINE",
            "-" * 72,
            "",
            "Hypothesis:",
            f"  {self.results.get('arbitrage', {}).get('hypothesis', 'N/A')}",
            "",
            "Risks:",
        ])
        for risk in self.results.get("arbitrage", {}).get("risks", []):
            lines.append(f"  - {risk}")
        lines.extend([
            "",
            "Top Pairs:",
        ])
        arb_opp = self.results.get("arbitrage", {}).get("opportunities")
        if arb_opp is not None and not arb_opp.empty:
            lines.append(arb_opp.head(10).to_string())
        else:
            lines.append("  No pairs discovered.")
        lines.extend([
            "",
            "Performance Metrics:",
            self._render_metrics_table("arbitrage"),
            "",
        ])

        # --- Combined Summary ---
        lines.extend([
            "-" * 72,
            "4. COMBINED SUMMARY (AVERAGE METRICS)",
            "-" * 72,
            "",
        ])
        combined = self.results.get("combined_metrics")
        if combined is not None and not combined.empty:
            lines.append(combined.to_string())
        else:
            lines.append("  No combined metrics available.")

        lines.extend([
            "",
            "=" * 72,
            "                         END OF REPORT",
            "=" * 72,
        ])

        return "\n".join(lines)

    def generate_csv_data(self) -> Dict[str, pd.DataFrame]:
        """Export each pipeline's metrics as a DataFrame.

        Returns
        -------
        dict[str, pd.DataFrame]
            Keys: ``momentum``, ``mean_reversion``, ``arbitrage``,
            ``combined_summary``.
        """
        return {
            "momentum": self.results.get("momentum", {}).get("metrics", pd.DataFrame()),
            "mean_reversion": self.results.get("mean_reversion", {}).get("metrics", pd.DataFrame()),
            "arbitrage": self.results.get("arbitrage", {}).get("metrics", pd.DataFrame()),
            "combined_summary": self.results.get("combined_metrics", pd.DataFrame()),
        }

    def generate_all(self) -> Dict[str, str]:
        """Generate all report formats (Markdown, CSV, DOCX).

        Returns
        -------
        dict[str, str]
            Paths to generated files with keys ``markdown``, ``csv``, ``docx``.
        """
        paths: Dict[str, str] = {}

        # Markdown report
        md_path = os.path.join(self.output_dir, "alpha_search_strategy_research_report.md")
        report_text = self.generate_text_report()
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(report_text)
        paths["markdown"] = md_path

        # CSV summary
        csv_paths = generate_csv_summary(self.results, self.output_dir)
        paths["csv"] = csv_paths[0] if csv_paths else ""

        # DOCX report (stub if python-docx not available)
        docx_path = os.path.join(self.output_dir, "alpha_search_strategy_research_report.docx")
        generate_docx_report(self.results, docx_path)
        paths["docx"] = docx_path

        return paths


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def generate_docx_report(
    results: Dict[str, Any],
    output_path: str,
) -> str:
    """Generate a DOCX report from pipeline results.

    .. note::
        This implementation generates a structured plain-text file with
        a ``.docx`` extension.  For true DOCX generation, install
        ``python-docx`` and subclass :class:`StrategyReportGenerator`.

    Parameters
    ----------
    results:
        Combined results from :func:`run_all_pipelines`.
    output_path:
        File path for the report (including ``.docx`` extension).

    Returns
    -------
    str
        The path to the written report file.
    """
    generator = StrategyReportGenerator(results)
    report_text = generator.generate_text_report()

    # Write as plain text (DOCX stub — can be upgraded with python-docx)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("ALPHA SEARCH STRATEGY RESEARCH REPORT\n")
        fh.write("=" * 72 + "\n\n")
        fh.write(report_text)

    logger.info("Report written to %s", output_path)
    return output_path


def generate_csv_summary(
    results: Dict[str, Any],
    output_dir: str,
) -> List[str]:
    """Write CSV summaries for each pipeline's metrics.

    Parameters
    ----------
    results:
        Combined results from :func:`run_all_pipelines`.
    output_dir:
        Directory where CSV files will be written.

    Returns
    -------
    list[str]
        Paths to the written CSV files.
    """
    os.makedirs(output_dir, exist_ok=True)
    generator = StrategyReportGenerator(results)
    csv_data = generator.generate_csv_data()

    written: List[str] = []
    for name, df in csv_data.items():
        if df is None or df.empty:
            continue
        path = os.path.join(output_dir, f"{name}_metrics.csv")
        df.to_csv(path, index=True)
        written.append(path)
        logger.info("CSV summary written: %s", path)

    return written
