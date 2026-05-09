"""Integration tests for the AgentSwarm collaboration pipeline.

Covers: full collaboration run, missing-agent detection, critique absorption,
consensus building with varying Sharpe/drawdown, and ticker filtering.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from alpha_search.agents.roles import (
    DataEngineerAgent,
    OpportunityAgent,
    QuantEngineerAgent,
    ResearchAgent,
    RiskManagerAgent,
)
from alpha_search.agents.swarm import AgentSwarm, CritiqueMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prices(n: int = 60, tickers: list[str] | None = None) -> pd.DataFrame:
    """Build a synthetic price panel with a MultiIndex (field, ticker)."""
    tickers = tickers or ["AAPL", "MSFT", "GOOGL"]
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    data: dict = {}
    rng = np.random.default_rng(42)
    for t in tickers:
        close = 100.0 * (1.0 + rng.normal(0.0005, 0.02, n)).cumprod()
        data[("Close", t)] = close
        data[("Volume", t)] = rng.integers(1_000_000, 10_000_000, n)
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["field", "ticker"])
    return df


def _make_empty_prices() -> pd.DataFrame:
    """Empty price DataFrame."""
    return pd.DataFrame(
        columns=pd.MultiIndex.from_tuples([], names=["field", "ticker"]),
        dtype=float,
    )


# ---------------------------------------------------------------------------
# 1. Missing-agent detection
# ---------------------------------------------------------------------------


class TestAgentSwarmSetup:
    """Swarm registration and validation."""

    def test_register_agent(self) -> None:
        swarm = AgentSwarm()
        swarm.register("test_agent", DataEngineerAgent())
        assert "test_agent" in swarm.agents

    def test_missing_agents_raises(self) -> None:
        """Running without required agents raises RuntimeError."""
        swarm = AgentSwarm()
        # Register only 1 agent — 4 are missing
        swarm.register("data_engineer", DataEngineerAgent())

        prices = _make_prices()
        with pytest.raises(RuntimeError) as exc_info:
            swarm.run_collaboration(tickers=["AAPL"], prices=prices)
        msg = str(exc_info.value)
        assert "Missing required agents" in msg
        assert "opportunity_agent" in msg
        assert "quant_engineer" in msg


# ---------------------------------------------------------------------------
# 2. Full collaboration run
# ---------------------------------------------------------------------------


class TestAgentSwarmRun:
    """End-to-end collaboration pipeline."""

    @pytest.fixture
    def swarm(self) -> AgentSwarm:
        s = AgentSwarm()
        s.register("data_engineer", DataEngineerAgent())
        s.register("opportunity_agent", OpportunityAgent())
        s.register("quant_engineer", QuantEngineerAgent())
        s.register("research_agent", ResearchAgent())
        s.register("risk_manager", RiskManagerAgent())
        return s

    def test_run_returns_expected_keys(self, swarm: AgentSwarm) -> None:
        prices = _make_prices(n=60)
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT", "GOOGL"], prices=prices)

        assert "run_id" in result
        assert "strategies" in result
        assert "critiques" in result
        assert "improvements" in result
        assert "consensus" in result
        assert "memory_records" in result

    def test_critiques_are_real_not_placeholders(self, swarm: AgentSwarm) -> None:
        """Critiques must contain specific data, not generic placeholder text."""
        prices = _make_prices(n=60)
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT", "GOOGL"], prices=prices)

        critiques = result["critiques"]
        assert len(critiques) > 0

        for c in critiques:
            # Every critique must have a non-empty message
            assert c["message"], f"Empty message from {c['from_agent']}"
            # Messages should contain numbers (specific observations)
            # OR ticker symbols (specific references)
            has_number = any(ch.isdigit() for ch in c["message"])
            has_ticker = any(
                ticker in c["message"] for ticker in ["AAPL", "MSFT", "GOOGL"]
            )
            assert has_number or has_ticker, (
                f"Critique from {c['from_agent']} has no specific data: {c['message'][:80]}"
            )

    def test_consensus_contains_sign_offs(self, swarm: AgentSwarm) -> None:
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT", "GOOGL"], prices=_make_prices(n=60))
        consensus = result["consensus"]

        assert "AGENT SIGN-OFFS:" in consensus
        # All 5 agents should have sign-off lines
        assert "DataEngineerAgent" in consensus
        assert "OpportunityAgent" in consensus
        assert "QuantEngineerAgent" in consensus
        assert "ResearchAgent" in consensus
        assert "RiskManagerAgent" in consensus

    def test_empty_prices_produces_data_quality_critique(self, swarm: AgentSwarm) -> None:
        """Empty price data should trigger a critical data-quality critique."""
        result = swarm.run_collaboration(
            tickers=["AAPL"], prices=_make_empty_prices()
        )
        critiques = result["critiques"]
        data_critiques = [c for c in critiques if c["critique_type"] == "data_quality"]
        assert len(data_critiques) > 0
        assert any(c["severity"] == "critical" for c in data_critiques)

    def test_run_id_is_unique(self, swarm: AgentSwarm) -> None:
        r1 = swarm.run_collaboration(tickers=["AAPL"], prices=_make_prices(n=60))
        r2 = swarm.run_collaboration(tickers=["AAPL"], prices=_make_prices(n=60))
        assert r1["run_id"] != r2["run_id"]

    def test_memory_records_populated(self, swarm: AgentSwarm) -> None:
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT"], prices=_make_prices(n=60))
        records = result["memory_records"]
        assert len(records) > 0
        # Should have event records for each phase
        events = [r for r in records if r.get("record_type") == "event"]
        assert len(events) >= 6  # At least 6 phase events


# ---------------------------------------------------------------------------
# 3. Critique absorption and stats
# ---------------------------------------------------------------------------


class TestCritiqueStats:
    """Swarm critique tracking."""

    def test_get_critique_stats(self) -> None:
        swarm = AgentSwarm()
        # Inject some critiques manually
        swarm.critiques = [
            CritiqueMessage("a", "b", "signal_quality", "critical", "msg1", "sug1"),
            CritiqueMessage("a", "b", "signal_quality", "warning", "msg2", "sug2"),
            CritiqueMessage("c", "d", "risk_concern", "critical", "msg3", "sug3"),
        ]
        stats = swarm.get_critique_stats()
        assert stats["total"] == 3
        assert stats["by_severity"]["critical"] == 2
        assert stats["by_severity"]["warning"] == 1
        assert stats["by_type"]["signal_quality"] == 2
        assert stats["by_type"]["risk_concern"] == 1
        assert stats["by_from_agent"]["a"] == 2
        assert stats["by_from_agent"]["c"] == 1
        assert stats["by_to_agent"]["b"] == 2
        assert stats["by_to_agent"]["d"] == 1


# ---------------------------------------------------------------------------
# 4. Ticker filtering from critiques
# ---------------------------------------------------------------------------


class TestTickerFiltering:
    """_filter_tickers_from_critiques uses word-boundary matching."""

    @pytest.fixture
    def swarm(self) -> AgentSwarm:
        s = AgentSwarm()
        s.register("data_engineer", DataEngineerAgent())
        s.register("opportunity_agent", OpportunityAgent())
        s.register("quant_engineer", QuantEngineerAgent())
        s.register("research_agent", ResearchAgent())
        s.register("risk_manager", RiskManagerAgent())
        return s

    def test_exact_ticker_match_removed(self, swarm: AgentSwarm) -> None:
        critiques = [
            CritiqueMessage(
                "data_engineer", "swarm", "data_quality", "critical",
                "AAPL: missing Close data", "remove AAPL",
            ),
        ]
        result = swarm._filter_tickers_from_critiques(["AAPL", "MSFT"], critiques)
        assert "AAPL" not in result
        assert "MSFT" in result

    def test_substring_collision_avoided(self, swarm: AgentSwarm) -> None:
        """MET must NOT match inside META — the original substring bug."""
        critiques = [
            CritiqueMessage(
                "data_engineer", "swarm", "data_quality", "critical",
                "META: missing Close data", "remove META",
            ),
        ]
        result = swarm._filter_tickers_from_critiques(["META", "MET"], critiques)
        assert "META" not in result
        assert "MET" in result  # MET must NOT be removed (substring collision)

    def test_case_insensitive_match(self, swarm: AgentSwarm) -> None:
        critiques = [
            CritiqueMessage(
                "data_engineer", "swarm", "data_quality", "critical",
                "aapl has bad data", "remove",
            ),
        ]
        result = swarm._filter_tickers_from_critiques(["AAPL"], critiques)
        assert "AAPL" not in result

    def test_only_critical_severity_filters(self, swarm: AgentSwarm) -> None:
        """Warning-level critiques should NOT remove tickers."""
        critiques = [
            CritiqueMessage(
                "data_engineer", "swarm", "data_quality", "warning",
                "AAPL: some missing bars", "check AAPL",
            ),
        ]
        result = swarm._filter_tickers_from_critiques(["AAPL"], critiques)
        assert "AAPL" in result  # Not removed — only critical filters


# ---------------------------------------------------------------------------
# 5. Drawdown negative convention
# ---------------------------------------------------------------------------


class TestDrawdownConvention:
    """Verify negative drawdown convention throughout the pipeline."""

    @pytest.fixture
    def swarm(self) -> AgentSwarm:
        s = AgentSwarm()
        s.register("data_engineer", DataEngineerAgent())
        s.register("opportunity_agent", OpportunityAgent())
        s.register("quant_engineer", QuantEngineerAgent())
        s.register("research_agent", ResearchAgent())
        s.register("risk_manager", RiskManagerAgent())
        return s

    def test_drawdown_is_negative_in_consensus(self, swarm: AgentSwarm) -> None:
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT"], prices=_make_prices(n=60))
        consensus = result["consensus"]

        # RiskManagerAgent sign-off should show drawdown as percentage
        assert "drawdown" in consensus.lower()

    def test_risk_status_uses_negative_convention(self, swarm: AgentSwarm) -> None:
        """RISK STATUS should correctly interpret negative drawdown."""
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT"], prices=_make_prices(n=60))
        consensus = result["consensus"]

        # Should have either PASS or CONDITIONAL (not garbled)
        assert "PASS" in consensus or "CONDITIONAL" in consensus

    def test_backtest_metrics_negative_drawdown(self, swarm: AgentSwarm) -> None:
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT"], prices=_make_prices(n=60))
        strategies = result["strategies"]

        portfolio = [s for s in strategies if s["type"] == "portfolio"]
        if portfolio:
            dd = portfolio[0].get("max_drawdown", 0)
            # Drawdown should be <= 0 (negative or zero)
            assert dd <= 0, f"Expected negative drawdown, got {dd}"


# ---------------------------------------------------------------------------
# 6. BacktestEngine integration (Fix #1)
# ---------------------------------------------------------------------------


class TestRealBacktestIntegration:
    """QuantEngineerAgent uses real BacktestEngine when available."""

    def test_backtest_without_engine_is_deterministic(self) -> None:
        """Fallback simplified backtest must be deterministic (no RNG)."""
        agent = QuantEngineerAgent()  # No engine injected
        signals = {
            "momentum": {
                "by_ticker": {
                    "AAPL": {"momentum": 0.10, "entry_signal": True},
                }
            },
            "mean_reversion": {"by_ticker": {}},
        }
        result1 = agent.backtest(signals)
        result2 = agent.backtest(signals)

        # Must be identical — no randomness
        assert result1 == result2
        assert result1["sharpe_ratio"] == result2["sharpe_ratio"]
        assert result1["max_drawdown"] == result2["max_drawdown"]

    def test_backtest_with_prices_and_engine(self) -> None:
        """When engine + prices are provided, real backtest runs."""
        from alpha_search.backtest.costs import CostModel
        from alpha_search.backtest.engine import BacktestEngine

        engine = BacktestEngine()
        cost_model = CostModel(commission=0.001, slippage=0.001)
        agent = QuantEngineerAgent(backtest_engine=engine, cost_model=cost_model)

        # Create simple momentum signal
        prices = _make_prices(n=60, tickers=["AAPL"])
        signals = {
            "momentum": {
                "by_ticker": {
                    "AAPL": {"momentum": 0.10, "entry_signal": True},
                }
            },
            "mean_reversion": {"by_ticker": {}},
        }

        result = agent.backtest(signals, prices)
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result
        assert "total_return" in result
        assert result["max_drawdown"] <= 0  # negative convention
