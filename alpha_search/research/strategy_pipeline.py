"""End-to-end strategy research pipelines.

Provides three fully-implemented research pipelines:

* :class:`MomentumPipeline` — trend-following using momentum and MA-crossover signals.
* :class:`MeanReversionPipeline` — contrarian trading using z-score and Bollinger-Band signals.
* :class:`ArbitragePipeline` — statistical arbitrage using correlated pairs and spread trading.

All pipelines use existing Alpha Search modules exclusively:

* ``alpha_search.signals.technical`` for signal generation.
* ``alpha_search.backtest.engine`` + ``alpha_search.backtest.costs`` for backtesting.
* ``alpha_search.backtest.metrics`` for performance measurement.

A convenience function :func:`run_all_pipelines` executes all three pipelines
against synthetic data and returns a combined results dictionary.

Example::

    from alpha_search.research import MomentumPipeline, generate_us_equity_data

    prices = generate_us_equity_data()
    pipeline = MomentumPipeline(prices, tickers=["AAPL", "MSFT", "GOOGL"])
    result = pipeline.run()
    print(result["metrics"])
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.signals.technical import (
    bollinger_band_position,
    ma_crossover,
    momentum,
    z_score_mean_reversion,
)

logger = logging.getLogger(__name__)

# Default cost model used across all pipelines
_DEFAULT_COST_MODEL = CostModel(commission=0.001, slippage=0.001)
_INITIAL_CAPITAL: float = 100_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_ticker_prices(
    prices_df: pd.DataFrame, ticker: str
) -> pd.DataFrame:
    """Extract a single-ticker OHLCV DataFrame from a MultiIndex-column DataFrame.

    Parameters
    ----------
    prices_df:
        DataFrame with MultiIndex columns ``(ticker, field)``.
    ticker:
        Ticker symbol to extract.

    Returns
    -------
    pd.DataFrame
        Single-ticker DataFrame with columns ``Open, High, Low, Close, Volume``.
    """
    if isinstance(prices_df.columns, pd.MultiIndex):
        ticker_df = prices_df.xs(ticker, level="ticker", axis=1).copy()
    else:
        # Fallback: assume single-ticker flat columns
        ticker_df = prices_df.copy()
    # Normalise column names to title case
    ticker_df.columns = [c.title() for c in ticker_df.columns]
    return ticker_df


def _compute_metrics_row(backtest_result: Any) -> Dict[str, float]:
    """Extract key metrics from a BacktestResult into a flat dict.

    Parameters
    ----------
    backtest_result:
        A :class:`BacktestResult` instance.

    Returns
    -------
    dict
        Keys: total_return, sharpe_ratio, max_drawdown, win_rate,
        annualized_return, volatility, num_trades, num_days.
    """
    m = backtest_result.metrics if hasattr(backtest_result, "metrics") else {}
    n_trades = (
        len(backtest_result.trades)
        if hasattr(backtest_result, "trades")
        else 0
    )
    return {
        "total_return": float(m.get("total_return", 0.0)),
        "sharpe_ratio": float(m.get("sharpe_ratio", 0.0)),
        "max_drawdown": float(m.get("max_drawdown", 0.0)),
        "win_rate": float(m.get("win_rate", 0.0)),
        "annualized_return": float(m.get("annualized_return", 0.0)),
        "volatility": float(m.get("volatility", 0.0)),
        "num_trades": int(n_trades),
        "num_days": float(m.get("num_days", 0.0)),
    }


# ---------------------------------------------------------------------------
# Momentum Pipeline
# ---------------------------------------------------------------------------

class MomentumPipeline:
    """End-to-end momentum (trend-following) strategy research pipeline.

    Discovers opportunities by ranking assets on recent price momentum,
    generates signals using the existing ``momentum()`` and
    ``ma_crossover()`` indicators, runs vectorised backtests, and
    compiles performance metrics.

    Parameters
    ----------
    prices:
        OHLCV DataFrame.  May have MultiIndex columns ``(ticker, field)``
        or flat columns for a single ticker.
    tickers:
        List of ticker symbols to analyse.
    capital:
        Initial capital for backtests (default $100,000).

    Attributes
    ----------
    results: dict
        Populated after :meth:`run` completes.
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        tickers: List[str],
        capital: float = _INITIAL_CAPITAL,
    ) -> None:
        self.prices = prices
        self.tickers = tickers
        self.capital = capital
        self.results: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Step 1: Discover                                                   #
    # ------------------------------------------------------------------ #

    def discover_opportunities(self) -> pd.DataFrame:
        """Rank tickers by momentum strength.

        For each ticker computes:

        * ``momentum_score`` – latest value from the momentum signal.
        * ``returns_20d`` – 20-day cumulative return.
        * ``volume_ratio`` – latest volume / 20-day average volume.

        Returns
        -------
        pd.DataFrame
            Sorted by *momentum_score* descending.  Index = ticker.
        """
        rows: List[Dict[str, float]] = []
        for ticker in self.tickers:
            try:
                ticker_df = _extract_ticker_prices(self.prices, ticker)
                if "Close" not in ticker_df.columns or ticker_df["Close"].empty:
                    continue
                close = ticker_df["Close"]

                # Momentum score (latest)
                mom_signal = momentum(close, window=20)
                mom_score = (
                    float(mom_signal.iloc[-1])
                    if not mom_signal.empty and not pd.isna(mom_signal.iloc[-1])
                    else 0.0
                )

                # 20-day return
                ret_20d = float(close.pct_change(20).iloc[-1]) if len(close) > 20 else 0.0

                # Volume ratio
                if "Volume" in ticker_df.columns:
                    vol = ticker_df["Volume"]
                    vol_ratio = (
                        float(vol.iloc[-1] / vol.rolling(20).mean().iloc[-1])
                        if len(vol) > 20 and vol.rolling(20).mean().iloc[-1] > 0
                        else 1.0
                    )
                else:
                    vol_ratio = 1.0

                rows.append(
                    {
                        "ticker": ticker,
                        "momentum_score": mom_score,
                        "returns_20d": ret_20d,
                        "volume_ratio": vol_ratio,
                    }
                )
            except Exception as exc:
                logger.warning("Momentum discovery failed for %s: %s", ticker, exc)

        df = pd.DataFrame(rows).set_index("ticker")
        if not df.empty:
            df = df.sort_values("momentum_score", ascending=False)
        return df

    # ------------------------------------------------------------------ #
    # Step 2: Signal generation                                          #
    # ------------------------------------------------------------------ #

    def generate_signals(self) -> Dict[str, pd.Series]:
        """Generate momentum signals for each ticker.

        Combines ``momentum()`` (softmax-squashed cumulative return) and
        ``ma_crossover()`` (binary 0/1 from MA20 > MA50) into an
        ensemble signal: ``signal = 0.6 * momentum + 0.4 * ma_crossover``.

        Returns
        -------
        dict[str, pd.Series]
            Mapping ticker -> combined signal series.
        """
        signals: Dict[str, pd.Series] = {}
        for ticker in self.tickers:
            try:
                ticker_df = _extract_ticker_prices(self.prices, ticker)
                if "Close" not in ticker_df.columns or len(ticker_df) < 50:
                    continue
                close = ticker_df["Close"]

                mom = momentum(close, window=20)
                ma_cross = ma_crossover(close, short=20, long=50)

                # Ensemble: weight momentum higher for trend strength
                combined = 0.6 * mom + 0.4 * ma_cross
                combined.name = f"{ticker}_momentum_signal"
                signals[ticker] = combined
            except Exception as exc:
                logger.warning("Signal generation failed for %s: %s", ticker, exc)

        logger.info("Generated momentum signals for %d tickers", len(signals))
        return signals

    # ------------------------------------------------------------------ #
    # Step 3: Backtest                                                   #
    # ------------------------------------------------------------------ #

    def backtest(self, signals: Dict[str, pd.Series]) -> Dict[str, Any]:
        """Run vectorised backtests for each ticker's signal.

        Parameters
        ----------
        signals:
            Output from :meth:`generate_signals`.

        Returns
        -------
        dict[str, BacktestResult]
            Mapping ticker -> backtest result.
        """
        engine = BacktestEngine()
        cost_model = _DEFAULT_COST_MODEL
        backtests: Dict[str, Any] = {}

        for ticker, signal in signals.items():
            try:
                ticker_df = _extract_ticker_prices(self.prices, ticker)
                result = engine.run(
                    prices=ticker_df,
                    signal=signal,
                    initial_capital=self.capital,
                    cost_model=cost_model,
                )
                backtests[ticker] = result
            except Exception as exc:
                logger.warning("Backtest failed for %s: %s", ticker, exc)

        logger.info("Completed %d momentum backtests", len(backtests))
        return backtests

    # ------------------------------------------------------------------ #
    # Step 4: Metrics                                                    #
    # ------------------------------------------------------------------ #

    def compute_metrics(self, backtests: Dict[str, Any]) -> pd.DataFrame:
        """Compile performance metrics from backtest results.

        Parameters
        ----------
        backtests:
            Output from :meth:`backtest`.

        Returns
        -------
        pd.DataFrame
            One row per ticker.  Columns include total_return, sharpe_ratio,
            max_drawdown, win_rate, annualized_return, volatility,
            num_trades, num_days.
        """
        rows: Dict[str, Dict[str, float]] = {}
        for ticker, bt in backtests.items():
            rows[ticker] = _compute_metrics_row(bt)
        df = pd.DataFrame.from_dict(rows, orient="index")
        if not df.empty:
            df = df.sort_values("sharpe_ratio", ascending=False)
        return df

    # ------------------------------------------------------------------ #
    # Orchestration                                                      #
    # ------------------------------------------------------------------ #

    def run(self) -> Dict[str, Any]:
        """Execute the complete momentum research pipeline.

        Returns
        -------
        dict
            Keys: ``opportunities``, ``signals``, ``backtests``,
            ``metrics``, ``hypothesis``, ``risks``.
        """
        logger.info("Starting MomentumPipeline for %d tickers", len(self.tickers))
        opportunities = self.discover_opportunities()
        signals = self.generate_signals()
        backtests = self.backtest(signals)
        metrics = self.compute_metrics(backtests)

        self.results = {
            "opportunities": opportunities,
            "signals": signals,
            "backtests": backtests,
            "metrics": metrics,
            "hypothesis": (
                "Stocks with strong recent price momentum will continue "
                "trending in the same direction over the next 1–4 weeks."
            ),
            "risks": [
                "Momentum crashes during sharp market reversals (volatility spikes).",
                "Prolonged drawdowns in choppy / range-bound markets.",
                "Concentration risk if only a few names show strong signals.",
                "Transaction costs erode returns for high-turnover signals.",
            ],
        }
        logger.info("MomentumPipeline complete — %d backtests run", len(backtests))
        return self.results


# ---------------------------------------------------------------------------
# Mean Reversion Pipeline
# ---------------------------------------------------------------------------

class MeanReversionPipeline:
    """End-to-end mean-reversion strategy research pipeline.

    Discovers opportunities by ranking assets on z-score deviation from
    their rolling mean, generates signals using
    ``z_score_mean_reversion()`` and ``bollinger_band_position()``,
    runs vectorised backtests, and compiles performance metrics.

    Parameters
    ----------
    prices:
        OHLCV DataFrame with MultiIndex columns ``(ticker, field)``
        or flat columns.
    tickers:
        List of ticker symbols to analyse.
    capital:
        Initial capital for backtests (default $100,000).
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        tickers: List[str],
        capital: float = _INITIAL_CAPITAL,
    ) -> None:
        self.prices = prices
        self.tickers = tickers
        self.capital = capital
        self.results: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Step 1: Discover                                                   #
    # ------------------------------------------------------------------ #

    def discover_opportunities(self) -> pd.DataFrame:
        """Rank tickers by mean-reversion potential.

        Computes the absolute z-score of the latest return relative to
        the 20-day rolling mean / std.  Higher absolute z-scores imply
        greater mean-reversion potential.

        Returns
        -------
        pd.DataFrame
            Sorted by ``abs_zscore`` descending.  Index = ticker.
        """
        rows: List[Dict[str, float]] = []
        for ticker in self.tickers:
            try:
                ticker_df = _extract_ticker_prices(self.prices, ticker)
                if "Close" not in ticker_df.columns or len(ticker_df) < 30:
                    continue
                close = ticker_df["Close"]
                returns = close.pct_change().dropna()

                if len(returns) < 20:
                    continue

                rolling_mean = returns.rolling(20).mean()
                rolling_std = returns.rolling(20).std().replace(0, np.nan)
                z = (returns - rolling_mean) / rolling_std
                latest_z = float(z.iloc[-1]) if not pd.isna(z.iloc[-1]) else 0.0

                # BB position: 0 = lower band (oversold), 1 = upper (overbought)
                bb_pos = bollinger_band_position(close, window=20, num_std=2.0)
                latest_bb = (
                    float(bb_pos.iloc[-1])
                    if not bb_pos.empty and not pd.isna(bb_pos.iloc[-1])
                    else 0.5
                )

                rows.append(
                    {
                        "ticker": ticker,
                        "z_score": latest_z,
                        "zscore": latest_z,  # alias for backward compatibility
                        "abs_zscore": abs(latest_z),
                        "bb_position": latest_bb,
                        "deviation_pct": float(
                            (close.iloc[-1] - close.rolling(20).mean().iloc[-1])
                            / close.rolling(20).mean().iloc[-1]
                        )
                        if close.rolling(20).mean().iloc[-1] > 0
                        else 0.0,
                    }
                )
            except Exception as exc:
                logger.warning("Mean-reversion discovery failed for %s: %s", ticker, exc)

        df = pd.DataFrame(rows).set_index("ticker")
        if not df.empty:
            df = df.sort_values("abs_zscore", ascending=False)
        return df

    # ------------------------------------------------------------------ #
    # Step 2: Signal generation                                          #
    # ------------------------------------------------------------------ #

    def generate_signals(self) -> Dict[str, pd.Series]:
        """Generate mean-reversion signals for each ticker.

        Combines ``z_score_mean_reversion()`` (contrarian signal in
        ``[-1, 1]``) and ``bollinger_band_position()`` (0 = buy, 1 = sell)
        into an ensemble:

        ``signal = 0.7 * z_score_signal + 0.3 * (0.5 - bb_position) * 2``

        The BB component is centred so that oversold (0) → +1 and
        overbought (1) → -1.

        Returns
        -------
        dict[str, pd.Series]
            Mapping ticker -> combined mean-reversion signal.
        """
        signals: Dict[str, pd.Series] = {}
        for ticker in self.tickers:
            try:
                ticker_df = _extract_ticker_prices(self.prices, ticker)
                if "Close" not in ticker_df.columns or len(ticker_df) < 30:
                    continue
                close = ticker_df["Close"]
                returns = close.pct_change().dropna()

                z_signal = z_score_mean_reversion(returns, window=20, threshold=2.0)
                bb_pos = bollinger_band_position(close, window=20, num_std=2.0)

                # Centre BB: 0→+1 (buy), 1→-1 (sell)
                bb_contrarian = (0.5 - bb_pos) * 2.0

                # Ensemble: weight z-score higher
                combined = 0.7 * z_signal + 0.3 * bb_contrarian
                combined.name = f"{ticker}_meanrev_signal"
                signals[ticker] = combined
            except Exception as exc:
                logger.warning(
                    "Mean-reversion signal generation failed for %s: %s", ticker, exc
                )

        logger.info("Generated mean-reversion signals for %d tickers", len(signals))
        return signals

    # ------------------------------------------------------------------ #
    # Step 3: Backtest                                                   #
    # ------------------------------------------------------------------ #

    def backtest(self, signals: Dict[str, pd.Series]) -> Dict[str, Any]:
        """Run vectorised backtests for each ticker's mean-reversion signal.

        Parameters
        ----------
        signals:
            Output from :meth:`generate_signals`.

        Returns
        -------
        dict[str, BacktestResult]
            Mapping ticker -> backtest result.
        """
        engine = BacktestEngine()
        cost_model = _DEFAULT_COST_MODEL
        backtests: Dict[str, Any] = {}

        for ticker, signal in signals.items():
            try:
                ticker_df = _extract_ticker_prices(self.prices, ticker)
                result = engine.run(
                    prices=ticker_df,
                    signal=signal,
                    initial_capital=self.capital,
                    cost_model=cost_model,
                )
                backtests[ticker] = result
            except Exception as exc:
                logger.warning("Mean-reversion backtest failed for %s: %s", ticker, exc)

        logger.info("Completed %d mean-reversion backtests", len(backtests))
        return backtests

    # ------------------------------------------------------------------ #
    # Step 4: Metrics                                                    #
    # ------------------------------------------------------------------ #

    def compute_metrics(self, backtests: Dict[str, Any]) -> pd.DataFrame:
        """Compile performance metrics from backtest results.

        Parameters
        ----------
        backtests:
            Output from :meth:`backtest`.

        Returns
        -------
        pd.DataFrame
            One row per ticker, sorted by Sharpe ratio descending.
        """
        rows: Dict[str, Dict[str, float]] = {}
        for ticker, bt in backtests.items():
            rows[ticker] = _compute_metrics_row(bt)
        df = pd.DataFrame.from_dict(rows, orient="index")
        if not df.empty:
            df = df.sort_values("sharpe_ratio", ascending=False)
        return df

    # ------------------------------------------------------------------ #
    # Orchestration                                                      #
    # ------------------------------------------------------------------ #

    def run(self) -> Dict[str, Any]:
        """Execute the complete mean-reversion research pipeline.

        Returns
        -------
        dict
            Keys: ``opportunities``, ``signals``, ``backtests``,
            ``metrics``, ``hypothesis``, ``risks``.
        """
        logger.info(
            "Starting MeanReversionPipeline for %d tickers", len(self.tickers)
        )
        opportunities = self.discover_opportunities()
        signals = self.generate_signals()
        backtests = self.backtest(signals)
        metrics = self.compute_metrics(backtests)

        self.results = {
            "opportunities": opportunities,
            "signals": signals,
            "backtests": backtests,
            "metrics": metrics,
            "hypothesis": (
                "Stocks that deviate significantly from their rolling mean "
                "will revert toward the mean over the short term."
            ),
            "risks": [
                "Trend persistence can cause large losses if price continues diverging.",
                "Z-score can stay elevated for extended periods (non-stationarity).",
                "Requires disciplined stop-losses to prevent runaway losses.",
                "Low liquidity can exaggerate slippage on reversal entry/exit.",
            ],
        }
        logger.info(
            "MeanReversionPipeline complete — %d backtests run", len(backtests)
        )
        return self.results


# ---------------------------------------------------------------------------
# Arbitrage (Pairs) Pipeline
# ---------------------------------------------------------------------------

class ArbitragePipeline:
    """End-to-end statistical-arbitrage (pairs-trading) research pipeline.

    Identifies the most correlated pairs from the universe, models the
    price spread, generates z-score-based entry/exit signals, runs
    backtests on each pair, and compiles performance metrics.

    Parameters
    ----------
    prices:
        OHLCV DataFrame with MultiIndex columns ``(ticker, field)``
        or a wide DataFrame of close prices (one column per ticker).
    tickers:
        List of ticker symbols to analyse.
    capital:
        Initial capital *per pair* backtest (default $100,000).
    max_pairs:
        Maximum number of top-correlated pairs to trade (default 10).
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        tickers: List[str],
        capital: float = _INITIAL_CAPITAL,
        max_pairs: int = 10,
    ) -> None:
        self.prices = prices
        self.tickers = [t for t in tickers if t in self._available_tickers()]
        self.capital = capital
        self.max_pairs = max_pairs
        self.results: Dict[str, Any] = {}

    def _available_tickers(self) -> List[str]:
        """Return tickers that exist in the price data."""
        if isinstance(self.prices.columns, pd.MultiIndex):
            return list(self.prices.columns.get_level_values("ticker").unique())
        return list(self.prices.columns)

    def _get_close_series(self, ticker: str) -> pd.Series:
        """Extract the Close price series for a single ticker."""
        ticker_df = _extract_ticker_prices(self.prices, ticker)
        return ticker_df["Close"]

    # ------------------------------------------------------------------ #
    # Step 1: Pair discovery (correlation)                               #
    # ------------------------------------------------------------------ #

    def find_pairs(self, min_correlation: float = 0.5) -> pd.DataFrame:
        """Alias for :meth:`discover_opportunities` that filters by min correlation.

        Parameters
        ----------
        min_correlation:
            Minimum absolute correlation threshold (default 0.5).

        Returns
        -------
        pd.DataFrame
            Columns: ticker_a, ticker_b, correlation, hedge_ratio.
        """
        df = self.discover_opportunities()
        if df.empty:
            return df
        return df[df["correlation"].abs() >= min_correlation].reset_index(drop=True)

    def discover_opportunities(self) -> pd.DataFrame:
        """Find the most correlated ticker pairs.

        Computes the Pearson correlation matrix of daily close-price
        returns and returns the top *max_pairs* pairs sorted by
        absolute correlation descending.

        Returns
        -------
        pd.DataFrame
            Columns: ticker_a, ticker_b, correlation, hedge_ratio.
            The hedge_ratio is the OLS beta of *ticker_a* ~ *ticker_b*.
        """
        # Build returns matrix
        close_dict: Dict[str, pd.Series] = {}
        for ticker in self.tickers:
            try:
                s = self._get_close_series(ticker)
                if len(s) > 30:
                    close_dict[ticker] = s
            except Exception:
                continue

        if len(close_dict) < 2:
            logger.warning("Insufficient tickers for pairs discovery")
            return pd.DataFrame(columns=["ticker_a", "ticker_b", "correlation", "hedge_ratio"])

        close_df = pd.DataFrame(close_dict)
        returns_df = close_df.pct_change().dropna()

        if returns_df.empty:
            return pd.DataFrame(columns=["ticker_a", "ticker_b", "correlation", "hedge_ratio"])

        corr_matrix = returns_df.corr()
        pairs: List[Dict[str, Any]] = []

        tickers_list = list(close_dict.keys())
        for i in range(len(tickers_list)):
            for j in range(i + 1, len(tickers_list)):
                t_a, t_b = tickers_list[i], tickers_list[j]
                corr_val = float(corr_matrix.loc[t_a, t_b])
                # OLS hedge ratio: beta of t_a on t_b using log prices
                log_a = np.log(close_df[t_a].dropna())
                log_b = np.log(close_df[t_b].reindex(log_a.index).dropna())
                if len(log_b) > 1:
                    cov = np.cov(log_a.loc[log_b.index].values, log_b.values)[0, 1]
                    var_b = np.var(log_b.values)
                    beta = float(cov / var_b) if var_b > 0 else 1.0
                else:
                    beta = 1.0

                pairs.append(
                    {
                        "ticker_a": t_a,
                        "ticker_b": t_b,
                        "correlation": corr_val,
                        "abs_correlation": abs(corr_val),
                        "hedge_ratio": beta,
                    }
                )

        pairs_df = pd.DataFrame(pairs)
        if pairs_df.empty:
            return pd.DataFrame(columns=["ticker_a", "ticker_b", "correlation", "hedge_ratio"])

        pairs_df = pairs_df.sort_values("abs_correlation", ascending=False).head(
            self.max_pairs
        )
        return pairs_df.reset_index(drop=True)[["ticker_a", "ticker_b", "correlation", "hedge_ratio"]]

    # ------------------------------------------------------------------ #
    # Step 2: Spread & signal generation                                 #
    # ------------------------------------------------------------------ #

    def generate_signals(
        self,
        pairs_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, pd.Series]:
        """Generate z-score spread signals for each pair.

        The spread is defined as::

            spread = log(price_a) - hedge_ratio * log(price_b)

        A z-score is computed over a 20-day rolling window.  The signal
        is ``-z_score / 2`` (clipped to ``[-1, 1]``), i.e. go long the
        spread when it is depressed and short when elevated.

        Parameters
        ----------
        pairs_df :
            Pre-computed pair DataFrame (from :meth:`discover_opportunities`).
            If ``None``, the method calls ``discover_opportunities()``
            internally — callers should pass the result to avoid
            redundant computation.

        Returns
        -------
        dict[str, pd.Series]
            Mapping ``"A_B"`` -> spread signal series.
        """
        if pairs_df is None:
            pairs_df = self.discover_opportunities()
        signals: Dict[str, pd.Series] = {}

        for _, row in pairs_df.iterrows():
            t_a, t_b = row["ticker_a"], row["ticker_b"]
            beta = row["hedge_ratio"]
            pair_key = f"{t_a}_{t_b}"

            try:
                close_a = self._get_close_series(t_a)
                close_b = self._get_close_series(t_b)

                # Align
                common_idx = close_a.index.intersection(close_b.index)
                a_aligned = close_a.loc[common_idx]
                b_aligned = close_b.loc[common_idx]

                # Log spread
                log_a = np.log(a_aligned)
                log_b = np.log(b_aligned)
                spread = log_a - beta * log_b

                # Z-score
                rolling_mean = spread.rolling(20).mean()
                rolling_std = spread.rolling(20).std().replace(0, np.nan)
                z_score = (spread - rolling_mean) / rolling_std

                # Signal: contrarian on spread z-score
                signal = np.clip(-z_score / 2.0, -1.0, 1.0)
                signal.name = f"{pair_key}_spread_signal"
                signals[pair_key] = signal
            except Exception as exc:
                logger.warning("Pair signal generation failed for %s: %s", pair_key, exc)

        logger.info("Generated pair-trade signals for %d pairs", len(signals))
        return signals

    # ------------------------------------------------------------------ #
    # Step 3: Backtest                                                   #
    # ------------------------------------------------------------------ #

    def backtest(
        self,
        signals: Dict[str, pd.Series],
        pairs_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """Run backtests on each pair's spread signal.

        The backtest uses a *synthetic spread price* built from the
        log-spread series (exponentiated and normalised) so that the
        existing :class:`BacktestEngine` can be reused without
        modification.

        Parameters
        ----------
        signals:
            Output from :meth:`generate_signals`.
        pairs_df :
            Pre-computed pair DataFrame.  If ``None``,
            ``discover_opportunities()`` is called internally.

        Returns
        -------
        dict[str, BacktestResult]
            Mapping pair key -> backtest result.
        """
        if pairs_df is None:
            pairs_df = self.discover_opportunities()
        engine = BacktestEngine()
        cost_model = _DEFAULT_COST_MODEL
        backtests: Dict[str, Any] = {}
        pair_info = {
            f"{r['ticker_a']}_{r['ticker_b']}": (r["ticker_a"], r["ticker_b"], r["hedge_ratio"])
            for _, r in pairs_df.iterrows()
        }

        for pair_key, signal in signals.items():
            if pair_key not in pair_info:
                continue
            t_a, t_b, beta = pair_info[pair_key]

            try:
                close_a = self._get_close_series(t_a)
                close_b = self._get_close_series(t_b)

                common_idx = close_a.index.intersection(close_b.index)
                a_aligned = close_a.loc[common_idx]
                b_aligned = close_b.loc[common_idx]

                # Synthetic spread price for backtesting
                log_a = np.log(a_aligned)
                log_b = np.log(b_aligned)
                spread = log_a - beta * log_b
                spread_price = np.exp(spread - spread.mean())

                # Build a minimal OHLCV DataFrame around the spread price
                synthetic_df = pd.DataFrame(
                    {
                        "Open": spread_price,
                        "High": spread_price * 1.001,
                        "Low": spread_price * 0.999,
                        "Close": spread_price,
                        "Volume": pd.Series(1_000_000, index=spread_price.index),
                    }
                )

                result = engine.run(
                    prices=synthetic_df,
                    signal=signal,
                    initial_capital=self.capital,
                    cost_model=cost_model,
                )
                backtests[pair_key] = result
            except Exception as exc:
                logger.warning("Pair backtest failed for %s: %s", pair_key, exc)

        logger.info("Completed %d pair backtests", len(backtests))
        return backtests

    # ------------------------------------------------------------------ #
    # Step 4: Metrics                                                    #
    # ------------------------------------------------------------------ #

    def compute_metrics(self, backtests: Dict[str, Any]) -> pd.DataFrame:
        """Compile performance metrics from pair backtests.

        Parameters
        ----------
        backtests:
            Output from :meth:`backtest`.

        Returns
        -------
        pd.DataFrame
            One row per pair, sorted by Sharpe ratio descending.
        """
        rows: Dict[str, Dict[str, float]] = {}
        for pair_key, bt in backtests.items():
            rows[pair_key] = _compute_metrics_row(bt)
        df = pd.DataFrame.from_dict(rows, orient="index")
        if not df.empty:
            df = df.sort_values("sharpe_ratio", ascending=False)
        return df

    # ------------------------------------------------------------------ #
    # Orchestration                                                      #
    # ------------------------------------------------------------------ #

    def run(self) -> Dict[str, Any]:
        """Execute the complete arbitrage (pairs) research pipeline.

        Returns
        -------
        dict
            Keys: ``opportunities``, ``signals``, ``backtests``,
            ``metrics``, ``hypothesis``, ``risks``.
        """
        logger.info(
            "Starting ArbitragePipeline for %d tickers (max_pairs=%d)",
            len(self.tickers),
            self.max_pairs,
        )
        opportunities = self.discover_opportunities()
        signals = self.generate_signals(opportunities)
        backtests = self.backtest(signals, opportunities)
        metrics = self.compute_metrics(backtests)

        self.results = {
            "opportunities": opportunities,
            "signals": signals,
            "backtests": backtests,
            "metrics": metrics,
            "hypothesis": (
                "Cointegrated / highly-correlated pairs will maintain a "
                "stationary spread, allowing profitable mean-reversion trades "
                "when the spread deviates from its equilibrium."
            ),
            "risks": [
                "Correlation breakdown — pairs can decouple during market stress.",
                "Cointegration failure — the spread may become non-stationary.",
                "Hedge ratio drift — requiring continuous recalibration.",
                "Double transaction costs (two legs per trade) erode edge.",
                "Capacity constrained — limited position size in less-liquid names.",
            ],
        }
        logger.info("ArbitragePipeline complete — %d pair backtests run", len(backtests))
        return self.results


# ---------------------------------------------------------------------------
# Convenience orchestrator
# ---------------------------------------------------------------------------

def run_all_pipelines(
    output_dir: str = "reports",
    us_tickers: Optional[List[str]] = None,
    days: int = 252,
) -> Dict[str, Any]:
    """Run all three research pipelines and return combined results.

    Generates synthetic US equity data, executes the momentum,
    mean-reversion, and arbitrage pipelines, and returns a unified
    results dictionary.  Optionally creates *output_dir* for future
    report generation.

    Parameters
    ----------
    output_dir:
        Directory path for report output (created if it does not exist).
    us_tickers:
        Override list of tickers.  Defaults to
        ``["AAPL", "MSFT", "GOOGL", "AMZN", "META"]``.
    days:
        Number of trading days of synthetic data to generate.

    Returns
    -------
    dict
        Top-level keys: ``"momentum"``, ``"mean_reversion"``, ``"arbitrage"``,
        ``"combined_metrics"``, ``"output_dir"``.
    """
    from alpha_search.research.sample_universes import generate_us_equity_data

    os.makedirs(output_dir, exist_ok=True)
    tickers = us_tickers or ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    logger.info("=" * 60)
    logger.info("ALPHA SEARCH — Full Research Pipeline")
    logger.info("=" * 60)

    # Generate data
    logger.info("Generating synthetic US equity data (%d days)...", days)
    prices = generate_us_equity_data(tickers=tickers, days=days, seed=42)

    # --- Momentum ---
    logger.info("-" * 40)
    logger.info("Running MomentumPipeline...")
    mom_pipe = MomentumPipeline(prices=prices, tickers=tickers, capital=_INITIAL_CAPITAL)
    mom_results = mom_pipe.run()

    # --- Mean Reversion ---
    logger.info("-" * 40)
    logger.info("Running MeanReversionPipeline...")
    mr_pipe = MeanReversionPipeline(prices=prices, tickers=tickers, capital=_INITIAL_CAPITAL)
    mr_results = mr_pipe.run()

    # --- Arbitrage ---
    logger.info("-" * 40)
    logger.info("Running ArbitragePipeline...")
    arb_pipe = ArbitragePipeline(
        prices=prices, tickers=tickers, capital=_INITIAL_CAPITAL, max_pairs=10
    )
    arb_results = arb_pipe.run()

    # Combined metrics summary
    combined_metrics = pd.DataFrame(
        {
            "momentum": mom_results["metrics"].mean()
            if not mom_results["metrics"].empty
            else pd.Series(dtype=float),
            "mean_reversion": mr_results["metrics"].mean()
            if not mr_results["metrics"].empty
            else pd.Series(dtype=float),
            "arbitrage": arb_results["metrics"].mean()
            if not arb_results["metrics"].empty
            else pd.Series(dtype=float),
        }
    )

    from datetime import datetime, timezone

    combined = {
        "momentum": mom_results,
        "mean_reversion": mr_results,
        "arbitrage": arb_results,
        "combined_metrics": combined_metrics,
        "output_dir": output_dir,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "RESEARCH / EDUCATIONAL PURPOSES ONLY. NOT INVESTMENT ADVICE.",
    }

    logger.info("=" * 60)
    logger.info("All pipelines complete")
    logger.info(
        "  Momentum:      %d backtests",
        len(mom_results.get("backtests", {})),
    )
    logger.info(
        "  Mean Reversion: %d backtests",
        len(mr_results.get("backtests", {})),
    )
    logger.info(
        "  Arbitrage:     %d pair backtests",
        len(arb_results.get("backtests", {})),
    )
    logger.info("=" * 60)

    return combined
