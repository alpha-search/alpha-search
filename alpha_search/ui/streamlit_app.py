"""Streamlit UI for Alpha Search interactive research and backtesting.

This module is import-safe: it only accesses streamlit APIs when ``main()``
is called.  Importing the module (e.g. ``from alpha_search.ui import streamlit_main``)
does **not** require a Streamlit runtime.
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from alpha_search.backtest.costs import CostModel
from alpha_search.backtest.engine import BacktestEngine
from alpha_search.data.providers import ProviderRegistry
from alpha_search.signals.technical import (
    bollinger_band_position,
    ma_crossover,
    momentum,
    rsi,
    z_score_mean_reversion,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar(st: Any) -> Dict[str, Any]:
    """Render the sidebar and return user inputs.

    Args:
        st: The ``streamlit`` module (injected so the file stays import-safe).
    """
    with st.sidebar:
        st.title("📊 Alpha Search")
        st.markdown("*The Operating System for Quantitative Research*")
        st.divider()

        st.header("Settings")

        ticker = st.text_input("Ticker Symbol", value="AAPL").upper().strip()

        col1, col2 = st.columns(2)
        with col1:
            default_start = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
            start_date = st.date_input("Start Date", value=pd.to_datetime(default_start))
        with col2:
            default_end = datetime.now().strftime("%Y-%m-%d")
            end_date = st.date_input("End Date", value=pd.to_datetime(default_end))

        st.divider()
        st.header("Backtest Settings")

        initial_capital = st.number_input(
            "Initial Capital ($)",
            min_value=1000.0,
            max_value=10_000_000.0,
            value=100_000.0,
            step=1000.0,
        )
        commission = st.number_input(
            "Commission (per trade)",
            min_value=0.0,
            max_value=0.1,
            value=0.001,
            step=0.0001,
            format="%.4f",
        )
        slippage = st.number_input(
            "Slippage (per trade)",
            min_value=0.0,
            max_value=0.1,
            value=0.001,
            step=0.0001,
            format="%.4f",
        )

        st.divider()
        st.markdown("**Version:** 0.1.0")
        st.markdown("**Mode:** Paper Trading Only")

    return {
        "ticker": ticker,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "initial_capital": initial_capital,
        "commission": commission,
        "slippage": slippage,
    }


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

# Module-level cache dict so we don't depend on ``st.cache_data`` at import time.
_price_cache: Dict[str, pd.DataFrame] = {}


def _cache_key(ticker: str, start: str, end: str) -> str:
    return f"{ticker}::{start}::{end}"


def fetch_prices(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Fetch prices with an in-memory LRU cache."""
    key = _cache_key(ticker, start, end)
    if key in _price_cache:
        logger.debug("Cache hit for %s", key)
        return _price_cache[key]

    try:
        registry = ProviderRegistry()
        df = registry.get_prices(ticker, start, end)
        if df is not None and not df.empty:
            _price_cache[key] = df
        return df
    except Exception as exc:
        logger.error("Failed to fetch data for %s: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------


def render_price_chart(st: Any, df: pd.DataFrame, ticker: str) -> None:
    """Render an interactive candlestick or line chart."""
    fig = go.Figure()

    has_ohlc = all(c in df.columns for c in ["Open", "High", "Low", "Close"])

    if has_ohlc and len(df) > 0:
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name=ticker,
            )
        )
    elif "Close" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                name=ticker,
                line=dict(color="#1f77b4", width=1.5),
            )
        )

    fig.update_layout(
        title=f"{ticker} Price Chart",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        xaxis_rangeslider_visible=False,
        height=500,
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_equity_curve(st: Any, equity: pd.Series) -> None:
    """Render the equity curve from a backtest."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity.index,
            y=equity.values,
            mode="lines",
            name="Equity",
            line=dict(color="#2ecc71", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(46, 204, 113, 0.1)",
        )
    )

    fig.add_hline(
        y=equity.iloc[0],
        line_dash="dash",
        line_color="gray",
        annotation_text="Initial Capital",
    )

    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        height=400,
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_drawdown_chart(st: Any, equity: pd.Series) -> None:
    """Render the drawdown chart."""
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax * 100

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode="lines",
            name="Drawdown",
            line=dict(color="#e74c3c", width=1),
            fill="tozeroy",
            fillcolor="rgba(231, 76, 60, 0.1)",
        )
    )
    fig.update_layout(
        title="Drawdown (%)",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        height=300,
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


def generate_signal(df: pd.DataFrame, signal_type: str) -> pd.Series:
    """Generate a signal series based on the selected type."""
    close = df["Close"]

    if signal_type == "Momentum (20-day)":
        return momentum(close, window=20)
    elif signal_type == "MA Crossover (20/50)":
        return ma_crossover(close, short=20, long=50)
    elif signal_type == "Z-Score Mean Reversion":
        returns = close.pct_change().fillna(0)
        return z_score_mean_reversion(returns, window=20, threshold=2.0)
    elif signal_type == "RSI":
        return rsi(close, window=14)
    elif signal_type == "Bollinger Band Position":
        return bollinger_band_position(close, window=20)
    else:
        return pd.Series(0.5, index=close.index, name="neutral")


# ---------------------------------------------------------------------------
# Metrics display
# ---------------------------------------------------------------------------


def render_metrics_table(st: Any, metrics: Dict[str, float]) -> None:
    """Render a styled metrics table."""
    if not metrics:
        st.info("No metrics available.")
        return

    display_data: List[Dict[str, str]] = []
    for key, value in metrics.items():
        if isinstance(value, float) and any(k in key for k in ("return", "drawdown", "rate", "volatility")):
            display_data.append({"Metric": key, "Value": f"{value * 100:.2f}%"})
        elif key in ("num_days", "num_trades"):
            display_data.append({"Metric": key, "Value": f"{int(value):,}"})
        elif isinstance(value, float):
            display_data.append({"Metric": key, "Value": f"{value:.4f}"})
        else:
            display_data.append({"Metric": key, "Value": str(value)})

    df_metrics = pd.DataFrame(display_data)
    st.dataframe(df_metrics, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main() -> None:
    """Main Streamlit application entry point."""
    import streamlit as st

    st.set_page_config(
        page_title="Alpha Search",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    settings = render_sidebar(st)

    ticker = settings["ticker"]
    start = settings["start_date"]
    end = settings["end_date"]

    st.title(f"🔬 Quant Research: {ticker}")

    # --- Data Section ---
    st.header("📈 Price Data")
    col1, col2 = st.columns([3, 1])

    with col1:
        fetch_clicked = st.button("🔄 Fetch Data", type="primary")

    if fetch_clicked or "df" in st.session_state:
        if fetch_clicked:
            with st.spinner(f"Fetching {ticker} data from {start} to {end}..."):
                df = fetch_prices(ticker, start, end)
                if df is not None:
                    st.session_state.df = df
                    st.session_state.ticker = ticker
        else:
            df = st.session_state.get("df")

        if df is not None and not df.empty:
            st.success(f"Loaded {len(df)} rows for {ticker}")
            render_price_chart(st, df, ticker)

            with st.expander("📋 Data Summary"):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Rows", len(df))
                with c2:
                    if "Close" in df.columns:
                        st.metric("Latest Close", f"${df['Close'].iloc[-1]:.2f}")
                with c3:
                    if "Volume" in df.columns:
                        st.metric("Avg Volume", f"{df['Volume'].mean():,.0f}")
                with c4:
                    if "Close" in df.columns:
                        total_ret = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
                        st.metric("Period Return", f"{total_ret:.2f}%")

                st.dataframe(df.tail(10), use_container_width=True)
        else:
            st.error("No data available. Please check the ticker symbol and date range.")
            return
    else:
        st.info("Click 'Fetch Data' to load price data.")
        return

    # --- Signal Section ---
    st.divider()
    st.header("📡 Signal Generation")

    df = st.session_state.df
    signal_type = st.selectbox(
        "Select Signal",
        options=[
            "Momentum (20-day)",
            "MA Crossover (20/50)",
            "Z-Score Mean Reversion",
            "RSI",
            "Bollinger Band Position",
        ],
        index=0,
    )

    signal = generate_signal(df, signal_type)

    fig_signal = go.Figure()
    fig_signal.add_trace(
        go.Scatter(
            x=signal.index,
            y=signal.values,
            mode="lines",
            name=signal_type,
            line=dict(color="#9b59b6", width=1.5),
        )
    )
    fig_signal.update_layout(
        title=f"Signal: {signal_type}",
        xaxis_title="Date",
        yaxis_title="Signal Value",
        height=300,
        template="plotly_white",
    )
    st.plotly_chart(fig_signal, use_container_width=True)

    # --- Backtest Section ---
    st.divider()
    st.header("🧪 Backtest")

    run_clicked = st.button("▶️ Run Backtest", type="primary")

    if run_clicked:
        with st.spinner("Running backtest..."):
            cost_model = CostModel(
                commission=settings["commission"],
                slippage=settings["slippage"],
            )
            engine = BacktestEngine()
            result = engine.run(
                df,
                signal,
                initial_capital=settings["initial_capital"],
                cost_model=cost_model,
            )

            st.session_state.backtest_result = result

        if hasattr(st.session_state, "backtest_result"):
            result = st.session_state.backtest_result

            st.subheader("Equity Curve")
            render_equity_curve(st, result.equity_curve)

            st.subheader("Drawdown")
            render_drawdown_chart(st, result.equity_curve)

            st.subheader("Performance Metrics")
            render_metrics_table(st, result.metrics)

            st.subheader("Trade Log")
            if not result.trades.empty:
                st.dataframe(result.trades, use_container_width=True, hide_index=True)
            else:
                st.info("No trades generated.")

            st.text(result.summary())


if __name__ == "__main__":
    main()
