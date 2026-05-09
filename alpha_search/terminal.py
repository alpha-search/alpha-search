"""Terminal facade - the main entry point for Alpha Search."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.backtest.metrics import Metrics
from alpha_search.data.providers import ProviderRegistry
from alpha_search.signals.technical import (
    ma_crossover,
    momentum,
    z_score_mean_reversion,
)

logger = logging.getLogger(__name__)


class Terminal:
    """Alpha Search Terminal - unified facade for quantitative research.

    Provides convenient access to data fetching, signal generation,
    backtesting, and reporting from a single entry point.

    Example::

        t = Terminal(universe=["AAPL", "MSFT"], start_date="2020-01-01", end_date="2023-12-31")
        df = t.data.get_prices("AAPL", "2020-01-01", "2023-12-31")
        result = t.backtest.run(df, signal_series)
    """

    def __init__(
        self,
        universe: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> None:
        """Initialize the Alpha Search Terminal.

        Args:
            universe: Default list of tickers to work with.
            start_date: Default start date (YYYY-MM-DD).
            end_date: Default end date (YYYY-MM-DD).
        """
        from datetime import datetime, timedelta

        self.universe = universe or []
        self.start_date = start_date or (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        self.end_date = end_date or datetime.now().strftime("%Y-%m-%d")

        # Sub-systems
        self.data = ProviderRegistry()
        self.backtest = BacktestEngine()

        # Signals namespace
        self.signals = _SignalsNamespace()

        logger.info(
            "Alpha Search Terminal initialized: universe=%s dates=%s to %s",
            self.universe,
            self.start_date,
            self.end_date,
        )

    # ------------------------------------------------------------------
    # Streamlit launcher
    # ------------------------------------------------------------------

    def run_terminal(self) -> None:
        """Launch the Streamlit interactive terminal."""
        app_path = Path(__file__).parent / "ui" / "streamlit_app.py"
        if not app_path.exists():
            raise FileNotFoundError(f"Streamlit app not found at {app_path}")

        cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
        logger.info("Launching Streamlit: %s", " ".join(cmd))
        subprocess.run(cmd)

    # ------------------------------------------------------------------
    # Research report
    # ------------------------------------------------------------------

    def research_report(self, ticker: str) -> Dict[str, Any]:
        """Generate a comprehensive research report for a single ticker.

        Fetches price data, computes multiple signals, runs backtests,
        and returns a summary dictionary.

        Args:
            ticker: Ticker symbol.

        Returns:
            Dictionary with price data, signals, backtest results, and metrics.
        """
        logger.info("Generating research report for %s", ticker)

        # Fetch data
        df = self.data.get_prices(ticker, self.start_date, self.end_date)
        if df.empty or "Close" not in df.columns:
            return {"error": f"No data available for {ticker}"}

        close = df["Close"]

        # Generate signals
        sig_momentum = momentum(close, window=20)
        sig_ma_cross = ma_crossover(close, short=20, long=50)
        sig_zscore = z_score_mean_reversion(close.pct_change().fillna(0), window=20)

        # Run backtests
        cost_model = CostModel(commission=0.001, slippage=0.001)

        result_mom = self.backtest.run(df, sig_momentum, cost_model=cost_model)
        result_ma = self.backtest.run(df, sig_ma_cross, cost_model=cost_model)
        result_zs = self.backtest.run(df, sig_zscore, cost_model=cost_model)

        # Price statistics
        returns = close.pct_change().dropna()
        price_stats = {
            "ticker": ticker,
            "start_date": str(df.index[0]),
            "end_date": str(df.index[-1]),
            "n_days": len(df),
            "latest_price": float(close.iloc[-1]),
            "total_return": float(close.iloc[-1] / close.iloc[0] - 1),
            "annualized_volatility": float(returns.std() * np.sqrt(252)),
            "avg_daily_return": float(returns.mean()),
        }

        report = {
            "price_statistics": price_stats,
            "signals": {
                "momentum": self._signal_summary(sig_momentum),
                "ma_crossover": self._signal_summary(sig_ma_cross),
                "z_score": self._signal_summary(sig_zscore),
            },
            "backtests": {
                "momentum": {
                    "total_return": result_mom.total_return,
                    "sharpe": result_mom.metrics.get("sharpe_ratio", 0),
                    "max_drawdown": result_mom.metrics.get("max_drawdown", 0),
                    "n_trades": result_mom.n_trades,
                    "metrics": result_mom.metrics,
                },
                "ma_crossover": {
                    "total_return": result_ma.total_return,
                    "sharpe": result_ma.metrics.get("sharpe_ratio", 0),
                    "max_drawdown": result_ma.metrics.get("max_drawdown", 0),
                    "n_trades": result_ma.n_trades,
                    "metrics": result_ma.metrics,
                },
                "z_score": {
                    "total_return": result_zs.total_return,
                    "sharpe": result_zs.metrics.get("sharpe_ratio", 0),
                    "max_drawdown": result_zs.metrics.get("max_drawdown", 0),
                    "n_trades": result_zs.n_trades,
                    "metrics": result_zs.metrics,
                },
            },
        }

        logger.info("Research report complete for %s", ticker)
        return report

    @staticmethod
    def _signal_summary(signal: pd.Series) -> Dict[str, Any]:
        """Create a summary dict for a signal series."""
        clean = signal.dropna()
        if clean.empty:
            return {"mean": 0, "std": 0, "min": 0, "max": 0, "n": 0}
        return {
            "mean": float(clean.mean()),
            "std": float(clean.std()),
            "min": float(clean.min()),
            "max": float(clean.max()),
            "n": len(clean),
        }

    def __repr__(self) -> str:
        return (
            f"<Terminal universe={self.universe} "
            f"dates={self.start_date}:{self.end_date}>"
        )


def main() -> None:
    """CLI entry point: launch the Alpha Search Streamlit terminal."""
    import argparse
    parser = argparse.ArgumentParser(description="Alpha Search Terminal")
    parser.add_argument("--universe", nargs="+", default=["AAPL"], help="Ticker universe")
    parser.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    t = Terminal(universe=args.universe, start_date=args.start, end_date=args.end)
    print(f"Alpha Search Terminal ready: {t}")
    t.run_terminal()


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Signals namespace
# ---------------------------------------------------------------------------


class _SignalsNamespace:
    """Convenient namespace for signal generation functions.

    Accessed via ``terminal.signals.momentum(...)`` etc.
    """

    @staticmethod
    def momentum(prices: pd.Series, window: int = 20) -> pd.Series:
        """Returns-based momentum signal."""
        return momentum(prices, window=window)

    @staticmethod
    def ma_crossover(prices: pd.Series, short: int = 20, long: int = 50) -> pd.Series:
        """Moving average crossover signal."""
        return ma_crossover(prices, short=short, long=long)

    @staticmethod
    def z_score(returns: pd.Series, window: int = 20, threshold: float = 2.0) -> pd.Series:
        """Z-score mean reversion signal."""
        return z_score_mean_reversion(returns, window=window, threshold=threshold)