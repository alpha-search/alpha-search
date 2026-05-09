"""Agent Swarm report generation utilities.

Provides tools to convert AgentSwarm collaboration results into human-readable
reports (Markdown + plain text).

Example::

    from alpha_search.research.agent_report import AgentSwarmReportGenerator

    results = swarm.run_collaboration(tickers, prices)
    generator = AgentSwarmReportGenerator(results)
    generator.generate_all()
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AgentSwarmReportGenerator
# ---------------------------------------------------------------------------


class AgentSwarmReportGenerator:
    """Generate structured text and Markdown reports from AgentSwarm results.

    Parameters
    ----------
    results: dict
        The result dictionary returned by
        :meth:`alpha_search.agents.swarm.AgentSwarm.run_collaboration`.
    output_dir: str
        Directory where report files will be written.
    """

    def __init__(self, results: Dict[str, Any], output_dir: str = "reports") -> None:
        self.results = results
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Static helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt_severity_icon(severity: str, use_unicode: bool = False) -> str:
        """Map a severity string to a visual icon.

        Parameters
        ----------
        severity: str
            One of ``"critical"``, ``"warning"``, ``"info"``.
        use_unicode: bool
            When *True*, return emoji icons; otherwise ASCII tags.

        Returns
        -------
        str
            Formatted severity indicator.
        """
        mapping = {
            "critical": ("🔴", "[CRIT]"),
            "warning": ("🟡", "[WARN]"),
            "info": ("🟢", "[INFO]"),
        }
        uni, ascii_ = mapping.get(severity.lower(), ("⚪", "[?]"))
        return uni if use_unicode else ascii_

    @staticmethod
    def _count_critiques(critiques: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate critique statistics.

        Parameters
        ----------
        critiques: list[dict]
            List of critique dictionaries.

        Returns
        -------
        dict
            Aggregated counts:

            * ``total`` — total number of critiques
            * ``by_severity`` — Counter mapping severity -> count
            * ``by_type`` — Counter mapping critique_type -> count
            * ``by_from_agent`` — Counter mapping from_agent -> count
            * ``by_to_agent`` — Counter mapping to_agent -> count
        """
        if not critiques:
            return {
                "total": 0,
                "by_severity": Counter(),
                "by_type": Counter(),
                "by_from_agent": Counter(),
                "by_to_agent": Counter(),
            }

        df = pd.DataFrame(critiques)
        return {
            "total": len(critiques),
            "by_severity": Counter(df["severity"].value_counts().to_dict())
            if "severity" in df.columns
            else Counter(),
            "by_type": Counter(df["critique_type"].value_counts().to_dict())
            if "critique_type" in df.columns
            else Counter(),
            "by_from_agent": Counter(df["from_agent"].value_counts().to_dict())
            if "from_agent" in df.columns
            else Counter(),
            "by_to_agent": Counter(df["to_agent"].value_counts().to_dict())
            if "to_agent" in df.columns
            else Counter(),
        }

    # ------------------------------------------------------------------ #
    # Private renderers                                                  #
    # ------------------------------------------------------------------ #

    def _render_strategy_summary(self, use_unicode: bool = False) -> str:
        """Render the strategy summaries as a formatted table.

        Parameters
        ----------
        use_unicode: bool
            Whether to use Markdown formatting.

        Returns
        -------
        str
            Formatted strategy table.
        """
        strategies = self.results.get("strategies", [])
        if not strategies:
            return "  No strategies available.\n"

        lines: List[str] = []

        if use_unicode:
            lines.append("| ID | Name | Type | Key Parameters |")
            lines.append("|---|---|---|---|")
            for strat in strategies:
                key_params = self._extract_key_params(strat)
                lines.append(
                    f"| {strat.get('id', 'N/A')} "
                    f"| {strat.get('name', 'N/A')} "
                    f"| {strat.get('type', 'N/A')} "
                    f"| {key_params} |"
                )
        else:
            lines.append(
                f"  {'ID':<22} {'Name':<30} {'Type':<16} Key Parameters"
            )
            lines.append(
                f"  {'-' * 22} {'-' * 30} {'-' * 16} {'-' * 40}"
            )
            for strat in strategies:
                key_params = self._extract_key_params(strat)
                lines.append(
                    f"  {strat.get('id', 'N/A'):<22} "
                    f"{strat.get('name', 'N/A'):<30} "
                    f"{strat.get('type', 'N/A'):<16} "
                    f"{key_params}"
                )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _extract_key_params(strategy: Dict[str, Any]) -> str:
        """Extract key parameters for a strategy (excluding id, name, type).

        Parameters
        ----------
        strategy: dict
            Strategy dictionary.

        Returns
        -------
        str
            Comma-separated key=value pairs.
        """
        skip_keys = {"id", "name", "type"}
        parts = []
        for key, value in strategy.items():
            if key in skip_keys:
                continue
            if isinstance(value, float):
                parts.append(f"{key}={value:.2f}")
            elif isinstance(value, bool):
                parts.append(f"{key}={value}")
            else:
                parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else "N/A"

    def _render_critique_stats(
        self, counts: Dict[str, Any], use_unicode: bool = False
    ) -> str:
        """Render critique statistics.

        Parameters
        ----------
        counts: dict
            Output from :meth:`_count_critiques`.
        use_unicode: bool
            Whether to use Markdown formatting.

        Returns
        -------
        str
            Formatted statistics block.
        """
        lines: List[str] = []

        # Total
        lines.append(f"  Total Critiques: {counts['total']}")
        lines.append("")

        # By severity
        if use_unicode:
            lines.append("**By Severity:**")
            lines.append("")
            lines.append("| Severity | Count |")
            lines.append("|---|---|")
            order = [("critical", "🔴"), ("warning", "🟡"), ("info", "🟢")]
            for sev, icon in order:
                c = counts["by_severity"].get(sev, 0)
                lines.append(f"| {icon} {sev.capitalize()} | {c} |")
            # Any unlisted severities
            for sev, c in counts["by_severity"].items():
                if sev not in {"critical", "warning", "info"}:
                    lines.append(f"| {sev.capitalize()} | {c} |")
        else:
            lines.append("  By Severity:")
            for sev in ["critical", "warning", "info"]:
                icon = self._fmt_severity_icon(sev, use_unicode=False)
                c = counts["by_severity"].get(sev, 0)
                lines.append(f"    {icon} {sev.capitalize():<10} : {c}")
        lines.append("")

        # By type
        if use_unicode:
            lines.append("**By Type:**")
            lines.append("")
            lines.append("| Type | Count |")
            lines.append("|---|---|")
            for typ, c in counts["by_type"].most_common():
                lines.append(f"| {typ} | {c} |")
        else:
            lines.append("  By Type:")
            for typ, c in counts["by_type"].most_common():
                lines.append(f"    {typ:<22} : {c}")
        lines.append("")

        # By from_agent
        if use_unicode:
            lines.append("**By From-Agent:**")
            lines.append("")
            lines.append("| Agent | Count |")
            lines.append("|---|---|")
            for agent, c in counts["by_from_agent"].most_common():
                lines.append(f"| {agent} | {c} |")
        else:
            lines.append("  By From-Agent:")
            for agent, c in counts["by_from_agent"].most_common():
                lines.append(f"    {agent:<22} : {c}")
        lines.append("")

        return "\n".join(lines)

    def _render_critique_log(
        self, critiques: List[Dict[str, Any]], use_unicode: bool = False
    ) -> str:
        """Render the full critique log sorted by severity.

        Critical entries appear first, then warning, then info.

        Parameters
        ----------
        critiques: list[dict]
            List of critique dictionaries.
        use_unicode: bool
            Whether to use Markdown formatting.

        Returns
        -------
        str
            Formatted critique log.
        """
        if not critiques:
            return "  No critiques recorded.\n"

        severity_order = {"critical": 0, "warning": 1, "info": 2}
        sorted_critiques = sorted(
            critiques,
            key=lambda c: severity_order.get(
                c.get("severity", "").lower(), 99
            ),
        )

        lines: List[str] = []
        for i, crit in enumerate(sorted_critiques, 1):
            sev = crit.get("severity", "info")
            icon = self._fmt_severity_icon(sev, use_unicode=use_unicode)
            from_a = crit.get("from_agent", "N/A")
            to_a = crit.get("to_agent", "N/A")
            typ = crit.get("critique_type", "N/A")
            msg = crit.get("message", "")
            sugg = crit.get("suggestion", "")
            ts = crit.get("timestamp", "")

            if use_unicode:
                lines.append(
                    f"{i}. **{icon} [{sev.upper()}]** "
                    f"`{from_a}` -> `{to_a}` (*{typ}*)"
                )
                lines.append(f"   - **Message:** {msg}")
                if sugg:
                    lines.append(f"   - **Suggestion:** {sugg}")
                if ts:
                    lines.append(f"   - **Timestamp:** {ts}")
                lines.append("")
            else:
                lines.append(
                    f"  [{i:>3}] {icon} [{sev.upper():<8}] "
                    f"{from_a:<18} -> {to_a:<18} ({typ})"
                )
                lines.append(f"        Message    : {msg}")
                if sugg:
                    lines.append(f"        Suggestion : {sugg}")
                if ts:
                    lines.append(f"        Timestamp  : {ts}")
                lines.append("")

        return "\n".join(lines)

    def _render_improvements(
        self, improvements: List[Dict[str, Any]], use_unicode: bool = False
    ) -> str:
        """Render applied improvements.

        Parameters
        ----------
        improvements: list[dict]
            List of improvement dictionaries.
        use_unicode: bool
            Whether to use Markdown formatting.

        Returns
        -------
        str
            Formatted improvements block.
        """
        if not improvements:
            return "  No improvements applied.\n"

        lines: List[str] = []
        for i, imp in enumerate(improvements, 1):
            agent = imp.get("agent", "N/A")
            trigger = imp.get("trigger", "")
            action = imp.get("action", "")
            impact = imp.get("impact", "")

            if use_unicode:
                lines.append(f"{i}. **Agent:** `{agent}`")
                if trigger:
                    lines.append(f"   - **Trigger:** {trigger}")
                lines.append(f"   - **Action:** {action}")
                if impact:
                    lines.append(f"   - **Impact:** {impact}")
                lines.append("")
            else:
                lines.append(f"  [{i:>3}] Agent  : {agent}")
                if trigger:
                    lines.append(f"        Trigger: {trigger}")
                lines.append(f"        Action : {action}")
                if impact:
                    lines.append(f"        Impact : {impact}")
                lines.append("")

        return "\n".join(lines)

    def _render_header(self, use_unicode: bool = False) -> List[str]:
        """Render the report header.

        Parameters
        ----------
        use_unicode: bool
            Whether to use Markdown formatting.

        Returns
        -------
        list[str]
            Header lines.
        """
        run_id = self.results.get("run_id", "N/A")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if use_unicode:
            return [
                "# Agent Swarm Collaboration Report",
                "",
                f"**Run ID:** `{run_id}`",
                f"**Generated:** {now}",
                "",
                "> ⚠️ **DISCLAIMER:** RESEARCH / EDUCATIONAL PURPOSES ONLY. "
                "NOT INVESTMENT ADVICE.",
                "",
            ]
        else:
            return [
                "+" + "-" * 78 + "+",
                "|" + " " * 20 + "AGENT SWARM COLLABORATION REPORT" + " " * 28 + "|",
                "+" + "-" * 78 + "+",
                f"|  Run ID    : {run_id:<64}|",
                f"|  Generated : {now:<64}|",
                "+" + "-" * 78 + "+",
                "",
                "  DISCLAIMER: RESEARCH / EDUCATIONAL PURPOSES ONLY.",
                "              NOT INVESTMENT ADVICE.",
                "",
            ]

    def _render_footer(self, use_unicode: bool = False) -> List[str]:
        """Render the report footer.

        Parameters
        ----------
        use_unicode: bool
            Whether to use Markdown formatting.

        Returns
        -------
        list[str]
            Footer lines.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if use_unicode:
            return [
                "---",
                "",
                f"*Report generated at {now}*",
                "",
                "*RESEARCH / EDUCATIONAL PURPOSES ONLY. NOT INVESTMENT ADVICE.*",
            ]
        else:
            return [
                "+" + "-" * 78 + "+",
                "|" + " " * 28 + "END OF REPORT" + " " * 37 + "|",
                "+" + "-" * 78 + "+",
                f"|  Generated: {now:<65}|",
                "+" + "-" * 78 + "+",
            ]

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def generate_text_report(self) -> str:
        """Generate a comprehensive plain-text report.

        Uses ASCII box-drawing characters and tags for severity indicators.

        Returns
        -------
        str
            Multi-line plain-text report.
        """
        critiques = self.results.get("critiques", [])
        improvements = self.results.get("improvements", [])
        consensus = self.results.get("consensus", "")
        memory_records = self.results.get("memory_records", [])
        counts = self._count_critiques(critiques)

        lines: List[str] = []

        # Header
        lines.extend(self._render_header(use_unicode=False))

        # Strategy Summaries
        lines.extend([
            "-" * 80,
            "  STRATEGY SUMMARIES",
            "-" * 80,
            "",
            self._render_strategy_summary(use_unicode=False),
        ])

        # Critique Statistics
        lines.extend([
            "-" * 80,
            "  CRITIQUE STATISTICS",
            "-" * 80,
            "",
            self._render_critique_stats(counts, use_unicode=False),
        ])

        # Full Critique Log
        lines.extend([
            "-" * 80,
            "  FULL CRITIQUE LOG (sorted by severity)",
            "-" * 80,
            "",
            self._render_critique_log(critiques, use_unicode=False),
        ])

        # Improvements Applied
        lines.extend([
            "-" * 80,
            "  IMPROVEMENTS APPLIED",
            "-" * 80,
            "",
            self._render_improvements(improvements, use_unicode=False),
        ])

        # Consensus
        lines.extend([
            "-" * 80,
            "  CONSENSUS RECOMMENDATION",
            "-" * 80,
            "",
        ])
        if consensus:
            for line in consensus.splitlines():
                lines.append(f"  {line}")
        else:
            lines.append("  No consensus recorded.")
        lines.append("")

        # Memory Records
        lines.extend([
            "-" * 80,
            "  MEMORY RECORDS",
            "-" * 80,
            "",
            f"  Total memory records: {len(memory_records)}",
            "",
        ])

        # Footer
        lines.extend(self._render_footer(use_unicode=False))

        return "\n".join(lines)

    def generate_markdown_report(self) -> str:
        """Generate a comprehensive Markdown report.

        Uses emoji icons for severity indicators and Markdown tables.

        Returns
        -------
        str
            Multi-line Markdown report.
        """
        critiques = self.results.get("critiques", [])
        improvements = self.results.get("improvements", [])
        consensus = self.results.get("consensus", "")
        memory_records = self.results.get("memory_records", [])
        counts = self._count_critiques(critiques)

        lines: List[str] = []

        # Header
        lines.extend(self._render_header(use_unicode=True))

        # Strategy Summaries
        lines.extend([
            "## Strategy Summaries",
            "",
            self._render_strategy_summary(use_unicode=True),
        ])

        # Critique Statistics
        lines.extend([
            "## Critique Statistics",
            "",
            self._render_critique_stats(counts, use_unicode=True),
        ])

        # Full Critique Log
        lines.extend([
            "## Full Critique Log (sorted by severity)",
            "",
            self._render_critique_log(critiques, use_unicode=True),
        ])

        # Improvements Applied
        lines.extend([
            "## Improvements Applied",
            "",
            self._render_improvements(improvements, use_unicode=True),
        ])

        # Consensus
        lines.extend([
            "## Consensus Recommendation",
            "",
            "```",
        ])
        if consensus:
            lines.append(consensus)
        else:
            lines.append("No consensus recorded.")
        lines.extend([
            "```",
            "",
        ])

        # Memory Records
        lines.extend([
            "## Memory Records",
            "",
            f"**Total memory records:** {len(memory_records)}",
            "",
        ])

        # Footer
        lines.extend(self._render_footer(use_unicode=True))

        return "\n".join(lines)

    def generate_all(self) -> Dict[str, str]:
        """Write both text and Markdown report files.

        Returns
        -------
        dict[str, str]
            Paths to generated files with keys ``text`` and ``markdown``.
        """
        paths: Dict[str, str] = {}
        run_id = self.results.get("run_id", "unknown")
        safe_id = str(run_id).replace("/", "_").replace("\\", "_")

        # Text report
        text_path = os.path.join(
            self.output_dir, f"agent_swarm_report_{safe_id}.txt"
        )
        text_report = self.generate_text_report()
        with open(text_path, "w", encoding="utf-8") as fh:
            fh.write(text_report)
        paths["text"] = text_path
        logger.info("Text report written to %s", text_path)

        # Markdown report
        md_path = os.path.join(
            self.output_dir, f"agent_swarm_report_{safe_id}.md"
        )
        md_report = self.generate_markdown_report()
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(md_report)
        paths["markdown"] = md_path
        logger.info("Markdown report written to %s", md_path)

        return paths
