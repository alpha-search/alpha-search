"""Tests for signal generation primitives."""

import numpy as np
import pandas as pd
import pytest

from alpha_search.signals import (
    conjunction,
    ensemble,
    ma_crossover,
    momentum,
    voting,
    z_score_mean_reversion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trend_series(periods: int = 60, trend: float = 0.5, noise: float = 0.1) -> pd.Series:
    """Return an upward-trending price series."""
    rng = np.random.default_rng(42)
    returns = np.full(periods, trend / periods) + rng.normal(0, noise, periods)
    prices = 100 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2023-01-01", periods=periods, freq="D")
    return pd.Series(prices, index=idx, name="close")


def _make_flat_series(periods: int = 60) -> pd.Series:
    """Return a flat (mean-reverting) price series centred at 100."""
    rng = np.random.default_rng(7)
    returns = rng.normal(0, 0.008, periods)
    prices = 100 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2023-01-01", periods=periods, freq="D")
    return pd.Series(prices, index=idx, name="close")


# ---------------------------------------------------------------------------
# Momentum signal
# ---------------------------------------------------------------------------


class TestMomentumSignal:
    """Rate-of-change (momentum) signal."""

    def test_momentum_signal(self) -> None:
        """A strongly trending series yields a positive momentum reading."""
        prices = _make_trend_series(periods=60, trend=5.0)
        sig = momentum(prices, window=20)

        # The last value should be positive because prices are trending up
        assert sig.iloc[-1] > 0.5  # sigmoid squashed to [0,1]
        # NaN for the first *window* observations
        assert sig.iloc[:20].isna().all()


# ---------------------------------------------------------------------------
# Moving-average crossover
# ---------------------------------------------------------------------------


class TestMACrossover:
    """Golden-cross / death-cross signal."""

    def test_ma_crossover_golden_cross(self) -> None:
        """When the short MA crosses above the long MA, signal == 1."""
        prices = pd.Series(
            [100] * 20 + list(range(100, 130)),
            index=pd.date_range("2023-01-01", periods=50, freq="D"),
            name="close",
        )
        sig = ma_crossover(prices, short=10, long=20)

        # In the ramp-up region the short MA should be above the long MA
        assert sig.iloc[-1] == 1.0

    def test_ma_crossover_death_cross(self) -> None:
        """When the short MA crosses below the long MA, signal == 0."""
        prices = pd.Series(
            [130] * 20 + list(range(130, 100, -1)),
            index=pd.date_range("2023-01-01", periods=50, freq="D"),
            name="close",
        )
        sig = ma_crossover(prices, short=10, long=20)

        # ma_crossover returns 0.0/1.0, not -1/1
        assert sig.iloc[-1] == 0.0

    def test_ma_crossover_short_long_validation(self) -> None:
        """short >= long raises ValueError."""
        prices = pd.Series([100, 101, 102], index=pd.date_range("2023-01-01", periods=3, freq="D"))
        with pytest.raises(ValueError):
            ma_crossover(prices, short=20, long=10)


# ---------------------------------------------------------------------------
# Z-score mean-reversion
# ---------------------------------------------------------------------------


class TestZScoreMeanReversion:
    """Z-score threshold-crossing signal."""

    def test_z_score_mean_reversion(self) -> None:
        """Returns far above the mean return a negative (short) signal."""
        # z_score_mean_reversion takes RETURNS, not prices
        returns = pd.Series(
            np.random.default_rng(42).normal(0, 0.01, 60),
            index=pd.date_range("2023-01-01", periods=60, freq="D"),
        )
        # Inject a large positive spike
        returns.iloc[-1] = returns.mean() + 3 * returns.std()

        sig = z_score_mean_reversion(returns, window=20, threshold=2.0)

        # The spike should trigger a short signal (negative, since -z/threshold)
        assert sig.iloc[-1] < 0


# ---------------------------------------------------------------------------
# Ensemble signals
# ---------------------------------------------------------------------------


class TestEnsembleSignals:
    """Weighted combination of multiple signals."""

    def test_ensemble_signals(self) -> None:
        """ensemble() returns a weighted average of aligned signals."""
        idx = pd.date_range("2023-01-01", periods=10, freq="D")
        sig_a = pd.Series([1.0] * 10, index=idx)
        sig_b = pd.Series([-1.0] * 10, index=idx)

        combined = ensemble([sig_a, sig_b], weights=[0.6, 0.4])

        expected = 0.6 * 1.0 + 0.4 * (-1.0)
        assert np.allclose(combined, expected)

    def test_ensemble_equal_weights(self) -> None:
        """Without explicit weights, ensemble uses equal weighting."""
        idx = pd.date_range("2023-01-01", periods=5, freq="D")
        sig_a = pd.Series([1.0] * 5, index=idx)
        sig_b = pd.Series([0.0] * 5, index=idx)

        combined = ensemble([sig_a, sig_b])
        expected = 0.5 * 1.0 + 0.5 * 0.0
        assert np.allclose(combined, expected)


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------


class TestVoting:
    """Majority-vote combination of signals."""

    def test_voting_threshold(self) -> None:
        """voting returns 1.0 when at least threshold signals are > 0.5."""
        idx = pd.date_range("2023-01-01", periods=3, freq="D")
        s1 = pd.Series([1.0, 1.0, 0.0], index=idx)
        s2 = pd.Series([1.0, 0.0, 0.0], index=idx)
        s3 = pd.Series([1.0, 0.0, 0.0], index=idx)

        result = voting([s1, s2, s3], threshold=2)
        assert result.iloc[0] == 1.0  # all 3 positive
        assert result.iloc[1] == 0.0  # only 1 positive
        assert result.iloc[2] == 0.0  # none positive


# ---------------------------------------------------------------------------
# Conjunction
# ---------------------------------------------------------------------------


class TestConjunction:
    """Logical AND of all signals."""

    def test_conjunction(self) -> None:
        """conjunction returns 1.0 only when every signal is > 0.5."""
        idx = pd.date_range("2023-01-01", periods=3, freq="D")
        s1 = pd.Series([1.0, 1.0, 0.0], index=idx)
        s2 = pd.Series([1.0, 0.0, 1.0], index=idx)

        result = conjunction([s1, s2])
        assert result.iloc[0] == 1.0  # both positive
        assert result.iloc[1] == 0.0  # s2 is 0
        assert result.iloc[2] == 0.0  # s1 is 0


# ---------------------------------------------------------------------------
# Signal composition via pandas operators
# ---------------------------------------------------------------------------


class TestSignalComposition:
    """AND / OR composition of binary signals using pandas operators."""

    def test_signal_composition_and(self) -> None:
        """AND requires both signals to be positive (> 0)."""
        idx = pd.date_range("2023-01-01", periods=5, freq="D")
        a = pd.Series([1.0, 1.0, -1.0, -1.0, 1.0], index=idx)
        b = pd.Series([1.0, -1.0, 1.0, -1.0, 1.0], index=idx)

        result = (a > 0) & (b > 0)
        expected = pd.Series([True, False, False, False, True], index=idx)
        pd.testing.assert_series_equal(result, expected)

    def test_signal_composition_or(self) -> None:
        """OR requires at least one signal to be positive."""
        idx = pd.date_range("2023-01-01", periods=5, freq="D")
        a = pd.Series([1.0, 1.0, -1.0, -1.0, 1.0], index=idx)
        b = pd.Series([1.0, -1.0, 1.0, -1.0, -1.0], index=idx)

        result = (a > 0) | (b > 0)
        expected = pd.Series([True, True, True, False, True], index=idx)
        pd.testing.assert_series_equal(result, expected)
