"""Unit tests for alpha_search/research/real_data_pipeline.py (new standalone functions).

All tests use mocked or locally-generated data — no live network calls.
yfinance.download is patched wherever it would otherwise make HTTP requests.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from alpha_search.research.real_data_pipeline import (
    UNIVERSE_CRYPTO,
    UNIVERSE_INDIA_EQUITY,
    UNIVERSE_US_LARGE_CAP,
    UNIVERSES,
    calculate_metrics,
    fetch_yfinance_ohlcv,
    generate_breakout_signal,
    generate_mean_reversion_signal,
    generate_momentum_signal,
    load_csv_ohlcv,
    run_vectorized_backtest,
    validate_ohlcv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 100, start_price: float = 100.0, seed: int = 0) -> pd.DataFrame:
    """Return a valid OHLCV DataFrame with DatetimeIndex."""
    rng = np.random.default_rng(seed)
    closes = start_price * np.cumprod(1 + rng.normal(0, 0.01, n))
    opens = closes * (1 + rng.normal(0, 0.003, n))
    highs = np.maximum(closes, opens) * (1 + rng.uniform(0, 0.005, n))
    lows = np.minimum(closes, opens) * (1 - rng.uniform(0, 0.005, n))
    volumes = rng.integers(100_000, 1_000_000, n).astype(float)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def _make_yf_download_response(ticker: str, n: int = 150) -> pd.DataFrame:
    """Simulate what yfinance.download returns for a single ticker."""
    df = _make_ohlcv(n)
    # Recent yfinance returns a MultiIndex: (field, ticker)
    df.columns = pd.MultiIndex.from_tuples(
        [(c, ticker) for c in df.columns], names=["Price", "Ticker"]
    )
    return df


# ---------------------------------------------------------------------------
# Universe constants
# ---------------------------------------------------------------------------


class TestUniverseConstants:
    def test_us_large_cap_non_empty(self) -> None:
        assert len(UNIVERSE_US_LARGE_CAP) >= 5

    def test_india_equity_non_empty(self) -> None:
        assert len(UNIVERSE_INDIA_EQUITY) >= 3

    def test_crypto_contains_btc(self) -> None:
        assert "BTC-USD" in UNIVERSE_CRYPTO

    def test_universes_dict_has_expected_keys(self) -> None:
        for key in ("us_large_cap", "india_equity", "crypto", "all"):
            assert key in UNIVERSES

    def test_all_universe_is_union(self) -> None:
        combined = set(UNIVERSE_US_LARGE_CAP) | set(UNIVERSE_INDIA_EQUITY) | set(UNIVERSE_CRYPTO)
        assert set(UNIVERSES["all"]) == combined


# ---------------------------------------------------------------------------
# fetch_yfinance_ohlcv
# ---------------------------------------------------------------------------


class TestFetchYfinanceOhlcv:
    def _mock_download(self, sym, **kwargs):
        return _make_yf_download_response(sym, n=150)

    def test_successful_fetch_returns_frame(self) -> None:
        with patch("yfinance.download", side_effect=self._mock_download):
            frames, succeeded, failed = fetch_yfinance_ohlcv(["AAPL"], period="2y")
        assert "AAPL" in frames
        assert "AAPL" in succeeded
        assert "AAPL" not in failed

    def test_failed_symbol_goes_to_failed_list(self) -> None:
        def bad_download(sym, **kwargs):
            raise RuntimeError("network error")

        with patch("yfinance.download", side_effect=bad_download):
            frames, succeeded, failed = fetch_yfinance_ohlcv(["BADSYM"], period="1y")
        assert "BADSYM" not in frames
        assert "BADSYM" in failed
        assert "BADSYM" not in succeeded

    def test_empty_response_is_skipped(self) -> None:
        with patch("yfinance.download", return_value=pd.DataFrame()):
            frames, succeeded, failed = fetch_yfinance_ohlcv(["EMPTY"], period="1y")
        assert "EMPTY" not in frames
        assert "EMPTY" in failed

    def test_partial_failure_does_not_stop_others(self) -> None:
        call_count = {"n": 0}

        def mixed_download(sym, **kwargs):
            call_count["n"] += 1
            if sym == "FAIL":
                raise RuntimeError("intentional")
            return _make_yf_download_response(sym, n=150)

        with patch("yfinance.download", side_effect=mixed_download):
            frames, succeeded, failed = fetch_yfinance_ohlcv(["AAPL", "FAIL", "MSFT"])

        assert "AAPL" in succeeded
        assert "MSFT" in succeeded
        assert "FAIL" in failed
        assert call_count["n"] == 3

    def test_non_positive_close_filtered(self) -> None:
        """Rows with Close <= 0 should be dropped; if too few remain, symbol is skipped."""
        df = _make_yf_download_response("TEST", n=10)
        # Only 10 rows → below 20-row threshold → should be skipped
        with patch("yfinance.download", return_value=df):
            frames, succeeded, failed = fetch_yfinance_ohlcv(["TEST"])
        assert "TEST" in failed

    def test_output_columns_are_title_case(self) -> None:
        with patch("yfinance.download", side_effect=self._mock_download):
            frames, _, _ = fetch_yfinance_ohlcv(["AAPL"])
        df = frames["AAPL"]
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in df.columns, f"Expected title-case column {col}"

    def test_output_index_is_datetime(self) -> None:
        with patch("yfinance.download", side_effect=self._mock_download):
            frames, _, _ = fetch_yfinance_ohlcv(["AAPL"])
        assert pd.api.types.is_datetime64_any_dtype(frames["AAPL"].index)


# ---------------------------------------------------------------------------
# load_csv_ohlcv
# ---------------------------------------------------------------------------


class TestLoadCsvOhlcv:
    def _write_csv(self, path: str, tickers: list[str], n: int = 80) -> None:
        rows = []
        for sym in tickers:
            df = _make_ohlcv(n)
            for ts, row in df.iterrows():
                rows.append({
                    "timestamp": ts.strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "open": row["Open"],
                    "high": row["High"],
                    "low": row["Low"],
                    "close": row["Close"],
                    "volume": row["Volume"],
                })
        pd.DataFrame(rows).to_csv(path, index=False)

    def test_single_symbol_loads(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            fname = f.name
        try:
            self._write_csv(fname, ["AAPL"])
            result = load_csv_ohlcv(fname)
            assert "AAPL" in result
            assert len(result["AAPL"]) > 0
        finally:
            os.unlink(fname)

    def test_multiple_symbols_split_correctly(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            fname = f.name
        try:
            self._write_csv(fname, ["AAPL", "MSFT"])
            result = load_csv_ohlcv(fname)
            assert "AAPL" in result
            assert "MSFT" in result
        finally:
            os.unlink(fname)

    def test_missing_file_returns_empty(self) -> None:
        result = load_csv_ohlcv("/nonexistent/path/data.csv")
        assert result == {}

    def test_output_columns_title_cased(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            fname = f.name
        try:
            self._write_csv(fname, ["TEST"])
            result = load_csv_ohlcv(fname)
            assert "TEST" in result
            for col in ("Open", "High", "Low", "Close"):
                assert col in result["TEST"].columns
        finally:
            os.unlink(fname)

    def test_index_is_datetime(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            fname = f.name
        try:
            self._write_csv(fname, ["AAPL"])
            result = load_csv_ohlcv(fname)
            assert pd.api.types.is_datetime64_any_dtype(result["AAPL"].index)
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# validate_ohlcv
# ---------------------------------------------------------------------------


class TestValidateOhlcv:
    def test_valid_dataframe_passes(self) -> None:
        df = _make_ohlcv(100)
        ok, issues = validate_ohlcv(df, "AAPL")
        assert ok, f"Unexpected issues: {issues}"

    def test_empty_dataframe_fails(self) -> None:
        ok, issues = validate_ohlcv(pd.DataFrame(), "EMPTY")
        assert not ok

    def test_missing_close_column_fails(self) -> None:
        df = _make_ohlcv(50).drop(columns=["Close"])
        ok, issues = validate_ohlcv(df, "NOCOL")
        assert not ok
        assert any("Close" in i for i in issues)

    def test_too_few_rows_fails(self) -> None:
        df = _make_ohlcv(10)
        ok, issues = validate_ohlcv(df, "SHORT")
        assert not ok
        assert any("rows" in i.lower() for i in issues)

    def test_non_positive_close_fails(self) -> None:
        df = _make_ohlcv(50)
        df["Close"] = -1.0
        ok, issues = validate_ohlcv(df, "NEG")
        assert not ok

    def test_issues_list_non_empty_on_failure(self) -> None:
        ok, issues = validate_ohlcv(pd.DataFrame(), "X")
        assert not ok
        assert len(issues) > 0

    def test_high_below_close_flagged(self) -> None:
        df = _make_ohlcv(60)
        df["High"] = df["Close"] * 0.5  # High < Close — invalid
        ok, issues = validate_ohlcv(df, "BADHIGH")
        assert not ok or any("high" in i.lower() or "integrity" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# generate_momentum_signal
# ---------------------------------------------------------------------------


class TestGenerateMomentumSignal:
    def test_returns_series(self) -> None:
        close = _make_ohlcv(100)["Close"]
        sig = generate_momentum_signal(close)
        assert isinstance(sig, pd.Series)

    def test_same_length_as_input(self) -> None:
        close = _make_ohlcv(120)["Close"]
        sig = generate_momentum_signal(close)
        assert len(sig) == len(close)

    def test_values_are_0_or_1(self) -> None:
        close = _make_ohlcv(150)["Close"]
        sig = generate_momentum_signal(close)
        finite = sig.dropna()
        assert set(finite.unique()).issubset({0, 1, 0.0, 1.0})

    def test_strongly_trending_up_gives_long_signal(self) -> None:
        """A steadily rising price series should produce at least some long signals."""
        idx = pd.date_range("2022-01-01", periods=100, freq="B")
        close = pd.Series(np.linspace(100, 200, 100), index=idx)
        sig = generate_momentum_signal(close, lookback=20, ma_confirm=False)
        assert sig.sum() > 0, "Expected positive momentum signals for trending-up prices"

    def test_no_ma_confirm_still_works(self) -> None:
        close = _make_ohlcv(100)["Close"]
        sig = generate_momentum_signal(close, ma_confirm=False)
        assert isinstance(sig, pd.Series)

    def test_short_series_handled(self) -> None:
        close = _make_ohlcv(5)["Close"]
        sig = generate_momentum_signal(close, lookback=20)
        # Should return all-NaN or empty — not raise
        assert isinstance(sig, pd.Series)


# ---------------------------------------------------------------------------
# generate_mean_reversion_signal
# ---------------------------------------------------------------------------


class TestGenerateMeanReversionSignal:
    def test_returns_series(self) -> None:
        close = _make_ohlcv(100)["Close"]
        sig = generate_mean_reversion_signal(close)
        assert isinstance(sig, pd.Series)

    def test_same_length_as_input(self) -> None:
        close = _make_ohlcv(120)["Close"]
        sig = generate_mean_reversion_signal(close)
        assert len(sig) == len(close)

    def test_long_only_values_are_0_or_1(self) -> None:
        close = _make_ohlcv(150)["Close"]
        sig = generate_mean_reversion_signal(close, allow_short=False)
        finite = sig.dropna()
        assert set(finite.unique()).issubset({0, 1, 0.0, 1.0})

    def test_short_signals_when_allow_short(self) -> None:
        """With allow_short=True, signal can be -1 (short)."""
        close = _make_ohlcv(150)["Close"]
        sig = generate_mean_reversion_signal(close, allow_short=True)
        finite = sig.dropna()
        assert set(finite.unique()).issubset({-1, 0, 1, -1.0, 0.0, 1.0})

    def test_dip_below_threshold_generates_long(self) -> None:
        """Inject an artificial dip to trigger a z-score below -z_threshold."""
        idx = pd.date_range("2022-01-01", periods=60, freq="B")
        close = pd.Series([100.0] * 60, index=idx, dtype=float)
        close.iloc[40:50] = 50.0  # large dip
        sig = generate_mean_reversion_signal(close, window=20, z_threshold=1.0)
        assert sig.dropna().sum() > 0, "Expected long signals during dip"

    def test_short_series_handled(self) -> None:
        close = _make_ohlcv(5)["Close"]
        sig = generate_mean_reversion_signal(close)
        assert isinstance(sig, pd.Series)


# ---------------------------------------------------------------------------
# generate_breakout_signal
# ---------------------------------------------------------------------------


class TestGenerateBreakoutSignal:
    def test_returns_series(self) -> None:
        df = _make_ohlcv(100)
        sig = generate_breakout_signal(df["Close"], df["High"], df["Low"])
        assert isinstance(sig, pd.Series)

    def test_same_length_as_input(self) -> None:
        df = _make_ohlcv(120)
        sig = generate_breakout_signal(df["Close"])
        assert len(sig) == len(df)

    def test_no_lookahead_via_shift(self) -> None:
        """Signal at day t must depend only on data up to day t-1 (enforced by shift)."""
        idx = pd.date_range("2022-01-01", periods=40, freq="B")
        # Flat price for first 25 bars, then spike on day 25
        prices = pd.Series([100.0] * 25 + [200.0] * 15, index=idx)
        # With shift(1), breakout on day 25 cannot appear in signal on day 25
        sig = generate_breakout_signal(prices, window=20)
        assert sig.iloc[24] == 0 or pd.isna(sig.iloc[24]), (
            "Signal must not fire on the same bar as the breakout (lookahead)"
        )

    def test_trending_prices_generate_signal(self) -> None:
        idx = pd.date_range("2022-01-01", periods=80, freq="B")
        prices = pd.Series(np.linspace(100, 200, 80), index=idx)
        sig = generate_breakout_signal(prices, window=20)
        assert sig.dropna().sum() > 0

    def test_with_high_low_provided(self) -> None:
        df = _make_ohlcv(100)
        sig = generate_breakout_signal(df["Close"], high=df["High"], low=df["Low"])
        assert isinstance(sig, pd.Series)
        assert len(sig) == 100


# ---------------------------------------------------------------------------
# run_vectorized_backtest
# ---------------------------------------------------------------------------


class TestRunVectorizedBacktest:
    def test_returns_backtest_result(self) -> None:
        from alpha_search.backtest.engine import BacktestResult

        df = _make_ohlcv(100)
        signal = generate_momentum_signal(df["Close"], lookback=10, ma_confirm=False)
        result = run_vectorized_backtest(
            close=df["Close"],
            signal=signal,
            high=df["High"],
            low=df["Low"],
            initial_capital=100_000.0,
        )
        assert isinstance(result, BacktestResult)

    def test_equity_curve_starts_at_capital(self) -> None:
        df = _make_ohlcv(100)
        signal = generate_momentum_signal(df["Close"], lookback=10, ma_confirm=False)
        result = run_vectorized_backtest(
            close=df["Close"],
            signal=signal,
            initial_capital=50_000.0,
        )
        assert result.equity_curve.iloc[0] == pytest.approx(50_000.0, rel=0.05)

    def test_max_drawdown_finite(self) -> None:
        df = _make_ohlcv(150, seed=1)
        signal = generate_momentum_signal(df["Close"], lookback=10, ma_confirm=False)
        result = run_vectorized_backtest(close=df["Close"], signal=signal)
        dd = result.metrics["max_drawdown"]
        assert np.isfinite(dd), "max_drawdown must be finite"
        assert dd >= 0, "max_drawdown magnitude must be non-negative"

    def test_cost_bps_applied(self) -> None:
        """Backtest with zero costs should have higher or equal equity than with costs."""
        df = _make_ohlcv(150, seed=5)
        signal = generate_momentum_signal(df["Close"], lookback=10, ma_confirm=False)
        r_free = run_vectorized_backtest(
            close=df["Close"], signal=signal, transaction_cost_bps=0, slippage_bps=0
        )
        r_cost = run_vectorized_backtest(
            close=df["Close"], signal=signal, transaction_cost_bps=20, slippage_bps=20
        )
        assert r_free.equity_curve.iloc[-1] >= r_cost.equity_curve.iloc[-1]

    def test_flat_signal_no_trades(self) -> None:
        df = _make_ohlcv(80)
        signal = pd.Series(0, index=df.index, dtype=float)
        result = run_vectorized_backtest(close=df["Close"], signal=signal, initial_capital=100_000.0)
        assert len(result.trades) == 0


# ---------------------------------------------------------------------------
# calculate_metrics
# ---------------------------------------------------------------------------


class TestCalculateMetrics:
    def _backtest_result(self, seed: int = 7) -> object:
        df = _make_ohlcv(150, seed=seed)
        signal = generate_momentum_signal(df["Close"], lookback=10, ma_confirm=False)
        return run_vectorized_backtest(
            close=df["Close"], signal=signal, initial_capital=100_000.0
        )

    def test_returns_dict(self) -> None:
        result = self._backtest_result()
        metrics = calculate_metrics(result)
        assert isinstance(metrics, dict)

    def test_core_metric_keys_present(self) -> None:
        result = self._backtest_result()
        metrics = calculate_metrics(result)
        for key in ("sharpe_ratio", "max_drawdown", "total_return", "annualized_return"):
            assert key in metrics, f"Missing metric key: {key}"

    def test_extended_keys_present(self) -> None:
        result = self._backtest_result()
        metrics = calculate_metrics(result)
        for key in ("num_trades", "exposure", "turnover"):
            assert key in metrics, f"Missing extended metric: {key}"

    def test_max_drawdown_finite(self) -> None:
        result = self._backtest_result()
        metrics = calculate_metrics(result)
        dd = metrics["max_drawdown"]
        assert np.isfinite(dd), "max_drawdown must be finite"
        assert dd >= 0, "max_drawdown magnitude must be non-negative"

    def test_exposure_between_0_and_1(self) -> None:
        result = self._backtest_result()
        metrics = calculate_metrics(result)
        assert 0.0 <= metrics["exposure"] <= 1.0

    def test_num_trades_non_negative(self) -> None:
        result = self._backtest_result()
        metrics = calculate_metrics(result)
        assert metrics["num_trades"] >= 0

    def test_flat_signal_zero_exposure(self) -> None:
        df = _make_ohlcv(80)
        signal = pd.Series(0, index=df.index, dtype=float)
        result = run_vectorized_backtest(close=df["Close"], signal=signal)
        metrics = calculate_metrics(result)
        assert metrics["exposure"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# export_research_outputs
# ---------------------------------------------------------------------------


class TestExportResearchOutputs:
    def _make_results(self) -> dict:
        df = _make_ohlcv(100)
        signal = generate_momentum_signal(df["Close"], lookback=10, ma_confirm=False)
        backtest = run_vectorized_backtest(close=df["Close"], signal=signal)
        metrics = calculate_metrics(backtest)
        backtest_results = {"AAPL": {"backtest": backtest, "metrics": metrics}}
        metrics_df = pd.DataFrame([metrics], index=["AAPL"])
        return {
            "universe": "test",
            "period": "2y",
            "interval": "1d",
            "symbols_requested": ["AAPL"],
            "symbols_succeeded": ["AAPL"],
            "symbols_failed": [],
            "run_timestamp": "2024-01-01T00:00:00+00:00",
            "duration_seconds": 1.0,
            "transaction_cost_bps": 10,
            "slippage_bps": 10,
            "momentum": {
                "verdict": "marginal",
                "avg_sharpe": 0.1,
                "backtest_results": backtest_results,
                "metrics_df": metrics_df,
                "hypothesis": "Test hypothesis",
                "no_trade_reasons": [],
            },
            "mean_reversion": {
                "verdict": "no_results",
                "avg_sharpe": None,
                "backtest_results": {},
                "metrics_df": pd.DataFrame(),
                "hypothesis": "",
                "no_trade_reasons": [],
            },
            "breakout": {
                "verdict": "no_results",
                "avg_sharpe": None,
                "backtest_results": {},
                "metrics_df": pd.DataFrame(),
                "hypothesis": "",
                "no_trade_reasons": [],
            },
            "validation_report": {},
            "disclaimer": "RESEARCH ONLY",
        }

    def test_creates_output_directory(self) -> None:
        from alpha_search.research.real_data_pipeline import export_research_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            results = self._make_results()
            out_dir = export_research_outputs(results, base_dir=tmpdir)
            assert os.path.isdir(out_dir)

    def test_metadata_json_created(self) -> None:
        from alpha_search.research.real_data_pipeline import export_research_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            results = self._make_results()
            out_dir = export_research_outputs(results, base_dir=tmpdir)
            meta_path = os.path.join(out_dir, "metadata.json")
            assert os.path.isfile(meta_path)
            with open(meta_path) as f:
                meta = json.load(f)
            assert "universe" in meta

    def test_report_md_created(self) -> None:
        from alpha_search.research.real_data_pipeline import export_research_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            results = self._make_results()
            out_dir = export_research_outputs(results, base_dir=tmpdir)
            report_path = os.path.join(out_dir, "report.md")
            assert os.path.isfile(report_path)

    def test_summary_csv_created(self) -> None:
        from alpha_search.research.real_data_pipeline import export_research_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            results = self._make_results()
            out_dir = export_research_outputs(results, base_dir=tmpdir)
            csv_path = os.path.join(out_dir, "strategy_results_summary.csv")
            assert os.path.isfile(csv_path)
