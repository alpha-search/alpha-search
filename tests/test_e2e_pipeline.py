"""End-to-end integration test: data → signals → backtest → agents → memory.

Exercises the complete Alpha Search pipeline in one cohesive flow:
1. Generate synthetic market data (sample_universes)
2. Run strategy signals (MomentumPipeline + MeanReversionPipeline)
3. Backtest each signal set
4. Feed results through the AgentSwarm collaboration loop
5. Persist decisions to MemoryStore and verify retrieval
"""

from __future__ import annotations

import pandas as pd
import pytest

from alpha_search.agents.roles import (
    DataEngineerAgent,
    OpportunityAgent,
    QuantEngineerAgent,
    ResearchAgent,
    RiskManagerAgent,
)
from alpha_search.agents.swarm import AgentSwarm
from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.memory.models import MemoryRecord
from alpha_search.memory.store import MemoryStore
from alpha_search.research.strategy_pipeline import MeanReversionPipeline, MomentumPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_prices(
    tickers: list[str],
    days: int = 200,
    seed: int = 42,
) -> pd.DataFrame:
    """Create deterministic OHLCV prices for testing (no API calls)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")
    data: dict[tuple[str, str], pd.Series] = {}
    for t in tickers:
        # GBM with slight positive drift
        returns = rng.normal(0.0003, 0.015, days)
        close = 100.0 * np.cumprod(1 + returns)
        noise = rng.uniform(0.005, 0.02, days)
        data[(t, "Close")] = pd.Series(close, index=dates)
        data[(t, "High")] = pd.Series(close * (1 + noise), index=dates)
        data[(t, "Low")] = pd.Series(close * (1 - noise), index=dates)
        data[(t, "Open")] = pd.Series(close + rng.normal(0, 0.5, days), index=dates)
        data[(t, "Volume")] = pd.Series(
            rng.integers(1_000_000, 10_000_000, days), index=dates
        )
    df = pd.DataFrame(data)
    df.columns.names = ["ticker", "field"]
    return df


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic_prices() -> pd.DataFrame:
    """200 days of deterministic test equity data for 5 tickers."""
    return _make_test_prices(
        tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        days=200,
        seed=42,
    )


@pytest.fixture(scope="module")
def tickers() -> list[str]:
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]


# ---------------------------------------------------------------------------
# Stage 1: Data generation
# ---------------------------------------------------------------------------


class TestDataGeneration:
    """Verify synthetic data is suitable for downstream pipeline stages."""

    def test_prices_have_expected_shape(self, synthetic_prices: pd.DataFrame) -> None:
        assert isinstance(synthetic_prices, pd.DataFrame)
        assert not synthetic_prices.empty
        # MultiIndex columns
        assert synthetic_prices.columns.nlevels == 2

    def test_close_prices_are_positive(
        self, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        for ticker in tickers:
            close = synthetic_prices.xs("Close", level=1, axis=1)[ticker]
            assert (close > 0).all(), f"{ticker} has non-positive close prices"

    def test_enough_bars_for_signals(self, synthetic_prices: pd.DataFrame) -> None:
        """Need at least 60 bars for momentum + mean-reversion signals."""
        assert len(synthetic_prices) >= 60


# ---------------------------------------------------------------------------
# Stage 2 & 3: Signal generation + backtest
# ---------------------------------------------------------------------------


class TestSignalAndBacktest:
    """MomentumPipeline and MeanReversionPipeline end-to-end."""

    def test_momentum_pipeline_produces_metrics(
        self, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        pipe = MomentumPipeline(prices=synthetic_prices, tickers=tickers, capital=100_000.0)
        result = pipe.run()

        assert "opportunities" in result
        assert "signals" in result
        assert "backtests" in result
        assert "metrics" in result

        metrics = result["metrics"]
        assert isinstance(metrics, pd.DataFrame)
        assert not metrics.empty
        assert "sharpe_ratio" in metrics.columns
        assert "max_drawdown" in metrics.columns
        assert "total_return" in metrics.columns

    def test_mean_reversion_pipeline_produces_metrics(
        self, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        pipe = MeanReversionPipeline(
            prices=synthetic_prices, tickers=tickers, capital=100_000.0
        )
        result = pipe.run()

        metrics = result["metrics"]
        assert isinstance(metrics, pd.DataFrame)
        assert not metrics.empty

    def test_momentum_max_drawdown_is_non_positive(
        self, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        """max_drawdown must be <= 0 (negative convention)."""
        pipe = MomentumPipeline(prices=synthetic_prices, tickers=tickers)
        result = pipe.run()
        for _, row in result["metrics"].iterrows():
            assert row["max_drawdown"] <= 0, (
                f"max_drawdown should be non-positive, got {row['max_drawdown']}"
            )

    def test_momentum_signals_are_bounded(
        self, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        """Combined momentum signal must be in a reasonable range."""
        pipe = MomentumPipeline(prices=synthetic_prices, tickers=tickers)
        signals = pipe.generate_signals()
        assert len(signals) > 0
        for ticker, sig in signals.items():
            assert isinstance(sig, pd.Series)
            # Allow NaN in warmup region but finite values elsewhere
            finite = sig.dropna()
            if not finite.empty:
                assert finite.min() >= -2.0, f"{ticker}: signal below -2"
                assert finite.max() <= 2.0, f"{ticker}: signal above 2"

    def test_backtest_engine_runs_directly(self, synthetic_prices: pd.DataFrame) -> None:
        """BacktestEngine can be used directly with pipeline signals."""
        from alpha_search.research.strategy_pipeline import _extract_ticker_prices

        engine = BacktestEngine()
        cost_model = CostModel(commission=0.001, slippage=0.001)

        pipe = MomentumPipeline(prices=synthetic_prices, tickers=["AAPL"], capital=50_000.0)
        signals = pipe.generate_signals()
        assert "AAPL" in signals

        # Use the pipeline's own extractor which handles both MultiIndex orderings
        ticker_df = _extract_ticker_prices(synthetic_prices, "AAPL")

        result = engine.run(
            prices=ticker_df,
            signal=signals["AAPL"],
            initial_capital=50_000.0,
            cost_model=cost_model,
        )
        assert hasattr(result, "metrics")
        assert "sharpe_ratio" in result.metrics
        assert result.metrics["max_drawdown"] <= 0


# ---------------------------------------------------------------------------
# Stage 4: Agent swarm collaboration
# ---------------------------------------------------------------------------


class TestAgentSwarmIntegration:
    """Full agent swarm run against synthetic prices."""

    @pytest.fixture
    def swarm(self) -> AgentSwarm:
        s = AgentSwarm()
        s.register("data_engineer", DataEngineerAgent())
        s.register("opportunity_agent", OpportunityAgent())
        s.register("quant_engineer", QuantEngineerAgent())
        s.register("research_agent", ResearchAgent())
        s.register("risk_manager", RiskManagerAgent())
        return s

    def test_swarm_completes_with_synthetic_data(
        self, swarm: AgentSwarm, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        result = swarm.run_collaboration(tickers=tickers, prices=synthetic_prices)

        assert "run_id" in result
        assert "strategies" in result
        assert "critiques" in result
        assert "consensus" in result
        assert "memory_records" in result

    def test_swarm_critiques_reference_real_data(
        self, swarm: AgentSwarm, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        """Critiques must contain ticker names or numeric data (not generic placeholders)."""
        result = swarm.run_collaboration(tickers=tickers, prices=synthetic_prices)

        for c in result["critiques"]:
            msg = c["message"]
            has_number = any(ch.isdigit() for ch in msg)
            has_ticker = any(t in msg for t in tickers)
            has_percentage = "%" in msg
            assert has_number or has_ticker or has_percentage, (
                f"Critique from {c['from_agent']} seems generic: {msg[:100]}"
            )

    def test_swarm_consensus_is_non_empty(
        self, swarm: AgentSwarm, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        result = swarm.run_collaboration(tickers=tickers, prices=synthetic_prices)
        consensus = result["consensus"]
        assert isinstance(consensus, str)
        assert len(consensus) > 100

    def test_swarm_risk_signoffs_in_consensus(
        self, swarm: AgentSwarm, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        result = swarm.run_collaboration(tickers=tickers, prices=synthetic_prices)
        assert "AGENT SIGN-OFFS:" in result["consensus"]
        assert "RiskManagerAgent" in result["consensus"]

    def test_swarm_drawdown_convention_negative(
        self, swarm: AgentSwarm, synthetic_prices: pd.DataFrame
    ) -> None:
        """Portfolio drawdown reported in consensus must be non-positive."""
        result = swarm.run_collaboration(tickers=["AAPL", "MSFT"], prices=synthetic_prices)
        strategies = result["strategies"]
        portfolio = [s for s in strategies if s.get("type") == "portfolio"]
        for p in portfolio:
            dd = p.get("max_drawdown", 0)
            assert dd <= 0, f"Drawdown should be non-positive, got {dd}"


# ---------------------------------------------------------------------------
# Stage 5: MemoryStore persistence
# ---------------------------------------------------------------------------


class TestMemoryStorePersistence:
    """Persist swarm decisions to MemoryStore and verify retrieval."""

    def test_pipeline_decisions_persist_to_memory(
        self, synthetic_prices: pd.DataFrame, tickers: list[str]
    ) -> None:
        """Full pipeline: run swarm, write decisions to store, read them back."""
        store = MemoryStore(":memory:")
        store.initialize()

        swarm = AgentSwarm()
        swarm.register("data_engineer", DataEngineerAgent())
        swarm.register("opportunity_agent", OpportunityAgent())
        swarm.register("quant_engineer", QuantEngineerAgent())
        swarm.register("research_agent", ResearchAgent())
        swarm.register("risk_manager", RiskManagerAgent())

        result = swarm.run_collaboration(tickers=tickers, prices=synthetic_prices)

        # Map swarm record_type → valid MemoryRecord memory_type
        _type_map = {
            "critique": "research_finding",
            "event": "agent_task",
            "strategy": "strategy_result",
        }
        # Persist memory records from swarm result
        memory_ids: list[str] = []
        for raw in result["memory_records"]:
            raw_type = raw.get("record_type", raw.get("memory_type", "event"))
            memory_type = _type_map.get(raw_type, "agent_task")
            record = MemoryRecord(
                agent_name=raw.get("agent_name", "swarm"),
                memory_type=memory_type,
                title=raw.get("title", "swarm event"),
                content=raw.get("content", str(raw))[:2000],
                tags=raw.get("tags", []),
            )
            mid = store.add_memory(record)
            memory_ids.append(mid)

        assert len(memory_ids) > 0

        # Verify records can be retrieved
        recent = store.list_recent(limit=50)
        assert len(recent) >= len(memory_ids)

        store.close()

    def test_blocker_filter_excludes_resolved(self) -> None:
        """get_unresolved_blockers() must exclude records with status != 'active'."""
        store = MemoryStore(":memory:")
        store.initialize()

        # Add one active blocker and one resolved blocker
        active = MemoryRecord(
            agent_name="test_agent",
            memory_type="blocker",
            title="Active blocker",
            content="Still blocking progress",
            status="active",
        )
        resolved = MemoryRecord(
            agent_name="test_agent",
            memory_type="blocker",
            title="Resolved blocker",
            content="This was fixed",
            status="resolved",
        )
        store.add_memory(active)
        store.add_memory(resolved)

        unresolved = store.get_unresolved_blockers(limit=50)
        titles = [r.title for r in unresolved]

        assert "Active blocker" in titles, "Active blocker should be returned"
        assert "Resolved blocker" not in titles, "Resolved blocker must be excluded"

        store.close()

    def test_architecture_decisions_persist(self) -> None:
        """Architecture decisions can be stored and retrieved by memory_type."""
        store = MemoryStore(":memory:")
        store.initialize()

        record = MemoryRecord(
            agent_name="quant_engineer",
            memory_type="architecture_decision",
            title="Use Wilder EMA for RSI",
            content="Switched from SMA to Wilder's EMA in RSI calculation.",
            tags=["rsi", "signals"],
            importance_score=0.9,
        )
        store.add_memory(record)

        decisions = store.get_memories(memory_type="architecture_decision", limit=10)
        assert len(decisions) == 1
        assert decisions[0].title == "Use Wilder EMA for RSI"

        store.close()


# ---------------------------------------------------------------------------
# Full pipeline round-trip
# ---------------------------------------------------------------------------


class TestFullPipelineRoundTrip:
    """Complete data → strategy → swarm → memory round-trip in one test."""

    def test_full_round_trip(self) -> None:
        """One test that exercises every pipeline stage end-to-end."""
        # 1. Generate data
        prices = _make_test_prices(tickers=["AAPL", "MSFT", "GOOGL"], days=150, seed=99)
        tickers = ["AAPL", "MSFT", "GOOGL"]

        # 2. Run momentum pipeline
        mom_pipe = MomentumPipeline(prices=prices, tickers=tickers, capital=100_000.0)
        mom_result = mom_pipe.run()
        assert not mom_result["metrics"].empty

        # 3. Run mean-reversion pipeline
        mr_pipe = MeanReversionPipeline(prices=prices, tickers=tickers, capital=100_000.0)
        mr_result = mr_pipe.run()
        assert not mr_result["metrics"].empty

        # 4. Run agent swarm
        swarm = AgentSwarm()
        swarm.register("data_engineer", DataEngineerAgent())
        swarm.register("opportunity_agent", OpportunityAgent())
        swarm.register("quant_engineer", QuantEngineerAgent())
        swarm.register("research_agent", ResearchAgent())
        swarm.register("risk_manager", RiskManagerAgent())

        collab_result = swarm.run_collaboration(tickers=tickers, prices=prices)
        assert len(collab_result["critiques"]) > 0

        # 5. Persist to memory
        store = MemoryStore(":memory:")
        store.initialize()

        # Store momentum metrics as a research finding
        metrics_summary = mom_result["metrics"]["sharpe_ratio"].to_dict()
        record = MemoryRecord(
            agent_name="momentum_pipeline",
            memory_type="research_finding",
            title="Momentum strategy metrics",
            content=f"Sharpe ratios: {metrics_summary}",
            tags=["momentum", "backtest"],
        )
        store.add_memory(record)

        # Store consensus
        consensus_record = MemoryRecord(
            agent_name="swarm",
            memory_type="strategy_result",
            title="Agent swarm consensus",
            content=collab_result["consensus"][:500],
            tags=["consensus", "swarm"],
        )
        store.add_memory(consensus_record)

        # 6. Verify memory retrieval
        all_memories = store.list_recent(limit=20)
        assert len(all_memories) == 2

        research = store.get_memories(memory_type="research_finding", limit=10)
        assert len(research) == 1
        assert research[0].title == "Momentum strategy metrics"

        store.close()
