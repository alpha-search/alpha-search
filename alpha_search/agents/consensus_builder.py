"""Consensus builder for the agent swarm.

Synthesises a final consensus recommendation from all agent outputs,
formerly part of the ``AgentSwarm`` god-class.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ConsensusBuilder:
    """Build a consensus report from backtest metrics, critiques, and agent sign-offs."""

    def build(
        self,
        tickers: list[str],
        signals: dict,
        backtest_result: dict,
        sentiment: dict,
        critiques: list,
    ) -> str:
        """Synthesize a final consensus recommendation from all agent outputs."""
        sharpe = backtest_result.get("sharpe_ratio", 0.0)
        max_dd = backtest_result.get("max_drawdown", 1.0)
        total_return = backtest_result.get("total_return", 0.0)

        # Count critical issues
        critical_count = sum(1 for c in critiques if c.severity == "critical")
        warning_count = sum(1 for c in critiques if c.severity == "warning")

        # Build ticker-specific notes
        ticker_notes = []
        for t in tickers:
            sent = sentiment.get(t, {})
            sent_dir = sent.get("direction", "neutral")
            sent_score = sent.get("score", 0.5)
            note = f"{t}: sentiment {sent_dir} ({sent_score:.2f})"
            ticker_notes.append(note)

        consensus_parts = [
            "=== AGENT SWARM CONSENSUS (run_id embedded) ===",
            "",
            "BACKTEST METRICS:",
            f"  Sharpe Ratio: {sharpe:.2f}  (threshold: >0.5)",
            f"  Max Drawdown: {max_dd:.1%}  (limit: <25%)",
            f"  Total Return: {total_return:.1%}",
            "",
            f"RISK STATUS: {'PASS' if max_dd > -0.25 and sharpe > 0.5 else 'CONDITIONAL'}",
            f"  Critical issues: {critical_count} | Warnings: {warning_count}",
            "",
            "TICKER ASSESSMENTS:",
        ]
        consensus_parts.extend(f"  {n}" for n in ticker_notes)
        consensus_parts.extend([
            "",
            "STRATEGY RECOMMENDATION:",
        ])

        # With negative drawdown convention: -0.20 = 20% drawdown
        if sharpe > 0.5 and max_dd > -0.25 and critical_count == 0:
            consensus_parts.append(
                "  PROCEED — All agents agree strategy is within risk parameters. "
                "Deploy with 20-day momentum lookback, sentiment confirmation filter, "
                "and 8% trailing stop-loss on mean-reversion leg."
            )
        elif sharpe > 0.5 and max_dd > -0.30 and warning_count <= 3:
            consensus_parts.append(
                "  CONDITIONAL PROCEED — Strategy meets Sharpe threshold but requires "
                "active risk monitoring. Max position size 15%, enforce sector cap, "
                "and review drawdown weekly. Stop-loss at 8% must be hard-coded."
            )
        else:
            consensus_parts.append(
                "  HOLD — Strategy does not meet minimum risk criteria. "
                "Key blockers: max drawdown exceeds 25% limit OR Sharpe below 0.5. "
                "Recommended: tighten stop-loss further, reduce position sizes, or "
                "wait for higher-volatility regime where mean-reversion performs better."
            )

        # Conditional sign-offs based on actual critique counts
        data_crits = [c for c in critiques if c.from_agent == "data_engineer"]
        opp_crits = [c for c in critiques if c.from_agent == "opportunity_agent"]
        quant_crits = [c for c in critiques if c.from_agent == "quant_engineer"]
        research_crits = [c for c in critiques if c.from_agent == "research_agent"]
        risk_crits = [c for c in critiques if c.from_agent == "risk_manager"]

        def _agent_ok(agent_crits: list) -> str:
            return "OK" if not any(c.severity == "critical" for c in agent_crits) else "XX"

        def _agent_status(agent_crits: list) -> str:
            n = len(agent_crits)
            nc = sum(1 for c in agent_crits if c.severity == "critical")
            if nc > 0:
                return f"{nc} critical issue(s) flagged"
            return f"{'verified' if n == 0 else f'{n} issue(s), none critical'}"

        consensus_parts.extend([
            "",
            "AGENT SIGN-OFFS:",
            f"  [{_agent_ok(data_crits)}] DataEngineerAgent    — {_agent_status(data_crits)}",
            f"  [{_agent_ok(opp_crits)}] OpportunityAgent     — {_agent_status(opp_crits)}",
            f"  [{_agent_ok(quant_crits)}] QuantEngineerAgent   — {_agent_status(quant_crits)}",
            f"  [{_agent_ok(research_crits)}] ResearchAgent        — {_agent_status(research_crits)}",
            f"  [{_agent_ok(risk_crits)}] RiskManagerAgent     — {_agent_status(risk_crits)} | drawdown {abs(max_dd):.1%}",
        ])

        return "\n".join(consensus_parts)
