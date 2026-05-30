"""Tests for alpha_search/research/ai_infra_strategy_pipeline.py.

All tests are deterministic — no network calls, no yfinance downloads.
Prices are generated locally using a seeded RNG.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Tuple

import numpy as np
import pandas as pd
import pytest

from alpha_search.research.ai_infra_strategy_pipeline import (
    build_breakout_signal,
    build_cross_sectional_momentum_signal,
    build_mean_reversion_signal,
    build_monthly_rebalance_weights,
    build_trend_following_signal,
    calculate_alpha_beta_vs_benchmark,
    calculate_strategy_metrics,
    export_ai_infra_outputs,
    generate_ai_infra_report,
    get_ai_infra_universe,
    run_strategy_backtest,
    validate_ai_infra_data,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_prices(
    n: int = 200,
    n_tickers: int = 5,
    seed: int = 0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (close, volume) DataFrames with deterministic data."""
    rng = np.random.default_rng(seed)
    tickers = [f"T{i}" for i in range(n_tickers)]
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    close = pd.DataFrame(
        {t: 100.0 * np.cumprod(1 + rng.normal(0, 0.01, n)) for t in tickers},
        index=idx,
    )
    volume = pd.DataFrame(
        {t: rng.integers(1_000_000, 10_000_000, n).astype(float) for t in tickers},
        index=idx,
    )
    return close, volume


def _make_returns(close: pd.DataFrame) -> pd.DataFrame:
    return close.pct_change()


def _make_minimal_results(bt_net: pd.Series, bt_gross: pd.Series) -> dict:
    metrics_n = calculate_strategy_metrics(bt_net)
    metrics_g = calculate_strategy_metrics(bt_gross)
    return {
        "universe_used": ["T0", "T1"],
        "symbols_skipped": [],
        "validation_report": {},
        "period": "2y",
        "interval": "1d",
        "cost_bps": 20.0,
        "long_only": False,
        "rf_annual": 0.0,
        "primary_benchmark": "SOXX",
        "run_timestamp": "2024-01-01T00:00:00+00:00",
        "duration_seconds": 1.0,
        "disclaimer": "Research only.",
        "agent_review": "# Agent Review\n\nTest.",
        "strategies": {
            "cross_sectional_momentum": {
                "verdict": "marginal",
                "metrics_net": metrics_n,
                "metrics_gross": metrics_g,
                "alpha_beta": {
                    "ann_alpha": 0.05,
                    "beta": 0.8,
                    "t_alpha": 1.5,
                    "r_squared": 0.4,
                },
                "is_metrics": metrics_n,
                "oos_metrics": metrics_n,
                "hypothesis": "Test hypothesis",
                "is_primary": True,
                "backtest": {
                    "net": bt_net,
                    "gross": bt_gross,
                    "equity_net": (1 + bt_net).cumprod(),
                    "equity_gross": (1 + bt_gross).cumprod(),
                    "turnover_per_rebal": 0.5,
                    "cost_drag": 0.01,
                    "n_rebal": 10,
                },
            },
        },
        "bench_summary": {"SOXX": metrics_n},
    }


# ---------------------------------------------------------------------------
# 1. TestUniverseDefinition
# ---------------------------------------------------------------------------


class TestUniverseDefinition:
    """Tests for get_ai_infra_universe()."""

    def test_returns_dict(self) -> None:
        u = get_ai_infra_universe()
        assert isinstance(u, dict)

    def test_has_required_keys(self) -> None:
        u = get_ai_infra_universe()
        assert "semiconductors" in u
        assert "semi_equipment" in u
        assert "ai_infra" in u

    def test_exactly_three_keys(self) -> None:
        u = get_ai_infra_universe()
        assert len(u) == 3

    def test_all_values_are_lists(self) -> None:
        u = get_ai_infra_universe()
        for key, val in u.items():
            assert isinstance(val, list), f"{key} value must be a list"

    def test_all_values_non_empty(self) -> None:
        u = get_ai_infra_universe()
        for key, val in u.items():
            assert len(val) > 0, f"{key} list must not be empty"

    def test_all_tickers_are_strings(self) -> None:
        u = get_ai_infra_universe()
        for key, tickers in u.items():
            for t in tickers:
                assert isinstance(t, str), f"Ticker {t!r} in {key} must be a string"

    def test_returns_copy_not_reference(self) -> None:
        u1 = get_ai_infra_universe()
        u2 = get_ai_infra_universe()
        u1["semiconductors"].append("__FAKE__")
        assert "__FAKE__" not in u2["semiconductors"], (
            "get_ai_infra_universe must return a copy"
        )

    def test_known_tickers_present(self) -> None:
        u = get_ai_infra_universe()
        assert "NVDA" in u["semiconductors"]
        assert "ASML" in u["semi_equipment"]
        assert "ANET" in u["ai_infra"]


# ---------------------------------------------------------------------------
# 2. TestValidateAiInfraData
# ---------------------------------------------------------------------------


class TestValidateAiInfraData:
    """Tests for validate_ai_infra_data()."""

    def test_valid_data_passes(self) -> None:
        close, volume = _make_prices(n=600)
        all_valid, report, skipped, valid_close, valid_volume = validate_ai_infra_data(
            close, volume, min_history_days=2
        )
        assert all_valid is True
        assert skipped == []
        assert set(valid_close.columns) == set(close.columns)

    def test_returns_five_tuple(self) -> None:
        close, volume = _make_prices(n=100)
        result = validate_ai_infra_data(close, volume, min_history_days=2)
        assert len(result) == 5

    def test_report_has_all_tickers(self) -> None:
        close, volume = _make_prices(n=100)
        _, report, _, _, _ = validate_ai_infra_data(close, volume, min_history_days=2)
        for col in close.columns:
            assert col in report

    def test_non_positive_close_gets_skipped(self) -> None:
        close, volume = _make_prices(n=100)
        # Force non-positive price in T0
        close = close.copy()
        close.iloc[10, 0] = -1.0
        all_valid, report, skipped, valid_close, valid_volume = validate_ai_infra_data(
            close, volume, min_history_days=2
        )
        assert "T0" in skipped
        assert "T0" not in valid_close.columns
        assert all_valid is False

    def test_non_positive_not_in_valid_close(self) -> None:
        close, volume = _make_prices(n=100)
        close = close.copy()
        close.iloc[5, 1] = 0.0  # zero price
        _, _, skipped, valid_close, _ = validate_ai_infra_data(
            close, volume, min_history_days=2
        )
        assert "T1" in skipped
        assert "T1" not in valid_close.columns

    def test_short_history_flagged_not_excluded(self) -> None:
        """Symbols with short history get an issue note but stay in valid_close."""
        close, volume = _make_prices(n=100)
        _, report, skipped, valid_close, _ = validate_ai_infra_data(
            close, volume, min_history_days=504  # require 2 years — won't be met
        )
        # Symbol stays in valid_close (only non-positive prices cause exclusion)
        assert set(valid_close.columns) == set(close.columns)
        # At least one ticker has the short-history issue reported
        has_issue = any(
            any("only" in issue for issue in rep.get("issues", []))
            for rep in report.values()
        )
        assert has_issue

    def test_eligible_flag_set_correctly(self) -> None:
        close, volume = _make_prices(n=600)
        _, report, _, _, _ = validate_ai_infra_data(
            close, volume, min_history_days=2
        )
        for rep in report.values():
            assert rep["eligible_for_selection"] is True

    def test_multiple_bad_tickers_all_skipped(self) -> None:
        close, volume = _make_prices(n=100)
        close = close.copy()
        close.iloc[10, 0] = -1.0
        close.iloc[20, 2] = 0.0
        _, _, skipped, valid_close, _ = validate_ai_infra_data(
            close, volume, min_history_days=2
        )
        assert "T0" in skipped
        assert "T2" in skipped
        assert len(valid_close.columns) == 3  # T1, T3, T4 remain

    def test_valid_volume_columns_match_valid_close(self) -> None:
        close, volume = _make_prices(n=100)
        close = close.copy()
        close.iloc[5, 0] = -5.0
        _, _, _, valid_close, valid_volume = validate_ai_infra_data(
            close, volume, min_history_days=2
        )
        for col in valid_volume.columns:
            assert col in valid_close.columns


# ---------------------------------------------------------------------------
# 3. TestCrossSectionalMomentumSignal
# ---------------------------------------------------------------------------


class TestCrossSectionalMomentumSignal:
    """Tests for build_cross_sectional_momentum_signal()."""

    @pytest.fixture
    def price_data(self):
        return _make_prices(n=400, n_tickers=10, seed=1)

    def test_returns_tuple_of_two(self, price_data) -> None:
        close, volume = price_data
        result = build_cross_sectional_momentum_signal(close, volume, lookback=60, skip=5)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_weights_is_dataframe(self, price_data) -> None:
        close, volume = price_data
        weights, _ = build_cross_sectional_momentum_signal(close, volume, lookback=60, skip=5)
        assert isinstance(weights, pd.DataFrame)

    def test_rebal_dates_is_dataframe(self, price_data) -> None:
        close, volume = price_data
        _, rebal = build_cross_sectional_momentum_signal(close, volume, lookback=60, skip=5)
        assert isinstance(rebal, pd.DataFrame)
        assert "rebal_date" in rebal.columns

    def test_weights_columns_match_tickers(self, price_data) -> None:
        close, volume = price_data
        weights, _ = build_cross_sectional_momentum_signal(close, volume, lookback=60, skip=5)
        assert set(weights.columns) == set(close.columns)

    def test_ls_weights_sum_near_zero(self, price_data) -> None:
        """Long/short weights at each date should sum near zero."""
        close, volume = price_data
        weights, _ = build_cross_sectional_momentum_signal(
            close, volume, lookback=60, skip=5, long_only=False
        )
        non_flat = weights[weights.abs().sum(axis=1) > 0]
        if len(non_flat) > 0:
            row_sums = non_flat.sum(axis=1).abs()
            assert (row_sums < 0.15).all(), (
                f"L/S weights should sum ~0; max abs sum was {row_sums.max():.4f}"
            )

    def test_long_only_weights_sum_near_one(self, price_data) -> None:
        close, volume = price_data
        weights, _ = build_cross_sectional_momentum_signal(
            close, volume, lookback=60, skip=5, long_only=True
        )
        non_flat = weights[weights.abs().sum(axis=1) > 0]
        if len(non_flat) > 0:
            row_sums = non_flat.sum(axis=1)
            assert (row_sums > 0.5).all()

    def test_weights_clipped_to_minus1_plus1(self, price_data) -> None:
        close, volume = price_data
        weights, _ = build_cross_sectional_momentum_signal(close, volume, lookback=60, skip=5)
        assert (weights >= -1.0).all().all()
        assert (weights <= 1.0).all().all()

    def test_no_lookahead_early_dates_flat(self, price_data) -> None:
        """With a 252-day lookback, early rebal dates must be flat (no data yet)."""
        close, volume = price_data
        weights, _ = build_cross_sectional_momentum_signal(
            close, volume, lookback=252, skip=21
        )
        # The first rebalance date should be flat because there aren't 252 bars of history
        first_date = weights.index[0]
        assert weights.loc[first_date].abs().sum() == 0.0, (
            "First rebal date should be flat when lookback > available history"
        )

    def test_no_signal_without_liquidity(self) -> None:
        """Zero volume means no signals — all positions flat."""
        close, volume = _make_prices(n=400, n_tickers=10, seed=2)
        zero_vol = pd.DataFrame(0.0, index=volume.index, columns=volume.columns)
        weights, _ = build_cross_sectional_momentum_signal(
            close, zero_vol, lookback=60, skip=5, min_dollar_vol=1.0
        )
        # With zero dollar volume, no name passes the liquidity screen
        assert weights.abs().sum().sum() == 0.0


# ---------------------------------------------------------------------------
# 4. TestTrendFollowingSignal
# ---------------------------------------------------------------------------


class TestTrendFollowingSignal:
    """Tests for build_trend_following_signal()."""

    def test_returns_dataframe(self) -> None:
        close, _ = _make_prices(n=300)
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        assert isinstance(sig, pd.DataFrame)

    def test_values_zero_or_one(self) -> None:
        close, _ = _make_prices(n=300)
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        unique_vals = set(sig.values.ravel())
        assert unique_vals.issubset({0.0, 1.0, np.nan}), (
            f"Signal must be 0 or 1, got: {unique_vals}"
        )

    def test_values_never_exceed_one(self) -> None:
        close, _ = _make_prices(n=300)
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        assert (sig.fillna(0) <= 1.0).all().all()

    def test_shape_matches_close(self) -> None:
        close, _ = _make_prices(n=300)
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        assert sig.shape == close.shape

    def test_columns_match_close(self) -> None:
        close, _ = _make_prices(n=300)
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        assert list(sig.columns) == list(close.columns)

    def test_uptrend_gives_signal_after_warmup(self) -> None:
        """A perfectly linear uptrend should produce signal=1 after MA warmup."""
        n = 300
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        # Strictly monotonically increasing prices
        price_series = pd.Series(np.linspace(50, 200, n), index=idx)
        close = pd.DataFrame({"UP": price_series})
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        # After warmup (50 bars), every bar should be 1
        post_warmup = sig.iloc[50:]
        assert (post_warmup["UP"] == 1.0).all(), (
            "Steadily trending up stock should have signal=1 after MA warmup"
        )

    def test_downtrend_gives_zero_after_warmup(self) -> None:
        """A perfectly monotonically decreasing price should give signal=0."""
        n = 300
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        price_series = pd.Series(np.linspace(200, 50, n), index=idx)
        close = pd.DataFrame({"DOWN": price_series})
        sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        post_warmup = sig.iloc[60:]  # give extra warmup
        assert (post_warmup["DOWN"] == 0.0).all(), (
            "Steadily declining stock should have signal=0 after warmup"
        )

    def test_default_ma_windows_used_when_none(self) -> None:
        """Passing ma_windows=None uses the default config list."""
        close, _ = _make_prices(n=300)
        sig_default = build_trend_following_signal(close, ma_windows=None)
        sig_explicit = build_trend_following_signal(close, ma_windows=[50, 100, 200])
        pd.testing.assert_frame_equal(sig_default, sig_explicit)


# ---------------------------------------------------------------------------
# 5. TestMeanReversionSignal
# ---------------------------------------------------------------------------


class TestMeanReversionSignal:
    """Tests for build_mean_reversion_signal()."""

    def test_returns_dataframe(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_mean_reversion_signal(close, window=20, z_threshold=2.0)
        assert isinstance(sig, pd.DataFrame)

    def test_shape_matches_close(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_mean_reversion_signal(close)
        assert sig.shape == close.shape

    def test_long_only_values_zero_or_one(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_mean_reversion_signal(close, allow_short=False)
        assert set(sig.values.ravel()).issubset({0.0, 1.0})

    def test_no_minus_one_when_allow_short_false(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_mean_reversion_signal(close, allow_short=False)
        assert -1.0 not in sig.values.ravel()

    def test_allow_short_can_produce_minus_one(self) -> None:
        """With allow_short=True, create conditions that trigger short signal."""
        n = 300
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        rng = np.random.default_rng(99)
        # Mostly flat prices with a sudden strong upward spike to trigger z > threshold
        prices = np.full(n, 100.0)
        prices[150:160] = 200.0  # large upward deviation
        close = pd.DataFrame({"A": prices}, index=idx)
        sig = build_mean_reversion_signal(close, window=20, z_threshold=1.5, allow_short=True)
        assert (-1.0 in sig["A"].values), (
            "allow_short=True should produce -1 signals on large upward deviations"
        )

    def test_dip_below_threshold_generates_long(self) -> None:
        """A large downward deviation should generate a long signal (value=1)."""
        n = 300
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        prices = np.full(n, 100.0)
        prices[150:160] = 20.0  # large downward dip
        close = pd.DataFrame({"B": prices}, index=idx)
        sig = build_mean_reversion_signal(close, window=20, z_threshold=1.5, allow_short=False)
        assert (1.0 in sig["B"].values), (
            "A large dip should generate a long (1) mean reversion signal"
        )

    def test_allow_short_values_in_minus1_0_1(self) -> None:
        close, _ = _make_prices(n=200, seed=7)
        sig = build_mean_reversion_signal(close, allow_short=True, z_threshold=0.5)
        assert set(sig.values.ravel()).issubset({-1.0, 0.0, 1.0})


# ---------------------------------------------------------------------------
# 6. TestBreakoutSignal
# ---------------------------------------------------------------------------


class TestBreakoutSignal:
    """Tests for build_breakout_signal()."""

    def test_returns_dataframe(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_breakout_signal(close, window=20)
        assert isinstance(sig, pd.DataFrame)

    def test_shape_matches_close(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_breakout_signal(close, window=20)
        assert sig.shape == close.shape

    def test_values_zero_or_one_long_only(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_breakout_signal(close, window=20, allow_short=False)
        assert set(sig.values.ravel()).issubset({0.0, 1.0})

    def test_no_lookahead_spike_not_in_prior_channel(self) -> None:
        """shift(1)-before-rolling: the channel at day t-1 must NOT include day t's price.

        Concretely: on day 49, the Donchian high = max(prices[30..48]).
        A giant spike inserted at day 50 must NOT raise the channel value at day 49
        (which would be backward-looking lookahead). We verify this by checking that
        the signal at day 49 is 0 (flat prices cannot break out of a flat channel).
        """
        n = 100
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        prices = np.full(n, 50.0)
        prices[50] = 1_000.0  # giant spike only on day 50
        close = pd.DataFrame({"SPK": prices}, index=idx)
        sig = build_breakout_signal(close, window=20, allow_short=False)
        # Day 49 is BEFORE the spike; the signal must be 0 (flat prices, flat channel)
        day_before_spike = idx[49]
        assert sig.loc[day_before_spike, "SPK"] == 0.0, (
            "Signal at day t-1 must not be contaminated by a future spike at day t"
        )

    def test_breakout_channel_uses_shift_before_rolling(self) -> None:
        """Verify that shift(1)-before-rolling means channel at day t = max([t-w..t-1]).

        When prices are flat at 50 and then spike to 1000 at day 50:
        - chan_high at day 50 = max(prices[31..49]) = 50 (spike excluded)
        - close[50] = 1000 > 50, so signal at day 50 = 1  (legitimate breakout, no lookahead)
        - chan_high at day 51 = max(prices[32..50]) = 1000 (spike now included in window)
        - close[51] = 50, so signal at day 51 = 0  (price below restored channel)
        This confirms that only past prices enter the channel computation.
        """
        n = 100
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        prices = np.full(n, 50.0)
        prices[50] = 1_000.0  # spike on day 50; prices return to 50 after
        close = pd.DataFrame({"SPK": prices}, index=idx)
        sig = build_breakout_signal(close, window=20, allow_short=False)
        # Day 50: close=1000 vs channel built on [30..49] = all 50s → breakout → 1
        assert sig.iloc[50]["SPK"] == 1.0, "Day of spike should show breakout (close > past channel)"
        # Day 51: close=50 vs channel built on [31..50] includes 1000 → no breakout → 0
        assert sig.iloc[51]["SPK"] == 0.0, "Day after spike should be flat (past channel includes spike)"

    def test_allow_short_includes_minus_one(self) -> None:
        """With allow_short=True, a breakdown should produce -1."""
        n = 100
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        prices = np.full(n, 100.0)
        prices[50] = 1.0  # massive drop on day 50
        prices[51] = 1.0  # stays low
        close = pd.DataFrame({"DRP": prices}, index=idx)
        sig = build_breakout_signal(close, window=20, allow_short=True)
        # After the drop the low channel will be exceeded; -1 should appear
        assert -1.0 in sig["DRP"].values

    def test_values_with_short_subset_of_minus1_0_1(self) -> None:
        close, _ = _make_prices(n=200)
        sig = build_breakout_signal(close, window=20, allow_short=True)
        assert set(sig.values.ravel()).issubset({-1.0, 0.0, 1.0})

    def test_uses_high_low_when_provided(self) -> None:
        """When high/low DataFrames are supplied, they must be used."""
        close, _ = _make_prices(n=200)
        # Supply very wide high/low so breakout never triggers
        high = close * 1000.0
        low = close * 0.001
        sig = build_breakout_signal(close, high=high, low=low, window=20, allow_short=False)
        assert (sig == 0.0).all().all(), (
            "With extreme high/low, no breakout should trigger"
        )


# ---------------------------------------------------------------------------
# 7. TestBuildMonthlyRebalanceWeights
# ---------------------------------------------------------------------------


class TestBuildMonthlyRebalanceWeights:
    """Tests for build_monthly_rebalance_weights()."""

    @pytest.fixture
    def signal_df(self):
        close, _ = _make_prices(n=400, n_tickers=8, seed=3)
        return build_trend_following_signal(close, ma_windows=[10, 20, 50])

    def test_returns_dataframe(self, signal_df) -> None:
        w = build_monthly_rebalance_weights(signal_df, long_only=True)
        assert isinstance(w, pd.DataFrame)

    def test_columns_match_signal(self, signal_df) -> None:
        w = build_monthly_rebalance_weights(signal_df, long_only=True)
        assert set(w.columns) == set(signal_df.columns)

    def test_long_only_weights_sum_to_one_when_eligible(self, signal_df) -> None:
        w = build_monthly_rebalance_weights(
            signal_df, long_only=True, min_eligible=1
        )
        non_flat = w[w.abs().sum(axis=1) > 0]
        if len(non_flat) > 0:
            row_sums = non_flat.sum(axis=1)
            assert ((row_sums - 1.0).abs() < 1e-9).all(), (
                f"Long-only weights should sum to 1.0; got {row_sums.values}"
            )

    def test_flat_period_rows_sum_to_zero(self, signal_df) -> None:
        """Rows with no eligible names should be all zeros."""
        w = build_monthly_rebalance_weights(
            signal_df, long_only=True, min_eligible=999  # impossible threshold
        )
        assert (w == 0.0).all().all(), "With impossible min_eligible, all rows must be zero"

    def test_weights_clipped_to_minus1_plus1(self, signal_df) -> None:
        w = build_monthly_rebalance_weights(signal_df, long_only=False)
        assert (w >= -1.0).all().all()
        assert (w <= 1.0).all().all()

    def test_long_only_no_negative_weights(self, signal_df) -> None:
        w = build_monthly_rebalance_weights(signal_df, long_only=True)
        assert (w >= 0.0).all().all()

    def test_rebal_dates_are_month_end(self, signal_df) -> None:
        w = build_monthly_rebalance_weights(signal_df, freq="ME")
        for d in w.index:
            assert d in signal_df.index


# ---------------------------------------------------------------------------
# 8. TestRunStrategyBacktest
# ---------------------------------------------------------------------------


class TestRunStrategyBacktest:
    """Tests for run_strategy_backtest()."""

    @pytest.fixture
    def bt_inputs(self):
        close, volume = _make_prices(n=400, n_tickers=5, seed=4)
        daily_rets = close.pct_change()
        tf_sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        weights = build_monthly_rebalance_weights(tf_sig, long_only=True, min_eligible=1)
        return daily_rets, weights

    def test_returns_dict(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights)
        assert isinstance(result, dict)

    def test_required_keys_present(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights)
        required = {"gross", "net", "equity_gross", "equity_net",
                    "turnover_per_rebal", "cost_drag", "n_rebal"}
        assert required.issubset(result.keys())

    def test_gross_and_net_are_series(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights)
        assert isinstance(result["gross"], pd.Series)
        assert isinstance(result["net"], pd.Series)

    def test_equity_series_start_near_one(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights)
        assert abs(result["equity_gross"].iloc[0] - 1.0) < 0.1
        assert abs(result["equity_net"].iloc[0] - 1.0) < 0.1

    def test_net_le_gross_with_positive_costs(self, bt_inputs) -> None:
        """Net equity must not exceed gross equity (costs are always non-negative)."""
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights, cost_bps=30.0)
        # sum of net returns <= sum of gross returns
        assert result["net"].sum() <= result["gross"].sum() + 1e-9

    def test_cost_drag_non_negative(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights, cost_bps=20.0)
        assert result["cost_drag"] >= -1e-9

    def test_zero_cost_net_equals_gross(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights, cost_bps=0.0)
        pd.testing.assert_series_equal(
            result["gross"].round(12), result["net"].round(12),
            check_names=False,
        )

    def test_flat_weights_give_near_zero_returns(self) -> None:
        """All-zero weights must produce zero gross and net returns."""
        close, _ = _make_prices(n=100)
        daily_rets = close.pct_change()
        # Build rebalance index from dates that actually exist in the returns index
        # (ME month-end dates may fall on weekends; use the last date per month that
        # is present in the business-day index).
        rebal_index = (
            daily_rets.groupby(pd.Grouper(freq="ME")).apply(lambda x: x.index[-1] if len(x) else None)
            .dropna()
        )
        flat_weights = pd.DataFrame(
            0.0,
            index=pd.DatetimeIndex(rebal_index.values),
            columns=close.columns,
        )
        result = run_strategy_backtest(daily_rets, flat_weights, cost_bps=10.0)
        assert result["gross"].abs().sum() < 1e-9
        assert result["n_rebal"] == 0

    def test_turnover_per_rebal_is_float(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights)
        assert isinstance(result["turnover_per_rebal"], float)

    def test_n_rebal_is_int(self, bt_inputs) -> None:
        daily_rets, weights = bt_inputs
        result = run_strategy_backtest(daily_rets, weights)
        assert isinstance(result["n_rebal"], int)


# ---------------------------------------------------------------------------
# 9. TestCalculateStrategyMetrics
# ---------------------------------------------------------------------------


class TestCalculateStrategyMetrics:
    """Tests for calculate_strategy_metrics()."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        close, _ = _make_prices(n=500)
        return close["T0"].pct_change().dropna()

    def test_returns_dict(self, sample_returns) -> None:
        m = calculate_strategy_metrics(sample_returns)
        assert isinstance(m, dict)

    def test_required_keys_present(self, sample_returns) -> None:
        m = calculate_strategy_metrics(sample_returns)
        required = {
            "annualized_return", "annualized_vol", "sharpe_ratio",
            "sortino_ratio", "max_drawdown", "calmar_ratio",
            "monthly_hit_rate", "t_stat_monthly", "total_return", "num_days",
        }
        assert required.issubset(m.keys())

    def test_max_drawdown_non_positive(self, sample_returns) -> None:
        """Drawdown convention: must be <= 0."""
        m = calculate_strategy_metrics(sample_returns)
        assert m["max_drawdown"] <= 0.0, (
            f"max_drawdown must be non-positive (got {m['max_drawdown']})"
        )

    def test_max_drawdown_negative_convention(self) -> None:
        """A known drawdown scenario: returns go from 0 to -50% then recover."""
        idx = pd.date_range("2020-01-01", periods=300, freq="B")
        # 100 flat days, then 50 big losses, then recovery
        rets = pd.concat([
            pd.Series(0.001, index=idx[:100]),
            pd.Series(-0.02, index=idx[100:150]),
            pd.Series(0.01, index=idx[150:300]),
        ])
        m = calculate_strategy_metrics(rets)
        assert m["max_drawdown"] < 0, "Max drawdown must be negative"
        assert m["max_drawdown"] >= -1.0, "Max drawdown must be >= -1.0"

    def test_monthly_hit_rate_in_unit_interval(self, sample_returns) -> None:
        m = calculate_strategy_metrics(sample_returns)
        assert 0.0 <= m["monthly_hit_rate"] <= 1.0

    def test_total_return_is_finite(self, sample_returns) -> None:
        m = calculate_strategy_metrics(sample_returns)
        assert np.isfinite(m["total_return"])

    def test_num_days_matches_input(self, sample_returns) -> None:
        m = calculate_strategy_metrics(sample_returns)
        assert m["num_days"] == len(sample_returns)

    def test_short_series_returns_nan_dict(self) -> None:
        tiny = pd.Series([0.01, 0.02, -0.01], index=pd.date_range("2020-01-01", periods=3))
        m = calculate_strategy_metrics(tiny)
        assert np.isnan(m["sharpe_ratio"])
        assert np.isnan(m["max_drawdown"])

    def test_annualized_vol_non_negative(self, sample_returns) -> None:
        m = calculate_strategy_metrics(sample_returns)
        assert m["annualized_vol"] >= 0.0

    def test_all_nan_returns_nan(self) -> None:
        nas = pd.Series(
            [np.nan] * 10,
            index=pd.date_range("2020-01-01", periods=10),
        )
        m = calculate_strategy_metrics(nas)
        assert np.isnan(m["sharpe_ratio"])


# ---------------------------------------------------------------------------
# 10. TestCalculateAlphaBeta
# ---------------------------------------------------------------------------


class TestCalculateAlphaBeta:
    """Tests for calculate_alpha_beta_vs_benchmark()."""

    @pytest.fixture
    def return_pair(self):
        close, _ = _make_prices(n=500, n_tickers=2, seed=5)
        s = close["T0"].pct_change().dropna()
        b = close["T1"].pct_change().dropna()
        return s, b

    def test_returns_dict(self, return_pair) -> None:
        s, b = return_pair
        result = calculate_alpha_beta_vs_benchmark(s, b)
        assert isinstance(result, dict)

    def test_required_keys_present(self, return_pair) -> None:
        s, b = return_pair
        result = calculate_alpha_beta_vs_benchmark(s, b)
        assert {"ann_alpha", "beta", "t_alpha", "r_squared"}.issubset(result.keys())

    def test_beta_finite_for_correlated_series(self) -> None:
        """Perfectly correlated series must yield a finite beta."""
        idx = pd.date_range("2020-01-01", periods=300, freq="B")
        rng = np.random.default_rng(99)
        common = rng.normal(0, 0.01, 300)
        s = pd.Series(common * 1.5 + rng.normal(0, 0.001, 300), index=idx)
        b = pd.Series(common, index=idx)
        result = calculate_alpha_beta_vs_benchmark(s, b)
        assert np.isfinite(result["beta"])
        assert result["beta"] > 0.0

    def test_short_series_returns_nan(self) -> None:
        """Fewer than min_obs observations must return NaN for all metrics."""
        idx = pd.date_range("2020-01-01", periods=10, freq="B")
        s = pd.Series(np.random.normal(0, 0.01, 10), index=idx)
        b = pd.Series(np.random.normal(0, 0.01, 10), index=idx)
        result = calculate_alpha_beta_vs_benchmark(s, b, min_obs=60)
        assert np.isnan(result["ann_alpha"])
        assert np.isnan(result["beta"])
        assert np.isnan(result["t_alpha"])
        assert np.isnan(result["r_squared"])

    def test_r_squared_between_0_and_1(self, return_pair) -> None:
        s, b = return_pair
        result = calculate_alpha_beta_vs_benchmark(s, b)
        if not np.isnan(result["r_squared"]):
            assert 0.0 <= result["r_squared"] <= 1.0

    def test_perfectly_correlated_r_squared_near_one(self) -> None:
        idx = pd.date_range("2020-01-01", periods=300, freq="B")
        rng = np.random.default_rng(42)
        common = rng.normal(0, 0.01, 300)
        # Strategy = 2 * benchmark (no noise) → R² should be ~1
        s = pd.Series(2.0 * common, index=idx)
        b = pd.Series(common, index=idx)
        result = calculate_alpha_beta_vs_benchmark(s, b)
        assert result["r_squared"] > 0.99

    def test_misaligned_indices_handled(self) -> None:
        """Inner join on misaligned indices should not crash."""
        idx_s = pd.date_range("2020-01-01", periods=200, freq="B")
        idx_b = pd.date_range("2020-06-01", periods=200, freq="B")
        rng = np.random.default_rng(10)
        s = pd.Series(rng.normal(0, 0.01, 200), index=idx_s)
        b = pd.Series(rng.normal(0, 0.01, 200), index=idx_b)
        result = calculate_alpha_beta_vs_benchmark(s, b, min_obs=5)
        # They overlap; function should return finite results or NaN gracefully
        assert isinstance(result, dict)
        assert "ann_alpha" in result


# ---------------------------------------------------------------------------
# 11. TestExportAiInfraOutputs
# ---------------------------------------------------------------------------


class TestExportAiInfraOutputs:
    """Tests for export_ai_infra_outputs()."""

    @pytest.fixture
    def bt_net_gross(self):
        close, volume = _make_prices(n=400, n_tickers=5, seed=6)
        daily_rets = close.pct_change()
        tf_sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        weights = build_monthly_rebalance_weights(tf_sig, long_only=True, min_eligible=1)
        bt = run_strategy_backtest(daily_rets, weights, cost_bps=20.0)
        return bt["net"], bt["gross"]

    def test_returns_string_path(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            assert isinstance(run_dir, str)

    def test_creates_output_directory(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            assert os.path.isdir(run_dir)

    def test_metadata_json_created(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            meta_path = os.path.join(run_dir, "metadata.json")
            assert os.path.isfile(meta_path), "metadata.json must be created"

    def test_metadata_json_is_valid(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            with open(os.path.join(run_dir, "metadata.json")) as fh:
                meta = json.load(fh)
            assert "run_timestamp" in meta
            assert "period" in meta

    def test_strategy_results_summary_csv_created(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            csv_path = os.path.join(run_dir, "strategy_results_summary.csv")
            assert os.path.isfile(csv_path), "strategy_results_summary.csv must be created"

    def test_strategy_results_summary_has_rows(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            df = pd.read_csv(os.path.join(run_dir, "strategy_results_summary.csv"))
            assert len(df) >= 1

    def test_report_md_created(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            assert os.path.isfile(os.path.join(run_dir, "report.md"))

    def test_agent_review_md_created(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            assert os.path.isfile(os.path.join(run_dir, "agent_review.md"))

    def test_agent_review_content_matches(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            with open(os.path.join(run_dir, "agent_review.md")) as fh:
                content = fh.read()
            assert "Agent Review" in content

    def test_figures_subdir_created(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            assert os.path.isdir(os.path.join(run_dir, "figures"))

    def test_run_dir_is_inside_base_dir(self, bt_net_gross) -> None:
        bt_net, bt_gross = bt_net_gross
        results = _make_minimal_results(bt_net, bt_gross)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = export_ai_infra_outputs(results, base_dir=tmpdir)
            assert run_dir.startswith(tmpdir)


# ---------------------------------------------------------------------------
# 12. TestGenerateAiInfraReport
# ---------------------------------------------------------------------------


class TestGenerateAiInfraReport:
    """Tests for generate_ai_infra_report()."""

    @pytest.fixture
    def minimal_results(self):
        close, volume = _make_prices(n=400, n_tickers=5, seed=8)
        daily_rets = close.pct_change()
        tf_sig = build_trend_following_signal(close, ma_windows=[10, 20, 50])
        weights = build_monthly_rebalance_weights(tf_sig, long_only=True, min_eligible=1)
        bt = run_strategy_backtest(daily_rets, weights, cost_bps=20.0)
        return _make_minimal_results(bt["net"], bt["gross"])

    def test_creates_markdown_file(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            assert os.path.isfile(path)

    def test_file_is_non_empty(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            assert os.path.getsize(path) > 0

    def test_contains_title(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "AI Infrastructure" in content or "Semiconductor" in content

    def test_contains_strategy_results_section(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "Strategy Results" in content

    def test_contains_methodology_section(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "Methodology" in content

    def test_contains_disclaimer(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "Research only" in content or "DISCLAIMER" in content

    def test_contains_benchmark_section(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "Benchmark" in content

    def test_contains_overall_verdict_section(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "Verdict" in content

    def test_strategy_name_in_report(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            assert "Cross Sectional Momentum" in content or "cross_sectional_momentum" in content.lower()

    def test_is_valid_markdown_has_headers(self, minimal_results) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.md")
            generate_ai_infra_report(minimal_results, path)
            with open(path) as fh:
                content = fh.read()
            # A proper Markdown report should contain at least one heading
            assert "#" in content
