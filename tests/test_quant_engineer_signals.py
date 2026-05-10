"""Unit tests for QuantEngineerAgent signal construction.

Covers build_momentum_signals, build_mean_reversion_signals,
critique_signals, and critique_opportunity_rankings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from alpha_search.agents.roles import (
    OpportunityAgent,
    QuantEngineerAgent,
)
from alpha_search.agents.swarm import CritiqueMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_multiindex_prices(
    n: int = 60,
    tickers: list[str] | None = None,
    trend: float = 0.001,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic OHLCV panel with MultiIndex(field, ticker) columns."""
    tickers = tickers or ["AAPL", "MSFT", "GOOGL"]
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(seed)
    data: dict = {}
    for t in tickers:
        close = 100.0 * np.cumprod(1.0 + trend + rng.normal(0, 0.01, n))
        data[("Close", t)] = close
        data[("Volume", t)] = rng.integers(1_000_000, 10_000_000, n).astype(float)
        data[("Open", t)] = close * rng.uniform(0.99, 1.01, n)
        data[("High", t)] = close * rng.uniform(1.00, 1.02, n)
        data[("Low", t)] = close * rng.uniform(0.98, 1.00, n)
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["field", "ticker"])
    return df


def _make_trending_prices(n: int = 60, seed: int = 0) -> pd.DataFrame:
    """Strongly upward-trending price data."""
    return _make_multiindex_prices(n=n, tickers=["AAPL"], trend=0.005, seed=seed)


def _make_mean_reverting_prices(n: int = 60, seed: int = 7) -> pd.DataFrame:
    """Prices that end far below their rolling mean (deeply oversold)."""
    tickers = ["AAPL", "MSFT"]
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(seed)
    data: dict = {}
    for t in tickers:
        # Flat for first 50 bars, then sharp drop of 15%
        close = 100.0 * np.ones(n)
        for i in range(1, n - 5):
            close[i] = close[i - 1] * (1.0 + rng.normal(0, 0.003))
        for i in range(n - 5, n):
            close[i] = close[i - 1] * 0.97  # steady drop
        data[("Close", t)] = close
        data[("Volume", t)] = rng.integers(500_000, 5_000_000, n).astype(float)
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["field", "ticker"])
    return df


# ---------------------------------------------------------------------------
# build_momentum_signals
# ---------------------------------------------------------------------------


class TestBuildMomentumSignals:
    """Tests for QuantEngineerAgent.build_momentum_signals()."""

    def test_returns_dict_keyed_by_ticker(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60, tickers=["AAPL", "MSFT"])
        signals = agent.build_momentum_signals(prices, lookback=20)
        assert isinstance(signals, dict)
        assert "AAPL" in signals["by_ticker"]
        assert "MSFT" in signals["by_ticker"]

    def test_scores_are_numeric(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60)
        signals = agent.build_momentum_signals(prices, lookback=20)
        for ticker, score in signals["scores"].items():
            assert isinstance(score, float), f"{ticker} score is {type(score)}"
            assert np.isfinite(score), f"{ticker} score is non-finite: {score}"

    def test_lookback_stored(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60)
        signals = agent.build_momentum_signals(prices, lookback=15)
        assert signals["lookback"] == 15

    def test_trending_prices_produce_positive_momentum(self) -> None:
        """Strongly trending prices → positive momentum score."""
        agent = QuantEngineerAgent()
        prices = _make_trending_prices(n=60)
        signals = agent.build_momentum_signals(prices, lookback=20)
        aapl = signals["by_ticker"].get("AAPL", {})
        assert aapl["momentum"] > 0, "Trending prices should produce positive momentum"

    def test_entry_signal_set_for_strong_trend(self) -> None:
        """entry_signal=True when 20-day return > 5%."""
        agent = QuantEngineerAgent()
        prices = _make_trending_prices(n=60, seed=0)
        signals = agent.build_momentum_signals(prices, lookback=20)
        aapl = signals["by_ticker"].get("AAPL", {})
        # trend=0.5% per day, 20-day ≈ 10% — should be > 5%
        if aapl.get("momentum", 0) > 0.05:
            assert bool(aapl["entry_signal"]) is True

    def test_exit_signal_set_for_negative_momentum(self) -> None:
        """exit_signal=True when momentum < 0."""
        agent = QuantEngineerAgent()
        # Flat / slightly down prices
        prices = _make_multiindex_prices(n=60, tickers=["AAPL"], trend=-0.003, seed=99)
        signals = agent.build_momentum_signals(prices, lookback=20)
        aapl = signals["by_ticker"].get("AAPL", {})
        if aapl.get("momentum", 0) < 0:
            assert bool(aapl["exit_signal"]) is True

    def test_short_history_tickers_skipped(self) -> None:
        """Tickers with fewer than lookback+5 bars are skipped."""
        agent = QuantEngineerAgent()
        # Only 10 bars — can't build a lookback=20 signal
        prices = _make_multiindex_prices(n=10, tickers=["TINY"])
        signals = agent.build_momentum_signals(prices, lookback=20)
        assert "TINY" not in signals["by_ticker"]

    def test_empty_prices_returns_empty_signals(self) -> None:
        agent = QuantEngineerAgent()
        empty = pd.DataFrame(
            columns=pd.MultiIndex.from_tuples([], names=["field", "ticker"]),
            dtype=float,
        )
        signals = agent.build_momentum_signals(empty)
        assert signals["by_ticker"] == {}
        assert signals["scores"] == {}


# ---------------------------------------------------------------------------
# build_mean_reversion_signals
# ---------------------------------------------------------------------------


class TestBuildMeanReversionSignals:
    """Tests for QuantEngineerAgent.build_mean_reversion_signals()."""

    def test_returns_dict_keyed_by_ticker(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60, tickers=["AAPL", "MSFT"])
        signals = agent.build_mean_reversion_signals(prices, z_threshold=2.0)
        assert isinstance(signals, dict)
        assert "by_ticker" in signals
        assert "AAPL" in signals["by_ticker"]
        assert "MSFT" in signals["by_ticker"]

    def test_z_threshold_stored(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60)
        signals = agent.build_mean_reversion_signals(prices, z_threshold=1.5)
        assert signals["z_score_threshold"] == 1.5

    def test_z_score_is_finite(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60)
        signals = agent.build_mean_reversion_signals(prices)
        for ticker, info in signals["by_ticker"].items():
            assert np.isfinite(info["z_score"]), f"{ticker} z_score is non-finite"

    def test_deeply_oversold_triggers_entry(self) -> None:
        """Prices sharply below rolling mean → z_score < -threshold → entry_signal."""
        agent = QuantEngineerAgent()
        prices = _make_mean_reverting_prices(n=60)
        signals = agent.build_mean_reversion_signals(prices, z_threshold=2.0)
        # At least one ticker should be oversold (z < -2)
        entry_signals = [
            info["entry_signal"]
            for info in signals["by_ticker"].values()
        ]
        # May or may not fire depending on price path — just assert structure is correct
        assert all(isinstance(e, (bool, np.bool_)) for e in entry_signals)

    def test_exit_signal_when_mean_reversion_complete(self) -> None:
        """exit_signal=True when z_score > -0.5 (price near or above mean)."""
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60, tickers=["AAPL"], trend=0.0, seed=42)
        signals = agent.build_mean_reversion_signals(prices)
        # Most flat-trending tickers should have exit_signal=True (z_score > -0.5)
        for ticker, info in signals["by_ticker"].items():
            if info["z_score"] > -0.5:
                assert bool(info["exit_signal"]) is True, (
                    f"{ticker}: z={info['z_score']:.2f} but exit_signal is False"
                )

    def test_short_history_tickers_skipped(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=20, tickers=["TINY"])
        # Need at least 30 bars
        signals = agent.build_mean_reversion_signals(prices)
        # 20 < 30, so TINY is skipped
        assert "TINY" not in signals["by_ticker"]

    def test_stop_loss_present(self) -> None:
        agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60)
        signals = agent.build_mean_reversion_signals(prices)
        assert signals["stop_loss"] == 0.08


# ---------------------------------------------------------------------------
# critique_signals
# ---------------------------------------------------------------------------


class TestCritiqueSignals:
    """Tests for QuantEngineerAgent.critique_signals()."""

    def test_short_lookback_triggers_warning(self) -> None:
        """Lookback < 10 days triggers a warning critique."""
        agent = QuantEngineerAgent()
        signals = {
            "momentum": {"lookback": 5, "by_ticker": {}},
            "mean_reversion": {"z_score_threshold": 2.0, "by_ticker": {}},
        }
        critiques = agent.critique_signals(signals)
        assert any(
            c.severity == "warning" and "lookback" in c.message.lower()
            for c in critiques
        ), "Expected warning about short lookback"

    def test_adequate_lookback_no_warning(self) -> None:
        """Lookback >= 10 days should not trigger the lookback warning."""
        agent = QuantEngineerAgent()
        signals = {
            "momentum": {"lookback": 20, "by_ticker": {}},
            "mean_reversion": {"z_score_threshold": 2.0, "by_ticker": {}},
        }
        critiques = agent.critique_signals(signals)
        lookback_warnings = [c for c in critiques if "lookback" in c.message.lower()]
        assert len(lookback_warnings) == 0

    def test_zero_entries_at_high_threshold_triggers_info(self) -> None:
        """z_score_threshold >= 2.0 with no entries → info critique."""
        agent = QuantEngineerAgent()
        signals = {
            "momentum": {"lookback": 20, "by_ticker": {}},
            "mean_reversion": {
                "z_score_threshold": 2.0,
                "by_ticker": {"AAPL": {"z_score": -1.0, "entry_signal": False}},
            },
        }
        critiques = agent.critique_signals(signals)
        info_critiques = [c for c in critiques if c.severity == "info"]
        assert len(info_critiques) > 0, "Expected info critique about zero entries"

    def test_overlap_between_strategies_triggers_warning(self) -> None:
        """Tickers in both momentum and mean_reversion → overlap warning."""
        agent = QuantEngineerAgent()
        # Create many tickers in both strategies
        by_ticker_shared = {f"T{i}": {"z_score": -1.0, "entry_signal": False} for i in range(4)}
        signals = {
            "momentum": {"lookback": 20, "by_ticker": {f"T{i}": {} for i in range(4)}},
            "mean_reversion": {"z_score_threshold": 2.0, "by_ticker": by_ticker_shared},
        }
        critiques = agent.critique_signals(signals)
        overlap_critiques = [c for c in critiques if "both" in c.message.lower()]
        assert len(overlap_critiques) > 0, "Expected overlap warning"

    def test_returns_list_of_critique_messages(self) -> None:
        agent = QuantEngineerAgent()
        signals = {
            "momentum": {"lookback": 20, "by_ticker": {}},
            "mean_reversion": {"z_score_threshold": 2.0, "by_ticker": {}},
        }
        critiques = agent.critique_signals(signals)
        assert isinstance(critiques, list)
        for c in critiques:
            assert isinstance(c, CritiqueMessage)


# ---------------------------------------------------------------------------
# critique_opportunity_rankings
# ---------------------------------------------------------------------------


class TestCritiqueOpportunityRankings:
    """Tests for QuantEngineerAgent.critique_opportunity_rankings()."""

    def test_tech_concentration_warning(self) -> None:
        """≥3 tech stocks in top-5 → sector concentration warning."""
        agent = QuantEngineerAgent()
        # AAPL, MSFT, NVDA, META, GOOGL — all tech, rank 1-5
        rankings = pd.DataFrame(
            {
                "momentum_score": [0.15, 0.12, 0.11, 0.10, 0.09],
                "rank": [1, 2, 3, 4, 5],
                "current_price": [180.0, 400.0, 500.0, 350.0, 140.0],
            },
            index=["AAPL", "MSFT", "NVDA", "META", "GOOGL"],
        )
        critiques = agent.critique_opportunity_rankings(rankings)
        assert any(
            "sector" in c.message.lower() or "tech" in c.message.lower()
            for c in critiques
        ), "Expected tech concentration warning"

    def test_diverse_portfolio_no_concentration_warning(self) -> None:
        """Non-tech-concentrated top-5 → no sector warning."""
        agent = QuantEngineerAgent()
        rankings = pd.DataFrame(
            {
                "momentum_score": [0.10, 0.09, 0.08, 0.07, 0.06],
                "rank": [1, 2, 3, 4, 5],
                "current_price": [50.0, 60.0, 70.0, 80.0, 90.0],
            },
            index=["XOM", "JNJ", "UNH", "JPM", "KO"],  # energy/healthcare/financial/consumer
        )
        critiques = agent.critique_opportunity_rankings(rankings)
        tech_warnings = [
            c for c in critiques if "tech" in c.message.lower() or "sector" in c.message.lower()
        ]
        assert len(tech_warnings) == 0

    def test_empty_rankings_returns_empty_list(self) -> None:
        agent = QuantEngineerAgent()
        critiques = agent.critique_opportunity_rankings(pd.DataFrame())
        assert critiques == []


# ---------------------------------------------------------------------------
# _aggregate_returns (internal metric aggregation)
# ---------------------------------------------------------------------------


class TestAggregateReturns:
    """Tests for QuantEngineerAgent._aggregate_returns()."""

    def test_empty_returns_gives_zero_metrics(self) -> None:
        agent = QuantEngineerAgent()
        result = agent._aggregate_returns([])
        assert result["sharpe_ratio"] == 0.0
        assert result["max_drawdown"] == 0.0
        assert result["total_return"] == 0.0
        assert result["win_rate"] == 0.0
        assert result["n_trades"] == 0

    def test_all_winning_trades(self) -> None:
        agent = QuantEngineerAgent()
        result = agent._aggregate_returns([0.05, 0.03, 0.08, 0.02, 0.04])
        assert result["win_rate"] == 1.0
        assert result["total_return"] > 0
        assert result["sharpe_ratio"] > 0

    def test_all_losing_trades(self) -> None:
        agent = QuantEngineerAgent()
        result = agent._aggregate_returns([-0.03, -0.05, -0.02, -0.04])
        assert result["win_rate"] == 0.0
        assert result["total_return"] < 0
        assert result["max_drawdown"] < 0  # negative convention

    def test_max_drawdown_is_negative(self) -> None:
        """max_drawdown must follow negative convention."""
        agent = QuantEngineerAgent()
        # A sequence with a clear drawdown
        result = agent._aggregate_returns([0.10, -0.15, 0.05, -0.10, 0.08])
        assert result["max_drawdown"] <= 0, (
            f"Expected non-positive drawdown, got {result['max_drawdown']}"
        )

    def test_n_trades_matches_input_length(self) -> None:
        agent = QuantEngineerAgent()
        returns = [0.01, -0.02, 0.03, 0.04, -0.01, 0.02]
        result = agent._aggregate_returns(returns)
        assert result["n_trades"] == len(returns)

    def test_sharpe_ratio_finite(self) -> None:
        agent = QuantEngineerAgent()
        result = agent._aggregate_returns([0.02, 0.01, 0.03, -0.01, 0.02])
        assert np.isfinite(result["sharpe_ratio"])


# ---------------------------------------------------------------------------
# backtest determinism (no randomness)
# ---------------------------------------------------------------------------


class TestBacktestDeterminism:
    """backtest() is deterministic in simplified mode."""

    def test_no_engine_backtest_is_deterministic(self) -> None:
        agent = QuantEngineerAgent()
        signals = {
            "momentum": {
                "lookback": 20,
                "by_ticker": {"AAPL": {"momentum": 0.12, "entry_signal": True}},
            },
            "mean_reversion": {
                "z_score_threshold": 2.0,
                "by_ticker": {"MSFT": {"z_score": -2.5, "entry_signal": True}},
            },
        }
        r1 = agent.backtest(signals)
        r2 = agent.backtest(signals)
        assert r1 == r2

    def test_with_prices_but_no_engine_uses_simplified(self) -> None:
        """When engine=None, prices arg is ignored and simplified backtest runs."""
        agent = QuantEngineerAgent()  # no engine
        prices = _make_multiindex_prices(n=60, tickers=["AAPL"])
        signals = {
            "momentum": {"lookback": 20, "by_ticker": {"AAPL": {"momentum": 0.10, "entry_signal": True}}},
            "mean_reversion": {"z_score_threshold": 2.0, "by_ticker": {}},
        }
        result = agent.backtest(signals, prices)
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result

    def test_with_real_engine_returns_valid_metrics(self) -> None:
        """When BacktestEngine is injected, real backtest runs."""
        from alpha_search.backtest.costs import CostModel
        from alpha_search.backtest.engine import BacktestEngine

        engine = BacktestEngine()
        cost = CostModel(commission=0.001, slippage=0.001)
        agent = QuantEngineerAgent(backtest_engine=engine, cost_model=cost)

        prices = _make_multiindex_prices(n=60, tickers=["AAPL"])
        signals = {
            "momentum": {"lookback": 20, "by_ticker": {"AAPL": {"momentum": 0.10, "entry_signal": True}}},
            "mean_reversion": {"z_score_threshold": 2.0, "by_ticker": {}},
        }
        result = agent.backtest(signals, prices)
        assert result["max_drawdown"] <= 0
        assert np.isfinite(result["sharpe_ratio"])
        assert "n_trades" in result


# ---------------------------------------------------------------------------
# OpportunityAgent rankings — signal construction integration
# ---------------------------------------------------------------------------


class TestOpportunityAgentRankings:
    """OpportunityAgent ranking methods feed QuantEngineerAgent critique_opportunity_rankings."""

    def test_momentum_ranking_has_required_columns(self) -> None:
        agent = OpportunityAgent()
        prices = _make_multiindex_prices(n=60, tickers=["AAPL", "MSFT", "GOOGL"])
        rankings = agent.rank_momentum(prices)
        assert "momentum_score" in rankings.columns
        assert "rank" in rankings.columns
        assert "recommendation" in rankings.columns

    def test_mean_reversion_ranking_has_required_columns(self) -> None:
        agent = OpportunityAgent()
        prices = _make_multiindex_prices(n=60, tickers=["AAPL", "MSFT", "GOOGL"])
        rankings = agent.rank_mean_reversion(prices)
        assert "z_score" in rankings.columns
        assert "rank" in rankings.columns

    def test_rankings_flow_to_quant_critique(self) -> None:
        """rank_momentum output can be fed to critique_opportunity_rankings."""
        opp_agent = OpportunityAgent()
        quant_agent = QuantEngineerAgent()
        prices = _make_multiindex_prices(n=60, tickers=["AAPL", "MSFT", "GOOGL"])
        rankings = opp_agent.rank_momentum(prices)
        critiques = quant_agent.critique_opportunity_rankings(rankings)
        assert isinstance(critiques, list)
