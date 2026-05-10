"""Tests for the Alpha Search strategy research pipeline.

These tests use real market data fetched from Yahoo Finance and
CoinGecko.  Network access is required.
"""

from __future__ import annotations

import tempfile

import pandas as pd
import pytest

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

# ---------------------------------------------------------------------------
# Sample universes (real data)
# ---------------------------------------------------------------------------


class TestSampleUniverses:
    """Tests for real data fetchers."""

    @pytest.mark.network
    def test_us_equity_shape(self) -> None:
        df = generate_us_equity_data(days=30)
        assert isinstance(df, pd.DataFrame)
        # Real data may have gaps for holidays; expect roughly 20-30 rows
        assert 15 <= len(df) <= 35, f"Expected 15-35 rows, got {len(df)}"
        assert "Close" in df.columns.get_level_values(1)

    @pytest.mark.network
    def test_indian_equity_has_data(self) -> None:
        df = generate_indian_equity_data(days=60)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 10, f"Expected >10 rows, got {len(df)}"
        # Real Indian equities should have some volatility
        returns = df.xs("Close", level=1, axis=1).pct_change().dropna()
        assert not returns.empty

    @pytest.mark.network
    def test_crypto_data(self) -> None:
        df = generate_crypto_data(days=30)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 10, f"Expected >10 rows, got {len(df)}"
        # CoinGecko coin IDs are used as column names
        coin_ids = [c for c in df.columns.get_level_values(0).unique()]
        assert len(coin_ids) > 0

    @pytest.mark.network
    def test_etf_data(self) -> None:
        df = generate_etf_data(days=30)
        assert "SPY" in df.columns.get_level_values(0)

    @pytest.mark.network
    def test_ohlcv_integrity(self) -> None:
        """High >= max(Open, Close) and Low <= min(Open, Close)."""
        df = generate_us_equity_data(days=30)
        for ticker in df.columns.get_level_values(0).unique():
            subset = df[ticker]
            assert (subset["High"] >= subset["Open"]).all()
            assert (subset["High"] >= subset["Close"]).all()
            assert (subset["Low"] <= subset["Open"]).all()
            assert (subset["Low"] <= subset["Close"]).all()


# ---------------------------------------------------------------------------
# Momentum pipeline
# ---------------------------------------------------------------------------


class TestMomentumPipeline:
    """Tests for MomentumPipeline."""

    @pytest.fixture
    def pipeline(self) -> MomentumPipeline:
        df = generate_us_equity_data(days=100, seed=42)
        tickers = list(df.columns.get_level_values(0).unique())[:3]
        return MomentumPipeline(prices=df, tickers=tickers, capital=100_000.0)

    def test_discover_opportunities(self, pipeline: MomentumPipeline) -> None:
        opps = pipeline.discover_opportunities()
        assert isinstance(opps, pd.DataFrame)
        assert len(opps) == 3
        assert "momentum_score" in opps.columns

    def test_generate_signals(self, pipeline: MomentumPipeline) -> None:
        signals = pipeline.generate_signals()
        assert isinstance(signals, dict)
        assert len(signals) == 3
        for ticker, sig in signals.items():
            assert isinstance(sig, pd.Series)

    def test_backtest(self, pipeline: MomentumPipeline) -> None:
        signals = pipeline.generate_signals()
        backtests = pipeline.backtest(signals)
        assert isinstance(backtests, dict)
        assert len(backtests) == 3

    def test_compute_metrics(self, pipeline: MomentumPipeline) -> None:
        signals = pipeline.generate_signals()
        backtests = pipeline.backtest(signals)
        metrics = pipeline.compute_metrics(backtests)
        assert isinstance(metrics, pd.DataFrame)
        assert "total_return" in metrics.columns
        assert "sharpe_ratio" in metrics.columns

    def test_run(self, pipeline: MomentumPipeline) -> None:
        results = pipeline.run()
        assert "opportunities" in results
        assert "signals" in results
        assert "backtests" in results
        assert "metrics" in results
        assert "hypothesis" in results
        assert "risks" in results


# ---------------------------------------------------------------------------
# Mean reversion pipeline
# ---------------------------------------------------------------------------


class TestMeanReversionPipeline:
    """Tests for MeanReversionPipeline."""

    @pytest.fixture
    def pipeline(self) -> MeanReversionPipeline:
        df = generate_us_equity_data(days=100, seed=43)
        tickers = list(df.columns.get_level_values(0).unique())[:3]
        return MeanReversionPipeline(prices=df, tickers=tickers, capital=100_000.0)

    def test_discover_opportunities(self, pipeline: MeanReversionPipeline) -> None:
        opps = pipeline.discover_opportunities()
        assert isinstance(opps, pd.DataFrame)
        assert "zscore" in opps.columns

    def test_run(self, pipeline: MeanReversionPipeline) -> None:
        results = pipeline.run()
        assert "metrics" in results
        assert "hypothesis" in results


# ---------------------------------------------------------------------------
# Arbitrage pipeline
# ---------------------------------------------------------------------------


class TestArbitragePipeline:
    """Tests for ArbitragePipeline."""

    @pytest.fixture
    def pipeline(self) -> ArbitragePipeline:
        df = generate_us_equity_data(days=100, seed=44)
        tickers = list(df.columns.get_level_values(0).unique())[:4]
        return ArbitragePipeline(prices=df, tickers=tickers, capital=100_000.0)

    def test_find_pairs(self, pipeline: ArbitragePipeline) -> None:
        pairs = pipeline.find_pairs(min_correlation=0.5)
        assert isinstance(pairs, pd.DataFrame)
        assert "correlation" in pairs.columns

    def test_run(self, pipeline: ArbitragePipeline) -> None:
        results = pipeline.run()
        assert "pairs" in results or "metrics" in results
        assert "hypothesis" in results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestRunAllPipelines:
    """Tests for the run_all_pipelines orchestrator."""

    @pytest.mark.network
    def test_runs_all_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = run_all_pipelines(output_dir=tmpdir)
            assert "momentum" in results
            assert "mean_reversion" in results
            assert "arbitrage" in results
            assert "timestamp" in results
            assert "disclaimer" in results

    @pytest.mark.network
    def test_has_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = run_all_pipelines(output_dir=tmpdir)
            for key in ("momentum", "mean_reversion", "arbitrage"):
                assert "metrics" in results[key] or "backtests" in results[key]
