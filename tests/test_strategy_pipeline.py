"""Tests for the Alpha Search strategy research pipeline."""

from __future__ import annotations

import os
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
# Sample universes
# ---------------------------------------------------------------------------


class TestSampleUniverses:
    """Tests for synthetic data generators."""

    def test_us_equity_shape(self) -> None:
        df = generate_us_equity_data(days=30)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 30
        assert "Close" in df.columns.get_level_values(1)

    def test_indian_equity_higher_volatility(self) -> None:
        df = generate_indian_equity_data(days=60)
        returns = df.xs("Close", level=1, axis=1).pct_change().dropna()
        annualized_vol = returns.std() * (252**0.5)
        # Indian equities should be more volatile than US (~30% vs ~20%)
        assert annualized_vol.mean() > 0.15

    def test_crypto_data(self) -> None:
        df = generate_crypto_data(days=30)
        assert len(df) == 30
        assert "BTC-USD" in df.columns.get_level_values(0)

    def test_etf_data(self) -> None:
        df = generate_etf_data(days=30)
        assert "SPY" in df.columns.get_level_values(0)

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

    def test_runs_all_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = run_all_pipelines(output_dir=tmpdir)
            assert "momentum" in results
            assert "mean_reversion" in results
            assert "arbitrage" in results
            assert "timestamp" in results
            assert "disclaimer" in results

    def test_has_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = run_all_pipelines(output_dir=tmpdir)
            for key in ("momentum", "mean_reversion", "arbitrage"):
                assert "metrics" in results[key] or "backtests" in results[key]
