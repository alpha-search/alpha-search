"""Walk-forward validation for backtesting strategies."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.backtest.metrics import Metrics
from alpha_search.core.errors import BacktestError

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """Walk-forward analysis to detect overfitting.

    Splits the data into consecutive train / test windows, fits the
    signal on the in-sample (train) data and evaluates on the
    out-of-sample (test) data.

    Example::

        wfv = WalkForwardValidator()
        results = wfv.run(
            prices,
            signal_func=lambda df: ma_crossover(df["Close"]),
            train_size=252,
            test_size=63,
            step=63,
        )
    """

    def __init__(self) -> None:
        self.engine = BacktestEngine()
        self.metrics = Metrics()

    def run(
        self,
        prices: pd.DataFrame,
        signal_func: Callable[[pd.DataFrame], pd.Series],
        train_size: int,
        test_size: int,
        step: int,
        initial_capital: float = 100000.0,
        cost_model: Optional[CostModel] = None,
    ) -> pd.DataFrame:
        """Run walk-forward validation.

        Args:
            prices: OHLCV DataFrame with a DatetimeIndex.
            signal_func: Callable that takes a price DataFrame and returns
                a signal Series.
            train_size: Number of days in the training window.
            test_size: Number of days in the test window.
            step: Number of days to advance the window each iteration.
            initial_capital: Starting capital for each test backtest.
            cost_model: Optional transaction cost model.

        Returns:
            DataFrame where each row is one walk-forward split with
            in-sample and out-of-sample metrics.
        """
        if prices is None or prices.empty:
            raise BacktestError("prices is empty", stage="wfv")
        if "Close" not in prices.columns:
            raise BacktestError("prices must have 'Close' column", stage="wfv")
        if len(prices) < train_size + test_size:
            raise BacktestError(
                f"Not enough data for walk-forward: {len(prices)} rows, "
                f"need at least {train_size + test_size}",
                stage="wfv",
            )

        n = len(prices)
        results: List[Dict[str, object]] = []

        test_start = train_size
        split_idx = 0

        while test_start + test_size <= n:
            train_end = test_start
            train_df = prices.iloc[:train_end]
            test_df = prices.iloc[test_start : test_start + test_size]

            # Generate signal on the full history up to test end
            # (In practice the signal_func should only use train data for fitting)
            try:
                signal = signal_func(prices.iloc[: test_start + test_size])
            except Exception as exc:
                logger.warning("Signal generation failed on split %d: %s", split_idx, exc)
                test_start += step
                split_idx += 1
                continue

            # In-sample backtest (train period only)
            is_signal = signal.reindex(train_df.index).ffill().fillna(0.0)
            is_result = self.engine.run(
                train_df, is_signal, initial_capital, cost_model
            )
            is_metrics = is_result.metrics

            # Out-of-sample backtest (test period only)
            oos_signal = signal.reindex(test_df.index).ffill().fillna(0.0)
            oos_result = self.engine.run(
                test_df, oos_signal, initial_capital, cost_model
            )
            oos_metrics = oos_result.metrics

            row: Dict[str, object] = {
                "split": split_idx,
                "train_start": str(train_df.index[0]),
                "train_end": str(train_df.index[-1]),
                "test_start": str(test_df.index[0]),
                "test_end": str(test_df.index[-1]),
                "is_total_return": is_metrics.get("total_return", np.nan),
                "is_sharpe": is_metrics.get("sharpe_ratio", np.nan),
                "is_max_dd": is_metrics.get("max_drawdown", np.nan),
                "oos_total_return": oos_metrics.get("total_return", np.nan),
                "oos_sharpe": oos_metrics.get("sharpe_ratio", np.nan),
                "oos_max_dd": oos_metrics.get("max_drawdown", np.nan),
                "sharpe_degradation": self.degradation(is_metrics, oos_metrics, "sharpe_ratio"),
            }
            results.append(row)
            logger.info(
                "WFV split %d: IS sharpe=%.3f -> OOS sharpe=%.3f",
                split_idx,
                is_metrics.get("sharpe_ratio", np.nan),
                oos_metrics.get("sharpe_ratio", np.nan),
            )

            test_start += step
            split_idx += 1

        if not results:
            logger.warning("Walk-forward produced no splits.")
            return pd.DataFrame()

        return pd.DataFrame(results)

    @staticmethod
    def degradation(
        is_metrics: Dict[str, float],
        oos_metrics: Dict[str, float],
        key: str = "sharpe_ratio",
    ) -> float:
        """Compute metric degradation from in-sample to out-of-sample.

        Returns ``1.0 - (OOS / IS)``, so a value of ``0.0`` means no
        degradation and ``1.0`` means complete loss of performance.
        """
        is_val = is_metrics.get(key)
        oos_val = oos_metrics.get(key)
        if is_val is None or oos_val is None:
            return np.nan
        if is_val == 0:
            return 0.0 if oos_val == 0 else 1.0
        return float(1.0 - oos_val / is_val)
